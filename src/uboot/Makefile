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
	@export ARCH=riscv; \
	make -C uboot $(UBOOT_DEFCONFIG) O=$(SDK_UBOOT_BUILD_DIR) || exit $?; \
	make -j$(NCPUS) -C $(SDK_UBOOT_BUILD_DIR) || exit $?;
endif

all: build
	$(SDK_UBOOT_SRC_DIR)/gen_image || exit $?;

clean:
	@export ARCH=riscv; \
	if [ -f $(SDK_UBOOT_BUILD_DIR)/Makefile ]; then $(MAKE) -C $(SDK_UBOOT_BUILD_DIR) clean; fi

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
