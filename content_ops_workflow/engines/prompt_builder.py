from __future__ import annotations

from typing import Any, Protocol

from content_ops_workflow.engines import context_engine, knowledge_engine


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

SCRIPT_STYLES = ["猎奇", "反差", "反反差", "共鸣", "避坑", "教程", "生活仪式"]


class CaseLike(Protocol):
    title: str
    platform: str
    url: str
    metrics: str
    reason: str
    transcript: str
    notes: str
    sales: str
    comments: str


def case_block(case: CaseLike) -> str:
    return f"""【素材信息】
- 标题: {case.title or "未填写"}
- 平台: {case.platform or "未填写"}
- 链接: {case.url or "未填写"}
- 数据: {case.metrics or "未填写"}
- 销量/成交: {getattr(case, "sales", "") or "未填写"}
- 人工选择原因: {case.reason or "未填写"}
- 口播/字幕: {(case.transcript or "未提供")[:3000]}
- 评论区: {(getattr(case, "comments", "") or "未提供")[:3000]}
- 备注: {(case.notes or "无")[:1500]}
"""


def build_candidate_prompt(case: CaseLike, analysis: str, product_match: str, script_goal: str, styles: list[str] | None = None) -> str:
    selected_styles = styles or SCRIPT_STYLES
    ctx = context_engine.build_context(
        goal=script_goal,
        product=product_match[:800],
        platform=case.platform,
        audience=analysis[:800],
    )
    return f"""你是内容运营 Prompt Builder。请基于爆款分析、产品承接和已验证 Pattern，生成多风格脚本候选。

必须输出严格 JSON，不要 Markdown，不要代码块。

硬约束：
1. 默认保留 Source Prototype Lock，不擅自替换职业身份、场景和内容外壳。
2. 如果原型是空姐/晚班/超长待机/职场女性/vlog，就围绕这个原型迁移；除非目标明确要求换人群。
3. 产品植入必须服务原场景，不要强行变成养生科普或避坑测评。
4. 每个候选先给完整口播稿，再给 loop_rows。
5. loop_rows 的口播稿列必须能连成完整口播，不允许只写画面说明。
6. loop_rows 每行必须包含这些列：{", ".join(LOOP_COLUMNS)}

候选风格：{", ".join(selected_styles)}

输出 JSON 格式：
{{
  "candidates": [
    {{
      "id": "C01",
      "style": "反差",
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

{case_block(case)}

【脚本目标】
{script_goal or "基于爆款结构生成多版本短视频脚本候选"}

【爆款分析】
{analysis[:5500]}

【产品承接】
{product_match[:3500]}

{context_engine.to_prompt_block(ctx)}
"""


def build_script_prompt(case: CaseLike, analysis: str, product_match: str, script_goal: str) -> str:
    ctx = context_engine.build_context(goal=script_goal, product=product_match[:800], platform=case.platform, audience=analysis[:800])
    return f"""你是内容运营 Workflow 的脚本生产器。你的职责是执行 Planning，不重新发散。

输出 Markdown，结构必须为：
# 内容运营脚本
## 1. 产品承接判断
## 2. 完整口播稿
## 3. 生产 loop 表

生产 loop 表必须使用 Markdown 表格，列名严格为：
{ " | ".join(LOOP_COLUMNS) }

要求：
1. 先给完整口播稿，再拆成生产表。
2. 表格里的“口播稿”列必须拼起来等于完整口播主线。
3. 产品自然出现，不硬广。
4. 必须保留爆款原型的场景、情绪、结构和节奏。
5. 不确定的信息标注“信息不足”，不要编造。

{case_block(case)}

【脚本目标】
{script_goal or "生成可进入 loop 的正式脚本"}

【爆款分析】
{analysis[:6000]}

【产品承接】
{product_match[:3500]}

{context_engine.to_prompt_block(ctx)}
"""


def build_feedback_prompt(data: dict[str, Any], evaluation: dict[str, Any] | None = None) -> str:
    return f"""你是 Evaluation Engine 的解释器。请基于发布数据和机器评分，输出可沉淀的实验结论。

【发布数据】
- 标题: {data.get("title", "")}
- 平台: {data.get("platform", "")}
- 视频链接: {data.get("video_url", "")}
- 候选ID/风格: {data.get("candidate_id", "")} / {data.get("style", "")}
- 产品: {data.get("product", "")}
- 模板: {data.get("template", "")}
- 受众: {data.get("audience", "")}
- 播放: {data.get("views", "")}
- 点赞: {data.get("likes", "")}
- 评论: {data.get("comments", "")}
- 收藏: {data.get("saves", "")}
- 转发: {data.get("shares", "")}
- 完播率: {data.get("completion_rate", "")}
- 转化/询单: {data.get("conversion", "")}
- 销量/成交: {data.get("sales", "")}
- 人工备注: {data.get("notes", "")}

【机器评分】
{evaluation or "未提供"}

请输出 Markdown：
# 发布数据复盘
## 1. Score 解释
## 2. Pattern 是否成立
## 3. 产品承接表现
## 4. 受众反馈
## 5. 下一轮建议
"""
