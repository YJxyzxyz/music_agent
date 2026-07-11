"""选歌：构建候选歌池，按听歌画像打分，挑选 N 首兼顾偏好的歌曲。"""
from config import settings
from profile import TasteProfile


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
        print(f"[选歌] 读取每日推荐歌曲失败：{e}")

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
        print(f"[选歌] 读取推荐歌单失败：{e}")

    # 去重（按 id）
    seen, unique = set(), []
    for s in pool:
        if s["id"] in seen:
            continue
        seen.add(s["id"])
        unique.append(s)
    return unique


def score_song(song: dict, profile: TasteProfile) -> float:
    if not profile.artist_set:
        return 0.0
    sc = 0.0
    for art in song["artists"]:
        sc += profile.normalized(art)
    return sc


def select_songs(api, profile: TasteProfile, n: int | None = None) -> list[dict]:
    n = n or settings.n_songs
    pool = build_pool(api, profile)
    if not pool:
        return []

    scored = [(score_song(s, profile), s) for s in pool]
    scored.sort(key=lambda x: x[0], reverse=True)

    chosen: list[dict] = []
    artist_count: dict[str, int] = {}
    max_per_artist = 2  # 多样性保护：同一艺人最多 2 首

    # 第一轮：优先高分且不过度集中的
    for sc, s in scored:
        if len(chosen) >= n:
            break
        primary = s["artists"][0] if s["artists"] else ""
        if artist_count.get(primary, 0) >= max_per_artist:
            continue
        chosen.append(s)
        artist_count[primary] = artist_count.get(primary, 0) + 1

    # 第二轮：若不足 n，放宽多样性限制补齐
    if len(chosen) < n:
        chosen_ids = {c["id"] for c in chosen}
        for sc, s in scored:
            if len(chosen) >= n:
                break
            if s["id"] in chosen_ids:
                continue
            chosen.append(s)

    # 附加推荐理由
    for s in chosen:
        tops = [a for a in s["artists"] if a in profile.artist_set]
        s["reason"] = f"你常听 {tops[0]}" if tops else "今日新鲜推荐"
    return chosen
