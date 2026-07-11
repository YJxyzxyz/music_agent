"""推荐场景名称与配文语气。"""

SCENES = {
    "default": ("日常", "自然、温暖，适合当天随手分享"),
    "morning": ("清晨", "清爽、轻盈，有开始新一天的感觉"),
    "commute": ("通勤", "有流动感，适合在路上听，但不要刻意鸡血"),
    "focus": ("专注", "克制、安静，适合工作或学习时陪伴"),
    "night": ("夜晚", "松弛、细腻，带一点夜色中的私人感受"),
    "weekend": ("周末", "自在、舒展，有从日常节奏里暂时抽身的感觉"),
}


def normalize_scene(scene: str | None) -> str:
    return scene if scene in SCENES else "default"
