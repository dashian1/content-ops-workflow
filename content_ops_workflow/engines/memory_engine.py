from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

from content_ops_workflow.config import SETTINGS


@dataclass(frozen=True)
class MemoryPaths:
    root: str
    knowledge: str
    case: str
    pattern: str
    strategy: str
    event: str


def paths() -> MemoryPaths:
    memory_root = os.path.join(SETTINGS.root, "memory")
    return MemoryPaths(
        root=memory_root,
        knowledge=os.path.join(memory_root, "knowledge"),
        case=os.path.join(memory_root, "case"),
        pattern=os.path.join(memory_root, "pattern"),
        strategy=os.path.join(memory_root, "strategy"),
        event=os.path.join(memory_root, "event"),
    )


def ensure_memory_dirs() -> None:
    for path in paths().__dict__.values():
        os.makedirs(path, exist_ok=True)


def append_jsonl(name: str, payload: dict[str, Any]) -> str:
    ensure_memory_dirs()
    target = os.path.join(paths().event, f"{name}.jsonl")
    with open(target, "a", encoding="utf-8") as f:
        f.write(json.dumps({**payload, "created": time.strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False) + "\n")
    return target


def write_json(area: str, filename: str, payload: dict[str, Any]) -> str:
    ensure_memory_dirs()
    base = getattr(paths(), area)
    target = os.path.join(base, filename)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return target


def read_text_files(area: str, limit: int = 8000) -> str:
    ensure_memory_dirs()
    base = getattr(paths(), area)
    chunks: list[str] = []
    for root, _dirs, files in os.walk(base):
        for name in sorted(files):
            if not name.lower().endswith((".md", ".txt", ".json", ".jsonl")):
                continue
            path = os.path.join(root, name)
            try:
                with open(path, encoding="utf-8") as f:
                    text = f.read().strip()
            except OSError:
                continue
            if text:
                rel = os.path.relpath(path, base)
                chunks.append(f"# {rel}\n\n{text}")
            if sum(len(chunk) for chunk in chunks) >= limit:
                return "\n\n---\n\n".join(chunks)[:limit]
    return "\n\n---\n\n".join(chunks)[:limit]


def load_patterns(limit: int = 6000) -> str:
    return read_text_files("pattern", limit)


def load_strategies(limit: int = 6000) -> str:
    return read_text_files("strategy", limit)
