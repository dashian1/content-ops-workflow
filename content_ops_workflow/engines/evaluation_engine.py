from __future__ import annotations

from typing import Any


WEIGHTS = {
    "views": 0.20,
    "completion_rate": 0.30,
    "like_rate": 0.20,
    "comment_rate": 0.10,
    "save_rate": 0.10,
    "conversion_rate": 0.10,
}


def evaluate(data: dict[str, Any]) -> dict[str, Any]:
    views = _num(data.get("views"))
    likes = _num(data.get("likes"))
    comments = _num(data.get("comments"))
    saves = _num(data.get("saves"))
    conversion = _num(data.get("conversion")) + _num(data.get("sales"))
    completion = _rate(data.get("completion_rate"))

    like_rate = likes / views if views else 0.0
    comment_rate = comments / views if views else 0.0
    save_rate = saves / views if views else 0.0
    conversion_rate = conversion / views if views else 0.0

    subs = {
        "views": _cap(views / 10000),
        "completion_rate": completion,
        "like_rate": _cap(like_rate / 0.05),
        "comment_rate": _cap(comment_rate / 0.01),
        "save_rate": _cap(save_rate / 0.02),
        "conversion_rate": _cap(conversion_rate / 0.002),
    }
    score = round(sum(subs[key] * WEIGHTS[key] for key in WEIGHTS) * 100, 1)
    return {
        "score": score,
        "subscores": {key: round(value * 100, 1) for key, value in subs.items()},
        "weights": WEIGHTS,
        "signals": {
            "views": views,
            "completion_rate": completion,
            "like_rate": like_rate,
            "comment_rate": comment_rate,
            "save_rate": save_rate,
            "conversion_rate": conversion_rate,
            "sales": _num(data.get("sales")),
        },
    }


def _num(value: Any) -> float:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return 0.0
    if text.endswith("万"):
        return float(text[:-1] or 0) * 10000
    try:
        return float(text)
    except ValueError:
        return 0.0


def _rate(value: Any) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        if text.endswith("%"):
            return float(text[:-1]) / 100
        number = float(text)
        return number / 100 if number > 1 else number
    except ValueError:
        return 0.0


def _cap(value: float) -> float:
    return max(0.0, min(1.0, value))
