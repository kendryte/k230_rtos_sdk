#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import zlib

from pathlib import Path
from typing import Dict, List, Optional, Tuple

from gmssl import func, sm3

from genimage_py.image_kd import KD_ALIGNMENT, KDIMG_CONTENT_START_OFFSET, KdImgHdr, KdImgPart

import image_tools


OTP_KEY_LEN = 32
KBURN_VALID_OTP_SIZE = 1024
KBURN_OTP_SIZE = KBURN_VALID_OTP_SIZE * 2
KBURN_LOCK_REGION_OFFSET = KBURN_VALID_OTP_SIZE
KBURN_OTP_LOCK_RO_FLAG = 0x12345678
KBURN_OTP_LOCK_NA_FLAG = 0xDEADBEEF

LOCK_POLICY = {
    "symmetric_key": "NA",
    "public_key_hash": "RO",
}

STAGE_SLOT_POLICY = {
    "spl": {
        1: {
            "mode": "sm4_sm2",
            "key_slot": 4,
            "hash_slot": 7,
        },
        2: {
            "mode": "aes_rsa",
            "key_slot": 2,
            "hash_slot": 6,
        },
    },
    "firmware": {
        1: {
            "mode": "sm4_sm2",
            "key_slot": 5,
            "hash_slot": 9,
        },
        2: {
            "mode": "aes_rsa",
            "key_slot": 3,
            "hash_slot": 8,
        },
    },
}


def slot_addr(slot_index: int) -> int:
    return slot_index * OTP_KEY_LEN


def little_endian_u32(value: int) -> bytes:
    return value.to_bytes(4, byteorder="little", signed=True)


def compute_rsa_pubkey_hash(config: image_tools.FirmwareConfig) -> bytes:
    pubkey = config.RSA_MODULUS + little_endian_u32(int(config.RSA_EXPONENT, 0))
    return hashlib.sha256(pubkey).digest()


def compute_sm2_pubkey_hash(config: image_tools.FirmwareConfig) -> bytes:
    id_len_bytes = little_endian_u32(len(config.SM2_ID))
    id_padded = config.SM2_ID + b"\x00" * (512 - 32 * 4 - len(config.SM2_ID))
    pubkey = id_len_bytes + id_padded + config.SM2_PUBLIC_KEY_X + config.SM2_PUBLIC_KEY_Y
    return bytes.fromhex(sm3.sm3_hash(func.bytes_to_list(pubkey)))


def infer_secure_boot_type_from_config(config_path: str, stage: str) -> int:
    config = image_tools.FirmwareConfig.from_file(config_path, section_name=stage)

    has_aes_rsa = (
        config.AES_KEY is not None and
        len(config.AES_KEY) == 32 and
        config.RSA_MODULUS is not None and
        len(config.RSA_MODULUS) > 0 and
        config.RSA_EXPONENT is not None
    )
    has_sm4_sm2 = (
        config.SM4_KEY is not None and
        len(config.SM4_KEY) == 16 and
        config.SM2_PUBLIC_KEY_X is not None and
        len(config.SM2_PUBLIC_KEY_X) > 0 and
        config.SM2_PUBLIC_KEY_Y is not None and
        config.SM2_ID is not None
    )

    if has_aes_rsa and has_sm4_sm2:
        raise ValueError(
            f"Secure boot type is ambiguous for {config_path}; use --config with the top-level .config"
        )
    if has_aes_rsa:
        return 2
    if has_sm4_sm2:
        return 1

    raise ValueError(f"Unable to infer secure boot type from {config_path}")


