from __future__ import annotations

import csv
import json
import os
import re
import shutil
import time
from dataclasses import dataclass
from typing import Any

from openpyxl import Workbook

from content_ops_workflow import llm
from content_ops_workflow import obsidian
from content_ops_workflow.config import SETTINGS
from content_ops_workflow.engines import comment_engine, context_engine, evaluation_engine, evolution_engine, loop_engine, memory_engine, planning_engine, prompt_builder
from content_ops_workflow.video_understanding import VideoPackage, build_video_package, is_video


LOOP_COLUMNS = prompt_builder.LOOP_COLUMNS
SCRIPT_STYLES = prompt_builder.SCRIPT_STYLES


@dataclass
class UploadedCase:
    title: str
    platform: str
    url: str
    metrics: str
    reason: str
    transcript: str
    notes: str
    file_path: str
    sales: str = ""
    comments: str = ""
    video_package: VideoPackage | None = None


def safe_filename(text: str, fallback: str = "content") -> str:
    text = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", (text or "").strip())
    text = re.sub(r"\s+", "_", text).strip("._ ")
    return text[:80] or fallback


def yaml_escape(value: str) -> str:
    value = (value or "").replace('"', '\\"')
    return f'"{value}"'


def yaml_list(values: list[str], indent: str = "  ") -> list[str]:
    clean = [value for value in values if value]
    if not clean:
        return [f"{indent}- 未分类"]
    return [f"{indent}- {value}" for value in clean]


def frontmatter(fields: dict[str, str], tags: list[str]) -> str:
    lines = ["---"]
    for key, value in fields.items():
        lines.append(f"{key}: {yaml_escape(str(value))}")
    lines.append("tags:")
    lines.extend(yaml_list(tags))
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def save_upload(file_storage: Any) -> str:
    if not file_storage or not getattr(file_storage, "filename", ""):
        return ""
    today = time.strftime("%Y-%m-%d")
    out_dir = os.path.join(SETTINGS.upload_dir, today)
    os.makedirs(out_dir, exist_ok=True)
    filename = safe_filename(file_storage.filename, "upload")
    target = os.path.join(out_dir, f"{time.strftime('%H%M%S')}_{filename}")
    file_storage.save(target)
    return target


def read_product_library(limit: int = 12000) -> str:
    if not os.path.isdir(SETTINGS.product_kb_dir):
        return f"产品库目录不存在: {SETTINGS.product_kb_dir}"
    chunks: list[str] = []
    for name in sorted(os.listdir(SETTINGS.product_kb_dir)):
        if not name.lower().endswith((".md", ".txt")):
            continue
        path = os.path.join(SETTINGS.product_kb_dir, name)
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read().strip()
        except OSError:
            continue
        if text:
            chunks.append(f"# {name}\n\n{text}")
    return "\n\n---\n\n".join(chunks)[:limit]


def read_template_library(limit: int = 8000) -> str:
    path = os.path.join(SETTINGS.root, "templates_library", "viral_templates.md")
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()[:limit]
    except OSError:
        return "未找到爆款结构模板库。"


def video_context(case: UploadedCase) -> str:
    if not case.video_package:
        return "未生成视频理解包。"
    package = case.video_package
    manifest_text = ""
    try:
        with open(package.manifest_path, encoding="utf-8") as f:
            manifest_text = f.read()[:2500]
    except OSError:
        pass
    return f"""视频理解包:
- package_dir: {package.package_dir}
- manifest_path: {package.manifest_path}
- duration: {package.duration:.1f}s
- fps: {package.fps:.2f}
- frames: {package.frame_count}
- transcript_source: {package.transcript_source}
- transcript_warning: {package.transcript_warning}

自动口播:
{package.transcript[:3000] if package.transcript else "未识别到有效口播"}

MANIFEST 摘要:
{manifest_text}
"""


