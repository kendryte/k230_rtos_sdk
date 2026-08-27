#!/usr/bin/env python
"""Interactive selector for SDK board defconfigs.

This script is compatible with Python 2.7 and Python 3.
"""

from __future__ import print_function

import argparse
import curses
import glob
import io
import os
import re
import sys


try:
    text_type = unicode
    binary_type = str
    PY2 = True
except NameError:
    text_type = str
    binary_type = bytes
    PY2 = False


KIND_ORDER = ("arduino", "canmv", "rtos", "other")
KIND_LABELS = {
    "all": "All",
    "arduino": "Arduino",
    "canmv": "CanMV / MicroPython",
    "rtos": "RT-Smart / RTOS",
    "other": "Other",
}
KIND_SHORT_LABELS = {
    "arduino": "Arduino",
    "canmv": "CanMV",
    "rtos": "RT-Smart",
    "other": "Other",
}
KIND_ALIASES = {
    "all": "all",
    "arduino": "arduino",
    "canmv": "canmv",
    "micropython": "canmv",
    "mpy": "canmv",
    "rtos": "rtos",
    "rtsmart": "rtos",
    "other": "other",
}
CHIP_ORDER = ("k230", "k230d")
CHIP_LABELS = {
    "all": "All",
    "k230": "K230",
    "k230d": "K230D",
}


class Defconfig(object):
    __slots__ = ("name", "kind", "chip", "description")

    def __init__(self, name, kind, chip, description):
        self.name = name
        self.kind = kind
        self.chip = chip
        self.description = description


def to_text(value):
    if isinstance(value, text_type):
        return value
    if isinstance(value, binary_type):
        return value.decode("utf-8")
    return text_type(value)


def write_line(value=u"", stream=None):
    stream = stream or sys.stdout
    value = to_text(value)
    if PY2:
        encoding = getattr(stream, "encoding", None) or "utf-8"
        stream.write(value.encode(encoding, "replace") + "\n")
    else:
        stream.write(value + "\n")


def read_text(path):
    with io.open(path, "r", encoding="utf-8") as input_file:
        return input_file.read()


def normalize_kind(value):
    normalized = re.sub(r"[ _-]", "", value.lower())
    if not normalized:
        return "all"
    if normalized in KIND_ALIASES:
        return KIND_ALIASES[normalized]
    choices = ", ".join(("arduino", "canmv", "rtos", "other"))
    raise argparse.ArgumentTypeError(
        "unknown firmware type '{0}'; choose {1}".format(value, choices)
    )


def normalize_chip(value):
    normalized = re.sub(r"[ _-]", "", value.lower())
    if not normalized:
        return "all"
    if normalized in ("all", "k230", "k230d"):
        return normalized
    raise argparse.ArgumentTypeError(
        "unknown chip '{0}'; choose k230 or k230d".format(value)
    )


def parse_board_descriptions(path):
    descriptions = {}
    board_key = None

    for line in read_text(path).splitlines():
        config_match = re.match(r"\s*config\s+(\S+)", line)
        if config_match:
            board_key = config_match.group(1)
            continue

        prompt_match = re.match(r'\s*bool\s+"([^"]+)"', line)
        if board_key and board_key.startswith("BOARD_") and prompt_match:
            descriptions[board_key] = prompt_match.group(1)
            board_key = None

    return descriptions


def parse_defconfig_descriptions(path):
    descriptions = {}
    if not os.path.exists(path):
        return descriptions

    for raw_line in read_text(path).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "|" not in line:
            continue
        name, description = line.split("|", 1)
        descriptions[name.strip()] = description.strip()

    return descriptions


def detect_kind(name, board_name, canmv_enabled):
    if re.search(r"(^|_)arduino_", name) or board_name.startswith("Arduino_"):
        return "arduino"
    if re.search(r"(^|_)rtos_", name):
        return "rtos"
    if canmv_enabled:
        return "canmv"
    return "other"


def detect_chip(name, board):
    if name.startswith("k230d_") or board.startswith("BOARD_K230D_"):
        return "k230d"
    return "k230"


