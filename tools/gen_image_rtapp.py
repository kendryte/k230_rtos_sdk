#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys

from pathlib import Path

import image_tools

sdk_root_dir = image_tools.get_validated_env_path("SDK_SRC_ROOT_DIR")
kconfig = image_tools.parse_kconfig(os.path.join(sdk_root_dir, ".config"))

sdk_build_images_dir = image_tools.get_validated_env_path("SDK_BUILD_IMAGES_DIR")
rtapp_generate_images_dir = Path(sdk_build_images_dir) / "rtapp"

os.makedirs(rtapp_generate_images_dir, exist_ok = True)

def generate_fake_rt_app() -> str:
    pesudo_rt_app_path_obj = image_tools.generate_temp_file_path("pesudo_rt_app_", "_bin")

    SIZE_BYTES = 4096
    zero_content = b'\x00' * SIZE_BYTES

    try:
        with open(pesudo_rt_app_path_obj, "wb") as f:
            f.write(zero_content)
        print(f"Generated fake RT-App file of {SIZE_BYTES} bytes at: {pesudo_rt_app_path_obj}")
    except IOError as e:
        print(f"Error writing pseudo RT-App file: {e}")
        raise

    return str(pesudo_rt_app_path_obj)

def main():
    use_fake_rt_app = False
    delete_original_file = False
    rt_app_file_path = None

    try:
        delete_original_file = kconfig["CONFIG_FAST_BOOT_DELETE_ORIGIIN_FILE"]

        rt_app_file_path = str(kconfig["CONFIG_FAST_BOOT_FILE_PATH"])
        if not Path(rt_app_file_path).exists():
            raise FileNotFoundError(f"User Configure CONFIG_FAST_BOOT_FILE_PATH ({rt_app_file_path}) not exists")
    except Exception as e:
        use_fake_rt_app = True
        rt_app_file_path = None
        print(f"An error occurred: {e}")

    if not kconfig["CONFIG_FAST_BOOT_CONFIGURATION"]:
        use_fake_rt_app = True

        print("Generating RTApp use fake rtapp because not enable fastboot")

    if use_fake_rt_app:
        print("Use fake rtapp")
        rt_app_file_path = generate_fake_rt_app()

    if rt_app_file_path is None:
        print(f"Generating RTApp unknown error")
        sys.exit(1)

    gzip_tool = image_tools.K230PrivGzip()
    rtapp_gzipped_file = gzip_tool.compress_file(rt_app_file_path)

    if delete_original_file or use_fake_rt_app:
        os.remove(rt_app_file_path)

    rtapp_image_file = image_tools.generate_temp_file_path("rt_app_", "_img")

    mkimg = image_tools.MkImage()
    mkimg.create_image([rtapp_gzipped_file], rtapp_image_file, "riscv", "u-boot", "firmware", "gzip", "0x00000000", "0x00000000", "rtapp", verbose = True)
    os.remove(rtapp_gzipped_file)

    rtapp_output_file = Path(rtapp_generate_images_dir) / "rtapp.elf.gz"
    if rtapp_output_file.exists():
        os.remove(rtapp_output_file)

    if not image_tools.generate_k230_image(rtapp_image_file, rtapp_output_file):
        print("RTApp generate image failed")
        sys.exit(1)
    os.remove(rtapp_image_file)

    bin_preload = Path(sdk_build_images_dir) / "bin" / "preload"

    if not use_fake_rt_app:
        bin_preload.parent.mkdir(parents=True, exist_ok=True)
        bin_preload.touch(exist_ok=True)
    else:
        if bin_preload.exists():
            os.remove(bin_preload)

    print(f"Generate RTApp Done.")

if __name__ == "__main__":
    main()
