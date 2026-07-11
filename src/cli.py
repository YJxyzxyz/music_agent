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

from config import check_required
from netease_api import NeteaseAPI
from login import setup_cookie, ensure_login
from orchestrator import run_once
from scheduler import start


def main():
    parser = argparse.ArgumentParser(description="网易云音乐推荐 Agent")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("login", help="扫码登录并保存 cookie")
    p_run = sub.add_parser("run", help="立即执行一次推荐+推送")
    p_run.add_argument("--force", action="store_true", help="忽略当天已推送")
    sub.add_parser("serve", help="每天定时自动运行")

    args = parser.parse_args()

    if args.cmd == "login":
        api = NeteaseAPI()
        setup_cookie(api)
        return

    if args.cmd == "run":
        missing = check_required()
        if missing:
            print(f"缺少配置：{', '.join(missing)}，请在 .env 中填写后重试。")
            sys.exit(1)
        api = NeteaseAPI()
        ensure_login(api)
        run_once(force=getattr(args, "force", False))
        return

    if args.cmd == "serve":
        missing = check_required()
        if missing:
            print(f"缺少配置：{', '.join(missing)}，请在 .env 中填写后重试。")
            sys.exit(1)
        api = NeteaseAPI()
        ensure_login(api)
        start()


if __name__ == "__main__":
    main()
