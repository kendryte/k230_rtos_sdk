# DongshanPi CanMV V3 configuration

Select `k230_canmv_dongshanpi_v3_defconfig` in a complete SDK checkout:

```bash
make k230_canmv_dongshanpi_v3_defconfig
make
```

This board configuration uses CSI0 as the default camera interface. The CSI0 link
mode and OV13850 four-lane options are both enabled; GC2093 two-lane auto-detection
remains available when that module is fitted. CSI1 is disabled because the four-lane camera uses its PHY.
The OV13850 module supplies its own clock; the SoC MCLK option is disabled for it.
CSI2 camera support is retained. GC2093 and OV5647 remain enabled as alternatives.

The LCD configuration enables ST7701 with reset GPIO22 and active-low backlight
GPIO25. The CanMV V3 board default selects the existing 480 x 640 ST7701 panel
for a 640 x 480 landscape display; applications may use `Display.init(Display.ST7701)`
without overriding the size or driving the backlight pin themselves.
The RT-Smart BSP selects RTL8733BS Wi-Fi on SDIO1, REG_ON GPIO6, an active-low
200 ms reset pulse and a 50 ms power-up delay. CST128 uses interrupt GPIO23 and
reset GPIO24, with a 480 x 640 raw coordinate range. U-Boot supplies the board
pin configuration; duplicate RT-Smart pin initialization is disabled.

The image/environment/OpenSBI files link to the existing DongshanPi board files.
The original DongshanPi defconfig remains available.

The display defaults require two V3-specific table selections in the companion
CanMV and MPP repositories: select the existing 480 x 640 panel as the default,
and mark its GPIO backlight active-low. Panel timings and initialization commands,
sensor drivers, and Wi-Fi drivers are unchanged. No LT6911C support is included.

## RT-Smart firmware

The RT-Smart counterpart uses the same V3 hardware configuration and BSP:

```bash
make k230_rtos_dongshanpi_v3_defconfig
make
```

It disables CanMV/MicroPython, enables the RT-Smart integrated examples, and
selects `genimage-sdcard-rtos.cfg`. U-Boot is built from the V3 source configuration;
the existing `k230_canmv_dongshanpi_v3_defconfig` BSP supplies the Wi-Fi and touch
settings. No separate RT-Smart BSP or U-Boot defconfig is required.

This configuration boots to the RT-Smart `msh` console. Fast-boot application
preloading and automatic application execution are disabled, so the generated
examples remain on the filesystem for manual use. The original DongshanPi RTOS
configuration starts Smart IPC with `-C 1`, which selects a 480 x 800 panel in
that example and does not match the V3's 480 x 640 panel. That command is not
reused, and no example or driver implementation changes are needed here.

RT-Smart applications select their own display connector; use `list_connector`
to find the existing `ST7701_480_640_DSI_V1` mode and set the application rotation
where supported. The CanMV `Display.init()` default described above applies only
to the MicroPython firmware. The companion MPP V3 active-low backlight selection
is also required for the RT-Smart firmware.
