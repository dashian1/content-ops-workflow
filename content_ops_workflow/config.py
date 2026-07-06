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
    obsidian_vault_name: str
    obsidian_rest_url: str
    obsidian_api_key: str
    obsidian_open_after_write: bool
    product_kb_dir: str
    api_url: str
    api_key: str
    model: str
    host: str
    port: int
    app_username: str
    app_password: str
    max_upload_mb: int
    external_loops_dir: str
    feishu_cli: str
    feishu_base_token: str
    feishu_analysis_table: str
    feishu_script_table: str
    feishu_loop_table: str
    feishu_review_table: str


def load_settings() -> Settings:
    return Settings(
        root=ROOT,
        upload_dir=os.path.join(ROOT, "uploads"),
        output_dir=os.path.join(ROOT, "outputs"),
        obsidian_dir=os.environ.get("OBSIDIAN_VAULT_DIR", os.path.join(ROOT, "obsidian_vault")),
        obsidian_vault_name=os.environ.get("OBSIDIAN_VAULT_NAME", "内容运营workflow"),
        obsidian_rest_url=os.environ.get("OBSIDIAN_REST_URL", "https://127.0.0.1:27124"),
        obsidian_api_key=os.environ.get("OBSIDIAN_API_KEY", ""),
        obsidian_open_after_write=os.environ.get("OBSIDIAN_OPEN_AFTER_WRITE", "").strip() == "1",
        product_kb_dir=os.environ.get(
            "PRODUCT_KB_DIR",
            os.path.join(os.path.dirname(ROOT), "灵鹤芝谷工具矩阵", "knowledge"),
        ),
        api_url=os.environ.get("API_URL", "https://ai-api.local.gdzskj.ltd/v1/chat/completions"),
        api_key=os.environ.get("API_KEY") or os.environ.get("DS_KEY", ""),
        model=os.environ.get("API_MODEL", "deepseek-v4-pro"),
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5015")),
        app_username=os.environ.get("APP_USERNAME", "admin"),
        app_password=os.environ.get("APP_PASSWORD", ""),
        max_upload_mb=int(os.environ.get("MAX_UPLOAD_MB", "800")),
        external_loops_dir=os.environ.get("EXTERNAL_LOOPS_DIR", r"E:\灵鹤芝谷素材库\loops"),
        feishu_cli=os.environ.get("FEISHU_CLI", ""),
        feishu_base_token=os.environ.get("FEISHU_BASE_TOKEN", ""),
        feishu_analysis_table=os.environ.get("FEISHU_ANALYSIS_TABLE", ""),
        feishu_script_table=os.environ.get("FEISHU_SCRIPT_TABLE", ""),
        feishu_loop_table=os.environ.get("FEISHU_LOOP_TABLE", ""),
        feishu_review_table=os.environ.get("FEISHU_REVIEW_TABLE", ""),
    )


SETTINGS = load_settings()


def ensure_dirs() -> None:
    for path in [
        SETTINGS.upload_dir,
        SETTINGS.output_dir,
        SETTINGS.obsidian_dir,
        SETTINGS.external_loops_dir,
        os.path.join(SETTINGS.obsidian_dir, "01_爆款分析"),
        os.path.join(SETTINGS.obsidian_dir, "02_话题库"),
        os.path.join(SETTINGS.obsidian_dir, "03_选题库"),
        os.path.join(SETTINGS.obsidian_dir, "04_结构库"),
        os.path.join(SETTINGS.obsidian_dir, "05_金句库"),
        os.path.join(SETTINGS.obsidian_dir, "06_剪辑风格库"),
        os.path.join(SETTINGS.obsidian_dir, "07_脚本产出"),
        os.path.join(SETTINGS.obsidian_dir, "08_loop生产"),
        os.path.join(SETTINGS.obsidian_dir, "09_视频理解包"),
        os.path.join(SETTINGS.obsidian_dir, "10_产品匹配"),
        os.path.join(SETTINGS.obsidian_dir, "11_数据复盘"),
    ]:
        os.makedirs(path, exist_ok=True)
