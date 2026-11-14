# DongshanPi CanMV V3 configuration

Select `k230_canmv_dongshanpi_v3_defconfig` in a complete SDK checkout:

```bash
make k230_canmv_dongshanpi_v3_defconfig
make
```

This board configuration uses CSI0 as the default camera interface with OV13850
four-lane support. CSI1 is disabled because the four-lane camera uses its PHY.
The OV13850 module supplies its own clock; the SoC MCLK option is disabled for it.
CSI2 camera support is retained. GC2093 and OV5647 remain enabled as alternatives.

The LCD configuration enables ST7701 with reset GPIO22 and backlight GPIO25.
The RT-Smart BSP selects RTL8733BS Wi-Fi on SDIO1, REG_ON GPIO6, an active-low
200 ms reset pulse and a 50 ms power-up delay. CST128 uses interrupt GPIO23 and
reset GPIO24, with a 480 x 640 raw coordinate range. U-Boot supplies the board
pin configuration; duplicate RT-Smart pin initialization is disabled.

The image/environment/OpenSBI files link to the existing DongshanPi board files.
The original DongshanPi defconfig remains available.

This contribution contains configuration, board identity, device tree and build
registration files only. Sensor, LCD, backlight, display mapping, Wi-Fi and I2C
driver implementations are unchanged. V3-specific LCD timing, display orientation
and backlight polarity previously implemented in driver source are outside this
configuration-only contribution and require separate validation with upstream drivers.

The prepared branches have not undergone a new full firmware build or board test.
