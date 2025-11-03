#!/bin/bash

set -eo pipefail

# Source configuration and functions
source ${SDK_SRC_ROOT_DIR}/.config
source ${SDK_TOOLS_DIR}/gen_image_func.sh

# Ensure output directory exists
OUTPUT_DIR="${SDK_BUILD_IMAGES_DIR}/rtapp"
rm -rf ${SDK_BUILD_IMAGES_DIR}/bin/preload
mkdir -p "$OUTPUT_DIR"
cd "$OUTPUT_DIR"

# If fast boot is not enabled, create placeholder
if [ "$CONFIG_FAST_BOOT_CONFIGURATION" != "y" ]; then
    echo "032K" > rtapp.elf.gz
    cd - >/dev/null
    exit 0
fi

# Get source file from Kconfig and expand variables
RTAPP_FILE=$(eval echo "$CONFIG_FAST_BOOT_FILE_PATH")
echo "DEBUG: RTAPP_FILE = $RTAPP_FILE"

# Check if source file exists
if [ ! -f "$RTAPP_FILE" ]; then
    echo "Error: File not found: $RTAPP_FILE"
    cd - >/dev/null
    exit 1
fi

# Package the file
RTAPP_FILENAME=$(basename "$RTAPP_FILE")
INTERMEDIATE_FILE="fn_ug_${RTAPP_FILENAME}"

if ! bin_gzip_ubootHead_firmHead "$RTAPP_FILE" "-O u-boot -T multi -a 0x0 -e 0x0 -n rtapp"; then
    echo "Error: Packaging failed"
    cd - >/dev/null
    exit 1
fi

# Move to final location
if [ ! -f "$INTERMEDIATE_FILE" ]; then
    echo "Error: Intermediate file not created"
    cd - >/dev/null
    exit 1
fi

mv "$INTERMEDIATE_FILE" rtapp.elf.gz

# Show result
ORIGINAL_SIZE=$(wc -c < "$RTAPP_FILE")
FINAL_SIZE=$(wc -c < rtapp.elf.gz)
RATIO=$(echo "scale=1; 100 * $FINAL_SIZE / $ORIGINAL_SIZE" | bc -l 2>/dev/null || echo "N/A")
echo "rtapp.elf.gz: ${ORIGINAL_SIZE} -> ${FINAL_SIZE} bytes (${RATIO}%)"
echo "preload" > ${SDK_BUILD_IMAGES_DIR}/bin/preload

cd - >/dev/null
