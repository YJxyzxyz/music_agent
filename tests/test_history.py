import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import history


class HistoryTests(unittest.TestCase):
    def test_recent_ids_reads_jsonl_and_legacy_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            history_file = root / "history.jsonl"
            state_file = root / "state.json"
            history_file.write_text(
                json.dumps({"date": "2026-07-10", "songs": [{"id": 10}]}) + "\n",
                encoding="utf-8",
            )
            state_file.write_text(
                json.dumps({"last_push_date": "2026-07-11", "songs": [{"id": 11}]}),
                encoding="utf-8",
            )
            with patch.object(history, "HISTORY_FILE", history_file), patch.object(
                history, "STATE_FILE", state_file
            ):
                result = history.recent_song_ids(2, today=dt.date(2026, 7, 11))
            self.assertEqual({10, 11}, result)

    def test_write_journal_creates_readable_markdown(self):
        songs = [{"name": "歌名", "artists": ["歌手"], "album": "专辑", "reason": "推荐理由"}]
        with tempfile.TemporaryDirectory() as tmp, patch.object(history, "JOURNAL_DIR", Path(tmp)):
            path = history.write_journal(songs, "今日配文", day=dt.date(2026, 7, 11))
            content = path.read_text(encoding="utf-8")
        self.assertIn("# 2026-07-11 音乐日记", content)
        self.assertIn("《歌名》", content)
        self.assertIn("今日配文", content)

    def test_write_journal_uses_localized_scene_name(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(history, "JOURNAL_DIR", Path(tmp)):
            path = history.write_journal([], "夜间配文", day=dt.date(2026, 7, 11), scene="night")
            content = path.read_text(encoding="utf-8")
        self.assertIn("场景：夜晚", content)


if __name__ == "__main__":
    unittest.main()
