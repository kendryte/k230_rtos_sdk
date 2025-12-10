
import struct
import zlib
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple, Iterable


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

    def to_bytes(self) -> bytes:
        byte_data = bytearray(16)
        byte_data[0] = self.boot
        byte_data[1:4] = bytes(self.first_chs)
        byte_data[4] = self.partition_type
        byte_data[5:8] = bytes(self.last_chs)
        byte_data[8:12] = struct.pack('<I', self.relative_sectors)
        byte_data[12:16] = struct.pack('<I', self.total_sectors)
        return byte_data

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

    def to_bytes(self) -> bytes:
        entry_bytes = bytearray(128)
        entry_bytes[0:16] = self.type_uuid
        entry_bytes[16:32] = self.uuid
        struct.pack_into('<Q', entry_bytes, 32, self.first_lba)
        struct.pack_into('<Q', entry_bytes, 40, self.last_lba)
        struct.pack_into('<Q', entry_bytes, 48, self.flags)
        for i in range(36):
            struct.pack_into('H', entry_bytes, 56 + i * 2, self.name[i])
        return entry_bytes


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

    def to_bytes(self) -> bytes:
        header_bytes = bytearray(92)
        header_bytes[0:8] = self.signature
        struct.pack_into('<I', header_bytes, 8, self.revision)
        struct.pack_into('<I', header_bytes, 12, self.header_size)
        struct.pack_into('<I', header_bytes, 16, self.header_crc)
        struct.pack_into('<I', header_bytes, 20, self.reserved)
        struct.pack_into('<Q', header_bytes, 24, self.current_lba)
        struct.pack_into('<Q', header_bytes, 32, self.backup_lba)
        struct.pack_into('<Q', header_bytes, 40, self.first_usable_lba)
        struct.pack_into('<Q', header_bytes, 48, self.last_usable_lba)
        header_bytes[56:72] = self.disk_uuid
        struct.pack_into('<Q', header_bytes, 72, self.starting_lba)
        struct.pack_into('<I', header_bytes, 80, self.number_entries)
        struct.pack_into('<I', header_bytes, 84, self.entry_size)
        struct.pack_into('<I', header_bytes, 88, self.table_crc)

        self.header_crc = zlib.crc32(header_bytes) & 0xFFFFFFFF
        struct.pack_into('<I', header_bytes, 16, self.header_crc)

        return header_bytes

def get_gpt_partition_type(shortcut: str) -> Optional[str]:
    """Look up GPT partition type UUID"""
    return GPT_PARTITION_TYPES.get(shortcut.upper())
