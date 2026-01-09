import logging
import zlib
import uuid
import os
import struct
import subprocess
import hashlib
import binascii
import stat
import tempfile
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Iterable
from .common import ImageHandler, Image, Partition, ImageError, run_command, prepare_image, parse_size, insert_data, safe_to_int, format_size

# Configure logger
logger = logging.getLogger(__name__)
from .image_com import *

from .lib.toc import *
from .lib.gpt import *

# Constant definitions
KD_IMG_HDR_MAGIC = 0x27CB8F93  # "KDIM"
KD_PART_MAGIC = 0x91DF6DA4     # "PART"

KBURN_FLAG_SPI_NAND_WRITE_WITH_OOB = 1024

MEDIUM_TYPE_MMC = 0
MEDIUM_TYPE_SPI_NAND = 1
MEDIUM_TYPE_SPI_NOR = 2

KDIMG_CONTENT_START_OFFSET = 64 * 1024  # Image content start offset (64KB)

KD_ALIGNMENT = 4096
KD_PART_ENTRY_ALIGN = 256      # Partition entry alignment size in bytes
KD_HEADER_ALIGN = 512          # Header alignment size in bytes

@dataclass
class KdImgPart:
    """kd_img_part_t structure mapping"""
    part_magic: int = KD_PART_MAGIC
    part_offset: int = 0  # Aligned to 4096
    part_size: int = 0    # Aligned to 4096
    part_erase_size: int = 0
    part_max_size: int = 0
    part_flag: int = 0

    part_content_offset: int = 0
    part_content_size: int = 0
    part_content_sha256: bytes = field(default_factory=lambda: b'\x00' * 32)
    part_name: str = ''

    def to_bytes(self) -> bytes:
        fmt = '<IIIIIIQII32s32s'
        name_bytes = self.part_name.encode('utf-8')[:31].ljust(32, b'\x00')
        data = struct.pack(
            fmt,
            self.part_magic,
            self.part_offset,
            self.part_size,
            self.part_erase_size,
            self.part_max_size,
            0,  # Reserved
            self.part_flag,
            self.part_content_offset,
            self.part_content_size,
            self.part_content_sha256,
            name_bytes
        )

        return data.ljust(KD_PART_ENTRY_ALIGN, b'\x00')


@dataclass
class KdImgHdr:
    """kd_img_hdr_t structure mapping"""
    img_hdr_magic: int = KD_IMG_HDR_MAGIC
    img_hdr_crc32: int = 0
    img_hdr_flag: int = 0
    img_hdr_version: int = 2

    part_tbl_num: int = 0
    part_tbl_crc32: int = 0
    image_info: str = ''
    chip_info: str = ''
    board_info: str = ''

    def to_bytes(self) -> bytes:
        """Convert to byte stream"""
        fmt = '<IIIIII32s32s64s'
        img_info_bytes = self.image_info.encode('utf-8')[:31].ljust(32, b'\x00')
        chip_info_bytes = self.chip_info.encode('utf-8')[:31].ljust(32, b'\x00')
        board_info_bytes = self.board_info.encode('utf-8')[:63].ljust(64, b'\x00')

        data = struct.pack(
            fmt,
            self.img_hdr_magic,
            self.img_hdr_crc32,
            self.img_hdr_flag,
            self.img_hdr_version,
            self.part_tbl_num,
            self.part_tbl_crc32,
            img_info_bytes,
            chip_info_bytes,
            board_info_bytes
        )

        # Ensure alignment to 512 bytes
        return data.ljust(KD_HEADER_ALIGN, b'\x00')

@dataclass
class KdImgPartRecord:
    image_file: str
    part: KdImgPart

