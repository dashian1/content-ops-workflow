from __future__ import annotations

import json
import os
from dataclasses import dataclass


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNTIME_CONFIG_PATH = os.path.join(ROOT, "runtime_config.json")


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
    notes_cli: str


def load_runtime_config() -> dict:
    try:
        with open(RUNTIME_CONFIG_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_runtime_config(data: dict) -> None:
    allowed = {
        "api_url",
        "api_key",
        "api_model",
        "obsidian_vault_dir",
        "obsidian_vault_name",
        "obsidian_rest_url",
        "obsidian_api_key",
        "product_kb_dir",
        "external_loops_dir",
        "feishu_cli",
        "feishu_base_token",
        "feishu_analysis_table",
        "feishu_script_table",
        "feishu_loop_table",
        "feishu_review_table",
        "notes_cli",
    }
    existing = load_runtime_config()
    clean = {key: str(value).strip() for key, value in data.items() if key in allowed}
    for secret_key in ("api_key", "obsidian_api_key"):
        if clean.get(secret_key) == "********" and existing.get(secret_key):
            clean[secret_key] = existing[secret_key]
    with open(RUNTIME_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)


def cfg(data: dict, env: str, key: str, default: str = "") -> str:
    return os.environ.get(env) or str(data.get(key) or data.get(env) or default)


def load_settings() -> Settings:
    data = load_runtime_config()
    return Settings(
        root=ROOT,
        upload_dir=os.path.join(ROOT, "uploads"),
        output_dir=os.path.join(ROOT, "outputs"),
        obsidian_dir=cfg(data, "OBSIDIAN_VAULT_DIR", "obsidian_vault_dir", os.path.join(ROOT, "obsidian_vault")),
        obsidian_vault_name=cfg(data, "OBSIDIAN_VAULT_NAME", "obsidian_vault_name", "内容运营workflow"),
        obsidian_rest_url=cfg(data, "OBSIDIAN_REST_URL", "obsidian_rest_url", "https://127.0.0.1:27124"),
        obsidian_api_key=cfg(data, "OBSIDIAN_API_KEY", "obsidian_api_key", ""),
        obsidian_open_after_write=os.environ.get("OBSIDIAN_OPEN_AFTER_WRITE", "").strip() == "1",
        product_kb_dir=cfg(data, "PRODUCT_KB_DIR", "product_kb_dir", os.path.join(os.path.dirname(ROOT), "大师安工具矩阵", "knowledge")),
        api_url=cfg(data, "API_URL", "api_url", "https://api.deepseek.com/v1"),
        api_key=os.environ.get("API_KEY") or os.environ.get("DS_KEY") or str(data.get("api_key") or ""),
        model=cfg(data, "API_MODEL", "api_model", "deepseek-chat"),
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5015")),
        app_username=os.environ.get("APP_USERNAME", "admin"),
        app_password=os.environ.get("APP_PASSWORD", ""),
        max_upload_mb=int(os.environ.get("MAX_UPLOAD_MB", "800")),
        external_loops_dir=cfg(data, "EXTERNAL_LOOPS_DIR", "external_loops_dir", os.path.join(ROOT, "loops")),
        feishu_cli=cfg(data, "FEISHU_CLI", "feishu_cli", ""),
        feishu_base_token=cfg(data, "FEISHU_BASE_TOKEN", "feishu_base_token", ""),
        feishu_analysis_table=cfg(data, "FEISHU_ANALYSIS_TABLE", "feishu_analysis_table", ""),
        feishu_script_table=cfg(data, "FEISHU_SCRIPT_TABLE", "feishu_script_table", ""),
        feishu_loop_table=cfg(data, "FEISHU_LOOP_TABLE", "feishu_loop_table", ""),
        feishu_review_table=cfg(data, "FEISHU_REVIEW_TABLE", "feishu_review_table", ""),
        notes_cli=cfg(data, "NOTES_CLI", "notes_cli", ""),
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
        os.path.join(SETTINGS.obsidian_dir, "09_视频理解区"),
        os.path.join(SETTINGS.obsidian_dir, "10_产品匹配"),
        os.path.join(SETTINGS.obsidian_dir, "11_数据复盘"),
    ]:
        os.makedirs(path, exist_ok=True)
