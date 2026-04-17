import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sysroot
from build import resolve_ndk_path


class SysrootManifestTests(unittest.TestCase):
    def test_manifest_round_trip_skips_download_when_inputs_match(self):
        with tempfile.TemporaryDirectory() as td:
            root = sysroot.Sysroot(
                path=td,
                termux_main={
                    "repo": "https://packages-cf.termux.dev/apt/termux-main/",
                    "dist": "stable",
                    "pkgs": ["glib"],
                },
            )

            def consume(coro):
                coro.close()

            with patch("sysroot.asyncio.run", side_effect=consume) as run:
                root("arm64")
                self.assertEqual(run.call_count, 1)

            with patch("sysroot.asyncio.run", side_effect=consume) as run:
                root("arm64")
                self.assertEqual(run.call_count, 0)

            manifest = Path(td, ".termux-sysroot-manifest.json")
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(payload["arch"], "aarch64")
            self.assertEqual(payload["schema"], 1)

    def test_resolve_ndk_path_prefers_environment_override(self):
        with patch.dict("os.environ", {"ANDROID_NDK": "/tmp/from-env"}, clear=False):
            self.assertEqual(resolve_ndk_path("/tmp/from-config"), "/tmp/from-env")

        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(resolve_ndk_path("/tmp/from-config"), "/tmp/from-config")


if __name__ == "__main__":
    unittest.main()
