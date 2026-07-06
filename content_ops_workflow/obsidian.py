from __future__ import annotations

import os
import subprocess
import urllib.parse
import webbrowser
from dataclasses import dataclass
from typing import Any

import requests

from content_ops_workflow.config import SETTINGS


@dataclass
class ObsidianWriteResult:
    ok: bool
    mode: str
    vault_path: str
    local_path: str
    open_uri: str
    error: str = ""


def rest_headers() -> dict[str, str]:
    headers = {"Content-Type": "text/markdown"}
    if SETTINGS.obsidian_api_key:
        headers["Authorization"] = f"Bearer {SETTINGS.obsidian_api_key}"
    return headers


def rest_enabled() -> bool:
    return bool(SETTINGS.obsidian_api_key and SETTINGS.obsidian_rest_url)


def plugin_status() -> dict[str, Any]:
    base = {
        "rest_url": SETTINGS.obsidian_rest_url,
        "vault": SETTINGS.obsidian_vault_name,
        "vault_dir": SETTINGS.obsidian_dir,
        "uri_available": True,
        "app_data_found": os.path.isdir(os.path.expandvars(r"%APPDATA%\obsidian")),
    }
    if not rest_enabled():
        return {
            **base,
            "ok": False,
            "mode": "file-uri",
            "message": "未配置 Obsidian Local REST API Key；当前使用文件写入 + obsidian:// URI 打开。",
        }
    try:
        response = requests.get(
            f"{SETTINGS.obsidian_rest_url.rstrip('/')}/",
            headers=rest_headers(),
            timeout=5,
            verify=False,
        )
    except requests.RequestException as exc:
        return {
            **base,
            "ok": False,
            "mode": "file-uri",
            "message": f"Obsidian Local REST API 连接失败：{exc}",
        }
    return {
        **base,
        "ok": response.status_code < 400,
        "mode": "plugin" if response.status_code < 400 else "file-uri",
        "status_code": response.status_code,
        "message": response.text[:500],
    }


def note_uri(vault_path: str) -> str:
    return "obsidian://open?" + urllib.parse.urlencode(
        {
            "vault": SETTINGS.obsidian_vault_name,
            "file": vault_path.replace("\\", "/"),
        }
    )


def vault_uri() -> str:
    return "obsidian://open?" + urllib.parse.urlencode({"vault": SETTINGS.obsidian_vault_name})


def local_note_path(vault_path: str) -> str:
    return os.path.join(SETTINGS.obsidian_dir, *vault_path.replace("\\", "/").split("/"))


def write_note(vault_path: str, body: str) -> ObsidianWriteResult:
    body = body.strip() + "\n"
    uri = note_uri(vault_path)
    local_path = local_note_path(vault_path)
    if rest_enabled():
        encoded_path = urllib.parse.quote(vault_path.replace("\\", "/"), safe="/")
        try:
            response = requests.put(
                f"{SETTINGS.obsidian_rest_url.rstrip('/')}/vault/{encoded_path}",
                headers=rest_headers(),
                data=body.encode("utf-8"),
                timeout=10,
                verify=False,
            )
            if response.status_code < 400:
                if SETTINGS.obsidian_open_after_write:
                    open_uri(uri)
                return ObsidianWriteResult(True, "plugin", vault_path, local_path, uri)
            error = f"Local REST API 写入失败：HTTP {response.status_code} {response.text[:300]}"
        except requests.RequestException as exc:
            error = f"Local REST API 写入失败：{exc}"
    else:
        error = "未配置 OBSIDIAN_API_KEY。"

    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(body)
    return ObsidianWriteResult(True, "file-uri", vault_path, local_path, uri, error=error)


def open_uri(uri: str) -> str:
    try:
        subprocess.Popen(["cmd", "/c", "start", "", uri], shell=False)
    except OSError:
        webbrowser.open(uri)
    return uri


def open_note(vault_path: str) -> str:
    return open_uri(note_uri(vault_path))


def open_vault() -> str:
    return open_uri(vault_uri())


def reveal_note(vault_path: str) -> dict[str, Any]:
    path = local_note_path(vault_path)
    if os.path.exists(path):
        subprocess.Popen(["explorer", "/select,", path], shell=False)
        return {"ok": True, "path": path}
    folder = os.path.dirname(path) or SETTINGS.obsidian_dir
    if os.path.isdir(folder):
        subprocess.Popen(["explorer", folder], shell=False)
        return {"ok": False, "path": path, "message": "笔记不存在，已打开所在目录。"}
    return {"ok": False, "path": path, "message": "笔记和目录都不存在。"}


def open_vault_folder() -> dict[str, Any]:
    os.makedirs(SETTINGS.obsidian_dir, exist_ok=True)
    subprocess.Popen(["explorer", SETTINGS.obsidian_dir], shell=False)
    return {"ok": True, "path": SETTINGS.obsidian_dir}