def build_stage_entries(stage: str, secure_boot_type: int, config_path: str) -> dict:
    config = image_tools.FirmwareConfig.from_file(config_path, section_name=stage)

    if secure_boot_type not in (1, 2):
        raise ValueError(f"Unsupported secure boot type {secure_boot_type} for stage {stage}")

    policy = STAGE_SLOT_POLICY[stage][secure_boot_type]

    if secure_boot_type == 2:
        if config.AES_KEY is None or config.RSA_MODULUS is None or config.RSA_EXPONENT is None:
            raise ValueError(f"Missing AES/RSA material for {stage} in {config_path}")
        symmetric_key = config.AES_KEY
        public_key_hash = compute_rsa_pubkey_hash(config)
    else:
        if config.SM4_KEY is None or config.SM2_PUBLIC_KEY_X is None or config.SM2_PUBLIC_KEY_Y is None or config.SM2_ID is None:
            raise ValueError(f"Missing SM4/SM2 material for {stage} in {config_path}")
        symmetric_key = config.SM4_KEY
        public_key_hash = compute_sm2_pubkey_hash(config)

    return {
        "stage": stage,
        "config": str(Path(config_path).resolve()),
        "type": secure_boot_type,
        "mode": policy["mode"],
        "entries": [
            {
                "purpose": "symmetric_key",
                "slot": f"OTPKEY_{policy['key_slot']}",
                "slot_index": policy["key_slot"],
                "raw_otp_addr": slot_addr(policy["key_slot"]),
                "lock": LOCK_POLICY["symmetric_key"],
                "value_hex": symmetric_key.hex(),
            },
            {
                "purpose": "public_key_hash",
                "slot": f"OTPKEY_{policy['hash_slot']}",
                "slot_index": policy["hash_slot"],
                "raw_otp_addr": slot_addr(policy["hash_slot"]),
                "lock": LOCK_POLICY["public_key_hash"],
                "value_hex": public_key_hash.hex(),
            },
        ],
    }


def resolve_secure_boot_stage_config(
    kconfig: dict,
    enable_key: str,
    type_key: str,
) -> Optional[Tuple[int, str]]:
    secure_boot_type, secure_boot_config = image_tools.resolve_secure_boot_stage_settings(
        kconfig,
        enable_key,
        type_key,
    )
    if secure_boot_type == 0 or secure_boot_config is None:
        return None

    return secure_boot_type, secure_boot_config


def lock_flag_to_word(lock_mode: Optional[str]) -> Optional[int]:
    if lock_mode is None:
        return None
    if lock_mode == "RO":
        return KBURN_OTP_LOCK_RO_FLAG
    if lock_mode == "NA":
        return KBURN_OTP_LOCK_NA_FLAG
    raise ValueError(f"Unsupported lock mode: {lock_mode}")


