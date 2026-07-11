import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scenes import normalize_scene


class SceneTests(unittest.TestCase):
    def test_known_scene_is_preserved(self):
        self.assertEqual("night", normalize_scene("night"))

    def test_unknown_scene_falls_back_to_default(self):
        self.assertEqual("default", normalize_scene("unexpected"))


if __name__ == "__main__":
    unittest.main()
