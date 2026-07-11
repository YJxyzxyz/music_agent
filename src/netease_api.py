"""网易云 API 直连客户端（纯 Python，无需 Node 服务端）。

所有请求走 music.163.com 的 weapi 接口，使用 netease_crypto.weapi 加密。
登录态通过 Cookie 头传递（cookie 字符串保存在 data/cookies.json）。

已验证可用的接口（2026-07 实测）：
  w/nuser/account/get          登录态
  personalized/playlist        推荐歌单（登录后按口味）
  v3/discovery/recommend/songs 每日推荐歌曲
  song/like/get                我喜欢的音乐 id 列表
  v3/playlist/detail           歌单详情（含 tracks）
  v3/song/detail               歌曲详情（含艺人）
注：原 login/qr/* 与 user/record 接口已被网易云下线，故采用 cookie 登录 + likelist 画像。
"""
import re
import requests
from config import settings
from netease_crypto import weapi

BASE = "https://music.163.com/weapi"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
    "Referer": "https://music.163.com/",
    "Content-Type": "application/x-www-form-urlencoded",
}


def _csrf(cookie: str) -> str:
    m = re.search(r"__csrf=([^;]+)", cookie or "")
    return m.group(1) if m else ""


class NeteaseAPI:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(_HEADERS)

    # ---------- 底层请求 ----------
    def request(self, path: str, payload: dict | None = None, with_cookie: bool = True):
        payload = dict(payload or {})
        cookie = settings.cookies
        if with_cookie and cookie:
            csrf = _csrf(cookie)
            if csrf:
                payload.setdefault("csrf_token", csrf)
            self.session.headers["Cookie"] = cookie

        url = f"{BASE}/{path.lstrip('/')}"
        data = weapi(payload)
        resp = self.session.post(url, data=data, timeout=20)
        resp.raise_for_status()
        return resp.json()

    # ---------- 登录态 ----------
    def login_status(self) -> dict:
        return self.request("w/nuser/account/get", {}, with_cookie=True)

    def user_id(self) -> str:
        st = self.login_status()
        # profile 在返回顶层
        return str(st.get("profile", {}).get("userId", ""))

    # ---------- 推荐 / 画像 ----------
    def recommend_playlists(self, limit: int = 30) -> list:
        """推荐歌单（登录后按口味）。"""
        d = self.request("personalized/playlist", {"limit": limit})
        return d.get("result") or []

    def recommend_songs(self, limit: int = 30) -> list:
        """每日推荐歌曲（已个性化）。"""
        d = self.request("v3/discovery/recommend/songs", {"limit": limit, "total": True})
        return d.get("data", {}).get("dailySongs") or []

    def likelist(self, uid: str, cap: int = 300) -> list:
        """我喜欢的音乐 id 列表（取最近 cap 个用于画像）。"""
        d = self.request("song/like/get", {"uid": uid})
        ids = d.get("ids") or []
        return ids[:cap]

    def playlist_detail(self, pid: str | int, n: int = 1000) -> dict:
        d = self.request("v3/playlist/detail", {"id": pid, "n": n})
        return d.get("playlist") or {}

    def song_detail(self, ids: list) -> list:
        c = "[" + ",".join(f'{{"id":{i}}}' for i in ids) + "]"
        d = self.request("v3/song/detail", {"c": c, "ids": str(ids)})
        return d.get("songs") or []
