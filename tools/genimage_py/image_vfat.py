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
        """
        查找最后一个有效簇的位置，用于最小化镜像。
        增加 VFAT (FAT16/FAT32) 兼容性检查和腐败 FAT 字段的健壮性处理，
        并修正 FAT16 簇的有效性判断逻辑。
        """
        try:
            with open(image.outfile, 'rb') as f:
                current_file_size = os.fstat(f.fileno()).st_size
                
                # --- 读取引导扇区关键字段 ---
                f.seek(11); bytes_per_sector = struct.unpack('<H', f.read(2))[0]
                f.seek(13); sectors_per_cluster = struct.unpack('<B', f.read(1))[0] 
                f.seek(14); reserved_sectors = struct.unpack('<H', f.read(2))[0]
                f.seek(16); num_fats = struct.unpack('<B', f.read(1))[0] 
                f.seek(17); root_entry_count = struct.unpack('<H', f.read(2))[0]
                f.seek(19); total_sectors_16 = struct.unpack('<H', f.read(2))[0]
                f.seek(22); sectors_per_fat_16 = struct.unpack('<H', f.read(2))[0]
                f.seek(32); total_sectors_32 = struct.unpack('<I', f.read(4))[0]
                f.seek(36); sectors_per_fat_32 = struct.unpack('<I', f.read(4))[0]

                # --- 1. 确定 FAT 扇区大小 (Handle corrupt FAT32 field) ---
                sectors_per_fat = 0
                
                # 尝试使用 FAT32 字段
                if sectors_per_fat_32 != 0:
                    fat_size_bytes_32 = sectors_per_fat_32 * bytes_per_sector
                    total_fat_region_size_32 = reserved_sectors * bytes_per_sector + num_fats * fat_size_bytes_32
                    
                    # 如果 FAT32 计算的大小超过实际文件大小，说明该字段腐败，回退。
                    if total_fat_region_size_32 > current_file_size:
                        print("DEBUG: FAT32 sector count appears corrupt. Falling back to FAT16 field.")
                    else:
                        sectors_per_fat = sectors_per_fat_32

                # 如果 FAT32 字段无效或腐败，使用 FAT16 字段
                if sectors_per_fat == 0 and sectors_per_fat_16 != 0:
                    sectors_per_fat = sectors_per_fat_16

                if sectors_per_fat == 0:
                    raise ImageError(f"FAT sector count is zero or invalid.")

                # 使用确定的 sectors_per_fat 最终计算关键参数
                fat_size_bytes = sectors_per_fat * bytes_per_sector
                total_fat_region_size = reserved_sectors * bytes_per_sector + num_fats * fat_size_bytes
                
                if total_fat_region_size > current_file_size:
                    raise ImageError(f"Calculated total FAT region size ({total_fat_region_size}) exceeds image size ({current_file_size}). Cannot minimize.")
                
                # --- 2. 确定 FAT 类型 (FAT Type Detection) ---
                total_sectors = total_sectors_32 if total_sectors_32 != 0 else total_sectors_16
                if total_sectors == 0:
                    raise ImageError("Total sectors count is zero or invalid.")

                root_dir_sectors = (root_entry_count * 32 + bytes_per_sector - 1) // bytes_per_sector
                data_sectors = total_sectors - (reserved_sectors + num_fats * sectors_per_fat + root_dir_sectors)
                total_clusters = data_sectors // sectors_per_cluster if sectors_per_cluster != 0 else 0
                
                fat_type = "FAT32"
                entry_bytes = 4
                mask = 0x0FFFFFFF
                
                # FAT32 簇值判断：只要不是 0x00000000 (可用) 且 小于 0x0FFFFFF8 (链结束)，就是有效的。
                is_used = lambda entry: entry != 0x00000000 and entry < 0x0FFFFFF8
                
                if total_clusters < 4085:
                    # 理论上是 FAT12，但我们将其视为无法支持
                    raise ImageError("FAT12 not supported for minimization.")
                elif total_clusters < 65525:
                    # FAT16
                    fat_type = "FAT16"
                    entry_bytes = 2
                    mask = 0xFFFF
                    # FAT16 簇值判断：只要不是 0x0000 (可用) 或 0x0001 (保留) 
                    # 那么它就是已分配或已使用的簇，包括链结束标记 (0xFFF8-0xFFFF)。
                    is_used = lambda entry: entry >= 0x0002

                print(f"DEBUG: Detected FAT Type: {fat_type} (Total Clusters: {total_clusters})")

                # --- 3. 计算偏移量和迭代 (FAT Iteration) ---
                data_region_offset = total_fat_region_size
                cluster_size_bytes = sectors_per_cluster * bytes_per_sector
                fat_offset = reserved_sectors * bytes_per_sector
                
                num_entries = fat_size_bytes // entry_bytes 
                last_used_cluster = 0
                
                # 遍历 FAT 表查找最后一个使用的簇（从簇 2 开始）
                for cluster in range(2, num_entries):
                    read_offset = fat_offset + cluster * entry_bytes
                    
                    f.seek(read_offset) 
                    buffer = f.read(entry_bytes)
                    
                    if len(buffer) < entry_bytes:
                        break 
                    
                    # Unpack based on detected FAT type
                    if fat_type == "FAT16":
                        fat_entry = struct.unpack('<H', buffer)[0]
                    elif fat_type == "FAT32":
                        fat_entry = struct.unpack('<I', buffer)[0] & mask
                    
                    # Check for valid used cluster entry
                    if is_used(fat_entry):
                        last_used_cluster = cluster

                if last_used_cluster == 0:
                    return -1

                # 计算最后一个簇的结束位置
                final_offset = data_region_offset + (last_used_cluster + 1) * cluster_size_bytes
                print(f"DEBUG: Last used cluster: {last_used_cluster}")
                return final_offset
        except Exception as e:
            raise ImageError(f"查找最后有效位置失败: {type(e).__name__} - {str(e)}")
        
            
    def _get_child_image(self, parent_image: Image, name: str) -> Optional[Image]:
        for dep in parent_image.dependencies:
            if dep.name == name:
                return dep
        return None

    def run(self, image: Image, config: Dict[str, Any]):
        self.setup(image, config)
        self.generate(image)
