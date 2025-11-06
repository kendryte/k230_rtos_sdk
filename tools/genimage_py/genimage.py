#!/usr/bin/env python3
import os
import sys
import argparse
import shutil
import tempfile
from typing import List, Dict, Optional, Any, Tuple
from common import (
    ImageError, Flash_type, Image, Partition, ImageHandler,
    run_command, parse_size
)

# image_type : type_handler
HANDLERS = {
    "vfat": "image_vfat",
    "hdimage": "image_hd",
    "kdimage": "image_kd",
    "uffs": "image_uffs"
}

# TODO: Add config file support of 'include'
#       Add dependenies image and sort

class GenImageTool:

    """Disk image generation tool main class"""
    def __init__(self, rootpath : str, outputpath : str, config_file : str):
        self.images: List[Image] = []

        self.rootpath: str = rootpath
        self.outputpath: str = outputpath
        self.config_file: str = config_file

        self.tmppath: str = str(tempfile.gettempdir())

        self.imagepath: str = ""
    
    def get_image_by_name(self, name: str) -> Optional[Image]:
        """Find image by name"""
        for image in self.images:
            if image.name == name or image.file == name:
                return image
        return None

    def parse_config(self) -> None:
        """Parse configuration file"""
        with open(self.config_file, 'r') as f:
            content = f.read()

        # Remove comments and empty lines
        lines = []
        for line in content.split('\n'):
            line = line.strip()
            # 分割行，保留#前的部分并去除两端空格
            if '#' in line:
                line = line.split('#', 1)[0].strip()
            if line:
                lines.append(line)

        # Parse nested block structure
        # print(lines)
        blocks, flash_blocks = self._parse_blocks(lines)

        # Process each block
        for block in blocks:
            if block['type'] == 'image':
                # print(f"block:{block}")
                self._process_image_block(block, flash_blocks)

    def _parse_blocks(self, lines: List[str]) -> (List[Dict[str, Any]], List[Dict[str, Any]]):
        """Parse nested block structure"""
        image_blocks = []
        flash_blocks = []
        i = 0
        while i < len(lines):
            line = lines[i]
            if line.startswith('image'):
                # Parse each image block
                block_name = line.split()[1]

                blocks, i = self._parse_image_block(lines, i + 1)
                image_blocks.append({
                    'type': "image",
                    'name': block_name,
                    'content': blocks
                })
            elif line.startswith('flash'):
                # Parse each flash block
                block_name = line.split()[1]

                block, i = self._get_type_config(lines, i + 1)
                flash_blocks.append({
                    'type': "flash",
                    'name': block_name,
                    'content': block
                })
            else: 
                raise ValueError(f"Unknown block type {line}")

            i += 1

        return image_blocks, flash_blocks

    def _parse_image_block(self, lines: List[str], index_start: int) -> (Dict[str, Any], int):
        i = index_start
        type_config = {}
        config = {}
        partitions = []

        # Process partitions and other configurations
        while i < len(lines):
            line = lines[i]
            if line.startswith('}'):
                break
            elif line.startswith('partition'):
                block_name = line.split()[1]
                partition, i = self._get_type_config(lines, i)
                i += 1

                partitions.append({
                    'type': 'partition',
                    'name': block_name,
                    'config': partition
                })
            elif len(line.split()) >= 2 and line.split()[1] == '{':
                # Process type configuration type_config
                parts = line.split()
                type_name = parts[0]
                type_config, i = self._get_type_config(lines, i - 1)
                i += 1
            else:
                config, i = self._get_type_config(lines, i - 1)

        blocks = {
            'type': type_name,
            'type_config': type_config,
            'config': config,
            'partitions': partitions
            }

        return blocks, i

    def _get_type_config(self, lines: List[str], index_start: int) -> (Dict[str, Any], int):
        # Parse configuration within {}
        i = index_start
        config = {}

        while i < len(lines):
            i += 1
            line = lines[i]
            stripped_line = line.strip()

            if '=' in stripped_line:
                key, value = stripped_line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")  # Remove quotes if present

                # Convert value to appropriate type
                if value.lower() == 'true':
                    config[key] = True
                elif value.lower() == 'false':
                    config[key] = False
                elif value.isdigit():
                    config[key] = int(value)
                else:
                    config[key] = value

            if stripped_line.endswith('}'):
                break

        return config, i

    def _load_handler(self, handler_type: str) -> Optional[ImageHandler]:
        """Load specified type handler"""
        if handler_type not in HANDLERS:
            print(f"Error: unknown image type {handler_type}")
            raise ValueError(f"Unknown image type {handler_type}")

        module_name = HANDLERS[handler_type]
        try:
            print(f"handler import: {module_name}")
            module = __import__(module_name)
            if hasattr(module, 'get_handler'):
                return module.get_handler()
            else:
                print(f"Error: module {module_name} does not have a get_handler function")
                raise ValueError(f"Module {module_name} does not have a get_handler function")

        except ImportError:
            print(f"Error: could not load handler for {handler_type}")
            raise ValueError(f"Could not load handler for {handler_type}")

    def _cal_image_size(self, image: Image, image_name: str) -> int:
        """Calculate file size"""

        size = 0
        # Traverse image to find file
        print(f"image_name: {image_name}")
        for img in self.images:
            if img.file == image_name:
                if img.size:
                    return img.size

        # # File path search
        # file_path = os.path.join(self.imagepath, image_name)

        # if os.path.exists(file_path):
        #     # Get file statistics
        #     stat_info = os.stat(file_path)
        #     # Get file size
        #     size = stat_info.st_size

        #     print(f"File {file_path} size is {size}")

        return size

    def _process_image_block(self, block: Dict[str, Any], flash_blocks: List[Dict[str, Any]]) -> None:
        """Process image"""
        image_name = block['name']
        content = block['content']

        image_config = content['config']

        image_type = content.get('type')

        # Create image object
        image = Image(
            name=image_name,
            file=image_name,
            image_type=image_type,
            size_str=image_config.get('size', None),
            size=parse_size(image_config.get('size', 0)),
            temporary=image_config.get('temporary', False),
            mountpoint=image_config.get('mountpoint', None),
            empty=image_config.get('empty', False),
            exec_pre=image_config.get('exec-pre', None),
            exec_post=image_config.get('exec-post', None),
            handler_config=content.get('type_config', {}),
            # holes=image_config.get('holes', {}),

            handler=self._load_handler(image_type)
        )

        # Process flash type
        self._process_image_flash_block(image, content.get('config'), flash_blocks)

        # Set mount point
        self._set_mount_path(image)

        # Set output file path
        if image.temporary:
            image.outfile = os.path.join(self.tmppath, image.file)
        else:
            image.outfile = os.path.join(self.outputpath, image.file)

        # Process partitions
        for sub_block in content['partitions']:
            if sub_block['type'] == 'partition':
                self._process_partition_block(image, sub_block)

        # Process dependent images
        for dep in image.partitions:
            dep_image = self.get_image_by_name(dep.image)
            if dep_image and dep_image.outfile:
                dep_path = dep_image.outfile
            else:
                dep_path = os.path.join(self.rootpath, dep.image)

            image.dependencies.append({
                'image': dep_image.name if dep_image else dep.image,
                'image_path': dep_path
            })

        print(f"image: {image}")

        self.images.append(image)

    def _set_mount_path(self, image: Image) -> None:
        if image.mountpoint:
            try:
                mountPath = f"{self.tmppath}/root/{image.mountpoint}"

                image.mountpath = os.path.join(self.tmppath, f"mp-{image.mountpoint}")

                shutil.move(mountPath, image.mountpath)
                os.makedirs(mountPath, exist_ok=True)
                
                ref_stat = os.stat(image.mountpath)
                os.chmod(mountPath, ref_stat.st_mode)
                os.chown(mountPath, ref_stat.st_uid, ref_stat.st_gid)
            except Exception as e:
                raise ImageError(f"Error: {e}")

    def _process_image_flash_block(self, image: Image, content: Dict[str, Any], flash_blocks: List[Dict[str, Any]]) -> None:
        """Process image flash_type"""
        if image.image_type in ['flash', 'uffs']:
            for sub_block in flash_blocks:
                if content.get('flashtype') == sub_block.get('name'):
                    content = sub_block['content']
                    flash_type = Flash_type(
                        name=sub_block['name'],
                        pebsize=content.get('pebsize', 0),
                        lebsize=content.get('lebsize', 0),
                        numpebs=content.get('numpebs', 0),
                        minimum_io_unit_size=content.get('minimum-io-unit-size', 0),
                        vid_header_offset=content.get('vid-header-offset', 0),
                        sub_page_size=content.get('sub-page-size', 0),

                        is_uffs=(image.image_type == 'uffs'),
                        page_size=content.get('page-size', 0),
                        block_pages=content.get('block-pages', 0),
                        total_blocks=content.get('total-blocks', 0),
                        spare_size=content.get('spare-size', 0),
                        status_offset=content.get('status-offset', 0),
                        ecc_option=content.get('ecc-option', 3),
                        ecc_size=content.get('ecc-size', 0)
                    )
                    # print(f"Flash_type: {lash_type}")

                    image.flash_type = flash_type
                    break
            else:
                raise ImageError(f"Image {image.name} flash type {flash_block['name']} not found")
    
    def _process_partition_block(self, image: Image, block: Dict[str, Any]) -> None:
        """Process image partition"""
        part_name = block['name']
        content = block['config']
        
        # Parse partition offset
        offset = content.get('offset')
        if offset:
            offset = parse_size(offset)
        
        # Parse partition size
        size = content.get('size')
        if size:
            size = parse_size(size)
        else:
            size = self._cal_image_size(image, content.get('image'))
        
        # Create partition object
        partition = Partition(
            name=part_name,
            parent_image=image.name,
            in_partition_table=content.get('in-partition-table', True),
            offset=offset if offset is not None else 0,
            size=size if size is not None else 0,
            image=content.get('image', None),
            partition_type=content.get('partition-type', None),
            partition_type_uuid=content.get('partition-type-uuid', None),
            partition_uuid=content.get('partition-uuid', None),
            bootable=content.get('bootable', False),
            read_only=content.get('read-only', False),
            hidden=content.get('hidden', False),
            fill=content.get('fill', False),
            logical=content.get('logical', False),
            align=parse_size(content.get('align', 0)),
            forced_primary=content.get('forced-primary', False),
            erase_size=parse_size(content.get('erase-size', 0)),
            flag=parse_size(content.get('flag', 0)),
            load=content.get('load', False),
            boot=content.get('boot', 0),
            extraargs=content.get('extraargs', None),
        )
        # print(f"partition: {partition}")

        image.partitions.append(partition)
    
    def _creat_work_dir(self) -> None:
        """Create working directory"""
        shutil.copytree(f"{self.rootpath}", f"{self.tmppath}/root")
    
    def run(self) -> None:
        """Run image generation tool"""
        try:

            self._creat_work_dir()

            print(f"parsing config file: {self.config_file}")
            self.parse_config()
            
            # Parse dependencies and sort
            # print("Parsing image dependencies...")
            # ordered_images = self.resolve_dependencies()

            # Generate all images
            print("Start generating images...")
            for image in self.images:
                print(f"Generate image: {image.name} ({image.image_type})")

                # Execute pre-command
                if image.exec_pre:
                    print(f"Run pre command: {image.exec_pre}")
                    run_command(image.exec_pre.split())

                # Call handler to generate image
                if image.handler:
                    image.handler.run(image, image.handler_config)
                else:
                    raise ImageError(f"Image {image.name} has no handler")

                # Execute post-command
                if image.exec_post:
                    print(f"Run post command: {image.exec_post}")
                    run_command(image.exec_post.split())
                print(f"Image {image.name} generated")

            print("All images generated successfully")
        except ImageError as e:
            print(f"error: {str(e)}", file=sys.stderr)
        finally:
            # Clean up temporary files
            shutil.rmtree(self.tmppath, ignore_errors=True)
            # pass

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rootpath', required=True)
    parser.add_argument('--outputpath', required=True)
    parser.add_argument('--config', required=True)
    args = parser.parse_args()

    tool = GenImageTool(args.rootpath, args.outputpath, args.config)
    tool.run()

if __name__ == "__main__":
    main()
