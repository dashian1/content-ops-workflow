from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import datetime
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
    profile = _feishu_profile()
    cli_ready = _cli_ready(cli)
    import_ready = bool(cli_ready)
    return {
        "ok": import_ready,
        "mode": "lark-cli" if import_ready else "package",
        "cli": " ".join(cli),
        "cli_ready": cli_ready,
        "profile": profile,
        "default_cli": DEFAULT_LARK_CLI,
        "base_token_configured": bool(SETTINGS.feishu_base_token),
        "tables": {
            "analysis": SETTINGS.feishu_analysis_table,
            "script": SETTINGS.feishu_script_table,
            "loop": SETTINGS.feishu_loop_table,
            "review": SETTINGS.feishu_review_table,
        },
        "message": _status_message(cli, profile),
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

    current = status()
    if not current.get("ok"):
        result["message"] = f"{current.get('message')} 已保留待上传包。"
        return result

    title = _title(kind, payload)
    try:
        imported = import_xlsx(xlsx, title)
        result.update(
            {
                "ok": True,
                "mode": "lark-cli",
                "import": imported,
                "url": imported.get("url", ""),
                "message": "已导入飞书表格。",
            }
        )
    except Exception as exc:
        result.update({"mode": "package", "message": f"飞书导入失败，已保留待上传包：{str(exc)[:1000]}"})
    return result


def import_xlsx(xlsx_path: str, title: str) -> dict[str, str]:
    cli = _find_cli()
    if not cli:
        raise FileNotFoundError("本机没有找到 lark-cli。")
    out = _run_lark(
        cli
        + [
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


def _find_cli() -> list[str]:
    configured = SETTINGS.feishu_cli or os.environ.get("LARK_CLI", "").strip()
    if configured and os.path.isfile(configured):
        return [configured]
    for name in ("lark-cli", "lark", "feishu", "bitable"):
        path = shutil.which(name)
        if path:
            return [path]
    if os.path.exists(DEFAULT_LARK_CLI):
        return [DEFAULT_LARK_CLI]
    npx = shutil.which("npx")
    if npx:
        return [npx, "@larksuite/cli@latest"]
    return []


def _cli_ready(cli: list[str]) -> bool:
    if not cli:
        return False
    try:
        out = _run_lark(cli + ["whoami"], cwd=SETTINGS.root, timeout=60)
        data = _first_json(out)
        return bool(data.get("available") and data.get("tokenStatus") == "ready")
    except Exception:
        return False


def _feishu_profile() -> dict[str, Any]:
    root = SETTINGS.feishu_cli if SETTINGS.feishu_cli and os.path.isdir(SETTINGS.feishu_cli) else os.path.expanduser(r"~\.feishu-cli")
    config_path = os.path.join(root, "config.yaml")
    token_path = os.path.join(root, "token.json")
    data: dict[str, Any] = {
        "root": root,
        "config_found": os.path.exists(config_path),
        "token_found": os.path.exists(token_path),
        "access_token_valid": False,
        "refresh_token_valid": False,
    }
    if os.path.exists(token_path):
        try:
            with open(token_path, encoding="utf-8") as f:
                token = json.load(f)
            data["expires_at"] = token.get("expires_at", "")
            data["refresh_expires_at"] = token.get("refresh_expires_at", "")
            data["access_token_valid"] = _future(token.get("expires_at", ""))
            data["refresh_token_valid"] = _future(token.get("refresh_expires_at", ""))
        except (OSError, json.JSONDecodeError):
            data["token_error"] = "token.json 读取失败"
    return data


def _future(value: str) -> bool:
    if not value:
        return False
    try:
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        return dt.timestamp() > time.time()
    except ValueError:
        return False


def _status_message(cli: list[str], profile: dict[str, Any]) -> str:
    if cli and _cli_ready(cli):
        return "已找到可执行 lark-cli，当前身份可用，可以尝试导入飞书表格。"
    if cli and profile.get("config_found"):
        return "已找到 lark-cli，但旧 .feishu-cli token 已过期；如导入个人云文档失败，需要重新登录 user 身份。"
    if cli:
        return "已找到 lark-cli，但身份不可用，需要先登录授权。"
    if profile.get("config_found") and profile.get("access_token_valid"):
        return "找到 .feishu-cli 且 token 有效，但没有找到可执行 lark-cli；当前只能生成待上传包。"
    if profile.get("config_found"):
        return "找到 .feishu-cli 凭证目录，但 token 已过期或不可用；需要重新登录飞书 CLI。"
    return "未找到 lark-cli 或 .feishu-cli，系统会先生成飞书待上传包。"


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
