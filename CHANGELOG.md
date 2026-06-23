# RTOS Only K230 Changelog

## K230 RTOS SDK Release Notes v0.8

We are pleased to announce the release of **K230 RTOS SDK v0.8**. This release expands board and sensor support, improves Secure Boot and image generation, adds new RT-Smart drivers and HAL features, updates AI and media components, and brings many stability and performance improvements across USB, networking, storage, display, and examples.

### 🚀 Key Highlights

* **New Board Support:** Added support for `k230_canmv_mrt`, `k230d_labplus_ai_camera_v2`, `k230d_canmv_lushanpi_lite`, Yahboom, WonderMK updates, and additional DongshanPi LPDDR4 configuration.
* **Secure Boot & OTP/PUF:** Added Secure Boot support, trusted preload validation, OTP security configuration, and PUFs cryptography support with related examples.
* **Display & Sensor Expansion:** Added OV13850(4K) support, Added Manual AE&GAIN Tune, And ISP Sense Switch, SPI/I8080 panel framework improvements, NV3030B QSPI LCD support, DSI lane-rate configuration, HDMI timing updates, and board-specific panel fixes.
* **Storage & Filesystem Improvements:** Added exFAT support, file preallocation support, SDIO/HS200 improvements, second MMC mounting, partition alignment, SPI NAND image generation, and SDCARD image configuration updates. **NOW, FileSystem Read and Write Speed have a big Improve.**
* **USB, HID & Networking:** Added OTG support for K230D, dual CDC ports, HID keyboard/mouse support, UVC RVV acceleration, additional UVC GUID formats, and expanded LWIP configuration.
* **AI, Runtime & Examples:** Updated AI examples to `nncase` runtime **2.11.0**, moved kmodel packaging to a separate repo, added multi-source AI analyzer, VICAP sensor, triple-camera RTSP, FFT visualizer, PMU, GZIP, cJSON, OTP, and security test examples.

---

### 📦 Component Updates

#### 1. RT-Smart (Kernel)

* **Board & Configuration:** Added K230D LushanPi Lite board configuration, K230 CanMV MRT board support, K230D LabPlus AI Camera v2 support, and low-power configuration for `k230d_labplus_ai_camera*`.
* **USB & HID:** Added K230D OTG support, dual CDC ports, HID class support for Cherry USB devices, USB host validation improvements, USB network stop-request handling, and UVC host RVV acceleration/profiling.
* **Storage & Filesystem:** Added exFAT support in FatFs, `dfs_elm` preallocation through `f_expand`, second MMC card mounting, SDIO erase-group/status support, and SDIO0 HS200 support.
* **Security:** Added Secure Boot trusted preload handling and validation, OTP byte-order contract preservation for PUFS RT/CDE drivers, and PUF firmware CDE/RVV memory operation updates.
* **Drivers:** Added PMU, FFT, GZIP decompression, ACodec headphone detection, Sitronix CF1124 touch, Synopsys DesignWare SSI private register definitions, and built-in GPIO MSH test commands.
* **Networking:** Increased LWIP configuration parameters across device defconfigs and raised maximum WLAN password length from 32 to 64 bytes.
* **Debug & System:** Enhanced user fault logging with thread ID, moved IRQ user frame to thread kernel stack before signal handling, improved RT-Thread usage tracking, fixed `clock_nanosleep`/`nanosleep`, and switched soft RTC timing to `cpu_ticks_ms`.

