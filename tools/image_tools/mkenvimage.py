#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Cross-platform Python wrapper for mkenvimage tool.

This script provides the same functionality as the original mkenvimage C tool
but works across different operating systems (Windows, Linux, macOS).

Usage:
    python mkenvimage.py [-h] [-r] [-b] [-p <byte>] -s <size> -o <output> <input>

The input file should contain key=value pairs, one per line.
Empty lines and comments (lines starting with #) are ignored.
"""

import argparse
import os
import sys
import struct
import zlib
from pathlib import Path


class MkenvImageError(Exception):
    """Custom exception for mkenvimage operations."""
    pass


class MkenvImage:
    """Cross-platform mkenvimage implementation."""
    
    def __init__(self):
        self.crc_size = 4  # uint32_t
        self.chunk_size = 4096
        
    def parse_int(self, value_str):
        """Parse integer value with error handling."""
        try:
            # Support decimal, hex (0x), octal (0o), binary (0b)
            result = int(value_str, 0)
            return result
        except ValueError:
            raise MkenvImageError(f"Bad integer format: {value_str}")

    def read_input_file(self, input_path):
        """Read input file and return content as bytes."""
        if input_path == "-":
            # Read from stdin
            if hasattr(sys.stdin, 'buffer'):
                return sys.stdin.buffer.read()
            else:
                return sys.stdin.read().encode('utf-8')
        else:
            try:
                with open(input_path, 'rb') as f:
                    return f.read()
            except IOError as e:
                raise MkenvImageError(f"Can't open \"{input_path}\": {e}")
    
    def parse_environment_data(self, file_content, env_size):
        """Parse environment data from file content."""
        env_data = bytearray()
        i = 0
        file_size = len(file_content)
        
        while i < file_size and len(env_data) < env_size - 1:
            char = file_content[i]
            
            if char == ord('\n'):
                if i == 0 or file_content[i-1] == ord('\n'):
                    # Skip empty lines
                    i += 1
                    continue
                elif file_content[i-1] == ord('\\'):
                    # Embedded newline in a variable
                    # Replace backslash with newline
                    if len(env_data) > 0:
                        env_data[-1] = ord('\n')
                    i += 1
                else:
                    # End of a variable
                    env_data.append(0)
                    i += 1
            elif (i == 0 or file_content[i-1] == ord('\n')) and char == ord('#'):
                # Comment line, skip until newline
                i += 1
                while i < file_size and file_content[i] != ord('\n'):
                    i += 1
            else:
                env_data.append(char)
                i += 1
        
        # Check if there's meaningful content left in the file
        remaining_content = file_content[i:]
        for j, char in enumerate(remaining_content):
            if char == ord('\n'):
                if j == 0 or (j > 0 and remaining_content[j-1] == ord('\n')):
                    continue
            elif (j == 0 or (j > 0 and remaining_content[j-1] == ord('\n'))) and char == ord('#'):
                # Skip comment
                while j < len(remaining_content) and remaining_content[j] != ord('\n'):
                    j += 1
            else:
                raise MkenvImageError("The environment file is too large for the target environment storage")
        
        # Ensure proper termination
        if len(env_data) == 0 or env_data[-1] != 0:
            env_data.append(0)
            if len(env_data) >= env_size:
                raise MkenvImageError("The environment file is too large for the target environment storage")
        
        # Add final null terminator
        if len(env_data) < env_size:
            env_data.append(0)
        
        return bytes(env_data)
    
    def calculate_crc(self, data):
        """Calculate CRC32 for the environment data."""
        return zlib.crc32(data) & 0xffffffff

    def create_environment_image(self, env_data, data_size, redundant=False, 
                               big_endian=False, pad_byte=0xff):
        """Create the complete environment image."""
        # Allocate buffer for the entire image
        image = bytearray([pad_byte] * data_size)
        
        # Calculate environment size (excluding CRC and redundant byte)
        env_size = data_size - self.crc_size - (1 if redundant else 0)
        
        # Ensure environment data fits
        if len(env_data) > env_size:
            raise MkenvImageError("Environment data too large")
        
        # Copy environment data to the correct position
        env_offset = self.crc_size + (1 if redundant else 0)
        image[env_offset:env_offset + len(env_data)] = env_data
        
        # Calculate and set CRC
        crc = self.calculate_crc(image[env_offset:env_offset + env_size])
        
        if big_endian:
            crc_bytes = struct.pack('>I', crc)
        else:
            crc_bytes = struct.pack('<I', crc)
        
        image[0:self.crc_size] = crc_bytes
        
        # Set redundant flag if needed
        if redundant:
            image[self.crc_size] = 1
        
        return bytes(image)
    
    def write_output_file(self, output_path, data):
        """Write data to output file."""
        if output_path == "-":
            # Write to stdout
            if hasattr(sys.stdout, 'buffer'):
                sys.stdout.buffer.write(data)
            else:
                sys.stdout.write(data.decode('latin1'))
        else:
            try:
                with open(output_path, 'wb') as f:
                    f.write(data)
            except IOError as e:
                raise MkenvImageError(f"Can't open output file \"{output_path}\": {e}")
    
    def create_image(self, input_path, output_path, data_size, redundant=False,
                    big_endian=False, pad_byte=0x00):
        """Main function to create environment image."""
        # Validate data size
        if data_size <= 0:
            raise MkenvImageError("Please specify the size of the environment partition.")
        
        # Read and parse input file
        file_content = self.read_input_file(input_path)
        env_size = data_size - self.crc_size - (1 if redundant else 0)
        env_data = self.parse_environment_data(file_content, env_size)
        
        # Create the environment image
        image_data = self.create_environment_image(
            env_data, data_size, redundant, big_endian, pad_byte
        )
        
        # Write output
        self.write_output_file(output_path, image_data)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate U-Boot environment image from key=value text file',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
The input file is in format:
    key1=value1
    key2=value2
    ...
Empty lines are skipped, and lines with a # in the first
column are treated as comments (also skipped).

If the input file is "-", data is read from standard input.
If the output file is "-", data is written to standard output.
        """
    )
    
    parser.add_argument('-s', '--size', required=True, type=str,
                       help='Size of the environment partition (e.g., 0x10000, 65536)')
    parser.add_argument('-o', '--output', required=True,
                       help='Output binary file path')
    parser.add_argument('-r', '--redundant', action='store_true',
                       help='The environment has multiple copies in flash')
    parser.add_argument('-b', '--big-endian', action='store_true',
                       help='The target is big endian (default is little endian)')
    parser.add_argument('-p', '--pad-byte', default='0xff', type=str,
                       help='Fill the image with specified byte instead of 0xff')
    parser.add_argument('-V', '--version', action='store_true',
                       help='Print version information and exit')
    parser.add_argument('input', nargs='?',
                       help='Input text file with key=value pairs (default: stdin)')
    
    args = parser.parse_args()
    
    # Handle version
    if args.version:
        print(f"mkenvimage.py version 1.0.0 (Python wrapper)")
        return 0
    
    # Set default input to stdin if not specified
    input_file = args.input if args.input is not None else "-"
    
    try:
        mkenv = MkenvImage()
        
        # Parse arguments
        data_size = mkenv.parse_int(args.size)
        pad_byte = mkenv.parse_int(args.pad_byte)
        
        # Validate pad byte range
        if pad_byte < 0 or pad_byte > 255:
            raise MkenvImageError(f"Pad byte must be between 0 and 255, got {pad_byte}")
        
        # Create the image
        mkenv.create_image(
            input_path=input_file,
            output_path=args.output,
            data_size=data_size,
            redundant=args.redundant,
            big_endian=args.big_endian,
            pad_byte=pad_byte
        )
        
        return 0
        
    except MkenvImageError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
