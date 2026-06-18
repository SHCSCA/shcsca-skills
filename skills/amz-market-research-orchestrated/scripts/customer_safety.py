#!/usr/bin/env python3
"""Customer-facing redaction and view-model safety helpers."""

from __future__ import annotations

import html
import re
from typing import Any


TECHNICAL_DISPLAY_KEYS = {"source_id", "source_ids", "provider", "tool", "raw_path", "path", "asin", "product_id", "video_id"}
CLIENT_VIEW_BLOCKED_KEYS = {"source_id", "source_ids", "used_source_ids", "provider", "tool", "raw_path", "path", "asin", "product_id", "video_id", "method_id"}
CLIENT_VIEW_ALLOWED_ASIN_KEYS = {
    "reference_asin",
    "reference_asins",
    "competitor_asin",
    "competitor_asins",
    "target_asin",
    "target_asins",
    "benchmark_asin",
    "benchmark_asins",
}
REVIEW_TEXT_KEYS = {"title", "text", "content", "body", "comment"}
GENERIC_TECHNICAL_VALUES = {"api", "us", "cn", "uk", "eu", "user"}

CUSTOMER_LABEL_REPLACEMENTS = [
    ("ready_for_normalization", "可用于方向判断，需供应链复核"),
    ("low_confidence_watch", "证据不足，建议观察"),
    ("amz-market-research-orchestrated", "市场研究报告"),
    ("three-report-index-v2", "三合一报告入口"),
    ("lifecycle-strategy-report-v2", "生命周期策略报告"),
    ("demand-gap-report-v2", "需求机会报告"),
    ("market-depth-report-v2", "市场深度报告"),
    ("ProductId", "内容商品记录"),
    ("collect_sorftime_product_enrichment.py", "产品详情补充采集"),
    ("product_detail", "竞品详情信息"),
    ("product_trend", "月度趋势数据"),
    ("category_trend", "类目月度趋势数据"),
    ("运行 产品详情补充采集 对核心 参考竞品 补充产品详情维度 补充图片数据；若多 参考竞品 仍为空，保留诊断并记录 市场数据 图片维度缺口。", "补充核心竞品主图；若多个参考竞品仍无可展示图片，保留图片缺口诊断。"),
    ("运行 产品详情补充采集 对核心 参考竞品 补充竞品详情信息 补充图片数据；若多 参考竞品 仍为空，保留诊断并记录 市场数据 图片维度缺口。", "补充核心竞品主图；若多个参考竞品仍无可展示图片，保留图片缺口诊断。"),
    ("调用 产品详情维度", "补充竞品详情信息"),
    ("补充产品详情维度 补充图片数据", "补充核心竞品主图数据"),
    ("补采图片字段", "补充图片数据"),
    ("竞品记录", "竞品"),
    ("StoreName", "供应商名称"),
    ("Photo", "图片记录"),
    ("Price", "价格"),
    ("used_source_ids", "证据强度"),
    ("source_ids", "证据强度"),
    ("source_id", "证据强度"),
    ("Product ID", "产品角色"),
    ("product_id", "产品角色"),
    ("raw_path", "内部审计记录"),
    ("provider", "数据覆盖"),
    ("tool", "分析方法"),
    ("method_id", "分析方法"),
    ("asin", "参考竞品"),
    ("Sorftime", "市场数据"),
    ("Firecrawl", "公开网页补充"),
    ("sorftime", "市场数据"),
    ("firecrawl", "公开网页补充"),
    ("Data Pack", "分析底稿"),
    ("data/raw", "内部审计记录"),
    ("数据血缘", "证据说明"),
    ("来源", "数据覆盖"),
    ("Provider Coverage", "数据覆盖"),
    ("lineage", "审计链路"),
    ("英文标题", "页面表达归纳"),
    ("Review", "评论"),
    ("reviews", "评论"),
    ("products", "竞品"),
    ("sources", "证据记录"),
]

STATUS_TEXT_REPLACEMENTS = [
    ("success", "已通过"),
    ("warning", "需复核"),
]

