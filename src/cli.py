"""命令行入口：
  python -m src.cli login    # 首次扫码登录
  python -m src.cli run      # 立即跑一次（--force 强制重推）
  python -m src.cli serve    # 每天定时自动运行
"""
import argparse
import os
import sys

# 兼容两种运行方式：`python -m src.cli` 与 `python src/cli.py`。
# 把 src 目录插到搜索路径最前面，确保本地同级模块（config 等）优先于同名第三方包。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DRAFT_PREVIEW_FILE, check_required
from netease_api import NeteaseAPI
from login import setup_cookie
from drafts import load_draft
from orchestrator import create_draft, publish_draft, regenerate_draft, run_once
from scheduler import start
from logging_setup import setup_logging
from preferences import load_preferences, record_song_feedback, set_artist_preference
from scenes import SCENES


def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="网易云音乐推荐 Agent")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("login", help="验证并保存网易云 Cookie")
    p_run = sub.add_parser("run", help="立即执行一次推荐+推送")
    p_run.add_argument("--force", action="store_true", help="忽略当天已推送")
    p_run.add_argument("--scene", choices=SCENES, help="本次配文场景，覆盖 .env 配置")
    p_draft = sub.add_parser("draft", help="生成推荐草稿但不推送")
    p_draft.add_argument("--scene", choices=SCENES, help="本次配文场景")
    p_regenerate = sub.add_parser("regenerate", help="保留草稿歌曲并重新生成配文")
    p_regenerate.add_argument("--scene", choices=SCENES, help="同时切换配文场景")
    p_push_draft = sub.add_parser("push-draft", help="确认并推送当前草稿")
    p_push_draft.add_argument("--force", action="store_true", help="允许重复推送同一草稿")
    sub.add_parser("show-draft", help="查看当前草稿")
    sub.add_parser("serve", help="每天定时自动运行")
    p_feedback = sub.add_parser("feedback", help="评价上一次推送中的歌曲")
    p_feedback.add_argument("action", choices=["like", "dislike"])
    p_feedback.add_argument("index", type=int, help="上一次推送中的歌曲序号")
    p_artist = sub.add_parser("artist", help="设置长期艺人偏好")
    p_artist.add_argument("action", choices=["prefer", "block", "neutral"])
    p_artist.add_argument("name", help="艺人名称")
    sub.add_parser("preferences", help="查看当前长期偏好")

    args = parser.parse_args()

    def require(*, deepseek: bool, pushplus: bool) -> None:
        missing = check_required(
            require_deepseek=deepseek,
            require_pushplus=pushplus,
        )
        if missing:
            parser.error(f"缺少配置：{', '.join(missing)}，请在 .env 中填写后重试。")

    def print_draft(draft: dict) -> None:
        strategy = draft.get("strategy", {})
        print(
            f"草稿：{draft['id']} · 状态：{draft.get('status', 'draft')} · "
            f"配文版本：{draft.get('revision', 1)} · 场景：{draft.get('scene', 'default')}"
        )
        if strategy:
            print(
                f"探索比例：{strategy.get('effective_ratio', 0):.0%} "
                f"（基础 {strategy.get('base_ratio', 0):.0%}，"
                f"探索反馈 +{strategy.get('explore_likes', 0)}/-{strategy.get('explore_dislikes', 0)}）"
            )
        for index, song in enumerate(draft["songs"], 1):
            artists = "、".join(song.get("artists", [])) or "未知艺人"
            print(f"{index}. 《{song['name']}》- {artists} [{song.get('reason', '')}]")
            print(f"   {song.get('explanation', '')}；总分 {song.get('score', 0):.2f}")
        print(f"\n--- 配文 ---\n{draft['caption']}\n------------")
        print(f"HTML 预览：{DRAFT_PREVIEW_FILE}")

    if args.cmd == "draft":
        require(deepseek=True, pushplus=False)
        print_draft(create_draft(scene=args.scene))
        return

    if args.cmd == "regenerate":
        require(deepseek=True, pushplus=False)
        try:
            draft = regenerate_draft(scene=args.scene)
        except ValueError as exc:
            parser.error(str(exc))
        print_draft(draft)
        return

    if args.cmd == "push-draft":
        require(deepseek=False, pushplus=True)
        try:
            result = publish_draft(force=args.force)
        except ValueError as exc:
            parser.error(str(exc))
        print(f"[推送] 草稿 {result['draft']['id']} 已发送。")
        return

    if args.cmd == "show-draft":
        try:
            draft = load_draft()
        except ValueError as exc:
            parser.error(str(exc))
        print_draft(draft)
        return

    if args.cmd == "feedback":
        try:
            song = record_song_feedback(args.action, args.index)
        except ValueError as exc:
            parser.error(str(exc))
        artists = "、".join(song.get("artists", [])) or "未知艺人"
        label = "喜欢" if args.action == "like" else "不喜欢"
        print(f"[反馈] 已记录{label}：《{song.get('name', '未知')}》- {artists}")
        return

    if args.cmd == "artist":
        try:
            set_artist_preference(args.action, args.name)
        except ValueError as exc:
            parser.error(str(exc))
        labels = {"prefer": "偏爱", "block": "屏蔽", "neutral": "恢复中性"}
        print(f"[偏好] 已将 {args.name} 设置为{labels[args.action]}。")
        return

    if args.cmd == "preferences":
        preferences = load_preferences()
        preferred = "、".join(sorted(preferences.preferred_artists)) or "无"
        blocked = "、".join(sorted(preferences.blocked_artists)) or "无"
        print(f"偏爱艺人：{preferred}\n屏蔽艺人：{blocked}\n歌曲反馈：{len(preferences.song_feedback)} 条")
        return

    if args.cmd == "login":
        api = NeteaseAPI()
        setup_cookie(api)
        return

    if args.cmd == "run":
        require(deepseek=True, pushplus=True)
        run_once(force=getattr(args, "force", False), scene=args.scene)
        return

    if args.cmd == "serve":
        require(deepseek=True, pushplus=True)
        start()


if __name__ == "__main__":
    main()
