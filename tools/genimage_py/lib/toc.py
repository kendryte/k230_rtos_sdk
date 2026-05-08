import struct
from dataclasses import dataclass
import os
from typing import List, Optional

TOC_ENTRY_ALIGN = (64)

@dataclass
class TocInsertData:
    """TOC insert data structure"""
    partition_name: str = ""
    partition_offset: int = 0
    partition_size: int = 0
    load: int = 0
    boot: int = 0

    def to_bytes(self) -> bytes:
        """Convert the data structure to a byte array"""
        fmt = "<32sQQBB"

        name_bytes = self.partition_name.encode("utf-8")[:31].ljust(32, b'\x00')
        data = struct.pack(
            fmt,
            name_bytes,
            self.partition_offset,
            self.partition_size,
            self.load,
            self.boot,
            )

        return data.ljust(TOC_ENTRY_ALIGN, b'\x00')

class Toc:
    def __init__(self, toc_offset: int):
        self.entries_num : int = 0
        self.toc_offset : int = toc_offset if toc_offset else 0
        self.toc_entries : List[TocInsertData] = []

    def add_toc_entry(self, toc_entry: TocInsertData) -> None:
        """add toc entry"""
        if not isinstance(toc_entry, TocInsertData):
            raise TypeError("Invalid TOC entry type!")

        self.toc_entries.append(toc_entry)
        self.entries_num += 1

    def get_toc_data(self) -> bytes:
        """get toc data"""
        if not self.entries_num:
            raise ValueError("No TOC entries!")

        toc_data = bytearray()

        for entry in self.toc_entries:
            toc_data += entry.to_bytes()

        return toc_data
