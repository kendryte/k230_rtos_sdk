include $(SDK_TOOLS_DIR)/toolchain_linux.mk

include $(SDK_SRC_ROOT_DIR)/.config

ifneq ($(shell [ -d $(SDK_BUILD_IMAGES_DIR)/opensbi ] && echo 1 || echo 0),1)
$(shell mkdir -p $(SDK_BUILD_IMAGES_DIR)/opensbi)
endif

ifeq ($(CONFIG_OPENSBI_USE_PREBUILT_FW_JUMP),y)
SDK_PREBUILT_FW_JUMP_PATH := $(SDK_BOARD_DIR)/$(CONFIG_OPENSBI_PREBUILT_FW_JUMP_PATH)
endif

.PHONY: all clean distclean

build:
	@rm -rf $(SDK_OPENSBI_BUILD_DIR)/opensbi.bin;
	@rm -rf $(SDK_OPENSBI_BUILD_DIR)/rtthread.bin;
	@rm -rf $(SDK_OPENSBI_SRC_DIR)/opensbi/rtthread.bin;
	@if [ ! -f $(SDK_BUILD_IMAGES_DIR)/rtsmart/rtthread.bin ]; then \
		echo "should run make rtsmart" && exit 1; \
	fi; \
	cp $(SDK_BUILD_IMAGES_DIR)/rtsmart/rtthread.bin $(SDK_OPENSBI_SRC_DIR)/opensbi/;

ifeq ($(CONFIG_OPENSBI_USE_PREBUILT_FW_JUMP),y)
	@echo "Using prebuilt fw_jump.bin instead of building OpenSBI..."
	@if [ ! -f $(SDK_PREBUILT_FW_JUMP_PATH) ]; then \
		echo "Prebuilt fw_jump.bin not found at $(SDK_PREBUILT_FW_JUMP_PATH)" && exit 1; \
	fi; \
	cp $(SDK_PREBUILT_FW_JUMP_PATH) $(SDK_OPENSBI_BUILD_DIR)/opensbi_fw_jump.bin;
	cp $(SDK_BUILD_IMAGES_DIR)/rtsmart/rtthread.bin $(SDK_OPENSBI_BUILD_DIR)/;
else
	@cd $(SDK_OPENSBI_SRC_DIR)/opensbi; \
	export PLATFORM=kendryte/fpgac908; \
	$(MAKE) -j$(NCPUS) O=$(SDK_OPENSBI_BUILD_DIR) OPENSBI_QUIET=1 CROSS_COMPILE=$(CROSS_COMPILE) || exit $?; \
	cp $(SDK_OPENSBI_BUILD_DIR)/platform/kendryte/fpgac908/firmware/fw_payload.bin $(SDK_OPENSBI_BUILD_DIR)/opensbi.bin; \
	cd -
endif

gen_image: build
	@$(SDK_OPENSBI_SRC_DIR)/gen_image

all: gen_image

clean:
	@rm -rf $(SDK_OPENSBI_BUILD_DIR)
	@rm -rf $(SDK_BUILD_IMAGES_DIR)/opensbi

distclean: clean
