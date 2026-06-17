#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Firmware image auto-discovery and medium-type guessing for K230.
"""

import os
from pathlib import Path
from typing import List, Optional


def find_built_images(search_dir: Optional[str] = None) -> List[Path]:
    """
    Search for built K230 firmware images in the output directory.

    After gen_image.sh runs, images are renamed from sysimage-*.img/kdimg
    to descriptive names like ``<board>_micropython_<rev>.img``.
    We match ``*.img`` and ``*.kdimg`` (excluding .gz / .md5 sidecars).

    :param search_dir: Directory to search. Defaults to $SDK_BUILD_DIR
                       or the project-root /output.
    :return: List of matching image Paths, sorted by name.
    """
    if search_dir:
        base = Path(search_dir)
    else:
        sdk_build = os.environ.get("SDK_BUILD_DIR")
        if sdk_build:
            base = Path(sdk_build)
        else:
            base = Path(__file__).resolve().parent.parent.parent / "output"

    if not base.exists():
        return []

    img_files: List[Path] = []
    kdimg_files: List[Path] = []

    for p in sorted(base.iterdir()):
        if not p.is_file():
            continue
        suffix = p.suffix.lower()
        if suffix == ".img":
            img_files.append(p)
        elif suffix == ".kdimg":
            kdimg_files.append(p)

    # Prefer .img files; only return .kdimg if no .img found
    return img_files if img_files else kdimg_files


def guess_medium_from_image(image_path: Path) -> str:
    """
    Guess the target medium type from the image filename.

    After gen_image.sh renames the image, the original medium prefix
    (sysimage-sdcard / sysimage-spinand / sysimage-spinor) is lost.
    We use these heuristics:

    - ``*_ota.kdimg``  → SDCARD  (OTA images are always built for SDCARD)
    - ``*.kdimg``      → SDCARD  (kdimg format is typically for SDCARD OTA)
    - ``*.img``        → SDCARD  (fallback; use -m to override)

    >>> guess_medium_from_image(Path('k230_canmv_micropython_local_nncase_v2.0.img'))
    'SDCARD'
    >>> guess_medium_from_image(Path('k230_canmv_micropython_local_nncase_v2.0_ota.kdimg'))
    'SDCARD'
    """
    name = image_path.name.lower()

    # _ota.kdimg  →  always SDCARD
    if name.endswith("_ota.kdimg"):
        return "SDCARD"

    # .kdimg (non-ota)  →  likely SDCARD
    if name.endswith(".kdimg"):
        return "SDCARD"

    # .img  →  default to SDCARD (most common); user can override with -m
    return "SDCARD"
