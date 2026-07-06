from __future__ import annotations

import os
import sys
import webbrowser
from hmac import compare_digest
from threading import Thread
from time import sleep

from flask import Flask, Response, jsonify, render_template, request

if __package__ is None or __package__ == "":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from content_ops_workflow import obsidian
from content_ops_workflow.config import SETTINGS, ensure_dirs
from content_ops_workflow.workflows.content_ops import (
    UploadedCase,
    analyze_case,
    deposit_to_obsidian,
    enrich_case_with_video,
    generate_script,
    generate_candidates,
    loop_from_candidate,
    match_product,
    record_feedback,
    read_product_library,
    save_script_and_loop,
    save_upload,
)


def create_app() -> Flask:
    ensure_dirs()
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["MAX_CONTENT_LENGTH"] = SETTINGS.max_upload_mb * 1024 * 1024
    app.before_request(require_basic_auth)

    @app.route("/")
    def index():
        return render_template(
            "index.html",
            obsidian_dir=SETTINGS.obsidian_dir,
            obsidian_rest_url=SETTINGS.obsidian_rest_url,
            obsidian_vault_name=SETTINGS.obsidian_vault_name,
            product_kb_dir=SETTINGS.product_kb_dir,
            api_configured=bool(SETTINGS.api_key),
        )

    @app.route("/health")
    def health():
        return jsonify({"ok": True})

    @app.route("/api/product-library")
    def product_library():
        return jsonify({"ok": True, "dir": SETTINGS.product_kb_dir, "preview": read_product_library(3000)})

    @app.route("/api/obsidian/status")
    def obsidian_status():
        return jsonify(obsidian.plugin_status())

    @app.route("/api/obsidian/open", methods=["POST"])
    def obsidian_open():
        data = request.json or {}
        vault_path = data.get("vault_path", "")
        if not vault_path:
            return jsonify({"ok": False, "error": "缺少 vault_path"})
        return jsonify({"ok": True, "open_uri": obsidian.open_note(vault_path)})

    @app.route("/api/analyze", methods=["POST"])
    def analyze():
        file_path = save_upload(request.files.get("file"))
        case = form_case(file_path)
        case = enrich_case_with_video(case)
        analysis = analyze_case(case)
        product_match = match_product(case, analysis)
        paths = deposit_to_obsidian(case, analysis, product_match)
        video_package = None
        if case.video_package:
            video_package = {
                "package_dir": case.video_package.package_dir,
                "manifest_path": case.video_package.manifest_path,
                "transcript": case.video_package.transcript,
                "transcript_source": case.video_package.transcript_source,
                "transcript_warning": case.video_package.transcript_warning,
                "frame_count": case.video_package.frame_count,
                "extracted_count": case.video_package.extracted_count,
            }
        return jsonify({"ok": True, "analysis": analysis, "product_match": product_match, "paths": paths, "file_path": file_path, "video_package": video_package})

    @app.route("/api/generate-script", methods=["POST"])
    def script():
        data = request.json or {}
        case = UploadedCase(
            title=data.get("title", ""),
            platform=data.get("platform", ""),
            url=data.get("url", ""),
            metrics=data.get("metrics", ""),
            reason=data.get("reason", ""),
            transcript=data.get("transcript", ""),
            notes=data.get("notes", ""),
            file_path=data.get("file_path", ""),
        )
        script_md = generate_script(case, data.get("analysis", ""), data.get("script_goal", ""), data.get("product_match", ""))
        paths = save_script_and_loop(case.title or "内容运营脚本", script_md)
        return jsonify({"ok": True, "script": script_md, "paths": paths})

    @app.route("/api/candidates", methods=["POST"])
    def candidates():
        data = request.json or {}
        case = json_case(data)
        styles = data.get("styles") or None
        candidates_data = generate_candidates(case, data.get("analysis", ""), data.get("product_match", ""), data.get("script_goal", ""), styles)
        from content_ops_workflow.workflows.content_ops import save_candidates

        paths = save_candidates(case.title or "内容运营候选池", candidates_data)
        return jsonify({"ok": True, "candidates": candidates_data, "paths": paths})

    @app.route("/api/candidate-loop", methods=["POST"])
    def candidate_loop():
        data = request.json or {}
        candidate = data.get("candidate") or {}
        title = data.get("title") or candidate.get("title") or "候选脚本"
        paths = loop_from_candidate(candidate, title)
        return jsonify({"ok": True, "paths": paths})

    @app.route("/api/feedback", methods=["POST"])
    def feedback():
        data = request.json or {}
        paths = record_feedback(data)
        return jsonify({"ok": True, "paths": paths, "review": paths.get("review", "")})

    return app


def require_basic_auth():
    if not SETTINGS.app_password or request.path == "/health":
        return None
    auth = request.authorization
    if auth and compare_digest(auth.username or "", SETTINGS.app_username) and compare_digest(auth.password or "", SETTINGS.app_password):
        return None
    return Response("Authentication required", 401, {"WWW-Authenticate": 'Basic realm="ContentOps"'})


def form_case(file_path: str) -> UploadedCase:
    if request.is_json:
        return json_case(request.get_json(silent=True) or {})
    return UploadedCase(
        title=request.form.get("title", "").strip(),
        platform=request.form.get("platform", "").strip(),
        url=request.form.get("url", "").strip(),
        metrics=request.form.get("metrics", "").strip(),
        reason=request.form.get("reason", "").strip(),
        transcript=request.form.get("transcript", "").strip(),
        notes=request.form.get("notes", "").strip(),
        file_path=file_path,
    )


def json_case(data: dict) -> UploadedCase:
    return UploadedCase(
        title=data.get("title", ""),
        platform=data.get("platform", ""),
        url=data.get("url", ""),
        metrics=data.get("metrics", ""),
        reason=data.get("reason", ""),
        transcript=data.get("transcript", ""),
        notes=data.get("notes", ""),
        file_path=data.get("file_path", ""),
    )


app = create_app()


def open_browser() -> None:
    sleep(1)
    webbrowser.open(f"http://{SETTINGS.host}:{SETTINGS.port}")


if __name__ == "__main__":
    print("内容运营 Workflow")
    print(f"Obsidian: {SETTINGS.obsidian_dir}")
    print(f"产品库: {SETTINGS.product_kb_dir}")
    if os.environ.get("NO_BROWSER") != "1":
        Thread(target=open_browser, daemon=True).start()
    app.run(host=SETTINGS.host, port=SETTINGS.port, debug=False)
