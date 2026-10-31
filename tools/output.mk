# Run once for all requested goals, preserving recursive make's flags/jobserver.
.DEFAULT_GOAL := __sdk_dispatch
.PHONY: __sdk_dispatch $(MAKECMDGOALS)
__sdk_dispatch:
	+@python3 "$(SDK_SRC_ROOT_DIR)/tools/sdk_output.py" \
		--root "$(SDK_SRC_ROOT_DIR)" --output "$(SDK_DISPATCH_OUTPUT)" \
		--make "$(MAKE)" -- $(MAKECMDGOALS)

ifneq ($(strip $(MAKECMDGOALS)),)
$(MAKECMDGOALS): __sdk_dispatch
	@:
endif
