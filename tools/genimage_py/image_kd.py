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
from .common import ImageHandler, Image, Partition, ImageError, run_command, prepare_image, parse_size, insert_data, TocInsertData

# Constant definitions
KD_IMG_HDR_MAGIC = 0x27CB8F93  # "KDIM"
KD_PART_MAGIC = 0x91DF6DA4     # "PART"

KBURN_FLAG_SPI_NAND_WRITE_WITH_OOB = 1024

MEDIUM_TYPE_MMC = 0
MEDIUM_TYPE_SPI_NAND = 1
MEDIUM_TYPE_SPI_NOR = 2

KDIMG_CONTENT_START_OFFSET = 64 * 1024  # Image content start offset (64KB)

# Constant definitions
GPT_REVISION_1_0 = 0x00010000
GPT_SECTORS = 33
GPT_ENTRIES = 128
GPT_PE_FLAG_BOOTABLE = 1 << 2
GPT_PE_FLAG_READ_ONLY = 1 << 60
GPT_PE_FLAG_HIDDEN = 1 << 62
GPT_PE_FLAG_NO_AUTO = 1 << 63

TYPE_NONE = 0
TYPE_MBR = 1 << 0
TYPE_GPT = 1 << 1
TYPE_HYBRID = TYPE_MBR | TYPE_GPT

PARTITION_TYPE_EXTENDED = 0x0f

KD_ALIGNMENT = 4096
KD_PART_ENTRY_ALIGN = 256      # Partition entry alignment size in bytes
KD_HEADER_ALIGN = 512          # Header alignment size in bytes

