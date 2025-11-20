#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Python wrapper for mkimage executable with cross-platform support.

This script provides a Python interface to the mkimage tool,
handling different operating systems and providing a clean API for
creating and manipulating U-Boot images.
"""

import os
import sys
import subprocess
import argparse
import logging
import platform
import shutil
from pathlib import Path
from typing import List, Optional, Union, Dict, Any
from enum import Enum


class Architecture(Enum):
    """Supported architectures"""
    ALPHA = "alpha"
    ARM = "arm"
    ARM64 = "arm64"
    I386 = "i386"
    IA64 = "ia64"
    M68K = "m68k"
    MICROBLAZE = "microblaze"
    MIPS = "mips"
    NIOS2 = "nios2"
    PPC = "ppc"
    RISCV = "riscv"
    SANDBOX = "sandbox"
    SH = "sh"
    SPARC = "sparc"
    X86_64 = "x86_64"
    XTENSA = "xtensa"


class OperatingSystem(Enum):
    """Supported operating systems"""
    OPENBSD = "openbsd"
    NETBSD = "netbsd"
    FREEBSD = "freebsd"
    BSD4_4 = "4_4bsd"
    LINUX = "linux"
    SOLARIS = "solaris"
    SCO = "sco"
    IRIX = "irix"
    QNX = "qnx"
    UBOOT = "u-boot"
    INTEGRITY = "integrity"


class ImageType(Enum):
    """Supported image types"""
    AISIMAGE = "aisimage"
    ATMELIMAGE = "atmelimage"
    COPRO = "copro"
    FILESYSTEM = "filesystem"
    FIRMWARE = "firmware"
    FIRMWARE_IVT = "firmware_ivt"
    FLAT_DT = "flat_dt"
    FPGA = "fpga"
    GPIMAGE = "gpimage"
    IMX8IMAGE = "imx8image"
    IMX8MIMAGE = "imx8mimage"
    IMXIMAGE = "imximage"
    INVALID = "invalid"
    KERNEL = "kernel"
    KERNEL_NOLOAD = "kernel_noload"
    KWBIMAGE = "kwbimage"
    LPC32XXIMAGE = "lpc32xximage"
    MTK_IMAGE = "mtk_image"
    MULTI = "multi"
    MXSIMAGE = "mxsimage"
    OMAPIMAGE = "omapimage"
    PBLIMAGE = "pblimage"
    PMMC = "pmmc"
    RAMDISK = "ramdisk"
    RKIMAGE = "rkimage"
    RKSD = "rksd"
    RKSPI = "rkspi"
    SCRIPT = "script"
    SOCFPGAIMAGE = "socfpgaimage"
    SOCFPGAIMAGE_V1 = "socfpgaimage_v1"
    STANDALONE = "standalone"
    STM32IMAGE = "stm32image"
    SUNXI_EGON = "sunxi_egon"
    SUNXI_TOC0 = "sunxi_toc0"
    TEE = "tee"
    UBLIMAGE = "ublimage"
    VYBRIDIMAGE = "vybridimage"
    X86_SETUP = "x86_setup"
    ZYNQIMAGE = "zynqimage"
    ZYNQMPBIF = "zynqmpbif"
    ZYNQMPIMAGE = "zynqmpimage"


class CompressionType(Enum):
    """Supported compression types"""
    NONE = "none"
    GZIP = "gzip"
    BZIP2 = "bzip2"
    LZ4 = "lz4"
    LZMA = "lzma"
    LZO = "lzo"
    ZSTD = "zstd"


class MkImageError(Exception):
    """Custom exception for mkimage operations"""
    pass


class MkImage:
    """
    Python wrapper for mkimage executable with cross-platform support.
    
    This class provides a Python interface to the mkimage tool,
    handling different operating systems and providing a clean API for
    creating and manipulating U-Boot images.
    """

    def __init__(self, executable_path: Optional[str] = None):
        """
        Initialize the mkimage wrapper.
        
        Args:
            executable_path: Path to mkimage executable. If None,
                           will try to find it in standard locations.
        
        Raises:
            MkImageError: If the executable cannot be found.
        """
        self.executable_path = self._find_executable(executable_path)
        self.logger = logging.getLogger(__name__)
        
    def _find_executable(self, provided_path: Optional[str] = None) -> str:
        """
        Find the mkimage executable on the system, handling Windows naming conventions.
        
        Args:
            provided_path: Explicit path to the executable
            
        Returns:
            Absolute path to the executable
            
        Raises:
            MkImageError: If executable cannot be found
        """
        executable_name = "mkimage"
        
        # 1. Check if an explicit path was provided
        if provided_path:
            provided_path_obj = Path(provided_path)
            # Use os.access for executable check for clarity
            if provided_path_obj.is_file() and os.access(provided_path_obj, os.X_OK):
                return str(provided_path_obj.resolve())
            else:
                raise MkImageError(f"Executable not found or not executable: {provided_path}")

        # Determine the correct executable name for the platform's local search
        if platform.system() == "Windows":
            full_executable_name = f"{executable_name}.exe"
        else:
            full_executable_name = executable_name

        # 2. Try to find executable in the same directory as this script (bin/subdir)
        # Path(__file__).resolve().parent gets the script's directory consistently.
        script_dir = Path(__file__).resolve().parent
        local_executable = script_dir / "bin" / full_executable_name

        if local_executable.exists() and os.access(local_executable, os.X_OK):
            return str(local_executable.resolve())

        # 3. Try to find in system PATH using shutil.which (platform-aware)
        # shutil.which handles platform differences (like 'which' vs 'where') 
        # and automatically checks for extensions (.exe) on Windows.
        system_executable = shutil.which(executable_name)
        
        if system_executable:
            return system_executable

        # 4. Final failure if not found
        raise MkImageError(
            f"'{full_executable_name}' executable not found. Please ensure it is installed "
            "and accessible via PATH, or provide the path explicitly."
        )
    
    def _execute_command(self, args: List[str], input_data: Optional[bytes] = None,
                        capture_output: bool = True) -> subprocess.CompletedProcess:
        """
        Execute the mkimage command with proper error handling.
        
        Args:
            args: Command line arguments
            input_data: Data to pipe to stdin (optional)
            capture_output: Whether to capture stdout/stderr
            
        Returns:
            subprocess.CompletedProcess object
            
        Raises:
            MkImageError: If command execution fails
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
                error_msg = f"mkimage failed with return code {result.returncode}"
                if result.stderr:
                    error_msg += f": {result.stderr.decode('utf-8', errors='replace')}"
                raise MkImageError(error_msg)
            
            return result
            
        except FileNotFoundError:
            raise MkImageError(f"Executable not found: {self.executable_path}")
        except subprocess.SubprocessError as e:
            raise MkImageError(f"Subprocess error: {e}")
    
    def create_image(self, data_files: Union[str, List[str]], output_file: str,
                     arch: Optional[Union[Architecture, str]] = None,
                     os_type: Optional[Union[OperatingSystem, str]] = None,
                     image_type: Optional[Union[ImageType, str]] = None,
                     compression: Optional[Union[CompressionType, str]] = None,
                     load_addr: Optional[str] = None,
                     entry_point: Optional[str] = None,
                     image_name: Optional[str] = None,
                     second_image_name: Optional[str] = None,
                     xip: bool = False,
                     no_data: bool = False,
                     quiet: bool = False,
                     verbose: bool = False) -> str:
        """
        Create a U-Boot image using mkimage.
        
        Args:
            data_files: Path to data file(s)
            output_file: Output image file path
            arch: Architecture (Architecture enum or string)
            os_type: Operating system (OperatingSystem enum or string)
            image_type: Image type (ImageType enum or string)
            compression: Compression type (CompressionType enum or string)
            load_addr: Load address (hex string)
            entry_point: Entry point (hex string)
            image_name: Image name
            second_image_name: Second image name
            xip: Execute in place
            no_data: Create image with no data
            quiet: Quiet mode
            verbose: Verbose mode

        Returns:
            Path to the created image file
            
        Raises:
            MkImageError: If image creation fails
        """
        args = []
        
        # Handle data files
        if isinstance(data_files, str):
            data_files = [data_files]
        
        # Validate data files exist
        for data_file in data_files:
            if not os.path.isfile(data_file):
                raise MkImageError(f"Data file not found: {data_file}")
        
        # Add options
        if arch:
            arch_value = arch.value if isinstance(arch, Architecture) else arch
            args.extend(["-A", arch_value])
        
        if os_type:
            os_value = os_type.value if isinstance(os_type, OperatingSystem) else os_type
            args.extend(["-O", os_value])
        
        if image_type:
            type_value = image_type.value if isinstance(image_type, ImageType) else image_type
            args.extend(["-T", type_value])
        
        if compression:
            comp_value = compression.value if isinstance(compression, CompressionType) else compression
            args.extend(["-C", comp_value])
        
        if load_addr:
            args.extend(["-a", load_addr])
        
        if entry_point:
            args.extend(["-e", entry_point])
        
        if image_name:
            args.extend(["-n", image_name])
        
        if second_image_name:
            args.extend(["-R", second_image_name])
        
        if xip:
            args.append("-x")
        
        if no_data:
            args.append("-s")
        
        if quiet:
            args.append("-q")
        
        if verbose:
            args.append("-v")
        
        # Add data files
        args.extend(["-d", ":".join(data_files)])
        
        # Add output file
        args.append(output_file)
        
        # Execute command
        self._execute_command(args, capture_output=False)

        return output_file
    
    def list_image_info(self, image_file: str, image_type: Optional[Union[ImageType, str]] = None,
                       quiet: bool = False) -> Dict[str, Any]:
        """
        List information about an image file.
        
        Args:
            image_file: Path to image file
            image_type: Image type for parsing (ImageType enum or string)
            quiet: Quiet mode
            
        Returns:
            Dictionary with image information
            
        Raises:
            MkImageError: If listing fails
        """
        if not os.path.isfile(image_file):
            raise MkImageError(f"Image file not found: {image_file}")
        
        args = ["-l", image_file]
        
        if image_type:
            type_value = image_type.value if isinstance(image_type, ImageType) else image_type
            args.extend(["-T", type_value])
        
        if quiet:
            args.append("-q")
        
        result = self._execute_command(args)
        
        # Parse the output (basic parsing)
        output = result.stdout.decode('utf-8').strip()
        return {
            'raw_output': output,
            'image_file': image_file
        }
    
    def create_fit_image(self, fit_source: str, output_file: str,
                        dtc_options: Optional[str] = None,
                        dtb_files: Optional[List[str]] = None,
                        ramdisk_file: Optional[str] = None,
                        external_data: bool = False,
                        align_size: Optional[str] = None,
                        auto_fit: bool = False,
                        update_timestamp: bool = False,
                        key_dir: Optional[str] = None,
                        key_dest: Optional[str] = None,
                        key_name_hint: Optional[str] = None,
                        signing_key: Optional[str] = None,
                        comment: Optional[str] = None,
                        resign: bool = False,
                        external_pos: Optional[str] = None,
                        required_keys: bool = False,
                        openssl_engine: Optional[str] = None,
                        algorithm: Optional[str] = None) -> str:
        """
        Create a FIT (Flattened Image Tree) image.
        
        Args:
            fit_source: FIT source file path or 'auto' for auto-generation
            output_file: Output FIT image file path
            dtc_options: Device tree compiler options
            dtb_files: List of DTB files to append
            ramdisk_file: Ramdisk file path
            external_data: Place data outside FIT structure
            align_size: Align size for FIT structure (hex)
            auto_fit: Use auto-generation
            update_timestamp: Update timestamp in FIT
            key_dir: Directory containing private keys
            key_dest: Write public keys to this DTB file
            key_name_hint: Key name hint
            signing_key: Signing key (in lieu of key_dir)
            comment: Comment in signature node
            resign: Re-sign existing FIT image
            external_pos: Place external data at static position
            required_keys: Mark keys as required in DTB
            openssl_engine: OpenSSL engine for signing
            algorithm: Algorithm for signing
            
        Returns:
            Path to the created FIT image file
            
        Raises:
            MkImageError: If FIT image creation fails
        """
        args = []
        
        # Add FIT source
        if auto_fit:
            args.extend(["-f", "auto"])
        else:
            if not os.path.isfile(fit_source):
                raise MkImageError(f"FIT source file not found: {fit_source}")
            args.extend(["-f", fit_source])
        
        # Add options
        if dtc_options:
            args.extend(["-D", dtc_options])
        
        if dtb_files:
            for dtb_file in dtb_files:
                if not os.path.isfile(dtb_file):
                    raise MkImageError(f"DTB file not found: {dtb_file}")
                args.extend(["-b", dtb_file])
        
        if ramdisk_file:
            if not os.path.isfile(ramdisk_file):
                raise MkImageError(f"Ramdisk file not found: {ramdisk_file}")
            args.extend(["-i", ramdisk_file])
        
        if external_data:
            args.append("-E")
        
        if align_size:
            args.extend(["-B", align_size])
        
        if update_timestamp:
            args.append("-t")
        
        # Signing options
        if key_dir:
            args.extend(["-k", key_dir])
        
        if key_dest:
            args.extend(["-K", key_dest])
        
        if key_name_hint:
            args.extend(["-g", key_name_hint])
        
        if signing_key:
            args.extend(["-G", signing_key])
        
        if comment:
            args.extend(["-c", comment])
        
        if resign:
            args.append("-F")
        
        if external_pos:
            args.extend(["-p", external_pos])
        
        if required_keys:
            args.append("-r")
        
        if openssl_engine:
            args.extend(["-N", openssl_engine])
        
        if algorithm:
            args.extend(["-o", algorithm])
        
        # Add output file
        args.append(output_file)
        
        # Execute command
        self._execute_command(args, capture_output=False)
        
        return output_file
    
    def get_version(self) -> str:
        """
        Get the version of mkimage.
        
        Returns:
            Version string
            
        Raises:
            MkImageError: If version command fails
        """
        args = ["-V"]
        result = self._execute_command(args)
        return result.stdout.decode('utf-8').strip()
    
    def get_supported_image_types(self) -> List[str]:
        """
        Get list of supported image types.
        
        Returns:
            List of supported image type names
            
        Raises:
            MkImageError: If command fails
        """
        args = ["-T", "list"]
        result = self._execute_command(args)
        
        # Parse the output to extract image types
        output = result.stdout.decode('utf-8')
        lines = output.strip().split('\n')
        
        image_types = []
        for line in lines[1:]:  # Skip the first line (error message)
            line = line.strip()
            if line and not line.startswith('Invalid'):
                # Extract the image type name (first word)
                parts = line.split()
                if parts:
                    image_types.append(parts[0])
        
        return image_types


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
        description='Python wrapper for mkimage with cross-platform support',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s create -d kernel.bin -A riscv -O linux -T kernel -C gzip -o uImage
  %(prog)s list uImage
  %(prog)s fit -f fit.its -o fitImage
  %(prog)s version
        """
    )

    parser.add_argument(
        '--executable',
        help='Path to mkimage executable'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Create command
    create_parser = subparsers.add_parser('create', help='Create a U-Boot image')
    create_parser.add_argument('-d', '--data', required=True, help='Data file(s) (comma-separated)')
    create_parser.add_argument('-o', '--output', required=True, help='Output image file')
    create_parser.add_argument('-A', '--arch', help='Architecture')
    create_parser.add_argument('-O', '--os', help='Operating system')
    create_parser.add_argument('-T', '--type', help='Image type')
    create_parser.add_argument('-C', '--compression', help='Compression type')
    create_parser.add_argument('-a', '--load-addr', help='Load address (hex)')
    create_parser.add_argument('-e', '--entry-point', help='Entry point (hex)')
    create_parser.add_argument('-n', '--name', help='Image name')
    create_parser.add_argument('-R', '--second-name', help='Second image name')
    create_parser.add_argument('-x', '--xip', action='store_true', help='Execute in place')
    create_parser.add_argument('-s', '--no-data', action='store_true', help='Create image with no data')
    create_parser.add_argument('-q', '--quiet', action='store_true', help='Quiet mode')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List image information')
    list_parser.add_argument('image', help='Image file path')
    list_parser.add_argument('-T', '--type', help='Image type for parsing')
    list_parser.add_argument('-q', '--quiet', action='store_true', help='Quiet mode')
    
    # FIT command
    fit_parser = subparsers.add_parser('fit', help='Create FIT image')
    fit_parser.add_argument('-f', '--fit-source', required=True, help='FIT source file or "auto"')
    fit_parser.add_argument('-o', '--output', required=True, help='Output FIT image file')
    fit_parser.add_argument('-D', '--dtc-options', help='Device tree compiler options')
    fit_parser.add_argument('-b', '--dtb', action='append', help='DTB files to append')
    fit_parser.add_argument('-i', '--ramdisk', help='Ramdisk file')
    fit_parser.add_argument('-E', '--external-data', action='store_true', help='Place data outside FIT')
    fit_parser.add_argument('-B', '--align', help='Align size (hex)')
    fit_parser.add_argument('-t', '--update-timestamp', action='store_true', help='Update timestamp')
    
    # Version command
    subparsers.add_parser('version', help='Show version information')
    
    # Types command
    subparsers.add_parser('types', help='List supported image types')
    
    return parser


def main() -> None:
    """Main entry point"""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    try:
        # Initialize the wrapper
        mkimage_tool = MkImage(args.executable)

        if args.command == 'create':
            # Parse data files
            data_files = [f.strip() for f in args.data.split(',')]

            output_path = mkimage_tool.create_image(
                data_files=data_files,
                output_file=args.output,
                arch=args.arch,
                os_type=args.os,
                image_type=args.type,
                compression=args.compression,
                load_addr=args.load_addr,
                entry_point=args.entry_point,
                image_name=args.name,
                second_image_name=args.second_name,
                xip=args.xip,
                no_data=args.no_data,
                quiet=args.quiet,
                verbose=args.verbose
            )
            print(f"Created image: {output_path}")

        elif args.command == 'list':
            info = mkimage_tool.list_image_info(
                args.image,
                args.type,
                args.quiet
            )
            print(info['raw_output'])

        elif args.command == 'fit':
            output_path = mkimage_tool.create_fit_image(
                fit_source=args.fit_source,
                output_file=args.output,
                dtc_options=args.dtc_options,
                dtb_files=args.dtb,
                ramdisk_file=args.ramdisk,
                external_data=args.external_data,
                align_size=args.align,
                auto_fit=(args.fit_source == "auto"),
                update_timestamp=args.update_timestamp
            )
            print(f"Created FIT image: {output_path}")

        elif args.command == 'version':
            version = mkimage_tool.get_version()
            print(version)

        elif args.command == 'types':
            types = mkimage_tool.get_supported_image_types()
            print("Supported image types:")
            for img_type in types:
                print(f"  {img_type}")

        else:
            parser.print_help()
            sys.exit(1)

    except MkImageError as e:
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
