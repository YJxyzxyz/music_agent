"""聚合最近一周的推荐与反馈，生成音乐偏好和心情周报。"""
from collections import Counter
import datetime as dt
from html import escape
import json
import logging

from caption import generate_weekly_mood_summary
from config import FEEDBACK_FILE, REPORT_DIR
from history import history_entries
from pusher import push_html
from scenes import SCENES, normalize_scene

logger = logging.getLogger(__name__)


def resolve_period(end_date: dt.date | str | None = None) -> tuple[dt.date, dt.date]:
    if isinstance(end_date, str):
        try:
            end_date = dt.date.fromisoformat(end_date)
        except ValueError as exc:
            raise ValueError("结束日期必须使用 YYYY-MM-DD 格式。") from exc
    end = end_date or dt.date.today()
    return end - dt.timedelta(days=6), end


def _feedback_events(start: dt.date, end: dt.date) -> list[dict]:
    if not FEEDBACK_FILE.exists():
        return []
    latest_by_song = {}
    for line in FEEDBACK_FILE.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
            created = dt.datetime.fromisoformat(event.get("created_at", "")).date()
        except (TypeError, ValueError):
            continue
        if event.get("type") != "song" or not start <= created <= end:
            continue
        song_id = str((event.get("song") or {}).get("id"))
        latest_by_song.pop(song_id, None)
        latest_by_song[song_id] = event
    return list(latest_by_song.values())


def collect_weekly_stats(start: dt.date, end: dt.date) -> dict:
    entries = history_entries(start, end)
    if not entries:
        raise ValueError(f"{start} 至 {end} 没有成功推送记录，无法生成周报。")

    songs = [song for entry in entries for song in entry.get("songs", [])]
    artists = Counter(
        artist
        for song in songs
        for artist in song.get("artists", [])
        if artist
    )
    scenes = Counter(normalize_scene(entry.get("scene")) for entry in entries)
    sources = Counter(song.get("source") or "未知来源" for song in songs)
    feedback = _feedback_events(start, end)
    liked = [(event.get("song") or {}) for event in feedback if event.get("action") == "like"]
    disliked = [(event.get("song") or {}) for event in feedback if event.get("action") == "dislike"]
    explored = [song for song in songs if song.get("reason") == "探索一点新口味"]
    explored_ids = {str(song.get("id")) for song in explored}
    explore_feedback = [
        event for event in feedback if str((event.get("song") or {}).get("id")) in explored_ids
    ]
    explore_likes = sum(event.get("action") == "like" for event in explore_feedback)
    explore_dislikes = sum(event.get("action") == "dislike" for event in explore_feedback)
    rated_explores = explore_likes + explore_dislikes

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "active_days": len({entry.get("date") for entry in entries}),
        "recommendation_count": len(songs),
        "top_artists": artists.most_common(8),
        "scenes": [
            {"key": key, "label": SCENES[key][0], "count": count}
            for key, count in scenes.most_common()
        ],
        "sources": sources.most_common(5),
        "liked_songs": liked,
        "disliked_songs": disliked,
        "explore_count": len(explored),
        "explore_likes": explore_likes,
        "explore_dislikes": explore_dislikes,
        "explore_acceptance": round(explore_likes / rated_explores, 3) if rated_explores else None,
        "songs": songs,
    }


def _song_label(song: dict) -> str:
    artists = "、".join(song.get("artists", [])) or "未知艺人"
    return f"《{song.get('name', '未知')}》- {artists}"


def _mood_input(stats: dict) -> dict:
    return {
        "period": f"{stats['start']} 至 {stats['end']}",
        "top_artists": stats["top_artists"],
        "liked_songs": [_song_label(song) for song in stats["liked_songs"]],
        "disliked_songs": [_song_label(song) for song in stats["disliked_songs"]],
        "recommended_songs": [_song_label(song) for song in stats["songs"][:35]],
        "scenes": stats["scenes"],
        "note": "这些是推荐记录与明确反馈，不等同于完整的实际播放历史。",
    }