CUSTOMER_TEXT_REPLACEMENTS = [
    ("Positive/Neutral/Negative 评论", "正向/中性/负向评论"),
    ("Positive / Neutral / Negative 评论", "正向/中性/负向评论"),
    ("Positive Reviews", "高星评论证据"),
    ("Negative Reviews", "低星评论证据"),
    ("Positive", "正向评论"),
    ("Neutral", "中性评论"),
    ("Negative", "负向评论"),
]

TOOL_DIMENSION_LABELS = {
    "product_detail": "产品详情维度",
    "product_trend": "趋势维度",
    "product_variations": "变体维度",
    "tiktok_product_detail": "TikTok 商品详情维度",
    "tiktok_product_search": "TikTok 商品搜索维度",
    "ali1688_similar_product": "1688 相似货源维度",
}


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", "" if value is None else str(value)).strip()


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def truncate(value: Any, limit: int = 120) -> str:
    text = clean(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def customer_safe_technical_failure_text(text: str) -> str:
    lower = text.casefold()
    if "returned no rows" not in lower and "no rows for" not in lower:
        return text
    dimensions: list[str] = []
    for raw, label in TOOL_DIMENSION_LABELS.items():
        if raw.casefold() in lower and label not in dimensions:
            dimensions.append(label)
    dimension_text = "、".join(dimensions) if dimensions else "部分数据维度"
    if "amazon" in lower or "asin" in lower or "参考竞品" in text:
        return f"{dimension_text}本轮未返回可验证结果，不能用于页面事实承诺；需要更换参考竞品或重新调用对应维度。"
    if "tiktok" in lower:
        return f"{dimension_text}本轮未返回可验证结果，不能用于内容趋势结论；需要更换关键词或重新调用对应维度。"
    return f"{dimension_text}本轮未返回可验证结果，不能用于客户版结论；需要补采后重新生成。"


def has_cjk(value: Any) -> bool:
    return re.search(r"[\u4e00-\u9fff]", str(value or "")) is not None


def collect_technical_values(value: Any, key: str | None = None) -> set[str]:
    values: set[str] = set()
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            values.update(collect_technical_values(child_value, str(child_key)))
    elif isinstance(value, list):
        for item in value:
            values.update(collect_technical_values(item, key))
    elif key in TECHNICAL_DISPLAY_KEYS and value not in (None, ""):
        text = str(value).strip()
        if len(text) >= 3 and text.casefold() not in GENERIC_TECHNICAL_VALUES:
            values.add(text)
    return values


def raw_english_review_values(data_pack: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for review in data_pack.get("reviews") or []:
        if not isinstance(review, dict):
            continue
        for key in REVIEW_TEXT_KEYS:
            text = clean(review.get(key))
            if len(text) < 8 or has_cjk(text):
                continue
            words = re.findall(r"[A-Za-z][A-Za-z']+", text)
            if len(words) >= 2:
                values.add(text)
    return values


def review_redaction_needles(text: str) -> set[str]:
    needles = {text, esc(text)}
    for limit in (60, 70, 72, 80, 90, 100, 120, 180, 220):
        if len(text) > limit:
            shortened = truncate(text, limit)
            needles.add(shortened)
            needles.add(esc(shortened))
    return {needle for needle in needles if len(needle) >= 8}


def apply_customer_label_replacements(text: str) -> str:
    for old, new in CUSTOMER_LABEL_REPLACEMENTS:
        if re.fullmatch(r"[A-Za-z0-9_ /-]+", old):
            text = re.sub(rf"(?<![A-Za-z0-9_]){re.escape(old)}(?![A-Za-z0-9_])", new, text)
        else:
            text = text.replace(old, new)
    return text


def replace_customer_labels_in_text_nodes(html_doc: str) -> str:
    parts = re.split(r"(<[^>]+>)", html_doc)
    for idx, part in enumerate(parts):
        if idx % 2 == 1:
            continue
        parts[idx] = apply_customer_label_replacements(part)
    return "".join(parts)


def redact_customer_html(html_doc: str, data_pack: dict[str, Any]) -> str:
    preserved_asins: dict[str, str] = {}
    preserved_review_excerpts: dict[str, str] = {}

    html_doc = re.sub(
        r"\bdata-report-style=[\"'](?:three-report-index-v2|market-depth-report-v2|lifecycle-strategy-report-v2|demand-gap-report-v2)[\"']",
        "",
        html_doc,
        flags=re.IGNORECASE,
    )

    def preserve_asin(match: re.Match[str]) -> str:
        token = f"__AMZ_KEEP_A_{len(preserved_asins)}__"
        preserved_asins[token] = match.group(0)
        return token

    html_doc = re.sub(
        r"<span\b(?=[^>]*\bdata-allow-asin=[\"'](?:benchmark-sniper|profit-model|competitor-table|demand-target-anchor|sku-reference)[\"'])[^>]*>\s*B0[A-Z0-9]{8}\s*</span>",
        preserve_asin,
        html_doc,
        flags=re.IGNORECASE,
    )

    def preserve_review_excerpt(match: re.Match[str]) -> str:
        token = f"__AMZ_ALLOWED_REVIEW_EXCERPT_{len(preserved_review_excerpts)}__"
        preserved_review_excerpts[token] = match.group(0)
        return token

    html_doc = re.sub(
        r"<([a-z0-9]+)\b(?=[^>]*\bdata-allow-english-review=[\"']short[\"'])[^>]*>.*?</\1>",
        preserve_review_excerpt,
        html_doc,
        flags=re.IGNORECASE | re.DOTALL,
    )

    html_doc = replace_customer_labels_in_text_nodes(html_doc)

    replacement_by_key = {
        "source_id": "高",
        "source_ids": "高",
        "provider": "数据覆盖",
        "tool": "分析方法",
        "raw_path": "内部审计记录",
        "path": "内部审计记录",
        "asin": "参考竞品",
        "product_id": "内容商品记录",
        "video_id": "内容记录",
    }

    def replace_value(value: Any, key: str | None = None) -> None:
        nonlocal html_doc
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                replace_value(child_value, str(child_key))
        elif isinstance(value, list):
            for item in value:
                replace_value(item, key)
        elif key in TECHNICAL_DISPLAY_KEYS and value not in (None, ""):
            text = str(value).strip()
            if len(text) < 3:
                return
            replacement = replacement_by_key.get(key or "", "证据记录")
            for needle in {text, esc(text)}:
                html_doc = html_doc.replace(needle, replacement)

    replace_value(data_pack)
    for review_text in raw_english_review_values(data_pack):
        for needle in review_redaction_needles(review_text):
            html_doc = html_doc.replace(needle, "中文化评论摘要")
    html_doc = re.sub(r"\bB0[A-Z0-9]{8}\b", "参考竞品", html_doc)
    html_doc = re.sub(r"\bsrc[_-][\w\u4e00-\u9fff-]+\b", "高", html_doc, flags=re.IGNORECASE)
    html_doc = re.sub(r"\bsf[_-][\w\u4e00-\u9fff-]+\b", "高", html_doc, flags=re.IGNORECASE)
    html_doc = re.sub(r"\bdata/raw/[^\s<>'\"]+", "内部审计记录", html_doc, flags=re.IGNORECASE)
    html_doc = re.sub(r"[A-Za-z]:\\[^\s<>'\"]+", "内部审计记录", html_doc)
    html_doc = html_doc.replace("证据强度: 高", "证据强度：高")
    html_doc = html_doc.replace("证据强度： 高", "证据强度：高")
    html_doc = html_doc.replace("数据数据覆盖", "数据覆盖")
    html_doc = html_doc.replace("数据来源", "数据覆盖")
    # Keep customer-safety text redaction from corrupting structural CSS classes.
    html_doc = html_doc.replace("cosmo-summary-item 数据覆盖", "cosmo-summary-item user")
    html_doc = html_doc.replace("cosmo-matrix-lane 数据覆盖-lane", "cosmo-matrix-lane user-lane")
    for token, preserved in preserved_asins.items():
        html_doc = html_doc.replace(token, preserved)
    for token, preserved in preserved_review_excerpts.items():
        html_doc = html_doc.replace(token, preserved)
    return html_doc


def customer_safe_asset_text(value: Any) -> str:
    text = clean(value)
    text = customer_safe_technical_failure_text(text)
    if "MCP returned Unauthorized" in text:
        text = text.replace("MCP returned Unauthorized, so public web evidence was collected with web search and marked separately.", "公开网页补充接口本轮未授权，已改用公开网页搜索结果并单独标注。")
    for old, new in CUSTOMER_TEXT_REPLACEMENTS:
        text = text.replace(old, new)
    text = apply_customer_label_replacements(text)
    for old, new in STATUS_TEXT_REPLACEMENTS:
        text = re.sub(rf"\b{re.escape(old)}\b", new, text)
    text = text.replace("ASIN", "参考竞品")
    replacements = {
        "竞品样本": "竞品",
        "市场样本": "市场数据",
        "评论样本": "评论记录",
        "产品样本": "产品记录",
        "供应样本": "供应记录",
        "样品": "实物",
        "样本": "数据记录",
        "补数": "复核",
        "打样": "实物测试",
        "待验证": "需核实",
        "待补": "需核实",
        "补 3-5": "增加 3-5",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\bB0[A-Z0-9]{8}\b", "参考竞品", text)
    text = re.sub(r"\bcollect_[\w\u4e00-\u9fff-]+\.py\b", "数据采集流程", text, flags=re.IGNORECASE)
    text = re.sub(r"\bsrc[_-][\w\u4e00-\u9fff-]+\b", "高", text, flags=re.IGNORECASE)
    text = re.sub(r"\bsf[_-][\w\u4e00-\u9fff-]+\b", "高", text, flags=re.IGNORECASE)
    text = re.sub(r"\bdata/raw/[^\s<>'\"]+", "内部审计记录", text, flags=re.IGNORECASE)
    text = re.sub(r"[A-Za-z]:\\[^\s<>'\"]+", "内部审计记录", text)
    text = text.replace("数据数据覆盖", "数据覆盖")
    text = text.replace("数据来源", "数据覆盖")
    return text


def client_safe_view_payload(value: Any, key: str | None = None) -> Any:
    if isinstance(value, dict):
        return {
            str(child_key): client_safe_view_payload(child, str(child_key))
            for child_key, child in value.items()
            if str(child_key) not in CLIENT_VIEW_BLOCKED_KEYS
        }
    if isinstance(value, list):
        return [client_safe_view_payload(item, key) for item in value]
    if isinstance(value, str):
        text = clean(value)
        if key in CLIENT_VIEW_ALLOWED_ASIN_KEYS:
            return text
        text = customer_safe_technical_failure_text(text)
        for old, new in CUSTOMER_TEXT_REPLACEMENTS:
            text = text.replace(old, new)
        text = apply_customer_label_replacements(text)
        for old, new in STATUS_TEXT_REPLACEMENTS:
            text = re.sub(rf"\b{re.escape(old)}\b", new, text)
        text = text.replace("ASIN", "参考竞品")
        text = re.sub(r"\bB0[A-Z0-9]{8}\b", "参考竞品", text)
        text = re.sub(r"\bcollect_[\w\u4e00-\u9fff-]+\.py\b", "数据采集流程", text, flags=re.IGNORECASE)
        text = re.sub(r"\b(?:src|sf)[_-][\w\u4e00-\u9fff-]+\b", "内部证据", text, flags=re.IGNORECASE)
        text = re.sub(r"\bdata/raw/[^\s<>'\"]+", "内部审计记录", text, flags=re.IGNORECASE)
        text = re.sub(r"[A-Za-z]:\\[^\s<>'\"]+", "内部审计记录", text)
        text = text.replace("数据数据覆盖", "数据覆盖")
        text = text.replace("数据来源", "数据覆盖")
        return text
    return value
