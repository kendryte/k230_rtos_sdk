#!/usr/bin/env python3
import os
import struct
from typing import Dict, List, Optional
from .common import ImageHandler, Image, ImageError, run_command, prepare_image, mountpath, parse_size, get_tool_path

class UffsHandler(ImageHandler):
    """UFFS filesystem handler"""
    type = "uffs"
    opts = ["extraargs", "size"]

    def __init__(self):
        self.config = {}
        self.flash_type = {}
        self.priv = None

    def setup(self, image: Image, config: Dict[str, str]) -> None:
        self.config = config
        
        # Check flash type configuration
        if not hasattr(image, 'flash_type') or not image.flash_type:
            raise ImageError("Flash type not specified")
        
        flash_type = image.flash_type
        if not getattr(flash_type, 'is_uffs', False):
            raise ImageError("Specified flash type is not uffs")
        
        # Check required flash parameters
        required_params = [
            'page_size', 
            'block_pages', 
            'total_blocks'
        ]
        for param in required_params:
            if not hasattr(flash_type, param) or getattr(flash_type, param) == 0:
                raise ImageError(f"Invalid {param} configuration in flash type")
        
        # Check ECC option validity
        if hasattr(flash_type, 'ecc_option') and flash_type.ecc_option > 3:
            raise ImageError("Invalid uffs flash ecc option")

    def parse(self, image: Image, config: Dict[str, str]) -> None:
        """Parse files and partition information in configuration"""
        # Process files list
        files = config.get("files", [])
        if isinstance(files, str):
            files = [files]

        for file_path in files:
            image.partitions.append(Partition(name="", parent_image=image.name, image=file_path))

        # Process segmented configuration
        file_sections = config.get("content", [])
        if not isinstance(file_sections, list):
            file_sections = [file_sections]

        for section in file_sections:
            if isinstance(section, dict):
                name = section.get("name")
                img = section.get("image")
                if name and img:
                    image.partitions.append(Partition(name=name, parent_image=image.name, image=img))

    def generate(self, image: Image) -> None:
        # Prepare image file
        prepare_image(image)

        # Get configuration parameters
        extraargs = self.config.get("extraargs", "")
        size_str = self.config.get("size", "")
        part_size = parse_size(size_str)

        # Verify image size alignment
        flash_type = image.flash_type
        block_size = flash_type.page_size * flash_type.block_pages
        if part_size % block_size != 0:
            raise ImageError(
                f"Invalid image size ({part_size}), must be aligned to {block_size} bytes"
            )

        # Calculate total blocks
        total_blocks = part_size // block_size

        # Build ECC option parameters
        ecc_opt = ["none", "soft", "hw", "auto"]
        ecc_option = flash_type.ecc_option if hasattr(flash_type, 'ecc_option') else 3  # default auto
        if ecc_option < 0 or ecc_option >= len(ecc_opt):
            raise ImageError(f"Invalid ECC option: {ecc_option}")

        # Delete existing output file
        if os.path.exists(image.outfile):
            os.remove(image.outfile)

        # Build mkuffs command
        cmd = [
            get_tool_path("mkuffs"),
            "-f", image.outfile,
            "-p", str(flash_type.page_size),
            "-s", str(flash_type.spare_size),
            "-b", str(flash_type.block_pages),
            "-t", str(total_blocks),
            "-x", ecc_opt[ecc_option],
            "-o", "0",
            "-d", mountpath(image),
            *extraargs.split()
        ]
        # Filter empty parameters
        cmd = [arg for arg in cmd if arg]

        # Execute command
        run_command(cmd)

        # Update image size
        try:
            stat_info = os.stat(image.outfile)
            image.size = stat_info.st_size
        except OSError as e:
            raise ImageError(f"Unable to get image file information: {str(e)}")


    def _get_child_image(self, parent_image: Image, name: str) -> Optional[Image]:
        """Get child image object"""
        for dep in parent_image.dependencies:
            if dep.name == name:
                return dep
        return None

    def run(self, image: Image, config: Dict[str, str]):
        self.setup(image, config)
        self.parse(image, config)
        self.generate(image)
