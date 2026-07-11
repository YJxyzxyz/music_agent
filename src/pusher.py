"""推送：通过 PushPlus 把『5 首歌 + 配文』推送到微信。"""
import requests
from config import settings, LAST_PUSH_FILE


def _build_html(songs: list[dict], caption: str) -> str:
    items = []
    for i, s in enumerate(songs, 1):
        arts = "、".join(s["artists"]) or "未知艺人"
        items.append(
            f"<li><b>{i}. 《{s['name']}》</b> — {arts}"
            f"<br><span style='color:#888;font-size:12px;'>"
            f"专辑：{s.get('album','')} · {s.get('reason','')}</span></li>"
        )
    song_html = "<ol>" + "".join(items) + "</ol>"
    caption_html = f"<p style='line-height:1.6;'>{caption.replace(chr(10), '<br>')}</p>"
    return f"<h3>🎵 今日为你精选</h3>{song_html}<hr>{caption_html}"


def push(songs: list[dict], caption: str) -> dict:
    if not settings.pushplus_token:
        raise ValueError("缺少 PUSHPLUS_TOKEN，请在 .env 中配置。")

    html = _build_html(songs, caption)
    LAST_PUSH_FILE.write_text(html, encoding="utf-8")

    payload = {
        "token": settings.pushplus_token,
        "title": "🎵 今日音乐推荐",
        "content": html,
        "template": "html",
    }
    resp = requests.post("https://www.pushplus.plus/send", json=payload, timeout=15)
    data = resp.json()
    if data.get("code") != 200:
        raise RuntimeError(f"PushPlus 推送失败：{data}")
    return data
