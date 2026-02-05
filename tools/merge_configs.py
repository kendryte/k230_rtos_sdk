#!/usr/bin/env python3
"""
prepare_defconfig.py - Merge samples config into defconfig if needed
Simple version - just handles merging logic
"""

import argparse
import os
import sys
import re

def is_enabled(value):
    """Check if a value represents 'enabled' state."""
    if not value:
        return False
    enabled_values = {'1', 'true', 'True', 'TRUE', 'y', 'Y', 'yes', 'YES', 'on', 'ON'}
    return str(value).strip() in enabled_values

def read_config_lines(file_path):
    """Read config file and return lines."""
    if not os.path.exists(file_path):
        print(f"Error: Config file not found: {file_path}")
        return []

    try:
        with open(file_path, 'r') as f:
            return f.readlines()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return []

def parse_samples_config(file_path):
    """Parse samples config into dictionary."""
    if not file_path or not os.path.exists(file_path):
        return {}

    samples = {}
    with open(file_path, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            match = re.match(r'^(CONFIG_[A-Za-z0-9_]+)=(.*)$', line)
            if match:
                samples[match.group(1)] = match.group(2)

    return samples

def config_exists(lines, config_name):
    """Check if config exists in lines."""
    pattern = re.compile(rf'^{config_name}=(.*)$')
    for line in lines:
        if pattern.match(line.strip()):
            return True
    return False

def merge_defconfig(input_path, samples_path, enable_samples):
    """Merge samples into defconfig if conditions are met."""
    lines = read_config_lines(input_path)
    if not lines:
        return None

    # Check if CONFIG_SDK_ENABLE_CANMV is y
    canmv_enabled = any(line.strip() == 'CONFIG_SDK_ENABLE_CANMV=y' for line in lines)

    # Decision logic:
    # 1. If canmv is enabled AND samples not forced → use original
    # 2. Otherwise, merge samples if enabled
    if canmv_enabled:
        print("CONFIG_SDK_ENABLE_CANMV=y")
        print("Using original defconfig without samples")
        return lines

    # Load samples if path provided
    samples = {}
    if samples_path and os.path.exists(samples_path) and enable_samples:
        samples = parse_samples_config(samples_path)

    if not samples:
        print("No samples to merge")
        return lines
    
    # Merge samples that don't already exist
    merged = lines[:]
    added = 0
    for config_name, config_value in samples.items():
        if not config_exists(merged, config_name):
            merged.append(f"{config_name}={config_value}\n")
            added += 1
            print(f"  Added: {config_name}={config_value}")
    
    print(f"Merged {added} configs from samples")
    return merged

def main():
    parser = argparse.ArgumentParser(description='Merge samples config into defconfig')
    parser.add_argument('--defconfig', required=True, help='Input defconfig file')
    parser.add_argument('--output', required=True, help='Output defconfig file')
    parser.add_argument('--samples', help='Samples config file (optional)')
    parser.add_argument('--enable-samples', help='Enable samples merging (1/true/yes)')

    args = parser.parse_args()

    # Basic validation
    if not os.path.exists(args.defconfig):
        print(f"Error: Defconfig not found: {args.defconfig}")
        sys.exit(1)

    # Merge if needed
    enable_samples = is_enabled(args.enable_samples)
    merged_lines = merge_defconfig(args.defconfig, args.samples, enable_samples)

    if merged_lines is None:
        print("Error: Failed to process defconfig")
        sys.exit(1)

    # Write output
    try:
        with open(args.output, 'w') as f:
            f.writelines(merged_lines)
        print(f"Created defconfig: {args.output}")
    except Exception as e:
        print(f"Error writing output: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