GPT_PARTITION_TYPES = {
    # Basic types
    "L": "0fc63daf-8483-4772-8e79-3d69d8477de4",
    "linux": "0fc63daf-8483-4772-8e79-3d69d8477de4",
    "S": "0657fd6d-a4ab-43c4-84e5-0933c84b4f4f",
    "swap": "0657fd6d-a4ab-43c4-84e5-0933c84b4f4f",
    "H": "933ac7e1-2eb4-4f13-b844-0e14e2aef915",
    "home": "933ac7e1-2eb4-4f13-b844-0e14e2aef915",
    "U": "c12a7328-f81f-11d2-ba4b-00a0c93ec93b",
    "uefi": "c12a7328-f81f-11d2-ba4b-00a0c93ec93b",
    "R": "a19d880f-05fc-4d3b-a006-743f0f84911e",
    "raid": "a19d880f-05fc-4d3b-a006-743f0f84911e",
    "V": "e6d6d379-f507-44c2-a23c-238f2a3df928",
    "lvm": "e6d6d379-f507-44c2-a23c-238f2a3df928",
    "F": "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7",
    "fat32": "ebd0a0a2-b9e5-4433-87c0-68b6b72699c7",

    # Special partitions
    "barebox-state": "4778ed65-bf42-45fa-9c5b-287a1dc4aab1",
    "barebox-env": "6c3737f2-07f8-45d1-ad45-15d260aab24d",
    "esp": "c12a7328-f81f-11d2-ba4b-00a0c93ec93b",
    "xbootldr": "bc13c2ff-59e6-4262-a352-b275fd6f7172",
    "srv": "3b8f8425-20e0-4f3b-907f-1a25a76f98e8",
    "var": "4d21b016-b534-45c2-a9fb-5c16e091fd2d",
    "tmp": "7ec6f557-3bc5-4aca-b293-16ef5df639d1",
    "user-home": "773f91ef-66d4-49b5-bd83-d683bf40ad16",
    "linux-generic": "0fc63daf-8483-4772-8e79-3d69d8477de4",

    # Root partitions (Discoverable Partitions Specification)
    "root-alpha": "6523f8ae-3eb1-4e2a-a05a-18b695ae656f",
    "root-arc": "d27f46ed-2919-4cb8-bd25-9531f3c16534",
    "root-arm": "69dad710-2ce4-4e3c-b16c-21a1d49abed3",
    "root-arm64": "b921b045-1df0-41c3-af44-4c6f280d3fae",
    "root-ia64": "993d8d3d-f80e-4225-855a-9daf8ed7ea97",
    "root-loongarch64": "77055800-792c-4f94-b39a-98c91b762bb6",
    "root-mips": "e9434544-6e2c-47cc-bae2-12d6deafb44c",
    "root-mips64": "d113af76-80ef-41b4-bdb6-0cff4d3d4a25",
    "root-mips-le": "37c58c8a-d913-4156-a25f-48b1b64e07f0",
    "root-mips64-le": "700bda43-7a34-4507-b179-eeb93d7a7ca3",
    "root-parisc": "1aacdb3b-5444-4138-bd9e-e5c2239b2346",
    "root-ppc": "1de3f1ef-fa98-47b5-8dcd-4a860a654d78",
    "root-ppc64": "912ade1d-a839-4913-8964-a10eee08fbd2",
    "root-ppc64-le": "c31c45e6-3f39-412e-80fb-4809c4980599",
    "root-riscv32": "60d5a7fe-8e7d-435c-b714-3dd8162144e1",
    "root-riscv64": "72ec70a6-cf74-40e6-bd49-4bda08e8f224",
    "root-s390": "08a7acea-624c-4a20-91e8-6e0fa67d23f9",
    "root-s390x": "5eead9a9-fe09-4a1e-a1d7-520d00531306",
    "root-tilegx": "c50cdd70-3862-4cc3-90e1-809a8c93ee2c",
    "root-x86": "44479540-f297-41b2-9af7-d131d5f0458a",
    "root-x86-64": "4f68bce3-e8cd-4db1-96e7-fbcaf984b709",

    # User partitions
    "usr-alpha": "e18cf08c-33ec-4c0d-8246-c6c6fb3da024",
    "usr-arc": "7978a683-6316-4922-bbee-38bff5a2fecc",
    "usr-arm": "7d0359a3-02b3-4f0a-865c-654403e70625",
    "usr-arm64": "b0e01050-ee5f-4390-949a-9101b17104e9",
    "usr-ia64": "4301d2a6-4e3b-4b2a-bb94-9e0b2c4225ea",
    "usr-loongarch64": "e611c702-575c-4cbe-9a46-434fa0bf7e3f",
    "usr-mips": "773b2abc-2a99-4398-8bf5-03baac40d02b",
    "usr-mips64": "57e13958-7331-4365-8e6e-35eeee17c61b",
    "usr-mips-le": "0f4868e9-9952-4706-979f-3ed3a473e947",
    "usr-mips64-le": "c97c1f32-ba06-40b4-9f22-236061b08aa8",
    "usr-parisc": "dc4a4480-6917-4262-a4ec-db9384949f25",
    "usr-ppc": "7d14fec5-cc71-415d-9d6c-06bf0b3c3eaf",
    "usr-ppc64": "2c9739e2-f068-46b3-9fd0-01c5a9afbcca",
    "usr-ppc64-le": "15bb03af-77e7-4d4a-b12b-c0d084f7491c",
    "usr-riscv32": "b933fb22-5c3f-4f91-af90-e2bb0fa50702",
    "usr-riscv64": "beaec34b-8442-439b-a40b-984381ed097d",
    "usr-s390": "cd0f869b-d0fb-4ca0-b141-9ea87cc78d66",
    "usr-s390x": "8a4f5770-50aa-4ed3-874a-99b710db6fea",
    "usr-tilegx": "55497029-c7c1-44cc-aa39-815ed1558630",
    "usr-x86": "75250d76-8cc6-458e-bd66-bd47cc81a812",
    "usr-x86-64": "8484680c-9521-48c6-9c11-b0720656f69e",

    # Verity verified partitions
    "root-alpha-verity": "fc56d9e9-e6e5-4c06-be32-e74407ce09a5",
    "root-arc-verity": "24b2d975-0f97-4521-afa1-cd531e421b8d",
    "root-arm-verity": "7386cdf2-203c-47a9-a498-f2ecce45a2d6",
    "root-arm64-verity": "df3300ce-d69f-4c92-978c-9bfb0f38d820",
    "root-ia64-verity": "86ed10d5-b607-45bb-8957-d350f23d0571",
    "root-loongarch64-verity": "f3393b22-e9af-4613-a948-9d3bfbd0c535",
    "root-mips-verity": "7a430799-f711-4c7e-8e5b-1d685bd48607",
    "root-mips64-verity": "579536f8-6a33-4055-a95a-df2d5e2c42a8",
    "root-mips-le-verity": "d7d150d2-2a04-4a33-8f12-16651205ff7b",
    "root-mips64-le-verity": "16b417f8-3e06-4f57-8dd2-9b5232f41aa6",
    "root-parisc-verity": "d212a430-fbc5-49f9-a983-a7feef2b8d0e",
    "root-ppc64-le-verity": "906bd944-4589-4aae-a4e4-dd983917446a",
    "root-ppc64-verity": "9225a9a3-3c19-4d89-b4f6-eeff88f17631",
    "root-ppc-verity": "98cfe649-1588-46dc-b2f0-add147424925",
    "root-riscv32-verity": "ae0253be-1167-4007-ac68-43926c14c5de",
    "root-riscv64-verity": "b6ed5582-440b-4209-b8da-5ff7c419ea3d",
    "root-s390-verity": "7ac63b47-b25c-463b-8df8-b4a94e6c90e1",
    "root-s390x-verity": "b325bfbe-c7be-4ab8-8357-139e652d2f6b",
    "root-tilegx-verity": "966061ec-28e4-4b2e-b4a5-1f0a825a1d84",
    "root-x86-64-verity": "2c7357ed-ebd2-46d9-aec1-23d437ec2bf5",
    "root-x86-verity": "d13c5d3b-b5d1-422a-b29f-9454fdc89d76",

    # User space Verity verification
    "usr-alpha-verity": "8cce0d25-c0d0-4a44-bd87-46331bf1df67",
    "usr-arc-verity": "fca0598c-d880-4591-8c16-4eda05c7347c",
    "usr-arm-verity": "c215d751-7bcd-4649-be90-6627490a4c05",
    "usr-arm64-verity": "6e11a4e7-fbca-4ded-b9e9-e1a512bb664e",
    "usr-ia64-verity": "6a491e03-3be7-4545-8e38-83320e0ea880",
    "usr-loongarch64-verity": "f46b2c26-59ae-48f0-9106-c50ed47f673d",
    "usr-mips-verity": "6e5a1bc8-d223-49b7-bca8-37a5fcceb996",
    "usr-mips64-verity": "81cf9d90-7458-4df4-8dcf-c8a3a404f09b",
    "usr-mips-le-verity": "46b98d8d-b55c-4e8f-aab3-37fca7f80752",
    "usr-mips64-le-verity": "3c3d61fe-b5f3-414d-bb71-8739a694a4ef",
    "usr-parisc-verity": "5843d618-ec37-48d7-9f12-cea8e08768b2",
    "usr-ppc64-le-verity": "ee2b9983-21e8-4153-86d9-b6901a54d1ce",
    "usr-ppc64-verity": "bdb528a5-a259-475f-a87d-da53fa736a07",
    "usr-ppc-verity": "df765d00-270e-49e5-bc75-f47bb2118b09",
    "usr-riscv32-verity": "cb1ee4e3-8cd0-4136-a0a4-aa61a32e8730",
    "usr-riscv64-verity": "8f1056be-9b05-47c4-81d6-be53128e5b54",
    "usr-s390-verity": "b663c618-e7bc-4d6d-90aa-11b756bb1797",
    "usr-s390x-verity": "31741cc4-1a2a-4111-a581-e00b447d2d06",
    "usr-tilegx-verity": "2fb4bf56-07fa-42da-8132-6b139f2026ae",
    "usr-x86-64-verity": "77ff5f63-e7b6-4633-acf4-1565b864c0e6",
    "usr-x86-verity": "8f461b0d-14ee-4e81-9aa9-049b6fb97abd",

    # Signature verified partitions
    "root-alpha-verity-sig": "d46495b7-a053-414f-80f7-700c99921ef8",
    "root-arc-verity-sig": "143a70ba-cbd3-4f06-919f-6c05683a78bc",
    "root-arm-verity-sig": "42b0455f-eb11-491d-98d3-56145ba9d037",
    "root-arm64-verity-sig": "6db69de6-29f4-4758-a7a5-962190f00ce3",
    "root-ia64-verity-sig": "e98b36ee-32ba-4882-9b12-0ce14655f46a",
    "root-loongarch64-verity-sig": "5afb67eb-ecc8-4f85-ae8e-ac1e7c50e7d0",
    "root-mips-verity-sig": "bba210a2-9c5d-45ee-9e87-ff2ccbd002d0",
    "root-mips64-verity-sig": "43ce94d4-0f3d-4999-8250-b9deafd98e6e",
    "root-mips-le-verity-sig": "c919cc1f-4456-4eff-918c-f75e94525ca5",
    "root-mips64-le-verity-sig": "904e58ef-5c65-4a31-9c57-6af5fc7c5de7",
    "root-parisc-verity-sig": "15de6170-65d3-431c-916e-b0dcd8393f25",
    "root-ppc64-le-verity-sig": "d4a236e7-e873-4c07-bf1d-bf6cf7f1c3c6",
    "root-ppc64-verity-sig": "f5e2c20c-45b2-4ffa-bce9-2a60737e1aaf",
    "root-ppc-verity-sig": "1b31b5aa-add9-463a-b2ed-bd467fc857e7",
    "root-riscv32-verity-sig": "3a112a75-8729-4380-b4cf-764d79934448",
    "root-riscv64-verity-sig": "efe0f087-ea8d-4469-821a-4c2a96a8386a",
    "root-s390-verity-sig": "3482388e-4254-435a-a241-766a065f9960",
    "root-s390x-verity-sig": "c80187a5-73a3-491a-901a-017c3fa953e9",
    "root-tilegx-verity-sig": "b3671439-97b0-4a53-90f7-2d5a8f3ad47b",
    "root-x86-64-verity-sig": "41092b05-9fc8-4523-994f-2def0408b176",
    "root-x86-verity-sig": "5996fc05-109c-48de-808b-23fa0830b676",

    # User space signature verification
    "usr-alpha-verity-sig": "5c6e1c76-076a-457a-a0fe-f3b4cd21ce6e",
    "usr-arc-verity-sig": "94f9a9a1-9971-427a-a400-50cb297f0f35",
    "usr-arm-verity-sig": "d7ff812f-37d1-4902-a810-d76ba57b975a",
    "usr-arm64-verity-sig": "c23ce4ff-44bd-4b00-b2d4-b41b3419e02a",
    "usr-ia64-verity-sig": "8de58bc2-2a43-460d-b14e-a76e4a17b47f",
    "usr-loongarch64-verity-sig": "b024f315-d330-444c-8461-44bbde524e99",
    "usr-mips-verity-sig": "97ae158d-f216-497b-8057-f7f905770f54",
    "usr-mips64-verity-sig": "05816ce2-dd40-4ac6-a61d-37d32dc1ba7d",
    "usr-mips-le-verity-sig": "3e23ca0b-a4bc-4b4e-8087-5ab6a26aa8a9",
    "usr-mips64-le-verity-sig": "f2c2c7ee-adcc-4351-b5c6-ee9816b66e16",
    "usr-parisc-verity-sig": "450dd7d1-3224-45ec-9cf2-a43a346d71ee",
    "usr-ppc64-le-verity-sig": "c8bfbd1e-268e-4521-8bba-bf314c399557",
    "usr-ppc64-verity-sig": "0b888863-d7f8-4d9e-9766-239fce4d58af",
    "usr-ppc-verity-sig": "7007891d-d371-4a80-86a4-5cb875b9302e",
    "usr-riscv32-verity-sig": "c3836a13-3137-45ba-b583-b16c50fe5eb4",
    "usr-riscv64-verity-sig": "d2f9000a-7a18-453f-b5cd-4d32f77a7b32",
    "usr-s390-verity-sig": "17440e4f-a8d0-467f-a46e-3912ae6ef2c5",
    "usr-s390x-verity-sig": "3f324816-667b-46ae-86ee-9b0c0c6c11b4",
    "usr-tilegx-verity-sig": "4ede75e2-6ccc-4cc8-b9c7-70334b087510",
    "usr-x86-64-verity-sig": "e7bb33fb-06cf-4e81-8273-e543b413e2e2",
    "usr-x86-verity-sig": "974a71c0-de41-43c3-be5d-5c5ccd1ad2c0",

    # Special partitions
    "esp": "c12a7328-f81f-11d2-ba4b-00a0c93ec93b",
    "xbootldr": "bc13c2ff-59e6-4262-a352-b275fd6f7172",
    "srv": "3b8f8425-20e0-4f3b-907f-1a25a76f98e8",
    "var": "4d21b016-b534-45c2-a9fb-5c16e091fd2d",
    "tmp": "7ec6f557-3bc5-4aca-b293-16ef5df639d1",
    "user-home": "773f91ef-66d4-49b5-bd83-d683bf40ad16",
    "linux-generic": "0fc63daf-8483-4772-8e79-3d69d8477de4"
}

