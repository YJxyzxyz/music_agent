import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pusher import _build_html


class PusherHtmlTests(unittest.TestCase):
    def test_html_contains_score_explanation_and_escapes_content(self):
        songs = [
            {
                "name": "A < B",
                "artists": ["甲 & 乙"],
                "album": "专辑",
                "reason": "探索一点新口味",
                "explanation": "画像 0.00 + 偏好 +0.00；来源：每日推荐",
            }
        ]
        html = _build_html(songs, "一句 <配文>\n第二句")
        self.assertIn("画像 0.00", html)
        self.assertIn("A &lt; B", html)
        self.assertIn("甲 &amp; 乙", html)
        self.assertIn("一句 &lt;配文&gt;<br>第二句", html)


if __name__ == "__main__":
    unittest.main()
