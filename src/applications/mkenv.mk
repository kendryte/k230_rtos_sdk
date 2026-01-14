ifneq ($(MKENV_INCLUDED),1)
export SDK_SRC_ROOT_DIR := $(realpath $(dir $(realpath $(lastword $(MAKEFILE_LIST))))/../../)
endif

include $(SDK_SRC_ROOT_DIR)/tools/mkenv.mk

include $(SDK_SRC_ROOT_DIR)/.config

export SDK_APPS_IMAGE_DIR := $(SDK_BUILD_IMAGES_DIR)/sdcard/app/

RM = rm -rf
ECHO = echo
CP = cp
MKDIR = mkdir
SED = sed
CAT = cat
TOUCH = touch
PYTHON = python3
ZIP = zip

export MKENV_INCLUDED_APPLICATIONS=1