class KdImageHandler(ComImageHandler):
    """KD Image Handler"""
    type = "kdimage"
    opts = [
        "image-info", "chip-info", "board-info",
        "part-flag", "medium-type"
    ]

    def __init__(self):
        super().__init__()
        self.temp = str(tempfile.gettempdir())

        self.file_size: int = KDIMG_CONTENT_START_OFFSET

        self.header: KdImgHdr = KdImgHdr()
        self.medium_type: str = "mmc"

        self.part_records: List[KdImgPartRecord] = []

    def _kburn_flag_flag(self, flag: int) -> int:
        return (flag >> 48) & 0xffff

    def _kburn_flag_val1(self, flag: int) -> int:
        return (flag >> 16) & 0xffffffff

    def _kburn_flag_val2(self, flag: int) -> int:
        return flag & 0xffff

    def setup(self, image: Image, config: Dict[str, Any]) -> None:
        """Initialize configuration and set up partition information"""
        super().setup(image, config)

        if super().is_block_device(image.outfile):
            raise ImageError("Writing to block device is not supported\n")

        self._parse_config_parameters()
        self._validate_config()
        super().validate_config_parameters()

        if self.table_type & TYPE_GPT:
            super().setup_uuid()

        self._add_virtual_partitions(image)

        for part in image.partitions:
            super().parse_part_uuid(part)
            self._setup_part_image(image, part)
            self._setup_file_size(image, part)
            # Check overlap
            super().check_overlap(image, part)

        super()._validate_mbr_partition_count(image)

    def _parse_config_parameters(self) -> None:
        """Parse configuration parameters to private data structure"""
        super()._parse_config_parameters()

        self.header.image_info = self.config.get("image_info", "")
        if '' == self.header.image_info:
            raise ValueError("Can not get 'image_info'")

        self.header.chip_info = self.config.get("chip_info", "")
        if '' == self.header.chip_info:
            raise ValueError("Can not get 'chip_info'")

        self.header.board_info = self.config.get("board_info", "")
        if '' == self.header.board_info:
            raise ValueError("Can not get 'board_info'")

    def _validate_config(self) -> None:
        """Validate configuration parameter effectiveness"""
        # Parse partition table type
        table_type = self.table_type
        if table_type == "hybrid":
            raise ImageError(f"Partition table type '{table_type}' is not supported")

        table_type = self.medium_type
        if table_type == "mmc":
            self.medium_type = MEDIUM_TYPE_MMC
        elif table_type == "spi_nand":
            self.medium_type = MEDIUM_TYPE_SPI_NAND
        elif table_type == "spi_nor":
            self.medium_type = MEDIUM_TYPE_SPI_NOR
        else:
            raise ValueError(f"'{table_type}' is not a valid medium-type")

    def _add_virtual_partitions(self, image: Image) -> None:
        """Add virtual partitions related to the partition table"""
        table_type = self.table_type

        if table_type & TYPE_MBR:
            # Add MBR partition table virtual partition (offset 0, size 512 bytes)
            super().add_partition_table(image,
                partition_name = "[MBR]",
                offset = 0,
                size = 512,
                in_partition_table = False
            )

        elif table_type & TYPE_GPT:
            # GPT Header (LBA1, 512 bytes)
            super().add_partition_table(image,
                partition_name = "[GPT header]",
                offset = 512,
                size = 512,
                in_partition_table = False
            )
            # GPT Partition Entry Array (default 128 entries, 128 bytes each)
            gpt_array_size = (GPT_SECTORS - 1) * 512
            gpt_location = self.gpt_location if self.gpt_location else 2 * 512
            super().add_partition_table(image,
                partition_name = "[GPT array]",
                offset = gpt_location,
                size = gpt_array_size,
                in_partition_table = False
            )
            # Add GPT backup partition (if needed)
            if not self.gpt_no_backup:
                super().add_partition_table(image,
                    partition_name = "[GPT backup]",
                    offset = 64 * 1024,
                    size = GPT_SECTORS * 512,
                    in_partition_table = False
                )
        # Handle TOC
        super().setup_toc(image, "[TOC]")

    def _setup_part_image(self, image: Image, part: Partition) -> None:
        """Setup partition image"""
        if not part.image:
            return

        child_size = super().get_child_image_size(image, part)

        if not part.size:
            part.size = super().roundup(child_size, 4096)

        if not part.size or child_size > part.size:
            if 0 == self._kburn_flag_flag(part.flag):
                raise ImageError("Setup failed, partition size too small")

    def _setup_file_size(self, image: Image, part: Partition) -> None:
        """setup file size"""
        self.file_size += super().roundup(part.size, 4096)

    def generate(self, image: Image) -> None:
        """Generate KD image file"""
        super().generate(image)
        prepare_image(image, self.file_size)
        self._write_partition_data(image)

    def _calculate_sha256(self, filename: str, offset: int, size: int) -> bytes:
        """Calculate the SHA256 of the specified region of the file"""
        hasher = hashlib.sha256()
        with open(filename, 'rb') as f:
            f.seek(offset)
            hasher.update(f.read(size))
        return hasher.digest()

    def _check_part_alignment(self, child_size: int, part: Partition) -> None:
        if child_size > part.size:
            flag_flag = self._kburn_flag_flag(part.flag)
            flag_val1, flag_val2 = self._kburn_flag_val1(part.flag), self._kburn_flag_val2(part.flag)

            if flag_flag == KBURN_FLAG_SPI_NAND_WRITE_WITH_OOB:
                page_oob_size = flag_val1 + flag_val2
                if child_size % page_oob_size != 0:
                    raise ImageError(f"Image size {child_size} not aligned to page({flag_val1})+OOB({flag_val2})")

                child_size_only_page = (child_size // page_oob_size) * flag_val1
                if child_size_only_page > part.size:
                    raise ImageError(f"Part {part.name} too small for {child_size_only_page}")
            else:
                raise ImageError(f"Partition {part.name} size overflow")

    def _write_partition_data(self, image: Image) -> None:
        """Write all partition data and maintain partition records"""
        padding_byte = b'\x00'
        if self.medium_type in (MEDIUM_TYPE_SPI_NAND, MEDIUM_TYPE_SPI_NOR):
            padding_byte = b'\xff'

        # Initialize write offset
        image_write_offset = KDIMG_CONTENT_START_OFFSET

        for part_idx, part in enumerate(image.partitions):
            # --- Handle virtual partitions (MBR and TOC) ---
            child_image = None
            if not part.image:
                if part.name == "[MBR]":
                    child_image = self._generate_mbr(image)  # Use MBR generation method without TOC
                    image_path = child_image.outfile
                    child_size = child_image.size
                elif part.name == "[TOC]":
                    if self.toc_enable:
                        child_image = self._generate_toc_partition(image) # Generate a separate TOC partition
                        image_path = child_image.outfile
                        child_size = child_image.size
                    else:
                        continue # Skip if TOC is not enabled
                else:
                    # For other virtual partitions without associated files, skip (e.g., GPT backup partition, if the logic is not here)
                    continue
            else:
                # --- Handle normal partitions ---
                image_path = super().get_child_image_path(image, part)
                child_size = super().get_child_image_size(image, part)

            self._check_part_alignment(child_size, part)

            # Alignment handling
            aligned_child_size = child_size
            if 4096 < child_size:
                aligned_child_size = super().roundup(child_size, 4096)

            # Deduplication logic for records
            skip_insert = False
            for record in self.part_records:
                if record.image_file == image_path:
                    logger.debug(f"Skipping duplicate part: {part.name} image: {image_path}")
                    part_record = KdImgPartRecord(
                        image_file=image_path,
                        part=KdImgPart(
                            part_magic=KD_PART_MAGIC,
                            part_offset=part.offset,
                            part_size=aligned_child_size,
                            part_erase_size=part.erase_size,
                            part_max_size=part.size,
                            part_flag=part.flag,
                            part_name=part.name,
                            part_content_offset=record.part.part_content_offset,
                            part_content_size=record.part.part_content_size,
                            part_content_sha256=record.part.part_content_sha256
                        )
                    )
                    self.part_records.append(part_record)

                    skip_insert = True
                    break

            if skip_insert:
                continue
            # Write data

            logger.debug(f"write name: {part.name} offset: {part.offset} part_size: {part.size},write_offset: {image_write_offset}, child_size: {child_size}, aligned_child_size: {aligned_child_size}")
            insert_data(image, image_path, aligned_child_size, image_write_offset, padding_byte)

            # Generate partition record
            part_record = KdImgPartRecord(
                image_file=image_path,
                part=KdImgPart(
                    part_magic=KD_PART_MAGIC,
                    part_offset=part.offset if part.offset else 0,
                    part_size=aligned_child_size,
                    part_erase_size=part.erase_size if part.erase_size else 0,
                    part_max_size=part.size,
                    part_flag=part.flag if part.flag else 0,
                    part_name=part.name,
                    part_content_offset=image_write_offset,
                    part_content_size=aligned_child_size,
                    part_content_sha256=self._calculate_sha256(image.outfile,
                                                            image_write_offset,
                                                            aligned_child_size)
                )
            )
            self.part_records.append(part_record)

            # Offset alignment
            image_write_offset += super().roundup(aligned_child_size, 4096)

            self.header.part_tbl_num = len([p for p in image.partitions])
            # print(f"tbl_num: {self.header.part_tbl_num} idx: {part_idx}")
            if part_idx > self.header.part_tbl_num:
                raise ValueError("Image partition count does not match")

        self._generate_final_stage(image, image_write_offset)

    def _generate_final_stage(self, image, image_write_offset):
        # Final stage of image generation
        part_table_data = b''
        for part in self.part_records:
            # print(f"kdimgpart: {part}")
            part_table_data += part.part.to_bytes()
            # print(f"test: {part.part.to_bytes()[0:100].hex()}")

        part_table_crc = self._calculate_crc32(part_table_data)

        # for part in self.part_records:
        #     name_bytes = part.part.part_name.encode('utf-8')[:31].ljust(32, b'\x00')
        #     print(f"magic: 0x{part.part.part_magic:0x}")
        #     print(f"offset: 0x{part.part.part_offset:0x}")
        #     print(f"size: 0x{part.part.part_size:0x}")
        #     print(f"erase_size: 0x{part.part.part_erase_size:0x}")
        #     print(f"max_size: 0x{part.part.part_max_size:0x}")
        #     print(f"flag: 0x{part.part.part_flag:0x}")
        #     print(f"name: {part.part.part_name}")
        #     print(f"content_offset: 0x{part.part.part_content_offset:0x}")
        #     print(f"content_size: 0x{part.part.part_content_size:0x}")
        #     print(f"name: {name_bytes.hex()}")
        #     print(f"content_sha256: {part.part.part_content_sha256.hex()}")

        # print(f"part table crc32: 0x{part_table_crc:0x}")

        # Build image header
        header = self.header
        header.img_hdr_magic = KD_IMG_HDR_MAGIC
        header.img_hdr_flag = 0x00
        header.img_hdr_version = 0x02
        header.part_tbl_crc32 = part_table_crc
        header.img_hdr_crc32 = 0x00  # Temporarily set to zero

        final_header_crc = self._calculate_crc32(header.to_bytes())

        header.img_hdr_crc32 = final_header_crc
        final_header_bytes = header.to_bytes()

        # print(f"header:{final_header_bytes[0:130].hex()}")
        # print(f"header: img_hdr_magic: 0x{header.img_hdr_magic:0x}")
        # print(f"header: img_hdr_crc32: 0x{header.img_hdr_crc32:0x}")
        # print(f"header: img_hdr_flag: 0x{header.img_hdr_flag:0x}")
        # print(f"header: img_hdr_version: 0x{header.img_hdr_version:0x}")
        # print(f"header: part_tbl_crc32: 0x{header.part_tbl_crc32:0x}")
        # print(f"header: part_tbl_num: {header.part_tbl_num}")
        # print(f"header: image_info: {header.image_info}")
        # print(f"header: chip_info: {header.chip_info}")
        # print(f"header: board_info: {header.board_info}")

        logger.debug(f"final header size: {len(final_header_bytes)}; part table size: {len(part_table_data)}")
        logger.debug(f"final header crc32: 0x{final_header_crc:08x}")

        try:
            with open(image.outfile, 'r+b') as f:
                # Write final header (start of file)
                f.seek(0)
                f.write(final_header_bytes)
                # Write partition table data (512 bytes offset)
                f.seek(512)
                f.write(part_table_data)  # Reuse the calculated partition table data
                # Truncate file
                f.truncate(image_write_offset)

        except IOError as e:
            raise ImageError(f"File write failed: {str(e)}")

        if not super().is_block_device(image.outfile):
            self._validate_file_size(image.outfile, image_write_offset)

        image_info = (f"Successfully generated image {image.outfile}, "
                    f"size {format_size(image_write_offset)}")
        logger.info(image_info)

    def _generate_toc_partition(self, image: Image) -> Image:
        """Generate TOC partition"""
        # Even if there are no entries, generate a minimal TOC partition
        toc_size = max(64, self.toc_num * 64)

        if not self.toc_num:
            # Create empty TOC partition (unchanged)
            child_image = Image(
                size = toc_size,
                outfile = os.path.join(self.temp, "partition_toc")
            )
            prepare_image(child_image, size=toc_size)
            logger.debug(f"write empty toc partition: {child_image.outfile} size {toc_size}")
            return child_image

        # Create TOC partition
        child_image = Image(
            size = toc_size,
            outfile = os.path.join(self.temp, "partition_toc")
        )
        prepare_image(child_image, size=toc_size)

        # Write TOC data
        super().write_toc(child_image, 0)

        return child_image

    def _generate_mbr(self, image: Image) -> Image:
        """Write MBR partition table (excluding TOC data)"""
        # Temporary working file
        child_image = Image(
            size = 512,
            outfile = os.path.join(self.temp, "partition_table_mbr")
        )
        prepare_image(child_image)

        # Write MBR to image
        super().write_mbr(image, child_image.outfile)

        return child_image

    def _calculate_crc32(self, data: bytes) -> int:
        return zlib.crc32(data) & 0xFFFFFFFF

    def _validate_file_size(self, path: str, expected: int) -> None:
        actual = os.path.getsize(path)
        if actual != expected:
            raise ImageError(f"File size anomaly: Expected={expected}(0x{expected:x}), Actual={actual}(0x{actual:x})")

    def run(self, image: Image, config: Dict[str, Any]) -> None:
        """Execute the image generation process"""
        self.setup(image, config)
        self.generate(image)
