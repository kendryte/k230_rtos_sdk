# RTOS Only K230 Changelog

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
