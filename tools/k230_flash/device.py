#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
USB / Serial device detection and bootloader mode switching for K230.

Adapted from the Arduino k230_flash/common.py reference implementation.
"""

import sys
import time
import struct
from typing import Optional

# VID/PID for K230 Serial (CanMV) mode and Bootloader mode
SERIAL_VID = 0x1209
SERIAL_PID = 0xABD1
BOOT_VID = 0x29F1
BOOT_PID = 0x0230

# ---------------------------------------------------------------------------
# Lazy imports for optional USB/Serial packages
# ---------------------------------------------------------------------------
_usb_available = True
_serial_available = True

try:
    import usb.core
    import usb.backend.libusb1
    import libusb_package
except ImportError:
    _usb_available = False

try:
    import serial.tools.list_ports
    import serial as _serial
except ImportError:
    _serial_available = False


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_usb_backend():
    """Load the libusb backend for pyusb."""
    if not _usb_available:
        raise ImportError(
            "pyusb and libusb_package are required for USB device detection. "
            "Install with: pip install pyusb libusb_package"
        )
    return usb.backend.libusb1.get_backend(
        find_library=libusb_package.find_library
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def find_serial_port(vid: int, pid: int) -> Optional[str]:
    """
    Find a serial port matching the given VID/PID.

    Returns the port name (e.g. /dev/ttyACM0) if exactly one device matches,
    None if zero match, and raises RuntimeError if multiple match.
    """
    if not _serial_available:
        raise ImportError(
            "pyserial is required for serial port detection. "
            "Install with: pip install pyserial"
        )
    matches = []
    for port in serial.tools.list_ports.comports():
        if port.vid == vid and port.pid == pid:
            matches.append(port)

    count = len(matches)
    if count == 0:
        return None
    if count > 1:
        msg = (
            f"Found {count} serial devices with VID:0x{vid:04X} PID:0x{pid:04X}. "
            f"Expected exactly 1. Ports: {[m.device for m in matches]}"
        )
        raise RuntimeError(msg)
    return matches[0].device


def count_bootloader_devices(vid: int, pid: int) -> int:
    """Return the number of USB devices matching the bootloader VID/PID."""
    backend = _get_usb_backend()
    if backend is None:
        raise RuntimeError("libusb backend not found. Cannot scan USB devices.")
    devices = list(usb.core.find(find_all=True, backend=backend,
                                  idVendor=vid, idProduct=pid))
    return len(devices)


def enter_bootloader_mode(port: str) -> bool:
    """
    Switch the K230 device into USB bootloader (burn) mode using raw
    USB CDC ACM control transfers via pyusb.

    This bypasses kernel CDC ACM driver differences between Linux and
    Windows, sending the magic sequence directly to the device:

      1. SET_LINE_CODING  (300, 5, MARK, 2 stop) → pending_magic_reset = true
      2. SEND_BREAK       → send_break_flag = true
      3. SET_CONTROL_LINE_STATE (DTR=1, RTS=1)   → triggers reboot_to_upgrade()

    Returns True if the signal sequence was sent successfully.
    """
    if not _usb_available:
        print("  Warning: pyusb not available, falling back to serial method.")
        return _enter_bootloader_via_serial(port)

    print(f"Attempting to switch device on {port} to Bootloader mode...")

    try:
        backend = _get_usb_backend()

        dev = usb.core.find(idVendor=SERIAL_VID, idProduct=SERIAL_PID, backend=backend)
        if dev is None:
            print(f"  Warning: USB device {SERIAL_VID:04X}:{SERIAL_PID:04X} not found via pyusb.")
            print("  Falling back to serial method.")
            return _enter_bootloader_via_serial(port)

        # Detach kernel driver so we can send control transfers directly.
        # After the magic sequence, the device reboots to bootloader mode
        # (different VID/PID), so re-attaching is unnecessary.
        try:
            for cfg in dev:
                for intf in cfg:
                    ifnum = intf.bInterfaceNumber
                    if dev.is_kernel_driver_active(ifnum):
                        dev.detach_kernel_driver(ifnum)
        except (usb.core.USBError, NotImplementedError):
            pass

        # Find the CDC ACM control interface number (class=0x02, subclass=0x02).
        cdc_ctrl_iface = None
        try:
            cfg = dev.get_active_configuration()
            for intf in cfg:
                if intf.bInterfaceClass == 0x02 and intf.bInterfaceSubClass == 0x02:
                    cdc_ctrl_iface = intf.bInterfaceNumber
                    break
        except usb.core.USBError:
            for cfg in dev:
                for intf in cfg:
                    if intf.bInterfaceClass == 0x02 and intf.bInterfaceSubClass == 0x02:
                        cdc_ctrl_iface = intf.bInterfaceNumber
                        break

        if cdc_ctrl_iface is None:
            cdc_ctrl_iface = 0

        wIndex = cdc_ctrl_iface

        # 1. SET_LINE_CODING — CDC spec field order:
        #      dwDTERate(4 LE) + bCharFormat(1) + bParityType(1) + bDataBits(1)
        line_coding = struct.pack('<I', 300) + bytes([2, 3, 5])
        dev.ctrl_transfer(bmRequestType=0x21, bRequest=0x20, wValue=0, wIndex=wIndex,
                          data_or_wLength=line_coding, timeout=1000)

        # 2. SEND_BREAK
        dev.ctrl_transfer(bmRequestType=0x21, bRequest=0x23, wValue=0xFFFF,
                          wIndex=wIndex, data_or_wLength=None, timeout=1000)

        # 3. SET_CONTROL_LINE_STATE — DTR=bit0, RTS=bit1 → 0x0003 = both on
        dev.ctrl_transfer(bmRequestType=0x21, bRequest=0x22, wValue=0x0003,
                          wIndex=wIndex, data_or_wLength=None, timeout=1000)

        print("  Signal sent via USB control transfer.")
        return True

    except usb.core.USBError as e:
        print(f"  Warning: USB error: {e}")
        print("  Falling back to serial method.")
        return _enter_bootloader_via_serial(port)


def _enter_bootloader_via_serial(port: str) -> bool:
    """
    Fallback: use pyserial to switch the device to bootloader mode.

    The Linux CDC ACM kernel driver may de-assert DTR/RTS when
    reconfiguring line settings. We force a clean sequence:
      1. Open with magic params (kernel sends SET_LINE_CODING)
      2. Force DTR/RTS low to create a known state
      3. Send break
      4. Assert DTR high
      5. Assert RTS high — rising edge triggers the firmware check

    The port is intentionally NOT closed so DTR/RTS remain asserted
    while the device reboots into bootloader mode.

    On macOS, IOKit does not support Mark parity at open() time,
    but accepts reconfiguration after the port is opened with
    standard params. We open 8N1 first, then reconfigure to the
    magic params (300 baud, 5 data bits, 2 stop bits) via the
    port's property setters before sending the break sequence.
    """
    print(f"Attempting to switch device on {port} to Bootloader mode (serial)...")

    try:
        ser = _serial.Serial(
            port=port,
            baudrate=1200,
            bytesize=_serial.EIGHTBITS,
            parity=_serial.PARITY_NONE,
            stopbits=_serial.STOPBITS_ONE,
            timeout=1,
            xonxoff=False,
            rtscts=False,
            dsrdtr=False,
        )
    except (ValueError, _serial.SerialException) as e:
        print(f"  Warning: Failed to open serial port {port}: {e}")
        return False

    # Reconfigure to magic params — macOS IOKit rejects these at
    # open() but accepts them via property setters on an open port.
    # This sends SET_LINE_CODING to the device, which is what the
    # bootloader entry sequence requires.
    try:
        ser.baudrate = 300
        ser.bytesize = _serial.FIVEBITS
        ser.stopbits = _serial.STOPBITS_TWO
    except (ValueError, _serial.SerialException) as e:
        print(f"  Warning: Failed to reconfigure serial params on {port}: {e}")
        ser.close()
        return False

    if not ser.is_open:
        raise _serial.SerialException(f"Failed to open serial port {port}")

    # Give the kernel time to finish SET_LINE_CODING + auto DTR/RTS
    time.sleep(0.2)

    # Force DTR/RTS low — kernel may have de-asserted them during
    # line reconfiguration; this creates a clean baseline.
    ser.dtr = False
    ser.rts = False
    time.sleep(0.1)

    # Send break (sets send_break_flag in firmware)
    ser.send_break()
    time.sleep(0.2)

    # Assert DTR (sets last_dtr_state in firmware)
    ser.dtr = True
    time.sleep(0.1)

    # Assert RTS — rising edge triggers magic-reboot check in firmware
    ser.rts = True
    time.sleep(0.2)

    print("  Signal sent. Keeping port open for device reboot.")
    # NOTE: do NOT close the port. Closing would de-assert DTR/RTS
    # and potentially interfere with the device's reboot sequence.
    return True


def wait_for_bootloader(vid: int, pid: int, timeout: int) -> bool:
    """
    Poll for the bootloader device to appear.

    Returns True if exactly one device is found within the timeout.
    """
    print("Waiting for device to enumerate in Bootloader mode...")
    start = time.time()
    while time.time() - start < timeout:
        count = count_bootloader_devices(vid, pid)
        if count == 1:
            print("  Success! Device detected in Bootloader mode.")
            return True
        if count > 1:
            raise RuntimeError(
                f"Multiple ({count}) bootloader devices detected during wait!"
            )
        time.sleep(0.25)
    return False


def ensure_device_in_bootloader(timeout: int = 10) -> None:
    """
    Ensure a K230 device is in USB bootloader (burn) mode.

    If a serial (CanMV) device is found, attempt to switch it to bootloader mode.
    If no devices are found, print warnings but do not abort — the caller may
    choose to proceed anyway (e.g. device already in bootloader mode from a
    previous run, or the flash CLI will report its own error).
    """
    print("--- Starting Device Check ---")

    try:
        serial_port = find_serial_port(SERIAL_VID, SERIAL_PID)
    except Exception as e:
        print(f"Warning: {e}")
        return

    if serial_port:
        print(f"Found Serial Device at {serial_port}.")
        if not enter_bootloader_mode(serial_port):
            print("Warning: Failed to send bootloader signal. The port may be in use by another program.")
            print("Please close any terminal programs (minicom, screen, etc.) and try again.")
        if wait_for_bootloader(BOOT_VID, BOOT_PID, timeout):
            print("Device is ready in Bootloader mode.")
        else:
            print("Warning: Timed out waiting for device to enter Bootloader mode.")
    else:
        print("No Serial Device found. Checking for existing Bootloader devices...")
        boot_count = count_bootloader_devices(BOOT_VID, BOOT_PID)
        if boot_count == 0:
            print("Warning: No devices found in Serial (CanMV) or Bootloader mode.")
            print("Please connect your K230 board and ensure it is powered on.")
        elif boot_count > 1:
            print(f"Warning: Found {boot_count} devices in Bootloader mode. Expected exactly 1.")
        else:
            print("Found exactly one device already in Bootloader mode.")
