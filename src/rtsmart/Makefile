ifneq ($(MKENV_INCLUDED),1)
export SDK_SRC_ROOT_DIR := $(realpath $(dir $(realpath $(lastword $(MAKEFILE_LIST))))/../../)
endif

include $(SDK_SRC_ROOT_DIR)/tools/mkenv.mk

include $(SDK_TOOLS_DIR)/toolchain_rtsmart.mk

include $(SDK_SRC_ROOT_DIR)/.config

ifneq ($(shell [ -d ${SDK_BUILD_IMAGES_DIR}/rtsmart ] && echo 1 || echo 0),1)
$(shell mkdir -p ${SDK_BUILD_IMAGES_DIR}/rtsmart)
endif

ifneq ($(shell [ -d ${SDK_BUILD_IMAGES_DIR}/bin/ ] && echo 1 || echo 0),1)
$(shell mkdir -p ${SDK_BUILD_IMAGES_DIR}/bin/)
endif

ifneq ($(shell [ -d ${SDK_BUILD_IMAGES_DIR}/sdcard/ ] && echo 1 || echo 0),1)
$(shell mkdir -p ${SDK_BUILD_IMAGES_DIR}/sdcard/)
endif

.PHONY: all clean distclean menuconfig

.parse_config:
	@export RTT_CC=gcc; \
	export RTT_CC_PREFIX=$(CROSS_COMPILE_PREFIX); \
	export RTT_EXEC_PATH=$(CROSS_COMPILE_DIR); \
	export RTSMART_SRC_DIR=$(SDK_RTSMART_SRC_DIR)/rtsmart; \
	export RTT_SDK_BUILD_DIR=$(SDK_RTSMART_BUILD_DIR); \
	export MPP_SRC_DIR=$(SDK_RTSMART_SRC_DIR)/mpp; \
	cp -f $(SDK_SRC_ROOT_DIR)/include/generated/autoconf.h $(SDK_RTSMART_SRC_DIR)/mpp/include/comm/k_autoconf_comm.h; \
	cp -f $(SDK_SRC_ROOT_DIR)/include/generated/autoconf.h $(SDK_RTSMART_SRC_DIR)/rtsmart/kernel/bsp/maix3/k_autoconf_comm.h; \
	cd $(SDK_RTSMART_SRC_DIR)/rtsmart/kernel/bsp/maix3; \
	if [ ! -f configs/${RTSMART_DEFCONFIG} ]; then \
		echo "Error: Configuration file '${RTSMART_DEFCONFIG}' not found."; \
		echo "Please ensure that '${RTSMART_DEFCONFIG}' exists in the 'configs' directory."; \
		exit 1; \
	fi; \
	rm -rf rtconfig.h; \
	scons --useconfig=configs/${RTSMART_DEFCONFIG} || exit $?; \
	cd -; \
	touch .parse_config

.PHONY: kernel
kernel: .parse_config
	@$(SDK_TOOLS_DIR)/gen_verinfo_h.sh $(SDK_RTSMART_SRC_DIR)/rtsmart/kernel/bsp/maix3/sdk_version.h
	@export RTT_CC=gcc; \
	export RTT_CC_PREFIX=$(CROSS_COMPILE_PREFIX); \
	export RTT_EXEC_PATH=$(CROSS_COMPILE_DIR); \
	export RTSMART_SRC_DIR=$(SDK_RTSMART_SRC_DIR)/rtsmart; \
	export RTT_SDK_BUILD_DIR=$(SDK_RTSMART_BUILD_DIR); \
	export MPP_SRC_DIR=$(SDK_RTSMART_SRC_DIR)/mpp; \
	cd $(SDK_RTSMART_SRC_DIR)/rtsmart/kernel/bsp/maix3; \
	rm -f rtthread.{elf,bin}; \
	scons -j$(NCPUS) || exit $?; \
	cp rtthread.bin ${SDK_BUILD_IMAGES_DIR}/rtsmart; \
	cd -;

.PHONY: mpp
mpp:
	@export PATH="$(CROSS_COMPILE_DIR):$(PATH)"; \
	export MPP_SRC_DIR=$(SDK_RTSMART_SRC_DIR)/mpp; \
	export RTSMART_SRC_DIR=$(SDK_RTSMART_SRC_DIR)/rtsmart; \
	export MPP_BUILD_DIR=$(SDK_RTSMART_BUILD_DIR)/mpp; \
	$(MAKE) -C $(SDK_RTSMART_SRC_DIR)/mpp/kernel -j$(NCPUS) || exit $?; \
	$(MAKE) -C $(SDK_RTSMART_SRC_DIR)/mpp/userapps/src -j$(NCPUS) || exit $?; \
	$(MAKE) -C $(SDK_RTSMART_SRC_DIR)/mpp/middleware/src -j$(NCPUS) || exit $?; \

