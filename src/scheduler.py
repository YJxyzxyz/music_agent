"""定时调度：每天在配置时间自动执行一次完整流程。"""
import time
import schedule
from config import settings
from orchestrator import run_once


def start():
    print(f"[调度] 已启动，每天 {settings.run_time} 自动推送（Ctrl+C 退出）。")
    schedule.every().day.at(settings.run_time).do(run_once)

    # 启动时先跑一次，便于验证（之后的按时间表）
    try:
        run_once()
    except Exception as e:
        print(f"[调度] 首次运行出错：{e}")

    while True:
        schedule.run_pending()
        time.sleep(30)
