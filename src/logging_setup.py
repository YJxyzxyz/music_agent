"""统一配置控制台与滚动文件日志。"""
import logging
from logging.handlers import RotatingFileHandler

from config import LOG_DIR


def setup_logging() -> None:
    root = logging.getLogger()
    if getattr(root, "_music_agent_configured", False):
        return

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    file_handler = RotatingFileHandler(
        LOG_DIR / "agent.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root.setLevel(logging.INFO)
    root.addHandler(console)
    root.addHandler(file_handler)
    root._music_agent_configured = True
