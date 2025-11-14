import struct
import subprocess
import uuid
import os
import stat
import zlib
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple, Iterable
from .common import ImageHandler, Image, Partition, ImageError, run_command, prepare_image, parse_size, insert_data, TocInsertData

# 常量定义
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
    # 基础类型
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

    # 特殊分区
    "barebox-state": "4778ed65-bf42-45fa-9c5b-287a1dc4aab1",
    "barebox-env": "6c3737f2-07f8-45d1-ad45-15d260aab24d",
    "esp": "c12a7328-f81f-11d2-ba4b-00a0c93ec93b",
    "xbootldr": "bc13c2ff-59e6-4262-a352-b275fd6f7172",
    "srv": "3b8f8425-20e0-4f3b-907f-1a25a76f98e8",
    "var": "4d21b016-b534-45c2-a9fb-5c16e091fd2d",
    "tmp": "7ec6f557-3bc5-4aca-b293-16ef5df639d1",
    "user-home": "773f91ef-66d4-49b5-bd83-d683bf40ad16",
    "linux-generic": "0fc63daf-8483-4772-8e79-3d69d8477de4",

    # 根分区 (Discoverable Partitions Specification)
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

    # 用户分区
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

    # Verity 验证分区
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

    # 用户空间Verity验证
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

    # 签名验证分区
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

    # 用户空间签名验证
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

    # 特殊分区
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
    """MBR分区表项结构"""
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
    """GPT分区表项结构"""
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
    """GPT头部结构"""
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
    """硬盘镜像处理器私有数据类"""
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
    """硬盘镜像处理器，支持MBR、GPT和混合分区表"""
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
        """解析带单位的大小字符串（K, M, G）"""
        if isinstance(size, int):
            return size
        if not isinstance(size, str):
            raise ImageError(f"无效的大小格式: {size}")
        
        return parse_size(size)
    
    @staticmethod
    def _roundup(value: int, align: int) -> int:
        """向上取整到对齐边界"""
        if align == 0:
            return value
        return ((value - 1) // align + 1) * align
    
    @staticmethod
    def _rounddown(value: int, align: int) -> int:
        """向下取整到对齐边界"""
        if align == 0:
            return value
        return value - (value % align)
    
    def setup(self, image: Image, config: Dict[str, Any]) -> None:

        self.config = config
        
        # 处理块设备
        self._handle_block_device(image)
        
        # 解析配置参数
        self._parse_config_parameters(config)
        
        # 验证配置参数
        self._validate_config_parameters()
        
        # 设置逻辑分区
        self._setup_logical_partitions(image)

        # 处理磁盘UUID和签名
        self._setup_uuid(image, config)

        # 混合分区表校验
        self._validate_hybrid_partition_table(image)

        # 计算分区偏移和大小
        self._calculate_partition_offsets(image)

    
    def _handle_block_device(self, image: Image) -> None:
        """处理块设备，自动获取其大小"""
        if os.path.exists(image.outfile):
            try:
                # 获取文件的统计信息
                stat_info = os.stat(image.outfile)
                # 检查是否是块设备
                if stat_info.st_mode & stat.S_ISBLK(stat_info.st_mode):
                    if image.size != 0:
                        raise ImageError("块设备目标不允许指定镜像大小")
                    
                    try:
                        with open(image.outfile, 'rb') as f:
                            f.seek(0, os.SEEK_END)
                            image.size = f.tell()
                    except OSError as e:
                        raise ImageError(f"无法获取块设备 {image.outfile} 的大小: {str(e)}")
                    
                    if image.size <= 0:
                        raise ImageError(f"块设备 {image.outfile} 大小无效: {image.size}")
            except OSError as e:
                raise ImageError(f"无法获取文件 {image.outfile} 的统计信息: {str(e)}")

    
    def _parse_config_parameters(self, config: Dict[str, Any]) -> None:
        """解析配置参数到私有数据结构"""
        self.priv.align = self._parse_size(config.get("align", 512))
        self.priv.extended_partition_index = int(config.get("extended-partition", 0))
        self.priv.gpt_location = self._parse_size(config.get("gpt-location", 2 * 512))
        self.priv.gpt_no_backup = config.get("gpt-no-backup", False)
        self.priv.fill = config.get("fill", False)

        # 解析TOC配置
        self.priv.toc_enable = config.get("toc", False)
        self.priv.toc_offset = self._parse_size(config.get("toc-offset", 0))
        
        # 解析分区表类型
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
            raise ImageError(f"无效的分区表类型: {table_type}")
        
        # 处理已弃用的配置
        self._handle_deprecated_config(config)
    
    def _handle_deprecated_config(self, config: Dict[str, Any]) -> None:
        """处理已弃用的配置参数"""
        if "partition-table" in config:
            self.priv.table_type = TYPE_MBR if config["partition-table"] else TYPE_NONE
            print("警告: 'partition-table' 已弃用，请使用 'partition-table-type'")
        if "gpt" in config:
            self.priv.table_type = TYPE_GPT if config["gpt"] else TYPE_MBR
            print("警告: 'gpt' 已弃用，请使用 'partition-table-type'")
    
    def _validate_config_parameters(self) -> None:
        """验证配置参数的有效性"""
        # 验证对齐参数
        if (self.priv.table_type != TYPE_NONE and 
            (self.priv.align % 512 != 0 or self.priv.align == 0)):
            raise ImageError(f"分区对齐({self.priv.align})必须是512字节的倍数")
        
        # 验证GPT位置
        if self.priv.gpt_location % 512 != 0:
            raise ImageError(f"GPT表位置({self.priv.gpt_location})必须是512字节的倍数")
    
    def _setup_uuid(self, image: Image, config: Dict[str, Any]) -> None:
        """设置磁盘UUID和签名"""
        # 处理磁盘UUID
        if "disk-uuid" in config:
            try:
                uuid.UUID(config["disk-uuid"])
                self.priv.disk_uuid = config["disk-uuid"]
            except ValueError:
                raise ImageError(f"无效的磁盘UUID: {config['disk-uuid']}")
        
        # 处理磁盘签名
        disk_signature = config.get("disk-signature")
        if disk_signature == "random":
            self.priv.disksig = uuid.getnode() & 0xFFFFFFFF  # 随机32位值
        elif disk_signature:
            if not (self.priv.table_type & TYPE_MBR):
                raise ImageError("'disk-signature' 仅对MBR和混合分区表有效")
            try:
                self.priv.disksig = int(disk_signature, 0)
            except ValueError:
                raise ImageError(f"无效的磁盘签名: {disk_signature}")
    
    def _validate_hybrid_partition_table(self, image: Image) -> None:
        """验证混合分区表的有效性"""
        if self.priv.table_type == TYPE_HYBRID:
            hybrid_entries = sum(1 for p in image.partitions 
                                if p.in_partition_table and p.partition_type)
            print(f"混合分区表: {hybrid_entries} 个分区")
            if hybrid_entries == 0:
                raise ImageError("混合分区表必须包含至少一个带partition-type的分区")
            if hybrid_entries > 3:
                raise ImageError(f"混合分区表最多支持3个分区，当前有{hybrid_entries}个")

    def _parse_partition_config(self, idx: int, part: Partition) -> None:
        """解析单个分区配置"""
        # 检查分区类型配置是否与分区表类型匹配
        if part.partition_type_uuid and not (self.priv.table_type & TYPE_GPT):
            raise ImageError(f"分区 {part.name}: partition-type-uuid 仅对GPT和混合分区表有效")
        
        if part.partition_type and not (self.priv.table_type & TYPE_MBR):
            raise ImageError(f"分区 {part.name}: partition-type 仅对MBR和混合分区表有效")
            
    
    def generate(self, image: Image) -> None:

        try:
            # 准备镜像文件
            prepare_image(image)

            
            # 确保扩展分区索引已设置
            self._ensure_extended_partition_index(image)

            # 写入分区数据
            for part in image.partitions:
                self._write_partition_data(image, part)
            
            # 写入分区表
            if self.priv.table_type & TYPE_GPT:
                self._write_gpt(image)
            elif self.priv.table_type & TYPE_MBR:
                self._write_mbr(image)

            # 写入TOC
            self._write_toc(image)

        except Exception as e:
            raise ImageError(f"生成镜像失败: {str(e)}")
    
    def _ensure_extended_partition_index(self, image: Image) -> None:
        """确保扩展分区索引已设置"""
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
        """设置逻辑分区和扩展分区"""
        if self.priv.extended_partition_index > 4:
            raise ImageError(f"无效的扩展分区索引({self.priv.extended_partition_index})，必须≤4")
        
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
                # 创建扩展分区
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
            
            # 校验强制主分区位置
            if part.forced_primary:
                if not found_extended:
                    raise ImageError(f"分区 {part.name}: forced-primary 只能用于扩展分区之后的分区")
            elif not in_extended and found_extended:
                raise ImageError(f"在强制主分区后不能创建非主分区 {part.name}")
            
            if mbr_entries > 4:
                raise ImageError("主分区数量过多（最多4个）")
    
    def _calculate_partition_offsets(self, image: Image) -> None:
        """计算分区偏移和大小"""
        now = 0
        gpt_backup = None
        self.priv.file_size = 0
        
        # 为分区表预留空间
        if self.priv.table_type != TYPE_NONE:
            # MBR分区表
            mbr = Partition(name="[MBR]",parent_image=image.name, offset=512 - 72, size=72, in_partition_table=False)
            image.partitions.append(mbr)
            now = mbr.offset + mbr.size
            
            # GPT分区表
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
                
                # GPT备份分区
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

        # 处理TOC
        if self.priv.toc_enable:
            self._setup_toc_partitions(image)

        # 处理自动调整分区
        self._setup_autoresize_partitions(image)
        
        # 计算每个分区的偏移和大小
        for part in image.partitions:
            
            # 设置分区对齐
            if not part.align:
                part.align = self.priv.align if (part.in_partition_table or 
                                                  self.priv.table_type == TYPE_NONE) else 1
            # 检查对齐
            if part.in_partition_table and ((part.align % self.priv.align) != 0):
                raise ImageError(f"分区 {part.name} 的对齐({part.align})必须是镜像对齐({self.priv.align})的倍数")
            
            self._parse_partition_config(image, part)

            if not part.size:
                image_path = next((dep['image_path'] for dep in image.dependencies 
                    if dep.get('image') == part.image), None)
                if not image_path or not os.path.exists(image_path):
                    raise ImageError(f"Subimage not found: {part.image}")

                child_size = os.path.getsize(image_path)
                part.size = self._roundup(child_size, part.align) if part.in_partition_table else child_size
      
            # 逻辑分区预留EBR空间
            if part.logical:
                now += self.priv.align
                now = self._roundup(now, part.align)

            if part == gpt_backup and 0 == part.offset:
                now += part.size
                part.offset = _roundup(now, 4096) - part.size

            # 设置偏移
            if not part.offset and (part.in_partition_table or self.priv.table_type == TYPE_NONE):
                part.offset = self._roundup(now, part.align)
            
            # 检查偏移是否符合对齐要求
            if part.offset % part.align != 0:
                raise ImageError(f"分区 {part.name} 偏移({part.offset})必须是{part.align}字节的倍数")
            
            # 确保分区大小有效
            if not part.size and part != self.priv.extended_partition:
                raise ImageError(f"分区 {part.name} 大小不能为零")
            
            # 检查分区重叠
            if not part.logical and self._check_overlap(image, part):
                raise ImageError(f"分区 {part.name} 与之前的分区重叠")

            # 检查分区大小是否为512字节倍数
            if part.in_partition_table and part.size % 512 != 0:
                raise ImageError(f"分区 {part.name} 大小({part.size})必须是512字节的倍数")
            
            # 更新当前位置
            if part.offset + part.size > now:
                now = part.offset + part.size

            # 更新文件大小
            if part.image:
                child_size = self._get_child_image_size(image, part.image)
                if part.offset + child_size > self.priv.file_size:
                    self.priv.file_size = part.offset + child_size

            # 更新扩展分区大小
            if part.logical :
                file_size = part.offset - self.priv.align + 512
                if file_size > self.priv.file_size:
                    self.priv.file_size = file_size

                self.priv.extended_partition.size = now - self.priv.extended_partition.offset
                
        # 确保镜像大小足够
        if not image.size:
            image.size = now
        
        print(f"image size: {image.size},now size: {now}")
        if now > image.size:
            raise ImageError("分区大小超过镜像大小")
        
        # 最终文件大小确定
        if self.priv.fill or ((self.priv.table_type & TYPE_GPT) and not self.priv.gpt_no_backup):
            self.priv.file_size = image.size
            print(f"update file size: {self.priv.file_size}")

    
    def _setup_autoresize_partitions(self, image: Image) -> None:
        """处理自动调整大小的分区"""
        resized = False
        for part in image.partitions:
            if not part.autoresize:
                continue
            
            if resized:
                raise ImageError("仅支持一个自动调整大小的分区")
            if image.size == 0:
                raise ImageError("使用自动调整分区时必须指定镜像大小")
            
            # 计算可用空间
            partsize = image.size - part.offset
            if self.priv.table_type & TYPE_GPT:
                partsize -= GPT_SECTORS * 512  # 减去GPT备份区域
            
            # 对齐调整
            partsize = self._rounddown(partsize, part.align or self.priv.align)
            
            if partsize <= 0:
                raise ImageError("分区超出设备大小")
            if partsize < part.size:
                raise ImageError(f"自动调整分区 {part.name} 大小({partsize})小于最小值({part.size})")
            
            part.size = partsize
            resized = True

    
    def _check_overlap(self, image: Image, part: Partition) -> bool:
        """检查分区是否重叠"""
        for other in image.partitions:
            if part == other:
                return False
            
            print(f"check overlap {part.name} {other.name}")
            # 检查是否完全不重叠
            if part.offset >= other.offset + other.size:
                continue
            if other.offset >= part.offset + part.size:
                continue
            
            # 检查是否有覆盖的空洞
            start = max(part.offset, other.offset)
            end = min(part.offset + part.size, other.offset + other.size)
            
            if self._image_has_hole_covering(image, other.image, start - other.offset, end - other.offset):
                continue
            
            # 发现重叠
            raise ImageError(
                f"分区 {part.name} (偏移 0x{part.offset:x}, 大小 0x{part.size:x}) "
                f"与之前的分区 {other.name} (偏移 0x{other.offset:x}, 大小 0x{other.size:x}) 重叠"
            )
        return False
    
    def _image_has_hole_covering(self, image: Image, child_name: str, start: int, end: int) -> bool:
        """检查子镜像是否有覆盖指定范围的空洞"""
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
        """获取子镜像大小"""
        for dep in image.partitions:
            if dep.name == child_name:
                return dep.size
        return 0
    
    def _write_partition_data(self, image: Image, part: Partition) -> None:
        """写入分区数据"""
        if not part.image:
            return
                
        child_size = 0
        image_path = ''

        # 查找子镜像
        for dep in image.dependencies:
            if dep.get('image') == part.image:
                image_path = dep.get('image_path')
                print(f"dep: {dep.get('image')}, {dep.get('image_path')}")
                break
            
        if os.path.exists(image_path):
            child_size = os.path.getsize(image_path)
        else:
            raise ImageError(f"找不到子镜像: {part.image}")

        # 检查子镜像大小
        if child_size > part.size:
            raise ImageError(f"分区 {part.name} 大小({part.size})小于子镜像 {part.image} 大小({child_size})")

        insert_data(image, image_path, part.size , part.offset, bytes(0))
    
    def _lba_to_chs(self, lba: int, chs: List[int]) -> None:
        """将LBA转换为CHS地址"""
        hpc = 255  # 每柱面磁头数
        spt = 63   # 每磁道扇区数
        s = lba % spt
        c = lba // spt
        h = c % hpc
        c = c // hpc
        
        chs[0] = h
        chs[1] = ((c & 0x300) >> 2) | (s + 1 if s != 0 else 0)
        chs[2] = c & 0xFF
    
    def _write_mbr(self, image: Image) -> None:
        """写入MBR分区表"""
        # 创建MBR结构
        mbr_data = bytearray(72)
        
        # 写入磁盘签名
        struct.pack_into('<I', mbr_data, 0, self.priv.disksig)
        
        # 写入分区表项
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
        
        # 处理混合分区表
        if self.priv.table_type == TYPE_HYBRID and i < 4:
            self._write_hybrid_mbr_entry(mbr_data, entry_offset)
        
        # 写入引导签名
        mbr_data[70] = 0x55
        mbr_data[71] = 0xAA
        
        # 写入MBR到镜像
        print("write mbr")
        with open(image.outfile, 'r+b') as f:
            f.seek(440)
            f.write(mbr_data)
        
        # 处理逻辑分区的EBR
        self._write_ebrs(image)
    
    def _write_mbr_partition_entry(self, mbr_data: bytearray, offset: int, part: Partition) -> None:
        """写入MBR分区表项"""
        entry = MbrPartitionEntry(
            boot=0x80 if part.bootable else 0x00,
            partition_type=part.partition_type,
            relative_sectors=int(part.offset / 512),
            total_sectors=int(part.size / 512)
        )
        
        # 计算CHS地址
        self._lba_to_chs(entry.relative_sectors, entry.first_chs)
        self._lba_to_chs(entry.relative_sectors + entry.total_sectors - 1, entry.last_chs)
        
        # 写入分区表项
        mbr_data[offset] = entry.boot
        mbr_data[offset+1:offset+4] = bytes(entry.first_chs)
        mbr_data[offset+4] = parse_size(entry.partition_type)
        mbr_data[offset+5:offset+8] = bytes(entry.last_chs)
        struct.pack_into('<I', mbr_data, offset+8, entry.relative_sectors)
        struct.pack_into('<I', mbr_data, offset+12, entry.total_sectors)
    
    def _write_hybrid_mbr_entry(self, mbr_data: bytearray, offset: int) -> None:
        """写入混合分区表的特殊项"""
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
        """写入扩展引导记录(EBR)"""
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
            
            # 第一个表项: 当前逻辑分区
            self._write_ebr_current_entry(ebr_data, part, extended_part)
            
            # 第二个表项: 下一个EBR
            if prev_part is not None:
                self._write_ebr_next_entry(ebr_data, part, extended_part)
            
            # 写入引导签名
            ebr_data[510] = 0x55
            ebr_data[511] = 0xAA
            
            # 写入EBR到镜像
            with open(image.outfile, 'r+b') as f:
                f.seek(ebr_offset)
                f.write(ebr_data)
                
            prev_part = part
    
    def _write_ebr_current_entry(self, ebr_data: bytearray, part: Partition, extended_part: Partition) -> None:
        """写入EBR中的当前分区表项"""
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
        
        # 写入第一个表项
        ebr_data[0] = entry1.boot
        ebr_data[1:4] = bytes(entry1.first_chs)
        ebr_data[4] = entry1.partition_type
        ebr_data[5:8] = bytes(entry1.last_chs)
        struct.pack_into('<I', ebr_data, 8, entry1.relative_sectors)
        struct.pack_into('<I', ebr_data, 12, entry1.total_sectors)
    
    def _write_ebr_next_entry(self, ebr_data: bytearray, part: Partition, extended_part: Partition) -> None:
        """写入EBR中的下一个分区表项"""
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
        
        # 写入第二个表项
        ebr_data[16] = entry2.boot
        ebr_data[17:20] = bytes(entry2.first_chs)
        ebr_data[20] = entry2.partition_type
        ebr_data[21:24] = bytes(entry2.last_chs)
        struct.pack_into('<I', ebr_data, 24, entry2.relative_sectors)
        struct.pack_into('<I', ebr_data, 28, entry2.total_sectors)
    
    def _write_gpt(self, image: Image) -> None:
        """写入GPT分区表"""
        # 创建GPT头部
        header = GptHeader()
        header.disk_uuid = uuid.UUID(self.priv.disk_uuid).bytes
        header.backup_lba = (image.size // 512) - 1 if not self.priv.gpt_no_backup else 1
        header.last_usable_lba = (image.size // 512) - 1 - GPT_SECTORS
        header.starting_lba = self.priv.gpt_location // 512
        
        # 收集分区信息
        gpt_entries, smallest_offset = self._collect_gpt_entries(image)
        
        # 设置第一个可用LBA
        if smallest_offset is None:
            smallest_offset = self.priv.gpt_location + (GPT_SECTORS - 1) * 512
        header.first_usable_lba = smallest_offset // 512
        
        # 构建分区表
        table_data = self._build_gpt_table(gpt_entries)
        
        # 计算分区表CRC
        header.table_crc = zlib.crc32(table_data) & 0xFFFFFFFF
        
        # 计算头部CRC并写入
        header_bytes = self._build_gpt_header(header)
        
        # 写入主GPT头部和分区表
        print("write gpt")
        with open(image.outfile, 'r+b') as f:
            f.seek(512)
            f.write(header_bytes)
            f.seek(self.priv.gpt_location)
            f.write(table_data)
        
        # 写入备份GPT
        if not self.priv.gpt_no_backup:
            self._write_gpt_backup(image, header, table_data)
        
        # 写入保护性MBR或混合MBR
        if self.priv.table_type == TYPE_HYBRID:
            self._write_mbr(image)
        else:
            self._write_protective_mbr(image)
    
    def _collect_gpt_entries(self, image: Image) -> Tuple[List[GptPartitionEntry], Optional[int]]:
        """收集GPT分区表项信息"""
        gpt_entries = []
        smallest_offset = None
        
        for part in image.partitions:
            if not part.in_partition_table:
                continue
                
            entry = self._create_gpt_entry(part)
            gpt_entries.append(entry)
            
            # 跟踪最小偏移
            if smallest_offset is None or part.offset < smallest_offset:
                smallest_offset = part.offset
                
        return gpt_entries, smallest_offset
    
    def _create_gpt_entry(self, part: Partition) -> GptPartitionEntry:
        """创建单个GPT分区表项"""
        entry = GptPartitionEntry()
        
        # 设置分区类型UUID
        if part.partition_type_uuid:
            try:
                entry.type_uuid = uuid.UUID(part.partition_type_uuid).bytes
            except ValueError:
                # 尝试查找类型别名
                type_uuid = self._get_gpt_partition_type(part.partition_type_uuid)
                if type_uuid:
                    entry.type_uuid = uuid.UUID(type_uuid).bytes
                else:
                    raise ImageError(f"分区 {part.name} 有无效的类型: {part.partition_type_uuid}")
        else:
            entry.type_uuid = self._get_gpt_partition_type('L').bytes
        
        # 设置分区UUID
        if part.partition_uuid:
            try:
                entry.uuid = uuid.UUID(part.partition_uuid).bytes
            except ValueError:
                raise ImageError(f"分区 {part.name} 有无效的UUID: {part.partition_uuid}")
        else:
            entry.uuid = uuid.uuid4().bytes
        
        # 设置LBA范围
        entry.first_lba = part.offset // 512
        entry.last_lba = (part.offset + part.size) // 512 - 1
        
        # 设置标志
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
        
        # 设置名称
        for i, c in enumerate(part.name[:36]):
            entry.name[i] = ord(c)
            
        return entry
    
    def _build_gpt_table(self, gpt_entries: List[GptPartitionEntry]) -> bytearray:
        """构建GPT分区表数据"""
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
        
        # 重新计算头部CRC
        header.header_crc = zlib.crc32(header_bytes) & 0xFFFFFFFF
        struct.pack_into('<I', header_bytes, 16, header.header_crc)
        
        return header_bytes

    def _write_gpt_backup(self, image: Image, header: GptHeader, table_data: bytearray) -> None:
        """写入GPT备份分区表"""
        # 备份头部
        backup_header = self._build_gpt_header(header)
        
        # 更新备份头部的LBA信息
        backup_current_lba = header.backup_lba
        backup_backup_lba = 1
        struct.pack_into('<Q', backup_header, 24, backup_current_lba)
        struct.pack_into('<Q', backup_header, 32, backup_backup_lba)
        struct.pack_into('<Q', backup_header, 72, image.size//512 - GPT_SECTORS)
        
        # 重新计算备份头部CRC
        struct.pack_into('<I', backup_header, 16, 0)  # 清零旧CRC
        backup_header_crc = zlib.crc32(backup_header) & 0xFFFFFFFF
        struct.pack_into('<I', backup_header, 16, backup_header_crc)
        
        # 写入备份分区表和头部
        with open(image.outfile, 'r+b') as f:
            f.seek(image.size - GPT_SECTORS * 512)
            f.write(table_data)
            f.seek(image.size - 512)
            f.write(backup_header)
    
    def _get_gpt_partition_type(self, shortcut: str) -> Optional[str]:
        """查找GPT分区类型UUID"""
        return GPT_PARTITION_TYPES.get(shortcut.upper())
    
    def _setup_toc_partitions(self, image: Image) -> None:
        """设置TOC分区"""
        if not self.priv.toc_enable:
            return

        toc_entries = []
        index_count = 0

        # 为每个分区创建TOC条目
        for part in image.partitions:
            if part.name.startswith('['):  # 跳过内部分区
                continue

            toc_entry = TocInsertData()
            toc_entry.partition_name = part.name[:31]  # 限制名称长度
            toc_entry.load = 1 if part.load else 0
            toc_entry.boot = part.boot
            toc_entry.partition_offset = part.offset if part.offset else 0
            toc_entry.partition_size = part.size if part.size else 0
            
            toc_entries.append(toc_entry)
            index_count += 1

        if index_count > 0:
            self.priv.toc_num = index_count
            
            # 创建TOC分区
            toc_size = 64 * index_count  # 每个TOC条目64字节
            toc_partition = Partition(
                name="[TOC]",
                parent_image=image.name,
                offset=self.priv.toc_offset if self.priv.toc_offset else 0,
                size=toc_size,
                in_partition_table=False
            )
            image.partitions.append(toc_partition)
            
            print(f"TOC Partition: {toc_partition.name} (offset 0x{toc_partition.offset:x}, size 0x{toc_partition.size:x})")
            
            # 存储TOC数据供后续写入
            image.handler_config['toc_entries'] = toc_entries

    @staticmethod
    def _safe_to_int(value):
        if isinstance(value, str):
            value = value.strip().lower()
            if value.startswith('0x'):
                return int(value, 16) # 转换为十六进制
            return int(value, 10) # 转换为十进制
        return int(value) if value is not None else 0

    def _write_toc(self, image: Image) -> None:
        """写入TOC数据"""
        if not self.priv.toc_enable or not self.priv.toc_num:
            return
            
        toc_entries = image.handler_config.get('toc_entries', [])
        if not toc_entries:
            return

        print("writing TOC")
        
        # 构建TOC数据
        toc_data = bytearray(self.priv.toc_num * 64)

        for i, toc_entry in enumerate(toc_entries):
            offset = i * 64

            # 写入分区名称 (32字节)
            name_bytes = toc_entry.partition_name.encode('utf-8')[:31]
            toc_data[offset:offset+32] = name_bytes.ljust(32, b'\x00')

            # 写入分区偏移 (8字节，小端)
            # 确保 partition_offset 是整数
            offset_val = self._safe_to_int(toc_entry.partition_offset)
            struct.pack_into('<Q', toc_data, offset + 32, offset_val)

            # 写入分区大小 (8字节，小端)
            # 确保 partition_size 是整数
            size_val = self._safe_to_int(toc_entry.partition_size)
            struct.pack_into('<Q', toc_data, offset + 40, size_val)

            # 写入标志 (2字节)
            # 确保 load 和 boot 都是整数，load 字段在 _setup_toc_partitions 中已被清理，但为安全起见也使用 safe_to_int
            load_val = self._safe_to_int(toc_entry.load)
            boot_val = self._safe_to_int(toc_entry.boot) # <--- CRITICAL FIX: 转换 boot 字段

            # bytearray 赋值需要整数 (0-255)
            toc_data[offset + 48] = load_val
            toc_data[offset + 49] = boot_val 

            # 填充剩余14字节
            toc_data[offset + 50:offset + 64] = b'\x00' * 14

        # 写入TOC到镜像
        toc_offset = self.priv.toc_offset if self.priv.toc_offset else 0
        with open(image.outfile, 'r+b') as f:
            f.seek(toc_offset)
            f.write(toc_data)

        print(f"TOC written at offset 0x{toc_offset:x}, size {len(toc_data)} bytes")

    def _write_protective_mbr(self, image: Image) -> None:
        """写入保护性MBR"""
        mbr_data = bytearray(72)
        
        # 写入磁盘签名
        struct.pack_into('<I', mbr_data, 0 , self.priv.disksig)
        
        # 保护性分区表项
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
        
        # 引导签名
        mbr_data[70] = 0x55
        mbr_data[71] = 0xAA
        
        with open(image.outfile, 'r+b') as f:
            f.seek(440)
            f.write(mbr_data)

    def run(self, image: Image, config: Dict[str, Any]) -> None:
        self.setup(image, config)
        self.generate(image)
