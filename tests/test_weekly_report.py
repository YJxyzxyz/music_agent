import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import weekly_report


def song(song_id, name, artist, reason="你常听"):
    return {
        "id": song_id,
        "name": name,
        "artists": [artist],
        "reason": reason,
        "source": "每日推荐",
    }


class WeeklyReportTests(unittest.TestCase):
    def test_collects_preferences_and_latest_feedback(self):
        entries = [
            {
                "date": "2026-07-10",
                "scene": "night",
                "songs": [song(1, "探索歌", "甲", "探索一点新口味"), song(2, "熟悉歌", "乙")],
            }
        ]
        feedback_events = [
            {"type": "song", "action": "like", "created_at": "2026-07-10T10:00:00+08:00", "song": song(1, "探索歌", "甲", "探索一点新口味")},
            {"type": "song", "action": "dislike", "created_at": "2026-07-10T11:00:00+08:00", "song": song(1, "探索歌", "甲", "探索一点新口味")},
            {"type": "song", "action": "like", "created_at": "2026-07-10T12:00:00+08:00", "song": song(2, "熟悉歌", "乙")},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            feedback = Path(tmp) / "feedback.jsonl"
            feedback.write_text(
                "\n".join(json.dumps(event, ensure_ascii=False) for event in feedback_events),
                encoding="utf-8",
            )
            with patch.object(weekly_report, "FEEDBACK_FILE", feedback), patch(
                "weekly_report.history_entries", return_value=entries
            ):
                stats = weekly_report.collect_weekly_stats(
                    dt.date(2026, 7, 5), dt.date(2026, 7, 11)
                )
        self.assertEqual(2, stats["recommendation_count"])
        self.assertEqual([["甲", 1], ["乙", 1]], [list(item) for item in stats["top_artists"]])
        self.assertEqual(["熟悉歌"], [item["name"] for item in stats["liked_songs"]])
        self.assertEqual(["探索歌"], [item["name"] for item in stats["disliked_songs"]])
        self.assertEqual(0.0, stats["explore_acceptance"])
        self.assertEqual("夜晚", stats["scenes"][0]["label"])

    def test_generate_writes_markdown_and_optionally_pushes(self):
        stats = {
            "start": "2026-07-05",
            "end": "2026-07-11",
            "active_days": 2,
            "recommendation_count": 10,
            "top_artists": [("甲", 3)],
            "scenes": [{"key": "night", "label": "夜晚", "count": 2}],
            "sources": [("每日推荐", 10)],
            "liked_songs": [song(1, "喜欢", "甲")],
            "disliked_songs": [],
            "explore_count": 2,
            "explore_likes": 1,
            "explore_dislikes": 0,
            "explore_acceptance": 1.0,
            "songs": [song(1, "喜欢", "甲")],
        }
        with tempfile.TemporaryDirectory() as tmp, patch.object(
            weekly_report, "REPORT_DIR", Path(tmp)
        ), patch("weekly_report.collect_weekly_stats", return_value=stats), patch(
            "weekly_report.generate_weekly_mood_summary", return_value="这一周的音乐偏好显得舒展。"
        ), patch("weekly_report.push_html", return_value={"code": 200}) as push_mock:
            result = weekly_report.generate_weekly_report(
                end_date="2026-07-11", push_report=True
            )
            content = Path(result["path"]).read_text(encoding="utf-8")
        self.assertIn("一周心情", content)
        self.assertIn("这一周的音乐偏好显得舒展", content)
        self.assertIn("接受率：100%", content)
        push_mock.assert_called_once()

    def test_no_history_has_clear_error(self):
        with patch("weekly_report.history_entries", return_value=[]):
            with self.assertRaisesRegex(ValueError, "没有成功推送记录"):
                weekly_report.collect_weekly_stats(
                    dt.date(2026, 7, 5), dt.date(2026, 7, 11)
                )


if __name__ == "__main__":
    unittest.main()
