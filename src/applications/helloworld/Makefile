# Include base configuration
include ../mkenv.mk
include $(SDK_RTSMART_SRC_DIR)/libs/mk/toolchain_riscv64_musl.mk

# Build configuration
DIR 	:= $(shell basename `pwd`)
BUILD	:= $(SDK_APPS_BUILD_DIR)/$(DIR)
BIN 	:= $(SDK_APPS_IMAGE_DIR)/$(DIR)

# Source files handling
SRC_DIRS  := .

SRCS 	:= $(shell find $(SRC_DIRS) -maxdepth 1 -type f \( -name "*.c" -o -name "*.cpp" -o -name "*.cc" \))
OBJS	:= $(addprefix $(BUILD)/, $(addsuffix .o, $(basename $(notdir $(SRCS)))))
DEPS	:= $(OBJS:.o=.d)

# Directory creation logic - Captured and sorted
OBJ_DIRS  := $(sort $(dir $(OBJS) $(BIN)))

# Library configuration
include $(SDK_RTSMART_SRC_DIR)/libs/mk/libmpp.mk
include $(SDK_RTSMART_SRC_DIR)/libs/mk/libopencv.mk
include $(SDK_RTSMART_SRC_DIR)/libs/mk/libnncase.mk
include $(SDK_RTSMART_SRC_DIR)/libs/mk/librtsmart_hal.mk
include $(SDK_RTSMART_SRC_DIR)/libs/mk/lib3rdparty.mk

# Compiler flags
C_CXX_FLAGS := -fopenmp -march=rv64imafdcv -mabi=lp64d -mcmodel=medany -Os
C_CXX_FLAGS += -I. $(LIB_CFLAGS) -I$(SDK_SRC_ROOT_DIR)/include -include "generated/autoconf.h"
C_CXX_FLAGS += -Wall -Wextra -ffunction-sections -fdata-sections

CFLAGS 		:= $(C_CXX_FLAGS) -std=gnu99
CXX_FLAGS 	:= $(C_CXX_FLAGS)

# Linker flags
LDFLAGS := -T $(SDK_RTSMART_SRC_DIR)/libs/mk/link.lds --static -Wl,--gc-sections
LDFLAGS += $(LIB_LDFLAGS)

# Phony targets
.PHONY: all clean distclean

all: $(BIN)
	@$(ECHO) [BUILD] applications $(DIR) done.

.PHONY: .FORCE
.FORCE:

# Rule to link the final ELF - Order-only dependency on directory
$(BIN): $(OBJS) .FORCE | $(OBJ_DIRS)
	@echo "[LD] $@"
	$(Q)$(CXX) $(CFLAGS) $(OBJS) $(LDFLAGS) -o $@
	$(Q)$(STRIP) $@

# Rule for C objects - Order-only dependency on directory
vpath %.c $(SRC_DIRS)
$(BUILD)/%.o: %.c | $(OBJ_DIRS)
	@echo "[CC] $@"
	$(Q)$(CC) $(CFLAGS) -MD -MP -MF $(@:.o=.d) -c $< -o $@

# Rule for C++ objects - Order-only dependency on directory
vpath %.cc $(SRC_DIRS)
$(BUILD)/%.o: %.cc | $(OBJ_DIRS)
	@echo "[CXX] $@"
	$(Q)$(CXX) $(CXX_FLAGS) -MD -MP -MF $(@:.o=.d) -c $< -o $@

vpath %.cpp $(SRC_DIRS)
$(BUILD)/%.o: %.cpp | $(OBJ_DIRS)
	@echo "[CXX] $@"
	$(Q)$(CXX) $(CXX_FLAGS) -MD -MP -MF $(@:.o=.d) -c $< -o $@

# Actual directory creation rule
$(OBJ_DIRS):
	$(Q)mkdir -p $@

clean:
	@rm -rf $(BIN)

distclean: clean
	@rm -rf $(BUILD)

-include $(DEPS)
