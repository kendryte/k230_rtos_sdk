#!/usr/bin/env python3
import logging
import os
import struct
from typing import Dict, List, Optional, Any
from .common import ImageHandler, Image, ImageError, run_command, Partition, prepare_image, mountpath, get_tool_path

# Configure logger
logger = logging.getLogger(__name__)

class VFatHandler(ImageHandler):
    """VFAT filesystem handler"""
    type = "vfat"
    opts = ["extraargs", "label", "files", "minimize"]

    def __init__(self):
        self.config = {}

    def setup(self, image: Image, config: Dict[str, str]) -> None:
        self.config = config
        # Check image size
        if not image.size:
            raise ImageError("Image size not set or zero")

        label = config.get("label", "")
        if label and len(label) > 11:
            raise ImageError("VFAT volume label cannot exceed 11 characters")

    def generate(self, image: Image) -> None:
        # Prepare image file
        prepare_image(image)

        # Get configuration parameters
        extraargs = self.config.get("extraargs", "")
        label = self.config.get("label", "")
        minimize = self.config.get("minimize", False)

        # Build label argument
        label_arg = f"-n {label}" if label else ""

        # Execute mkdosfs to create vfat filesystem
        cmd = [get_tool_path("mkdosfs"), *extraargs.split(), *label_arg.split(), image.outfile]
        # Filter empty string arguments
        cmd = [arg for arg in cmd if arg]
        
        # Check if formatting was successful
        if run_command(cmd) != 0:
            raise ImageError(f"Failed to create VFAT filesystem on {image.outfile}")

        # Process files in partitions
        for part in image.partitions:
            child_image = self._get_child_image(image, part.image)
            if not child_image:
                raise ImageError(f"Child image not found: {part.image}")

            src_path = child_image.outfile
            target = part.name or os.path.basename(src_path)

            # Create target directory (if there are subdirectories)
            if '/' in target:
                dir_path = os.path.dirname(target)
                mmd_cmd = [get_tool_path("mmd"), "-DsS", "-i", image.outfile, f"::{dir_path}"]
                env = os.environ.copy()
                if run_command(mmd_cmd, env=env) != 0:
                    raise ImageError(f"Failed to create directory '::{dir_path}' in VFAT image")

            # Copy files to vfat image
            mcopy_cmd = [get_tool_path("mcopy"), "-sp", "-i", image.outfile, src_path, f"::{target}"]
            env = os.environ.copy()
            
            # Check if copy was successful (will fail if image is too small)
            if run_command(mcopy_cmd, env=env) != 0:
                raise ImageError(f"Failed to copy '{src_path}' to VFAT image. The image size may be too small.")

        # If not empty image and no partitions, copy files from mountpath
        if not image.empty and not image.partitions:
            mpath = mountpath(image)
            if os.path.exists(mpath):
                files = os.listdir(mpath)
                for file in files:
                    src_file = os.path.join(mpath, file)
                    mcopy_cmd = [get_tool_path("mcopy"), "-sp", "-i", image.outfile, src_file, "::"]
                    env = os.environ.copy()
                    if run_command(mcopy_cmd, env=env) != 0:
                        raise ImageError(f"Failed to copy '{file}' from mountpath to VFAT image.")

        # Handle image minimization
        if minimize:
            last_pos = self._find_last_valid_pos(image)
            if last_pos <= 0:
                raise ImageError("Unable to find valid filesystem position, minimization failed")

            # Get current file size
            current_size = os.stat(image.outfile).st_size

            # Truncate file to minimum necessary size
            if last_pos < current_size:
                with open(image.outfile, 'r+b') as f:
                    f.truncate(last_pos)
                image.size = last_pos
                logger.info(f"minimize image size to {last_pos} bytes 0x{last_pos:0x}")


    def _find_last_valid_pos(self, image: Image) -> int:
        """
        Finds the position of the last valid cluster for image minimization.
        Adds robust handling for VFAT (FAT16/FAT32) compatibility checks and corrupted FAT fields,
        and corrects the validity check logic for FAT16 clusters.
        """
        try:
            with open(image.outfile, 'rb') as f:
                current_file_size = os.fstat(f.fileno()).st_size
                
                # --- Read Boot Sector Key Fields ---
                f.seek(11); bytes_per_sector = struct.unpack('<H', f.read(2))[0]
                f.seek(13); sectors_per_cluster = struct.unpack('<B', f.read(1))[0] 
                f.seek(14); reserved_sectors = struct.unpack('<H', f.read(2))[0]
                f.seek(16); num_fats = struct.unpack('<B', f.read(1))[0] 
                f.seek(17); root_entry_count = struct.unpack('<H', f.read(2))[0]
                f.seek(19); total_sectors_16 = struct.unpack('<H', f.read(2))[0]
                f.seek(22); sectors_per_fat_16 = struct.unpack('<H', f.read(2))[0]
                f.seek(32); total_sectors_32 = struct.unpack('<I', f.read(4))[0]
                f.seek(36); sectors_per_fat_32 = struct.unpack('<I', f.read(4))[0]

                # --- 1. Determine FAT Sector Size (Handle corrupt FAT32 field) ---
                sectors_per_fat = 0
                
                # Try using the FAT32 fields
                if sectors_per_fat_32 != 0:
                    fat_size_bytes_32 = sectors_per_fat_32 * bytes_per_sector
                    total_fat_region_size_32 = reserved_sectors * bytes_per_sector + num_fats * fat_size_bytes_32
                    
                    # If the size calculated by FAT32 exceeds the actual file size, the field is corrupt, fall back.
                    if total_fat_region_size_32 > current_file_size:
                        logger.debug("DEBUG: FAT32 sector count appears corrupt. Falling back to FAT16 field.")
                    else:
                        sectors_per_fat = sectors_per_fat_32

                # If FAT32 field is invalid or corrupt, use FAT16 field
                if sectors_per_fat == 0 and sectors_per_fat_16 != 0:
                    sectors_per_fat = sectors_per_fat_16

                if sectors_per_fat == 0:
                    raise ImageError(f"FAT sector count is zero or invalid.")

                # Use the determined sectors_per_fat to finalize key parameter calculation
                fat_size_bytes = sectors_per_fat * bytes_per_sector
                total_fat_region_size = reserved_sectors * bytes_per_sector + num_fats * sectors_per_fat * bytes_per_sector
                
                if total_fat_region_size > current_file_size:
                    raise ImageError(f"Calculated total FAT region size ({total_fat_region_size}) exceeds image size ({current_file_size}). Cannot minimize.")
                
                # --- 2. Determine FAT Type (FAT Type Detection) ---
                total_sectors = total_sectors_32 if total_sectors_32 != 0 else total_sectors_16
                if total_sectors == 0:
                    raise ImageError("Total sectors count is zero or invalid.")

                root_dir_sectors = (root_entry_count * 32 + bytes_per_sector - 1) // bytes_per_sector
                data_sectors = total_sectors - (reserved_sectors + num_fats * sectors_per_fat + root_dir_sectors)
                total_clusters = data_sectors // sectors_per_cluster if sectors_per_cluster != 0 else 0
                
                fat_type = "FAT32"
                entry_bytes = 4
                mask = 0x0FFFFFFF
                
                # FAT32 cluster value check: it is valid as long as it's not 0x00000000 (free) AND less than 0x0FFFFFF8 (end of chain).
                is_used = lambda entry: entry != 0x00000000 and entry < 0x0FFFFFF8
                
                if total_clusters < 4085:
                    # Theoretically FAT12, but we treat it as unsupported
                    raise ImageError("FAT12 not supported for minimization.")
                elif total_clusters < 65525:
                    # FAT16
                    fat_type = "FAT16"
                    entry_bytes = 2
                    mask = 0xFFFF
                    # FAT16 cluster value check: it is considered an allocated or used cluster, including the end-of-chain marker (0xFFF8-0xFFFF), as long as it's not 0x0000 (free) OR 0x0001 (reserved).
                    is_used = lambda entry: entry >= 0x0002

                logger.debug(f"DEBUG: Detected FAT Type: {fat_type} (Total Clusters: {total_clusters})")

                # --- 3. Calculate Offsets and Iterate (FAT Iteration) ---
                data_region_offset = total_fat_region_size
                cluster_size_bytes = sectors_per_cluster * bytes_per_sector
                fat_offset = reserved_sectors * bytes_per_sector
                
                num_entries = fat_size_bytes // entry_bytes 
                last_used_cluster = 0
                
                # Iterate through the FAT table to find the last used cluster (starting from cluster 2)
                for cluster in range(2, num_entries):
                    read_offset = fat_offset + cluster * entry_bytes
                    
                    f.seek(read_offset) 
                    buffer = f.read(entry_bytes)
                    
                    if len(buffer) < entry_bytes:
                        break 
                    
                    # Unpack based on detected FAT type
                    if fat_type == "FAT16":
                        fat_entry = struct.unpack('<H', buffer)[0]
                    elif fat_type == "FAT32":
                        fat_entry = struct.unpack('<I', buffer)[0] & mask
                    
                    # Check for valid used cluster entry
                    if is_used(fat_entry):
                        last_used_cluster = cluster

                if last_used_cluster == 0:
                    return -1

                # Calculate the end position of the last cluster
                final_offset = data_region_offset + (last_used_cluster + 1) * cluster_size_bytes
                logger.debug(f"DEBUG: Last used cluster: {last_used_cluster}")
                return final_offset
        except Exception as e:
            raise ImageError(f"Failed to find last valid position: {type(e).__name__} - {str(e)}")
        
            
    def _get_child_image(self, parent_image: Image, name: str) -> Optional[Image]:
        for dep in parent_image.dependencies:
            if dep.name == name:
                return dep
        return None

    def run(self, image: Image, config: Dict[str, Any]):
        self.setup(image, config)
        self.generate(image)
