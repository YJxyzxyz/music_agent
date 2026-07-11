import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from profile import TasteProfile
from preferences import UserPreferences
from selector import select_songs


def raw_song(song_id, name, artist):
    return {"id": song_id, "name": name, "ar": [{"name": artist}], "al": {"name": "A"}}


class FakeAPI:
    def __init__(self, songs):
        self.songs = songs

    def recommend_songs(self, limit=30):
        return self.songs

    def recommend_playlists(self):
        return []


class SelectorTests(unittest.TestCase):
    def test_recent_song_is_excluded_when_pool_is_large_enough(self):
        api = FakeAPI([raw_song(1, "旧歌", "甲"), raw_song(2, "新歌", "乙")])
        chosen = select_songs(api, TasteProfile({"甲": 10, "乙": 1}), n=1, exclude_ids={1})
        self.assertEqual([2], [song["id"] for song in chosen])

    def test_recent_song_is_restored_when_needed_to_fill_selection(self):
        api = FakeAPI([raw_song(1, "旧歌", "甲"), raw_song(2, "新歌", "乙")])
        chosen = select_songs(api, TasteProfile({"甲": 10, "乙": 1}), n=2, exclude_ids={1})
        self.assertEqual({1, 2}, {song["id"] for song in chosen})

    def test_preferred_artist_changes_ranking_without_taste_profile(self):
        api = FakeAPI([raw_song(1, "普通", "甲"), raw_song(2, "偏爱", "乙")])
        preferences = UserPreferences(preferred_artists={"乙"})
        chosen = select_songs(api, TasteProfile({}), n=1, preferences=preferences)
        self.assertEqual(2, chosen[0]["id"])
        self.assertEqual("你特别偏爱 乙", chosen[0]["reason"])

    def test_disliked_song_and_blocked_artist_are_filtered(self):
        api = FakeAPI(
            [raw_song(1, "不喜欢", "甲"), raw_song(2, "屏蔽", "乙"), raw_song(3, "保留", "丙")]
        )
        preferences = UserPreferences(blocked_artists={"乙"}, song_feedback={"1": -1})
        chosen = select_songs(api, TasteProfile({}), n=3, preferences=preferences)
        self.assertEqual([3], [song["id"] for song in chosen])

    def test_exploration_reserves_a_slot_for_unfamiliar_artist(self):
        api = FakeAPI(
            [
                raw_song(1, "熟悉一", "甲"),
                raw_song(2, "熟悉二", "乙"),
                raw_song(3, "探索", "丙"),
            ]
        )
        chosen = select_songs(
            api,
            TasteProfile({"甲": 10, "乙": 8}),
            n=2,
            explore_ratio=0.5,
        )
        self.assertEqual([1, 3], [song["id"] for song in chosen])
        self.assertEqual("探索一点新口味", chosen[1]["reason"])

    def test_zero_exploration_keeps_highest_scoring_songs(self):
        api = FakeAPI(
            [
                raw_song(1, "熟悉一", "甲"),
                raw_song(2, "熟悉二", "乙"),
                raw_song(3, "探索", "丙"),
            ]
        )
        chosen = select_songs(
            api,
            TasteProfile({"甲": 10, "乙": 8}),
            n=2,
            explore_ratio=0,
        )
        self.assertEqual([1, 2], [song["id"] for song in chosen])


if __name__ == "__main__":
    unittest.main()