def enrich_case_with_video(case: UploadedCase) -> UploadedCase:
    if case.file_path and is_video(case.file_path):
        package = build_video_package(case.file_path, case.transcript, case.title, case.url)
        case.video_package = package
        if not case.transcript and package.transcript:
            case.transcript = package.transcript
    return case


def analyze_prompt(case: UploadedCase, product_library: str) -> str:
    return f"""你是内容运营负责人。请分析一条由人工筛选出来的爆款素材。

这一步不是简单总结内容，而是拆出可复用的运营资产。必须按下面字段输出 Markdown。

【硬性约束｜防跑偏】
1. 分析阶段只拆解“原爆款素材”，不要生成本品脚本，不要把素材改写成产品广告。
2. 必须保留原素材的 source_prototype_lock：职业身份、生活场景、情绪张力、呈现形式、植入方式。
3. 产品库只允许在“## 10. 产品承接”里用于判断可承接产品，不能覆盖原素材话题、受众、结构和表达。
4. 如果原素材是空姐/晚班/超长待机/职场女性/vlog/高蛋白拿铁，就必须围绕这个原型拆解；不得改写成灵芝茶避坑、掉发、配料表、测评打假等其他原型。
5. 遇到信息不足，标注“信息不足”，不要脑补具体数据、账号背景和视频画面。

【素材信息】
- 标题: {case.title or "未填写"}
- 平台: {case.platform or "未填写"}
- 链接: {case.url or "未填写"}
- 数据: {case.metrics or "未填写"}
- 人工选择原因: {case.reason or "未填写"}
- 上传文件: {case.file_path or "无"}
- 口播/字幕: {case.transcript[:3000] if case.transcript else "未提供"}
- 备注: {case.notes[:1500] if case.notes else "无"}

【视频理解】
{video_context(case)}

【产品库摘要】
{product_library}

【爆款结构模板库】
{read_template_library()}

请输出:

# 爆款内容分析

## 0. Source Prototype Lock
- 原始人物/身份:
- 原始场景:
- 原始情绪/冲突:
- 原始呈现形式:
- 原始产品植入方式:
- 禁止迁移成:

## 1. 基础判断
- 是否值得拆:
- 爆款类型:
- 最值得复用的一句话:

## 2. 话题
- 大话题:
- 小话题:
- 话题热度原因:

## 3. 选题
- 选题角度:
- 选题冲突:
- 选题可复用模板:

## 4. 受众群体
- 核心受众:
- 隐性受众:
- 受众痛点/欲望:
- 受众为什么会停留:

## 5. 呈现形式
- 内容形态:
- 人设/叙述者:
- 场景:
- 画面载体:

## 6. 爆款元素
- 情绪:
- 反差/冲突:
- 信息差:
- 猎奇点:
- 评论触发点:

## 7. 内容结构
按 开头3秒 / 承接 / 递进 / 转折 / 高潮 / 收尾 拆。

## 8. 金句表达
- 标题句式:
- 开头句式:
- 中段金句:
- 收尾金句:
- 可迁移表达:

## 9. 剪辑风格
- 节奏:
- 字幕:
- 音效/音乐:
- 镜头:
- B-roll:
- 转场:

## 10. 产品承接
- 适合承接的产品:
- 为什么适合:
- 产品自然出现的位置:
- 必须出现的产品证据:
- 不适合承接的产品:

## 11. 风险点
- 不能照搬:
- 合规风险:
- 版权/平台风险:
- 安全改写方向:

## 12. 可沉淀知识
- 话题卡片:
- 选题卡片:
- 结构卡片:
- 金句卡片:
- 剪辑风格卡片:
"""


def analyze_case(case: UploadedCase) -> str:
    product_library = read_product_library()
    return llm.call_text(
        "你是内容运营总监、短视频编导和产品转化策略负责人。",
        analyze_prompt(case, product_library),
        max_tokens=5000,
    )


