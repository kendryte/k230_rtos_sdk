ifneq ($(MKENV_INCLUDED),1)
include mkenv.mk
endif

subdirs-y :=
include apps.mk

.PHONY: all clean distclean

all: $(subdirs-y)
	@echo "Make Applications done."

ifneq ($(strip $(subdirs-y)),)
.PHONY: $(subdirs-y)

$(subdirs-y):
	@echo "[BUILD] applications $@"
	@$(MAKE) -C $@ all || exit $?;
endif

clean:
	@if [ -n "$(subdirs-y)" ]; then \
		for dir in $(subdirs-y); do \
			echo "[CLEAN] applications $$dir"; \
			$(MAKE) -C $$dir clean || exit $?; \
		done; \
	fi

distclean: clean
	@if [ -n "$(subdirs-y)" ]; then \
		for dir in $(subdirs-y); do \
			echo "[DISTCLEAN] applications $$dir"; \
			$(MAKE) -C $$dir distclean || exit $?; \
		done; \
	fi

.PHONY: gen_kconfig
gen_kconfig:
	@echo "# Dynamic generate by Makefile, DO NOT Modify it.\n" > $(SDK_BUILD_DIR)/Kconfig.app; \
	for dir in $(shell find $(SDK_APPS_SRC_DIR) -maxdepth 1 -mindepth 1 -type d); do \
		echo "source \"$$dir/Kconfig\"" >> $(SDK_BUILD_DIR)/Kconfig.app; \
	done; \
