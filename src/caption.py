"""配文：用 DeepSeek 根据挑选的 5 首歌生成适合发朋友圈的文案。"""
import json

from openai import OpenAI
from config import settings
from scenes import SCENES, normalize_scene


def _client() -> OpenAI:
    if not settings.deepseek_api_key:
        raise ValueError("缺少 DEEPSEEK_API_KEY，请在 .env 中配置。")
    return OpenAI(
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        max_retries=max(0, settings.api_retry_attempts - 1),
        timeout=settings.api_timeout,
    )


def _format_songs(songs: list[dict]) -> str:
    lines = []
    for i, s in enumerate(songs, 1):
        arts = "、".join(s["artists"]) or "未知艺人"
        lines.append(f"{i}. 《{s['name']}》 - {arts}（专辑：{s.get('album','')}）")
    return "\n".join(lines)


def generate_caption(songs: list[dict], scene: str = "default") -> str:
    client = _client()
    song_text = _format_songs(songs)
    scene = normalize_scene(scene)
    scene_label, scene_tone = SCENES[scene]

    system = (
        "你是一个懂音乐、文笔细腻的内容创作者，擅长写适合发微信朋友圈的短配文。"
        "风格温暖、有共鸣、带一点文艺感，适当使用 emoji，但不过度。"
        "不要写标题，直接给一段可复制粘贴的文案（3-6 句），"
        "可以巧妙融入今天推荐歌单的氛围，但不必逐首点评。"
        f"当前场景是『{scene_label}』，语气应当{scene_tone}。"
    )
    user = (
        f"今天根据你的听歌习惯，为你挑选了这些歌：\n{song_text}\n\n"
        "请据此写一段朋友圈配文，让人想点开听歌。只输出文案本身。"
    )

    resp = client.chat.completions.create(
        model=settings.deepseek_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.9,
        # V4 等思考型模型会先输出 reasoning_content 再写正式 content，
        # 上限太小会被思考过程吃光导致 content 为空，这里给足空间。
        max_tokens=2000,
    )
    content = (resp.choices[0].message.content or "").strip()
    if not content:
        # 思考型模型被截断（finish_reason=length）时 content 为空，给出明确提示
        raise ValueError(
            f"配文生成为空（模型 {settings.deepseek_model} 可能是思考型模型且被截断）。"
            "请增大 max_tokens 或改用 deepseek-chat。"
        )
    return content


def generate_weekly_mood_summary(summary_input: dict) -> str:
    """根据一周推荐与反馈生成克制的心情回顾。"""
    response = _client().chat.completions.create(
        model=settings.deepseek_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "你是一位克制、细腻的音乐编辑。请根据一周的音乐推荐和用户明确反馈，"
                    "写一段 4-6 句的中文心情回顾。可以描述这一周呈现出的情绪色彩、节奏和变化，"
                    "但必须说明这是从音乐偏好得到的轻量推断，不要诊断心理状态，不要编造现实事件，"
                    "不要逐条复述统计数字，不写标题。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(summary_input, ensure_ascii=False),
            },
        ],
        temperature=0.7,
        max_tokens=1200,
    )
    content = (response.choices[0].message.content or "").strip()
    if not content:
        raise ValueError("每周心情总结生成为空，请稍后重试。")
    return content