.PHONY: libs
libs:
	@$(MAKE) -C $(SDK_RTSMART_SRC_DIR)/libs -j$(NCPUS) all || exit $?;

.PHONY: examples
examples:
ifneq ($(CONFIG_SDK_ENABLE_CANMV),y)

ifeq ($(CONFIG_MPP_ENABLE_USERAPPS_SAMPLES),y)
	@export PATH="$(CROSS_COMPILE_DIR):$(PATH)"; \
	export MPP_SRC_DIR=$(SDK_RTSMART_SRC_DIR)/mpp; \
	export RTSMART_SRC_DIR=$(SDK_RTSMART_SRC_DIR)/rtsmart; \
	export MPP_BUILD_DIR=$(SDK_RTSMART_BUILD_DIR)/mpp; \
	$(MAKE) -C $(SDK_RTSMART_SRC_DIR)/mpp/userapps/sample -j$(NCPUS) all || exit $?;
endif

ifeq ($(CONFIG_MPP_ENABLE_MIDDLEWARE_SAMPLES),y)
	@export PATH="$(CROSS_COMPILE_DIR):$(PATH)"; \
	export MPP_SRC_DIR=$(SDK_RTSMART_SRC_DIR)/mpp; \
	export RTSMART_SRC_DIR=$(SDK_RTSMART_SRC_DIR)/rtsmart; \
	export MPP_BUILD_DIR=$(SDK_RTSMART_BUILD_DIR)/mpp; \
	$(MAKE) -C $(SDK_RTSMART_SRC_DIR)/mpp/middleware/sample -j$(NCPUS) all || exit $?;
endif

ifeq ($(CONFIG_RTT_ENABLE_BUILD_EXAMPLES),y)
	@$(MAKE) -C $(SDK_RTSMART_SRC_DIR)/examples -j$(NCPUS) all || exit $?;
endif

endif

.PHONY: kernel-clean
kernel-clean:
	@export RTT_CC=gcc; \
	export RTT_CC_PREFIX=$(CROSS_COMPILE_PREFIX); \
	export RTT_EXEC_PATH=$(CROSS_COMPILE_DIR); \
	export RTSMART_SRC_DIR=$(SDK_RTSMART_SRC_DIR)/rtsmart; \
	export RTT_SDK_BUILD_DIR=$(SDK_RTSMART_BUILD_DIR); \
	export MPP_SRC_DIR=$(SDK_RTSMART_SRC_DIR)/mpp; \
	cd $(SDK_RTSMART_SRC_DIR)/rtsmart/kernel/bsp/maix3; \
	rm -f rtthread.elf .config .config.old k_autoconf_comm.h link_stacksize.lds link.lds rtconfig.h; \
	scons -c || exit $?; \
	cd -; \
	rm -rf ${SDK_BUILD_IMAGES_DIR}/rtsmart;

.PHONY: mpp-clean
mpp-clean:
	@export PATH="$(CROSS_COMPILE_DIR):$(PATH)"; \
	export MPP_SRC_DIR=$(SDK_RTSMART_SRC_DIR)/mpp; \
	export RTSMART_SRC_DIR=$(SDK_RTSMART_SRC_DIR)/rtsmart; \
	export MPP_BUILD_DIR=$(SDK_RTSMART_BUILD_DIR)/mpp; \
	$(MAKE) -C $(SDK_RTSMART_SRC_DIR)/mpp/kernel clean || exit $?; \
	$(MAKE) -C $(SDK_RTSMART_SRC_DIR)/mpp/userapps/src clean || exit $?; \
	$(MAKE) -C $(SDK_RTSMART_SRC_DIR)/mpp/userapps/sample clean || exit $?; \
	$(MAKE) -C $(SDK_RTSMART_SRC_DIR)/mpp/middleware/src clean || exit $?; \
	$(MAKE) -C $(SDK_RTSMART_SRC_DIR)/mpp/middleware/sample clean || exit $?; \
	rm -rf .mpp_built .mpp_samples; \
	rm -rf $(SDK_RTSMART_SRC_DIR)/rtsmart/userapps/root/bin

.PHONY: libs-clean
libs-celan:
	@$(MAKE) -C $(SDK_RTSMART_SRC_DIR)/libs clean || exit $?;

.PHONY: examples-clean
examples-clean:
ifneq ($(CONFIG_SDK_ENABLE_CANMV),y)

ifeq ($(CONFIG_RTT_ENABLE_BUILD_EXAMPLES),y)
	@$(MAKE) -C $(SDK_RTSMART_SRC_DIR)/examples clean || exit $?;
endif

endif

ALL_TARGETS := .parse_config mpp libs examples

