"""推荐历史、近期去重和每日 Markdown 音乐日记。"""
import datetime as dt
import json
import logging

from config import HISTORY_FILE, JOURNAL_DIR, STATE_FILE
from scenes import SCENES, normalize_scene

logger = logging.getLogger(__name__)


def _parse_date(value: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def _iter_entries():
    if HISTORY_FILE.exists():
        for line in HISTORY_FILE.read_text(encoding="utf-8").splitlines():
            try:
                yield json.loads(line)
            except (TypeError, ValueError):
                logger.warning("忽略无法解析的历史记录")

    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            yield {"date": state.get("last_push_date"), "songs": state.get("songs", [])}
        except (OSError, ValueError):
            logger.warning("无法读取旧版 state.json 历史")


def recent_song_ids(days: int, today: dt.date | None = None) -> set:
    if days <= 0:
        return set()
    today = today or dt.date.today()
    cutoff = today - dt.timedelta(days=days - 1)
    result = set()
    for entry in _iter_entries():
        entry_date = _parse_date(entry.get("date"))
        if not entry_date or not cutoff <= entry_date <= today:
            continue
        result.update(song.get("id") for song in entry.get("songs", []) if song.get("id"))
    return result


def history_entries(start: dt.date, end: dt.date) -> list[dict]:
    """读取日期区间内的推送历史；仅在没有历史文件时回退到旧版 state。"""
    entries = []
    if HISTORY_FILE.exists():
        for line in HISTORY_FILE.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
            except (TypeError, ValueError):
                continue
            entry_date = _parse_date(entry.get("date"))
            if entry_date and start <= entry_date <= end:
                entries.append(entry)
        return entries

    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        entry_date = _parse_date(state.get("last_push_date"))
        if entry_date and start <= entry_date <= end:
            entries.append(
                {
                    "date": state.get("last_push_date"),
                    "songs": state.get("songs", []),
                    "caption": state.get("caption", ""),
                    "scene": state.get("scene", "default"),
                }
            )
    return entries


def append_history(
    songs: list[dict],
    caption: str,
    pushed_at: dt.datetime | None = None,
    scene: str = "default",
) -> None:
    pushed_at = pushed_at or dt.datetime.now().astimezone()
    entry = {
        "date": pushed_at.date().isoformat(),
        "pushed_at": pushed_at.isoformat(timespec="seconds"),
        "songs": songs,
        "caption": caption,
        "scene": scene,
    }
    with HISTORY_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def write_journal(
    songs: list[dict],
    caption: str,
    day: dt.date | None = None,
    scene: str = "default",
):
    day = day or dt.date.today()
    scene = normalize_scene(scene)
    scene_label = SCENES[scene][0]
    JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
    path = JOURNAL_DIR / f"{day.isoformat()}.md"
    lines = [
        f"# {day.isoformat()} 音乐日记",
        "",
        f"场景：{scene_label}",
        "",
        caption,
        "",
        "## 今日推荐",
        "",
    ]
    for index, song in enumerate(songs, 1):
        artists = "、".join(song.get("artists", [])) or "未知艺人"
        album = song.get("album") or "未知专辑"
        reason = song.get("reason") or "今日推荐"
        lines.append(f"{index}. **《{song.get('name', '未知')}》** - {artists}")
        lines.append(f"   专辑：{album}；推荐理由：{reason}")
        if song.get("explanation"):
            lines.append(f"   评分说明：{song['explanation']}；总分 {song.get('score', 0):.2f}")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return path
