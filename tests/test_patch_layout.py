import unittest

from build import Build


class PatchLayoutTests(unittest.TestCase):
    def test_patch_files_are_resolved_from_root_patches_dir(self):
        runner = Build()

        self.assertEqual(runner.patches["engine"]["file"].name, "engine.patch")
        self.assertEqual(runner.patches["engine"]["file"].parent.name, "patches")
        self.assertNotIn("3.41.5", str(runner.patches["engine"]["file"]))


if __name__ == "__main__":
    unittest.main()
