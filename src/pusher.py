"""推送：通过 PushPlus 把『5 首歌 + 配文』推送到微信。"""
from html import escape

import requests
from config import DRAFT_PREVIEW_FILE, settings, LAST_PUSH_FILE
from http_utils import request_json


def _build_html(songs: list[dict], caption: str) -> str:
    items = []
    for i, s in enumerate(songs, 1):
        arts = escape("、".join(s["artists"]) or "未知艺人")
        name = escape(str(s.get("name", "未知")))
        album = escape(str(s.get("album", "")))
        reason = escape(str(s.get("reason", "")))
        explanation = escape(str(s.get("explanation", "")))
        items.append(
            f"<li><b>{i}. 《{name}》</b> — {arts}"
            f"<br><span style='color:#888;font-size:12px;'>"
            f"专辑：{album} · {reason}<br>{explanation}</span></li>"
        )
    song_html = "<ol>" + "".join(items) + "</ol>"
    safe_caption = escape(caption).replace("\n", "<br>")
    caption_html = f"<p style='line-height:1.6;'>{safe_caption}</p>"
    return f"<h3>🎵 今日为你精选</h3>{song_html}<hr>{caption_html}"


def write_draft_preview(songs: list[dict], caption: str):
    DRAFT_PREVIEW_FILE.write_text(_build_html(songs, caption), encoding="utf-8")
    return DRAFT_PREVIEW_FILE


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
    data = request_json(
        requests.Session(),
        "POST",
        "https://www.pushplus.plus/send",
        operation="PushPlus 推送",
        json=payload,
    )
    if data.get("code") != 200:
        raise RuntimeError(f"PushPlus 推送失败：{data}")
    return data
