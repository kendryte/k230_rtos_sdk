#!/usr/bin/env python3

import argparse
import json
import secrets
import sys

from pathlib import Path
from typing import Tuple

from Crypto.PublicKey import RSA
from gmssl import sm2


DEFAULT_VERSION_BYTES = "00000000"
DEFAULT_SM2_ID = "1234567812345678"
ROM_SM4_IV_HEX = "000102030405060708090a0b0c0d0e0f"


def ensure_output_dir(output_dir: Path, force: bool) -> None:
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"Output path is not a directory: {output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    if force:
        return

    existing_targets = [
        output_dir / "secure_config_aes_rsa_pem.json",
        output_dir / "secure_config_sm4_sm2.json",
        output_dir / "spl_rsa_pub.pem",
        output_dir / "spl_rsa_priv.pem",
        output_dir / "firmware_rsa_pub.pem",
        output_dir / "firmware_rsa_priv.pem",
    ]

    existing = [path for path in existing_targets if path.exists()]
    if existing:
        joined = ", ".join(str(path) for path in existing)
        raise ValueError(f"Refusing to overwrite existing files without --force: {joined}")


def write_json(output_path: Path, payload: dict) -> None:
    output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def generate_rsa_keypair(bits: int) -> RSA.RsaKey:
    return RSA.generate(bits)


def write_rsa_keypair(output_dir: Path, stage: str, bits: int) -> Tuple[str, str]:
    key = generate_rsa_keypair(bits)
    public_path = output_dir / f"{stage}_rsa_pub.pem"
    private_path = output_dir / f"{stage}_rsa_priv.pem"

    public_path.write_bytes(key.publickey().export_key())
    private_path.write_bytes(key.export_key())

    return public_path.name, private_path.name


def generate_sm2_keypair() -> Tuple[str, str, str]:
    keygen = sm2.CryptSM2(private_key="1", public_key="")
    curve_order = int(keygen.ecc_table["n"], 16)
    private_int = secrets.randbelow(curve_order - 1) + 1
    private_key = f"{private_int:064x}"
    public_key = keygen._kg(private_int, keygen.ecc_table["g"])

    return private_key, public_key[:64], public_key[64:]


def firmware_section(version_bytes: str) -> dict:
    return {
        "firmware": {
            "version_bytes": version_bytes,
        }
    }


def build_aes_rsa_stage(stage: str, version_bytes: str, output_dir: Path, rsa_bits: int) -> dict:
    public_name, private_name = write_rsa_keypair(output_dir, stage, rsa_bits)

    return {
        **firmware_section(version_bytes),
        "aes": {
            "key": secrets.token_hex(32),
            "auth_data": "",
        },
        "rsa": {
            "key_size": rsa_bits,
            "public_key_file": public_name,
            "private_key_file": private_name,
        },
    }


def build_sm4_sm2_stage(stage: str, version_bytes: str, sm2_id: str) -> dict:
    private_key, public_key_x, public_key_y = generate_sm2_keypair()
    sm4_section = {
        "key": secrets.token_hex(16),
    }

    if stage == "spl":
        sm4_section["iv"] = ROM_SM4_IV_HEX

    return {
        **firmware_section(version_bytes),
        "sm4": sm4_section,
        "sm2": {
            "private_key": private_key,
            "public_key_x": public_key_x,
            "public_key_y": public_key_y,
            "id": sm2_id,
        },
    }


def build_aes_rsa_config(output_dir: Path, rsa_bits: int, version_bytes: str) -> dict:
    return {
        "spl": build_aes_rsa_stage("spl", version_bytes, output_dir, rsa_bits),
        "firmware": build_aes_rsa_stage("firmware", version_bytes, output_dir, rsa_bits),
    }


def build_sm4_sm2_config(version_bytes: str, sm2_id: str) -> dict:
    return {
        "spl": build_sm4_sm2_stage("spl", version_bytes, sm2_id),
        "firmware": build_sm4_sm2_stage("firmware", version_bytes, sm2_id),
    }


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate fresh secure-boot configs and key material for K230",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        required=True,
        help="Directory where generated configs and key files will be written",
    )
    parser.add_argument(
        "--rsa-bits",
        type=int,
        default=2048,
        help="RSA key size for AES+RSA configs (default: 2048)",
    )
    parser.add_argument(
        "--sm2-id",
        default=DEFAULT_SM2_ID,
        help="SM2 signer ID string (default: 1234567812345678)",
    )
    parser.add_argument(
        "--version-bytes",
        default=DEFAULT_VERSION_BYTES,
        help="4-byte firmware version field as hex (default: 00000000)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite previously generated files in the output directory",
    )
    return parser


def main() -> None:
    parser = create_argument_parser()
    args = parser.parse_args()

    try:
        if args.rsa_bits < 2048:
            raise ValueError("RSA key size must be at least 2048 bits")

        version_bytes = args.version_bytes.lower()
        if len(version_bytes) != 8:
            raise ValueError("--version-bytes must be exactly 4 bytes of hex")
        bytes.fromhex(version_bytes)

        output_dir = Path(args.output_dir).expanduser().resolve()
        ensure_output_dir(output_dir, args.force)

        aes_rsa_config = build_aes_rsa_config(output_dir, args.rsa_bits, version_bytes)
        sm4_sm2_config = build_sm4_sm2_config(version_bytes, args.sm2_id)

        aes_rsa_path = output_dir / "secure_config_aes_rsa_pem.json"
        sm4_sm2_path = output_dir / "secure_config_sm4_sm2.json"
        write_json(aes_rsa_path, aes_rsa_config)
        write_json(sm4_sm2_path, sm4_sm2_config)

        print(f"Generated {aes_rsa_path}")
        print(f"Generated {sm4_sm2_path}")
        print("Update CONFIG_SECURE_BOOT_CONFIG_FILE or pass these files directly to the secure-boot tools.")
    except Exception as exc:
        print(f"Failed to generate secure-boot configs: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()