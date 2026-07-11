"""推荐草稿的原子持久化与状态管理。"""
import json

from config import DRAFT_FILE


def save_draft(draft: dict) -> None:
    temp = DRAFT_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(DRAFT_FILE)


def load_draft() -> dict:
    if not DRAFT_FILE.exists():
        raise ValueError("当前没有推荐草稿，请先运行 draft。")
    try:
        draft = json.loads(DRAFT_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("推荐草稿无法读取，请重新运行 draft。") from exc
    if not draft.get("id") or not draft.get("songs") or not draft.get("caption"):
        raise ValueError("推荐草稿内容不完整，请重新运行 draft。")
    return draft
