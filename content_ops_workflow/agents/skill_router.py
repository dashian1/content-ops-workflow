from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class SkillDef:
    id: str
    zh_name: str
    en_name: str
    triggers: tuple[str, ...]
    agents: tuple[str, ...]
    output: tuple[str, ...]
    description: str


SKILLS: tuple[SkillDef, ...] = (
    SkillDef(
        id="duanshipin-gouzi",
        zh_name="短视频钩子",
        en_name="Short Video Hook",
        triggers=("hook", "开头", "前三秒", "留存", "爆款", "脚本", "抖音"),
        agents=("viral_analysis", "script"),
        output=("hook", "opening", "retention_angle"),
        description="生成短视频开头、前三秒停留和留存钩子。",
    ),
    SkillDef(
        id="shipin-tishi",
        zh_name="视频提示词",
        en_name="Video Prompt Structuring",
        triggers=("视频", "分镜", "画面", "镜头", "动作", "状态"),
        agents=("video_understanding", "script", "loop"),
        output=("shot_prompt", "visual_direction"),
        description="把脚本、画面、人物状态结构化成视频生成提示。",
    ),
    SkillDef(
        id="jingtou-duijiao",
        zh_name="镜头对焦",
        en_name="Camera And Focus Direction",
        triggers=("镜头", "景别", "运镜", "对焦", "分镜", "画面"),
        agents=("video_understanding", "script", "loop"),
        output=("camera", "shot_table"),
        description="生成镜头语言、对焦、景别和运镜说明。",
    ),
    SkillDef(
        id="biaoqing-yanyi",
        zh_name="表情演绎",
        en_name="Acting And Micro-expression",
        triggers=("表情", "动作", "神情", "情绪", "口播", "人物"),
        agents=("script", "loop"),
        output=("acting", "expression", "performance"),
        description="生成真人口播的表情、动作、神情和情绪曲线。",
    ),
    SkillDef(
        id="seedance-ugc-daoyan",
        zh_name="Seedance UGC 导演",
        en_name="Seedance UGC Director",
        triggers=("ugc", "广告", "产品", "带货", "种草", "脚本"),
        agents=("product_strategy", "script"),
        output=("ugc_script", "ad_variant"),
        description="生成产品 UGC 广告脚本、达人表达和带货变体。",
    ),
)


def route_skills(intent: dict[str, Any], agent: str = "") -> list[dict[str, Any]]:
    text = " ".join(str(v) for v in intent.values() if not isinstance(v, (dict, list)))
    for value in intent.values():
        if isinstance(value, list):
            text += " " + " ".join(str(x) for x in value)
        if isinstance(value, dict):
            text += " " + " ".join(str(x) for x in value.values())
    text = text.lower()
    hits: list[dict[str, Any]] = []
    for skill in SKILLS:
        score = 0
        reasons = []
        if agent and agent in skill.agents:
            score += 2
            reasons.append(f"适用于 {agent} agent")
        for trigger in skill.triggers:
            if trigger.lower() in text:
                score += 1
                reasons.append(f"命中关键词：{trigger}")
        if score:
            item = asdict(skill)
            item.update({"confidence": min(0.98, 0.45 + score * 0.11), "reason": "；".join(reasons[:4])})
            hits.append(item)
    hits.sort(key=lambda item: item["confidence"], reverse=True)
    return hits[:5]
