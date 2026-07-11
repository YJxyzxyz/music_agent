"""听歌画像：从『我喜欢的音乐』反推用户偏好的艺人权重，用于后续选歌打分。

注：网易云已下线 user/record（听歌排行）接口，故用 likelist 作为画像数据源。
"""
import logging

logger = logging.getLogger(__name__)


class TasteProfile:
    def __init__(self, artist_weights: dict[str, float]):
        self.artist_weights = dict(
            sorted(artist_weights.items(), key=lambda kv: kv[1], reverse=True)
        )
        self.artist_set = set(self.artist_weights.keys())
        self.max_weight = max(self.artist_weights.values()) if self.artist_weights else 1.0

    def artist_score(self, artist_name: str) -> float:
        return self.artist_weights.get(artist_name, 0.0)

    def normalized(self, artist_name: str) -> float:
        w = self.artist_score(artist_name)
        return w / self.max_weight if self.max_weight else 0.0

    def top_artists(self, n: int = 10) -> list[str]:
        return list(self.artist_weights.keys())[:n]

    def describe(self) -> str:
        top = "、".join(self.top_artists(8))
        return f"你常听的艺人：{top}"


def _batch(iterable, n):
    for i in range(0, len(iterable), n):
        yield iterable[i : i + n]


def build_profile(api, uid: str, cap: int = 300) -> TasteProfile:
    ids = api.likelist(uid, cap=cap)
    if not ids:
        logger.warning("未取到『我喜欢的音乐』，将退化为无画像挑选")
        return TasteProfile({})

    weights: dict[str, float] = {}
    for chunk in _batch(ids, 100):
        try:
            songs = api.song_detail(chunk)
        except Exception as e:
            logger.warning("批量获取歌曲详情失败：%s", e)
            continue
        for s in songs:
            for ar in s.get("ar", []):
                name = ar.get("name")
                if name:
                    weights[name] = weights.get(name, 0) + 1

    if not weights:
        logger.warning("未解析到艺人信息，将退化为无画像挑选")
    else:
        logger.info("基于 %s 首喜欢歌曲构建，覆盖 %s 位艺人", len(ids), len(weights))
    return TasteProfile(weights)