def load_defconfigs(root):
    boards_path = os.path.join(root, "boards", "Kconfig")
    info_path = os.path.join(root, "configs", "defconfig_info")
    pattern = os.path.join(root, "configs", "*_defconfig")
    board_descriptions = parse_board_descriptions(boards_path)
    config_descriptions = parse_defconfig_descriptions(info_path)
    defconfigs = []

    for path in sorted(glob.glob(pattern)):
        contents = read_text(path)
        name = to_text(os.path.basename(path))
        board_match = re.search(r"^CONFIG_(BOARD_[A-Z0-9_]+)=y$", contents, re.M)
        board_name_match = re.search(
            r'^CONFIG_BOARD_NAME="([^"]*)"$', contents, re.M
        )
        board = board_match.group(1) if board_match else "BOARD_K230_CANMV"
        board_name = board_name_match.group(1) if board_name_match else ""
        canmv_enabled = bool(
            re.search(r"^CONFIG_SDK_ENABLE_CANMV=y$", contents, re.M)
        )
        kind = detect_kind(name, board_name, canmv_enabled)
        chip = detect_chip(name, board)
        description = config_descriptions.get(
            name, board_descriptions.get(board, board)
        )
        defconfigs.append(Defconfig(name, kind, chip, description))

    return defconfigs


def grouped_configs(defconfigs, kind_filter, chip_filter):
    groups = []
    for kind in KIND_ORDER:
        if kind_filter != "all" and kind != kind_filter:
            continue
        items = [
            config
            for config in defconfigs
            if config.kind == kind
            and (chip_filter == "all" or config.chip == chip_filter)
        ]
        if items:
            groups.append((kind, items))
    return groups


def print_defconfigs(defconfigs, current, kind_filter, chip_filter):
    groups = grouped_configs(defconfigs, kind_filter, chip_filter)
    visible = [config for unused_kind, items in groups for config in items]
    name_width = max([len(config.name) for config in visible] or [0])

    filters = []
    if kind_filter != "all":
        filters.append("type: {0}".format(kind_filter))
    if chip_filter != "all":
        filters.append("chip: {0}".format(chip_filter))
    suffix = " ({0})".format(", ".join(filters)) if filters else ""
    write_line("Available defconfigs: {0}{1}".format(len(visible), suffix))
    number = 0
    for kind, items in groups:
        write_line()
        write_line("{0} ({1})".format(KIND_LABELS[kind], len(items)))
        for config in items:
            number += 1
            marker = "*" if config.name == current else " "
            line = u"  {0:2d} [{1}] {2} {3} -- {4}".format(
                number,
                marker,
                CHIP_LABELS[config.chip].ljust(5),
                config.name.ljust(name_width),
                config.description,
            )
            write_line(line)

    write_line()
    write_line("Run 'make list-def' in an interactive terminal to select a config.")


