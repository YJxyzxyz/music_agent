"""编排器：串联 登录 → 画像 → 选歌 → 配文 → 推送 的完整每日流程。"""
import json
import datetime
from config import settings, STATE_FILE
from netease_api import NeteaseAPI
from login import ensure_login
from profile import build_profile
from selector import select_songs
from caption import generate_caption
from pusher import push


def _today() -> str:
    return datetime.date.today().isoformat()


def _already_pushed_today() -> bool:
    if STATE_FILE.exists():
        try:
            st = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            return st.get("last_push_date") == _today()
        except Exception:
            return False
    return False


def _save_state(songs, caption):
    STATE_FILE.write_text(
        json.dumps(
            {
                "last_push_date": _today(),
                "songs": songs,
                "caption": caption,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def run_once(force: bool = False) -> dict:
    """执行一次完整流程。force=True 时忽略当天已推送。"""
    if not force and _already_pushed_today():
        print(f"[{_today()}] 今日已推送，跳过（用 --force 强制重跑）。")
        return {"skipped": True}

    api = NeteaseAPI()
    print("[流程] 确保登录态 …")
    ensure_login(api)

    print("[流程] 读取听歌画像 …")
    uid = api.user_id()
    profile = build_profile(api, uid)
    print(f"[画像] {profile.describe()}")

    print("[流程] 挑选歌曲 …")
    songs = select_songs(api, profile)
    if not songs:
        raise RuntimeError("未能获取到任何候选歌曲，请检查网络与登录态。")
    for i, s in enumerate(songs, 1):
        arts = "、".join(s["artists"])
        print(f"  {i}. 《{s['name']}》 - {arts}  [{s.get('reason','')}]")

    print("[流程] 生成朋友圈配文 …")
    caption = generate_caption(songs)
    print(f"--- 配文 ---\n{caption}\n-------------")

    print("[流程] 推送到微信 …")
    push(songs, caption)

    _save_state(songs, caption)
    print(f"[{_today()}] 完成推送 ✅")
    return {"songs": songs, "caption": caption}
