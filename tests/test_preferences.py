import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import preferences


class PreferenceTests(unittest.TestCase):
    def test_feedback_can_be_changed_without_double_counting_artist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / "state.json"
            prefs = root / "preferences.json"
            events = root / "feedback.jsonl"
            state.write_text(
                json.dumps({"songs": [{"id": 7, "name": "歌", "artists": ["甲"]}]}),
                encoding="utf-8",
            )
            with patch.object(preferences, "STATE_FILE", state), patch.object(
                preferences, "PREFERENCES_FILE", prefs
            ), patch.object(preferences, "FEEDBACK_FILE", events):
                preferences.record_song_feedback("like", 1)
                preferences.record_song_feedback("like", 1)
                current = preferences.load_preferences()
                self.assertEqual(1, current.artist_feedback["甲"])

                preferences.record_song_feedback("dislike", 1)
                current = preferences.load_preferences()
                self.assertEqual(-1, current.artist_feedback["甲"])
                self.assertEqual(-1, current.song_feedback["7"])
                self.assertEqual(3, len(events.read_text(encoding="utf-8").splitlines()))

    def test_neutral_clears_explicit_and_learned_artist_preference(self):
        with tempfile.TemporaryDirectory() as tmp:
            prefs = Path(tmp) / "preferences.json"
            events = Path(tmp) / "feedback.jsonl"
            initial = preferences.UserPreferences(
                preferred_artists={"甲"}, artist_feedback={"甲": 3}
            )
            with patch.object(preferences, "PREFERENCES_FILE", prefs), patch.object(
                preferences, "FEEDBACK_FILE", events
            ):
                preferences.save_preferences(initial)
                preferences.set_artist_preference("neutral", "甲")
                current = preferences.load_preferences()
            self.assertNotIn("甲", current.preferred_artists)
            self.assertNotIn("甲", current.artist_feedback)


if __name__ == "__main__":
    unittest.main()
