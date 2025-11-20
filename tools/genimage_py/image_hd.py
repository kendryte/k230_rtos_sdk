import struct
import subprocess
import uuid
import os
import stat
import zlib
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple, Iterable
from .common import ImageHandler, Image, Partition, ImageError, run_command, prepare_image, parse_size, insert_data, TocInsertData

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

    # Verity verification partitions
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

    # Signature verification partitions
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
    "usr-riscv64-verity-sig": "8f1056be-9b05-47c4-81d6-be53128e5b54",
    "usr-s390-verity-sig": "b663c618-e7bc-4d6d-90aa-11b756bb1797",
    "usr-s390x-verity-sig": "31741cc4-1a2a-4111-a581-e00b447d2d06",
    "usr-tilegx-verity-sig": "2fb4bf56-07fa-42da-8132-6b139f2026ae",
    "usr-x86-64-verity-sig": "77ff5f63-e7b6-4633-acf4-1565b864c0e6",
    "usr-x86-verity-sig": "8f461b0d-14ee-4e81-9aa9-049b6fb97abd",

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
    """MBR partition table entry structure"""
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
class GptPartitionEntry:
    """GPT partition table entry structure"""
    type_uuid: bytes = b''
    uuid: bytes = b''
    first_lba: int = 0
    last_lba: int = 0
    flags: int = 0
    name: List[int] = None
    
    def __post_init__(self):
        if self.name is None:
            self.name = [0] * 36
        if not self.type_uuid:
            self.type_uuid = b'\x00' * 16
        if not self.uuid:
            self.uuid = b'\x00' * 16

@dataclass
class GptHeader:
    """GPT header structure"""
    signature: bytes = b'EFI PART'
    revision: int = GPT_REVISION_1_0
    header_size: int = 92
    header_crc: int = 0
    reserved: int = 0
    current_lba: int = 1
    backup_lba: int = 0
    first_usable_lba: int = 0
    last_usable_lba: int = 0
    disk_uuid: bytes = b''
    starting_lba: int = 2
    number_entries: int = GPT_ENTRIES
    entry_size: int = 128
    table_crc: int = 0
    
    def __post_init__(self):
        if not self.disk_uuid:
            self.disk_uuid = uuid.uuid4().bytes

@dataclass
class HdPrivateData:
    """Hard disk image handler private data class"""
    extended_partition_index: int = 0
    extended_partition: Optional[Partition] = None
    align: int = 512
    disksig: int = 0
    disk_uuid: str = str(uuid.uuid4())
    table_type: int = TYPE_MBR
    gpt_location: int = 2 * 512
    gpt_no_backup: bool = False
    fill: bool = False
    file_size: int = 0
    toc_enable: bool = False
    toc_offset: int = 0
    toc_num: int = 0

