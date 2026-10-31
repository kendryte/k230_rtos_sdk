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
	@$(MAKE) -C $@ all
endif

clean:
	@if [ -n "$(subdirs-y)" ]; then \
		for dir in $(subdirs-y); do \
			echo "[CLEAN] applications $$dir"; \
			$(MAKE) -C $$dir clean || exit $$?; \
		done; \
	fi

distclean: clean
	@if [ -n "$(subdirs-y)" ]; then \
		for dir in $(subdirs-y); do \
			echo "[DISTCLEAN] applications $$dir"; \
			$(MAKE) -C $$dir distclean || exit $$?; \
		done; \
	fi

.PHONY: gen_kconfig
gen_kconfig:
	@set -e; \
	output="$(SDK_BUILD_DIR)/Kconfig.app"; \
	temporary=$$(mktemp "$$output.XXXXXX"); \
	trap 'rm -f "$$temporary"' EXIT HUP INT TERM; \
	echo "# Dynamic generate by Makefile, DO NOT Modify it." > "$$temporary"; \
	for dir in $(sort $(wildcard $(SDK_APPS_SRC_DIR)/*/)); do \
		echo "source \"$${dir}Kconfig\"" >> "$$temporary"; \
	done; \
	cmp -s "$$temporary" "$$output" || mv "$$temporary" "$$output"