class Selector(object):
    def __init__(
        self, stdscr, defconfigs, current, kind_filter, chip_filter
    ):
        self.stdscr = stdscr
        self.defconfigs = list(defconfigs)
        self.current = current
        self.kind_counts = dict(
            (kind, sum(config.kind == kind for config in self.defconfigs))
            for kind in KIND_ORDER
        )
        self.chip_counts = dict(
            (chip, sum(config.chip == chip for config in self.defconfigs))
            for chip in CHIP_ORDER
        )
        if kind_filter == "all":
            self.categories = ["all"] + [
                kind for kind in KIND_ORDER if self.kind_counts[kind]
            ]
        else:
            self.categories = [kind_filter]
        if chip_filter == "all":
            self.chips = ["all"] + [
                chip for chip in CHIP_ORDER if self.chip_counts[chip]
            ]
        else:
            self.chips = [chip_filter]
        self.category_index = 0
        self.chip_index = 0
        self.selected_index = 0
        self.top_index = 0
        self._select_current()

    @property
    def category(self):
        return self.categories[self.category_index]

    @property
    def chip(self):
        return self.chips[self.chip_index]

    @property
    def visible(self):
        return [
            config
            for config in self.defconfigs
            if (self.category == "all" or config.kind == self.category)
            and (self.chip == "all" or config.chip == self.chip)
        ]

    def _select_current(self):
        for index, config in enumerate(self.visible):
            if config.name == self.current:
                self.selected_index = index
                return
        self.selected_index = 0

    def _change_category(self, offset):
        if len(self.categories) == 1:
            return
        self.category_index = (self.category_index + offset) % len(self.categories)
        self.selected_index = 0
        self.top_index = 0
        self._select_current()

    def _change_chip(self, offset):
        if len(self.chips) == 1:
            return
        self.chip_index = (self.chip_index + offset) % len(self.chips)
        self.selected_index = 0
        self.top_index = 0
        self._select_current()

    def _move(self, offset):
        items = self.visible
        if items:
            self.selected_index = max(
                0, min(len(items) - 1, self.selected_index + offset)
            )

    def _put(self, y, x, value, attr=0):
        height, width = self.stdscr.getmaxyx()
        if y < 0 or y >= height or x < 0 or x >= width - 1:
            return
        value = to_text(value)
        if PY2:
            encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
            value = value.encode(encoding, "replace")
        try:
            self.stdscr.addnstr(y, x, value, width - x - 1, attr)
        except curses.error:
            pass

    def _firmware_count(self, kind):
        return sum(
            (kind == "all" or config.kind == kind)
            and (self.chip == "all" or config.chip == self.chip)
            for config in self.defconfigs
        )

    def _chip_count(self, chip):
        return sum(
            (chip == "all" or config.chip == chip)
            and (self.category == "all" or config.kind == self.category)
            for config in self.defconfigs
        )

    def _draw_firmware_tabs(self, width):
        chunks = ["Firmware: "]
        for index, kind in enumerate(self.categories):
            label = "{0} {1}".format(
                KIND_LABELS[kind], self._firmware_count(kind)
            )
            if index == self.category_index:
                chunks.append("[{0}]".format(label))
            else:
                chunks.append(" {0} ".format(label))
        self._put(1, 0, " ".join(chunks)[: width - 1], curses.A_BOLD)

    def _draw_chip_tabs(self, width):
        chunks = ["Chip:     "]
        for index, chip in enumerate(self.chips):
            label = "{0} {1}".format(CHIP_LABELS[chip], self._chip_count(chip))
            if index == self.chip_index:
                chunks.append("[{0}]".format(label))
            else:
                chunks.append(" {0} ".format(label))
        self._put(2, 0, " ".join(chunks)[: width - 1], curses.A_BOLD)

    def draw(self):
        self.stdscr.erase()
        height, width = self.stdscr.getmaxyx()
        if height < 14 or width < 80:
            self._put(0, 0, "CanMV K230 Defconfig Selector", curses.A_BOLD)
            self._put(2, 0, "Terminal is too small. Resize to at least 80 x 14.")
            self._put(height - 1, 0, "q/Esc: cancel")
            self.stdscr.refresh()
            return 0

        self._put(0, 0, "CanMV K230 Defconfig Selector", curses.A_BOLD)
        current = self.current or "none"
        self._draw_firmware_tabs(width)
        self._draw_chip_tabs(width)
        self._put(3, 0, "-" * (width - 1), curses.A_DIM)

        items = self.visible
        list_height = height - 9
        if self.selected_index < self.top_index:
            self.top_index = self.selected_index
        if self.selected_index >= self.top_index + list_height:
            self.top_index = self.selected_index - list_height + 1
        max_top = max(0, len(items) - list_height)
        self.top_index = min(self.top_index, max_top)

        for row, config in enumerate(
            items[self.top_index : self.top_index + list_height], start=4
        ):
            index = self.top_index + row - 4
            selected = index == self.selected_index
            pointer = ">" if selected else " "
            marker = "*" if config.name == self.current else " "
            kind = KIND_SHORT_LABELS[config.kind]
            chip = CHIP_LABELS[config.chip]
            line = "{0} {1} {2} {3} {4}".format(
                pointer, marker, chip.ljust(5), kind.ljust(9), config.name
            )
            attr = curses.A_REVERSE if selected else 0
            if marker == "*" and not selected:
                attr = curses.A_BOLD
            self._put(row, 0, line, attr)

        self._put(height - 5, 0, "-" * (width - 1), curses.A_DIM)
        self._put(height - 4, 0, "Current: {0}".format(current), curses.A_BOLD)
        if items:
            selected = items[self.selected_index]
            selected_text = "Selected: {0} [{1}, {2}]".format(
                selected.name,
                CHIP_LABELS[selected.chip],
                KIND_LABELS[selected.kind],
            )
            self._put(height - 3, 0, selected_text, curses.A_BOLD)
            self._put(height - 2, 0, selected.description)
        self._put(
            height - 1,
            0,
            "Up/Down config | Left/Right firmware | Tab chip | Enter apply | q cancel",
            curses.A_DIM,
        )
        self.stdscr.refresh()
        return list_height

    def run(self):
        try:
            curses.curs_set(0)
        except curses.error:
            pass
        self.stdscr.keypad(True)

        while True:
            page_size = self.draw()
            key = self.stdscr.getch()
            if key in (ord("q"), ord("Q"), 27):
                return None
            if key in (curses.KEY_UP, ord("k")):
                self._move(-1)
            elif key in (curses.KEY_DOWN, ord("j")):
                self._move(1)
            elif key in (curses.KEY_LEFT, ord("h")):
                self._change_category(-1)
            elif key in (curses.KEY_RIGHT, ord("l")):
                self._change_category(1)
            elif key == 9:
                self._change_chip(1)
            elif key == getattr(curses, "KEY_BTAB", -1):
                self._change_chip(-1)
            elif key == curses.KEY_HOME:
                self.selected_index = 0
            elif key == curses.KEY_END:
                self.selected_index = max(0, len(self.visible) - 1)
            elif key == curses.KEY_PPAGE:
                self._move(-max(1, page_size))
            elif key == curses.KEY_NPAGE:
                self._move(max(1, page_size))
            elif key in (curses.KEY_ENTER, 10, 13) and self.visible:
                return self.visible[self.selected_index]