class HdImageHandler(ImageHandler):
    """Hard disk image handler, supports MBR, GPT and hybrid partition tables"""
    type = "hdimage"
    opts = [
        "align", "extended-partition", "partition-table-type",
        "gpt-location", "gpt-no-backup", "fill", "partition-table",
        "gpt", "disk-uuid", "disksig", "disk-signature", "toc", "toc-offset"
    ]
    
    def __init__(self):
        self.config = {}
        self.priv: HdPrivateData = HdPrivateData()
    
    def _parse_size(self, size: Any) -> int:
        """Parse size string with units (K, M, G)"""
        if isinstance(size, int):
            return size
        if not isinstance(size, str):
            raise ImageError(f"Invalid size format: {size}")
        
        return parse_size(size)
    
    @staticmethod
    def _roundup(value: int, align: int) -> int:
        """Round up to alignment boundary"""
        if align == 0:
            return value
        return ((value - 1) // align + 1) * align
    
    @staticmethod
    def _rounddown(value: int, align: int) -> int:
        """Round down to alignment boundary"""
        if align == 0:
            return value
        return value - (value % align)
    
    def setup(self, image: Image, config: Dict[str, Any]) -> None:

        self.config = config
        
        # Handle block device
        self._handle_block_device(image)
        
        # Parse configuration parameters
        self._parse_config_parameters(config)
        
        # Validate configuration parameters
        self._validate_config_parameters()
        
        # Set up logical partitions
        self._setup_logical_partitions(image)

        # Handle disk UUID and signature
        self._setup_uuid(image, config)

        # Hybrid partition table validation
        self._validate_hybrid_partition_table(image)

        # Calculate partition offsets and sizes
        self._calculate_partition_offsets(image)

    
    def _handle_block_device(self, image: Image) -> None:
        """Handle block device, automatically get its size"""
        if os.path.exists(image.outfile):
            try:
                # Get file statistics
                stat_info = os.stat(image.outfile)
                # Check if it's a block device
                if stat_info.st_mode & stat.S_ISBLK(stat_info.st_mode):
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
            except OSError as e:
                raise ImageError(f"Unable to get statistics for file {image.outfile}: {str(e)}")

    
    def _parse_config_parameters(self, config: Dict[str, Any]) -> None:
        """Parse configuration parameters to private data structure"""
        self.priv.align = self._parse_size(config.get("align", 512))
        self.priv.extended_partition_index = int(config.get("extended-partition", 0))
        self.priv.gpt_location = self._parse_size(config.get("gpt-location", 2 * 512))
        self.priv.gpt_no_backup = config.get("gpt-no-backup", False)
        self.priv.fill = config.get("fill", False)

        # Parse TOC configuration
        self.priv.toc_enable = config.get("toc", False)
        self.priv.toc_offset = self._parse_size(config.get("toc-offset", 0))
        
        # Parse partition table type
        table_type = config.get("partition-table-type", "mbr")
        if table_type == "none":
            self.priv.table_type = TYPE_NONE
        elif table_type in ["mbr", "dos"]:
            self.priv.table_type = TYPE_MBR
        elif table_type == "gpt":
            self.priv.table_type = TYPE_GPT
        elif table_type == "hybrid":
            self.priv.table_type = TYPE_HYBRID
        else:
            raise ImageError(f"Invalid partition table type: {table_type}")
        
        # Handle deprecated configuration
        self._handle_deprecated_config(config)
    
    def _handle_deprecated_config(self, config: Dict[str, Any]) -> None:
        """Handle deprecated configuration parameters"""
        if "partition-table" in config:
            self.priv.table_type = TYPE_MBR if config["partition-table"] else TYPE_NONE
            print("Warning: 'partition-table' is deprecated, please use 'partition-table-type'")
        if "gpt" in config:
            self.priv.table_type = TYPE_GPT if config["gpt"] else TYPE_MBR
            print("Warning: 'gpt' is deprecated, please use 'partition-table-type'")
    
    def _validate_config_parameters(self) -> None:
        """Validate configuration parameters"""
        # Validate alignment parameters
        if (self.priv.table_type != TYPE_NONE and 
            (self.priv.align % 512 != 0 or self.priv.align == 0)):
            raise ImageError(f"Partition alignment ({self.priv.align}) must be a multiple of 512 bytes")
        
        # Validate GPT location
        if self.priv.gpt_location % 512 != 0:
            raise ImageError(f"GPT table location ({self.priv.gpt_location}) must be a multiple of 512 bytes")
    
    def _setup_uuid(self, image: Image, config: Dict[str, Any]) -> None:
        """Setup disk UUID and signature"""
        # Handle disk UUID
        if "disk-uuid" in config:
            try:
                uuid.UUID(config["disk-uuid"])
                self.priv.disk_uuid = config["disk-uuid"]
            except ValueError:
                raise ImageError(f"Invalid disk UUID: {config['disk-uuid']}")
        
        # Handle disk signature
        disk_signature = config.get("disk-signature")
        if disk_signature == "random":
            self.priv.disksig = uuid.getnode() & 0xFFFFFFFF  # Random 32-bit value
        elif disk_signature:
            if not (self.priv.table_type & TYPE_MBR):
                raise ImageError("'disk-signature' is only valid for MBR and hybrid partition tables")
            try:
                self.priv.disksig = int(disk_signature, 0)
            except ValueError:
                raise ImageError(f"Invalid disk signature: {disk_signature}")
    
    def _validate_hybrid_partition_table(self, image: Image) -> None:
        """Validate hybrid partition table validity"""
        if self.priv.table_type == TYPE_HYBRID:
            hybrid_entries = sum(1 for p in image.partitions 
                                if p.in_partition_table and p.partition_type)
            print(f"Hybrid partition table: {hybrid_entries} partitions")
            if hybrid_entries == 0:
                raise ImageError("Hybrid partition table must contain at least one partition with partition-type")
            if hybrid_entries > 3:
                raise ImageError(f"Hybrid partition table supports max 3 partitions, currently has {hybrid_entries}")

    def _parse_partition_config(self, idx: int, part: Partition) -> None:
        """Parse single partition configuration"""
        # Check if partition type configuration matches partition table type
        if part.partition_type_uuid and not (self.priv.table_type & TYPE_GPT):
            raise ImageError(f"Partition {part.name}: partition-type-uuid is only valid for GPT and hybrid partition tables")
        
        if part.partition_type and not (self.priv.table_type & TYPE_MBR):
            raise ImageError(f"Partition {part.name}: partition-type is only valid for MBR and hybrid partition tables")
            
    
    def generate(self, image: Image) -> None:

        try:
            # Prepare image file
            prepare_image(image)

            
            # Ensure extended partition index is set
            self._ensure_extended_partition_index(image)

            # Write partition data
            for part in image.partitions:
                self._write_partition_data(image, part)
            
            # Write partition table
            if self.priv.table_type & TYPE_GPT:
                self._write_gpt(image)
            elif self.priv.table_type & TYPE_MBR:
                self._write_mbr(image)

            # Write TOC
            self._write_toc(image)

        except Exception as e:
            raise ImageError(f"Failed to generate image: {str(e)}")
    
    def _ensure_extended_partition_index(self, image: Image) -> None:
        """Ensure extended partition index is set"""
        if self.priv.extended_partition_index:
            return
            
        count = 0
        for part in image.partitions:
            if not part.in_partition_table:
                continue
                
            count += 1
            if count > 4:
                self.priv.extended_partition_index = 4
    
    def _setup_logical_partitions(self, image: Image) -> None:
        """Setup logical partitions and extended partition"""
        if self.priv.extended_partition_index > 4:
            raise ImageError(f"Invalid extended partition index ({self.priv.extended_partition_index}), must be <= 4")
        
        if self.priv.table_type != TYPE_MBR:
            return
            
        self._ensure_extended_partition_index(image)
        if not self.priv.extended_partition_index:
            return
        
        count = 0
        mbr_entries = 0
        in_extended = False
        found_extended = False
        
        for part in image.partitions:
            if not part.in_partition_table:
                continue
                
            count += 1
            if self.priv.extended_partition_index == count:
                # Create extended partition
                offset = part.offset - self.priv.align if part.offset else 0
                extended_part = Partition(
                    name="[Extended]",
                    offset=offset,
                    parent_image=image.name,
                    size=0,
                    in_partition_table=True,
                    partition_type=PARTITION_TYPE_EXTENDED,
                    align=self.priv.align
                )
                image.partitions.append(extended_part)
                self.priv.extended_partition = extended_part
                in_extended = found_extended = True
                mbr_entries += 1
            
            print(f"forced_primary: {part.forced_primary}; in_extended: {in_extended}; ")
            
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
            
            if mbr_entries > 4:
                raise ImageError("Too many primary partitions (max 4)")
    
    def _calculate_partition_offsets(self, image: Image) -> None:
        """Calculate partition offsets and sizes"""
        now = 0
        gpt_backup = None
        self.priv.file_size = 0
        
        # Reserve space for partition table
        if self.priv.table_type != TYPE_NONE:
            # MBR partition table
            mbr = Partition(name="[MBR]",parent_image=image.name, offset=512 - 72, size=72, in_partition_table=False)
            image.partitions.append(mbr)
            now = mbr.offset + mbr.size
            
            # GPT partition table
            if self.priv.table_type & TYPE_GPT:
                print("Create GPT")
                gpt_header = Partition(
                    name="[GPT header]",
                    parent_image=image.name, 
                    offset=512, 
                    size=512, 
                    in_partition_table=False
                )
                gpt_array = Partition(
                    name="[GPT array]",
                    parent_image=image.name,
                    offset=self.priv.gpt_location,
                    size=(GPT_SECTORS - 1) * 512,
                    in_partition_table=False
                )
                image.partitions.append(gpt_header)
                image.partitions.append(gpt_array)
                now = max(now, gpt_array.offset + gpt_array.size)
                
                # GPT backup partition
                backup_size = GPT_SECTORS * 512
                backup_offset = image.size - backup_size if image.size else 0
                gpt_backup = Partition(
                    name="[GPT backup]",
                    parent_image=image.name,
                    offset=backup_offset,
                    size=backup_size,
                    in_partition_table=False
                )
                image.partitions.append(gpt_backup)

        # Handle TOC
        if self.priv.toc_enable:
            self._setup_toc_partitions(image)

        # Handle autoresize partitions
        self._setup_autoresize_partitions(image)
        
        # Calculate offset and size for each partition
        for part in image.partitions:
            
            # Set partition alignment
            if not part.align:
                part.align = self.priv.align if (part.in_partition_table or 
                                                  self.priv.table_type == TYPE_NONE) else 1
            # Check alignment
            if part.in_partition_table and ((part.align % self.priv.align) != 0):
                raise ImageError(f"Partition {part.name} alignment ({part.align}) must be a multiple of image alignment ({self.priv.align})")
            
            self._parse_partition_config(image, part)

            if not part.size:
                image_path = next((dep['image_path'] for dep in image.dependencies 
                    if dep.get('image') == part.image), None)
                if not image_path or not os.path.exists(image_path):
                    raise ImageError(f"Subimage not found: {part.image}")

                child_size = os.path.getsize(image_path)
                part.size = self._roundup(child_size, part.align) if part.in_partition_table else child_size
      
            # Reserve EBR space for logical partitions
            if part.logical:
                now += self.priv.align
                now = self._roundup(now, part.align)

            if part == gpt_backup and 0 == part.offset:
                now += part.size
                part.offset = _roundup(now, 4096) - part.size

            # Set offset
            if not part.offset and (part.in_partition_table or self.priv.table_type == TYPE_NONE):
                part.offset = self._roundup(now, part.align)
            
            # Check if offset meets alignment requirements
            if part.offset % part.align != 0:
                raise ImageError(f"Partition {part.name} offset ({part.offset}) must be a multiple of {part.align} bytes")
            
            # Ensure partition size is valid
            if not part.size and part != self.priv.extended_partition:
                raise ImageError(f"Partition {part.name} size cannot be zero")
            
            # Check for partition overlap
            if not part.logical and self._check_overlap(image, part):
                raise ImageError(f"Partition {part.name} overlaps with a previous partition")

            # Check if partition size is a multiple of 512 bytes
            if part.in_partition_table and part.size % 512 != 0:
                raise ImageError(f"Partition {part.name} size ({part.size}) must be a multiple of 512 bytes")
            
            # Update current position
            if part.offset + part.size > now:
                now = part.offset + part.size

            # Update file size
            if part.image:
                child_size = self._get_child_image_size(image, part.image)
                if part.offset + child_size > self.priv.file_size:
                    self.priv.file_size = part.offset + child_size

            # Update extended partition size
            if part.logical :
                file_size = part.offset - self.priv.align + 512
                if file_size > self.priv.file_size:
                    self.priv.file_size = file_size

                self.priv.extended_partition.size = now - self.priv.extended_partition.offset
                
        # Ensure image size is sufficient
        if not image.size:
            image.size = now
        
        print(f"image size: {image.size},now size: {now}")
        if now > image.size:
            raise ImageError("Partition size exceeds image size")
        
        # Final file size determination
        if self.priv.fill or ((self.priv.table_type & TYPE_GPT) and not self.priv.gpt_no_backup):
            self.priv.file_size = image.size
            print(f"update file size: {self.priv.file_size}")

    
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
            if self.priv.table_type & TYPE_GPT:
                partsize -= GPT_SECTORS * 512  # Subtract GPT backup area
            
            # Alignment adjustment
            partsize = self._rounddown(partsize, part.align or self.priv.align)
            
            if partsize <= 0:
                raise ImageError("Partition exceeds device size")
            if partsize < part.size:
                raise ImageError(f"Auto-resizing partition {part.name} size ({partsize}) is smaller than minimum size ({part.size})")
            
            part.size = partsize
            resized = True

    
    def _check_overlap(self, image: Image, part: Partition) -> bool:
        """Check if partitions overlap"""
        for other in image.partitions:
            if part == other:
                return False
            
            print(f"check overlap {part.name} {other.name}")
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
    
    def _image_has_hole_covering(self, image: Image, child_name: str, start: int, end: int) -> bool:
        """Check if the sub-image has a hole covering the specified range"""
        if not child_name:
            return False
            
        print(f"check child image {child_name} {start} {end}")
        for dep in image.partitions:
            if dep.name == child_name:
                for hole in dep.holes:
                    if hole.start <= start and end <= hole.end:
                        return True
        return False
    
    def _get_child_image_size(self, image: Image, child_name: str) -> int:
        """Get the size of the sub-image"""
        for dep in image.partitions:
            if dep.name == child_name:
                return dep.size
        return 0
    
    def _write_partition_data(self, image: Image, part: Partition) -> None:
        """Write partition data"""
        if not part.image:
            return
                
        child_size = 0
        image_path = ''

        # Find sub-image
        for dep in image.dependencies:
            if dep.get('image') == part.image:
                image_path = dep.get('image_path')
                print(f"dep: {dep.get('image')}, {dep.get('image_path')}")
                break
            
        if os.path.exists(image_path):
            child_size = os.path.getsize(image_path)
        else:
            raise ImageError(f"Sub-image not found: {part.image}")

        # Check sub-image size
        if child_size > part.size:
            raise ImageError(f"Partition {part.name} size ({part.size}) is smaller than sub-image {part.image} size ({child_size})")

        insert_data(image, image_path, part.size , part.offset, bytes(0))
    
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
    
    def _write_mbr(self, image: Image) -> None:
        """Write MBR partition table"""
        # Create MBR structure
        mbr_data = bytearray(72)
        
        # Write disk signature
        struct.pack_into('<I', mbr_data, 0, self.priv.disksig)
        
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
        if self.priv.table_type == TYPE_HYBRID and i < 4:
            self._write_hybrid_mbr_entry(mbr_data, entry_offset)
        
        # Write boot signature
        mbr_data[70] = 0x55
        mbr_data[71] = 0xAA
        
        # Write MBR to image
        print("write mbr")
        with open(image.outfile, 'r+b') as f:
            f.seek(440)
            f.write(mbr_data)
        
        # Handle EBRs for logical partitions
        self._write_ebrs(image)
    
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
    
    def _write_ebrs(self, image: Image) -> None:
        """Write Extended Boot Records (EBR)"""
        extended_part = self.priv.extended_partition
        if not extended_part:
            return
            
        logical_parts = [p for p in image.partitions if p.logical]
        if not logical_parts:
            return
            
        prev_part = None
        for part in logical_parts:
            ebr_offset = part.offset - self.priv.align + 446
            ebr_data = bytearray(512)
            
            # First entry: current logical partition
            self._write_ebr_current_entry(ebr_data, part, extended_part)
            
            # Second entry: next EBR
            if prev_part is not None:
                self._write_ebr_next_entry(ebr_data, part, extended_part)
            
            # Write boot signature
            ebr_data[510] = 0x55
            ebr_data[511] = 0xAA
            
            # Write EBR to image
            with open(image.outfile, 'r+b') as f:
                f.seek(ebr_offset)
                f.write(ebr_data)
                
            prev_part = part
    
    def _write_ebr_current_entry(self, ebr_data: bytearray, part: Partition, extended_part: Partition) -> None:
        """Write current partition entry in EBR"""
        entry1 = MbrPartitionEntry(
            partition_type=part.partition_type,
            relative_sectors=int(self.priv.align / 512),
            total_sectors=int(part.size / 512)
        )
        
        self._lba_to_chs(
            entry1.relative_sectors + int((part.offset - self.priv.align) / 512), 
            entry1.first_chs
        )
        self._lba_to_chs(
            entry1.relative_sectors + entry1.total_sectors - 1 + 
            int((part.offset - self.priv.align) / 512), 
            entry1.last_chs
        )
        
        # Write first entry
        ebr_data[0] = entry1.boot
        ebr_data[1:4] = bytes(entry1.first_chs)
        ebr_data[4] = entry1.partition_type
        ebr_data[5:8] = bytes(entry1.last_chs)
        struct.pack_into('<I', ebr_data, 8, entry1.relative_sectors)
        struct.pack_into('<I', ebr_data, 12, entry1.total_sectors)
    
    def _write_ebr_next_entry(self, ebr_data: bytearray, part: Partition, extended_part: Partition) -> None:
        """Write next partition entry in EBR"""
        next_ebr_rel_sectors = int(
            (part.offset - self.priv.align - extended_part.offset) / 512
        )
        entry2 = MbrPartitionEntry(
            partition_type=PARTITION_TYPE_EXTENDED,
            relative_sectors=next_ebr_rel_sectors,
            total_sectors=int((part.size + self.priv.align) / 512)
        )
        
        self._lba_to_chs(extended_part.offset // 512, entry2.first_chs)
        self._lba_to_chs(
            (extended_part.offset // 512) + entry2.total_sectors - 1, 
            entry2.last_chs
        )
        
        # Write second entry
        ebr_data[16] = entry2.boot
        ebr_data[17:20] = bytes(entry2.first_chs)
        ebr_data[20] = entry2.partition_type
        ebr_data[21:24] = bytes(entry2.last_chs)
        struct.pack_into('<I', ebr_data, 24, entry2.relative_sectors)
        struct.pack_into('<I', ebr_data, 28, entry2.total_sectors)
    
    def _write_gpt(self, image: Image) -> None:
        """Write GPT partition table"""
        # Create GPT header
        header = GptHeader()
        header.disk_uuid = uuid.UUID(self.priv.disk_uuid).bytes
        header.backup_lba = (image.size // 512) - 1 if not self.priv.gpt_no_backup else 1
        header.last_usable_lba = (image.size // 512) - 1 - GPT_SECTORS
        header.starting_lba = self.priv.gpt_location // 512
        
        # Collect partition information
        gpt_entries, smallest_offset = self._collect_gpt_entries(image)
        
        # Set first usable LBA
        if smallest_offset is None:
            smallest_offset = self.priv.gpt_location + (GPT_SECTORS - 1) * 512
        header.first_usable_lba = smallest_offset // 512
        
        # Build partition table
        table_data = self._build_gpt_table(gpt_entries)
        
        # Calculate partition table CRC
        header.table_crc = zlib.crc32(table_data) & 0xFFFFFFFF
        
        # Calculate header CRC and write
        header_bytes = self._build_gpt_header(header)
        
        # Write primary GPT header and partition table
        print("write gpt")
        with open(image.outfile, 'r+b') as f:
            f.seek(512)
            f.write(header_bytes)
            f.seek(self.priv.gpt_location)
            f.write(table_data)
        
        # Write backup GPT
        if not self.priv.gpt_no_backup:
            self._write_gpt_backup(image, header, table_data)
        
        # Write protective MBR or hybrid MBR
        if self.priv.table_type == TYPE_HYBRID:
            self._write_mbr(image)
        else:
            self._write_protective_mbr(image)
    
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
    
    def _create_gpt_entry(self, part: Partition) -> GptPartitionEntry:
        """Create a single GPT partition table entry"""
        entry = GptPartitionEntry()
        
        # Set partition type UUID
        if part.partition_type_uuid:
            try:
                entry.type_uuid = uuid.UUID(part.partition_type_uuid).bytes
            except ValueError:
                # Try to find type alias
                type_uuid = self._get_gpt_partition_type(part.partition_type_uuid)
                if type_uuid:
                    entry.type_uuid = uuid.UUID(type_uuid).bytes
                else:
                    raise ImageError(f"Partition {part.name} has invalid type: {part.partition_type_uuid}")
        else:
            entry.type_uuid = self._get_gpt_partition_type('L').bytes
        
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
    
    def _build_gpt_table(self, gpt_entries: List[GptPartitionEntry]) -> bytearray:
        """Build GPT partition table data"""
        table_data = bytearray(GPT_ENTRIES * 128)
        for i, entry in enumerate(gpt_entries[:GPT_ENTRIES]):
            offset = i * 128
            table_data[offset:offset+16] = entry.type_uuid
            table_data[offset+16:offset+32] = entry.uuid
            struct.pack_into('<Q', table_data, offset+32, entry.first_lba)
            struct.pack_into('<Q', table_data, offset+40, entry.last_lba)
            struct.pack_into('<Q', table_data, offset+48, entry.flags)
            for j in range(36):
                struct.pack_into('<H', table_data, offset+56 + j*2, entry.name[j])
                
        return table_data
    
    def _build_gpt_header(self, header: GptHeader) -> bytearray:
        header_bytes = bytearray(92)
        header_bytes[0:8] = header.signature
        struct.pack_into('<I', header_bytes, 8, header.revision)
        struct.pack_into('<I', header_bytes, 12, header.header_size)
        struct.pack_into('<I', header_bytes, 16, header.header_crc)
        struct.pack_into('<I', header_bytes, 20, header.reserved)
        struct.pack_into('<Q', header_bytes, 24, header.current_lba)
        struct.pack_into('<Q', header_bytes, 32, header.backup_lba)
        struct.pack_into('<Q', header_bytes, 40, header.first_usable_lba)
        struct.pack_into('<Q', header_bytes, 48, header.last_usable_lba)
        header_bytes[56:72] = header.disk_uuid
        struct.pack_into('<Q', header_bytes, 72, header.starting_lba)
        struct.pack_into('<I', header_bytes, 80, header.number_entries)
        struct.pack_into('<I', header_bytes, 84, header.entry_size)
        struct.pack_into('<I', header_bytes, 88, header.table_crc)
        
        # Recalculate header CRC
        header.header_crc = zlib.crc32(header_bytes) & 0xFFFFFFFF
        struct.pack_into('<I', header_bytes, 16, header.header_crc)
        
        return header_bytes

    def _write_gpt_backup(self, image: Image, header: GptHeader, table_data: bytearray) -> None:
        """Write GPT backup partition table"""
        # Backup header
        backup_header = self._build_gpt_header(header)
        
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
    
    def _get_gpt_partition_type(self, shortcut: str) -> Optional[str]:
        """Look up GPT partition type UUID"""
        return GPT_PARTITION_TYPES.get(shortcut.upper())
    
    def _setup_toc_partitions(self, image: Image) -> None:
        """Setup TOC partition"""
        if not self.priv.toc_enable:
            return

        toc_entries = []
        index_count = 0

        # Create TOC entry for each partition
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
            
            # Create TOC partition
            toc_size = 64 * index_count  # 64 bytes per TOC entry
            toc_partition = Partition(
                name="[TOC]",
                parent_image=image.name,
                offset=self.priv.toc_offset if self.priv.toc_offset else 0,
                size=toc_size,
                in_partition_table=False
            )
            image.partitions.append(toc_partition)
            
            print(f"TOC Partition: {toc_partition.name} (offset 0x{toc_partition.offset:x}, size 0x{toc_partition.size:x})")
            
            # Store TOC data for later writing
            image.handler_config['toc_entries'] = toc_entries

    @staticmethod
    def _safe_to_int(value):
        if isinstance(value, str):
            value = value.strip().lower()
            if value.startswith('0x'):
                return int(value, 16) # Convert to hexadecimal
            return int(value, 10) # Convert to decimal
        return int(value) if value is not None else 0

    def _write_toc(self, image: Image) -> None:
        """Write TOC data"""
        if not self.priv.toc_enable or not self.priv.toc_num:
            return
            
        toc_entries = image.handler_config.get('toc_entries', [])
        if not toc_entries:
            return

        print("writing TOC")
        
        # Build TOC data
        toc_data = bytearray(self.priv.toc_num * 64)

        for i, toc_entry in enumerate(toc_entries):
            offset = i * 64

            # Write partition name (32 bytes)
            name_bytes = toc_entry.partition_name.encode('utf-8')[:31]
            toc_data[offset:offset+32] = name_bytes.ljust(32, b'\x00')

            # Write partition offset (8 bytes, little-endian)
            # Ensure partition_offset is an integer
            offset_val = self._safe_to_int(toc_entry.partition_offset)
            struct.pack_into('<Q', toc_data, offset + 32, offset_val)

            # Write partition size (8 bytes, little-endian)
            # Ensure partition_size is an integer
            size_val = self._safe_to_int(toc_entry.partition_size)
            struct.pack_into('<Q', toc_data, offset + 40, size_val)

            # Write flags (2 bytes)
            # Ensure load and boot are integers. The load field was cleaned up in _setup_toc_partitions, but use safe_to_int for safety
            load_val = self._safe_to_int(toc_entry.load)
            boot_val = self._safe_to_int(toc_entry.boot) # <--- CRITICAL FIX: Convert boot field

            # bytearray assignment requires integers (0-255)
            toc_data[offset + 48] = load_val
            toc_data[offset + 49] = boot_val 

            # Fill remaining 14 bytes
            toc_data[offset + 50:offset + 64] = b'\x00' * 14

        # Write TOC to image
        toc_offset = self.priv.toc_offset if self.priv.toc_offset else 0
        with open(image.outfile, 'r+b') as f:
            f.seek(toc_offset)
            f.write(toc_data)

        print(f"TOC written at offset 0x{toc_offset:x}, size {len(toc_data)} bytes")

    def _write_protective_mbr(self, image: Image) -> None:
        """Write Protective MBR"""
        mbr_data = bytearray(72)
        
        # Write disk signature
        struct.pack_into('<I', mbr_data, 0 , self.priv.disksig)
        
        # Protective partition table entry
        entry_offset = 6
        entry = MbrPartitionEntry(
            partition_type=0xee,
            relative_sectors=1,
            total_sectors=(image.size // 512) - 1
        )
        self._lba_to_chs(entry.relative_sectors, entry.first_chs)
        self._lba_to_chs(entry.relative_sectors + entry.total_sectors - 1, entry.last_chs)
        
        mbr_data[entry_offset] = entry.boot
        mbr_data[entry_offset+1:entry_offset+4] = bytes(entry.first_chs)
        mbr_data[entry_offset+4] = entry.partition_type
        mbr_data[entry_offset+5:entry_offset+8] = bytes(entry.last_chs)
        struct.pack_into('<I', mbr_data, entry_offset+8, entry.relative_sectors)
        struct.pack_into('<I', mbr_data, entry_offset+12, entry.total_sectors)
        
        # Boot signature
        mbr_data[70] = 0x55
        mbr_data[71] = 0xAA
        
        with open(image.outfile, 'r+b') as f:
            f.seek(440)
            f.write(mbr_data)

    def run(self, image: Image, config: Dict[str, Any]) -> None:
        self.setup(image, config)
        self.generate(image)
