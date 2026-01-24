# RTOS Only K230 Changelog

## K230 RTOS SDK Release Notes v0.6

We are pleased to announce the release of **K230 RTOS SDK v0.6**. This version introduces significant enhancements to the Media Process Platform (MPP), expands driver support for the RT-Smart kernel, and improves overall system stability and performance.

### 🚀 Key Highlights

* **Advanced Audio Features:** Integrated Audio 3A (AEC, ANS, AGC) and support for G.711A/U encoding/decoding.
* **Enhanced Video Pipeline:** Added multi-channel video encoding (VENC) and improved VICAP scaling/cropping capabilities.
* **New Hardware Support:** Introduced support for the `k230d_evb` board and additional display panels.
* **RT-Smart Kernel Maturity:** Improved driver frameworks (Serial, I2C, SPI) and added syscalls for enhanced POSIX compatibility.

---

### 📦 Component Updates

#### 1. RT-Smart (Kernel)

* **New Drivers:** Added support for `onewire` (DS18x20) and `ws2812` LED drivers.
* **System Enhancements:** * Enabled `romfs` support for efficient read-only file systems.
* Added `statfs` syscall.
* Optimized memory management and task scheduling.


* **Network:** Updated `netmgmt` drivers and adapted CDC/EC200M (4G) modules to the serial framework.
* **Debugging:** Added VO (Video Output) debug tools and OSD enable/disable controls.

#### 2. MPP (Media Process Platform)

* **Video Encoding (VENC):**
* Added multi-channel encoding demos.
* Added support for rotation and mirroring in the encoding pipeline.
* Introduced `VENC_2D` for picture framing and OSD overlay.


* **Video Input (VICAP):** Updated usage instructions and enabled multi-channel output with hardware scaling and cropping.
* **Audio (AENC/ADEC):** * Added G.711A/U codec support.
* Enabled binding for Audio Input (AI) to Audio Encoder (AENC) and Audio Decoder (ADEC) to Audio Output (AO).
* **Audio 3A:** Integration of Acoustic Echo Cancellation (AEC), Automatic Noise Suppression (ANS), and Automatic Gain Control (AGC).



#### 3. RT-Smart Libraries & Examples

* **Libraries:**
* Integrated the `mqttclient` 3rd-party library.
* Added HAL support for `netmgmt`, `statfs`, and `reset_to_bootloader`.
* Enhanced driver wrappers for UART, PWM, ADC, and I2C.


* **Examples:**
* **AI+RTSP Demos:** Added new demos for AI-powered RTSP streaming.
* **Media Demos:** Added `vi -> venc -> MAPI -> small core` file saving example.
* **CV Lite:** Introduced the `cv_lite` module with vision functions (corner detection, undistort, rects).



#### 4. U-Boot & Board Support

* **Boot Optimization:** Improved boot speed and updated prebuilt binaries.
* **New Boards:** Added configurations for `k230d_evb` and updated `junroc` support.
* **Panels:** Added support for `nt35516` and `nt35532` display panels.

---

### 🛠 Bug Fixes & Improvements

* **Stability:** Fixed USB CDC 100ms stall issues and `lsusb -t` crash bugs.
* **Drivers:** Resolved I2C transfer timeouts and fixed `drv_touch` interrupt handling.
* **Memory:** Fixed various `malloc` handling issues and `lwp_pmutex` bugs.
* **Build System:** Improved GitHub Actions workflows and updated repo management tools.

---

### ⚠️ Important Notice for Developers

This version is tagged as **legacy** because it represents the "end of an era" for the current SDK structure.

* **Current Projects:** If you are in the middle of a product cycle, stay on this version.
* **New Projects:** Be aware that the next major version will likely feature a different repository structure or breaking API changes.

---

### 🔗 Repository Links

