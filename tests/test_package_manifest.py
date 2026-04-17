import unittest

import yaml

from build import resolve_preset


class PackageManifestTests(unittest.TestCase):
    def test_package_yaml_defines_web_and_split_artifact_resources(self):
        with open("package.yaml", "rb") as fh:
            data = yaml.safe_load(fh)

        resources = data["resource"]
        self.assertIn("flutter_web_sdk", resources)
        self.assertIn("engine_common_artifacts", resources)
        self.assertIn("linux_gen_snapshot", resources)
        self.assertNotIn("artifacts", resolve_preset("termux").package_sections)

    def test_termux_sections_exclude_linux_profile_payloads(self):
        sections = resolve_preset("termux").package_sections

        self.assertNotIn("flutter_linux_gtk_profile", sections)
        self.assertNotIn("android_gen_snapshot_arm64_profile", sections)
        self.assertIn("android_gen_snapshot_arm64", sections)
        self.assertIn("flutter_web_sdk", sections)


if __name__ == "__main__":
    unittest.main()
