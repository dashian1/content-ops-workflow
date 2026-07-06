from __future__ import annotations

import os

from content_ops_workflow.config import SETTINGS
from content_ops_workflow.engines import memory_engine


def read_product_library(limit: int = 12000) -> str:
    if not os.path.isdir(SETTINGS.product_kb_dir):
        return f"产品库目录不存在: {SETTINGS.product_kb_dir}"
    chunks: list[str] = []
    for name in sorted(os.listdir(SETTINGS.product_kb_dir)):
        if not name.lower().endswith((".md", ".txt")):
            continue
        path = os.path.join(SETTINGS.product_kb_dir, name)
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read().strip()
        except OSError:
            continue
        if text:
            chunks.append(f"# {name}\n\n{text}")
    return "\n\n---\n\n".join(chunks)[:limit]


def read_template_library(limit: int = 8000) -> str:
    path = os.path.join(SETTINGS.root, "templates_library", "viral_templates.md")
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()[:limit]
    except OSError:
        return "未找到爆款结构模板库。"


def read_brand_and_platform(limit: int = 6000) -> str:
    knowledge = memory_engine.read_text_files("knowledge", limit)
    return knowledge or "暂无品牌规范 / 平台规则沉淀。"

