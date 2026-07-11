import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import drafts


class DraftStorageTests(unittest.TestCase):
    def test_round_trip(self):
        draft = {"id": "abc", "songs": [{"id": 1}], "caption": "文案"}
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            drafts, "DRAFT_FILE", Path(tmp) / "draft.json"
        ):
            drafts.save_draft(draft)
            loaded = drafts.load_draft()
        self.assertEqual(draft, loaded)

    def test_missing_draft_has_clear_error(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            drafts, "DRAFT_FILE", Path(tmp) / "draft.json"
        ):
            with self.assertRaisesRegex(ValueError, "没有推荐草稿"):
                drafts.load_draft()


if __name__ == "__main__":
    unittest.main()
