import unittest
from pathlib import Path
from unittest.mock import patch

import build


class CommandBuilderTests(unittest.TestCase):
    def test_build_flutter_core_omits_flutter_gtk_target(self):
        runner = build.Build.__new__(build.Build)
        runner.jobs = 8

        with patch("build.subprocess.run") as run:
            runner.build_flutter_core("arm64", "debug", root="/tmp/flutter", jobs=8)

        cmd = run.call_args.args[0]
        self.assertIn("flutter", cmd)
        self.assertNotIn("flutter/shell/platform/linux:flutter_gtk", cmd)

    def test_build_linux_desktop_only_builds_flutter_gtk(self):
        runner = build.Build.__new__(build.Build)
        runner.jobs = 8

        with patch("build.subprocess.run") as run:
            runner.build_linux_desktop("arm64", "debug", root="/tmp/flutter", jobs=8)

        cmd = run.call_args.args[0]
        self.assertIn("flutter/shell/platform/linux:flutter_gtk", cmd)
        self.assertNotIn("dartaotruntime_product", cmd)


class RecordingBuild(build.Build):
    def __init__(self):
        self.events = []
        self.release = Path(".")
        self.tag = "3.41.5"

    def configure(self, arch, mode, **kwargs):
        self.events.append(("configure", mode))

    def build_flutter_core(self, arch, mode, **kwargs):
        self.events.append(("core", mode))

    def build_linux_desktop(self, arch, mode, **kwargs):
        self.events.append(("linux", mode))

    def build_dart(self, arch, mode, **kwargs):
        self.events.append(("dart", mode))

    def build_impellerc(self, arch, mode, **kwargs):
        self.events.append(("impellerc", mode))

    def build_const_finder(self, arch, mode, **kwargs):
        self.events.append(("const_finder", mode))

    def prepare_web_sdk(self, **kwargs):
        self.events.append(("web", "prepare"))

    def configure_android(self, arch="arm64", mode="release", **kwargs):
        self.events.append(("configure_android", mode))

    def build_android_gen_snapshot(self, arch="arm64", mode="release", **kwargs):
        self.events.append(("android", mode))

    def debuild(self, arch, output=None, root=None, section=None, **kwargs):
        self.events.append(("package", tuple(section or [])))

    def output(self, arch):
        return Path("release/flutter_test.deb")


class BuildSelectedTests(unittest.TestCase):
    def test_termux_build_selected_skips_linux_desktop_and_profile(self):
        runner = RecordingBuild()
        runner.build_selected(arch="arm64", preset="termux", jobs=4)

        self.assertIn(("web", "prepare"), runner.events)
        self.assertIn(("core", "debug"), runner.events)
        self.assertIn(("android", "release"), runner.events)
        self.assertNotIn(("linux", "debug"), runner.events)
        self.assertNotIn(("configure_android", "profile"), runner.events)
        self.assertTrue(any(event[0] == "package" for event in runner.events))

    def test_android_release_only_skips_packaging(self):
        runner = RecordingBuild()
        runner.build_selected(arch="arm64", preset="android-release-only", jobs=4)

        self.assertIn(("android", "release"), runner.events)
        self.assertFalse(any(event[0] == "package" for event in runner.events))


if __name__ == "__main__":
    unittest.main()
