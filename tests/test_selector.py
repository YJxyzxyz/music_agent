import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from profile import TasteProfile
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


if __name__ == "__main__":
    unittest.main()
