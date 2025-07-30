#!/usr/bin/env python3

import os
import shutil
import toml
import re

def expand_vars(value):
    """Expand ${VAR} or $VAR from environment variables"""
    return os.path.expandvars(value)

def expand_config_vars(cfg):
    """Expand environment variables in config entries"""
    for section in ('copy', 'move'):
        for entry in cfg.get(section, []):
            for key in ('src', 'dst'):
                if key in entry:
                    entry[key] = expand_vars(entry[key])
    return cfg

def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def copy_file(src, dst):
    ensure_dir(os.path.dirname(dst))
    shutil.copy2(src, dst)
    print(f"[COPY] {src} → {dst}")

def move_file(src, dst):
    ensure_dir(os.path.dirname(dst))
    shutil.move(src, dst)
    print(f"[MOVE] {src} → {dst}")

def process_config(config_path):
    cfg = toml.load(config_path)
    cfg = expand_config_vars(cfg)

    for entry in cfg.get('copy', []):
        src, dst = entry['src'], entry['dst']
        if os.path.isdir(src):
            for root, _, files in os.walk(src):
                for f in files:
                    rel_path = os.path.relpath(os.path.join(root, f), src)
                    dst_path = os.path.join(dst, rel_path)
                    copy_file(os.path.join(root, f), dst_path)
        else:
            copy_file(src, dst)

    for entry in cfg.get('move', []):
        src, dst = entry['src'], entry['dst']
        move_file(src, dst)

if __name__ == '__main__':
    config_dir = os.environ.get('SDK_BOARD_DIR', '.')
    config_path = os.path.join(config_dir, 'romfs.toml')  # Use romfs.toml here
    if not os.path.isfile(config_path):
        raise FileNotFoundError(f"Missing config file: {config_path}")
    print(f"📄 Using config: {config_path}")

    romfs_dir = os.environ.get('ROMFS_DIR', 'romfs')
    if os.path.exists(romfs_dir):
        print(f"🧹 Cleaning folder: {romfs_dir}")
        shutil.rmtree(romfs_dir)
    os.makedirs(romfs_dir, exist_ok=True)

    process_config(config_path)
