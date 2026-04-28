#!/usr/bin/env python3

import argparse
import sys

from pathlib import Path

import image_tools


HEADER_GUARD = "K230_SECURE_BOOT_CONFIG_AUTOGEN_H"
ZERO_AES_IV = bytes(12)
ZERO_SM4_IV = bytes(16)


def format_c_array(iv_bytes: bytes) -> str:
    return ", ".join(f"0x{byte:02x}" for byte in iv_bytes)


def generate_header(
    output_path: Path,
    firmware_aes_iv: bytes,
    firmware_sm4_iv: bytes,
) -> None:
    content = f"""#ifndef {HEADER_GUARD}
#define {HEADER_GUARD}

#include <asm/types.h>

static const uint8_t k230_firmware_gcm_iv[] = {{
    {format_c_array(firmware_aes_iv)}
}};

static const uint8_t k230_firmware_sm4_iv[] = {{
    {format_c_array(firmware_sm4_iv)}
}};

#endif
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")


def resolve_firmware_runtime_ivs(
    secure_boot_type: int,
    secure_config_path: Path,
) -> tuple[bytes, bytes]:
    if secure_boot_type == 0:
        return ZERO_AES_IV, ZERO_SM4_IV

    if secure_boot_type == 2:
        return ZERO_AES_IV, ZERO_SM4_IV

    if secure_boot_type == 1:
        return ZERO_AES_IV, ZERO_SM4_IV

    raise ValueError(f"Unsupported downstream firmware secure-boot type {secure_boot_type}")


def resolve_runtime_ivs(config_path: Path) -> tuple[bytes, bytes]:
    kconfig = image_tools.parse_kconfig(str(config_path))

    secure_boot_type, secure_config = image_tools.resolve_downstream_secure_boot_settings(kconfig)
    if secure_boot_type == 0 or secure_config is None:
        return ZERO_AES_IV, ZERO_SM4_IV

    return resolve_firmware_runtime_ivs(secure_boot_type, Path(secure_config))


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate U-Boot secure boot runtime IV header")
    parser.add_argument("--config", required=True, help="Path to the top-level .config file")
    parser.add_argument("--output", required=True, help="Path to the generated header")
    args = parser.parse_args()

    firmware_aes_iv, firmware_sm4_iv = resolve_runtime_ivs(Path(args.config))
    generate_header(Path(args.output), firmware_aes_iv, firmware_sm4_iv)

    print(f"Generated secure boot runtime header: {args.output}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Failed to generate secure boot runtime header: {exc}", file=sys.stderr)
        sys.exit(1)