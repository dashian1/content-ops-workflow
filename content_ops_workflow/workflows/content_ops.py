from __future__ import annotations

import csv
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


LOOP_COLUMNS = [
    "脚本",
    "镜头",
    "状态",
    "时长(秒)",
    "场景",
    "景别",
    "运镜",
    "画面",
    "动作神情",
    "口播稿",
    "字幕",
    "分镜图",
    "分镜图链接",
    "视频链接",
]


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


def safe_filename(text: str, fallback: str = "content") -> str:
    text = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", (text or "").strip())
    text = re.sub(r"\s+", "_", text).strip("._ ")
    return text[:80] or fallback


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


def analyze_prompt(case: UploadedCase, product_library: str) -> str:
    return f"""你是内容运营负责人。请分析一条由人工筛选出来的爆款素材。

这一步不是简单总结内容，而是拆出可复用的运营资产。必须按下面字段输出 Markdown。

【素材信息】
- 标题: {case.title or "未填写"}
- 平台: {case.platform or "未填写"}
- 链接: {case.url or "未填写"}
- 数据: {case.metrics or "未填写"}
- 人工选择原因: {case.reason or "未填写"}
- 上传文件: {case.file_path or "无"}
- 口播/字幕: {case.transcript[:3000] if case.transcript else "未提供"}
- 备注: {case.notes[:1500] if case.notes else "无"}

【产品库摘要】
{product_library}

请输出:

# 爆款内容分析

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


def deposit_to_obsidian(case: UploadedCase, analysis: str) -> dict[str, dict[str, str]]:
    title = case.title or "爆款素材"
    frontmatter = [
        "---",
        f"title: {title}",
        f"platform: {case.platform}",
        f"url: {case.url}",
        f"metrics: {case.metrics}",
        f"created: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        "---",
        "",
    ]
    full = "\n".join(frontmatter) + analysis
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
        body = f"# {label}卡片 - {title}\n\n来源: [[{analysis_note_name}]]\n\n{extract_section(analysis, marker)}"
        paths[label] = write_obsidian_note(folder, title, body)
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


def script_prompt(case: UploadedCase, analysis: str, product_library: str, script_goal: str) -> str:
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


def generate_script(case: UploadedCase, analysis: str, script_goal: str) -> str:
    return llm.call_text(
        "你是短视频内容运营、产品转化编导和合规审稿。",
        script_prompt(case, analysis, read_product_library(), script_goal),
        max_tokens=5200,
    )


def save_script_and_loop(title: str, script_markdown: str) -> dict[str, str]:
    script_path = write_obsidian_note("07_脚本产出", title or "运营脚本", script_markdown)
    rows = parse_loop_markdown_table(script_markdown)
    today_dir = os.path.join(SETTINGS.output_dir, time.strftime("%Y-%m-%d"))
    os.makedirs(today_dir, exist_ok=True)
    base = f"{time.strftime('%H%M%S')}_{safe_filename(title or 'loop')}"
    csv_path = os.path.join(today_dir, f"{base}_loop.csv")
    xlsx_path = os.path.join(today_dir, f"{base}_loop.xlsx")
    write_loop_csv(csv_path, rows)
    write_loop_xlsx(xlsx_path, rows)
    loop_vault_path = f"08_loop生产/{os.path.basename(csv_path)}"
    loop_local_path = os.path.join(SETTINGS.obsidian_dir, "08_loop生产", os.path.basename(csv_path))
    os.makedirs(os.path.dirname(loop_local_path), exist_ok=True)
    shutil.copyfile(csv_path, loop_local_path)
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
    }


def parse_loop_markdown_table(markdown: str) -> list[dict[str, str]]:
    lines = [line.strip() for line in markdown.splitlines() if line.strip().startswith("|")]
    table_lines = [line for line in lines if "脚本" in line and "镜头" in line or len(line.split("|")) >= len(LOOP_COLUMNS) + 2]
    rows: list[dict[str, str]] = []
    header_seen = False
    for line in table_lines:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells:
            continue
        if all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        if "脚本" in cells and "镜头" in cells:
            header_seen = True
            continue
        if not header_seen:
            continue
        values = cells[: len(LOOP_COLUMNS)]
        values += [""] * (len(LOOP_COLUMNS) - len(values))
        rows.append(dict(zip(LOOP_COLUMNS, values)))
    if rows:
        return rows
    return [{column: "" for column in LOOP_COLUMNS}]


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
