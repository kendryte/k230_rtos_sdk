#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import argparse
import shutil
from pathlib import Path
from contextlib import contextmanager
import subprocess
import tempfile
import urllib.request
from urllib.error import URLError, HTTPError
from typing import Tuple
import os

# Custom exceptions for better error handling
class ImageToolsImportError(Exception):
    """Raised when image_tools module cannot be imported"""
    pass

class DDRTestImageError(Exception):
    """Base exception for DDR test image generation errors"""
    pass

def import_image_tools():
    """
    Import image_tools module with proper error handling.
    Returns the module or raises ImageToolsImportError.
    """
    try:
        import image_tools
        return image_tools
    except ImportError as e:
        raise ImageToolsImportError(f"Failed to import image_tools: {e}")

# Configuration constants
DDR_CONFIG = {
    128: ("vpu_h264enc_4k_loop_128M.bin", "ddr_dma_cpu_read_write_128m.bin"),
    512: ("vpu_jpegenc_8k_loop_512MB.bin", "ddr_dma_cpu_read_write_20000000.bin"),
    1024: ("vpu_jpegenc_8k_loop_512MB.bin", "ddr_dma_cpu_read_write_40000000.bin"),
    2048: ("vpu_miniplayer_8k_loop_0x40000000.bin", "ddr_dma_cpu_read_write_80000000.bin"),
}

