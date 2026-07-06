from __future__ import annotations

import json
from typing import Any

from content_ops_workflow import llm


EMPTY_INSIGHT = {
    "pain_points": [],
    "questions": [],
    "objections": [],
    "purchase_intents": [],
    "audience_labels": [],
    "viral_phrases": [],
    "risk_signals": [],
    "next_topics": [],
}


def analyze_comments(comments: str, title: str = "", platform: str = "") -> dict[str, Any]:
    text = (comments or "").strip()
    if not text:
        return {"ok": True, "source": "empty", **EMPTY_INSIGHT}
    prompt = f"""你是 Comment Insight Engine。请把评论区转成内容运营可用的结构化洞察。

只输出 JSON，不要 Markdown。

字段：
{{
  "pain_points": [],
  "questions": [],
  "objections": [],
  "purchase_intents": [],
  "audience_labels": [],
  "viral_phrases": [],
  "risk_signals": [],
  "next_topics": []
}}

要求：
1. 不要复述全部评论，只提炼对选题、脚本、产品承接、风险有用的洞察。
2. purchase_intents 只收录明确购买/询价/链接/适配问题。
3. risk_signals 收录质疑、反感、合规风险、信任问题。
4. next_topics 要能直接变成下一条视频选题。

标题: {title}
平台: {platform}

评论区：
{text[:6000]}
"""
    raw = llm.call_text("你是内容运营评论洞察引擎，只输出 JSON。", prompt, max_tokens=2200)
    try:
        data = json.loads(_clean_json(raw))
    except json.JSONDecodeError:
        data = {"raw": raw, **EMPTY_INSIGHT}
    data = _merge_rule_based(text, data)
    return {"ok": True, "source": "llm", **data}


def _clean_json(text: str) -> str:
    clean = text.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    start = clean.find("{")
    end = clean.rfind("}")
    if start >= 0 and end >= start:
        return clean[start : end + 1]
    return clean


def _merge_rule_based(text: str, data: dict[str, Any]) -> dict[str, Any]:
    lines = [line.strip() for line in text.replace("。", "\n").replace("？", "?\n").replace("！", "!\n").splitlines() if line.strip()]
    purchase_words = ("怎么买", "在哪里买", "链接", "多少钱", "价格", "下单", "想买", "适合我", "有用吗")
    risk_words = ("广告", "智商税", "假的", "不信", "太硬", "夸张", "割韭菜", "骗人")
    question_words = ("?", "？", "吗", "怎么", "哪里", "多少", "适合")
    purchase = [line for line in lines if any(word in line for word in purchase_words)]
    risks = [line for line in lines if any(word in line for word in risk_words)]
    questions = [line for line in lines if any(word in line for word in question_words)]
    data["purchase_intents"] = _dedupe([*(data.get("purchase_intents") or []), *purchase])[:8]
    data["risk_signals"] = _dedupe([*(data.get("risk_signals") or []), *risks])[:8]
    data["questions"] = _dedupe([*(data.get("questions") or []), *questions])[:8]
    if purchase:
        data["next_topics"] = _dedupe([*(data.get("next_topics") or []), *[f"集中回答：{item}" for item in purchase]])[:8]
    return data


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = str(item).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result