def product_match_prompt(case: UploadedCase, analysis: str, product_library: str) -> str:
    return f"""你是产品匹配和内容运营策略负责人。请基于爆款分析、爆款模板库和产品库，单独输出产品匹配报告。

【爆款素材】
- 标题: {case.title}
- 平台: {case.platform}
- 链接: {case.url}
- 数据: {case.metrics}
- 人工选择原因: {case.reason}

【爆款分析】
{analysis[:5000]}

【爆款结构模板库】
{read_template_library()}

【产品库】
{product_library}

请输出 Markdown:

# 产品匹配报告

## 1. 推荐产品排序
| 排名 | 产品 | 匹配度(0-100) | 适配理由 | 风险 |

## 2. 最佳承接产品
- 产品:
- 目标受众:
- 对应爆款结构模板:
- 为什么适合:
- 不适合的部分:

## 3. 产品自然出现位置
- 开头:
- 中段:
- 证据段:
- 收尾:

## 4. 必须出现的视觉证据
- 证据1:
- 证据2:
- 证据3:

## 5. 合规边界
- 禁用表达:
- 安全替代表达:
- 不能照搬的爆款表达:

## 6. 脚本生成建议
- 推荐风格:
- 推荐时长:
- 推荐呈现形式:
- 推荐剪辑风格:
"""


def match_product(case: UploadedCase, analysis: str) -> str:
    return llm.call_text(
        "你是产品匹配、内容转化和合规策略负责人。",
        product_match_prompt(case, analysis, read_product_library()),
        max_tokens=3200,
    )


def write_obsidian_note(folder: str, title: str, body: str) -> dict[str, str]:
    vault_path = f"{folder}/{time.strftime('%Y%m%d_%H%M%S')}_{safe_filename(title)}.md"
    result = obsidian.write_note(vault_path, body)
    return {
        "mode": result.mode,
        "vault_path": result.vault_path,
        "local_path": result.local_path,
        "open_uri": result.open_uri,
        "error": result.error,
    }


def deposit_to_obsidian(case: UploadedCase, analysis: str, product_match: str = "") -> dict[str, dict[str, str]]:
    title = case.title or "爆款素材"
    created = time.strftime("%Y-%m-%d %H:%M:%S")
    base_fields = {
        "title": title,
        "type": "viral_analysis",
        "status": "analyzed",
        "platform": case.platform,
        "url": case.url,
        "metrics": case.metrics,
        "source_file": case.file_path,
        "video_package": case.video_package.package_dir if case.video_package else "",
        "video_manifest": case.video_package.manifest_path if case.video_package else "",
        "transcript_source": case.video_package.transcript_source if case.video_package else ("manual" if case.transcript else ""),
        "created": created,
    }
    base_tags = ["内容运营", "爆款分析", f"平台/{safe_filename(case.platform, '未填')}"]
    full = frontmatter(base_fields, base_tags) + analysis
    paths: dict[str, dict[str, str]] = {
        "analysis": write_obsidian_note("01_爆款分析", title, full),
    }
    analysis_note_name = os.path.splitext(os.path.basename(paths["analysis"]["vault_path"]))[0]

    card_sections = [
        ("02_话题库", "话题", "## 2. 话题"),
        ("03_选题库", "选题", "## 3. 选题"),
        ("04_结构库", "结构", "## 7. 内容结构"),
        ("05_金句库", "金句", "## 8. 金句表达"),
        ("06_剪辑风格库", "剪辑风格", "## 9. 剪辑风格"),
    ]
    for folder, label, marker in card_sections:
        card_type = {
            "话题": "topic_card",
            "选题": "angle_card",
            "结构": "structure_card",
            "金句": "quote_card",
            "剪辑风格": "editing_style_card",
        }.get(label, "knowledge_card")
        card_body = frontmatter(
            {
                "title": f"{label}卡片 - {title}",
                "type": card_type,
                "status": "active",
                "source_note": analysis_note_name,
                "platform": case.platform,
                "source_url": case.url,
                "created": created,
            },
            ["内容运营", "知识卡片", label, f"平台/{safe_filename(case.platform, '未填')}"],
        )
        body = f"{card_body}# {label}卡片 - {title}\n\n来源: [[{analysis_note_name}]]\n\n{extract_section(analysis, marker)}"
        paths[label] = write_obsidian_note(folder, title, body)
    if case.video_package:
        try:
            with open(case.video_package.manifest_path, encoding="utf-8") as f:
                manifest = f.read()
            paths["video_manifest"] = write_obsidian_note("09_视频理解包", title, manifest)
        except OSError:
            pass
    if product_match:
        body = frontmatter(
            {
                "title": f"产品匹配 - {title}",
                "type": "product_match",
                "status": "active",
                "source_note": analysis_note_name,
                "platform": case.platform,
                "source_url": case.url,
                "created": created,
            },
            ["内容运营", "产品匹配", f"平台/{safe_filename(case.platform, '未填')}"],
        )
        paths["product_match"] = write_obsidian_note("10_产品匹配", title, body + product_match)
    return paths


