from __future__ import annotations

from dataclasses import asdict, dataclass

from content_ops_workflow.engines import knowledge_engine, memory_engine


@dataclass(frozen=True)
class TaskContext:
    product_library: str
    template_library: str
    brand_platform_rules: str
    patterns: str
    strategies: str
    context_note: str


def build_context(goal: str = "", product: str = "", platform: str = "", audience: str = "") -> TaskContext:
    note = "\n".join(
        line
        for line in [
            f"目标: {goal}" if goal else "",
            f"产品: {product}" if product else "",
            f"平台: {platform}" if platform else "",
            f"受众: {audience}" if audience else "",
        ]
        if line
    )
    return TaskContext(
        product_library=knowledge_engine.read_product_library(),
        template_library=knowledge_engine.read_template_library(),
        brand_platform_rules=knowledge_engine.read_brand_and_platform(),
        patterns=memory_engine.load_patterns(),
        strategies=memory_engine.load_strategies(),
        context_note=note or "未提供额外任务目标。",
    )


def to_prompt_block(context: TaskContext) -> str:
    data = asdict(context)
    return f"""【任务上下文】
{data["context_note"]}

【产品知识】
{data["product_library"]}

【爆款结构模板库】
{data["template_library"]}

【品牌规范 / 平台规则】
{data["brand_platform_rules"]}

【已验证 Pattern】
{data["patterns"] or "暂无已验证 Pattern。"}

【历史 Strategy】
{data["strategies"] or "暂无历史 Strategy。"}
"""

