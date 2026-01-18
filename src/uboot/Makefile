ifneq ($(MKENV_INCLUDED),1)
export SDK_SRC_ROOT_DIR := $(realpath $(dir $(realpath $(lastword $(MAKEFILE_LIST))))/../../)
endif

include $(SDK_SRC_ROOT_DIR)/tools/mkenv.mk

include $(SDK_TOOLS_DIR)/toolchain_linux.mk

ifneq ($(shell [ -d ${SDK_BUILD_IMAGES_DIR}/uboot ] && echo 1 || echo 0),1)
$(shell mkdir -p ${SDK_BUILD_IMAGES_DIR}/uboot)
endif

.PHONY: all clean distclean build menuconfig

build:
ifeq ($(CONFIG_UBOOT_USE_PREBUILT),y)
	@echo "Using prebuilt U-Boot binaries, skipping compilation"
	@mkdir -p $(SDK_UBOOT_BUILD_DIR)/spl
	@cp $(SDK_BOARD_DIR)/$(CONFIG_UBOOT_PREBUILT_SPL_PATH) $(SDK_UBOOT_BUILD_DIR)/spl/u-boot-spl.bin
	@cp $(SDK_BOARD_DIR)/$(CONFIG_UBOOT_PREBUILT_UBOOT_PATH) $(SDK_UBOOT_BUILD_DIR)/u-boot.bin
else
	@echo "Building U-Boot from source"
	@cp $(SDK_SRC_ROOT_DIR)/include/generated/autoconf.h $(SDK_UBOOT_SRC_DIR)/uboot/board/kendryte/common/sdk_autoconf.h
	@$(MAKE) -C uboot $(UBOOT_DEFCONFIG) ARCH=riscv O=$(SDK_UBOOT_BUILD_DIR) || exit $?;
	@$(MAKE) -C $(SDK_UBOOT_BUILD_DIR) ARCH=riscv || exit $?;
endif

all: build
	@python3 $(SDK_TOOLS_DIR)/gen_image_uboot.py -s $(SDK_UBOOT_BUILD_DIR)/spl/u-boot-spl.bin -u $(SDK_UBOOT_BUILD_DIR)/u-boot.bin

clean:
	@if [ -f $(SDK_UBOOT_BUILD_DIR)/Makefile ]; then $(MAKE) -C $(SDK_UBOOT_BUILD_DIR) ARCH=riscv clean; fi

distclean: clean
	@rm -rf $(SDK_UBOOT_BUILD_DIR)
	@rm -rf ${SDK_BUILD_IMAGES_DIR}/uboot

menuconfig: clean
	@export ARCH=riscv; \
	make -C uboot $(UBOOT_DEFCONFIG) || exit $?; \
	make -C uboot menuconfig || exit $?; \
	make -C uboot savedefconfig || exit $?; \
	cp uboot/defconfig $(SDK_UBOOT_SRC_DIR)/uboot/configs/$(UBOOT_DEFCONFIG); \
	make -C uboot distclean || exit $?;

.PHONY: arduino-sdk arduino-sdk-clean arduino-sdk-distclean
arduino-sdk:
	@rm -rf $(SDK_ARDUINO_SDK_BUILD_DIR)/variants/$(CONFIG_BOARD)/uboot/**
	@mkdir -p $(SDK_ARDUINO_SDK_BUILD_DIR)/variants/$(CONFIG_BOARD)/uboot
	@cp -rf $(SDK_BUILD_IMAGES_DIR)/uboot/* $(SDK_ARDUINO_SDK_BUILD_DIR)/variants/$(CONFIG_BOARD)/uboot/

arduino-sdk-clean:
	@rm -rf $(SDK_ARDUINO_SDK_BUILD_DIR)/$(CONFIG_BOARD)/uboot/**

arduino-sdk-distclean: arduino-sdk-clean
