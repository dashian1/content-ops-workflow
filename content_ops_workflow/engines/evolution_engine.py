from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any

from content_ops_workflow.engines import memory_engine


def update_from_feedback(feedback: dict[str, Any], evaluation: dict[str, Any], review: str = "") -> dict[str, Any]:
    pattern_name = _extract_pattern(feedback, review)
    scope = " / ".join(part for part in [feedback.get("platform", ""), feedback.get("style", ""), feedback.get("product", "")] if part)
    pattern_id = _pattern_id(pattern_name, scope)
    score = round(float(evaluation.get("score", 0)) / 100, 3)
    confidence = _confidence(feedback, evaluation)
    payload = {
        "id": pattern_id,
        "pattern": pattern_name,
        "score": score,
        "confidence": confidence,
        "trend": "unknown",
        "decay": "0.01/day",
        "scope": scope or "general",
        "last_verify": time.strftime("%Y-%m-%d"),
        "evidence": {
            "title": feedback.get("title", ""),
            "video_url": feedback.get("video_url", ""),
            "candidate_id": feedback.get("candidate_id", ""),
            "metrics": evaluation.get("signals", {}),
            "review_excerpt": review[:800],
        },
    }
    path = memory_engine.write_json("pattern", f"{pattern_id}.json", payload)
    event_path = memory_engine.append_jsonl("evolution", {"pattern": payload, "path": path})
    return {"pattern": payload, "path": path, "event_path": event_path}


def _extract_pattern(feedback: dict[str, Any], review: str) -> str:
    for key in ("template", "style", "candidate_id"):
        value = str(feedback.get(key) or "").strip()
        if value:
            return value
    match = re.search(r"模板[:：]\s*(.+)", review)
    if match:
        return match.group(1).strip()[:40]
    return "未命名 Pattern"


def _pattern_id(pattern: str, scope: str) -> str:
    digest = hashlib.sha1(f"{pattern}|{scope}".encode("utf-8")).hexdigest()[:10]
    return f"ptn_{digest}"


def _confidence(feedback: dict[str, Any], evaluation: dict[str, Any]) -> float:
    views = float(evaluation.get("signals", {}).get("views", 0) or 0)
    filled = sum(1 for key in ("likes", "comments", "saves", "completion_rate", "conversion", "sales") if str(feedback.get(key, "")).strip())
    base = min(0.8, views / 50000)
    return round(min(0.95, 0.25 + base + filled * 0.04), 3)
