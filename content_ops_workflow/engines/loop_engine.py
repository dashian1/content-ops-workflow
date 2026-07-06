from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from typing import Any

from content_ops_workflow.config import SETTINGS


JOB_VERSION = "content-loop-job/v1"
STATUS_VALUES = ["queued", "picked", "running", "done", "failed", "cancelled"]


def loops_root() -> str:
    configured = (SETTINGS.external_loops_dir or "").strip()
    if configured:
        return configured
    return os.path.join(SETTINGS.root, "loops")


def handoff_dir() -> str:
    return os.path.join(loops_root(), "content_ops_handoff")


def jobs_dir() -> str:
    return os.path.join(handoff_dir(), "jobs")


def status_dir() -> str:
    return os.path.join(handoff_dir(), "status")


def results_dir() -> str:
    return os.path.join(handoff_dir(), "results")


def ensure_dirs() -> None:
    for path in [handoff_dir(), jobs_dir(), status_dir(), results_dir()]:
        os.makedirs(path, exist_ok=True)


def create_job(
    title: str,
    rows: list[dict[str, str]],
    source_paths: dict[str, str],
    candidate: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ensure_dirs()
    job_id = f"loop_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    job_folder = os.path.join(jobs_dir(), job_id)
    os.makedirs(job_folder, exist_ok=True)

    copied_sources = _copy_sources(job_folder, source_paths)
    job = {
        "version": JOB_VERSION,
        "job_id": job_id,
        "title": title,
        "status": "queued",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "rows": rows,
        "source_paths": copied_sources,
        "candidate": candidate or {},
        "metadata": metadata or {},
        "expected_result": {
            "status_json": os.path.join(status_dir(), f"{job_id}.json"),
            "result_json": os.path.join(results_dir(), f"{job_id}.json"),
            "fields": ["status", "storyboard_links", "image_links", "video_links", "error", "updated_at"],
        },
    }
    job_path = os.path.join(job_folder, "job.json")
    with open(job_path, "w", encoding="utf-8") as f:
        json.dump(job, f, ensure_ascii=False, indent=2)

    status = write_status(job_id, "queued", {"job_path": job_path, "title": title})
    manifest_path = _write_manifest()
    return {
        "ok": True,
        "job_id": job_id,
        "job_path": job_path,
        "job_folder": job_folder,
        "status_path": status["status_path"],
        "manifest_path": manifest_path,
        "handoff_dir": handoff_dir(),
    }


def write_status(job_id: str, status: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    ensure_dirs()
    clean_status = status if status in STATUS_VALUES else "running"
    data = {
        "job_id": job_id,
        "status": clean_status,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        **(payload or {}),
    }
    status_path = os.path.join(status_dir(), f"{job_id}.json")
    with open(status_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return {"ok": True, "status_path": status_path, "status": clean_status}


def write_result(job_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    ensure_dirs()
    data = {
        "job_id": job_id,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        **payload,
    }
    result_path = os.path.join(results_dir(), f"{job_id}.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    if data.get("status"):
        write_status(job_id, str(data["status"]), data)
    return {"ok": True, "result_path": result_path}


def list_jobs(limit: int = 50) -> dict[str, Any]:
    ensure_dirs()
    items: list[dict[str, Any]] = []
    for root, _dirs, files in os.walk(jobs_dir()):
        if "job.json" not in files:
            continue
        path = os.path.join(root, "job.json")
        try:
            with open(path, encoding="utf-8") as f:
                job = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        status = read_status(job.get("job_id", ""))
        items.append(
            {
                "job_id": job.get("job_id", ""),
                "title": job.get("title", ""),
                "created_at": job.get("created_at", ""),
                "status": status.get("status") or job.get("status", "queued"),
                "job_path": path,
                "status_path": status.get("status_path", ""),
            }
        )
    items.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    return {"ok": True, "handoff_dir": handoff_dir(), "jobs": items[:limit]}


def read_status(job_id: str) -> dict[str, Any]:
    if not job_id:
        return {}
    path = os.path.join(status_dir(), f"{job_id}.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        data["status_path"] = path
        return data
    except (OSError, json.JSONDecodeError):
        return {}


def _copy_sources(job_folder: str, source_paths: dict[str, str]) -> dict[str, str]:
    copied: dict[str, str] = {}
    for label, path in source_paths.items():
        if path and os.path.exists(path):
            target = os.path.join(job_folder, os.path.basename(path))
            shutil.copyfile(path, target)
            copied[label] = target
    return copied


def _write_manifest() -> str:
    manifest = {
        "version": JOB_VERSION,
        "handoff_dir": handoff_dir(),
        "jobs_dir": jobs_dir(),
        "status_dir": status_dir(),
        "results_dir": results_dir(),
        "status_values": STATUS_VALUES,
        "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    path = os.path.join(handoff_dir(), "manifest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return path
