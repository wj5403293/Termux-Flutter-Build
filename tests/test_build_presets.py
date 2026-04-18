import unittest

from build import BuildPreset, resolve_preset


class ResolvePresetTests(unittest.TestCase):
    def test_termux_preset_keeps_web_and_android_release_only(self):
        plan = resolve_preset("termux")

        self.assertIsInstance(plan, BuildPreset)
        self.assertTrue(plan.prepare_web_sdk)
        self.assertTrue(plan.build_android_release)
        self.assertTrue(plan.package_deb)
        self.assertFalse(plan.build_linux_desktop)
        self.assertFalse(plan.build_linux_profile)
        self.assertFalse(plan.build_android_profile)
        self.assertIn("flutter_web_sdk", plan.package_sections)
        self.assertNotIn("flutter_linux_gtk_profile", plan.package_sections)

    def test_unknown_removed_android_release_only_preset_raises(self):
        with self.assertRaises(ValueError):
            resolve_preset("android-release-only")

    def test_unknown_preset_raises_value_error(self):
        with self.assertRaises(ValueError):
            resolve_preset("nope")


if __name__ == "__main__":
    unittest.main()
