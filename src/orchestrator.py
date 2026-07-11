"""编排登录、画像、选歌、配文、推送和本地归档的每日流程。"""
import datetime
import json
import logging

from caption import generate_caption
from config import STATE_FILE, settings
from history import append_history, recent_song_ids, write_journal
from login import ensure_login
from netease_api import NeteaseAPI
from profile import build_profile
from pusher import push
from selector import select_songs

logger = logging.getLogger(__name__)


def _today() -> str:
    return datetime.date.today().isoformat()


def _already_pushed_today() -> bool:
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            return state.get("last_push_date") == _today()
        except (OSError, ValueError):
            logger.warning("无法读取 state.json，将继续本次运行")
    return False


def _save_state(songs: list[dict], caption: str) -> None:
    STATE_FILE.write_text(
        json.dumps(
            {"last_push_date": _today(), "songs": songs, "caption": caption},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def run_once(force: bool = False) -> dict:
    """执行一次完整流程；force=True 时忽略当天已经推送的状态。"""
    if not force and _already_pushed_today():
        logger.info("[%s] 今日已推送，跳过（用 --force 强制重跑）", _today())
        return {"skipped": True}

    try:
        api = NeteaseAPI()
        logger.info("[流程] 确保登录态")
        ensure_login(api)

        logger.info("[流程] 读取听歌画像")
        uid = api.user_id()
        profile = build_profile(api, uid)
        logger.info("[画像] %s", profile.describe())

        excluded = recent_song_ids(settings.recent_dedup_days)
        logger.info(
            "[流程] 挑选歌曲（避开近 %s 天的 %s 首历史推荐）",
            settings.recent_dedup_days,
            len(excluded),
        )
        songs = select_songs(api, profile, exclude_ids=excluded)
        if not songs:
            raise RuntimeError("未能获取到任何候选歌曲，请检查网络与登录态。")
        for index, song in enumerate(songs, 1):
            logger.info(
                "%s. 《%s》- %s [%s]",
                index,
                song["name"],
                "、".join(song["artists"]),
                song.get("reason", ""),
            )

        logger.info("[流程] 生成朋友圈配文")
        caption = generate_caption(songs)
        logger.info("[配文]\n%s", caption)

        logger.info("[流程] 推送到微信")
        push_result = push(songs, caption)

        # Push 成功后先记录状态，避免日记写入异常导致下一次重复推送。
        _save_state(songs, caption)
        append_history(songs, caption)
        journal_path = write_journal(songs, caption)
        logger.info("[%s] 完成推送；音乐日记：%s", _today(), journal_path)
        return {
            "songs": songs,
            "caption": caption,
            "push": push_result,
            "journal": str(journal_path),
        }
    except Exception:
        logger.exception("[%s] 本次运行失败", _today())
        raise
