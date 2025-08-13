#!/usr/bin/env python3
import argparse
import subprocess
import tempfile
import shutil
import os
import glob
import sys

def run_cmd(cmd, cwd=None):
    subprocess.check_call(cmd, cwd=cwd)

def main():
    parser = argparse.ArgumentParser(description="Merge all .a libraries from a folder into one.")
    parser.add_argument(
        "--toolchain-prefix", required=True,
        help="Toolchain prefix, e.g. riscv64-unknown-elf"
    )
    parser.add_argument(
        "--input", required=True,
        help="Folder to search for .a files (recursive)"
    )
    parser.add_argument(
        "--output", required=True,
        help="Path to output combined .a"
    )
    parser.add_argument(
        "--workdir", default=None,
        help="Optional working directory (default: temporary folder)"
    )
    args = parser.parse_args()

    # Ensure toolchain prefix ends with '-'
    prefix = args.toolchain_prefix
    if not prefix.endswith("-"):
        prefix += "-"
    ar = prefix + "ar"
    ranlib = prefix + "ranlib"

    # Find all .a files
    libs = glob.glob(os.path.join(args.input, "**", "*.a"), recursive=True)
    if not libs:
        print(f"No .a files found in {args.input}", file=sys.stderr)
        sys.exit(1)

    # Prepare working directory
    workdir = args.workdir or tempfile.mkdtemp(prefix="merge_a_")
    if not os.path.exists(workdir):
        os.makedirs(workdir)

    try:
        # Extract each .a into its own subfolder to avoid collisions
        for lib in libs:
            extract_dir = os.path.join(workdir, os.path.basename(lib) + "_extract")
            os.makedirs(extract_dir, exist_ok=True)
            run_cmd([ar, "x", os.path.abspath(lib)], cwd=extract_dir)
            # Rename and move extracted .o files to main workdir
            for obj in glob.glob(os.path.join(extract_dir, "*.o")):
                new_name = f"{os.path.basename(lib).replace('.a','')}_{os.path.basename(obj)}"
                dest = os.path.join(workdir, new_name)
                shutil.move(obj, dest)

        # Create combined .a
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        run_cmd([ar, "rcs", os.path.abspath(args.output)] + glob.glob(os.path.join(workdir, "*.o")))
        run_cmd([ranlib, os.path.abspath(args.output)])

        print(f"Combined library created: {args.output}")

    finally:
        if args.workdir is None:
            shutil.rmtree(workdir)

if __name__ == "__main__":
    main()
