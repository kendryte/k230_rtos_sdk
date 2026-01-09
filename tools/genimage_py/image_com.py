import logging
import struct
import subprocess
import uuid
import os
import stat
import zlib
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple, Iterable
from .common import ImageHandler, Image, Partition, ImageError, run_command, prepare_image, parse_size, insert_data, safe_to_int

# Configure logger
logger = logging.getLogger(__name__)
from .lib.toc import *
from .lib.gpt import *

class ComImageHandler(ImageHandler):
    opts = [
        "partition-table-type", "gpt-location", "gpt-no-backup",
        "disk-uuid", "disksig", "disk-signature",
        "toc", "toc-offset"
    ]

    def __init__(self):
        self.config: Dict[str, Any] = {}

        self.disksig: int = 0
        self.disk_uuid: str = str(uuid.uuid4())
        self.table_type: int = TYPE_NONE
        self.gpt_location: int = 2 * 512
        self.gpt_no_backup: bool = False
        self.file_size: int = 0

        self.toc_enable: bool = False
        self.toc_offset: int = 0
        self.toc_num: int = 0
        self.toc: Optional[Toc] = None

    def _parse_config_parameters(self) -> None:
        """Parse configuration parameters to private data structure"""
        config = self.config
        self.gpt_location = self._parse_size(config.get("gpt-location", 0))
        self.gpt_no_backup = config.get("gpt-no-backup", False)

        # Parse TOC configuration
        self.toc_enable = config.get("toc", False)
        self.toc_offset = self._parse_size(config.get("toc-offset", 0))

        # Parse partition table type
        table_type = config.get("partition-table-type", "none")
        if table_type == "none":
            self.table_type = TYPE_NONE
        elif table_type in ["mbr", "dos"]:
            self.table_type = TYPE_MBR
        elif table_type == "gpt":
            self.table_type = TYPE_GPT
        elif table_type == "hybrid":
            self.table_type = TYPE_HYBRID
        else:
            raise ImageError(f"Invalid partition table type: {table_type}")


    def _parse_size(self, size: Any) -> int:
        """Parse size string with units (K, M, G)"""
        if isinstance(size, int):
            return size
        if not isinstance(size, str):
            raise ImageError(f"Invalid size format: {size}")

        return parse_size(size)

    def validate_hybrid_partition_table(self, image: Image) -> None:
        """Validate hybrid partition table validity"""
        if self.table_type == TYPE_HYBRID:
            hybrid_entries = sum(1 for p in image.partitions
                                if p.in_partition_table and p.partition_type)
            logger.debug(f"Hybrid partition table: {hybrid_entries} partitions")
            if hybrid_entries == 0:
                raise ImageError("Hybrid partition table must contain at least one partition with partition-type")
            if hybrid_entries > 3:
                raise ImageError(f"Hybrid partition table supports max 3 partitions, currently has {hybrid_entries}")

    def _validate_mbr_partition_count(self, image: Image) -> None:
        """Validate MBR partition count"""
        # MBR partition count check (maximum 4 primary partitions)
        if self.table_type == TYPE_MBR:
            user_parts = [p for p in image.partitions if p.in_partition_table]
            if len(user_parts) > 4:
                raise ImageError(f"MBR partition table supports a maximum of 4 primary partitions, current configuration has {len(user_parts)}")

    def validate_config_parameters(self) -> None:
        """Validate configuration parameters"""
        if 0 == self.gpt_location:
            self.gpt_location = 2 * 512

        # Validate GPT location
        if self.gpt_location % 512:
            raise ImageError(f"GPT table location ({self.gpt_location}) must be a multiple of 512 bytes")

    def setup_toc(self, image: Image, partition_name: str) -> None:
        """setup toc"""
        if not self.toc_enable:
            return

        toc_offset = self.toc_offset if self.toc_offset else 0

        toc = Toc(toc_offset)
        index_count = 0

        # Create TOC entries for each partition
        for part in image.partitions:
            if part.name.startswith('['):
                continue

            toc.add_toc_entry(TocInsertData(
                    partition_name = part.name,
                    partition_offset = safe_to_int(part.offset),
                    partition_size = safe_to_int(part.size),
                    load = 1 if part.load else 0,
                    boot = safe_to_int(part.boot),
                )
            )
            index_count += 1

        if index_count > 0:
            # Creat [TOC] partition
            toc_size = 64 * index_count

            self.add_partition_table(image,
                partition_name= partition_name,
                offset= toc_offset,
                size= toc_size,
                in_partition_table=False
            )
            self.toc = toc
            self.toc_num = self.toc.entries_num
            logger.debug(f"TOC Partition: {partition_name} (offset 0x{toc_offset:x}, size 0x{toc_size:x})")

    def write_toc(self, image: Image, write_offset = None) -> None:
        """write toc data"""
        if self.toc_enable and self.toc_num and self.toc:
            logger.debug("writing TOC")

            toc = self.toc
            # Build toc data
            toc_data = toc.get_toc_data()

            if toc_data is None:
                return

            # Write toc data
            if write_offset is None:
                write_offset = toc.toc_offset if toc.toc_offset else 0

            with open(image.outfile, 'r+b') as f:
                f.seek(write_offset)
                f.write(toc_data)

            logger.debug(f"TOC written at offset 0x{write_offset:x}, size {len(toc_data)} bytes")

    def add_partition_table(self, image: Image, partition_name: str, offset: int, size: int, in_partition_table: bool) -> None:
        entry = Partition(
            name=partition_name,
            parent_image=image.name,
            offset=offset,
            size=size,
            in_partition_table=in_partition_table
        )
        image.partitions.append(entry)

    def _image_has_hole_covering(self, image: Image, child_name: str, start: int, end: int) -> bool:
        """Check if the sub-image has a hole covering the specified range"""
        if not child_name:
            return False

        logger.debug(f"check child image {child_name} {start} {end}")
        for dep in image.partitions:
            if dep.name == child_name:
                for hole in dep.holes:
                    if hole.start <= start and end <= hole.end:
                        return True
        return False

    def check_overlap(self, image: Image, part: Partition) -> bool:
        """Check if partitions overlap"""
        for other in image.partitions:
            if part == other:
                return False

            # print(f"check overlap {part.name} {other.name}")
            # Check if they are completely non-overlapping
            if part.offset >= other.offset + other.size:
                continue
            if other.offset >= part.offset + part.size:
                continue

            # Check for covering hole
            start = max(part.offset, other.offset)
            end = min(part.offset + part.size, other.offset + other.size)

            if self._image_has_hole_covering(image, other.image, start - other.offset, end - other.offset):
                continue

            # Overlap found
            raise ImageError(
                f"Partition {part.name} (offset 0x{part.offset:x}, size 0x{part.size:x}) "
                f"overlaps with previous partition {other.name} (offset 0x{other.offset:x}, size 0x{other.size:x})"
            )
        return False

    @staticmethod
    def roundup(value: int, align: int) -> int:
        """Round up to alignment boundary"""
        if align == 0:
            return value
        return ((value - 1) // align + 1) * align

    @staticmethod
    def rounddown(value: int, align: int) -> int:
        """Round down to alignment boundary"""
        if align == 0:
            return value
        return value - (value % align)

    @staticmethod
    def is_block_device(file_path: str) -> bool:
        """Handle block devices, automatically fetching their size"""
        if os.path.exists(file_path):
            stat_info = os.stat(file_path)
            return (stat_info.st_mode & stat.S_ISBLK(stat_info.st_mode))
        return False

    def parse_part_uuid(self, part: Partition) -> None:
        if self.table_type == TYPE_NONE:
            part.in_partition_table = False

        if part.partition_type_uuid and (not (self.table_type & TYPE_GPT)):
            raise ValueError("'partition-type-uuid' is only valid for gpt and hybrid partition-table-type")
        if part.partition_type and (not (self.table_type & TYPE_MBR)):
            raise ValueError("'partition-type' is only valid for mbr and hybrid partition-table-type")

        if (self.table_type & TYPE_GPT) and (part.in_partition_table):
            if not part.partition_type_uuid:
                part.partition_type_uuid = "L"
            if part.partition_type_uuid:
                uuid = get_gpt_partition_type(part.partition_type_uuid).bytes
                if not uuid:
                    raise ValueError(f"Invalid type shortcut: {part.partition_type_uuid}")
                part.partition_uuid = uuid

    def setup_uuid(self) -> None:
        """Setup disk UUID and signature"""
        config = self.config
        # Handle disk UUID
        if "disk-uuid" in config:
            try:
                uuid.UUID(config["disk-uuid"])
                self.disk_uuid = config["disk-uuid"]
            except ValueError:
                raise ImageError(f"Invalid disk UUID: {config['disk-uuid']}")

        # Handle disk signature
        disk_signature = config.get("disk-signature")
        if disk_signature == "random":
            self.disksig = uuid.getnode() & 0xFFFFFFFF  # Random 32-bit value
        elif disk_signature:
            if not (self.table_type & TYPE_MBR):
                raise ImageError("'disk-signature' is only valid for MBR and hybrid partition tables")
            try:
                self.disksig = int(disk_signature, 0)
            except ValueError:
                raise ImageError(f"Invalid disk signature: {disk_signature}")

    def get_child_image_size(self, image: Image, part: Partition) -> int:
        image_path = next((dep['image_path'] for dep in image.dependencies
            if dep.get('image') == part.image), None)
        if not image_path or not os.path.exists(image_path):
            raise ImageError(f"Subimage not found: {part.image}")

        return os.path.getsize(image_path)

    def get_child_image_path(self, image: Image, part: Partition) -> str:
        image_path = next((dep['image_path'] for dep in image.dependencies
            if dep.get('image') == part.image), None)
        if not image_path or not os.path.exists(image_path):
            raise ImageError(f"Subimage not found: {part.image}")

        return image_path

    def _lba_to_chs(self, lba: int, chs: List[int]) -> None:
        """Convert LBA to CHS address"""
        hpc = 255  # Heads per cylinder
        spt = 63   # Sectors per track
        s = lba % spt
        c = lba // spt
        h = c % hpc
        c = c // hpc

        chs[0] = h
        chs[1] = ((c & 0x300) >> 2) | (s + 1 if s != 0 else 0)
        chs[2] = c & 0xFF

    def _write_mbr_partition_entry(self, mbr_data: bytearray, offset: int, part: Partition) -> None:
        """Write MBR partition table entry"""
        entry = MbrPartitionEntry(
            boot=0x80 if part.bootable else 0x00,
            partition_type=parse_size(part.partition_type),
            relative_sectors=int(part.offset / 512),
            total_sectors=int(part.size / 512)
        )

        # Calculate CHS address
        self._lba_to_chs(entry.relative_sectors, entry.first_chs)
        self._lba_to_chs(entry.relative_sectors + entry.total_sectors - 1, entry.last_chs)

        # Write partition table entry
        struct.pack_into('<16s', mbr_data, offset, entry.to_bytes())

    def _write_hybrid_mbr_entry(self, mbr_data: bytearray, offset: int) -> None:
        """Write special entry for hybrid partition table"""
        entry = MbrPartitionEntry(
            partition_type=0xee,
            relative_sectors=1,
            total_sectors=(self.gpt_location // 512) + GPT_SECTORS - 2
        )
        self._lba_to_chs(entry.relative_sectors, entry.first_chs)
        self._lba_to_chs(entry.relative_sectors + entry.total_sectors - 1, entry.last_chs)

        struct.pack_into('<16s', mbr_data, offset, entry.to_bytes())

    def write_mbr(self, image: Image, write_path: str) -> None:
        """Write MBR partition table"""
        # Create MBR structure
        mbr_data = bytearray(72)

        # Write disk signature
        struct.pack_into('<I', mbr_data, 0, self.disksig)

        # Write partition table entries
        entry_offset = 6
        i = 0

        for part in image.partitions:
            if not part.in_partition_table or part.logical:
                continue

            if i >= 4:
                break
            self._write_mbr_partition_entry(mbr_data, entry_offset, part)
            entry_offset += 16
            i += 1
        # Handle hybrid partition table
        if self.table_type == TYPE_HYBRID and i < 4:
            self._write_hybrid_mbr_entry(mbr_data, entry_offset)

        # Write boot signature
        mbr_data[70] = 0x55
        mbr_data[71] = 0xAA

        # Write MBR to image
        logger.debug("write mbr")
        try:
            with open(write_path, 'r+b') as f:
                f.seek(440)
                f.write(mbr_data)
        except OSError as e:
            raise ImageError(f"Failed to write MBR: {e}")

    def write_protective_mbr(self, image: Image) -> None:
        """Write Protective MBR"""
        mbr_data = bytearray(72)

        # Write disk signature
        struct.pack_into('<I', mbr_data, 0 , self.disksig)

        # Protective partition table entry
        entry_offset = 6
        entry = MbrPartitionEntry(
            partition_type=0xee,
            relative_sectors=1,
            total_sectors=(image.size // 512) - 1
        )
        self._lba_to_chs(entry.relative_sectors, entry.first_chs)
        self._lba_to_chs(entry.relative_sectors + entry.total_sectors - 1, entry.last_chs)

        struct.pack_into('<16s', mbr_data, entry_offset, entry.to_bytes())

        # Boot signature
        mbr_data[70] = 0x55
        mbr_data[71] = 0xAA

        with open(image.outfile, 'r+b') as f:
            f.seek(440)
            f.write(mbr_data)

    def setup(self, image: Image, config: Dict[str, Any]) -> None:
        self.config = config

    def generate(self, image: Image) -> None:
        pass
