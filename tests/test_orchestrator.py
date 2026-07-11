import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import orchestrator
from profile import TasteProfile


SONG = {
    "id": 1,
    "name": "歌",
    "artists": ["甲"],
    "album": "专辑",
    "reason": "你常听 甲",
    "score": 1.0,
}


class DraftWorkflowTests(unittest.TestCase):
    @patch("orchestrator.write_draft_preview")
    @patch("orchestrator.save_draft")
    @patch("orchestrator.generate_caption", return_value="配文")
    @patch("orchestrator.select_songs", return_value=[SONG.copy()])
    @patch("orchestrator.adaptive_explore_strategy", return_value={"base_ratio": 0.2, "effective_ratio": 0.2, "explore_likes": 0, "explore_dislikes": 0})
    @patch("orchestrator.load_preferences")
    @patch("orchestrator.recent_song_ids", return_value=set())
    @patch("orchestrator.build_profile", return_value=TasteProfile({"甲": 1}))
    @patch("orchestrator.ensure_login")
    @patch("orchestrator.NeteaseAPI")
    @patch("orchestrator.push")
    def test_create_draft_never_pushes(
        self,
        push_mock,
        api_class,
        ensure_login,
        build_profile,
        recent_song_ids,
        load_preferences,
        strategy,
        select_songs,
        generate_caption,
        save_draft,
        write_preview,
    ):
        api_class.return_value.user_id.return_value = "1"
        draft = orchestrator.create_draft(scene="night")
        self.assertEqual("draft", draft["status"])
        self.assertEqual("night", draft["scene"])
        push_mock.assert_not_called()
        save_draft.assert_called_once()

    @patch("orchestrator.write_draft_preview")
    @patch("orchestrator.save_draft")
    @patch("orchestrator.generate_caption", return_value="新配文")
    @patch("orchestrator.load_draft")
    def test_regenerate_keeps_songs_and_increments_revision(
        self, load_draft, generate_caption, save_draft, write_preview
    ):
        songs = [SONG.copy()]
        load_draft.return_value = {
            "id": "abc",
            "status": "draft",
            "revision": 1,
            "scene": "default",
            "songs": songs,
            "caption": "旧配文",
        }
        result = orchestrator.regenerate_draft(scene="focus")
        self.assertIs(songs, result["songs"])
        self.assertEqual("新配文", result["caption"])
        self.assertEqual(2, result["revision"])
        self.assertEqual("focus", result["scene"])

    @patch("orchestrator.push")
    @patch("orchestrator.load_draft")
    def test_pushed_draft_cannot_be_sent_twice(self, load_draft, push_mock):
        load_draft.return_value = {
            "id": "abc",
            "status": "pushed",
            "songs": [SONG.copy()],
            "caption": "配文",
            "scene": "default",
        }
        with self.assertRaisesRegex(ValueError, "已经推送"):
            orchestrator.publish_draft()
        push_mock.assert_not_called()

    @patch("orchestrator.write_journal", return_value=Path("journal.md"))
    @patch("orchestrator.append_history")
    @patch("orchestrator._save_state")
    @patch("orchestrator.save_draft")
    @patch("orchestrator.push", return_value={"code": 200})
    @patch("orchestrator.load_draft")
    def test_publish_marks_draft_and_archives_success(
        self,
        load_draft,
        push_mock,
        save_draft,
        save_state,
        append_history,
        write_journal,
    ):
        draft = {
            "id": "abc",
            "status": "draft",
            "songs": [SONG.copy()],
            "caption": "配文",
            "scene": "default",
        }
        load_draft.return_value = draft
        result = orchestrator.publish_draft()
        self.assertEqual("pushed", draft["status"])
        self.assertEqual(200, draft["push_code"])
        push_mock.assert_called_once_with(draft["songs"], "配文")
        save_draft.assert_called_once_with(draft)
        save_state.assert_called_once_with(draft)
        append_history.assert_called_once()
        write_journal.assert_called_once()
        self.assertEqual("journal.md", result["journal"])


if __name__ == "__main__":
    unittest.main()
