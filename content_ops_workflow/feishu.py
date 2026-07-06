from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from typing import Any

from content_ops_workflow.config import SETTINGS


DEFAULT_LARK_CLI = r"C:\Users\gba\.workbuddy\binaries\node\versions\22.22.2\lark-cli.cmd"

TABLES = {
    "analysis": "爆款分析",
    "script": "脚本候选",
    "loop": "Loop生产",
    "review": "数据复盘",
}


def status() -> dict[str, Any]:
    cli = _find_cli()
    return {
        "ok": bool(cli),
        "mode": "lark-cli" if cli else "package",
        "cli": cli,
        "default_cli": DEFAULT_LARK_CLI,
        "base_token_configured": bool(SETTINGS.feishu_base_token),
        "tables": {
            "analysis": SETTINGS.feishu_analysis_table,
            "script": SETTINGS.feishu_script_table,
            "loop": SETTINGS.feishu_loop_table,
            "review": SETTINGS.feishu_review_table,
        },
        "message": "已找到老项目 lark-cli，可导入飞书表格。" if cli else "未找到 lark-cli，系统会先生成待上传包。",
    }


def push_payload(kind: str, payload: dict[str, Any], attachment_paths: list[str] | None = None) -> dict[str, Any]:
    attachment_paths = attachment_paths or []
    package_dir = os.path.join(SETTINGS.output_dir, "feishu_packages", time.strftime("%Y-%m-%d"))
    os.makedirs(package_dir, exist_ok=True)
    base = f"{time.strftime('%H%M%S')}_{kind}"
    payload_path = os.path.join(package_dir, f"{base}.json")
    with open(payload_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    copied = _copy_attachments(package_dir, attachment_paths)
    xlsx = next((path for path in copied if path.lower().endswith(".xlsx")), "")
    result: dict[str, Any] = {
        "ok": False,
        "mode": "package",
        "kind": kind,
        "table_name": TABLES.get(kind, kind),
        "payload_path": payload_path,
        "attachments": copied,
        "message": "已生成飞书待上传包。",
    }
    if not xlsx:
        result["message"] = "没有 xlsx 附件，已生成飞书待上传包。"
        return result

    cli = _find_cli()
    if not cli:
        result["message"] = "未找到 lark-cli，已生成飞书待上传包。"
        return result

    title = _title(kind, payload)
    try:
        imported = import_xlsx(xlsx, title)
        result.update({"ok": True, "mode": "lark-cli", "import": imported, "url": imported.get("url", ""), "message": "已导入飞书表格。"})
    except Exception as exc:
        result.update({"mode": "package", "message": f"飞书导入失败，已保留待上传包：{str(exc)[:1000]}"})
    return result


def import_xlsx(xlsx_path: str, title: str) -> dict[str, str]:
    cli = _find_cli()
    if not cli:
        raise FileNotFoundError("本机没有找到 lark-cli。")
    out = _run_lark(
        [
            cli,
            "drive",
            "+import",
            "--file",
            f".\\{os.path.basename(xlsx_path)}",
            "--type",
            "sheet",
            "--name",
            title,
            "--as",
            "user",
            "--format",
            "json",
        ],
        cwd=os.path.dirname(xlsx_path),
        timeout=1200,
    )
    data = _first_json(out)
    payload = data.get("data", data)
    token = payload.get("token") or payload.get("file_token") or ""
    url = payload.get("url") or (f"https://ucnscwivbsrz.feishu.cn/sheets/{token}" if token else "")
    if not token or not url:
        raise RuntimeError(f"飞书导入结果缺少 token/url：{out[:1000]}")
    return {"status": "imported", "token": token, "url": url, "title": title}


def _copy_attachments(package_dir: str, attachment_paths: list[str]) -> list[str]:
    copied: list[str] = []
    for path in attachment_paths:
        if path and os.path.exists(path):
            target = os.path.join(package_dir, os.path.basename(path))
            shutil.copyfile(path, target)
            copied.append(target)
    return copied


def _find_cli() -> str:
    configured = SETTINGS.feishu_cli or os.environ.get("LARK_CLI", "").strip()
    if configured and os.path.exists(configured):
        return configured
    for name in ("lark-cli", "lark", "feishu", "bitable"):
        path = shutil.which(name)
        if path:
            return path
    if os.path.exists(DEFAULT_LARK_CLI):
        return DEFAULT_LARK_CLI
    return ""


def _run_lark(cmd: list[str], cwd: str, timeout: int = 900) -> str:
    proc = subprocess.run(
        cmd,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
        shell=False,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stdout + "\n" + proc.stderr).strip()[:2000])
    return proc.stdout


def _first_json(text: str) -> dict[str, Any]:
    start = text.find("{")
    if start < 0:
        raise ValueError(text[:1000] or "飞书命令没有返回 JSON。")
    depth = 0
    in_str = False
    escape = False
    for index, char in enumerate(text[start:], start):
        if in_str:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_str = False
        else:
            if char == '"':
                in_str = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[start : index + 1])
    raise ValueError("飞书命令返回的 JSON 不完整。")


def _title(kind: str, payload: dict[str, Any]) -> str:
    case = payload.get("case") if isinstance(payload.get("case"), dict) else {}
    title = str(payload.get("title") or case.get("title") or TABLES.get(kind, kind)).strip()
    suffix = time.strftime("%m%d_%H%M")
    return f"{title[:40]}_{TABLES.get(kind, kind)}_{suffix}"
