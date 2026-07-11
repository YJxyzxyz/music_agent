"""全局配置：加载 .env，集中管理路径与参数。"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 项目根目录（src 的上一级）
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
NETEASE_SERVER_DIR = BASE_DIR / "netease_api_server"

# 运行时文件
COOKIES_FILE = DATA_DIR / "cookies.json"
QR_FILE = DATA_DIR / "qr_login.png"
STATE_FILE = DATA_DIR / "state.json"
LAST_PUSH_FILE = DATA_DIR / "last_push.html"
HISTORY_FILE = DATA_DIR / "history.jsonl"
PREFERENCES_FILE = DATA_DIR / "preferences.json"
FEEDBACK_FILE = DATA_DIR / "feedback.jsonl"
JOURNAL_DIR = DATA_DIR / "journal"
LOG_DIR = DATA_DIR / "logs"

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)

load_dotenv(BASE_DIR / ".env")


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(_env(name, str(default))))
    except ValueError:
        return default


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(_env(name, str(default))))
    except ValueError:
        return default


def _env_ratio(name: str, default: float) -> float:
    return min(1.0, _env_float(name, default))


class Settings:
    # DeepSeek
    deepseek_api_key: str = _env("DEEPSEEK_API_KEY")
    deepseek_base_url: str = _env("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    deepseek_model: str = _env("DEEPSEEK_MODEL", "deepseek-chat")

    # PushPlus
    pushplus_token: str = _env("PUSHPLUS_TOKEN")

    # 运行参数
    run_time: str = _env("RUN_TIME", "09:00")
    n_songs: int = _env_int("N_SONGS", 5, minimum=1)
    n_playlists: int = _env_int("N_PLAYLISTS", 3)
    recent_dedup_days: int = _env_int("RECENT_DEDUP_DAYS", 30)
    explore_ratio: float = _env_ratio("EXPLORE_RATIO", 0.2)
    scene_mode: str = _env("SCENE_MODE", "default")
    api_retry_attempts: int = _env_int("API_RETRY_ATTEMPTS", 3, minimum=1)
    api_retry_backoff: float = _env_float("API_RETRY_BACKOFF", 1.5)
    api_timeout: float = _env_float("API_TIMEOUT", 20.0, minimum=1.0)

    @property
    def cookies(self) -> str:
        """从 cookies.json 读取 cookie 字符串；不存在返回空。"""
        if COOKIES_FILE.exists():
            import json
            try:
                data = json.loads(COOKIES_FILE.read_text(encoding="utf-8"))
                return data.get("cookie", "")
            except Exception:
                return ""
        return ""

    def save_cookies(self, cookie: str) -> None:
        import json
        COOKIES_FILE.write_text(
            json.dumps({"cookie": cookie}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


settings = Settings()


def check_required() -> list[str]:
    """返回缺失的必填配置项名称。"""
    missing = []
    if not settings.deepseek_api_key:
        missing.append("DEEPSEEK_API_KEY")
    if not settings.pushplus_token:
        missing.append("PUSHPLUS_TOKEN")
    return missing
