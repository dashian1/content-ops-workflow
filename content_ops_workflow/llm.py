from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests

from content_ops_workflow.config import SETTINGS


def normalize_api_url(api_url: str) -> str:
    parsed = urlsplit(api_url.rstrip("/"))
    if not parsed.scheme or not parsed.netloc:
        return api_url.rstrip("/")
    path = parsed.path.rstrip("/")
    lower = path.lower()
    if lower.endswith("/chat/completions"):
        normalized = path
    elif lower.endswith("/v1"):
        normalized = f"{path}/chat/completions"
    else:
        normalized = "/v1/chat/completions"
    return urlunsplit((parsed.scheme, parsed.netloc, normalized, parsed.query, parsed.fragment))


def is_configured() -> bool:
    key = (SETTINGS.api_key or "").strip().lower()
    return bool(key) and not key.startswith("sk-your-")


def call_text(system: str, user: str, max_tokens: int = 4000) -> str:
    if not is_configured():
        return "API key not configured"
    body: dict[str, Any] = {
        "model": SETTINGS.model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
    }
    try:
        response = requests.post(
            normalize_api_url(SETTINGS.api_url),
            headers={"Authorization": f"Bearer {SETTINGS.api_key}", "Content-Type": "application/json"},
            json=body,
            timeout=180,
        )
    except requests.RequestException as exc:
        return f"API request failed: {exc}"
    if response.status_code != 200:
        return f"API Error {response.status_code}: {response.text[:500]}"
    data = response.json()
    return data["choices"][0]["message"].get("content") or "[empty response]"