def extract_section(markdown: str, marker: str) -> str:
    index = markdown.find(marker)
    if index < 0:
        return "未提取到对应段落。"
    rest = markdown[index:]
    next_match = re.search(r"\n## \d+\. ", rest[len(marker):])
    if not next_match:
        return rest.strip()
    end = len(marker) + next_match.start()
    return rest[:end].strip()


def script_prompt(case: UploadedCase, analysis: str, product_match: str, product_library: str, script_goal: str) -> str:
    return f"""你是内容运营编导。请基于爆款分析和产品库，生成一条可进入生产 loop 的新脚本。

要求:
1. 不是搬运原爆款，而是迁移它的结构、情绪、金句和剪辑风格。
2. 产品必须自然进入，不要硬广。
3. 输出先给产品承接判断，再给生产表。
4. 生产表必须使用这些列:
脚本｜镜头｜状态｜时长(秒)｜场景｜景别｜运镜｜画面｜动作神情｜口播稿｜字幕｜分镜图｜分镜图链接｜视频链接

【脚本目标】
{script_goal or "基于爆款结构生成一条适合产品转化的短视频脚本"}

【爆款素材】
- 标题: {case.title}
- 平台: {case.platform}
- 链接: {case.url}
- 数据: {case.metrics}
- 人工选择原因: {case.reason}

【爆款分析】
{analysis[:6000]}

【产品匹配报告】
{product_match[:3000] if product_match else "未提供，请自行从产品库中匹配。"}

【产品库】
{product_library}

请输出 Markdown:

# 内容运营脚本

## 1. 产品承接判断
- 推荐产品:
- 为什么适合这个爆款结构:
- 可借用的爆款元素:
- 不能照搬的部分:
- 产品自然出现的位置:
- 必须出现的视觉证据:
- 合规替代表达:

## 2. 口播稿

## 3. 生产 loop 表
用 Markdown 表格输出，列名严格为:
脚本｜镜头｜状态｜时长(秒)｜场景｜景别｜运镜｜画面｜动作神情｜口播稿｜字幕｜分镜图｜分镜图链接｜视频链接
"""


def generate_script(case: UploadedCase, analysis: str, script_goal: str, product_match: str = "") -> str:
    return llm.call_text(
        "??????????????????????",
        prompt_builder.build_script_prompt(case, analysis, product_match, script_goal),
        max_tokens=5200,
    )

