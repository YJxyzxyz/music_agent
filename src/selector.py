"""选歌：构建候选歌池，按听歌画像打分，挑选 N 首兼顾偏好的歌曲。"""
import logging

from config import settings
from preferences import UserPreferences
from profile import TasteProfile

logger = logging.getLogger(__name__)


def _normalize_song(song: dict) -> dict:
    artists = [ar.get("name", "") for ar in song.get("ar", []) if ar.get("name")]
    album = song.get("al", {}).get("name", "")
    return {
        "id": song.get("id"),
        "name": song.get("name", "未知"),
        "artists": artists,
        "album": album,
    }


def build_pool(api, profile: TasteProfile) -> list[dict]:
    pool: list[dict] = []

    # 1) 每日推荐歌曲（最个性化）
    try:
        for s in api.recommend_songs(limit=30):
            pool.append(_normalize_song(s))
    except Exception as e:
        logger.warning("读取每日推荐歌曲失败：%s", e)

    # 2) 推荐歌单里的歌曲，扩充候选
    try:
        playlists = api.recommend_playlists()[: settings.n_playlists]
        for pl in playlists:
            pid = pl.get("id")
            if not pid:
                continue
            detail = api.playlist_detail(pid)
            for tr in detail.get("tracks", [])[:50]:
                pool.append(_normalize_song(tr))
    except Exception as e:
        logger.warning("读取推荐歌单失败：%s", e)

    # 去重（按 id）
    seen, unique = set(), []
    for s in pool:
        if s["id"] in seen:
            continue
        seen.add(s["id"])
        unique.append(s)
    return unique


def score_song(
    song: dict,
    profile: TasteProfile,
    preferences: UserPreferences | None = None,
) -> float:
    sc = 0.0
    for art in song["artists"]:
        sc += profile.normalized(art)
    if preferences:
        sc += preferences.adjustment(song)
    return sc


def select_songs(
    api,
    profile: TasteProfile,
    n: int | None = None,
    exclude_ids: set | None = None,
    preferences: UserPreferences | None = None,
    explore_ratio: float | None = None,
) -> list[dict]:
    n = n or settings.n_songs
    pool = build_pool(api, profile)
    if not pool:
        return []

    preferences = preferences or UserPreferences()
    explore_ratio = settings.explore_ratio if explore_ratio is None else explore_ratio
    explore_ratio = min(1.0, max(0.0, explore_ratio))
    available = []
    blocked_count = 0
    for song in pool:
        if preferences.blocks(song) or preferences.dislikes(song):
            blocked_count += 1
        else:
            available.append(song)
    pool = available
    if blocked_count:
        logger.info("个人反馈过滤 %s 首不喜欢歌曲或已屏蔽艺人的歌曲", blocked_count)

    exclude_ids = exclude_ids or set()
    fresh = [s for s in pool if s["id"] not in exclude_ids]
    repeated = [s for s in pool if s["id"] in exclude_ids]
    if repeated:
        logger.info("历史去重排除 %s 首近期推荐；候选不足时会自动补回", len(repeated))

    scored = [(score_song(s, profile, preferences), s) for s in fresh]
    if len(fresh) < n:
        logger.warning("去重后仅剩 %s 首候选，放宽历史限制补齐推荐", len(fresh))
        scored.extend((score_song(s, profile, preferences), s) for s in repeated)
    scored.sort(key=lambda x: x[0], reverse=True)

    chosen: list[dict] = []
    artist_count: dict[str, int] = {}
    max_per_artist = 2  # 多样性保护：同一艺人最多 2 首
    exploration_ids = set()

    def take(candidates, limit: int, enforce_diversity: bool = True) -> None:
        chosen_ids = {song["id"] for song in chosen}
        for _, song in candidates:
            if len(chosen) >= limit or song["id"] in chosen_ids:
                continue
            primary = song["artists"][0] if song["artists"] else ""
            if enforce_diversity and artist_count.get(primary, 0) >= max_per_artist:
                continue
            chosen.append(song)
            chosen_ids.add(song["id"])
            artist_count[primary] = artist_count.get(primary, 0) + 1

    explore_count = min(n, int(n * explore_ratio + 0.5))
    familiar_count = n - explore_count
    take(scored, familiar_count)

    # 探索位从低熟悉度候选中选择，仍保留网易云候选池原本的个性化顺序。
    chosen_ids = {song["id"] for song in chosen}
    explore_candidates = []
    for song in fresh:
        score = score_song(song, profile, preferences)
        if song["id"] not in chosen_ids and score <= 0.25:
            explore_candidates.append((score, song))
    before_explore = set(chosen_ids)
    take(explore_candidates, n)
    exploration_ids.update(song["id"] for song in chosen if song["id"] not in before_explore)

    # 探索候选不足时回到完整评分池，并最终放宽艺人多样性以补齐。
    if len(chosen) < n:
        take(scored, n)
    if len(chosen) < n:
        take(scored, n, enforce_diversity=False)

    # 附加推荐理由
    for s in chosen:
        preference_reason = preferences.reason(s)
        tops = [a for a in s["artists"] if a in profile.artist_set]
        if s["id"] in exploration_ids:
            s["reason"] = "探索一点新口味"
        else:
            s["reason"] = preference_reason or (f"你常听 {tops[0]}" if tops else "今日新鲜推荐")
    return chosen
