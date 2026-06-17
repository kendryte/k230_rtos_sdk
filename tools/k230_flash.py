#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
K230 Image Download/Flash Tool — thin CLI wrapper.

Usage:
    python3 k230_flash.py -m SDCARD                    # auto-detect image & flash
    python3 k230_flash.py -m SDCARD -f my_image.img    # flash specific image
    python3 k230_flash.py -m SPI_NAND -f image.img     # flash to specific medium
    python3 k230_flash.py --list-devices               # list connected devices
    python3 k230_flash.py --list-images                # list discovered images
"""

import sys
import argparse
from pathlib import Path

from k230_flash import (
    ensure_device_in_bootloader,
    K230FlashTool,
    find_built_images,
)


def main():
    parser = argparse.ArgumentParser(
        description="K230 Image Download/Flash Tool — wraps k230_flash_cli for easy flashing.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "-f", "--file",
        type=str, default=None,
        help="Path to the firmware image file to flash. If omitted, auto-discover from output directory.",
    )
    parser.add_argument(
        "-m", "--medium-type",
        default=None,
        help="Target storage medium (required for flashing): EMMC, SDCARD, SPI_NAND, SPI_NOR, OTP.",
    )
    parser.add_argument(
        "-t", "--timeout",
        type=int, default=10,
        help="Timeout in seconds for bootloader detection (default: 10).",
    )
    parser.add_argument(
        "--flash-timeout",
        type=int, default=None,
        help="Timeout in seconds for the flash operation itself (default: no limit).",
    )
    parser.add_argument(
        "--no-reboot",
        action="store_true",
        help="Do NOT auto-reboot the device after flashing.",
    )
    parser.add_argument(
        "-l", "--list-devices",
        action="store_true",
        help="List connected K230 devices in bootloader mode and exit.",
    )
    parser.add_argument(
        "--search-dir",
        type=str, default=None,
        help="Directory to search for built images (default: SDK output dir).",
    )
    parser.add_argument(
        "--list-images",
        action="store_true",
        help="List discovered firmware images and exit.",
    )
    parser.add_argument(
        "--skip-bootloader-check",
        action="store_true",
        help="Skip the bootloader-mode detection step (useful if device is already in burn mode).",
    )

    args = parser.parse_args()

    # --list-devices
    if args.list_devices:
        print(K230FlashTool().list_devices())
        return

    # --list-images
    if args.list_images:
        images = find_built_images(args.search_dir)
        if not images:
            print("No firmware images found.")
            return
        print("Discovered firmware images:")
        for img in images:
            print(f"  {img}")
        return

    # resolve image path
    if args.file:
        image_path = Path(args.file)
        if not image_path.exists():
            print(f"Error: Image file not found: {args.file}")
            sys.exit(1)
    else:
        images = find_built_images(args.search_dir)
        if not images:
            print("Error: No firmware images found. Build the project first or specify -f <image>.")
            sys.exit(1)
        if len(images) == 1:
            image_path = images[0]
            print(f"Auto-detected image: {image_path}")
        else:
            print("Multiple images found. Please specify one with -f:")
            for img in images:
                print(f"  {img}")
            sys.exit(1)

    # medium type is required for flashing
    if not args.medium_type:
        print("Error: -m/--medium-type is required. Choices: EMMC, SDCARD, SPI_NAND, SPI_NOR, OTP")
        sys.exit(1)

    medium_type = args.medium_type.upper()
    valid = {"EMMC", "SDCARD", "SPI_NAND", "SPI_NOR", "OTP"}
    if medium_type not in valid:
        print(f"Error: invalid medium '{args.medium_type}'. Choices: {', '.join(sorted(valid))}")
        sys.exit(1)

    # main workflow
    try:
        if not args.skip_bootloader_check:
            print("=== Ensuring Device is in Bootloader Mode ===")
            ensure_device_in_bootloader(args.timeout)

        print(f"\n=== Flashing Firmware ===")
        print(f"Image:  {image_path}")
        print(f"Medium: {medium_type}\n")

        flash_tool = K230FlashTool()
        flash_tool.flash(
            image_path=str(image_path),
            medium_type=medium_type,
            auto_reboot=not args.no_reboot,
            timeout=args.flash_timeout,
        )

        print("\n=== Flash Operation Completed Successfully ===")

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
