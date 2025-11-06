#!/usr/bin/env python3
import os
import sys
import subprocess
import tempfile
import shutil
from dataclasses import dataclass
from typing import Optional
from typing import List, Dict, Optional, Any, Callable

class ImageError(Exception):
    """镜像处理相关错误"""
    pass

@dataclass
class TocInsertData:
    """TOC插入数据结构"""
    partition_name: str = ""
    partition_offset: int = 0
    partition_size: int = 0
    load: bool = False
    boot: bool = False

@dataclass
class Partition:
    """分区信息类"""
    name: str
    parent_image: str  # 所属镜像名称
    in_partition_table: bool = True
    offset: int = 0
    size: Optional[int] = None
    image: Optional[str] = None  # 引用的镜像文件
    partition_type: Optional[str] = None  # 分区类型
    partition_type_uuid: Optional[str] = None  # GPT分区类型UUID
    partition_uuid: Optional[str] = None  # 分区UUID
    bootable: bool = False
    read_only: bool = False
    hidden: bool = False
    autoresize: bool = False
    fill: bool = False
    logical: bool = False
    align: Optional[int] = None
    forced_primary: bool = False
    erase_size : int = 0
    flag: Optional[str] = None
    load: bool = False  # TOC load flag
    boot: int = 0  # TOC boot flag
    # 其他可能的属性
    extraargs: Optional[str] = None

@dataclass
class Flash_type:
    name: str
    pebsize: int = 0
    lebsize: int = 0
    numpebs: int = 0
    minimum_io_unit_size: int = 0
    vid_header_offset: int = 0
    sub_page_size: int = 0

    is_uffs: bool = False
    page_size: int = 0
    block_pages: int = 0
    total_blocks: int = 0
    spare_size: int = 0
    status_offset: int = 0
    ecc_option: int = 0
    ecc_size: int = 0

    
@dataclass
class Image:
    """镜像文件信息类"""
    name: str = None
    file: str = None
    image_type: str = None  # 如hdimage, vfat, ext4等
    size: Optional[int] = None
    size_str: Optional[str] = None  # 原始大小字符串（带单位）
    temporary: bool = False  # 是否为临时文件
    mountpoint: Optional[str] = None
    mountpath: Optional[str] = None
    exec_pre: Optional[str] = None
    exec_post: Optional[str] = None
    partitions: List[Partition] = None  # 分区列表
    empty: bool = False  # 是否为空镜像
    outfile: str = ""
    holes: List[int] = None  # 空洞列表
    handler: Any = None  # 关联的处理器
    handler_config: Dict[str, Any] = None  # 处理器配置
    done: bool = False
    flash_type : Flash_type = None  # 镜像类型
    dependencies: List[Any] = None  # 依赖的镜像列表
    
    def __post_init__(self):
        if self.partitions is None:
            self.partitions = []
        if self.dependencies is None:
            self.dependencies = []
        if self.handler_config is None:
            self.handler_config = {}

class ImageHandler:
    """镜像处理器基类"""
    type: str = ""
    opts: List[str] = []
    
    def generate(self, image: Image):
        """生成镜像文件"""
        pass
    
    def setup(self, image: Image, config: Dict[str, Any]):
        """设置镜像参数"""
        pass

    def run(self,image: Image, config: Dict[str, str]):
        """执行镜像处理"""
        raise NotImplementedError("子类必须实现run方法")

def insert_data(image: Image, image_path: str, size: int, offset: int, padding_byte: bytes) -> None:
    try:
        if not os.path.exists(image_path):
            raise ImageError(f"error: {image_path} not exist")

        with open(image.outfile, 'r+b') as f_out:
            f_out.seek(offset)
            file_size = os.path.getsize(image_path)  # 获取源文件大小
            print(f"insert data: {image_path} to {image.outfile} at {offset} size {file_size}")
            with open(image_path, 'rb') as f_in:
                chunk_size = 4 * 1024 * 1024  # 4MB块
                remaining = file_size
                while remaining > 0:
                    chunk = f_in.read(min(chunk_size, remaining))
                    if not chunk:
                        break
                    f_out.write(chunk)
                    remaining -= len(chunk)
            
            if (pad_size := size - file_size) > 0:
                f_out.write(padding_byte * pad_size)
                print(f"write padding: {pad_size} bytes")
    except IOError as e:
        raise ImageError(f"写入文件失败: {str(e)}")


