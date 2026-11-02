import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tools import sdk_output


class LegacyStateTests(unittest.TestCase):
    def test_leftover_include_does_not_block_activation(self):
        for linked_config in (False, True):
            for populated_include in (False, True):
                with self.subTest(linked_config=linked_config,
                                  populated_include=populated_include):
                    with tempfile.TemporaryDirectory() as temporary:
                        root = Path(temporary)
                        output = root / "output/board_defconfig"
                        header = output / "include/generated/autoconf.h"
                        header.parent.mkdir(parents=True)
                        header.write_text("selected board\n")
                        (output / ".config").write_text(
                            'CONFIG_BOARD_CONFIG_NAME="board_defconfig"\n')
                        (output / ".config.old").write_text("saved config\n")
                        if linked_config:
                            (root / ".config").symlink_to("output/board_defconfig/.config")
                        (root / "include").mkdir()
                        (root / ".config.old").write_text("legacy config\n")
                        if populated_include:
                            legacy_header = root / "include/autoconf.h"
                            legacy_header.write_text("legacy board\n")
                            os.utime(legacy_header, ns=(1234567890, 1234567890))
                            (root / "include/alias.h").symlink_to("autoconf.h")

                        sdk_output.migrate_legacy(root, output)
                        sdk_output.activate_output(root, output)

                        for name in sdk_output.STATE_PATHS:
                            self.assertTrue((root / name).is_symlink())
                            self.assertEqual((root / name).resolve(), output / name)
                        self.assertEqual(header.read_text(), "selected board\n")
                        self.assertEqual((output / ".config.old").read_text(), "saved config\n")
                        backups = list((root / "output").glob("legacy-state-*"))
                        self.assertEqual(len(backups), 1)
                        backup = backups[0]
                        self.assertTrue((backup / "include").is_dir())
                        self.assertEqual((backup / ".config.old").read_text(), "legacy config\n")
                        if populated_include:
                            saved_header = backup / "include/autoconf.h"
                            self.assertEqual(saved_header.read_text(), "legacy board\n")
                            self.assertEqual(saved_header.stat().st_mtime_ns, 1234567890)
                            self.assertEqual(os.readlink(backup / "include/alias.h"), "autoconf.h")

                        sdk_output.migrate_legacy(root, output)
                        sdk_output.activate_output(root, output)
                        self.assertEqual(list((root / "output").glob("legacy-state-*")), backups)

    def test_no_output_leaves_leftovers_in_place(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "include").mkdir()
            (root / "include/autoconf.h").write_text("legacy board\n")

            sdk_output.migrate_legacy(root, None)

            self.assertFalse((root / "include").is_symlink())
            self.assertEqual((root / "include/autoconf.h").read_text(), "legacy board\n")
            self.assertFalse((root / "output").exists())

    def test_complete_legacy_state_migrates_to_its_board(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = root / "output/legacy_defconfig"
            (root / ".config").write_text('CONFIG_BOARD_CONFIG_NAME="legacy_defconfig"\n')
            (root / "include").mkdir()
            (root / "include/autoconf.h").write_text("legacy board\n")

            sdk_output.migrate_legacy(root, root / "output/selected_defconfig")

            self.assertEqual((root / ".config").resolve(), output / ".config")
            self.assertEqual((root / "include").resolve(), output / "include")
            self.assertEqual((output / "include/autoconf.h").read_text(), "legacy board\n")
            self.assertEqual(list((root / "output").glob("legacy-state-*")), [])


class DistcleanTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        repository = Path(__file__).resolve().parents[2]
        for name in ("Makefile", "tools/output.mk", "tools/sdk_output.py",
                     "tools/mkenv.mk", "tools/kconfig.mk", "tools/kconfig/Makefile"):
            destination = self.root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(repository / name, destination)
        self.saved = self.root / "output/saved_defconfig"
        (self.saved / "include").mkdir(parents=True)
        (self.saved / ".config").write_text('CONFIG_BOARD_CONFIG_NAME="saved_defconfig"\n')
        (self.saved / "include/autoconf.h").write_text("saved board\n")
        self.backup_header = self.root / "output/legacy-state-saved/include/autoconf.h"
        self.backup_header.parent.mkdir(parents=True)
        self.backup_header.write_text("legacy board\n")

    def make(self, *goals):
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(("SDK_", "CONFIG_", "MK_"))
               and key not in ("MAKEFLAGS", "MFLAGS", "MAKELEVEL")}
        return subprocess.run(
            ["make", "--no-print-directory", *goals,
             "SDK_TOOLCHAIN_DIR={}".format(self.root / "toolchains")],
            cwd=self.root, env=env, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=30)

    def test_unconfigured_distclean_preserves_saved_outputs(self):
        lock_path = self.root / "output/.build.lock"
        lock_file = lock_path.open("a")
        self.addCleanup(lock_file.close)
        for include_kind in ("missing", "directory", "symlink"):
            with self.subTest(include_kind=include_kind):
                include = self.root / "include"
                if include_kind == "directory":
                    include.mkdir()
                    (include / "autoconf.h").write_text("leftover header\n")
                elif include_kind == "symlink":
                    include.symlink_to("output/saved_defconfig/include")
                (self.root / ".config.old").write_text("leftover config\n")
                (self.root / "tools/kconfig/conf").write_text("leftover binary\n")
                for _ in range(2):
                    result = self.make("distclean")
                    self.assertEqual(result.returncode, 0, result.stdout)
                    self.assertIn("distclean done.", result.stdout)
                    self.assertTrue(os.path.samestat(os.fstat(lock_file.fileno()), lock_path.stat()))
                    self.assertEqual(lock_path.stat().st_size, 0)
                self.assertFalse(include.exists() or include.is_symlink())
                self.assertFalse((self.root / ".config.old").exists())
                self.assertFalse((self.root / "tools/kconfig/conf").exists())
                self.assertFalse((self.root / "toolchains").exists())
                self.assertTrue((self.saved / ".config").is_file())
                self.assertEqual((self.saved / "include/autoconf.h").read_text(), "saved board\n")
                self.assertEqual(self.backup_header.read_text(), "legacy board\n")

    def test_configured_distclean_still_cleans_components_and_selected_output(self):
        output = self.root / "output/active_defconfig"
        output.mkdir()
        (output / ".config").write_text('CONFIG_BOARD_CONFIG_NAME="active_defconfig"\n')
        (self.root / ".config").symlink_to("output/active_defconfig/.config")
        for component in ("uboot", "rtsmart", "opensbi", "applications"):
            source = self.root / "src" / component
            source.mkdir(parents=True)
            (source / "Makefile").write_text(
                'distclean:\n\t@touch "$(SDK_SRC_ROOT_DIR)/{}-cleaned"\n'.format(component))

        result = self.make("distclean")

        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse(output.exists())
        self.assertTrue(self.saved.is_dir())
        self.assertEqual(self.backup_header.read_text(), "legacy board\n")
        for name in sdk_output.STATE_PATHS:
            self.assertFalse((self.root / name).exists() or (self.root / name).is_symlink())
        for component in ("uboot", "rtsmart", "opensbi", "applications"):
            self.assertTrue((self.root / (component + "-cleaned")).is_file())

    def test_unconfigured_build_still_requires_configuration(self):
        for goals in ((), ("all",), ("distclean", "all")):
            with self.subTest(goals=goals):
                result = self.make(*goals)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Please run make xxx_defconfig first", result.stdout)

    def test_build_directories_follow_requested_goals(self):
        (self.root / ".config").symlink_to("output/saved_defconfig/.config")
        (self.root / "directory-test.mk").write_text(
            "SDK_SRC_ROOT_DIR := $(CURDIR)\n"
            "include tools/mkenv.mk\n"
            ".PHONY: all help list_def list-def dl_toolchain distclean\n"
            "all help list_def list-def dl_toolchain distclean:\n\t@:\n")
        for goals, needs_directories in (
                ((), True), (("all",), True), (("distclean", "all"), True),
                (("help", "all"), True), (("distclean",), False),
                (("help",), False), (("list_def",), False),
                (("list-def",), False), (("dl_toolchain",), False),
                (("help", "distclean"), False)):
            with self.subTest(goals=goals):
                images = self.saved / "images"
                toolchain = self.root / "toolchains"
                shutil.rmtree(images, ignore_errors=True)
                shutil.rmtree(toolchain, ignore_errors=True)

                result = self.make("-f", "directory-test.mk", *goals)

                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertEqual(images.is_dir(), needs_directories)
                self.assertEqual(toolchain.is_dir(), needs_directories)


if __name__ == "__main__":
    unittest.main()