@dataclass
class MbrPartitionEntry:
    """MBR partition entry structure"""
    boot: int = 0
    first_chs: List[int] = None
    partition_type: int = 0
    last_chs: List[int] = None
    relative_sectors: int = 0
    total_sectors: int = 0
    
    def __post_init__(self):
        if self.first_chs is None:
            self.first_chs = [0, 0, 0]
        if self.last_chs is None:
            self.last_chs = [0, 0, 0]

@dataclass
class MbrTail:
    """MBR tail structure mapping"""
    disk_signature: int = 0
    copy_protected: int = 0
    mbr_partition_entry: List[MbrPartitionEntry] = field(default_factory=list)
    boot_signature: int = 0

    def to_bytes(self) -> bytes:
        pass

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


@dataclass
class KdPrivateData:
    header: KdImgHdr = field(default_factory=KdImgHdr)

    file_size: int = 0
    table_type: str = ""
    medium_type: str = "mmc"
    gpt_location: int = 0
    gpt_no_backup: bool = False

    disk_uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    disksig: int = 0

    part_records: List[KdImgPartRecord] = field(default_factory=list)

    # TOC support fields
    toc_enable: bool = False
    toc_offset: int = 0
    toc_num: int = 0

class KdImageHandler(ImageHandler):
    """KD Image Handler"""
    type = "kdimage"
    opts = [
        "image-info", "chip-info", "board-info",
        "part-flag", "partition-table-type", "gpt-no-backup",
        "gpt-location", "medium-type", "toc", "toc-offset"
    ]

    def __init__(self):
        self.config: Dict[str, Any] = {}
        self.priv: KdPrivateData = KdPrivateData()
        self.temp = str(tempfile.gettempdir())

    def _kburn_flag_flag(self, flag: int) -> int:
        return (flag >> 48) & 0xffff

    def _kburn_flag_val1(self, flag: int) -> int:
        return (flag >> 16) & 0xffffffff

    def _kburn_flag_val2(self, flag: int) -> int:
        return flag & 0xffff

    def _roundup(self, value: int, align: int) -> int:
        """Align up to the alignment boundary (returns original value if align is 0)"""
        if align == 0:
            return value
        return ((value - 1) // align + 1) * align

    def _is_block_device(self, file_path: str) -> bool:
        """Handle block devices, automatically fetching their size"""
        if os.path.exists(file_path):
            # 获取文件的统计信息
            stat_info = os.stat(file_path)
            # 检查是否是块设备
            return (stat_info.st_mode & stat.S_ISBLK(stat_info.st_mode))

        return False


    def setup(self, image: Image, config: Dict[str, Any]) -> None:
        """Initialize configuration and set up partition information"""
        self.config = config

        if self._is_block_device(image.outfile):
            raise ImageError("Writing to block device is not supported\n")

        self._parse_config()
        self._validate_config()
        self._add_virtual_partitions(image)
        self._calculate_partition_offsets(image)

    def _parse_config(self) -> None:
        """Parse configuration parameters into private data structure"""
        priv = self.priv
        priv.header.image_info = self.config.get("image_info", "")
        if '' == priv.header.image_info:
            raise ValueError("Can not get 'image_info'")

        priv.header.chip_info = self.config.get("chip_info", "")
        if '' == priv.header.chip_info:
            raise ValueError("Can not get 'chip_info'")

        priv.header.board_info = self.config.get("board_info", "")
        if '' == priv.header.board_info:
            raise ValueError("Can not get 'board_info'")

        priv.table_type = self.config.get("partition-table-type", "none").lower()
        priv.gpt_location = int(self.config.get("gpt-location", 0))
        priv.gpt_no_backup = self.config.get("gpt-no-backup", False)

        # Parse TOC configuration
        priv.toc_enable = self.config.get("toc", False)
        toc_offset_val = self.config.get("toc-offset", 0)
        if isinstance(toc_offset_val, str):
            priv.toc_offset = parse_size(toc_offset_val)
        else:
            priv.toc_offset = int(toc_offset_val)

    def _setup_uuid(self) -> None:
        """Set disk UUID and signature"""
        # Handle disk UUID
        config = self.config
        if "disk-uuid" in config:
            try:
                uuid.UUID(config["disk-uuid"])
                self.priv.disk_uuid = config["disk-uuid"]
            except ValueError:
                raise ImageError(f"Invalid disk UUID: {config['disk-uuid']}")
        
        # Handle disk signature
        disk_signature = config.get("disk-signature")
        if disk_signature == "random":
            self.priv.disksig = uuid.getnode() & 0xFFFFFFFF  # 随机32位值
        elif disk_signature:
            if not (self.priv.table_type & TYPE_MBR):
                raise ImageError("'disk-signature' is only valid for MBR and hybrid partition tables")
            try:
                self.priv.disksig = int(disk_signature, 0)
            except ValueError:
                raise ImageError(f"Invalid disk signature: {disk_signature}")


    def _parse_part_uuid(self, part: Partition) -> None:
        if self.priv.table_type == TYPE_NONE:
            part.in_partition_table = False

        if part.partition_type_uuid and (not (self.priv.table_type & TYPE_GPT)):
            raise ValueError("'partition-type-uuid' is only valid for gpt and hybrid partition-table-type")
        if part.partition_type and (not (self.priv.table_type & TYPE_MBR)):
            raise ValueError("'partition-type' is only valid for mbr and hybrid partition-table-type")

        if (self.priv.table_type & TYPE_GPT) and (part.in_partition_table):
            if not part.partition_type_uuid:
                part.partition_type_uuid = "L"
            if part.partition_type_uuid:
                uuid = self._get_gpt_partition_type(part.partition_type_uuid).bytes
                if not uuid:
                    raise ValueError(f"Invalid type shortcut: {part.partition_type_uuid}")
                part.partition_uuid = uuid
            


    def _validate_config(self) -> None:
        """Validate configuration parameter effectiveness"""

        # Parse partition table type
        table_type = self.priv.table_type
        if table_type == "none":
            self.priv.table_type = TYPE_NONE
        elif table_type in ["mbr", "dos"]:
            self.priv.table_type = TYPE_MBR
        elif table_type == "gpt":
            self.priv.table_type = TYPE_GPT
        else:
            raise ImageError(f"Partition table type '{table_type}' is not supported")

        table_type = self.priv.medium_type
        if table_type == "mmc":
            self.priv.medium_type = MEDIUM_TYPE_MMC
        elif table_type == "spi_nand":
            self.priv.medium_type = MEDIUM_TYPE_SPI_NAND
        elif table_type == "spi_nor":
            self.priv.medium_type = MEDIUM_TYPE_SPI_NOR
        else:
            raise ValueError(f"'{table_type}' is not a valid medium-type")

        self._validate_config_parameters()

    def _validate_config_parameters(self) -> None:
        """Validate configuration parameter effectiveness"""
        if self.priv.table_type & TYPE_GPT:
            self._setup_uuid()
            # Validate GPT location
            if self.priv.gpt_location % 512 != 0:
                raise ImageError(f"GPT table location ({self.priv.gpt_location}) must be a multiple of 512 bytes")

    def _add_virtual_partitions(self, image: Image) -> None:
        """Add virtual partitions related to the partition table"""
        table_type = self.priv.table_type
        
        if table_type & TYPE_MBR:
            # Add MBR partition table virtual partition (offset 0, size 512 bytes)
            mbr_part = Partition(
                name="partition_table_mbr",
                parent_image=image,
                offset=0,
                size=512,
                in_partition_table=False  # MBR itself is not included in the partition table entries
            )
            image.partitions.append(mbr_part)
        
        elif table_type == TYPE_GPT:
            # GPT Header (LBA1, 512 bytes)
            gpt_header = Partition(
                name="partition_table_gpt_header",
                parent_image=image,
                offset=512,
                size=512,
                in_partition_table=False
            )
            # GPT Partition Entry Array (default 128 entries, 128 bytes each)
            gpt_array_size = (GPT_SECTORS - 1) * 512
            gpt_location = self.priv.gpt_location if self.priv.gpt_location else 2 * 512
            gpt_array = Partition(
                name="partition_table_gpt_array",
                parent_image=image,
                offset=gpt_location,
                size=gpt_array_size,
                in_partition_table=False
            )
            image.partitions.append(gpt_header)
            image.partitions.append(gpt_array)

            # Add GPT backup partition (if needed)
            if not self.priv.gpt_no_backup:
                gpt_backup = Partition(
                    name="partition_table_gpt_backup",
                    parent_image=image,
                    offset=64 * 1024,
                    size=GPT_SECTORS * 512,
                    in_partition_table=False
                )
                image.partitions.append(gpt_backup)

        if self.priv.toc_enable:
            toc_offset = self.priv.toc_offset if self.priv.toc_offset else 0
            # The initial size can be a minimum value, the actual size will be calculated in _setup_toc_partitions
            toc_partition = Partition(
                name="partition_toc",
                parent_image=image.name,
                offset=toc_offset,
                size=64, # Initial size, will be overwritten later
                in_partition_table=False
            )
            image.partitions.append(toc_partition)

    def _calculate_partition_offsets(self, image: Image) -> None:
        """Calculate the offset and size of all partitions, handling alignment and overlap checks"""

        self.priv.file_size = KDIMG_CONTENT_START_OFFSET

        # Handle TOC (must be processed when calculating file size, as it may affect subsequent partition offsets)
        if self.priv.toc_enable:
            self._setup_toc_partitions(image)

        for part in image.partitions:
            self._parse_part_uuid(part)

            if not part.image:
                continue

            image_path = next((dep['image_path'] for dep in image.dependencies 
                                if dep.get('image') == part.image), None)
            if not image_path or not os.path.exists(image_path):
                raise ImageError(f"Subimage not found: part:{part}")

            child_size = os.path.getsize(image_path)

            if not part.size:
                part.size = self._roundup(child_size, 4096)
            
            if not part.size or child_size > part.size:
                raise ImageError("Setup failed, partition size too small")

            self.priv.file_size += self._roundup(part.size, 4096)

        # Check for overlapping partitions
        self._has_overlapping_partitions(image.partitions)

        # MBR partition count check (maximum 4 primary partitions)
        if self.priv.table_type == TYPE_MBR:
            user_parts = [p for p in image.partitions if p.in_partition_table]
            if len(user_parts) > 4:
                raise ImageError(f"MBR partition table supports a maximum of 4 primary partitions, current configuration has {len(user_parts)}")

    def _setup_toc_partitions(self, image: Image) -> None:
        """Set up TOC entries and update TOC partition size"""
        if not self.priv.toc_enable:
            return

        toc_entries = []
        index_count = 0

        # Create a TOC entry for each partition
        for part in image.partitions:
            if part.name.startswith('['):  # Skip internal partitions
                continue

            toc_entry = TocInsertData()
            toc_entry.partition_name = part.name[:31]  # Limit name length
            toc_entry.load = 1 if part.load else 0
            toc_entry.boot = part.boot
            toc_entry.partition_offset = part.offset if part.offset else 0
            toc_entry.partition_size = part.size if part.size else 0

            toc_entries.append(toc_entry)
            index_count += 1

        if index_count > 0:
            self.priv.toc_num = index_count

            # Find the TOC partition and update its size
            toc_partition = next((p for p in image.partitions if p.name == "partition_toc"), None)
            if toc_partition:
                toc_size = 64 * index_count  # Each TOC entry is 64 bytes
                toc_partition.size = toc_size

                print(f"TOC Partition: {toc_partition.name} (offset 0x{toc_partition.offset:x}, size 0x{toc_size:x})")

                # Store TOC data for later writing
                image.handler_config['toc_entries'] = toc_entries

    def _has_overlapping_partitions(self, partitions: List[Partition]):
        """Check for overlaps in the partition list"""
        sorted_parts = sorted(partitions, key=lambda p: p.offset)
        for i in range(1, len(sorted_parts)):
            print(f"check {sorted_parts[i-1].name}, {sorted_parts[i].name}")
            prev = sorted_parts[i-1]
            curr = sorted_parts[i]
            if curr.offset < prev.offset + prev.size:
                raise ImageError(f"Partition {curr.name} overlaps with {prev.name}")

    def _get_gpt_partition_type(self, shortcut: str) -> Optional[str]:
        """Look up GPT partition type UUID"""
        return GPT_PARTITION_TYPES.get(shortcut.upper())

    def generate(self, image: Image) -> None:
        """Generate KD image file"""
        try:
            prepare_image(image, self.priv.file_size)
            self._write_partition_data(image)

        except Exception as e:
            raise ImageError(f"Failed to generate KD image: {str(e)}")

    def _calculate_sha256(self, filename: str, offset: int, size: int) -> bytes:
        """Calculate the SHA256 of the specified region of the file"""
        hasher = hashlib.sha256()
        with open(filename, 'rb') as f:
            f.seek(offset)
            hasher.update(f.read(size))
        return hasher.digest()

    def _write_partition_data(self, image: Image) -> None:
        """Write all partition data and maintain partition records"""
        padding_byte = b'\x00'
        if self.priv.medium_type in (MEDIUM_TYPE_SPI_NAND, MEDIUM_TYPE_SPI_NOR):
            padding_byte = b'\xff'

        # Initialize write offset
        image_write_offset = KDIMG_CONTENT_START_OFFSET

        for part_idx, part in enumerate(image.partitions):

            # --- Handle virtual partitions (MBR and TOC) ---
            child_image = None
            if not part.image:
                if part.name == "partition_table_mbr":
                    child_image = self._generate_mbr(image)  # Use MBR generation method without TOC
                    image_path = child_image.outfile
                    child_size = child_image.size
                elif part.name == "partition_toc":
                    if self.priv.toc_enable:
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
                # Get sub-image path
                image_path = next((dep['image_path'] for dep in image.dependencies 
                                if dep.get('image') == part.image), None)
                if not image_path or not os.path.exists(image_path):
                    raise ImageError(f"Subimage not found: {part.image}")

                child_size = os.path.getsize(image_path)
                
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

            # Alignment handling
            aligned_child_size = child_size 
            if 4096 < child_size:
                aligned_child_size = self._roundup(child_size, 4096)

            # Deduplication logic for records
            skip_insert = False
            for record in self.priv.part_records:
                if record.image_file == image_path:
                    print(f"Skipping duplicate part: {part.name} image: {image_path}")
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
                    self.priv.part_records.append(part_record)

                    skip_insert = True
                    break

            if skip_insert:
                continue
            # Write data

            print(f"write name: {part.name} offset: {part.offset} part_size: {part.size},write_offset: {image_write_offset}, child_size: {child_size}, aligned_child_size: {aligned_child_size}")
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
            self.priv.part_records.append(part_record)

            # Offset alignment
            image_write_offset += self._roundup(aligned_child_size, 4096)

            self.priv.header.part_tbl_num = len([p for p in image.partitions])
            # print(f"tbl_num: {self.priv.header.part_tbl_num} idx: {part_idx}")
            if part_idx > self.priv.header.part_tbl_num:
                raise ValueError("Image partition count does not match")

        # Final stage of image generation
        part_table_data = b''
        for part in self.priv.part_records:
            # print(f"kdimgpart: {part}")
            part_table_data += part.part.to_bytes()
            # print(f"test: {part.part.to_bytes()[0:100].hex()}")

        part_table_crc = self._calculate_crc32(part_table_data)

        # for part in self.priv.part_records:
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
        header = self.priv.header
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

        print(f"final header size: {len(final_header_bytes)}; part table size: {len(part_table_data)}")
        print(f"final header crc32: 0x{final_header_crc:08x}")

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

        if not self._is_block_device(image.outfile):
            self._validate_file_size(image.outfile, image_write_offset)

        image_info = (f"Successfully generated image {image.outfile}, "
                    f"size {image_write_offset} bytes "
                    f"(0x{image_write_offset:x})")
        print(image_info)

    @staticmethod
    def _safe_to_int(value):
        """Safely converts the value to an integer, supporting '0x' prefix and None values."""
        if isinstance(value, str):
            value = value.strip().lower()
            if value.startswith('0x'):
                # Convert to hexadecimal
                return int(value, 16) 
            try:
                # Attempt to convert to decimal
                return int(value, 10) 
            except ValueError:
                # Strings that cannot be converted to numbers return 0
                return 0
        # If not a string, attempt direct conversion to integer, None converts to 0
        return int(value) if value is not None else 0
    
    def _generate_toc_partition(self, image: Image) -> Image:
        """Generate TOC partition"""
        toc_entries = image.handler_config.get('toc_entries', [])

        # Even if there are no entries, generate a minimal TOC partition
        toc_size = max(64, len(toc_entries) * 64)

        if not toc_entries:
            # Create empty TOC partition (unchanged)
            child_image = Image(
                size = toc_size,
                outfile = os.path.join(self.temp, "partition_toc")
            )
            prepare_image(child_image, size=toc_size)
            print(f"write empty toc partition: {child_image.outfile} size {toc_size}")
            return child_image

        # Build TOC data
        toc_data = bytearray(toc_size)
        
        for i, toc_entry in enumerate(toc_entries):
            offset = i * 64

            # Write partition name (32 bytes) (unchanged)
            name_bytes = toc_entry.partition_name.encode('utf-8')[:31]
            toc_data[offset:offset+32] = name_bytes.ljust(32, b'\x00')

            # Write partition offset (8 bytes, little-endian)
            offset_val = self._safe_to_int(toc_entry.partition_offset)
            struct.pack_into('<Q', toc_data, offset + 32, offset_val)

            # Write partition size (8 bytes, little-endian)
            size_val = self._safe_to_int(toc_entry.partition_size)
            struct.pack_into('<Q', toc_data, offset + 40, size_val)

            # Write flags (2 bytes)
            load_val = self._safe_to_int(toc_entry.load)
            boot_val = self._safe_to_int(toc_entry.boot)

            # bytearray assignment requires integers
            toc_data[offset + 48] = load_val
            toc_data[offset + 49] = boot_val

            # Fill remaining 14 bytes
            toc_data[offset + 50:offset + 64] = b'\x00' * 14

        # Create TOC partition
        child_image = Image(
            size = toc_size,
            outfile = os.path.join(self.temp, "partition_toc")
        )
        prepare_image(child_image, size=toc_size)

        # Write TOC data
        with open(child_image.outfile, 'r+b') as f:
            f.write(toc_data)

        print(f"write toc partition: {child_image.outfile} size {toc_size}")
        return child_image

    def _generate_mbr(self, image: Image) -> Image:
        """Write MBR partition table (excluding TOC data)"""
        # Create MBR structure (512 bytes total, partition table starts at 446, length 64, boot signature 2 bytes)
        # MBR data starts at byte 440
        mbr_data = bytearray(72) 
        
        # Write disk signature (440-443)
        struct.pack_into('<I', mbr_data, 0, self.priv.disksig)
        
        # Write partition table entries (446-509)
        entry_offset = 6 # Internal offset of partition table entries in MBR data (446 - 440)
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
        if self.priv.table_type == TYPE_HYBRID and i < 4:
            self._write_hybrid_mbr_entry(mbr_data, entry_offset)
        
        # Write boot signature (510-511)
        mbr_data[70] = 0x55
        mbr_data[71] = 0xAA

        # Temporary working file
        child_image = Image(
            size = 512,
            outfile = os.path.join(self.temp, "partition_table_mbr")
        )

        prepare_image(child_image)

        # Write MBR to image
        print("write mbr")
        with open(child_image.outfile, 'r+b') as f:
            f.seek(440)
            f.write(mbr_data)

        return child_image

    def _write_mbr_partition_entry(self, mbr_data: bytearray, offset: int, part: Partition) -> None:
        """Write MBR partition table entry"""
        entry = MbrPartitionEntry(
            boot=0x80 if part.bootable else 0x00,
            partition_type=part.partition_type,
            relative_sectors=int(part.offset / 512),
            total_sectors=int(part.size / 512)
        )
        
        # Calculate CHS address
        self._lba_to_chs(entry.relative_sectors, entry.first_chs)
        self._lba_to_chs(entry.relative_sectors + entry.total_sectors - 1, entry.last_chs)
        
        # Write partition table entry
        mbr_data[offset] = entry.boot
        mbr_data[offset+1:offset+4] = bytes(entry.first_chs)
        mbr_data[offset+4] = parse_size(entry.partition_type)
        mbr_data[offset+5:offset+8] = bytes(entry.last_chs)
        struct.pack_into('<I', mbr_data, offset+8, entry.relative_sectors)
        struct.pack_into('<I', mbr_data, offset+12, entry.total_sectors)

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

    def _write_hybrid_mbr_entry(self, mbr_data: bytearray, offset: int) -> None:
        """Write special entry for hybrid partition table"""
        entry = MbrPartitionEntry(
            partition_type=0xee,
            relative_sectors=1,
            total_sectors=(self.priv.gpt_location // 512) + GPT_SECTORS - 2
        )
        self._lba_to_chs(entry.relative_sectors, entry.first_chs)
        self._lba_to_chs(entry.relative_sectors + entry.total_sectors - 1, entry.last_chs)
        
        mbr_data[offset] = entry.boot
        mbr_data[offset+1:offset+4] = bytes(entry.first_chs)
        mbr_data[offset+4] = entry.partition_type
        mbr_data[offset+5:offset+8] = bytes(entry.last_chs)
        struct.pack_into('<I', mbr_data, offset+8, entry.relative_sectors)
        struct.pack_into('<I', mbr_data, offset+12, entry.total_sectors)

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
