from __future__ import annotations

import os
import shutil
import subprocess
from typing import Any

from content_ops_workflow.config import SETTINGS
from content_ops_workflow import obsidian


SUPPORTED = ["obsidian", "obsidian-cli", "notesmd-cli", "notesmd"]


def find_cli() -> str:
    configured = SETTINGS.notes_cli.strip()
    if configured and os.path.exists(configured):
        return configured
    for name in SUPPORTED:
        path = shutil.which(name)
        if path:
            return path
    return ""


def status() -> dict[str, Any]:
    cli = find_cli()
    kind = _kind(cli)
    return {
        "ok": bool(cli),
        "cli": cli,
        "kind": kind or "uri-fallback",
        "vault": SETTINGS.obsidian_vault_name,
        "vault_dir": SETTINGS.obsidian_dir,
        "message": _message(kind, bool(cli)),
    }


def open_note(vault_path: str) -> dict[str, Any]:
    cli = find_cli()
    kind = _kind(cli)
    if kind == "official-obsidian":
        return _run([cli, "open", f"obsidian://open?vault={SETTINGS.obsidian_vault_name}&file={vault_path.replace('\\', '/')}"])
    if kind in {"obsidian-cli", "notesmd"}:
        return _fallback_open(vault_path, f"已降级使用 obsidian:// 打开；{kind} 的命令参数未强绑定，避免误写 vault。")
    uri = obsidian.open_note(vault_path)
    return {"ok": True, "mode": "uri-fallback", "uri": uri, "message": "未找到笔记 CLI，已用 obsidian:// 打开。"}


def open_vault() -> dict[str, Any]:
    cli = find_cli()
    kind = _kind(cli)
    if kind == "official-obsidian":
        return _run([cli, "open", f"obsidian://open?vault={SETTINGS.obsidian_vault_name}"])
    uri = obsidian.open_vault()
    return {"ok": True, "mode": "uri-fallback", "uri": uri, "message": "未找到官方 Obsidian CLI，已用 obsidian:// 打开 vault。"}


def reveal(vault_path: str = "") -> dict[str, Any]:
    if vault_path:
        return obsidian.reveal_note(vault_path)
    return obsidian.open_vault_folder()


def _fallback_open(vault_path: str, message: str) -> dict[str, Any]:
    uri = obsidian.open_note(vault_path)
    return {"ok": True, "mode": "uri-fallback", "uri": uri, "message": message}


def _run(cmd: list[str]) -> dict[str, Any]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
        return {
            "ok": proc.returncode == 0,
            "mode": "cli",
            "command": " ".join(cmd),
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
        }
    except Exception as exc:
        return {"ok": False, "mode": "cli", "error": str(exc)}


def _kind(path: str) -> str:
    name = os.path.basename(path).lower()
    if name in {"obsidian.exe", "obsidian.cmd", "obsidian"}:
        return "official-obsidian"
    if "obsidian-cli" in name:
        return "obsidian-cli"
    if "notesmd" in name:
        return "notesmd"
    return ""


def _message(kind: str, found: bool) -> str:
    if kind == "official-obsidian":
        return "已找到官方 Obsidian CLI。"
    if kind:
        return f"已找到 {kind}，当前用于发现和打开，写入仍走 vault 文件/REST。"
    if not found:
        return "未找到笔记 CLI。Obsidian 1.12+ 可在 Settings > General 启用官方 CLI；当前使用文件写入 + obsidian:// URI。"
    return "已找到 CLI。"