[🔗 Full Changelog](https://github.com/canmv-k230/rtsmart/compare/rtos-v0.7...rtos-v0.8)

#### 2. MPP (Media Process Platform)

* **Display & Connector:** Added DSI lane-rate support, improved pixel clock correction, added I8080 interface support, improved SPI panel framework, added NV3030B QSPI LCD support, and added MRT MIPI ST7701 initialization.
* **Panels & HDMI:** Added custom/VESA HDMI timing parameters for LT9611, refined HDMI timing calculations, updated JD9852 panel clock, fixed Yahboom ST7701 backlight polarity, updated LCKFB connector initialization for LushanPi Lite, and reverted WonderMK panel timing.
* **Sensors & ISP:** Added OV13850 support, fixed IMX335 initialization timing and retry behavior, added mirror/flip for IMX335/BF3238/SC123SG, added ISP scene switching, sensor manual exposure API, and list-mode/again-range APIs.
* **Audio & Video:** Added PDM noise reduction and cache queue overflow optimization, improved VPU exit cleanup, fixed 3DNR MMZ allocation issues, improved layer image size handling, and added SDMA channel reservation APIs.
* **AI & RTSP:** Optimized AI code to fix memory leak and RTSP issues, and refactored AI module block/register return values.
* **Build & Tests:** Added fuzz and unit test directories, removed unused connector includes, and cleaned connector software bridge declarations.

[🔗 Full Changelog](https://github.com/canmv-k230/mpp/compare/rtos-v0.7...rtos-v0.8)

#### 3. RT-Smart Libraries & Examples

* **Libraries:**
  * Added improved linker script section alignment and TLS support.
  * Added `posix_fallocate`, `pthread_get_tid`, and mutex retry sleep support in syscall wrappers.
  * Added GPIO mutex locking, streamlined GPIO/FPIOA pin validation, and fixed GPIO toggle type casting.
  * Added cJSON support, GZIP decompression driver, PMU HAL, FFT driver, HID input driver, input auto-reconnect support, and RVV operation helpers.
  * Added PUFs asymmetric cryptography, cipher, hash, HMAC/CMAC, and OTP security configuration support.
  * Updated `nncase` runtime to 2.11.0 and moved kmodels to a separate repository.
  * Increased maximum WLAN password length from 32 to 64 bytes and enabled LVGL build by default.

* **Examples:**
  * Added OTP provisioning and OTP security state tests with LED status configuration.
  * Added PUF/RNG/key-management/ECC/ECDH/DRBG/AEAD/DMA boundary security tests.
  * Added `fs_speedtest`, cJSON samples, GZIP decompression example, PMU sample, FFT spectrum visualizer, VICAP sensor sample, triple-camera AI RTSP demo, and multi-source AI analyzer demo.
  * Added USB HID mouse support and improved HID keyboard handling and reconnect error handling.
  * Updated AI examples for `nncase` 2.11.0 and made AI parameters optional.
  * Improved video pipeline connector initialization, display deinitialization, active-resolution handling, raw12 sensor dump, scene path/name handling, UVC face detection init, and graceful thread shutdown.

[🔗 Libraries Full Changelog](https://github.com/canmv-k230/k230_rtsmart_lib/compare/rtos-v0.7...rtos-v0.8) | [🔗 Examples Full Changelog](https://github.com/canmv-k230/k230_rtsmart_examples/compare/rtos-v0.7...rtos-v0.8)

#### 4. U-Boot & SDK Board Support

* **SDK Board Support:** Added or updated board configuration for Yahboom, K230 CanMV MRT, K230D CanMV LushanPi Lite, K230D LabPlus AI Camera v2, DongshanPi LPDDR4, WonderMK, and related RTC/sample settings.
* **Image Generation:** Added SPI NAND image generation configuration, configurable partition auto-resize alignment, DDR test image generation script, OTA image config updates, and SDCARD FAT format/cluster-size tuning.
* **Secure Boot:** Added Secure Boot support and fixed Secure Boot Kconfig entries to use `config` instead of `menuconfig`.
* **Version & Release Tools:** Refactored release scripts, unified branch/tag handling, updated repo version parsing, removed dirty suffix from revisions, and added commit-count revision formatting.
* **Prebuilt Bootloader:** Updated prebuilt U-Boot binaries multiple times for the v0.8 release cycle.
* **Build & CI:** Refactored top-level Makefile to use the defconfig script, added `INSTALL` variable support, enabled all-samples/LVGL/minihttp daily builds, and retained parallel build workflow improvements.

[🔗 Full Changelog](https://github.com/canmv-k230/u-boot/compare/rtos-v0.7...rtos-v0.8)

---

### 🛠 Bug Fixes & Improvements

* **Stability:** Improved watchdog handling, USB DWC2 DMA buffer handling, USB host class validation, video pipeline shutdown, VPU exit cleanup, and RTSP/AI memory handling.
* **Security:** Added Secure Boot validation paths, OTP/PUF support, and cryptographic driver/test coverage.
* **Performance:** Added RVV acceleration for UVC host format conversion and kernel/library memory operations; improved SPI driver allocation and transfer handling.
* **Storage:** Added exFAT/preallocation support, improved SDIO behavior, and refined SD card image formatting.
* **Display & Camera:** Added new panel interfaces and sensor support while fixing board-specific backlight, timing, and initialization issues.
* **Build System:** Improved defconfig management, release tooling, Kconfig correctness, image generation robustness, and example/library build organization.

---

### 🔗 Repository Links

* [[k230_rtos_sdk](https://github.com/kendryte/k230_rtos_sdk/releases/tag/v0.8)](https://github.com/kendryte/k230_rtos_sdk/releases/tag/v0.8)
* [[rtsmart](https://github.com/canmv-k230/rtsmart/releases/tag/rtos-v0.8)](https://github.com/canmv-k230/rtsmart/releases/tag/rtos-v0.8)
* [[mpp](https://github.com/canmv-k230/mpp/releases/tag/rtos-v0.8)](https://github.com/canmv-k230/mpp/releases/tag/rtos-v0.8)
* [[k230_rtsmart_lib](https://github.com/canmv-k230/k230_rtsmart_lib/releases/tag/rtos-v0.8)](https://github.com/canmv-k230/k230_rtsmart_lib/releases/tag/rtos-v0.8)
* [[k230_rtsmart_examples](https://github.com/canmv-k230/k230_rtsmart_examples/releases/tag/rtos-v0.8)](https://github.com/canmv-k230/k230_rtsmart_examples/releases/tag/rtos-v0.8)
* [[u-boot](https://github.com/canmv-k230/u-boot/releases/tag/rtos-v0.8)](https://github.com/canmv-k230/u-boot/releases/tag/rtos-v0.8)

**Full Changelog**: https://github.com/kendryte/k230_rtos_sdk/compare/v0.6...v0.8

---

## K230 RTOS SDK Release Notes v0.7

We are pleased to announce the release of **K230 RTOS SDK v0.7**. This version introduces new board support for `k230d_canmv_mini`, adds USB host class NCM and CH397 networking, integrates the Tuya IoT SDK, and brings continued improvements to drivers, LVGL, and the build system.

### 🚀 Key Highlights

* **New Board Support:** Added support for the `k230d_canmv_mini` board across all components.
* **USB Networking:** Introduced USB host class NCM and CH397 Ethernet adapter support in the RT-Smart kernel.
* **LVGL Enhancements:** Fixed display buffer sizing, added alpha channel support for display creation, and added `lvgl_sensor` demo with MMZ buffer management.
* **Tuya IoT Integration:** Added Tuya SDK library and sample application for IoT connectivity.
* **Build & CI Optimization:** Optimized workflow build times with parallel make and reorganized example layout and build system.

---

### 📦 Component Updates

#### 1. RT-Smart (Kernel)

* **New Board:** Added support for `k230d_canmv_mini`.
* **USB Networking:** Added USB host class NCM and CH397 Ethernet adapter support with default mode and improved mode selection.
* **Touch & Input:** Fixed touch IRQ handling, refactored touch read logic, increased message buffer, and implemented interrupt enable/disable for `drv_touch`.
* **Network:** Removed unnecessary log when net fcntl sets nonblock; added ifdef guards for WLAN and improved error handling in `netmgmt`.
* **WiFi:** Added Realtek adaptivity configuration option.
* **Drivers:** Added bus name and DTS hint to I2C timeout log.
* **System:** Added `canmv_misc` get kernel build info feature.
* **Syscall:** Fixed RT-Smart syscall dispatch to translate Linux riscv64 `munmap`/`exit` numbers.

[🔗 Full Changelog](https://github.com/canmv-k230/rtsmart/compare/canmv-v1.5...rtos-v0.7)

#### 2. MPP (Media Process Platform)

* **Video Output (VO):** Added hwtimer for VO to tune update timing; fixed VO update layer attr failure; corrected boundary checks and rotation bpp logic.
* **Sensor:** Fixed GC2093 CSI1 mode table AE mapping indices and set 960p mode fps to 90.
* **Media:** Modified ffmpeg and x264 compile parameters.
* **Build:** Excluded `pngtest.c` from vglite\_util; fixed makefile echo usage and ignore `libframework.a`.

[🔗 Full Changelog](https://github.com/canmv-k230/mpp/compare/canmv-v1.5...rtos-v0.7)

#### 3. RT-Smart Libraries & Examples

* **Libraries:**
  * Fixed LVGL `lv_display_set_buffers` to use correct buffer size.
  * Added user-configurable alpha channel when creating LVGL display.
  * Integrated Tuya SDK.
  * Fixed MQTT build issues.
  * Updated LVGL port.
  * Added HID keyboard event API header file.
  * Enhanced makefile build process with better structure.

* **Examples:**
  * Added `lvgl_sensor` demo with MMZ buffer management and improved FPS calculation.
  * Added Tuya sample application.
  * Added `triple_camera_ai` demo.
  * Added USB HID keyboard test application.
  * Updated AI examples to adapt to docs.
  * Improved `smart_ipc` makefile.
  * Modified ogg demo.
  * Fixed `TEST_GPIO_PIN_MAX` definition for board compatibility.
  * Reorganized RTOS SDK example layout and build system.

[🔗 Libraries Full Changelog](https://github.com/canmv-k230/k230_rtsmart_lib/compare/canmv-v1.5...rtos-v0.7) | [🔗 Examples Full Changelog](https://github.com/canmv-k230/k230_rtsmart_examples/compare/canmv-v1.5...rtos-v0.7)

#### 4. U-Boot & Board Support

* **New Board:** Added `k230d_canmv_mini` board configuration.
* **DTS:** Updated board mondermk device tree.
* **CI:** Optimized workflow build times with parallel make; updated board mappings and added new configs to workflow.

[🔗 Full Changelog](https://github.com/canmv-k230/u-boot/compare/canmv-v1.5...rtos-v0.7)

---

### 🛠 Bug Fixes & Improvements

* **Drivers:** Fixed touch IRQ and refactored touch interrupt enable/disable; corrected VO boundary checks and rotation logic.
* **Networking:** Fixed CH397 default mode; added WLAN ifdef guards and improved netmgmt error handling.
* **LVGL:** Fixed display buffer sizing and MQTT build issues.
* **Syscall:** Fixed RT-Smart syscall dispatch for Linux riscv64 compatibility.
* **Build System:** Optimized CI with parallel make; improved error handling in VFAT image generation; reorganized example layout.

---

### 🔗 Repository Links

* [[k230_rtos_sdk](https://github.com/kendryte/k230_rtos_sdk/releases/tag/v0.7)](https://github.com/kendryte/k230_rtos_sdk/releases/tag/v0.7)
* [[rtsmart](https://github.com/canmv-k230/rtsmart/releases/tag/rtos-v0.7)](https://github.com/canmv-k230/rtsmart/releases/tag/rtos-v0.7)
* [[mpp](https://github.com/canmv-k230/mpp/releases/tag/rtos-v0.7)](https://github.com/canmv-k230/mpp/releases/tag/rtos-v0.7)
* [[k230_rtsmart_lib](https://github.com/canmv-k230/k230_rtsmart_lib/releases/tag/rtos-v0.7)](https://github.com/canmv-k230/k230_rtsmart_lib/releases/tag/rtos-v0.7)
* [[k230_rtsmart_examples](https://github.com/canmv-k230/k230_rtsmart_examples/releases/tag/rtos-v0.7)](https://github.com/canmv-k230/k230_rtsmart_examples/releases/tag/rtos-v0.7)
* [[u-boot](https://github.com/canmv-k230/u-boot/releases/tag/rtos-v0.7)](https://github.com/canmv-k230/u-boot/releases/tag/rtos-v0.7)

**Full Changelog**: https://github.com/kendryte/k230_rtos_sdk/compare/v0.6...v0.7

---

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

### 📦 k230_rtsmart_lib

* **New HAL Drivers**:

  * Added new UART, SPI, PWM, GPIO, FPIOA, WDT, and SBUS HAL drivers.
  * External SPI CS pin control supported.
* **Test Infrastructure**:

  * Introduced test cases for SPI (ST7789), GPIO, SBUS, timers, and FPIOA.
* **Fixes & Improvements**:

  * Fixed crash caused by invalid GPIO instance.
  * Fixed FPIOA bugs and driver warnings.
  * Added face_liveness.kmodel as part of the testing set.

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
| **rtsmart_lib** | [canmv-v1.3...rtos-v0.5](https://github.com/canmv-k230/k230_rtsmart_lib/compare/canmv-v1.3...rtos-v0.5) |
| **mpp**          | [canmv-v1.3...rtos-v0.5](https://github.com/canmv-k230/mpp/compare/canmv-v1.3...rtos-v0.5)              |
| **u-boot**       | [canmv-v1.3...rtos-v0.5](https://github.com/canmv-k230/u-boot/compare/canmv-v1.3...rtos-v0.5)           |

---

### 📝 Summary

The `rtos-v0.5` release focuses on transitioning the CanMV K230 platform toward **real-time RTOS workflows**. It introduces new drivers, boards, HAL libraries, and debugging infrastructure essential for embedded systems work. This sets the stage for future development with tight real-time constraints and modular software stacks.

We encourage developers working with RT-Thread to upgrade and try out the new platform capabilities.

For questions, contributions, or bug reports, visit our [GitHub organization](https://github.com/kendryte/canmv_k230).
