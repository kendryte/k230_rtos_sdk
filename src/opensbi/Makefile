include $(SDK_TOOLS_DIR)/toolchain_linux.mk

include $(SDK_SRC_ROOT_DIR)/.config

ifneq ($(shell [ -d $(SDK_BUILD_IMAGES_DIR)/opensbi ] && echo 1 || echo 0),1)
$(shell mkdir -p $(SDK_BUILD_IMAGES_DIR)/opensbi)
endif

ifeq ($(CONFIG_OPENSBI_USE_PREBUILT_FW_JUMP),y)
SDK_PREBUILT_FW_JUMP_PATH := $(SDK_BOARD_DIR)/$(CONFIG_OPENSBI_PREBUILT_FW_JUMP_PATH)
endif

SHELL := bash

.PHONY: all clean distclean

.PHONY: build
build:
	@rm -rf $(SDK_OPENSBI_BUILD_DIR)/opensbi.bin;
	@rm -rf $(SDK_OPENSBI_BUILD_DIR)/rtthread.bin;
	@rm -rf $(SDK_OPENSBI_SRC_DIR)/opensbi/rtthread.bin;

	@if [ ! -f $(SDK_BUILD_IMAGES_DIR)/rtsmart/rtthread.bin ]; then \
		echo "should run make rtsmart" && exit 1; \
	fi;
	@cp $(SDK_BUILD_IMAGES_DIR)/rtsmart/rtthread.bin $(SDK_OPENSBI_BUILD_DIR)/rtthread.bin;

ifeq ($(CONFIG_OPENSBI_USE_PREBUILT_FW_JUMP),y)
	@echo "Using prebuilt fw_jump.bin instead of building OpenSBI..."
	@if [ ! -f $(SDK_PREBUILT_FW_JUMP_PATH) ]; then \
		echo "Prebuilt fw_jump.bin not found at $(SDK_PREBUILT_FW_JUMP_PATH)" && exit 1; \
	fi; \
	cp $(SDK_PREBUILT_FW_JUMP_PATH) $(SDK_OPENSBI_BUILD_DIR)/opensbi.bin;
else
	@echo "Compiling OpenSBI..."
	@pushd $(SDK_OPENSBI_SRC_DIR)/opensbi > /dev/null; \
	$(MAKE) O=$(SDK_OPENSBI_BUILD_DIR) PLATFORM=kendryte/fpgac908 FW_PAYLOAD=n OPENSBI_QUIET=1 CROSS_COMPILE=$(CROSS_COMPILE) || exit $?; \
	cp $(SDK_OPENSBI_BUILD_DIR)/platform/kendryte/fpgac908/firmware/fw_jump.bin $(SDK_OPENSBI_BUILD_DIR)/opensbi.bin || exit $?; \
	popd > /dev/null;
endif

all: build
	@python3 $(SDK_TOOLS_DIR)/gen_image_opensbi.py -o $(SDK_OPENSBI_BUILD_DIR)/opensbi.bin -r $(SDK_OPENSBI_BUILD_DIR)/rtthread.bin

clean:
	@rm -rf $(SDK_OPENSBI_BUILD_DIR)
	@rm -rf $(SDK_BUILD_IMAGES_DIR)/opensbi

distclean: clean

.PHONY: arduino-sdk arduino-sdk-clean arduino-sdk-distclean
arduino-sdk:
	@rm -rf $(SDK_ARDUINO_SDK_BUILD_DIR)/variants/$(CONFIG_BOARD)/opensbi/**
	@mkdir -p $(SDK_ARDUINO_SDK_BUILD_DIR)/variants/$(CONFIG_BOARD)/opensbi
	@cp -rf $(SDK_BUILD_IMAGES_DIR)/opensbi/* $(SDK_ARDUINO_SDK_BUILD_DIR)/variants/$(CONFIG_BOARD)/opensbi/

arduino-sdk-clean:
	@rm -rf $(SDK_ARDUINO_SDK_BUILD_DIR)/$(CONFIG_BOARD)/opensbi/**

arduino-sdk-distclean: arduino-sdk-clean