@contextmanager
def temporary_directory():
    """创建临时目录（兼容性封装，实际可用 tempfile.TemporaryDirectory）"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

def gen_cfg(cfg_path: Path) -> None:
    """Generate configuration file for genimage"""
    content = """image ddr_test.img {
\thdimage {
\t\t# Enable TOC (Table of Contents)
\t\ttoc = true
\t\ttoc-offset = 0xe0000
\t\t# use mbr
\t\tpartition-table-type = "mbr"

\t\t# use gpt
\t\t# partition-table-type = "gpt"
\t\t# disk-uuid = "bc8ba9e1-f3d0-443a-9d55-976a737bde84"
\t}

\t# OTA meta 分区：用于存放 A/B 槽位版本块
\t# 注意：仅在 TOC 中占位，初始内容为空，后续由 OTA/boot 写入
\tpartition ota_meta {
\t\tin-partition-table = false
\t\toffset = 0xf0000
\t\tsize = 0x800
\t}

\tpartition spl {
\t\tin-partition-table = false
\t\toffset = 0x100000
\t\timage = "uboot/fn_u-boot-spl.bin"
\t}

\t# TODO: Update to use fat partition
\tpartition uboot_env {
\t\tin-partition-table = false
\t\toffset = 0x1e0000
\t\tsize = 0x10000
\t\timage = "uboot/env.bin"
\t}

\tpartition uboot {
\t\tin-partition-table = false
\t\toffset = 0x200000
\t\timage = "uboot/fn_ug_u-boot.bin"
\t}

\tpartition rtt_a {
\t\tin-partition-table = false
\t\toffset = 10M
\t\tsize = 20M
\t\timage = "fn_mkimg_gz_vpu.bin"
\t\tload = true
\t\tboot = 0x3
\t}
}"""
    try:
        cfg_path.write_text(content, encoding="utf-8")
    except (PermissionError, OSError) as e:
        raise DDRTestImageError(f"Failed to write config file {cfg_path}: {e}")

def get_vpu_cpu_by_ddr_size(ddr_size: int) -> Tuple[str, str]:
    """Get VPU and CPU binary names based on DDR size"""
    if ddr_size not in DDR_CONFIG:
        supported = ", ".join(map(str, DDR_CONFIG.keys()))
        raise DDRTestImageError(f"Unsupported DDR size: {ddr_size}. Supported: {supported}")
    return DDR_CONFIG[ddr_size]

def download_file(url: str, save_path: Path) -> None:
    """Download file using wget with proper error handling and real-time progress"""
    cmd = ["wget", "-c", "--progress=bar:force", "-O", str(save_path), url]
    try:
        # Run wget with real-time output
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # Print output in real-time
        for line in process.stdout:
            print(f"  {line.rstrip()}")
        
        # Wait for process to complete
        return_code = process.wait()
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, cmd)
            
    except subprocess.CalledProcessError as e:
        raise DDRTestImageError(f"Failed to download {url}")

def verify_file_exists(url: str, filename: str, timeout: int = 5) -> bool:
    """
    Verify if a specific file exists on the mirror.
    Uses HEAD request to check without downloading.
    """
    file_url = f"{url.rstrip('/')}/{filename}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        req = urllib.request.Request(file_url, method="HEAD", headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status == 200
    except (URLError, HTTPError, TimeoutError):
        return False

def get_preferred_mirror(vpu_filename: str, cpu_filename: str) -> str:
    """
    Find a working mirror that has both required files.
    Returns the base URL of the first working mirror.
    """
    mirrors = [
        "https://kendryte-download.canaan-creative.com/k230/downloads/dl/ddr_test",
        "https://ai.b-bug.org/k230/downloads/dl/ddr_test",
    ]

    working_mirrors = []
    
    for mirror in mirrors:
        print(f"  Checking mirror: {mirror}")
        
        # Check if both files exist on this mirror
        vpu_exists = verify_file_exists(f"{mirror}/vpu", vpu_filename)
        cpu_exists = verify_file_exists(f"{mirror}/ddr_test_bin", cpu_filename)
        
        if vpu_exists and cpu_exists:
            print(f"  ✓ Mirror has both required files")
            return mirror
        elif vpu_exists or cpu_exists:
            print(f"  ⚠ Mirror has incomplete files (VPU: {vpu_exists}, CPU: {cpu_exists})")
            working_mirrors.append(mirror)
        else:
            print(f"  ✗ Mirror unreachable or missing files")
    
    # If no mirror has both files, try the first partially working one
    if working_mirrors:
        print(f"  ⚠ Using partially working mirror: {working_mirrors[0]}")
        return working_mirrors[0]
    
    raise DDRTestImageError("All download mirrors are unreachable or missing required files")

def download_ddr_test_bin(vpu: str, cpu: str, images_dir: Path, image_tools) -> None:
    """Download DDR test binaries from the best available mirror"""
    base_url = get_preferred_mirror(vpu, cpu)
    
    vpu_url = f"{base_url}/vpu/{vpu}"
    cpu_url = f"{base_url}/ddr_test_bin/{cpu}"

    print(f"  Downloading VPU binary from {vpu_url}")
    download_file(vpu_url, images_dir / vpu)

    print(f"  Downloading CPU binary from {cpu_url}")
    download_file(cpu_url, images_dir / cpu)

def addhead(vpu_cpu_bin_path: Path, output_path: Path, image_tools) -> None:
    """Add U-Boot header to binary"""
    with temporary_directory() as tmpdir:
        gz_file = image_tools.K230PrivGzip().compress_file(str(vpu_cpu_bin_path))
        mkimg_vpu = tmpdir / "vpu_img"

        image_tools.MkImage().create_image(
            [gz_file], str(mkimg_vpu), "riscv", "u-boot", "firmware",
            "gzip", "0", "0", "vpn", verbose=True
        )

        if not image_tools.generate_k230_image(str(mkimg_vpu), str(output_path), None, None):
            raise DDRTestImageError("U-Boot image generation failed")

def _comment_line_in_file(file_path: Path, pattern: str) -> None:
    """Comment out lines matching pattern in file"""
    lines = file_path.read_text(encoding="utf-8").splitlines(keepends=True)
    new_lines = []
    for line in lines:
        if pattern in line and not line.lstrip().startswith("//"):
            new_lines.append("//" + line)
        else:
            new_lines.append(line)
    file_path.write_text("".join(new_lines), encoding="utf-8")

def run_make_uboot(sdk_root: Path) -> None:
    """Run U-Boot build with real-time output and optimal number of parallel jobs"""
    # Use number of CPU cores, but cap at 8 to avoid overwhelming the system
    cpu_count = min(os.cpu_count() or 2, 8)
    print(f"  Building U-Boot with -j{cpu_count}...")
    print("  " + "="*50)
    
    try:
        # Run make with real-time output
        process = subprocess.Popen(
            ["make", "uboot", f"-j{cpu_count}"],  # V=1 for verbose output
            cwd=sdk_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        
        # Print output in real-time
        for line in process.stdout:
            print(f"  {line.rstrip()}")
        
        # Wait for process to complete
        return_code = process.wait()
        print("  " + "="*50)
        
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, ["make", "uboot"])
            
    except subprocess.CalledProcessError as e:
        raise DDRTestImageError(f"U-Boot build failed with exit code {e.returncode}")

def patch_uboot_files(sdk_root: Path, apply_patch: bool) -> None:
    """Patch or unpatch U-Boot source files"""
    spl_file = sdk_root / "src/uboot/uboot/board/kendryte/common/k230_spl.c"
    boot_file = sdk_root / "src/uboot/uboot/board/kendryte/common/k230_boot.c"
    files_to_patch = [spl_file, boot_file]
    
    for f in files_to_patch:
        if not f.exists():
            raise DDRTestImageError(f"Required file not found: {f}")
            
        bak = f.with_suffix(f.suffix + ".bak")
        
        if apply_patch:
            # Only backup if not already backed up
            if not bak.exists():
                print(f"  Backing up {f.name} to {bak.name}")
                shutil.copy2(f, bak)
            else:
                print(f"  Backup {bak.name} already exists, using it as reference")
                
            # Apply patches
            _comment_line_in_file(f, "spl_device_disable()")
            _comment_line_in_file(f, "k230_setup_user_tag()")
            
        else:
            # Restore from backup if it exists
            if bak.exists():
                print(f"  Restoring {f.name} from backup")
                shutil.move(bak, f)
            else:
                print(f"  Warning: No backup found for {f.name}, cannot restore")

def build_uboot_with_patches(sdk_root_dir: Path) -> None:
    """
    Build U-Boot with temporary patches.
    Shows real-time build logs.
    Raises DDRTestImageError on failure.
    """
    print("🔧 Patching U-Boot source files...")
    
    try:
        # Apply patches
        patch_uboot_files(sdk_root_dir, apply_patch=True)
        
        # Attempt build with real-time logs
        run_make_uboot(sdk_root_dir)
        
        print("✅ U-Boot build completed.")
        
    except Exception as e:
        raise DDRTestImageError(f"U-Boot build failed: {e}")
        
    finally:
        # ALWAYS restore original files, even if build fails
        print("🔄 Restoring original U-Boot source files...")
        patch_uboot_files(sdk_root_dir, apply_patch=False)

def main() -> None:
    """Main function with proper error handling"""
    parser = argparse.ArgumentParser(description="Generate DDR test image.")
    parser.add_argument(
        "ddr_size",
        type=int,
        choices=[128, 512, 1024, 2048],
        help="DDR size in MB (128, 512, 1024, or 2048)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show verbose output"
    )
    args = parser.parse_args()

    try:
        # Import image_tools inside main to avoid module-level exit
        image_tools = import_image_tools()
        
        # Get required paths
        sdk_root_dir = Path(image_tools.get_validated_env_path("SDK_SRC_ROOT_DIR"))
        images_path = Path(image_tools.get_validated_env_path("SDK_BUILD_IMAGES_DIR"))
        images_path.mkdir(parents=True, exist_ok=True)

        # Build U-Boot with patches (shows real-time logs)
        build_uboot_with_patches(sdk_root_dir)

        # Download DDR test binaries
        print("\n📥 Downloading DDR test binaries...")
        vpu, cpu = get_vpu_cpu_by_ddr_size(args.ddr_size)
        download_ddr_test_bin(vpu, cpu, images_path, image_tools)

        # Add header to VPU binary
        print("\n🔧 Adding U-Boot header to VPU binary...")
        vpu_bin = images_path / vpu
        vpu_img = images_path / "fn_mkimg_gz_vpu.bin"
        addhead(vpu_bin, vpu_img, image_tools)

        # Clean up downloaded binaries
        vpu_bin.unlink(missing_ok=True)
        (images_path / cpu).unlink(missing_ok=True)

        # Generate final image
        print("\n📦 Generating final image...")
        cfg_path = images_path / "ddr_test_img.cfg"
        gen_cfg(cfg_path)

        genimage_script = sdk_root_dir / "tools" / "genimage.py"
        cmd = [
            sys.executable, str(genimage_script),
            "--rootpath", str(images_path),
            "--outputpath", str(images_path),
            "--config", str(cfg_path)
        ]
        
        # Run genimage with real-time output
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )
        for line in process.stdout:
            print(f"  {line.rstrip()}")
        
        return_code = process.wait()
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, cmd)

        # Compress and rename
        print("\n🗜️ Compressing final image...")
        raw_img = images_path / "ddr_test.img"
        final_img = images_path / f"ddr_test_{args.ddr_size}MB.img.gz"

        result = subprocess.run(
            ["gzip", "-k", "-f", str(raw_img)], 
            check=True, 
            capture_output=True, 
            text=True
        )
        
        if result.returncode == 0 and (images_path / "ddr_test.img.gz").exists():
            (images_path / "ddr_test.img.gz").rename(final_img)

        # Final cleanup
        vpu_img.unlink(missing_ok=True)
        cfg_path.unlink(missing_ok=True)

        print(f"\n\033[32m✅ DDR Test Image generated successfully!\n📁 {final_img}\033[0m")

    except ImageToolsImportError as e:
        print(f"  Error: {e}", file=sys.stderr)
        sys.exit(1)
    except DDRTestImageError as e:
        print(f"  Error: {e}", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"  Command failed: {' '.join(e.cmd)}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n  Interrupted by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"  Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
