from __future__ import annotations

import os
import sys
import webbrowser
from threading import Thread
from time import sleep

from flask import Flask, jsonify, render_template, request

if __package__ is None or __package__ == "":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from content_ops_workflow import obsidian
from content_ops_workflow.config import SETTINGS, ensure_dirs
from content_ops_workflow.workflows.content_ops import (
    UploadedCase,
    analyze_case,
    deposit_to_obsidian,
    generate_script,
    read_product_library,
    save_script_and_loop,
    save_upload,
)


def create_app() -> Flask:
    ensure_dirs()
    app = Flask(__name__, template_folder="templates", static_folder="static")

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
        analysis = analyze_case(case)
        paths = deposit_to_obsidian(case, analysis)
        return jsonify({"ok": True, "analysis": analysis, "paths": paths, "file_path": file_path})

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
        script_md = generate_script(case, data.get("analysis", ""), data.get("script_goal", ""))
        paths = save_script_and_loop(case.title or "内容运营脚本", script_md)
        return jsonify({"ok": True, "script": script_md, "paths": paths})

    return app


def form_case(file_path: str) -> UploadedCase:
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
