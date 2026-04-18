import unittest
from pathlib import Path
from unittest.mock import patch

import build


class DebuildTests(unittest.TestCase):
    def test_debuild_does_not_require_windows_sync_hook(self):
        runner = build.Build.__new__(build.Build)
        runner.package = {"control": {}, "resource": {}, "define": {}}
        runner.root = Path("/tmp/flutter-root")

        with patch("build.Package") as package_cls:
            package_instance = package_cls.return_value

            runner.debuild(arch="arm64", output="/tmp/flutter.deb", root="/tmp/flutter-root")

        package_cls.assert_called_once_with(root="/tmp/flutter-root", arch="arm64", control={}, resource={}, define={})
        package_instance.debuild.assert_called_once_with(output="/tmp/flutter.deb", section=None)


if __name__ == "__main__":
    unittest.main()
