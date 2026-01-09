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
from .image_com import *

from .lib.toc import *
from .lib.gpt import *

class HdImageHandler(ComImageHandler):
    """Hard disk image handler, supports MBR, GPT and hybrid partition tables"""
    type = "hdimage"
    opts = [
        "align", "extended-partition", "fill",
    ]

    def __init__(self):
        super().__init__()
        self.extended_partition_index: int = 0
        self.extended_partition: Optional[Partition] = None
        self.align: int = 0
        self.fill: bool = False

    def setup(self, image: Image, config: Dict[str, Any]) -> None:
        super().setup(image, config)

        self._parse_config_parameters()

        # Handle block device
        self._handle_block_device(image)

        # Validate configuration parameters
        self.validate_config_parameters()

        # Set up logical partitions
        self._setup_logical_partitions(image)

        # Handle disk UUID and signature
        super().setup_uuid()

        # Hybrid partition table validation
        super().validate_hybrid_partition_table(image)

        # Calculate partition offsets and sizes
        self._calculate_partition_offsets(image)


    def _handle_block_device(self, image: Image) -> None:
        """Handle block device, automatically get its size"""
        if super().is_block_device(image.outfile):
            if image.size != 0:
                raise ImageError("Block device target does not allow specifying image size")

            try:
                with open(image.outfile, 'rb') as f:
                    f.seek(0, os.SEEK_END)
                    image.size = f.tell()
            except OSError as e:
                raise ImageError(f"Unable to get size of block device {image.outfile}: {str(e)}")

            if image.size <= 0:
                raise ImageError(f"Block device {image.outfile} size is invalid: {image.size}")

    def _parse_config_parameters(self) -> None:
        """Parse configuration parameters to private data structure"""
        super()._parse_config_parameters()
        config = self.config

        self.align = super()._parse_size(config.get("align", 0))
        self.extended_partition_index = int(config.get("extended-partition", 0))
        self.fill = config.get("fill", False)

        # Handle deprecated configuration
        self._handle_deprecated_config(config)

    def _handle_deprecated_config(self, config: Dict[str, Any]) -> None:
        """Handle deprecated configuration parameters"""
        if "partition-table" in config:
            self.table_type = TYPE_MBR if config["partition-table"] else TYPE_NONE
            logger.warning("'partition-table' is deprecated, please use 'partition-table-type'")
        if "gpt" in config:
            self.table_type = TYPE_GPT if config["gpt"] else TYPE_MBR
            logger.warning("'gpt' is deprecated, please use 'partition-table-type'")

    def validate_config_parameters(self) -> None:
        """Validate configuration parameters"""
        super().validate_config_parameters()
        # Validate alignment parameters
        if not self.align:
            self.align = 1 if self.table_type == TYPE_NONE else 512

        if (self.table_type != TYPE_NONE and
            (self.align % 512 != 0 or self.align == 0)):
            raise ImageError(f"Partition alignment ({self.align}) must be a multiple of 512 bytes")

        # Validate GPT location
        if self.gpt_location % 512 != 0:
            raise ImageError(f"GPT table location ({self.gpt_location}) must be a multiple of 512 bytes")

    def generate(self, image: Image) -> None:
        super().generate(image)

        # Prepare image file
        prepare_image(image)

        # Ensure extended partition index is set
        self._ensure_extended_partition_index(image)

        # Write partition data
        self._write_partition_data(image)

        # Write partition table
        self._write_partition_table(image)

        # Write TOC
        super().write_toc(image)


    def _write_partition_table(self, image: Image) -> None:
        """Write partition table"""
        if self.table_type & TYPE_GPT:
            self.write_gpt(image)
            if self.table_type == TYPE_HYBRID:
                super().write_mbr(image, image.outfile)
                self.write_ebrs(image)
            else:
                super().write_protective_mbr(image)

        elif self.table_type & TYPE_MBR:
            super().write_mbr(image, image.outfile)
            self.write_ebrs(image)

    def _ensure_extended_partition_index(self, image: Image) -> None:
        """Ensure extended partition index is set"""
        if self.extended_partition_index:
            return

        count = 0
        for part in image.partitions:
            if not part.in_partition_table:
                continue

            count += 1
            if count > 4:
                self.extended_partition_index = 4

    def _setup_logical_partitions(self, image: Image) -> None:
        """Setup logical partitions and extended partition"""
        if self.extended_partition_index > 4:
            raise ImageError(f"Invalid extended partition index ({self.extended_partition_index}), must be <= 4")

        if self.table_type != TYPE_MBR:
            return

        self._ensure_extended_partition_index(image)
        if not self.extended_partition_index:
            return

        count = 0
        mbr_entries = 0
        in_extended = False
        found_extended = False

        for part in image.partitions:
            if not part.in_partition_table:
                continue

            count += 1
            if self.extended_partition_index == count:
                # Create extended partition
                offset = part.offset - self.align if part.offset else 0
                extended_part = Partition(
                    name="[Extended]",
                    offset=offset,
                    parent_image=image.name,
                    size=0,
                    in_partition_table=True,
                    partition_type=PARTITION_TYPE_EXTENDED,
                    align=self.align
                )
                image.partitions.append(extended_part)
                self.extended_partition = extended_part
                in_extended = found_extended = True
                mbr_entries += 1

            logger.debug(f"forced_primary: {part.forced_primary}; in_extended: {in_extended}; ")

            if part.forced_primary:
                in_extended = False
            if in_extended and not part.forced_primary:
                part.logical = True
            else:
                mbr_entries += 1

            # Validate forced primary partition position
            if part.forced_primary:
                if not found_extended:
                    raise ImageError(f"Partition {part.name}: forced-primary can only be used for partitions after the extended partition")
            elif not in_extended and found_extended:
                raise ImageError(f"Cannot create a non-primary partition {part.name} after a forced primary partition")

        super()._validate_mbr_partition_count(image)

    def _creat_partition_table(self, image: Image) -> int:
        now = 512
        # MBR partition table
        super().add_partition_table(image,
            partition_name = "[MBR]",
            offset = 512 - 72,
            size = 72,
            in_partition_table = False
        )
        table_type = self.table_type
        # GPT partition table
        if table_type & TYPE_GPT:
            super().add_partition_table(image,
                partition_name = "[GPT header]",
                offset = 512,
                size = 512,
                in_partition_table = False
            )
            super().add_partition_table(image,
                partition_name = "[GPT array]",
                offset = self.gpt_location,
                size = (GPT_SECTORS - 1) * 512,
                in_partition_table = False
            )

            # GPT backup partition
            backup_size = GPT_SECTORS * 512
            backup_offset = image.size - backup_size if image.size else 0
            super().add_partition_table(image,
                partition_name = "[GPT backup]",
                offset = backup_offset,
                size = backup_size,
                in_partition_table = False
            )
            now = max(now, self.gpt_location +(GPT_SECTORS - 1) * 512)

        # Handle TOC partitions
        super().setup_toc(image, "[TOC]")

        return now

    def _calculate_partition_offsets(self, image: Image) -> None:
        """Calculate partition offsets and sizes"""
        now = 0
        self.file_size = 0

        # Reserve space for partition table
        if self.table_type != TYPE_NONE:
            now = self._creat_partition_table(image)

        # Handle autoresize partitions
        self._setup_autoresize_partitions(image)

        for part in image.partitions:
            # Set partition alignment
            if not part.align:
                part.align = self.align if (part.in_partition_table or
                                                  self.table_type == TYPE_NONE) else 1
            # Check alignment
            if part.in_partition_table and ((part.align % self.align) != 0):
                raise ImageError(f"Partition {part.name} alignment ({part.align}) must be a multiple of image alignment ({self.align})")

            super().parse_part_uuid(part)

            if not part.size:
                child_size = super().get_child_image_size(image, part)
                part.size = super().roundup(child_size, part.align) if part.in_partition_table else child_size

            # Reserve EBR space for logical partitions
            if part.logical:
                now += self.align
                now = super().roundup(now, part.align)

            if part.name == "[GPT backup]" and 0 == part.offset:
                now += part.size
                part.offset = super().roundup(now, 4096) - part.size

            # Set offset
            if not part.offset and (part.in_partition_table or self.table_type == TYPE_NONE):
                part.offset = super().roundup(now, part.align)

            # Check if offset meets alignment requirements
            if part.offset % part.align != 0:
                raise ImageError(f"Partition {part.name} offset ({part.offset}) must be a multiple of {part.align} bytes")

            # Ensure partition size is valid
            if not part.size and part != self.extended_partition:
                raise ImageError(f"Partition {part.name} size cannot be zero")

            # Check for partition overlap
            if not part.logical and super().check_overlap(image, part):
                raise ImageError(f"Partition {part.name} overlaps with a previous partition")

            # Check if partition size is a multiple of 512 bytes
            if part.in_partition_table and part.size % 512 != 0:
                raise ImageError(f"Partition {part.name} size ({part.size}) must be a multiple of 512 bytes")

            # Update current position
            if part.offset + part.size > now:
                now = part.offset + part.size

            # Update file size
            if part.image:
                child_size = super().get_child_image_size(image, part)
                if part.offset + child_size > self.file_size:
                    self.file_size = part.offset + child_size

            # Update extended partition size
            if part.logical :
                file_size = part.offset - self.align + 512
                if file_size > self.file_size:
                    self.file_size = file_size

                self.extended_partition.size = now - self.extended_partition.offset

        # Ensure image size is sufficient
        if not image.size:
            image.size = now

        logger.debug(f"image size: {image.size},now size: {now}")
        if now > image.size:
            raise ImageError("Partition size exceeds image size")

        # Final file size determination
        if self.fill or ((self.table_type & TYPE_GPT) and not self.gpt_no_backup):
            self.file_size = image.size
            logger.debug(f"update file size: {self.file_size}")


    def _setup_autoresize_partitions(self, image: Image) -> None:
        """Handle auto-resizing partitions"""
        resized = False
        for part in image.partitions:
            if not part.autoresize:
                continue

            if resized:
                raise ImageError("Only one auto-resizing partition is supported")
            if image.size == 0:
                raise ImageError("Image size must be specified when using auto-resizing partitions")

            # Calculate available space
            partsize = image.size - part.offset
            if self.table_type & TYPE_GPT:
                partsize -= GPT_SECTORS * 512  # Subtract GPT backup area

            # Alignment adjustment
            partsize = super().rounddown(partsize, part.align or self.align)

            if partsize <= 0:
                raise ImageError("Partition exceeds device size")
            if partsize < part.size:
                raise ImageError(f"Auto-resizing partition {part.name} size ({partsize}) is smaller than minimum size ({part.size})")

            part.size = partsize
            resized = True

    def _write_partition_data(self, image: Image) -> None:
        """Write partition data"""
        for part in image.partitions:
            if not part.image:
                # 允许的无镜像分区：
                #  - ota_meta：纯占位，由运行时 OTA/boot 写入
                #  - 内部伪分区：[MBR] / [GPT header] / [GPT array] / [GPT backup] / [TOC] / [Extended] 等
                if part.name == "ota_meta" or (part.name.startswith('[') and part.name.endswith(']')):
                    continue

                # 其他任意分区未指定 image，都视为配置错误，直接报错
                raise ImageError(
                    f"Partition {part.name} has no image file; only 'ota_meta' "
                    f"and internal metadata partitions like [MBR]/[TOC] may omit image"
                )

            child_size = 0
            image_path = ''

            # Find sub-image
            for dep in image.dependencies:
                if dep.get('image') == part.image:
                    image_path = dep.get('image_path')
                    logger.debug(f"dep: {dep.get('image')}, {dep.get('image_path')}")
                    break

            if os.path.exists(image_path):
                child_size = os.path.getsize(image_path)
            else:
                raise ImageError(f"Sub-image not found: {part.image}")

            # Check sub-image size
            if child_size > part.size:
                raise ImageError(f"Partition {part.name} size ({part.size}) is smaller than sub-image {part.image} size ({child_size})")

            insert_data(image, image_path, part.size , part.offset, bytes(0))

    def _write_ebr_current_entry(ebr_data: bytearray, part: Partition) -> None:
        """Write current partition entry in EBR"""
        align = self.align

        entry = MbrPartitionEntry(
            partition_type=parse_size(part.partition_type),
            relative_sectors=int(align / 512),
            total_sectors=int(part.size / 512)
        )

        super()._lba_to_chs(
            entry.relative_sectors + int((part.offset - align) / 512),
            entry.first_chs
        )
        super()._lba_to_chs(
            entry.relative_sectors + entry.total_sectors - 1 +
            int((part.offset - align) / 512),
            entry.last_chs
        )

        struct.pack_into('<16s', ebr_data, 0, entry.to_bytes())

    def _write_ebr_next_entry(ebr_data: bytearray, part: Partition) -> None:
        """Write next partition entry in EBR"""
        extended_part = self.extended_partition
        align = self.align

        next_ebr_rel_sectors = int(
            (part.offset - align - extended_part.offset) / 512
        )
        entry2 = MbrPartitionEntry(
            partition_type=PARTITION_TYPE_EXTENDED,
            relative_sectors=next_ebr_rel_sectors,
            total_sectors=int((part.size + align) / 512)
        )

        super()._lba_to_chs(extended_part.offset // 512, entry2.first_chs)
        super()._lba_to_chs(
            (extended_part.offset // 512) + entry2.total_sectors - 1,
            entry2.last_chs
        )

        struct.pack_into('<16s', ebr_data, 16, entry2.to_bytes())

    def _build_gpt_table(self, gpt_entries: List[GptPartitionEntry]) -> bytearray:
        """Build GPT partition table data"""
        table_data = bytearray(GPT_ENTRIES * 128)
        for entry in enumerate(gpt_entries[:GPT_ENTRIES]):
            table_data += entry.to_bytes()

        return table_data

    def _create_gpt_entry(self, part: Partition) -> GptPartitionEntry:
        """Create a single GPT partition table entry"""
        entry = GptPartitionEntry()

        # Set partition type UUID
        if part.partition_type_uuid:
            try:
                entry.type_uuid = uuid.UUID(part.partition_type_uuid).bytes
            except ValueError:
                # Try to find type alias
                type_uuid = get_gpt_partition_type(part.partition_type_uuid)
                if type_uuid:
                    entry.type_uuid = uuid.UUID(type_uuid).bytes
                else:
                    raise ImageError(f"Partition {part.name} has invalid type: {part.partition_type_uuid}")
        else:
            entry.type_uuid = get_gpt_partition_type('L').bytes

        # Set partition UUID
        if part.partition_uuid:
            try:
                entry.uuid = uuid.UUID(part.partition_uuid).bytes
            except ValueError:
                raise ImageError(f"Partition {part.name} has invalid UUID: {part.partition_uuid}")
        else:
            entry.uuid = uuid.uuid4().bytes

        # Set LBA range
        entry.first_lba = part.offset // 512
        entry.last_lba = (part.offset + part.size) // 512 - 1

        # Set flags
        flags = 0
        if part.bootable:
            flags |= GPT_PE_FLAG_BOOTABLE
        if getattr(part, 'read_only', False):
            flags |= GPT_PE_FLAG_READ_ONLY
        if getattr(part, 'hidden', False):
            flags |= GPT_PE_FLAG_HIDDEN
        if getattr(part, 'no_automount', False):
            flags |= GPT_PE_FLAG_NO_AUTO
        entry.flags = flags

        # Set name
        for i, c in enumerate(part.name[:36]):
            entry.name[i] = ord(c)

        return entry

    def _collect_gpt_entries(self, image: Image) -> Tuple[List[GptPartitionEntry], Optional[int]]:
        """Collect GPT partition table entry information"""
        gpt_entries = []
        smallest_offset = None

        for part in image.partitions:
            if not part.in_partition_table:
                continue

            entry = self._create_gpt_entry(part)
            gpt_entries.append(entry)

            # Track smallest offset
            if smallest_offset is None or part.offset < smallest_offset:
                smallest_offset = part.offset

        return gpt_entries, smallest_offset

    def _write_gpt_backup(self, image: Image, header: GptHeader, table_data: bytearray) -> None:
        """Write GPT backup partition table"""
        # Backup header
        backup_header = header.to_bytes()

        # Update LBA information in backup header
        backup_current_lba = header.backup_lba
        backup_backup_lba = 1
        struct.pack_into('<Q', backup_header, 24, backup_current_lba)
        struct.pack_into('<Q', backup_header, 32, backup_backup_lba)
        struct.pack_into('<Q', backup_header, 72, image.size//512 - GPT_SECTORS)

        # Recalculate backup header CRC
        struct.pack_into('<I', backup_header, 16, 0)  # Zero out old CRC
        backup_header_crc = zlib.crc32(backup_header) & 0xFFFFFFFF
        struct.pack_into('<I', backup_header, 16, backup_header_crc)

        # Write backup partition table and header
        with open(image.outfile, 'r+b') as f:
            f.seek(image.size - GPT_SECTORS * 512)
            f.write(table_data)
            f.seek(image.size - 512)
            f.write(backup_header)

    def write_gpt(self, image: Image) -> None:
        """Write GPT partition table"""
        # Create GPT header
        gpt_location = self.gpt_location
        header = GptHeader()
        header.disk_uuid = uuid.UUID(self.disk_uuid).bytes
        header.backup_lba = (image.size // 512) - 1 if not self.gpt_no_backup else 1
        header.last_usable_lba = (image.size // 512) - 1 - GPT_SECTORS
        header.starting_lba = gpt_location // 512

        # Collect partition information
        gpt_entries, smallest_offset = self._collect_gpt_entries(image)

        # Set first usable LBA
        if smallest_offset is None:
            smallest_offset = gpt_location + (GPT_SECTORS - 1) * 512
        header.first_usable_lba = smallest_offset // 512

        # Build partition table
        table_data = self._build_gpt_table(gpt_entries)

        # Calculate partition table CRC
        header.table_crc = zlib.crc32(table_data) & 0xFFFFFFFF

        # Calculate header CRC and write
        header_bytes = header.to_bytes()

        # Write primary GPT header and partition table
        logger.debug("write gpt")
        with open(image.outfile, 'r+b') as f:
            f.seek(512)
            f.write(header_bytes)
            f.seek(gpt_location)
            f.write(table_data)

        # Write backup GPT
        if not self.gpt_no_backup:
            self._write_gpt_backup(image, header, table_data)

    def write_ebrs(self, image: Image) -> None:
        """Write Extended Boot Records (EBR)"""
        if not self.extended_partition:
            return

        logical_parts = [p for p in image.partitions if p.logical]
        if not logical_parts:
            return

        prev_part = None
        for part in logical_parts:
            ebr_offset = part.offset - self.align + 446
            ebr_data = bytearray(512)

            # First entry: current logical partition
            self._write_ebr_current_entry(ebr_data, part)

            # Second entry: next EBR
            if prev_part is not None:
                self._write_ebr_next_entry(ebr_data, part)

            # Write boot signature
            ebr_data[510] = 0x55
            ebr_data[511] = 0xAA

            # Write EBR to image
            try:
                logger.debug(f"write ebr at 0x{ebr_offset:x}")
                with open(image.outfile, 'r+b') as f:
                    f.seek(ebr_offset)
                    f.write(ebr_data)
            except OSError as e:
                raise ImageError(f"Failed to write EBR: {e}")

            prev_part = part

    def run(self, image: Image, config: Dict[str, Any]) -> None:
        self.setup(image, config)
        self.generate(image)
