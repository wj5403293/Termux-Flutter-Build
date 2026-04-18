import tempfile
import unittest
from pathlib import Path

from package import explore_file


class PackageWalkTests(unittest.TestCase):
    def test_explore_file_walks_directories(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            nested = root / "nested"
            nested.mkdir()
            file_path = nested / "file.txt"
            file_path.write_text("ok", encoding="utf-8")

            items = list(explore_file(root))

        self.assertIn(Path("nested"), items)
        self.assertIn(Path("nested/file.txt"), items)


if __name__ == "__main__":
    unittest.main()