def candidate_prompt(case: UploadedCase, analysis: str, product_match: str, script_goal: str, styles: list[str]) -> str:
    return f"""你是内容运营脚本主编。请基于爆款分析、产品匹配报告和产品库，一次生成多个脚本候选。

必须输出严格 JSON，不要 Markdown 代码块。

每个候选都要有:
- id
- style
- title
- hook
- product
- audience
- risk_note
- reason_to_pick
- oral_script
- loop_rows

loop_rows 每行必须包含:
脚本, 镜头, 状态, 时长(秒), 场景, 景别, 运镜, 画面, 动作神情, 口播稿, 字幕, 分镜图, 分镜图链接, 视频链接

【候选生成硬约束】
1. 默认保留爆款分析里的 Source Prototype Lock，不要擅自替换职业身份、场景和内容外壳。
2. 如果原型是空姐晚班 vlog，候选可以换风格，但人物仍应是空姐/民航人/航班晚班场景；不得默认迁移成办公室、北漂、普通白领、测评或避坑。
3. 产品植入必须服务于原型场景：晚班、超长待机、职场女性、自律补给、出勤前后，而不是强行进入养生科普。
4. 只有 script_goal 明确要求“迁移到其他职业/人群”时，才允许换职业外壳。
5. loop_rows 的口播稿必须能连成一条完整口播，不允许只写画面说明。

候选风格:
{", ".join(styles)}

【脚本目标】
{script_goal or "基于爆款结构生成多版本短视频脚本候选"}

【爆款素材】
- 标题: {case.title}
- 平台: {case.platform}
- 链接: {case.url}
- 数据: {case.metrics}
- 人工选择原因: {case.reason}

【爆款分析】
{analysis[:5500]}

【产品匹配报告】
{product_match[:3500]}

【产品库】
{read_product_library(8000)}

JSON 格式:
{{
  "candidates": [
    {{
      "id": "C01",
      "style": "猎奇",
      "title": "",
      "hook": "",
      "product": "",
      "audience": "",
      "risk_note": "",
      "reason_to_pick": "",
      "oral_script": "",
      "loop_rows": [
        {{
          "脚本": "C01",
          "镜头": "镜头1",
          "状态": "待生产",
          "时长(秒)": "3",
          "场景": "",
          "景别": "",
          "运镜": "",
          "画面": "",
          "动作神情": "",
          "口播稿": "",
          "字幕": "",
          "分镜图": "",
          "分镜图链接": "",
          "视频链接": ""
        }}
      ]
    }}
  ]
}}
"""


def clean_json_text(text: str) -> str:
    clean = text.strip()
    if clean.startswith("```"):
        clean = clean.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    start = clean.find("{")
    if start > 0:
        clean = clean[start:]
    if clean.startswith("{"):
        depth = 0
        in_string = False
        escaped = False
        for index, char in enumerate(clean):
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return clean[: index + 1]
    return clean


LEGACY_LOOP_COLUMN_ALIASES = {
    "脚本": ["脚本", "鑴氭湰"],
    "镜头": ["镜头", "闀滃ご"],
    "状态": ["状态", "鐘舵€?", "鐘舵€"],
    "时长(秒)": ["时长(秒)", "鏃堕暱(绉?", "鏃堕暱(绉"],
    "场景": ["场景", "鍦烘櫙"],
    "景别": ["景别", "鏅埆"],
    "运镜": ["运镜", "杩愰暅"],
    "画面": ["画面", "鐢婚潰"],
    "动作神情": ["动作神情", "鍔ㄤ綔绁炴儏"],
    "口播稿": ["口播稿", "鍙ｆ挱绋?", "鍙ｆ挱绋"],
    "字幕": ["字幕", "瀛楀箷"],
    "分镜图": ["分镜图", "鍒嗛暅鍥?", "鍒嗛暅鍥"],
    "分镜图链接": ["分镜图链接", "鍒嗛暅鍥鹃摼鎺?", "鍒嗛暅鍥鹃摼鎺"],
    "视频链接": ["视频链接", "瑙嗛閾炬帴"],
}


