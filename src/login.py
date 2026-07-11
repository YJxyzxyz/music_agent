"""登录：网易云已下线 web 扫码登录接口，这里采用 cookie 登录。

首次使用：在浏览器登录 music.163.com，打开开发者工具 → Network/Application，
复制 Cookie 中完整的 `MUSIC_U=...`（建议复制整段 Cookie 字符串更稳），
运行 `python -m src.cli login` 粘贴保存。之后自动复用，失效时重新粘贴。
"""
from config import settings


def _is_logged_in(api) -> bool:
    try:
        st = api.login_status()
        # w/nuser/account/get 的 profile 在顶层（不是 data.profile）
        return bool(st.get("code") == 200 and st.get("profile"))
    except Exception:
        return False


def setup_cookie(api=None) -> str:
    """交互式粘贴并保存 cookie。"""
    print("[登录] 请粘贴你的网易云 Cookie（可从浏览器开发者工具复制）：")
    cookie = input("Cookie > ").strip()
    if not cookie:
        raise ValueError("Cookie 为空。")
    # 先临时写入以便 login_status 校验
    settings.save_cookies(cookie)
    api = api or __import__("netease_api").NeteaseAPI()
    if _is_logged_in(api):
        print("[登录] Cookie 有效，已保存。")
        return cookie
    raise ValueError("该 Cookie 无效或已过期，请重新获取。")


def ensure_login(api=None) -> str:
    """确保已有有效登录态，否则交互式要求粘贴 cookie。返回 cookie。"""
    api = api or __import__("netease_api").NeteaseAPI()
    cookie = settings.cookies
    if cookie and _is_logged_in(api):
        print("[登录] 复用已保存的登录态。")
        return cookie
    print("[登录] 未登录或登录态失效，需要重新粘贴 Cookie。")
    return setup_cookie(api)
