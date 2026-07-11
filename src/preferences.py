"""个人反馈与艺人偏好的持久化模型。"""
from dataclasses import dataclass, field
import datetime as dt
import json

from config import FEEDBACK_FILE, PREFERENCES_FILE, STATE_FILE


@dataclass
class UserPreferences:
    blocked_artists: set[str] = field(default_factory=set)
    preferred_artists: set[str] = field(default_factory=set)
    song_feedback: dict[str, int] = field(default_factory=dict)
    artist_feedback: dict[str, int] = field(default_factory=dict)

    def blocks(self, song: dict) -> bool:
        return any(artist in self.blocked_artists for artist in song.get("artists", []))

    def dislikes(self, song: dict) -> bool:
        return self.song_feedback.get(str(song.get("id")), 0) < 0

    def adjustment(self, song: dict) -> float:
        score = max(0, self.song_feedback.get(str(song.get("id")), 0)) * 0.5
        for artist in song.get("artists", []):
            if artist in self.preferred_artists:
                score += 0.75
            score += self.artist_feedback.get(artist, 0) * 0.2
        return score

    def reason(self, song: dict) -> str | None:
        for artist in song.get("artists", []):
            if artist in self.preferred_artists:
                return f"你特别偏爱 {artist}"
        for artist in song.get("artists", []):
            if self.artist_feedback.get(artist, 0) > 0:
                return f"根据你的喜欢反馈，推荐 {artist}"
        return None


def load_preferences() -> UserPreferences:
    if not PREFERENCES_FILE.exists():
        return UserPreferences()
    try:
        data = json.loads(PREFERENCES_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return UserPreferences()
    try:
        return UserPreferences(
            blocked_artists=set(data.get("blocked_artists", [])),
            preferred_artists=set(data.get("preferred_artists", [])),
            song_feedback={str(key): int(value) for key, value in data.get("song_feedback", {}).items()},
            artist_feedback={str(key): int(value) for key, value in data.get("artist_feedback", {}).items()},
        )
    except (TypeError, ValueError):
        return UserPreferences()


def save_preferences(preferences: UserPreferences) -> None:
    data = {
        "blocked_artists": sorted(preferences.blocked_artists),
        "preferred_artists": sorted(preferences.preferred_artists),
        "song_feedback": preferences.song_feedback,
        "artist_feedback": preferences.artist_feedback,
    }
    temp = PREFERENCES_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(PREFERENCES_FILE)


def _last_push_song(index: int) -> dict:
    if not STATE_FILE.exists():
        raise ValueError("还没有可反馈的推送记录，请先运行一次推荐。")
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("上一次推送记录无法读取。") from exc
    songs = state.get("songs", [])
    if index < 1 or index > len(songs):
        raise ValueError(f"歌曲序号应在 1 到 {len(songs)} 之间。")
    return songs[index - 1]


def _append_event(event: dict) -> None:
    event["created_at"] = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    with FEEDBACK_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def record_song_feedback(kind: str, index: int) -> dict:
    if kind not in {"like", "dislike"}:
        raise ValueError("反馈类型必须是 like 或 dislike。")
    song = _last_push_song(index)
    preferences = load_preferences()
    value = 1 if kind == "like" else -1
    song_id = str(song.get("id"))
    previous = preferences.song_feedback.get(song_id, 0)
    preferences.song_feedback[song_id] = value
    delta = value - previous
    for artist in song.get("artists", []):
        current = preferences.artist_feedback.get(artist, 0)
        preferences.artist_feedback[artist] = max(-5, min(5, current + delta))
    save_preferences(preferences)
    _append_event({"type": "song", "action": kind, "song": song})
    return song


def set_artist_preference(action: str, artist: str) -> None:
    artist = artist.strip()
    if not artist:
        raise ValueError("艺人名称不能为空。")
    if action not in {"prefer", "block", "neutral"}:
        raise ValueError("艺人操作必须是 prefer、block 或 neutral。")

    preferences = load_preferences()
    preferences.blocked_artists.discard(artist)
    preferences.preferred_artists.discard(artist)
    if action == "prefer":
        preferences.preferred_artists.add(artist)
    elif action == "block":
        preferences.blocked_artists.add(artist)
    else:
        preferences.artist_feedback.pop(artist, None)
    save_preferences(preferences)
    _append_event({"type": "artist", "action": action, "artist": artist})