def normalize_loop_row(row: dict[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for column in LOOP_COLUMNS:
        value = ""
        for alias in LEGACY_LOOP_COLUMN_ALIASES.get(column, [column]):
            if alias in row and row.get(alias) is not None:
                value = str(row.get(alias, ""))
                break
        normalized[column] = value
    return normalized


def normalize_candidate_rows(data: dict[str, Any]) -> dict[str, Any]:
    for candidate in data.get("candidates", []) if isinstance(data.get("candidates"), list) else []:
        rows = candidate.get("loop_rows")
        if isinstance(rows, list):
            candidate["loop_rows"] = [normalize_loop_row(row) for row in rows if isinstance(row, dict)]
    return data


def generate_candidates(case: UploadedCase, analysis: str, product_match: str, script_goal: str, styles: list[str] | None = None) -> dict[str, Any]:
    selected_styles = styles or SCRIPT_STYLES
    raw = llm.call_text(
        "???????????????????????",
        prompt_builder.build_candidate_prompt(case, analysis, product_match, script_goal, selected_styles),
        max_tokens=7000,
    )
    try:
        data = json.loads(clean_json_text(raw))
    except json.JSONDecodeError:
        data = {"candidates": [], "raw": raw}
    return normalize_candidate_rows(data)

def save_candidates(title: str, candidates: dict[str, Any]) -> dict[str, str]:
    today_dir = os.path.join(SETTINGS.output_dir, "candidates", time.strftime("%Y-%m-%d"))
    os.makedirs(today_dir, exist_ok=True)
    base = f"{time.strftime('%H%M%S')}_{safe_filename(title or 'candidates')}"
    json_path = os.path.join(today_dir, f"{base}.json")
    md_path = os.path.join(today_dir, f"{base}.md")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(candidates, f, ensure_ascii=False, indent=2)
    markdown = candidates_to_markdown(title, candidates)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown)
    note = write_obsidian_note("07_脚本产出", f"候选池_{title}", markdown)
    return {"json": json_path, "markdown": md_path, "obsidian": note["local_path"], "obsidian_vault_path": note["vault_path"], "obsidian_open_uri": note["open_uri"]}


def candidates_to_markdown(title: str, data: dict[str, Any]) -> str:
    lines = [
        frontmatter(
            {"title": f"脚本候选池 - {title}", "type": "script_candidate_pool", "status": "candidate", "created": time.strftime("%Y-%m-%d %H:%M:%S")},
            ["内容运营", "脚本候选池"],
        ),
        f"# 脚本候选池 - {title}",
        "",
    ]
    for item in data.get("candidates", []):
        lines.extend(
            [
                f"## {item.get('id', '')} {item.get('style', '')} - {item.get('title', '')}",
                "",
                f"- Hook: {item.get('hook', '')}",
                f"- 产品: {item.get('product', '')}",
                f"- 受众: {item.get('audience', '')}",
                f"- 选择理由: {item.get('reason_to_pick', '')}",
                f"- 风险: {item.get('risk_note', '')}",
                "",
                "### 口播",
                item.get("oral_script", ""),
                "",
            ]
        )
    if data.get("raw"):
        lines.extend(["## 原始输出", "", data["raw"]])
    return "\n".join(lines).strip() + "\n"


def loop_from_candidate(candidate: dict[str, Any], title: str) -> dict[str, Any]:
    rows = []
    for row in candidate.get("loop_rows", []):
        rows.append(normalize_loop_row(row))
    if not rows:
        rows = [{column: "" for column in LOOP_COLUMNS}]
    today_dir = os.path.join(SETTINGS.output_dir, time.strftime("%Y-%m-%d"))
    os.makedirs(today_dir, exist_ok=True)
    base = f"{time.strftime('%H%M%S')}_{safe_filename(title or candidate.get('title') or 'candidate_loop')}"
    csv_path = os.path.join(today_dir, f"{base}_loop.csv")
    xlsx_path = os.path.join(today_dir, f"{base}_loop.xlsx")
    write_loop_csv(csv_path, rows)
    write_loop_xlsx(xlsx_path, rows)
    external = sync_loop_files(csv_path, xlsx_path)
    job = loop_engine.create_job(
        title=title or candidate.get("title") or "candidate_loop",
        rows=rows,
        source_paths={"csv": csv_path, "xlsx": xlsx_path, **external},
        candidate=candidate,
        metadata={"source": "candidate_loop"},
    )
    return {"csv": csv_path, "xlsx": xlsx_path, **external, "loop_job": job}


def sync_loop_files(csv_path: str, xlsx_path: str) -> dict[str, str]:
    handoff_dir = loop_engine.handoff_dir()
    os.makedirs(handoff_dir, exist_ok=True)
    result: dict[str, str] = {}
    for label, path in (("external_csv", csv_path), ("external_xlsx", xlsx_path)):
        if path and os.path.exists(path):
            target = os.path.join(handoff_dir, os.path.basename(path))
            shutil.copyfile(path, target)
            result[label] = target
    return result


def feedback_prompt(data: dict[str, Any]) -> str:
    evaluation = evaluation_engine.evaluate(data)
    return prompt_builder.build_feedback_prompt(data, evaluation)

def record_feedback(data: dict[str, Any]) -> dict[str, str]:
    today_dir = os.path.join(SETTINGS.output_dir, "feedback", time.strftime("%Y-%m-%d"))
    os.makedirs(today_dir, exist_ok=True)
    raw_path = os.path.join(today_dir, "feedback.jsonl")
    with open(raw_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({**data, "created": time.strftime("%Y-%m-%d %H:%M:%S")}, ensure_ascii=False) + "\n")
    review = llm.call_text("你是短视频内容运营复盘负责人。", feedback_prompt(data), max_tokens=2600)
    note = frontmatter(
        {
            "title": f"数据复盘 - {data.get('title', '未命名')}",
            "type": "performance_review",
            "status": "reviewed",
            "platform": data.get("platform", ""),
            "product": data.get("product", ""),
            "candidate_id": data.get("candidate_id", ""),
            "style": data.get("style", ""),
            "template": data.get("template", ""),
            "video_url": data.get("video_url", ""),
            "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
        ["内容运营", "数据复盘", f"平台/{safe_filename(data.get('platform', ''), '未填')}", f"产品/{safe_filename(data.get('product', ''), '未填')}"],
    ) + review
    obs = write_obsidian_note("11_数据复盘", data.get("title", "发布数据复盘"), note)
    return {"raw_jsonl": raw_path, "review": review, "obsidian": obs["local_path"], "obsidian_vault_path": obs["vault_path"], "obsidian_open_uri": obs["open_uri"]}


def save_script_and_loop(title: str, script_markdown: str) -> dict[str, Any]:
    script_path = write_obsidian_note("07_脚本产出", title or "运营脚本", script_markdown)
    rows = parse_loop_markdown_table(script_markdown)
    today_dir = os.path.join(SETTINGS.output_dir, time.strftime("%Y-%m-%d"))
    os.makedirs(today_dir, exist_ok=True)
    base = f"{time.strftime('%H%M%S')}_{safe_filename(title or 'loop')}"
    csv_path = os.path.join(today_dir, f"{base}_loop.csv")
    xlsx_path = os.path.join(today_dir, f"{base}_loop.xlsx")
    write_loop_csv(csv_path, rows)
    write_loop_xlsx(xlsx_path, rows)
    external = sync_loop_files(csv_path, xlsx_path)
    loop_vault_path = f"08_loop生产/{os.path.basename(csv_path)}"
    loop_local_path = os.path.join(SETTINGS.obsidian_dir, "08_loop生产", os.path.basename(csv_path))
    os.makedirs(os.path.dirname(loop_local_path), exist_ok=True)
    shutil.copyfile(csv_path, loop_local_path)
    job = loop_engine.create_job(
        title=title or "运营脚本",
        rows=rows,
        source_paths={"csv": csv_path, "xlsx": xlsx_path, **external, "obsidian_csv": loop_local_path},
        metadata={"source": "formal_script", "script_path": script_path["local_path"]},
    )
    return {
        "script": script_path["local_path"],
        "script_vault_path": script_path["vault_path"],
        "script_open_uri": script_path["open_uri"],
        "script_write_mode": script_path["mode"],
        "script_write_error": script_path["error"],
        "loop_vault_path": loop_vault_path,
        "loop_local_path": loop_local_path,
        "csv": csv_path,
        "xlsx": xlsx_path,
        "loop_job": job,
        **external,
    }


def parse_loop_markdown_table(markdown: str) -> list[dict[str, str]]:
    lines = [line.strip() for line in markdown.splitlines() if line.strip().startswith("|")]
    rows: list[dict[str, str]] = []
    header: list[str] = []
    for line in lines:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells:
            continue
        non_empty_cells = [cell.replace(" ", "") for cell in cells if cell.strip()]
        if non_empty_cells and all(set(cell) <= {"-", ":"} for cell in non_empty_cells):
            continue
        if _is_loop_header(cells):
            header = cells
            continue
        if not header and len(cells) >= len(LOOP_COLUMNS):
            header = LOOP_COLUMNS
            continue
        if not header:
            continue
        raw = dict(zip(header, cells))
        rows.append(normalize_loop_row(raw))
    if rows:
        return rows
    return [{column: "" for column in LOOP_COLUMNS}]


def _is_loop_header(cells: list[str]) -> bool:
    joined = "|".join(cells)
    if "??" in joined and "??" in joined:
        return True
    return "???" in joined and "???" in joined

def write_loop_csv(path: str, rows: list[dict[str, str]]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOOP_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_loop_xlsx(path: str, rows: list[dict[str, str]]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "loop"
    ws.append(LOOP_COLUMNS)
    for row in rows:
        ws.append([row.get(column, "") for column in LOOP_COLUMNS])
    for col in ws.columns:
        letter = col[0].column_letter
        ws.column_dimensions[letter].width = 18
    wb.save(path)


def build_case_summary(case: UploadedCase, analysis: str = "", product_match: str = "") -> str:
    return f"""标题: {case.title}
平台: {case.platform}
链接: {case.url}
数据: {case.metrics}
销量/成交: {case.sales}
人工选择原因: {case.reason}
口播/字幕: {(case.transcript or '')[:1200]}
评论区: {(case.comments or '')[:1200]}
备注: {(case.notes or '')[:800]}

爆款分析摘要:
{analysis[:1800]}

产品匹配摘要:
{product_match[:1200]}
"""


def build_operating_context(case: UploadedCase, analysis: str = "", product_match: str = "", goal: str = "") -> dict[str, Any]:
    comment_insight = comment_engine.analyze_comments(case.comments, case.title, case.platform)
    context = context_engine.build_context(
        goal=goal,
        product=extract_section(product_match, "## 2.")[:400] if product_match else "",
        platform=case.platform,
        audience=(extract_section(analysis, "## 4.")[:400] if analysis else "") + "\n" + json.dumps(comment_insight, ensure_ascii=False)[:800],
    )
    plan = planning_engine.build_plan(build_case_summary(case, analysis, product_match), context, goal)
    path = memory_engine.append_jsonl(
        "planning",
        {
            "case": {
                "title": case.title,
                "platform": case.platform,
                "url": case.url,
                "metrics": case.metrics,
            },
            "goal": goal,
            "comment_insight": comment_insight,
            "plan": plan,
        },
    )
    return {
        "context": {
            "context_note": context.context_note,
            "has_products": bool(context.product_library.strip()),
            "has_patterns": bool(context.patterns.strip()),
            "has_strategies": bool(context.strategies.strip()),
        },
        "prompt_context": context_engine.to_prompt_block(context),
        "plan": plan,
        "comment_insight": comment_insight,
        "memory_event": path,
    }


def evaluate_and_evolve(data: dict[str, Any], review: str = "") -> dict[str, Any]:
    evaluation = evaluation_engine.evaluate(data)
    evolution = evolution_engine.update_from_feedback(data, evaluation, review)
    return {"evaluation": evaluation, "evolution": evolution}
