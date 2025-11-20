#!/usr/bin/env python3
import os
import sys
import subprocess
import tempfile
import shutil
from dataclasses import dataclass
from typing import Optional
from typing import List, Dict, Optional, Any, Callable

class ImageError(Exception):
    """Image processing related errors"""
    pass

@dataclass
class TocInsertData:
    """TOC insert data structure"""
    partition_name: str = ""
    partition_offset: int = 0
    partition_size: int = 0
    load: bool = False
    boot: bool = False

@dataclass
class Partition:
    """Partition information class"""
    name: str
    parent_image: str  # Parent image name
    in_partition_table: bool = True
    offset: int = 0
    size: Optional[int] = None
    image: Optional[str] = None  # Referenced image file
    partition_type: Optional[str] = None  # Partition type
    partition_type_uuid: Optional[str] = None  # GPT partition type UUID
    partition_uuid: Optional[str] = None  # Partition UUID
    bootable: bool = False
    read_only: bool = False
    hidden: bool = False
    autoresize: bool = False
    fill: bool = False
    logical: bool = False
    align: Optional[int] = None
    forced_primary: bool = False
    erase_size : int = 0
    flag: Optional[str] = None
    load: bool = False  # TOC load flag
    boot: int = 0  # TOC boot flag
    # Other possible attributes
    extraargs: Optional[str] = None

@dataclass
class Flash_type:
    name: str
    pebsize: int = 0
    lebsize: int = 0
    numpebs: int = 0
    minimum_io_unit_size: int = 0
    vid_header_offset: int = 0
    sub_page_size: int = 0

    is_uffs: bool = False
    page_size: int = 0
    block_pages: int = 0
    total_blocks: int = 0
    spare_size: int = 0
    status_offset: int = 0
    ecc_option: int = 0
    ecc_size: int = 0

    
@dataclass
class Image:
    """Image file information class"""
    name: str = None
    file: str = None
    image_type: str = None  # e.g., hdimage, vfat, ext4, etc.
    size: Optional[int] = None
    size_str: Optional[str] = None  # Original size string (with units)
    temporary: bool = False  # Whether it's a temporary file
    mountpoint: Optional[str] = None
    mountpath: Optional[str] = None
    exec_pre: Optional[str] = None
    exec_post: Optional[str] = None
    partitions: List[Partition] = None  # Partition list
    empty: bool = False  # Whether it's an empty image
    outfile: str = ""
    holes: List[int] = None  # Hole list
    handler: Any = None  # Associated handler
    handler_config: Dict[str, Any] = None  # Handler configuration
    done: bool = False
    flash_type : Flash_type = None  # Image type
    dependencies: List[Any] = None  # Dependency image list
    
    def __post_init__(self):
        if self.partitions is None:
            self.partitions = []
        if self.dependencies is None:
            self.dependencies = []
        if self.handler_config is None:
            self.handler_config = {}

class ImageHandler:
    """Image handler base class"""
    type: str = ""
    opts: List[str] = []
    
    def generate(self, image: Image):
        """Generate image file"""
        pass
    
    def setup(self, image: Image, config: Dict[str, Any]):
        """Set up image parameters"""
        pass

    def run(self,image: Image, config: Dict[str, str]):
        """Execute image processing"""
        raise NotImplementedError("Subclass must implement run method")

def insert_data(image: Image, image_path: str, size: int, offset: int, padding_byte: bytes) -> None:
    try:
        if not os.path.exists(image_path):
            raise ImageError(f"error: {image_path} not exist")

        with open(image.outfile, 'r+b') as f_out:
            f_out.seek(offset)
            file_size = os.path.getsize(image_path)  # Get source file size
            print(f"insert data: {image_path} to {image.outfile} at {offset} size {file_size}")
            with open(image_path, 'rb') as f_in:
                chunk_size = 4 * 1024 * 1024  # 4MB chunk
                remaining = file_size
                while remaining > 0:
                    chunk = f_in.read(min(chunk_size, remaining))
                    if not chunk:
                        break
                    f_out.write(chunk)
                    remaining -= len(chunk)
            
            if (pad_size := size - file_size) > 0:
                f_out.write(padding_byte * pad_size)
                print(f"write padding: {pad_size} bytes")
    except IOError as e:
        raise ImageError(f"Failed to write file: {str(e)}")