ifneq ($(CONFIG_RTSMART_ENABLE_ROMFS),y)
ALL_TARGETS += kernel
endif

all: $(ALL_TARGETS)
	@echo "Copy sensor configs from $(SDK_RTSMART_SRC_DIR)/rtsmart/userapps/root/bin/ to ${SDK_BUILD_IMAGES_DIR}/bin/"

ifeq ($(CONFIG_MPP_ENABLE_SENSOR_GC2093),y)
	@rsync -a --delete $(SDK_RTSMART_SRC_DIR)/rtsmart/userapps/root/bin/gc2093-* ${SDK_BUILD_IMAGES_DIR}/bin/
endif
ifeq ($(CONFIG_MPP_ENABLE_SENSOR_OV5647),y)
	@rsync -a --delete $(SDK_RTSMART_SRC_DIR)/rtsmart/userapps/root/bin/ov5647-* ${SDK_BUILD_IMAGES_DIR}/bin/
endif
ifeq ($(CONFIG_MPP_ENABLE_SENSOR_IMX335),y)
	@rsync -a --delete $(SDK_RTSMART_SRC_DIR)/rtsmart/userapps/root/bin/imx335-* ${SDK_BUILD_IMAGES_DIR}/bin/
endif
ifeq ($(CONFIG_MPP_ENABLE_SENSOR_SC132GS),y)
	@rsync -a --delete $(SDK_RTSMART_SRC_DIR)/rtsmart/userapps/root/bin/sc132gs-* ${SDK_BUILD_IMAGES_DIR}/bin/
endif
ifeq ($(CONFIG_MPP_ENABLE_SENSOR_XS9950),y)
	@rsync -a --delete $(SDK_RTSMART_SRC_DIR)/rtsmart/userapps/root/bin/xs9950-* ${SDK_BUILD_IMAGES_DIR}/bin/
endif
ifeq ($(CONFIG_MPP_ENABLE_SENSOR_BF3238),y)
	@rsync -a --delete $(SDK_RTSMART_SRC_DIR)/rtsmart/userapps/root/bin/bf3238-* ${SDK_BUILD_IMAGES_DIR}/bin/
endif

ifneq ($(CONFIG_SDK_ENABLE_CANMV),y)

ifeq ($(CONFIG_MPP_ENABLE_USERAPPS_SAMPLES),y)
	@echo "Copy mpp userapps sample."
	$(call sync_dir, $(SDK_RTSMART_SRC_DIR)/mpp/userapps/sample/elf/, $(SDK_BUILD_IMAGES_DIR)/sdcard/app/userapps/)
endif

ifeq ($(CONFIG_MPP_ENABLE_MIDDLEWARE_SAMPLES),y)
	@echo "Copy mpp middleware sample."
	$(call sync_dir, $(SDK_RTSMART_SRC_DIR)/mpp/middleware/elf/, $(SDK_BUILD_IMAGES_DIR)/sdcard/app/middleware/)
endif

ifeq ($(CONFIG_RTT_ENABLE_BUILD_EXAMPLES),y)
	@echo "Copy rtsmart examples."
	$(call sync_dir, $(SDK_RTSMART_SRC_DIR)/examples/elf/, $(SDK_BUILD_IMAGES_DIR)/sdcard/app/examples/)
endif

endif

ifeq ($(CONFIG_RTSMART_COPY_LIBS_TEST),y)
	@echo "Copy rtsmart libs examples."
	$(call sync_dir, $(SDK_RTSMART_BUILD_DIR)/libs/elf/, $(SDK_BUILD_IMAGES_DIR)/sdcard/app/rtsmart_libs_tests/)
endif

	@echo "Generate ${SDK_BUILD_IMAGES_DIR}/bin/config.txt"
	@$(SDK_SRC_ROOT_DIR)/src/rtsmart/gen_config

clean: mpp-clean kernel-clean libs-celan examples-clean
	@rm -rf .parse_config
	@rm -rf ${SDK_BUILD_IMAGES_DIR}/rtsmart

distclean: clean

menuconfig:
	@rm -rf .parse_config
	@rm -rf ${SDK_BUILD_IMAGES_DIR}/rtsmart
	@export RTT_CC=gcc; \
	export RTT_CC_PREFIX=$(CROSS_COMPILE_PREFIX); \
	export RTT_EXEC_PATH=$(CROSS_COMPILE_DIR); \
	export RTSMART_SRC_DIR=$(SDK_RTSMART_SRC_DIR)/rtsmart; \
	export RTT_SDK_BUILD_DIR=$(SDK_RTSMART_BUILD_DIR); \
	export MPP_SRC_DIR=$(SDK_RTSMART_SRC_DIR)/mpp; \
	cd $(SDK_RTSMART_SRC_DIR)/rtsmart/kernel/bsp/maix3; \
	rm -rf rtconfig.h .config .config.old; \
	scons --useconfig=configs/${RTSMART_DEFCONFIG} || exit $?; \
	scons --genconfig; \
	scons --menuconfig; \
	cp .config configs/${RTSMART_DEFCONFIG}; \
	cd -;

