import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from package import explore_file


class PackagePy311CompatibilityTests(unittest.TestCase):
    def test_explore_file_walks_directories_without_path_walk(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nested = root / "nested"
            nested.mkdir()
            file_path = nested / "file.txt"
            file_path.write_text("ok", encoding="utf-8")

            with patch.object(Path, "walk", side_effect=AttributeError("walk")):
                items = list(explore_file(root))

        self.assertIn(Path("nested"), items)
        self.assertIn(Path("nested/file.txt"), items)


if __name__ == "__main__":
    unittest.main()