def mountpath(image: Image) -> str:
    """Get mount point of image"""
    if image.mountpath:
        return image.mountpath
    elif image.mountpoint:
        return image.mountpoint
    else:
        return None


def run_command(cmd: List[str], env: Optional[Dict[str, str]] = None) -> int:
    """Run external command and return result"""
    try:
        print(f"run: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env
        )
        return 0
    except subprocess.CalledProcessError as e:
        print(f"Command execution failed: {e.output}", file=sys.stderr)
        return e.returncode

def parse_size(size_str: str) -> int:
    """Parse size string with units"""
    if not size_str:
        return 0
        
    size_str = size_str.strip().lower()
    suffixes = {
        'k': 1024,
        'm': 1024 * 1024,
        'g': 1024 * 1024 * 1024,
        't': 1024 * 1024 * 1024 * 1024
    }
    
    # Handle hexadecimal
    if size_str.startswith('0x'):
        try:
            num = int(size_str, 16)
            return num
        except ValueError:
            raise ImageError(f"Invalid hexadecimal size format: {size_str}")
    
    # Extract number and unit
    num_str = ''
    suffix = ''
    for c in size_str:
        if c.isdigit() or c == '.':
            num_str += c
        else:
            suffix = c
            break
    
    if not num_str:
        raise ImageError(f"Invalid size format: {size_str}")
    
    try:
        num = float(num_str)
    except ValueError:
        raise ImageError(f"Invalid size format: {size_str}")
    
    # Apply unit
    if suffix in suffixes:
        return int(num * suffixes[suffix])
    else:
        # No unit, default to bytes
        return int(num)

def get_tool_path(tool_name: str, bin_dir: Optional[str] = None) -> str:
    """
    Get tool path, prioritize from specified bin directory, then from system PATH.
    Added support for different operating systems, especially executable file extensions on Windows.

    Args:
        tool_name: Tool name.
        bin_dir: Local tool directory, defaults to 'bin' subdirectory of current script directory.

    Returns:
        Absolute path of found tool, or tool name itself if not found.
    """
    # 1. Determine local bin directory
    if bin_dir is None:
        # Get bin subdirectory of current script directory
        # Note: os.path.abspath(__file__) only works when running as a file
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
        except NameError:
            # Compatible with interactive environment or non-main script calls
            current_dir = os.getcwd()

        bin_dir = os.path.join(current_dir, 'bin')

    # Define possible executable file extensions on different operating systems
    if os.name == 'nt':
        # Windows system: check common extensions
        executable_suffixes = ['', '.exe', '.cmd', '.bat']
    else:
        # POSIX systems (Linux, macOS, etc.): usually no extensions
        executable_suffixes = ['']

    # 2. First check bin directory
    for suffix in executable_suffixes:
        bin_tool = os.path.join(bin_dir, tool_name + suffix)

        # Check if file exists and is executable
        if os.path.exists(bin_tool) and os.access(bin_tool, os.X_OK):
            return bin_tool

    # 3. If not in bin directory, check system PATH
    # Use shutil.which instead of manually traversing PATH, it handles OS-related logic automatically
    system_tool = shutil.which(tool_name)
    if system_tool:
        # shutil.which returns absolute path
        return system_tool

    # 4. If not found anywhere, return tool name (let system handle at runtime)
    return tool_name

def prepare_image(image: Image, size = 0) -> int:
    """Prepare image file (create empty file of specified size)"""
    try:
        # path creat
        if not os.path.exists(os.path.dirname(image.outfile)):
            os.makedirs(os.path.dirname(image.outfile), exist_ok=True)
        with open(image.outfile, 'wb') as f:
            if not size:
                size = image.size
            if size:
                print(f"Preparing image file {image.outfile} size {size} bytes")
                f.seek(size - 1)
                f.write(b'\x00')
        return 0
    except IOError as e:
        raise ImageError(f"Unable to create image file {image.outfile}: {str(e)}")
