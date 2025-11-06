#!/usr/bin/env python3
import os
import struct
from typing import Dict, List, Optional, Any
from .common import ImageHandler, Image, ImageError, run_command, Partition, prepare_image, mountpath, get_tool_path

class VFatHandler(ImageHandler):
    """VFAT 文件系统处理器"""
    type = "vfat"
    opts = ["extraargs", "label", "files", "minimize"]

    def __init__(self):
        self.config = {}

    def setup(self, image: Image, config: Dict[str, str]) -> None:
        self.config = config
        # 检查镜像大小
        if not image.size:
            raise ImageError("未设置镜像大小或大小为零")

        label = config.get("label", "")
        if label and len(label) > 11:
            raise ImageError("vfat 卷标不能超过 11 个字符")

    def generate(self, image: Image) -> None:
        # 准备镜像文件
        prepare_image(image)

        # 获取配置参数
        extraargs = self.config.get("extraargs", "")
        label = self.config.get("label", "")
        minimize = self.config.get("minimize", False)

        # 构建标签参数
        label_arg = f"-n {label}" if label else ""

        # 执行 mkdosfs 创建 vfat 文件系统
        cmd = [get_tool_path("mkdosfs"), *extraargs.split(), *label_arg.split(), image.outfile]
        # 过滤空字符串参数
        cmd = [arg for arg in cmd if arg]
        run_command(cmd)

        # 处理分区中的文件
        for part in image.partitions:
            child_image = self._get_child_image(image, part.image)
            if not child_image:
                raise ImageError(f"找不到子镜像: {part.image}")

            src_path = child_image.outfile
            target = part.name or os.path.basename(src_path)

            # 创建目标目录（如果有子目录）
            if '/' in target:
                dir_path = os.path.dirname(target)
                mmd_cmd = [get_tool_path("mmd"), "-DsS", "-i", image.outfile, f"::{dir_path}"]
                env = os.environ.copy()
                env["MTOOLS_SKIP_CHECK"] = "1"
                run_command(mmd_cmd, env=env)

            # 复制文件到 vfat 镜像
            mcopy_cmd = [get_tool_path("mcopy"), "-sp", "-i", image.outfile, src_path, f"::{target}"]
            env = os.environ.copy()
            env["MTOOLS_SKIP_CHECK"] = "1"
            run_command(mcopy_cmd, env=env)

        # 如果不是空镜像且没有分区，复制 mountpath 中的文件
        if not image.empty and not image.partitions:
            files = os.listdir(mountpath(image))
            if files:
                for file in files:
                    mcopy_cmd = [get_tool_path("mcopy"), "-sp", "-i", image.outfile, f"{mountpath(image)}/{file}", "::"]
                    env = os.environ.copy()
                    env["MTOOLS_SKIP_CHECK"] = "1"
                    run_command(mcopy_cmd, env=env)

        # 处理镜像最小化
        if minimize:
            last_pos = self._find_last_valid_pos(image)
            if last_pos <= 0:
                raise ImageError("无法找到有效的文件系统位置，最小化失败")

            # 获取当前文件大小
            current_size = os.stat(image.outfile).st_size

            # 截断文件到最小必要大小
            if last_pos < current_size:
                with open(image.outfile, 'r+b') as f:
                    f.truncate(last_pos)
                image.size = last_pos
                print(f"minimize image size to {last_pos} bytes 0x{last_pos:0x}")


    def _find_last_valid_pos(self, image: Image) -> int:
        """查找最后一个有效簇的位置，用于最小化镜像"""
        try:
            with open(image.outfile, 'rb') as f:
                # 读取引导扇区信息
                f.seek(11)
                bytes_per_sector = struct.unpack('<H', f.read(2))[0]
                f.seek(13)
                sectors_per_cluster = f.read(1)[0]
                f.seek(14)
                reserved_sectors = struct.unpack('<H', f.read(2))[0]
                f.seek(16)
                num_fats = f.read(1)[0]
                f.seek(32)
                total_sectors = struct.unpack('<I', f.read(4))[0]
                f.seek(36)
                sectors_per_fat = struct.unpack('<I', f.read(4))[0]

                # 计算关键偏移量
                fat_offset = reserved_sectors * bytes_per_sector
                fat_size_bytes = sectors_per_fat * bytes_per_sector
                data_region_offset = (reserved_sectors + num_fats * sectors_per_fat) * bytes_per_sector
                cluster_size_bytes = sectors_per_cluster * bytes_per_sector

                # FAT 表项数量
                num_entries = fat_size_bytes // 4
                last_used_cluster = 0

                # 遍历 FAT 表查找最后一个使用的簇（从簇 2 开始）
                for cluster in range(2, num_entries):
                    f.seek(fat_offset + cluster * 4)
                    fat_entry = struct.unpack('<I', f.read(4))[0] & 0x0FFFFFFF  # 掩码获取低 28 位

                    # 有效的簇值范围：0x00000001 - 0x0FFFFFF7
                    if 0x00000001 <= fat_entry <= 0x0FFFFFF7:
                        last_used_cluster = cluster

                if last_used_cluster == 0:
                    return -1

                # 计算最后一个簇的结束位置
                return data_region_offset + last_used_cluster * cluster_size_bytes
        except Exception as e:
            raise ImageError(f"查找最后有效位置失败: {str(e)}")

    def _get_child_image(self, parent_image: Image, name: str) -> Optional[Image]:
        for dep in parent_image.dependencies:
            if dep.name == name:
                return dep
        return None

    def run(self, image: Image, config: Dict[str, Any]):
        self.setup(image, config)
        self.generate(image)
