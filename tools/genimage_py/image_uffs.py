#!/usr/bin/env python3
import os
import struct
from common import ImageHandler, Image, ImageError, run_command, prepare_image, mountpath, parse_size, get_tool_path
from typing import Dict, List, Optional

class UffsHandler(ImageHandler):
    """UFFS 文件系统处理器"""
    type = "uffs"
    opts = ["extraargs", "size"]

    def __init__(self):
        self.config = {}
        self.flash_type = {}
        self.priv = None

    def setup(self, image: Image, config: Dict[str, str]) -> None:
        self.config = config
        
        # 检查 flash 类型配置
        if not hasattr(image, 'flash_type') or not image.flash_type:
            raise ImageError("未指定 flash 类型")
        
        flash_type = image.flash_type
        if not getattr(flash_type, 'is_uffs', False):
            raise ImageError("指定的 flash 类型不是 uffs")
        
        # 检查必要的 flash 参数
        required_params = [
            'page_size', 
            'block_pages', 
            'total_blocks'
        ]
        for param in required_params:
            if not hasattr(flash_type, param) or getattr(flash_type, param) == 0:
                raise ImageError(f"flash 类型中 {param} 配置无效")
        
        # 检查 ECC 选项有效性
        if hasattr(flash_type, 'ecc_option') and flash_type.ecc_option > 3:
            raise ImageError("无效的 uffs flash ecc 选项")

    def parse(self, image: Image, config: Dict[str, str]) -> None:
        """解析配置中的文件和分区信息"""
        # 处理 files 列表
        files = config.get("files", [])
        if isinstance(files, str):
            files = [files]

        for file_path in files:
            image.partitions.append(Partition(name="", parent_image=image.name, image=file_path))

        # 处理分段配置
        file_sections = config.get("content", [])
        if not isinstance(file_sections, list):
            file_sections = [file_sections]

        for section in file_sections:
            if isinstance(section, dict):
                name = section.get("name")
                img = section.get("image")
                if name and img:
                    image.partitions.append(Partition(name=name, parent_image=image.name, image=img))

    def generate(self, image: Image) -> None:
        # 准备镜像文件
        prepare_image(image)

        # 获取配置参数
        extraargs = self.config.get("extraargs", "")
        size_str = self.config.get("size", "")
        part_size = parse_size(size_str)

        # 验证镜像大小对齐
        flash_type = image.flash_type
        block_size = flash_type.page_size * flash_type.block_pages
        if part_size % block_size != 0:
            raise ImageError(
                f"镜像大小 ({part_size}) 无效，必须对齐到 {block_size} 字节"
            )

        # 计算总块数
        total_blocks = part_size // block_size

        # 构建 ECC 选项参数
        ecc_opt = ["none", "soft", "hw", "auto"]
        ecc_option = flash_type.ecc_option if hasattr(flash_type, 'ecc_option') else 3  # 默认 auto
        if ecc_option < 0 or ecc_option >= len(ecc_opt):
            raise ImageError(f"无效的 ECC 选项: {ecc_option}")

        # 删除已存在的输出文件
        if os.path.exists(image.outfile):
            os.remove(image.outfile)

        # 构建 mkuffs 命令
        cmd = [
            get_tool_path("mkuffs"),
            "-f", image.outfile,
            "-p", str(flash_type.page_size),
            "-s", str(flash_type.spare_size),
            "-b", str(flash_type.block_pages),
            "-t", str(total_blocks),
            "-x", ecc_opt[ecc_option],
            "-o", "0",
            "-d", mountpath(image),
            *extraargs.split()
        ]
        # 过滤空参数
        cmd = [arg for arg in cmd if arg]

        # 执行命令
        run_command(cmd)

        # 更新镜像大小
        try:
            stat_info = os.stat(image.outfile)
            image.size = stat_info.st_size
        except OSError as e:
            raise ImageError(f"无法获取镜像文件信息: {str(e)}")


    def _get_child_image(self, parent_image: Image, name: str) -> Optional[Image]:
        """获取子镜像对象"""
        for dep in parent_image.dependencies:
            if dep.name == name:
                return dep
        return None

    def run(self, image: Image, config: Dict[str, str]):
        self.setup(image, config)
        self.parse(image, config)
        self.generate(image)

def get_handler() -> UffsHandler:
    return UffsHandler()
