#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Python wrapper around the k230_flash_cli binary.

Adapted from the Arduino k230_flash/k230_flash.py reference implementation.
"""

import os
import sys
import time
import json
import signal
import platform
import subprocess
import threading
import stat as stat_module
from pathlib import Path
from typing import Optional, List, Union, Dict


class K230FlashTool:
    """
    Python wrapper for the Kendryte K230 Flash CLI binary (k230_flash_cli).

    Handles OS detection, binary resolution, argument construction,
    and subprocess management with cancellation support.
    """

    BIN_MAP = {
        "Windows": "k230_flash_cli.exe",
        "Linux":   "k230_flash_cli",
        "Darwin":  "k230_flash_cli_mac",
    }

    VALID_MEDIA = ["EMMC", "SDCARD", "SPI_NAND", "SPI_NOR", "OTP"]

    def __init__(self, binary_dir: Optional[str] = None):
        """
        :param binary_dir: Path to the folder containing k230_flash_cli.
                           Defaults to <package_dir>/bin.
        """
        self.os_name = platform.system()
        if binary_dir:
            self.binary_dir = Path(binary_dir).resolve()
        else:
            self.binary_dir = Path(__file__).resolve().parent / "bin"
        self.binary_path = self._resolve_binary()

        self._cancelled = threading.Event()
        self._current_process: Optional[subprocess.Popen] = None
        self._original_sigint_handler = None

    # ------------------------------------------------------------------
    # binary resolution
    # ------------------------------------------------------------------

    def _resolve_binary(self) -> Path:
        """Find the correct binary for the current OS and ensure it is executable."""
        if self.os_name not in self.BIN_MAP:
            raise OSError(f"Unsupported OS: {self.os_name}")

        bin_name = self.BIN_MAP[self.os_name]
        candidates = [bin_name, "k230_flash", "k230_flash_cli"]

        found = None
        for c in candidates:
            p = self.binary_dir / c
            if p.exists():
                found = p
                break

        if not found:
            raise FileNotFoundError(
                f"Binary not found in '{self.binary_dir}'.\n"
                f"Expected one of: {candidates}.\n"
                f"Please place the compiled k230_flash_cli tool there."
            )

        if self.os_name in ("Linux", "Darwin"):
            st = os.stat(found)
            os.chmod(found, st.st_mode | stat_module.S_IEXEC)

        return found

    # ------------------------------------------------------------------
    # cancellation / signal handling
    # ------------------------------------------------------------------

    def cancel(self):
        """Cancel the currently running process."""
        self._cancelled.set()
        if self._current_process:
            try:
                self._current_process.terminate()
                try:
                    self._current_process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self._current_process.kill()
                    self._current_process.wait()
            except (ProcessLookupError, OSError):
                pass

    def _setup_signal_handlers(self):
        def _handler(sig, frame):
            print("\nReceived interrupt signal, cancelling operation...")
            self.cancel()
        self._original_sigint_handler = signal.signal(signal.SIGINT, _handler)

    def _restore_signal_handlers(self):
        if self._original_sigint_handler:
            signal.signal(signal.SIGINT, self._original_sigint_handler)

    # ------------------------------------------------------------------
    # subprocess runner
    # ------------------------------------------------------------------

    def _run(self, args: List[str], stream: bool = True,
             parse_json: bool = False, timeout: Optional[int] = None) -> Union[str, List, Dict]:
        """
        Execute the binary with the given arguments.

        :param args:       List of CLI arguments.
        :param stream:     If True, print stdout in real time.
        :param parse_json: If True, attempt to parse captured output as JSON.
        :param timeout:    Optional timeout in seconds.
        :return:           Output string, or parsed JSON if parse_json=True.
        """
        self._cancelled.clear()
        cmd = [str(self.binary_path)] + args

        try:
            self._setup_signal_handlers()

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace',
            )
            self._current_process = process

            captured_lines: List[str] = []
            start_time = time.time()

            if process.stdout:
                while True:
                    if self._cancelled.is_set():
                        process.terminate()
                        raise KeyboardInterrupt("Operation cancelled by user")

                    if timeout and (time.time() - start_time) > timeout:
                        process.terminate()
                        raise TimeoutError(
                            f"Command timed out after {timeout}s: {' '.join(cmd)}"
                        )

                    try:
                        line = process.stdout.readline()
                    except (IOError, ValueError):
                        break

                    if not line:
                        break

                    captured_lines.append(line)
                    if stream and not parse_json:
                        print(line, end='', flush=True)

            # Wait for completion
            remaining = None
            if timeout:
                elapsed = time.time() - start_time
                remaining = max(1, timeout - elapsed)
            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                raise TimeoutError(
                    f"Command timed out after {timeout}s: {' '.join(cmd)}"
                )

            if self._cancelled.is_set():
                raise KeyboardInterrupt("Operation cancelled by user")

            full_output = "".join(captured_lines)

            # Non-zero return codes are acceptable for help/list commands
            if process.returncode != 0:
                if process.returncode in (-2, -15) or \
                   any(a in args for a in ("--help", "-h", "--list-device", "-l")):
                    return full_output
                raise subprocess.CalledProcessError(process.returncode, cmd, output=full_output)

            if parse_json:
                try:
                    return json.loads(full_output.strip())
                except json.JSONDecodeError:
                    start = full_output.find('[')
                    end = full_output.rfind(']') + 1
                    if start != -1 and end != -1:
                        try:
                            return json.loads(full_output[start:end])
                        except json.JSONDecodeError:
                            pass
                    if stream:
                        print("Warning: Expected JSON but got raw text.")
                    return full_output

            return full_output

        except FileNotFoundError:
            raise FileNotFoundError(f"Flash tool binary not found: {self.binary_path}")
        except PermissionError:
            raise PermissionError(
                f"Permission denied accessing flash tool binary: {self.binary_path}"
            )
        finally:
            self._current_process = None
            self._restore_signal_handlers()

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def list_devices(self) -> str:
        """List connected K230 devices (USB bootloader mode)."""
        return self._run(["-l"], stream=True)

    def flash(self, image_path: str, medium_type: str = "SDCARD",
              auto_reboot: bool = True, timeout: Optional[int] = None) -> None:
        """
        Flash a firmware image to the K230 device.

        :param image_path:  Path to the firmware image file (.img or .kdimg).
        :param medium_type: Target storage medium: EMMC, SDCARD, SPI_NAND, SPI_NOR, or OTP.
        :param auto_reboot: If True, reboot the device after flashing.
        :param timeout:     Timeout in seconds for the flash operation.
        """
        img = Path(image_path)
        if not img.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        medium = medium_type.upper()
        if medium not in self.VALID_MEDIA:
            raise ValueError(f"Invalid medium '{medium_type}'. Valid: {self.VALID_MEDIA}")

        args = ["-m", medium, "-f", str(img.resolve())]
        if auto_reboot:
            args.append("--auto-reboot")

        print(f"--- Flashing {medium} with image: {img.name} ---")
        print("Press Ctrl+C to cancel the operation.")
        try:
            self._run(args, stream=True, timeout=timeout)
            print("\n--- Flash Complete ---")
        except KeyboardInterrupt:
            print("\n--- Flash Operation Cancelled by User ---")
            raise
        except TimeoutError:
            print(f"\n--- Flash Operation Timed Out ---")
            raise

    def __del__(self):
        if self._current_process and self._current_process.poll() is None:
            self.cancel()
        self._restore_signal_handlers()