def roundup(value: int, alignment: int) -> int:
    return ((value + alignment - 1) // alignment) * alignment


def calculate_crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def resolve_kdimg_board_info() -> str:
    board_dir = image_tools.get_optional_env_path("SDK_BOARD_DIR")
    if board_dir:
        return Path(board_dir).name

    return "secure_boot"


def build_kdimg(parts: List[Tuple[str, int, bytes]]) -> bytes:
    if not parts:
        raise ValueError("kdimg requires at least one part")

    next_content_offset = KDIMG_CONTENT_START_OFFSET
    part_records: List[Tuple[KdImgPart, bytes]] = []

    for part_name, part_offset, content in parts:
        part_content_size = len(content)
        part = KdImgPart(
            part_offset=part_offset,
            part_size=part_content_size,
            part_max_size=part_content_size,
            part_content_offset=next_content_offset,
            part_content_size=part_content_size,
            part_content_sha256=hashlib.sha256(content).digest(),
            part_name=part_name,
        )
        part_records.append((part, content))
        next_content_offset += roundup(part_content_size, KD_ALIGNMENT)

    part_table_data = b"".join(part.to_bytes() for part, _ in part_records)
    header = KdImgHdr(
        part_tbl_num=len(part_records),
        part_tbl_crc32=calculate_crc32(part_table_data),
        image_info="otp",
        chip_info="K230",
        board_info=resolve_kdimg_board_info(),
    )
    header.img_hdr_crc32 = calculate_crc32(header.to_bytes())

    image = bytearray(next_content_offset)
    image[:len(header.to_bytes())] = header.to_bytes()
    image[512:512 + len(part_table_data)] = part_table_data

    for part, content in part_records:
        start = part.part_content_offset
        image[start:start + len(content)] = content

    return bytes(image)


def build_otp_regions(stages: List[dict]) -> Tuple[bytearray, bytearray]:
    otp_data = bytearray(KBURN_VALID_OTP_SIZE)
    otp_lock_region = bytearray(KBURN_VALID_OTP_SIZE)
    written_slots: Dict[int, bytes] = {}
    lock_slots: Dict[int, int] = {}

    for stage in stages:
        for entry in stage["entries"]:
            slot_offset = int(entry["raw_otp_addr"])
            value = bytes.fromhex(entry["value_hex"])

            if slot_offset + len(value) > KBURN_VALID_OTP_SIZE:
                raise ValueError(f"OTP entry exceeds writable OTP range: {entry['slot']}")

            existing_value = written_slots.get(slot_offset)
            if existing_value is not None and existing_value != value:
                raise ValueError(f"Conflicting OTP data for offset 0x{slot_offset:03x}")

            written_slots[slot_offset] = value
            otp_data[slot_offset:slot_offset + len(value)] = value

            lock_word = lock_flag_to_word(entry.get("lock"))
            if lock_word is None:
                continue

            existing_lock = lock_slots.get(slot_offset)
            if existing_lock is not None and existing_lock != lock_word:
                raise ValueError(f"Conflicting OTP lock mode for offset 0x{slot_offset:03x}")

            lock_slots[slot_offset] = lock_word
            lock_bytes = int(lock_word).to_bytes(4, byteorder="little", signed=False)
            for word_offset in range(0, OTP_KEY_LEN, 4):
                otp_lock_region[slot_offset + word_offset:slot_offset + word_offset + 4] = lock_bytes

    return otp_data, otp_lock_region


def resolve_default_output_dir(output_arg: Optional[str]) -> Path:
    if output_arg:
        return Path(output_arg).resolve().parent

    build_images_dir = image_tools.get_optional_env_path("SDK_BUILD_IMAGES_DIR")
    if build_images_dir:
        return Path(build_images_dir) / "uboot"

    board_dir = image_tools.get_optional_env_path("SDK_BOARD_DIR")
    if board_dir:
        return Path(board_dir)

    return Path.cwd()


def resolve_default_output(output_arg: Optional[str]) -> Path:
    if output_arg:
        return Path(output_arg)

    build_images_dir = image_tools.get_optional_env_path("SDK_BUILD_IMAGES_DIR")
    if build_images_dir:
        return Path(build_images_dir) / "uboot" / "otp_config.json"

    board_dir = image_tools.get_optional_env_path("SDK_BOARD_DIR")
    if board_dir:
        return Path(board_dir) / "otp_config.json"

    return Path("otp_config.json")


def cleanup_outputs(paths: List[Path]) -> None:
    for path in paths:
        if path.exists():
            path.unlink()


def resolve_stage_results(args: argparse.Namespace) -> List[dict]:
    if args.config:
        kconfig = image_tools.parse_kconfig(args.config)
        stages: List[dict] = []

        spl_config = resolve_secure_boot_stage_config(
            kconfig,
            "CONFIG_SECURE_BOOT_SPL_ENABLE",
            "CONFIG_SECURE_BOOT_SPL_TYPE",
        )
        if spl_config:
            spl_type, spl_config_path = spl_config
            stages.append(build_stage_entries("spl", spl_type, spl_config_path))

        firmware_type, firmware_config_path = image_tools.resolve_downstream_secure_boot_settings(kconfig)
        if firmware_type != 0 and firmware_config_path is not None:
            stages.append(build_stage_entries("firmware", firmware_type, firmware_config_path))

        return stages

    stages = []
    if args.spl_config:
        spl_config_path = image_tools.resolve_config_path(args.spl_config)
        stages.append(build_stage_entries("spl", infer_secure_boot_type_from_config(spl_config_path, "spl"), spl_config_path))
    if args.firmware_config:
        firmware_config_path = image_tools.resolve_config_path(args.firmware_config)
        stages.append(build_stage_entries("firmware", infer_secure_boot_type_from_config(firmware_config_path, "firmware"), firmware_config_path))
    return stages


def burn_file_info(name: str, path: Path, offset: int, size: int) -> dict:
    return {
        "name": name,
        "file": str(path.resolve()),
        "offset": offset,
        "size": size,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate burner-ready OTP data for K230 secure boot")
    parser.add_argument("--config", help="Path to the top-level .config file")
    parser.add_argument("--spl-config", help="SPL secure config file name or path")
    parser.add_argument("--firmware-config", help="Downstream firmware secure config file name or path")
    parser.add_argument("-o", "--output", help="Output OTP config JSON path")
    parser.add_argument("--bin-output", help="Output burner-ready OTP data image path")
    parser.add_argument("--lock-output", help="Output post-verify OTP key-lock image path")
    parser.add_argument("--full-output", help="Output full burner-ready OTP medium image path")
    args = parser.parse_args()

    if args.config and (args.spl_config or args.firmware_config):
        parser.error("--config cannot be used together with --spl-config or --firmware-config")

    if not args.config and not args.spl_config and not args.firmware_config:
        parser.error("At least one of --config, --spl-config, or --firmware-config is required")

    output_path = resolve_default_output(args.output)
    output_dir = resolve_default_output_dir(args.output)
    bin_output_path = Path(args.bin_output) if args.bin_output else output_dir / "otp_data.kdimg"
    lock_output_path = Path(args.lock_output) if args.lock_output else output_dir / "otp_key_lock.kdimg"
    full_output_path = Path(args.full_output) if args.full_output else output_dir / "otp_full.kdimg"

    stages = resolve_stage_results(args)

    if not stages:
        cleanup_outputs([output_path, bin_output_path, lock_output_path, full_output_path])
        print("Secure boot is not enabled, no OTP data generated")
        return

    result = {
        "slot_policy": {
            "spl": STAGE_SLOT_POLICY["spl"],
            "firmware": STAGE_SLOT_POLICY["firmware"],
        },
        "stages": stages,
        "burn_files": [
            burn_file_info("otp_data", bin_output_path, 0, KBURN_VALID_OTP_SIZE),
            burn_file_info("otp_key_lock", lock_output_path, KBURN_LOCK_REGION_OFFSET, KBURN_VALID_OTP_SIZE),
            burn_file_info("otp_full", full_output_path, 0, KBURN_OTP_SIZE),
        ],
    }

    otp_data, otp_lock_region = build_otp_regions(stages)
    otp_data_image = build_kdimg([
        ("otp_data", 0, bytes(otp_data)),
    ])
    otp_key_lock = build_kdimg([
        ("otp_key_lock", KBURN_LOCK_REGION_OFFSET, bytes(otp_lock_region)),
    ])
    otp_full = build_kdimg([
        ("otp_data", 0, bytes(otp_data)),
        ("otp_key_lock", KBURN_LOCK_REGION_OFFSET, bytes(otp_lock_region)),
    ])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(result, output_file, indent=2)
        output_file.write("\n")

    bin_output_path.parent.mkdir(parents=True, exist_ok=True)
    bin_output_path.write_bytes(otp_data_image)

    lock_output_path.parent.mkdir(parents=True, exist_ok=True)
    lock_output_path.write_bytes(otp_key_lock)

    full_output_path.parent.mkdir(parents=True, exist_ok=True)
    full_output_path.write_bytes(otp_full)

    print(f"Generated OTP config: {output_path}")
    print(f"Generated OTP data image: {bin_output_path}")
    print(f"Generated OTP key-lock image: {lock_output_path}")
    print(f"Generated OTP full image: {full_output_path}")


if __name__ == "__main__":
    main()