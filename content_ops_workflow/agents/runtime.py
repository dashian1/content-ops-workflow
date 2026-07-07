from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from typing import Any

from content_ops_workflow.agents.skill_router import route_skills
from content_ops_workflow.config import SETTINGS


RUNS_DIR = os.path.join(SETTINGS.output_dir, "agent_runs")


@dataclass
class AgentNode:
    id: str
    title: str
    agent: str
    cluster: str
    status: str = "pending"
    inputs: dict[str, Any] | None = None
    outputs: dict[str, Any] | None = None
    skills_used: list[dict[str, Any]] | None = None
    error: str = ""
    started_at: str = ""
    finished_at: str = ""


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _run_dir(run_id: str) -> str:
    return os.path.join(RUNS_DIR, run_id)


def _graph_path(run_id: str) -> str:
    return os.path.join(_run_dir(run_id), "graph.json")


def _event_path(run_id: str) -> str:
    return os.path.join(_run_dir(run_id), "events.jsonl")


def _write_json(path: str, data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _read_json(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def append_event(run_id: str, event: dict[str, Any]) -> None:
    os.makedirs(_run_dir(run_id), exist_ok=True)
    payload = {"time": _now(), **event}
    with open(_event_path(run_id), "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def default_nodes(intent: dict[str, Any]) -> list[AgentNode]:
    nodes = [
        AgentNode("import", "素材导入", "import", "采集理解集群", inputs={"url": intent.get("url", ""), "raw": intent.get("raw", "")}),
        AgentNode("video", "视频理解", "video_understanding", "采集理解集群", inputs={"file_path": intent.get("file_path", "")}),
        AgentNode("comment", "评论洞察", "comment_insight", "采集理解集群", inputs={"comments": intent.get("comments", "")}),
        AgentNode("analysis", "爆款反推", "viral_analysis", "策略创作集群", inputs={"title": intent.get("title", ""), "platform": intent.get("platform", "")}),
        AgentNode("product", "产品承接", "product_strategy", "策略创作集群", inputs={"product": intent.get("product", ""), "sales": intent.get("sales", "")}),
        AgentNode("script", "脚本生产", "script", "策略创作集群", inputs={"goal": intent.get("goal", ""), "styles": intent.get("styles", [])}),
        AgentNode("loop", "Loop 交接", "loop", "执行交接集群", inputs={}),
        AgentNode("review", "复盘进化", "review_evolution", "复盘进化集群", inputs={}),
    ]
    for node in nodes:
        node.skills_used = route_skills({**intent, **(node.inputs or {})}, node.agent)
    return nodes


def create_run(intent: dict[str, Any]) -> dict[str, Any]:
    os.makedirs(RUNS_DIR, exist_ok=True)
    run_id = time.strftime("%Y%m%d_%H%M%S")
    suffix = 1
    base = run_id
    while os.path.exists(_run_dir(run_id)):
        suffix += 1
        run_id = f"{base}_{suffix}"
    nodes = default_nodes(intent)
    graph = {
        "ok": True,
        "run_id": run_id,
        "status": "planned",
        "created_at": _now(),
        "updated_at": _now(),
        "intent": intent,
        "clusters": ["采集理解集群", "策略创作集群", "执行交接集群", "复盘进化集群"],
        "nodes": [asdict(node) for node in nodes],
        "edges": [
            ["import", "video"],
            ["import", "comment"],
            ["video", "analysis"],
            ["comment", "analysis"],
            ["analysis", "product"],
            ["product", "script"],
            ["script", "loop"],
            ["loop", "review"],
        ],
    }
    _write_json(_graph_path(run_id), graph)
    append_event(run_id, {"type": "run_created", "intent": intent})
    return graph


def get_run(run_id: str) -> dict[str, Any]:
    path = _graph_path(run_id)
    if not os.path.exists(path):
        return {"ok": False, "error": "run not found", "run_id": run_id}
    graph = _read_json(path)
    events = []
    event_path = _event_path(run_id)
    if os.path.exists(event_path):
        with open(event_path, encoding="utf-8") as f:
            events = [json.loads(line) for line in f if line.strip()]
    graph["events"] = events[-100:]
    return graph


def list_runs(limit: int = 20) -> dict[str, Any]:
    if not os.path.exists(RUNS_DIR):
        return {"ok": True, "runs": []}
    runs = []
    for name in sorted(os.listdir(RUNS_DIR), reverse=True):
        path = _graph_path(name)
        if not os.path.exists(path):
            continue
        graph = _read_json(path)
        runs.append(
            {
                "run_id": graph.get("run_id", name),
                "status": graph.get("status", ""),
                "created_at": graph.get("created_at", ""),
                "title": graph.get("intent", {}).get("title") or graph.get("intent", {}).get("raw", "")[:40],
                "node_count": len(graph.get("nodes", [])),
            }
        )
        if len(runs) >= limit:
            break
    return {"ok": True, "runs": runs}


def update_node(run_id: str, node_id: str, status: str, outputs: dict[str, Any] | None = None, error: str = "") -> dict[str, Any]:
    graph = get_run(run_id)
    if not graph.get("ok"):
        return graph
    for node in graph.get("nodes", []):
        if node.get("id") == node_id:
            node["status"] = status
            node["outputs"] = outputs or node.get("outputs") or {}
            node["error"] = error
            if status == "running" and not node.get("started_at"):
                node["started_at"] = _now()
            if status in {"done", "failed", "skipped", "waiting_user"}:
                node["finished_at"] = _now()
            break
    graph["updated_at"] = _now()
    graph["status"] = _derive_status(graph.get("nodes", []))
    graph.pop("events", None)
    _write_json(_graph_path(run_id), graph)
    append_event(run_id, {"type": "node_update", "node_id": node_id, "status": status, "outputs": outputs or {}, "error": error})
    return get_run(run_id)


def _derive_status(nodes: list[dict[str, Any]]) -> str:
    statuses = {node.get("status") for node in nodes}
    if "failed" in statuses:
        return "failed"
    if "running" in statuses:
        return "running"
    if statuses and statuses <= {"done", "skipped"}:
        return "done"
    if "waiting_user" in statuses:
        return "waiting_user"
    return "planned"
