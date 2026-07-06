from __future__ import annotations

import json
from typing import Any

from content_ops_workflow import llm
from content_ops_workflow.engines.context_engine import TaskContext, to_prompt_block


def build_plan(case_summary: str, context: TaskContext, goal: str = "") -> dict[str, Any]:
    prompt = f"""你是内容运营 Planning Engine。你的职责不是写脚本，而是决定今天应该怎么做。

请输出严格 JSON，不要 Markdown：
{{
  "strategy": "",
  "hook": "",
  "duration": 22,
  "product_insert": "",
  "emotion": "",
  "cta": "",
  "why": "",
  "execution_constraints": []
}}

【目标】
{goal or "基于爆款结构生成可执行内容方案"}

【素材摘要】
{case_summary}

{to_prompt_block(context)}
"""
    raw = llm.call_text("你是内容运营规划引擎，只输出 JSON。", prompt, max_tokens=1800)
    try:
        return json.loads(_clean_json(raw))
    except json.JSONDecodeError:
        return {"strategy": "", "hook": "", "duration": 0, "product_insert": "", "emotion": "", "cta": "", "why": raw, "execution_constraints": []}


def _clean_json(text: str) -> str:
    clean = text.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    start = clean.find("{")
    if start > 0:
        clean = clean[start:]
    end = clean.rfind("}")
    if end >= 0:
        clean = clean[: end + 1]
    return clean