* [[k230_rtos_sdk](https://github.com/kendryte/k230_rtos_sdk/releases/tag/rtos-v0.6)](https://github.com/kendryte/k230_rtos_sdk/releases/tag/rtos-v0.6)
* [[rtsmart](https://github.com/canmv-k230/rtsmart/releases/tag/rtos-v0.6)](https://github.com/canmv-k230/rtsmart/releases/tag/rtos-v0.6)
* [[mpp](https://github.com/canmv-k230/mpp/releases/tag/rtos-v0.6)](https://github.com/canmv-k230/mpp/releases/tag/rtos-v0.6)
* [[k230_rtsmart_lib](https://github.com/canmv-k230/k230_rtsmart_lib/releases/tag/rtos-v0.6)](https://github.com/canmv-k230/k230_rtsmart_lib/releases/tag/rtos-v0.6)
* [[k230_rtsmart_examples](https://github.com/canmv-k230/k230_rtsmart_examples/releases/tag/rtos-v0.6)](https://github.com/canmv-k230/k230_rtsmart_examples/releases/tag/rtos-v0.6)
* [[u-boot](https://github.com/canmv-k230/u-boot/releases/tag/rtos-v0.6)](https://github.com/canmv-k230/u-boot/releases/tag/rtos-v0.6)

**Full Changelog**: https://github.com/kendryte/k230_rtos_sdk/compare/v0.5...v0.6

## 🚀 RTOS Only K230 `rtos-v0.5` Release Notes

We are excited to announce the **rtos-v0.5** release of the CanMV K230 platform — a major milestone focused on **RT-Thread-based development**, board enablement, and driver refactoring. This release includes extensive improvements across all core components and new board support, making it ideal for real-time and embedded scenarios.

---

### 🧠 CanMV Core Platform

While this release primarily targets RT-Thread integration, it builds on top of the stable `canmv-v1.3` release. For foundational changes, see the [v1.3 release notes](https://github.com/kendryte/canmv_k230/releases/tag/v1.3).

---

### ⚙️ RT-Smart OS

* **Board Support**:

  * Added support for `rtt_evb` and `junroc` boards.
* **UART Improvements**:

  * Enabled fractional baud rate divisor (DLF) for better accuracy.
  * Refactored UART driver to use RT-Thread serial framework.
  * Improved `putc()` timeout logic.
* **Touch & Peripheral Drivers**:

  * Added FT5406 touch panel driver.
  * Added initial pinmux module and config updates.
  * Refactored `drv_pwm` and `drv_rtc`, improved reliability.
* **System Improvements**:

  * Better default driver/component init levels.
  * Enhanced NTP time sync handling.
  * Fixed boot failure issues on `evb` board.
  * OSPI fixes for chip select handling.
* **Code Cleanup**:

  * Reverted unintentional RTC defaults.
  * Merged multiple dev branches for platform stabilization.

[🔗 Full Changelog](https://github.com/canmv-k230/rtsmart/compare/canmv-v1.3...rtos-v0.5)

---

### 📦 k230\_rtsmart\_lib

* **New HAL Drivers**:

  * Added new UART, SPI, PWM, GPIO, FPIOA, WDT, and SBUS HAL drivers.
  * External SPI CS pin control supported.
* **Test Infrastructure**:

  * Introduced test cases for SPI (ST7789), GPIO, SBUS, timers, and FPIOA.
* **Fixes & Improvements**:

  * Fixed crash caused by invalid GPIO instance.
  * Fixed FPIOA bugs and driver warnings.
  * Added face\_liveness.kmodel as part of the testing set.

[🔗 Full Changelog](https://github.com/canmv-k230/k230_rtsmart_lib/compare/canmv-v1.3...rtos-v0.5)

---

### 🎥 MPP (Media Processing Platform)

* **Display Support**:

  * Added driver for NT35516 display.
* **Sensor Fixes**:

  * Fixed GC2093 sensor configuration issues.
* **RTT Compatibility**:

  * Improved build config for RT-Smart-based systems.

[🔗 Full Changelog](https://github.com/canmv-k230/mpp/compare/canmv-v1.3...rtos-v0.5)

---

### 🛠️ U-Boot Bootloader

* **Board Support**:

  * Added support for `rtt_evb` and `junroc` boards.
* **RTOS Integration**:

  * Added support for building and pushing prebuilt U-Boot images to `k230_rtos_sdk`.
* **Driver Improvements**:

  * Updated SDHCI driver for better stability.

[🔗 Full Changelog](https://github.com/canmv-k230/u-boot/compare/canmv-v1.3...rtos-v0.5)

---

### 📈 Full Changelog

| Repository       | Compare Link                                                                                            |
| ---------------- | ------------------------------------------------------------------------------------------------------- |
| **rtsmart**      | [canmv-v1.3...rtos-v0.5](https://github.com/canmv-k230/rtsmart/compare/canmv-v1.3...rtos-v0.5)          |
| **rtsmart\_lib** | [canmv-v1.3...rtos-v0.5](https://github.com/canmv-k230/k230_rtsmart_lib/compare/canmv-v1.3...rtos-v0.5) |
| **mpp**          | [canmv-v1.3...rtos-v0.5](https://github.com/canmv-k230/mpp/compare/canmv-v1.3...rtos-v0.5)              |
| **u-boot**       | [canmv-v1.3...rtos-v0.5](https://github.com/canmv-k230/u-boot/compare/canmv-v1.3...rtos-v0.5)           |

---

### 📝 Summary

The `rtos-v0.5` release focuses on transitioning the CanMV K230 platform toward **real-time RTOS workflows**. It introduces new drivers, boards, HAL libraries, and debugging infrastructure essential for embedded systems work. This sets the stage for future development with tight real-time constraints and modular software stacks.

We encourage developers working with RT-Thread to upgrade and try out the new platform capabilities.

For questions, contributions, or bug reports, visit our [GitHub organization](https://github.com/kendryte/canmv_k230).
