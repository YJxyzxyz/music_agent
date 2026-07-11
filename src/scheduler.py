"""定时调度：每天在配置时间自动执行一次完整流程。"""
import time
import logging
import schedule
from config import settings
from orchestrator import run_once
from weekly_report import generate_weekly_report

logger = logging.getLogger(__name__)


def _scheduled_run():
    try:
        return run_once()
    except Exception:
        logger.exception("定时任务执行失败，调度器将继续运行")
        return None


def _scheduled_weekly_report():
    try:
        return generate_weekly_report(push_report=settings.weekly_report_push)
    except Exception:
        logger.exception("每周音乐报告生成失败，调度器将继续运行")
        return None


def configure_jobs() -> None:
    schedule.clear("daily-recommendation")
    schedule.clear("weekly-report")
    schedule.every().day.at(settings.run_time).do(_scheduled_run).tag("daily-recommendation")
    if settings.weekly_report_enabled:
        day = settings.weekly_report_day
        if day not in {
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        }:
            logger.warning("WEEKLY_REPORT_DAY=%s 无效，回退为 sunday", day)
            day = "sunday"
        getattr(schedule.every(), day).at(settings.weekly_report_time).do(
            _scheduled_weekly_report
        ).tag("weekly-report")


def start():
    print(f"[调度] 已启动，每天 {settings.run_time} 自动推送（Ctrl+C 退出）。")
    configure_jobs()
    if settings.weekly_report_enabled:
        print(
            f"[调度] 每周 {settings.weekly_report_day} {settings.weekly_report_time} "
            "生成音乐周报。"
        )

    # 启动时先跑一次，便于验证（之后的按时间表）
    try:
        run_once()
    except Exception:
        logger.exception("调度器首次运行出错")

    while True:
        schedule.run_pending()
        time.sleep(30)
