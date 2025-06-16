# CanMV K230 Changelog

## v1.3

Version 1.3 introduces new image format support and build system improvements.

### Project Updates
- Added new `kdimg` image format support via genimage updates

## v1.3-RC2

Release candidate 2 for version 1.3 brings important fixes and stability improvements.

### Bug Fixes
#### **CanMV**
- Fixed `machine.I2C` module error handling
- Resolved `machine.FPIOA` pin function setting issues
- Corrected MicroPython HAL TX data errors

#### **RT-Smart**
- Fixed RTL8189 AP mode issues
- Resolved I2C transfer timeout problems

## v1.3-RC1

Initial release candidate for version 1.3 with significant enhancements across all components.

### New Features
#### **CanMV**
- Enhanced display capabilities
- Updated MicroPython port with additional modules
- Improved hardware abstraction layer

#### **MPP**
- Added IDR frame request interface (`kd_mapi_venc_request_idr`)
- Improved image flip and mirror functionality

#### **RT-Smart**
- Optimized task scheduling and memory management
- Expanded peripheral support (SPI, I2C)
- Filesystem reliability improvements

#### **U-Boot**
- Added support for `k230d_evb` board
- Optimized boot process

#### **New Component**
- Introduced `k230_rtsmart_lib` runtime support library

## v1.2.2

Version 1.2.2 introduces minor bug fixes and new features to enhance functionality and performance.

### New Features

#### **RT-Smart**
- Enhanced the `tsensor` driver with mutex support for improved concurrency and stability.

#### **CanMV**
- Added support for a new MIPI panel with a resolution of 368x552.
- Introduced the `machine.chipid` and `machine.temperature` APIs for accessing unique device identifiers and temperature data.
- Implemented `os.urandom` for generating random bytes and `os.statvfs` for retrieving filesystem statistics.

### Bug Fixes

#### **RT-Smart**
- Resolved an issue where the MTP could not monitor the `data` partition effectively.

#### **CanMV**
- Fixed a bug that caused sensor snapshot failures when the sensor channel was bound to display.

## v1.2.1

Version 1.2.1 is a minor bug fix for v1.2

### Bug Fixes

- **CanMV**:
  - Fix sensor and display release vb, now can remove try and catch block
  - Fix machine.I2C

## v1.2

Version 1.2 brings several new features, improvements, and bug fixes to the project. This update focuses on RTOS support, new hardware support, and various enhancements across the CanMV, RT-Smart, MPP, and U-Boot components.

### Project Updates

- **RTOS Only SDK**: Added support for RTOS-only SDK build sample code and AI demo compile support.
- **New Board Support**: Added support for board **ATK-DNK230D**.

### New Features

- **CanMV**:
  - Added **soft I2C support** for software-driven I2C communication.
  - Added **SPI LCD driver** support for SPI-based LCD displays.
  - Integrated **Audio 3A support** for improved audio processing.
  - Expanded **hardware support** with new boards, including **ATK-DNK230D**.
  - Added **MIPI DSI debugger support** for debugging MIPI DSI displays.
  - Introduced new **machine.TOUCH module** for touchscreen functionality.
  - New board type format added to display **board memory size**.

- **RT-Smart**:
  - Added **dynamic memory size detection** support.
  - Integrated support for **4G module (EC200M)**.
  - Added **probe support for touch devices**, including a new driver for **CHCS5XXX**.
  - Introduced **FPIOA driver** for flexible I/O array support.
  - Added **USB host split** support.
  - Improved project structure to allow users to **specify custom app folder**.
  - Added support for **resizing GPT partitions**.

- **MPP**:
  - Added **MIPI DSI debugger support** for debugging MIPI DSI displays.
  - Added support for new **sensor models (bf3238, sc132gs)**.
  - Added support for new **2.4-inch, 480x640 LCD** display.
  - Added **build sample support** for MPP.

- **U-Boot**:
  - Added **dynamic memory size detection**.
  - Integrated support for new **boards** including **ATK-DNK230D**.
  - Enhanced **Kburn OTP support**.

### Bug Fixes

- **CanMV**:
  - Fixed **sensor MCM mode error**.
  - Fixed **LVGL pixel format** handling issue.
  - Resolved **SPI driver** issues.
  - Fixed **UART driver** communication problems.
  - Corrected **machine.PWM duty** cycle error.
  - Fixed **NN image inference error**.

- **RT-Smart**:
  - Fixed issues with **SPI driver**.
  - Corrected **I2C driver** issues.
  - Resolved **UART driver** bugs.
  - Fixed **CherryUSB** functionality.

- **MPP**:
  - Fixed **sensor register configuration** for **GC2093**, **OV5647**, and **IMX335**.
  - Fixed **LCD timing** for 3.5-inch 480x800 ST7701 display.

## v1.1

Version 1.1 is a complete overhaul for the K230 platform, designed to be more user-friendly and development-oriented.

### Project Updates

- **Repo Management**: Subprojects are now managed with `repo`.
- **Dependencies**: Linux dependencies have been removed.
- **Build System**: Introduction of a new compilation system.
- **Board Support**: Added support for new boards, including DonshanPI, LCKFB, and others.

### New Features

- **CanMV**:
  - Added support for WS2812 LEDs via GPIO.
  - Network support: Ethernet and Wi-Fi.
  - New board support: DonshanPI, LCKFB, etc.
  - Added support for a new display panel: ILI9806.
  - Audio module update: Added volume control capabilities.
  
- **RT-Smart**:
  - Automatic partition creation and mounting to `/data`.
  - Project management via Kconfig.
  - Added support for WS2812 LEDs via GPIO.
  - Added support for I2C slave mode.
  - Ethernet-over-USB support with RTL8152.
  - WLAN support: RTL8189 and CYW43xx.
  - Added support for NTP (Network Time Protocol).

- **MPP (Multi-Processor Platform)**:
  - Sensor driver framework updated, now support GC2093, OV5647, and IMX335.
  - Updated screen driver framework.

- **U-Boot**:
  - New `kburn` tool, no longer dependent on DRAM.
  - Added support for new boards: DonshanPI, LCKFB, and more.

### Bug Fixes

- **CanMV**:
  - Fixed IOMUX pins (36, 37).
  - Released UART3 for user access.

- **RT-Smart**:
  - Fixed missing I2C, SPI, and UART device nodes.
