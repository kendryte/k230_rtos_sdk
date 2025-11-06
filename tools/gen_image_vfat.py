# -*- coding: utf-8 -*-

import os, sys, argparse

from typing import Union
from pathlib import Path

import image_tools
import genimage_py as genimage

sdk_images_dir = image_tools.get_validated_env_path("SDK_BUILD_IMAGES_DIR")

def generate_bin_vfat(output_path):
    config_path = image_tools.generate_temp_file_path("bin_vfat_", "_cfg")

    try:
        config_snippet = """\
image bin.vfat {
    vfat {
        label = "BIN"
    }
    size = 10M
    mountpoint = "bin"
}
"""
        with open(config_path, "w") as f:
            f.write(config_snippet)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

    # generate preload
    bin_preload = Path(sdk_images_dir) / "bin" / "preload"

    bin_preload.parent.mkdir(parents=True, exist_ok=True)
    bin_preload.touch(exist_ok=True)

    tool = genimage.GenImageTool(sdk_images_dir, output_path, config_path)
    tool.run()

    print(f"Generating bin.vfat done, at {Path(output_path) / "bin.vfat"}")

def main():
    parser = argparse.ArgumentParser(description="bin.vfat Generate Script")
    parser.add_argument("-o", "--output", required=True, type=str, help="bin.vfat output path")
    args = parser.parse_args()

    generate_bin_vfat(args.output)

if __name__ == "__main__":
    main()
