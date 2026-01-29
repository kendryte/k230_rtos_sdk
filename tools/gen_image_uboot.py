#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, argparse

from pathlib import Path

import image_tools

sdk_root_dir = image_tools.get_validated_env_path("SDK_SRC_ROOT_DIR")
kconfig = image_tools.parse_kconfig(os.path.join(sdk_root_dir, ".config"))

sdk_uboot_build_dir = image_tools.get_validated_env_path("SDK_UBOOT_BUILD_DIR")

sdk_build_images_dir = image_tools.get_validated_env_path("SDK_BUILD_IMAGES_DIR")
uboot_generate_images_dir = Path(sdk_build_images_dir) / "uboot"

os.makedirs(uboot_generate_images_dir, exist_ok = True)

def generate_uboot_env_bin(data_size : int = 0x10000, pad_byte : bytes = 0x00):
    sdk_board_dir = image_tools.get_validated_env_path("SDK_BOARD_DIR")
    uboot_env_file = Path(sdk_board_dir) / str(kconfig["CONFIG_UBOOT_ENV_FILE"])

    if not uboot_env_file.exists():
        print(f"U-Boot env file ({uboot_env_file}) not exist")
        sys.exit(1)

    uboot_env_bin_file = Path(uboot_generate_images_dir) / "env.bin"

    mkenvimage = image_tools.MkenvImage()

    mkenvimage.create_image(uboot_env_file, uboot_env_bin_file, data_size, pad_byte = pad_byte)

    print(f"Convert U-Boot env {uboot_env_file} => {uboot_env_bin_file} done.")

def get_uboot_text_base() -> int:
    uboot_config_file = Path(sdk_uboot_build_dir) / ".config"

    # if not build uboot, use default text base.
    if not uboot_config_file.exists():
        return 0x80000000

    uboot_config = image_tools.parse_kconfig(uboot_config_file)

    return image_tools.safe_str_to_int(uboot_config["CONFIG_SYS_TEXT_BASE"])

def generate_uboot_spl_bin(spl_path):
    if not Path(spl_path).exists():
        print(f"U-Boot SPL Binary ({spl_path}) not exists")
        sys.exit(1)

    uboot_spl_output_file = Path(uboot_generate_images_dir) / "fn_u-boot-spl.bin"

    if not image_tools.generate_k230_image(spl_path, uboot_spl_output_file):
        print("U-Boot generate SPL image failed")
        sys.exit(1)

    uboot_spl_swap_output_file = Path(uboot_generate_images_dir) / "swap_fn_u-boot-spl.bin"
    image_tools.swap_bytes_in_file(uboot_spl_output_file, uboot_spl_swap_output_file)

    print(f"Generate U-Boot SPL Done.")

def generate_uboot_bin(uboot_path):
    if not Path(uboot_path).exists():
        print(f"UBOOT Binary ({uboot_path}) not exists")
        sys.exit(1)

    uboot_enable_secure_boot = False
    uboot_secure_boot_type = None
    uboot_secure_boot_config = None

    try:
        uboot_enable_secure_boot = bool(kconfig["CONFIG_UBOOT_ENABLE_SECURE_BOOT"])
        if uboot_enable_secure_boot:
            uboot_secure_boot_type = int(kconfig["CONFIG_UBOOT_SECURE_BOOT_TYPE"])
            if uboot_secure_boot_type != 0:
                uboot_secure_boot_config = str(kconfig["CONFIG_UBOOT_SECURE_BOOT_CONFIG_FILE"])
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

    gzip_tool = image_tools.K230PrivGzip()
    uboot_gzipped_file = gzip_tool.compress_file(uboot_path)

    uboot_text_base = get_uboot_text_base()
    print(f"Generating U-Boot binary with text base: 0x{uboot_text_base:08x}")

    uboot_image_file = image_tools.generate_temp_file_path("uboot_", "_img")

    mkimg = image_tools.MkImage()
    mkimg.create_image([uboot_gzipped_file], uboot_image_file, "riscv", "u-boot", "firmware", "gzip", f"0x{uboot_text_base:08x}", f"0x{uboot_text_base:08x}", "uboot", verbose = True)
    os.remove(uboot_gzipped_file)

    uboot_output_file = Path(uboot_generate_images_dir) / "fn_ug_u-boot.bin"

    if not image_tools.generate_k230_image(uboot_image_file, uboot_output_file, uboot_secure_boot_type, uboot_secure_boot_config):
        print("U-Boot generate image failed")
        sys.exit(1)
    os.remove(uboot_image_file)

    print(f"Generate U-Boot Done.")

def main():
    parser = argparse.ArgumentParser(description="UBOOT Generate Image Script")
    parser.add_argument("-s", "--spl", required=True, type=str, help="UBOOT SPL Binary Path")
    parser.add_argument("-u", "--uboot", required=True, type=str, help="UBOOT Binary Path")
    args = parser.parse_args()

    generate_uboot_env_bin()

    generate_uboot_spl_bin(args.spl)
    generate_uboot_bin(args.uboot)

if __name__ == "__main__":
    main()