def select_defconfig(defconfigs, current, kind_filter, chip_filter):
    return curses.wrapper(
        lambda stdscr: Selector(
            stdscr, defconfigs, current, kind_filter, chip_filter
        ).run()
    )


def build_parser():
    default_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser(
        description="Select and apply a CanMV K230 SDK defconfig"
    )
    parser.add_argument("--root", default=default_root, help=argparse.SUPPRESS)
    parser.add_argument("--current", default="", help=argparse.SUPPRESS)
    parser.add_argument(
        "--type",
        default="all",
        type=normalize_kind,
        metavar="TYPE",
        help="firmware filter: arduino, canmv, rtos, or other",
    )
    parser.add_argument(
        "--chip",
        default="all",
        type=normalize_chip,
        metavar="CHIP",
        help="chip filter: k230 or k230d",
    )
    parser.add_argument(
        "--output",
        help="write the selected defconfig name to this file",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="print defconfigs instead of opening the selector",
    )
    return parser


def main():
    args = build_parser().parse_args()
    try:
        defconfigs = load_defconfigs(os.path.abspath(args.root))
    except (OSError, UnicodeError) as exc:
        write_line(
            "Error: unable to read defconfigs: {0}".format(exc), sys.stderr
        )
        return 1

    if not defconfigs:
        write_line("Error: no defconfigs found", sys.stderr)
        return 1

    if args.list or not (sys.stdin.isatty() and sys.stdout.isatty()):
        print_defconfigs(defconfigs, args.current, args.type, args.chip)
        return 0

    try:
        selected = select_defconfig(
            defconfigs, args.current, args.type, args.chip
        )
    except curses.error as exc:
        write_line(
            "Error: unable to start terminal selector: {0}".format(exc),
            sys.stderr,
        )
        return 1

    if selected is None:
        write_line("Defconfig selection cancelled.")
        return 0

    if args.output:
        try:
            with io.open(args.output, "w", encoding="utf-8") as output_file:
                output_file.write(to_text(selected.name) + u"\n")
        except OSError as exc:
            write_line(
                "Error: unable to save selection: {0}".format(exc), sys.stderr
            )
            return 1
    else:
        write_line(selected.name)
    write_line("Selected defconfig: {0}".format(selected.name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
