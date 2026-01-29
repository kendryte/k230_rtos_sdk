#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, sys, argparse

from typing import Union
from pathlib import Path

import image_tools

sdk_root_dir = image_tools.get_validated_env_path("SDK_SRC_ROOT_DIR")
kconfig = image_tools.parse_kconfig(os.path.join(sdk_root_dir, ".config"))

sdk_build_images_dir = image_tools.get_validated_env_path("SDK_BUILD_IMAGES_DIR")
opensbi_generate_images_dir = Path(sdk_build_images_dir) / "opensbi"

os.makedirs(opensbi_generate_images_dir, exist_ok = True)

# Define a custom exception for clarity
class FileConcatenationError(Exception):
    """Custom error for file combining failures."""
    pass

def concatenate_with_padding(
    output_path: str,
    file1_path: str,
    file2_path: str,
    file2_offset: int,
    block_size: int = 1024
) -> Path:
    """
    Concatenates two binary files into an output file, inserting zero-padding 
    to ensure the second file starts at the specified byte offset.

    Args:
        output_path: Path to the final combined binary file.
        file1_path: Path to the first binary file.
        file2_path: Path to the second binary file.
        file2_offset: The absolute byte offset from the start of the output file 
                      where the second file must begin.
        block_size: Chunk size used for writing padding (for efficiency).

    Returns:
        Path: The Path object of the successfully created output file.

    Raises:
        FileConcatenationError: If files are missing, the offset is invalid, or file I/O fails.
    """
    # 1. Path and Existence Checks
    file1 = Path(file1_path)
    file2 = Path(file2_path)
    output_file = Path(output_path)

    for f in [file1, file2]:
        if not f.is_file():
            raise FileConcatenationError(f"Required binary file not found: {f}")

    if file2_offset < 0:
        raise FileConcatenationError(f"File 2 offset ({file2_offset}) must be zero or positive.")

    # 2. Calculate Required Padding
    file1_size = file1.stat().st_size

    # Padding is the space between the end of File 1 and the start of File 2
    padding_length = file2_offset - file1_size

    # 3. Validation
    if padding_length < 0:
        raise FileConcatenationError(
            f"File 1 ({file1_size} bytes) is too large. It cannot fit before the "
            f"required start offset of File 2 ({file2_offset} bytes)."
        )

    print(f"Padding required: {padding_length} bytes.")

    # 4. File Concatenation and Padding
    try:
        with output_file.open('wb') as out_f:
            
            # 4a. Write First File
            print(f"Writing {file1.name} to offset 0x0")
            with file1.open('rb') as in_f:
                # Read and write all content of File 1
                out_f.write(in_f.read()) 

            # 4b. Write Padding (Zeros)
            if padding_length > 0:
                # Create a reusable buffer of zeros for efficient writing
                zero_buffer = b'\x00' * block_size
                bytes_written = 0
                
                while bytes_written < padding_length:
                    # Determine how many bytes to write in this chunk
                    chunk_size = min(block_size, padding_length - bytes_written)
                    out_f.write(zero_buffer[:chunk_size])
                    bytes_written += chunk_size
            
            # Sanity check: file pointer must be exactly at the required offset
            if out_f.tell() != file2_offset:
                 raise FileConcatenationError(
                    f"Internal Error: File pointer (0x{out_f.tell():X}) did not match "
                    f"expected File 2 start offset (0x{file2_offset:X})."
                )

            # 4c. Write Second File
            file2_size = file2.stat().st_size
            print(f"Writing {file2.name} to offset 0x{file2_offset:X}")
            with file2.open('rb') as in_f:
                # Write content of File 2 immediately after the padding
                out_f.write(in_f.read()) 

    except IOError as e:
        raise FileConcatenationError(f"File I/O error during combining: {e}")

    print(f"Combined image created successfully at: {output_file}")
    return output_file

def get_opensbi_jump_addr() -> int:
    mem_rtsmart_base = image_tools.safe_str_to_int(kconfig["CONFIG_MEM_RTSMART_BASE"])
    mem_opensbi_size = image_tools.safe_str_to_int(kconfig["CONFIG_RTSMART_OPENSIB_MEMORY_SIZE"])

    return mem_rtsmart_base + mem_opensbi_size

def generate_opensbi_rtsmart(opensbi_jump_path, rtsmart_kernel_path):
    if not Path(opensbi_jump_path).exists() or not Path(rtsmart_kernel_path).exists():
        print(f"opensbi_jump_path {opensbi_jump_path} or rtsmart_kernel_path {rtsmart_kernel_path} not exist")
        sys.exit(1)

    opensbi_jump_addr = get_opensbi_jump_addr()
    membase_addr = image_tools.safe_str_to_int(kconfig["CONFIG_MEM_BASE_ADDR"])

    file_2_byte_offset = opensbi_jump_addr - membase_addr

    # Check for negative offset (unlikely but safe)
    if file_2_byte_offset < 0:
        print(f"Error: Calculated file offset ({file_2_byte_offset}) is negative.")
        sys.exit(1)

    print(f"OpenSBI Jump Addr 0x{opensbi_jump_addr:08x}")

    opensbi_jump_padding_rtsmart_file = image_tools.generate_temp_file_path("opensbi_rtsmart_", "_bin")
    try:
        concatenate_with_padding(opensbi_jump_padding_rtsmart_file, opensbi_jump_path, rtsmart_kernel_path, file_2_byte_offset)
    except Exception as e:
        print(f"An error occurred: {e}")
        sys.exit(1)

    gzip_tool = image_tools.K230PrivGzip()
    opensbi_rtsmart_gzipped_file = gzip_tool.compress_file(opensbi_jump_padding_rtsmart_file)
    os.remove(opensbi_jump_padding_rtsmart_file)

    opensbi_jump_rtsmart_image_file = image_tools.generate_temp_file_path("opensbi_rtsmart_image_", "_img")

    mkimg = image_tools.MkImage()
    mkimg.create_image([opensbi_rtsmart_gzipped_file], opensbi_jump_rtsmart_image_file, "riscv", "opensbi", "multi", "gzip", f"0x{membase_addr:08x}", f"0x{membase_addr:08x}", "rtt", verbose = True)
    os.remove(opensbi_rtsmart_gzipped_file)

    opensbi_rtsmart_output_file = Path(opensbi_generate_images_dir) / "opensbi_rtt_system.bin"

    if not image_tools.generate_k230_image(opensbi_jump_rtsmart_image_file, opensbi_rtsmart_output_file):
        print("OpenSBI + RTSmart generate image failed")
        sys.exit(1)
    os.remove(opensbi_jump_rtsmart_image_file)

    print(f"Generate OpenSBI + RTSmart Done.")

def main():
    parser = argparse.ArgumentParser(description="OpenSBI and RTSmrt Generate Image Script")
    parser.add_argument("-o", "--opensbi", required=True, type=str, help="OpenSBI Jump Binary Path")
    parser.add_argument("-r", "--rtsmart", required=True, type=str, help="RTSmart Binary Path")
    args = parser.parse_args()

    generate_opensbi_rtsmart(args.opensbi, args.rtsmart)

if __name__ == "__main__":
    main()
