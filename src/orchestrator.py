"""编排推荐草稿、确认推送和每日自动运行流程。"""
import datetime as dt
import json
import logging
import uuid

from caption import generate_caption
from config import STATE_FILE, settings
from drafts import load_draft, save_draft
from history import append_history, recent_song_ids, write_journal
from login import ensure_login
from netease_api import NeteaseAPI
from preferences import adaptive_explore_strategy, load_preferences
from profile import build_profile
from pusher import push, write_draft_preview
from scenes import normalize_scene
from selector import select_songs

logger = logging.getLogger(__name__)


def _today() -> str:
    return dt.date.today().isoformat()


def _now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def _already_pushed_today() -> bool:
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            return state.get("last_push_date") == _today()
        except (OSError, ValueError):
            logger.warning("无法读取 state.json，将继续本次运行")
    return False


def _save_state(draft: dict) -> None:
    STATE_FILE.write_text(
        json.dumps(
            {
                "last_push_date": _today(),
                "draft_id": draft["id"],
                "songs": draft["songs"],
                "caption": draft["caption"],
                "scene": draft["scene"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _log_songs(songs: list[dict]) -> None:
    for index, song in enumerate(songs, 1):
        logger.info(
            "%s. 《%s》- %s [%s | %.2f]",
            index,
            song["name"],
            "、".join(song["artists"]),
            song.get("reason", ""),
            song.get("score", 0.0),
        )


def create_draft(scene: str | None = None) -> dict:
    """生成推荐和配文草稿，不发送 PushPlus。"""
    scene = normalize_scene(scene or settings.scene_mode)
    api = NeteaseAPI()
    logger.info("[草稿] 确保登录态")
    ensure_login(api)

    logger.info("[草稿] 读取听歌画像")
    uid = api.user_id()
    profile = build_profile(api, uid)
    logger.info("[画像] %s", profile.describe())

    excluded = recent_song_ids(settings.recent_dedup_days)
    preferences = load_preferences()
    strategy = adaptive_explore_strategy(settings.explore_ratio)
    logger.info(
        "[草稿] 挑选歌曲：历史排除 %s 首，探索比例 %.0f%%（基础 %.0f%%）",
        len(excluded),
        strategy["effective_ratio"] * 100,
        strategy["base_ratio"] * 100,
    )
    songs = select_songs(
        api,
        profile,
        exclude_ids=excluded,
        preferences=preferences,
        explore_ratio=strategy["effective_ratio"],
    )
    if not songs:
        raise RuntimeError("未能获取到任何候选歌曲，请检查网络与登录态。")
    _log_songs(songs)

    logger.info("[草稿] 生成朋友圈配文")
    caption = generate_caption(songs, scene=scene)
    created_at = _now()
    draft = {
        "id": uuid.uuid4().hex[:12],
        "status": "draft",
        "revision": 1,
        "created_at": created_at,
        "updated_at": created_at,
        "scene": scene,
        "strategy": strategy,
        "songs": songs,
        "caption": caption,
    }
    save_draft(draft)
    preview_path = write_draft_preview(songs, caption)
    logger.info("[草稿] 已保存 %s，预览：%s", draft["id"], preview_path)
    return draft


def regenerate_draft(scene: str | None = None) -> dict:
    """保留当前草稿歌曲，只重新生成配文。"""
    draft = load_draft()
    if draft.get("status") == "pushed":
        raise ValueError("该草稿已经推送，请先运行 draft 生成新草稿。")
    draft["scene"] = normalize_scene(scene or draft.get("scene"))
    draft["caption"] = generate_caption(draft["songs"], scene=draft["scene"])
    draft["revision"] = int(draft.get("revision", 1)) + 1
    draft["updated_at"] = _now()
    save_draft(draft)
    write_draft_preview(draft["songs"], draft["caption"])
    logger.info("[草稿] 配文已重新生成，当前版本 %s", draft["revision"])
    return draft


def publish_draft(force: bool = False) -> dict:
    """推送当前草稿，并在成功后归档状态、历史和音乐日记。"""
    draft = load_draft()
    if draft.get("status") == "pushed" and not force:
        raise ValueError("该草稿已经推送；如需重复发送请使用 --force。")

    logger.info("[草稿] 推送 %s 到微信", draft["id"])
    push_result = push(draft["songs"], draft["caption"])
    draft["status"] = "pushed"
    draft["pushed_at"] = _now()
    draft["push_code"] = push_result.get("code")
    save_draft(draft)

    _save_state(draft)
    append_history(draft["songs"], draft["caption"], scene=draft["scene"])
    journal_path = write_journal(
        draft["songs"],
        draft["caption"],
        scene=draft["scene"],
    )
    logger.info("[%s] 完成推送；音乐日记：%s", _today(), journal_path)
    return {"draft": draft, "push": push_result, "journal": str(journal_path)}


def run_once(force: bool = False, scene: str | None = None) -> dict:
    """兼容原有一键流程：生成草稿后立即推送。"""
    if not force and _already_pushed_today():
        logger.info("[%s] 今日已推送，跳过（用 --force 强制重跑）", _today())
        return {"skipped": True}
    try:
        create_draft(scene=scene)
        return publish_draft()
    except Exception:
        logger.exception("[%s] 本次运行失败", _today())
        raise