def mountpath(image: Image) -> str:
    """获取镜像的挂载点"""
    if image.mountpath:
        return image.mountpath
    elif image.mountpoint:
        return image.mountpoint
    else:
        return None


def run_command(cmd: List[str], env: Optional[Dict[str, str]] = None) -> int:
    """运行外部命令并返回结果"""
    try:
        print(f"run: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=env
        )
        return 0
    except subprocess.CalledProcessError as e:
        print(f"命令执行失败: {e.output}", file=sys.stderr)
        return e.returncode

def parse_size(size_str: str) -> int:
    """解析带单位的大小字符串"""
    if not size_str:
        return 0
        
    size_str = size_str.strip().lower()
    suffixes = {
        'k': 1024,
        'm': 1024 * 1024,
        'g': 1024 * 1024 * 1024,
        't': 1024 * 1024 * 1024 * 1024
    }
    
    # 处理十六进制
    if size_str.startswith('0x'):
        try:
            num = int(size_str, 16)
            return num
        except ValueError:
            raise ImageError(f"无效的十六进制大小格式: {size_str}")
    
    # 提取数字和单位
    num_str = ''
    suffix = ''
    for c in size_str:
        if c.isdigit() or c == '.':
            num_str += c
        else:
            suffix = c
            break
    
    if not num_str:
        raise ImageError(f"无效的大小格式: {size_str}")
    
    try:
        num = float(num_str)
    except ValueError:
        raise ImageError(f"无效的大小格式: {size_str}")
    
    # 应用单位
    if suffix in suffixes:
        return int(num * suffixes[suffix])
    else:
        # 没有单位，默认字节
        return int(num)

def get_tool_path(tool_name: str, bin_dir: Optional[str] = None) -> str:
    """
    获取工具路径，优先从指定的bin目录查找，然后从系统PATH查找。
    增加了对不同操作系统的支持，特别是 Windows 下的可执行文件扩展名。

    Args:
        tool_name: 工具名称。
        bin_dir: 本地工具目录，默认为当前脚本所在目录的 'bin' 子目录。

    Returns:
        找到的工具的绝对路径，如果找不到，则返回工具名称本身。
    """
    # 1. 确定本地 bin 目录
    if bin_dir is None:
        # 获取当前脚本所在目录的bin子目录
        # 注意：os.path.abspath(__file__) 仅在作为文件运行时有效
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
        except NameError:
            # 兼容交互式环境或非主脚本调用
            current_dir = os.getcwd()

        bin_dir = os.path.join(current_dir, 'bin')

    # 定义在不同操作系统上可能的可执行文件扩展名
    if os.name == 'nt':
        # Windows 系统：检查常见扩展名
        executable_suffixes = ['', '.exe', '.cmd', '.bat']
    else:
        # POSIX 系统 (Linux, macOS, etc.)：通常没有扩展名
        executable_suffixes = ['']

    # 2. 首先检查bin目录
    for suffix in executable_suffixes:
        bin_tool = os.path.join(bin_dir, tool_name + suffix)

        # 检查文件是否存在且可执行
        if os.path.exists(bin_tool) and os.access(bin_tool, os.X_OK):
            return bin_tool

    # 3. 如果bin目录没有，检查系统PATH
    # 使用 shutil.which 替代手动遍历 PATH，它能自动处理 OS 相关的逻辑
    system_tool = shutil.which(tool_name)
    if system_tool:
        # shutil.which 返回的是绝对路径
        return system_tool

    # 4. 如果都找不到，返回工具名称（让系统在运行时处理）
    return tool_name

def prepare_image(image: Image, size = 0) -> int:
    """准备镜像文件（创建指定大小的空文件）"""
    try:
        # path creat
        if not os.path.exists(os.path.dirname(image.outfile)):
            os.makedirs(os.path.dirname(image.outfile), exist_ok=True)
        with open(image.outfile, 'wb') as f:
            if not size:
                size = image.size
            if size:
                print(f"准备镜像文件 {image.outfile} 大小 {size} 字节")
                f.seek(size - 1)
                f.write(b'\x00')
        return 0
    except IOError as e:
        raise ImageError(f"无法创建镜像文件 {image.outfile}: {str(e)}")
