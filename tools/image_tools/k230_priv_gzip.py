#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Python wrapper for k230_priv_gzip executable with cross-platform support.

This script provides a Python interface to the k230_priv_gzip tool,
handling different operating systems and providing a clean API for
compression and decompression operations.
"""

import os
import sys
import subprocess
import argparse
import logging
import platform
from pathlib import Path
from typing import List, Optional, Union, Dict, Any
from enum import Enum


class CompressionLevel(Enum):
    """Compression level options"""
    FAST = 1
    DEFAULT = 6
    BEST = 9


class K230PrivGzipError(Exception):
    """Custom exception for k230_priv_gzip operations"""
    pass


class K230PrivGzip:
    """
    Python wrapper for k230_priv_gzip executable with cross-platform support.
    
    This class provides a Python interface to the k230_priv_gzip tool,
    handling different operating systems and providing a clean API for
    compression and decompression operations.
    """

    def __init__(self, executable_path: Optional[str] = None):
        """
        Initialize the k230_priv_gzip wrapper.
        
        Args:
            executable_path: Path to k230_priv_gzip executable. If None,
                           will try to find it in standard locations.
        
        Raises:
            K230PrivGzipError: If the executable cannot be found.
        """
        self.executable_path = self._find_executable(executable_path)
        self.logger = logging.getLogger(__name__)
        self.compression_levels_to_try = [9, 8, 7, 6, 5, 4]

    def _find_executable(self, provided_path: Optional[str] = None) -> str:
        """
        Find the k230_priv_gzip executable on the system.
        
        Args:
            provided_path: Explicit path to the executable
            
        Returns:
            Path to the executable
            
        Raises:
            K230PrivGzipError: If executable cannot be found
        """
        if provided_path:
            if os.path.isfile(provided_path) and os.access(provided_path, os.X_OK):
                return provided_path
            else:
                raise K230PrivGzipError(f"Executable not found or not executable: {provided_path}")
        
        # Try to find executable in the same directory as this script
        script_dir = Path(__file__).parent
        local_executable = script_dir / "bin" / "k230_priv_gzip"

        if local_executable.exists() and os.access(local_executable, os.X_OK):
            return str(local_executable)

        # Try to find in system PATH
        try:
            result = subprocess.run(['which', 'k230_priv_gzip'], 
                                  capture_output=True, text=True, check=True)
            if result.stdout.strip():
                return result.stdout.strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            pass
        
        # Windows-specific handling
        if platform.system() == "Windows":
            # Try with .exe extension
            windows_executable = script_dir / "bin" / "k230_priv_gzip.exe"
            if windows_executable.exists():
                return str(windows_executable)
            
            # Try in PATH with .exe
            try:
                result = subprocess.run(['where', 'k230_priv_gzip.exe'], 
                                      capture_output=True, text=True, check=True)
                if result.stdout.strip():
                    return result.stdout.strip().split('\n')[0]
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass

        raise K230PrivGzipError(
            "k230_priv_gzip executable not found. Please ensure it is installed "
            "and accessible, or provide the path explicitly."
        )
    
    def _execute_command(self, args: List[str], input_data: Optional[bytes] = None,
                        capture_output: bool = True) -> subprocess.CompletedProcess:
        """
        Execute the k230_priv_gzip command with proper error handling.
        
        Args:
            args: Command line arguments
            input_data: Data to pipe to stdin (optional)
            capture_output: Whether to capture stdout/stderr
            
        Returns:
            subprocess.CompletedProcess object
            
        Raises:
            K230PrivGzipError: If command execution fails
        """
        cmd = [self.executable_path] + args
        
        try:
            self.logger.debug(f"Executing command: {' '.join(cmd)}")
            
            if input_data is not None:
                result = subprocess.run(
                    cmd,
                    input=input_data,
                    capture_output=capture_output,
                    check=False
                )
            else:
                result = subprocess.run(
                    cmd,
                    capture_output=capture_output,
                    check=False
                )
            
            # Check for errors
            if result.returncode != 0:
                error_msg = f"k230_priv_gzip failed with return code {result.returncode}"
                if result.stderr:
                    error_msg += f": {result.stderr.decode('utf-8', errors='replace')}"
                raise K230PrivGzipError(error_msg)
            
            return result
            
        except FileNotFoundError:
            raise K230PrivGzipError(f"Executable not found: {self.executable_path}")
        except subprocess.SubprocessError as e:
            raise K230PrivGzipError(f"Subprocess error: {e}")

    def _replace_byte_at_index(self, file_path: str, index: int, old_byte: int, new_byte: int):
        """Replaces a specific byte in the file. (As implemented in a previous turn)"""
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            with open(file_path, 'r+b') as f:
                f.seek(index)
                target_byte = f.read(1)
                
                if not target_byte:
                    raise EOFError(f"File too short to access index {index}")

                if target_byte[0] == old_byte:
                    f.seek(index)
                    f.write(bytes([new_byte]))
                    logging.debug(f"Byte at index {index} changed 0x{old_byte:02x} -> 0x{new_byte:02x}.")
                else:
                    raise ValueError(
                        f"Expected byte 0x{old_byte:02x} at index {index}, found 0x{target_byte[0]:02x}"
                    )
        except Exception as e:
            raise K230PrivGzipError(f"Error modifying byte at index {index} in {file_path}: {e}")

    def compress_file(self, input_path: str, output_path: Optional[str] = None,
                      keep_original: bool = True, compression_level: Optional[int] = None,
                      force: bool = True, suffix: str = ".gz") -> str:
        """
        Compress a file using k230_priv_gzip with compression level fallback 
        and then modifies the third byte (index 2) of the output file from 0x08 to 0x09.
        """
        if not os.path.isfile(input_path):
            raise K230PrivGzipError(f"Input file not found: {input_path}")

        final_output_path = output_path if output_path else input_path + suffix
        compression_successful = False
        
        # Determine which levels to attempt
        levels_to_try = []
        if compression_level is not None:
            # If a level is explicitly given, try only that one
            levels_to_try = [compression_level]
        else:
            # Otherwise, use the predefined fallback order
            levels_to_try = self.compression_levels_to_try

        # --- 1. Compression Loop with Fallback ---

        for level in levels_to_try:
            base_args = []

            # Add compression level
            base_args.append(f"-n{level}") # The shell script uses -n, assuming k230_priv_gzip supports this format

            # Add options (-f and -k from shell script)
            if keep_original:
                base_args.append("-k")
            if force:
                base_args.append("-f")
            if suffix != ".gz":
                base_args.extend(["-S", suffix])

            try:
                if output_path:
                    # Case A: Output to stdout, then write to file
                    args = base_args + ["-c", input_path]
                    result = self._execute_command(args)

                    with open(final_output_path, 'wb') as f:
                        f.write(result.stdout)

                else:
                    # Case B: In-place compression
                    args = base_args + [input_path]
                    self._execute_command(args, capture_output=False)

                logging.info(f"Compression succeeded with level -n{level}")
                compression_successful = True
                break # Exit the loop after successful compression

            except CalledProcessError as e:
                logging.warning(f"Compression failed with level -n{level}. Trying next level. Error: {e.stderr.decode() if e.stderr else e}")
            except Exception as e:
                raise K230PrivGzipError(f"An unexpected error occurred during compression: {e}")

        if not compression_successful:
            raise K230PrivGzipError(f"Compression failed after trying all levels ({levels_to_try}) for file: {input_path}")

        # Target: Byte at index 2 (The third byte)
        # Change: 0x08 -> 0x09
        self._replace_byte_at_index(
            file_path=final_output_path, 
            index=2, 
            old_byte=0x08, 
            new_byte=0x09
        )

        return final_output_path

    def decompress_file(self, input_path: str, output_path: Optional[str] = None,
                       keep_original: bool = True, force: bool = True) -> str:
        """
        Decompress a file using k230_priv_gzip.
        
        Args:
            input_path: Path to compressed file
            output_path: Path to output file (optional)
            keep_original: Whether to keep the original file
            force: Force overwrite of existing files
            
        Returns:
            Path to the decompressed file
            
        Raises:
            K230PrivGzipError: If decompression fails
        """
        if not os.path.isfile(input_path):
            raise K230PrivGzipError(f"Input file not found: {input_path}")
        
        args = ["-d"]  # Decompress flag
        
        # Add options
        if keep_original:
            args.append("-k")
        if force:
            args.append("-f")
        
        # Add output file if specified
        if output_path:
            args.extend(["-c", input_path])
            
            # Write to output file
            result = self._execute_command(args)
            try:
                with open(output_path, 'wb') as f:
                    f.write(result.stdout)
                return output_path
            except IOError as e:
                raise K230PrivGzipError(f"Failed to write output file: {e}")
        else:
            # In-place decompression
            args.append(input_path)
            self._execute_command(args, capture_output=False)
            
            # Return the expected output filename (remove .gz suffix)
            if input_path.endswith('.gz'):
                return input_path[:-3]
            else:
                return input_path
    
    def compress_data(self, data: bytes, compression_level: Optional[int] = None) -> bytes:
        """
        Compress data in memory using k230_priv_gzip.
        
        Args:
            data: Data to compress
            compression_level: Compression level (1-9, None for default)
            
        Returns:
            Compressed data
            
        Raises:
            K230PrivGzipError: If compression fails
        """
        args = ["-c"]  # Write to stdout
        
        # Add compression level if specified
        if compression_level is not None:
            if not 1 <= compression_level <= 9:
                raise K230PrivGzipError("Compression level must be between 1 and 9")
            args.append(f"-{compression_level}")
        
        # Use stdin for input data
        result = self._execute_command(args, input_data=data)
        return result.stdout
    
    def decompress_data(self, compressed_data: bytes) -> bytes:
        """
        Decompress data in memory using k230_priv_gzip.
        
        Args:
            compressed_data: Compressed data
            
        Returns:
            Decompressed data
            
        Raises:
            K230PrivGzipError: If decompression fails
        """
        args = ["-d", "-c"]  # Decompress and write to stdout
        
        # Use stdin for input data
        result = self._execute_command(args, input_data=compressed_data)
        return result.stdout
    
    def test_file(self, file_path: str) -> bool:
        """
        Test the integrity of a compressed file.
        
        Args:
            file_path: Path to compressed file
            
        Returns:
            True if file is valid, False otherwise
            
        Raises:
            K230PrivGzipError: If test fails due to errors
        """
        if not os.path.isfile(file_path):
            raise K230PrivGzipError(f"File not found: {file_path}")
        
        args = ["-t", file_path]
        
        try:
            self._execute_command(args, capture_output=False)
            return True
        except K230PrivGzipError:
            return False
    
    def list_file(self, file_path: str) -> Dict[str, Any]:
        """
        List information about a compressed file.
        
        Args:
            file_path: Path to compressed file
            
        Returns:
            Dictionary with file information
            
        Raises:
            K230PrivGzipError: If listing fails
        """
        if not os.path.isfile(file_path):
            raise K230PrivGzipError(f"File not found: {file_path}")
        
        args = ["-l", file_path]
        result = self._execute_command(args)
        
        # Parse the output (basic parsing)
        lines = result.stdout.decode('utf-8').strip().split('\n')
        if len(lines) >= 2:
            # Try to parse the last line which contains the file info
            info_line = lines[-1].split()
            if len(info_line) >= 5:
                return {
                    'compressed_size': int(info_line[0]),
                    'uncompressed_size': int(info_line[1]),
                    'ratio': float(info_line[2].rstrip('%')),
                    'uncompressed_name': info_line[-1],
                    'raw_output': result.stdout.decode('utf-8')
                }
        
        return {'raw_output': result.stdout.decode('utf-8')}
    
    def get_version(self) -> str:
        """
        Get the version of k230_priv_gzip.
        
        Returns:
            Version string
            
        Raises:
            K230PrivGzipError: If version command fails
        """
        args = ["-V"]
        result = self._execute_command(args)
        return result.stdout.decode('utf-8').strip()


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def create_argument_parser() -> argparse.ArgumentParser:
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        description='Python wrapper for k230_priv_gzip with cross-platform support',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s compress input.txt -o output.gz
  %(prog)s decompress input.gz -o output.txt
  %(prog)s compress-data "Hello World" -o compressed.gz
  %(prog)s test file.gz
  %(prog)s list file.gz
        """
    )
    
    parser.add_argument(
        '--executable',
        help='Path to k230_priv_gzip executable'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Compress command
    compress_parser = subparsers.add_parser('compress', help='Compress a file')
    compress_parser.add_argument('input', help='Input file path')
    compress_parser.add_argument('-o', '--output', help='Output file path')
    compress_parser.add_argument('-k', '--keep', action='store_true', help='Keep original file')
    compress_parser.add_argument('-f', '--force', action='store_true', help='Force overwrite')
    compress_parser.add_argument('-l', '--level', type=int, choices=range(1, 10), 
                               help='Compression level (1-9)')
    compress_parser.add_argument('-S', '--suffix', default='.gz', help='Suffix for compressed files')
    
    # Decompress command
    decompress_parser = subparsers.add_parser('decompress', help='Decompress a file')
    decompress_parser.add_argument('input', help='Input file path')
    decompress_parser.add_argument('-o', '--output', help='Output file path')
    decompress_parser.add_argument('-k', '--keep', action='store_true', help='Keep original file')
    decompress_parser.add_argument('-f', '--force', action='store_true', help='Force overwrite')
    
    # Compress data command
    compress_data_parser = subparsers.add_parser('compress-data', help='Compress data from stdin')
    compress_data_parser.add_argument('data', nargs='?', help='Data to compress (optional, reads from stdin)')
    compress_data_parser.add_argument('-o', '--output', help='Output file path')
    compress_data_parser.add_argument('-l', '--level', type=int, choices=range(1, 10), 
                                      help='Compression level (1-9)')
    
    # Decompress data command
    decompress_data_parser = subparsers.add_parser('decompress-data', help='Decompress data from stdin')
    decompress_data_parser.add_argument('data', nargs='?', help='Data to decompress (optional, reads from stdin)')
    decompress_data_parser.add_argument('-o', '--output', help='Output file path')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Test compressed file integrity')
    test_parser.add_argument('input', help='Input file path')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List compressed file information')
    list_parser.add_argument('input', help='Input file path')
    
    # Version command
    subparsers.add_parser('version', help='Show version information')
    
    return parser


def main() -> None:
    """Main entry point"""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    try:
        # Initialize the wrapper
        gzip_tool = K230PrivGzip(args.executable)

        if args.command == 'compress':
            output_path = gzip_tool.compress_file(
                args.input,
                args.output,
                args.keep,
                args.level,
                args.force,
                args.suffix
            )
            print(f"Compressed: {args.input} -> {output_path}")

        elif args.command == 'decompress':
            output_path = gzip_tool.decompress_file(
                args.input,
                args.output,
                args.keep,
                args.force
            )
            print(f"Decompressed: {args.input} -> {output_path}")

        elif args.command == 'compress-data':
            if args.data:
                data = args.data.encode('utf-8')
            else:
                data = sys.stdin.buffer.read()

            compressed_data = gzip_tool.compress_data(data, args.level)
            
            if args.output:
                with open(args.output, 'wb') as f:
                    f.write(compressed_data)
                print(f"Compressed data written to: {args.output}")
            else:
                sys.stdout.buffer.write(compressed_data)

        elif args.command == 'decompress-data':
            if args.data:
                data = args.data.encode('utf-8')
            else:
                data = sys.stdin.buffer.read()
            
            decompressed_data = gzip_tool.decompress_data(data)
            
            if args.output:
                with open(args.output, 'wb') as f:
                    f.write(decompressed_data)
                print(f"Decompressed data written to: {args.output}")
            else:
                sys.stdout.buffer.write(decompressed_data)

        elif args.command == 'test':
            is_valid = gzip_tool.test_file(args.input)
            if is_valid:
                print(f"File {args.input} is valid")
                sys.exit(0)
            else:
                print(f"File {args.input} is invalid")
                sys.exit(1)

        elif args.command == 'list':
            info = gzip_tool.list_file(args.input)
            if 'compressed_size' in info:
                print(f"Compressed: {info['compressed_size']} bytes")
                print(f"Uncompressed: {info['uncompressed_size']} bytes")
                print(f"Ratio: {info['ratio']}%")
                print(f"Name: {info['uncompressed_name']}")
            else:
                print(info['raw_output'])

        elif args.command == 'version':
            version = gzip_tool.get_version()
            print(version)

        else:
            parser.print_help()
            sys.exit(1)

    except K230PrivGzipError as e:
        logging.error(f"Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logging.info("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