def build_markdown(stats: dict, mood_summary: str) -> str:
    lines = [
        f"# 音乐周报：{stats['start']} 至 {stats['end']}",
        "",
        "## 一周心情",
        "",
        mood_summary,
        "",
        "## 偏好概览",
        "",
        f"- 有推荐记录的天数：{stats['active_days']} 天",
        f"- 推荐歌曲：{stats['recommendation_count']} 首",
        f"- 喜欢反馈：{len(stats['liked_songs'])} 首",
        f"- 不喜欢反馈：{len(stats['disliked_songs'])} 首",
        f"- 探索歌曲：{stats['explore_count']} 首",
    ]
    if stats["explore_acceptance"] is not None:
        lines.append(f"- 已评价探索歌曲接受率：{stats['explore_acceptance']:.0%}")

    lines.extend(["", "## 常出现的艺人", ""])
    if stats["top_artists"]:
        lines.extend(
            f"- {artist}：{count} 首" for artist, count in stats["top_artists"]
        )
    else:
        lines.append("- 暂无艺人数据")

    lines.extend(["", "## 明确反馈", "", "### 喜欢", ""])
    lines.extend(f"- {_song_label(song)}" for song in stats["liked_songs"])
    if not stats["liked_songs"]:
        lines.append("- 本周暂无喜欢反馈")
    lines.extend(["", "### 不喜欢", ""])
    lines.extend(f"- {_song_label(song)}" for song in stats["disliked_songs"])
    if not stats["disliked_songs"]:
        lines.append("- 本周暂无不喜欢反馈")

    lines.extend(["", "## 场景分布", ""])
    lines.extend(f"- {item['label']}：{item['count']} 次" for item in stats["scenes"])
    lines.extend(
        [
            "",
            "> 说明：网易云实际播放排行接口已不可用，本报告基于本周成功推送记录与明确反馈，心情总结仅作音乐偏好的轻量回顾。",
            "",
        ]
    )
    return "\n".join(lines)


def build_html(stats: dict, mood_summary: str) -> str:
    artist_items = "".join(
        f"<li>{escape(artist)}：{count} 首</li>" for artist, count in stats["top_artists"]
    ) or "<li>暂无艺人数据</li>"
    liked_items = "".join(
        f"<li>{escape(_song_label(song))}</li>" for song in stats["liked_songs"]
    ) or "<li>本周暂无喜欢反馈</li>"
    mood = escape(mood_summary).replace("\n", "<br>")
    acceptance = (
        f"<li>已评价探索歌曲接受率：{stats['explore_acceptance']:.0%}</li>"
        if stats["explore_acceptance"] is not None
        else ""
    )
    return (
        f"<h2>音乐周报 · {stats['start']} 至 {stats['end']}</h2>"
        f"<h3>一周心情</h3><p style='line-height:1.7'>{mood}</p>"
        "<h3>偏好概览</h3><ul>"
        f"<li>活跃 {stats['active_days']} 天，推荐 {stats['recommendation_count']} 首</li>"
        f"<li>喜欢 {len(stats['liked_songs'])} 首，不喜欢 {len(stats['disliked_songs'])} 首</li>"
        f"<li>探索歌曲 {stats['explore_count']} 首</li>{acceptance}</ul>"
        f"<h3>常出现的艺人</h3><ul>{artist_items}</ul>"
        f"<h3>本周喜欢</h3><ul>{liked_items}</ul>"
        "<hr><small>基于成功推送记录与明确反馈；心情内容仅作音乐偏好的轻量回顾。</small>"
    )


def generate_weekly_report(
    end_date: dt.date | str | None = None,
    push_report: bool = False,
) -> dict:
    start, end = resolve_period(end_date)
    stats = collect_weekly_stats(start, end)
    mood_summary = generate_weekly_mood_summary(_mood_input(stats))
    markdown = build_markdown(stats, mood_summary)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"{start.isoformat()}_to_{end.isoformat()}.md"
    path.write_text(markdown, encoding="utf-8")

    push_result = None
    if push_report:
        push_result = push_html(
            f"🎧 音乐周报 · {end.isoformat()}",
            build_html(stats, mood_summary),
        )
    logger.info("音乐周报已生成：%s", path)
    return {
        "path": str(path),
        "stats": stats,
        "mood_summary": mood_summary,
        "push": push_result,
    }