.PHONY: arduino-sdk arduino-sdk-clean arduino-sdk-distclean
arduino-sdk:
	@rm -rf $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib/**
	@rm -rf $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/include/**

	# Copy 3rd-party include and libraries
	@mkdir -p $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/include/3rd_party
	@mkdir -p $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib-3rd_party
	@cp -rf $(SDK_RTSMART_BUILD_DIR)/libs/3rd-party/include/* $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/include/3rd_party/
	@cp -rf $(SDK_RTSMART_BUILD_DIR)/libs/3rd-party/lib/* $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib-3rd_party/
	@python3 $(SDK_TOOLS_DIR)/merge_libs.py \
		--toolchain-prefix $(CROSS_COMPILE) \
		--input $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib-3rd_party \
		--output $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib/lib3rd_party.a || exit $?;
	@rm -rf $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib-3rd_party

	# Copy rtsmart_hal include and libraries
	@mkdir -p $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/include/rtsmart_hal
	@mkdir -p $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib-rtsmart_hal
	@cp -rf $(SDK_RTSMART_BUILD_DIR)/libs/rtsmart_hal/include/* $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/include/rtsmart_hal/
	@cp -rf $(SDK_RTSMART_BUILD_DIR)/libs/rtsmart_hal/lib/* $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib-rtsmart_hal/
	@python3 $(SDK_TOOLS_DIR)/merge_libs.py \
		--toolchain-prefix $(CROSS_COMPILE) \
		--input $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib-rtsmart_hal \
		--output $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib/librtsmart_hal.a || exit $?;
	@rm -rf $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib-rtsmart_hal

	# Copy mpp include and libraries
	@mkdir -p $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/include/mpp
	@mkdir -p $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/include/mpp/api
	@mkdir -p $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib-mpp
	@cp -rf $(SDK_RTSMART_SRC_DIR)/mpp/include/* $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/include/mpp/
	@cp -rf $(SDK_RTSMART_SRC_DIR)/mpp/userapps/api/* $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/include/mpp/api/
	@cp -rf $(SDK_RTSMART_SRC_DIR)/mpp/userapps/lib/* $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib-mpp/

	@python3 $(SDK_TOOLS_DIR)/merge_libs.py \
		--toolchain-prefix $(CROSS_COMPILE) \
		--input $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib-mpp \
		--output $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib/libmpp.a || exit $?;
	@rm -rf $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib-mpp

	# Copy opencv include and libraries
	@mkdir -p $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/include/opencv4
	@cp -rf $(SDK_RTSMART_SRC_DIR)/libs/opencv/include/* $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/include/

	@mkdir -p $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib-opencv
	@cp -rf $(SDK_RTSMART_SRC_DIR)/libs/opencv/lib/*.a $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib-opencv/
	@python3 $(SDK_TOOLS_DIR)/merge_libs.py \
		--toolchain-prefix $(CROSS_COMPILE) \
		--input $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib-opencv \
		--output $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib/libopencv.a || exit $?;
	@rm -rf $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib-opencv

	@mkdir -p $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib-opencv-3rdparty
	@cp -rf $(SDK_RTSMART_SRC_DIR)/libs/opencv/lib/opencv4/3rdparty/*.a $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib-opencv-3rdparty/
	@python3 $(SDK_TOOLS_DIR)/merge_libs.py \
		--toolchain-prefix $(CROSS_COMPILE) \
		--input $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib-opencv-3rdparty \
		--output $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib/libopencv_3rdparty.a || exit $?;
	@rm -rf $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib-opencv-3rdparty

	# Copy openblas include and libraries
	@mkdir -p $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/include/openblas
	@cp -rf $(SDK_RTSMART_SRC_DIR)/libs/openblas/include/* $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/include/openblas/
	@cp -rf $(SDK_RTSMART_SRC_DIR)/libs/openblas/lib/*.a $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib/

	# Copy nncase include and libraries
	@mkdir -p $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/nncase/
	@cp -rf $(SDK_RTSMART_SRC_DIR)/libs/nncase/riscv64/* $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/nncase/

	@echo "Generate Arduino-core sdk done."

arduino-sdk-clean:
	@rm -rf $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/lib/**
	@rm -rf $(SDK_ARDUINO_SDK_BUILD_DIR)/cores/k230/sdk/include/**

arduino-sdk-distclean: arduino-sdk-clean
