"""Build writable JFFS2 images with the RT-Smart port's zlib compressor."""
import os
import re
import shutil
import stat
import subprocess

from .common import ImageHandler, ImageError, mountpath, parse_size, run_command


def find_mkfs_jffs2():
    """Return the first mkfs.jffs2 that runs: bundled, then the host's.

    The bundled binary links liblzo2 and zlib dynamically, so it does not
    run on every build host. Image generation checks the compressor list and
    enables only zlib.
    """
    bundled = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin", "mkfs.jffs2")
    search = os.pathsep.join([os.environ.get("PATH", ""), "/usr/sbin", "/sbin"])
    failures = []
    for tool in (bundled, shutil.which("mkfs.jffs2", path=search)):
        if not tool or not os.access(tool, os.X_OK):
            continue
        try:
            result = subprocess.run([tool, "--version"], check=False,
                                    capture_output=True, text=True)
        except OSError as error:
            failures.append(f"{tool}: {error}")
            continue
        if result.returncode == 0:
            return tool
        failures.append(f"{tool}: {(result.stderr or result.stdout).strip()}")
    detail = "; ".join(failures) if failures else "none found"
    raise ImageError(f"No runnable mkfs.jffs2 (install mtd-utils): {detail}")


def list_compressors(tool, options=()):
    """Parse the entire list so an unfamiliar compressor cannot stay enabled."""
    try:
        result = subprocess.run([tool, *options, "-L"], check=False,
                                capture_output=True, text=True,
                                env={**os.environ, "LC_ALL": "C"})
    except OSError as error:
        raise ImageError(f"Cannot list mkfs.jffs2 compressors: {error}") from error
    # mtd-utils 2.1.1 and 2.2.0 print -L through their error-reporting helper,
    # including this banner and an exit status of 255.
    if result.returncode not in (0, 255):
        raise ImageError(f"mkfs.jffs2 compressor query failed ({result.returncode}): "
                         f"{(result.stdout + result.stderr).strip()}")
    compressors = {}
    for line in (result.stdout + "\n" + result.stderr).splitlines():
        line = line.strip()
        if not line or line == "mkfs.jffs2: error!:":
            continue
        match = re.fullmatch(r"([A-Za-z0-9_][A-Za-z0-9_-]*)\s+priority\s*:\s*"
                             r"-?\d+\s+(enabled|disabled)", line)
        if not match or match[1] in compressors:
            raise ImageError(f"Unrecognized mkfs.jffs2 compressor list entry: {line!r}")
        compressors[match[1]] = match[2] == "enabled"
    if not compressors:
        raise ImageError("mkfs.jffs2 returned an empty compressor list")
    return compressors


class Jffs2Handler(ImageHandler):
    type = "jffs2"
    opts = ["block-size", "page-size"]

    def setup(self, image, config):
        self.block_size = parse_size(str(config.get("block-size", "8192")))
        self.page_size = parse_size(str(config.get("page-size", "4096")))
        if self.block_size < 8192 or self.block_size & (self.block_size - 1):
            raise ImageError("JFFS2 erase block must be a power of two, at least 8192 bytes")
        if self.page_size != 4096:
            raise ImageError("RT-Smart JFFS2 requires a 4096-byte data page")
        if not image.size or image.size % self.block_size:
            raise ImageError("JFFS2 partition size must be a multiple of its erase block")

    def check_tree(self, image, root):
        # The RT-Smart port only converts regular-file and directory modes;
        # it stops in BUG() on symlinks, devices, FIFOs and sockets.
        if not root or not os.path.isdir(root):
            raise ImageError(f"JFFS2 image {image.name} has no source directory")
        for dirpath, dirnames, filenames in os.walk(root):
            for name in dirnames + filenames:
                path = os.path.join(dirpath, name)
                mode = os.lstat(path).st_mode
                if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
                    raise ImageError(f"JFFS2 image {image.name}: unsupported file type: "
                                     f"{os.path.relpath(path, root)}")

    def generate(self, image):
        root = mountpath(image)
        self.check_tree(image, root)
        tool = find_mkfs_jffs2()
        # Disable all optional compressors before enabling zlib. Host and
        # target must agree: the target does not enable LZO, Rubin or RTIME.
        compressors = list_compressors(tool)
        if "zlib" not in compressors:
            raise ImageError("mkfs.jffs2 was built without zlib support")
        compression_options = []
        for name in compressors:
            if name != "zlib":
                compression_options.extend(["-x", name])
        compression_options.extend(["-X", "zlib", "-m", "priority"])
        configured = list_compressors(tool, compression_options)
        if (configured.keys() != compressors.keys() or
                {name for name, enabled in configured.items() if enabled} != {"zlib"}):
            raise ImageError("mkfs.jffs2 did not enable exclusively zlib compression")
        cmd = [tool, *compression_options, "-l", "-f", "-U",
               "-e", str(self.block_size), "-s", str(self.page_size),
               f"--pad={image.size}", "-r", root, "-o", image.outfile]
        if run_command(cmd) != 0:
            raise ImageError(f"Failed to generate JFFS2 image {image.name}")
        if os.path.getsize(image.outfile) > image.size:
            raise ImageError(f"JFFS2 content exceeds partition {image.name}")

    def run(self, image, config):
        self.setup(image, config)
        self.generate(image)
