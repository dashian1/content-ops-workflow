from __future__ import annotations

import os
from dataclasses import dataclass


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass(frozen=True)
class Settings:
    root: str
    upload_dir: str
    output_dir: str
    obsidian_dir: str
    product_kb_dir: str
    api_url: str
    api_key: str
    model: str
    host: str
    port: int


def load_settings() -> Settings:
    return Settings(
        root=ROOT,
        upload_dir=os.path.join(ROOT, "uploads"),
        output_dir=os.path.join(ROOT, "outputs"),
        obsidian_dir=os.environ.get("OBSIDIAN_VAULT_DIR", os.path.join(ROOT, "obsidian_vault")),
        product_kb_dir=os.environ.get(
            "PRODUCT_KB_DIR",
            os.path.join(os.path.dirname(ROOT), "灵鹤芝谷工具矩阵", "knowledge"),
        ),
        api_url=os.environ.get("API_URL", "https://ai-api.local.gdzskj.ltd/v1/chat/completions"),
        api_key=os.environ.get("API_KEY") or os.environ.get("DS_KEY", ""),
        model=os.environ.get("API_MODEL", "deepseek-v4-pro"),
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5015")),
    )


SETTINGS = load_settings()


def ensure_dirs() -> None:
    for path in [
        SETTINGS.upload_dir,
        SETTINGS.output_dir,
        SETTINGS.obsidian_dir,
        os.path.join(SETTINGS.obsidian_dir, "01_爆款分析"),
        os.path.join(SETTINGS.obsidian_dir, "02_话题库"),
        os.path.join(SETTINGS.obsidian_dir, "03_选题库"),
        os.path.join(SETTINGS.obsidian_dir, "04_结构库"),
        os.path.join(SETTINGS.obsidian_dir, "05_金句库"),
        os.path.join(SETTINGS.obsidian_dir, "06_剪辑风格库"),
        os.path.join(SETTINGS.obsidian_dir, "07_脚本产出"),
        os.path.join(SETTINGS.obsidian_dir, "08_loop生产"),
    ]:
        os.makedirs(path, exist_ok=True)

