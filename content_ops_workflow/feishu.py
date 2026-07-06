from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from typing import Any

from content_ops_workflow.config import SETTINGS


TABLES = {
    "analysis": "爆款分析",
    "script": "脚本候选",
    "loop": "Loop生产",
    "review": "数据复盘",
}


def status() -> dict[str, Any]:
    cli = SETTINGS.feishu_cli or _find_cli()
    return {
        "ok": bool(cli),
        "mode": "cli" if cli else "package",
        "cli": cli,
        "base_token_configured": bool(SETTINGS.feishu_base_token),
        "tables": {
            "analysis": SETTINGS.feishu_analysis_table,
            "script": SETTINGS.feishu_script_table,
            "loop": SETTINGS.feishu_loop_table,
            "review": SETTINGS.feishu_review_table,
        },
        "message": "已找到飞书 CLI，可直接推送。" if cli else "未找到飞书 CLI，系统会先生成待上传包。",
    }


def push_payload(kind: str, payload: dict[str, Any], attachment_paths: list[str] | None = None) -> dict[str, Any]:
    attachment_paths = attachment_paths or []
    package_dir = os.path.join(SETTINGS.output_dir, "feishu_packages", time.strftime("%Y-%m-%d"))
    os.makedirs(package_dir, exist_ok=True)
    base = f"{time.strftime('%H%M%S')}_{kind}"
    payload_path = os.path.join(package_dir, f"{base}.json")
    with open(payload_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    copied: list[str] = []
    for path in attachment_paths:
        if path and os.path.exists(path):
            target = os.path.join(package_dir, os.path.basename(path))
            shutil.copyfile(path, target)
            copied.append(target)

    cli = SETTINGS.feishu_cli or _find_cli()
    result: dict[str, Any] = {
        "ok": False,
        "mode": "package",
        "kind": kind,
        "table_name": TABLES.get(kind, kind),
        "payload_path": payload_path,
        "attachments": copied,
        "message": "已生成飞书待上传包；配置 FEISHU_CLI 后可自动推送。",
    }
    if not cli:
        return result

    cmd = [
        cli,
        "push",
        "--kind",
        kind,
        "--payload",
        payload_path,
    ]
    if SETTINGS.feishu_base_token:
        cmd.extend(["--base", SETTINGS.feishu_base_token])
    table_id = _table_id(kind)
    if table_id:
        cmd.extend(["--table", table_id])
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90, encoding="utf-8", errors="replace")
        result.update(
            {
                "ok": proc.returncode == 0,
                "mode": "cli",
                "cli": cli,
                "command": " ".join(cmd),
                "stdout": proc.stdout.strip(),
                "stderr": proc.stderr.strip(),
                "message": "飞书 CLI 推送完成。" if proc.returncode == 0 else "飞书 CLI 推送失败，已保留待上传包。",
            }
        )
    except OSError as exc:
        result.update({"mode": "package", "message": f"飞书 CLI 启动失败，已保留待上传包：{exc}"})
    except subprocess.TimeoutExpired:
        result.update({"mode": "package", "message": "飞书 CLI 推送超时，已保留待上传包。"})
    return result


def _find_cli() -> str:
    for name in ("feishu", "lark", "bitable"):
        path = shutil.which(name)
        if path:
            return path
    return ""


def _table_id(kind: str) -> str:
    return {
        "analysis": SETTINGS.feishu_analysis_table,
        "script": SETTINGS.feishu_script_table,
        "loop": SETTINGS.feishu_loop_table,
        "review": SETTINGS.feishu_review_table,
    }.get(kind, "")
