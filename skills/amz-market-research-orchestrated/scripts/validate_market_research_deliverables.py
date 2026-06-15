#!/usr/bin/env python3
"""Validate amz-market-research-orchestrated v2 report artifacts."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from normalize_data_pack import (
    CABINET_CLOSET_HARD_NOISE,
    LIGHTING_KEYWORD_SIGNALS,
    LIGHTING_HARD_PRODUCT_NOISE,
    LIGHTING_NOISE_TOKENS,
    LIGHTING_PRODUCT_SIGNALS,
    category_dedupe_key,
    is_lighting_research,
    keyword_dedupe_key,
    normalized_key,
    product_dedupe_key,
    review_dedupe_key,
    supplier_dedupe_key,
    tiktok_author_dedupe_key,
    tiktok_product_dedupe_key,
    tiktok_video_dedupe_key,
    web_document_dedupe_key,
)
from check_data_readiness import assess as assess_data_readiness
from site_assets import COMPAT_INDEX_REPORT, HTML_BUNDLE_DIR, INTERACTIVE_FEATURES as SITE_INTERACTIVE_FEATURES, SITE_ASSETS

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATE_BASELINE_MANIFEST = SKILL_DIR / "references" / "template-baseline-manifest.json"
HTML_TEMPLATE_SLOT_CONTRACT = SKILL_DIR / "references" / "html-template-slot-contract.json"
CANONICAL_TEMPLATE_ASSETS = {
    "market-depth-report-v2": SKILL_DIR / "assets" / "canonical_templates" / "market-depth-reference.html",
    "lifecycle-strategy-report-v2": SKILL_DIR / "assets" / "canonical_templates" / "lifecycle-strategy-reference.html",
    "demand-gap-report-v2": SKILL_DIR / "assets" / "canonical_templates" / "demand-gap-reference.html",
}

BUNDLE_INDEX_REPORT = f"{HTML_BUNDLE_DIR}/report.html"
CHILD_SKILLS = {
    "market_depth": "child_skills/market-depth-report",
    "lifecycle_strategy": "child_skills/lifecycle-strategy-report",
    "demand_gap": "child_skills/demand-gap-report",
    "critic": "child_skills/market-research-critic",
}
INTERACTIVE_FEATURES = set(SITE_INTERACTIVE_FEATURES)

REQUIRED_FILES = [
    "data/data_pack.json",
    "data/normalized/normalized_data_pack.json",
    "data/normalized/data_readiness_report.json",
    "data/lineage.md",
    "report_brief.json",
    "analysis/analysis_plan.json",
    "analysis/cosmo_alexa_tags.json",
    "analysis/lifecycle_strategy.json",
    "analysis/market_depth_view.json",
    "analysis/lifecycle_strategy_view.json",
    "analysis/demand_gap_view.json",
    "analysis/critic_review.json",
    "analysis/refinement_plan.json",
    "analysis/critic_summary.md",
    "analysis/child_skill_invocation_log.json",
    COMPAT_INDEX_REPORT,
    BUNDLE_INDEX_REPORT,
    f"{HTML_BUNDLE_DIR}/market-depth-report.html",
    f"{HTML_BUNDLE_DIR}/lifecycle-strategy-report.html",
    f"{HTML_BUNDLE_DIR}/demand-gap-report.html",
    "output/report.md",
    "output/delivery_result.json",
    SITE_ASSETS["css"],
    SITE_ASSETS["js"],
    SITE_ASSETS["data"],
]

DATA_PACK_KEYS = [
    "sources",
    "products",
    "keywords",
    "categories",
    "reviews",
    "tiktok_products",
    "tiktok_videos",
    "suppliers",
    "web_documents",
    "data_gaps",
    "quality",
    "normalization",
]

ENTITY_LIST_KEYS = [
    "products",
    "keywords",
    "categories",
    "reviews",
    "tiktok_products",
    "tiktok_videos",
    "tiktok_authors",
    "suppliers",
    "web_documents",
]

SOURCE_REQUIRED_KEYS = ["source_id", "provider", "fetched_at", "confidence"]

BANNED_REPORT_PHRASES = [
    "Amazon官方销量",
    "亚马逊官方销量",
    "官方月销量",
    "官方销售额",
]

INDEX_STYLE_MARKER = "三合一报告入口"
MIN_KEYWORD_SAMPLE_COUNT = 1000

CHILD_REPORTS = {
    "market_depth": {
        "path": f"{HTML_BUNDLE_DIR}/market-depth-report.html",
        "filename": "market-depth-report.html",
        "style": "market-depth-report-v2",
        "sections": [
            "大盘仪表盘 · Market Dashboard",
            "COSMO + Alexa 标签识别 · 产品标签 × 用户标签",
            "Top 竞品全景扫描",
            "VOC 体验深潜 · 痛点 × 爽点雷达",
            "标杆竞品狙击拆解",
            "新品狙击企划 · Product Definition",
            "建议定价策略",
            "视觉与包装指导 · Visual Direction",
            "AI生图 Prompt · 可直接使用",
            "供应链成本估算 · 1688大盘数据",
        ],
        "terms": ["价格带销量分布图", "COSMO + Alexa", "15 类核心标签", "竞品狙击结论", "定价战略核心逻辑", "AI生图 Prompt", "供应链核心结论"],
    },
    "lifecycle_strategy": {
        "path": f"{HTML_BUNDLE_DIR}/lifecycle-strategy-report.html",
        "filename": "lifecycle-strategy-report.html",
        "style": "lifecycle-strategy-report-v2",
        "sections": [
            "战略仪表盘",
            "用户画像",
            "生命周期旅程",
            "四维拓品生态",
            "拓品方案池",
            "Bundle 策略",
            "30/60/90 天路线图",
            "风险矩阵",
            "市场验证摘要",
        ],
        "terms": ["SKU", "Bundle", "供应链", "复购", "AOV", "LTV"],
    },
    "demand_gap": {
        "path": f"{HTML_BUNDLE_DIR}/demand-gap-report.html",
        "filename": "demand-gap-report.html",
        "style": "demand-gap-report-v2",
        "sections": [
            "目标ASIN锚点",
            "决策看板",
            "市场痛点全景图（需求主题）",
            "满意度鸿沟",
            "KANO × JTBD",
            "用户原声",
            "需求优先级",
        ],
        "terms": ["KANO", "JTBD", "心智断层", "负面触发点", "转化机会"],
    },
}

SUBPROCESS_REPORT_KEYS = {"market_depth", "lifecycle_strategy", "demand_gap"}
SUBPROCESS_CHILD_KEYS = {*SUBPROCESS_REPORT_KEYS, "critic"}

COSMO_ALEXA_RELATION_TYPES = {
    "USED_FOR_FUNC",
    "USED_FOR_EVE",
    "USED_FOR_AUD",
    "CAPABLE_OF",
    "USED_TO",
    "USED_AS",
    "IS_A",
    "USED_ON",
    "USED_IN_LOC",
    "USED_IN_BODY",
    "USED_WITH",
    "USED_BY",
    "xINTERSTED_IN",
    "xIs_A",
    "xWANT",
}

LIFECYCLE_BANNED_FALLBACK_TERMS = [
    "备用与替换核心配件",
    "信任说明卡 + 快速启动卡",
    "场景化配件包",
    "清洁、保养与维护套装",
    "替换充电线与数据线套装",
    "户外感应灯 对标配件",
    "Type A",
    "Type B",
    "Type C",
    "Type D",
    "拓品路径A",
    "拓品路径B",
    "拓品路径C",
    "拓品路径D",
    "STEM 探索套装",
]
LIFECYCLE_STRATEGY_TYPE_KEYS = {
    "core_validation",
    "scenario_upgrade",
    "accessory_gap",
    "maintenance_repurchase",
}
LIFECYCLE_RAW_TYPE_CODES = {"A", "B", "C", "D"}

BUNDLE_INDEX_REQUIRED_LINKS = [spec["filename"] for spec in CHILD_REPORTS.values()]
COMPAT_INDEX_REQUIRED_LINKS = [f"html_reports/{spec['filename']}" for spec in CHILD_REPORTS.values()]

HTML_REQUIRED_CLASSES = [
    "kpi-grid",
    "evidence-table",
    "insight-table",
    "mini-chart",
]

STYLE_REQUIRED_DASHBOARD_CLASSES = {
    "lifecycle-strategy-report-v2": ["kpi-grid", "evidence-table", "insight-table", "mini-chart"],
    "demand-gap-report-v2": ["kpi-grid", "evidence-table", "insight-table", "demand-chart", "data-chart-source=\"appealsRows\"", "data-chart-source=\"gapRows\""],
}

REPORT_REQUIRED_CLASSES = {
    "market-depth-report-v2": [
        "report-header",
        "section-number",
        "chart-container",
        "insight-box",
        "conclusion",
        "comp-deep-grid",
        "comp-deep-card",
    ],
    "lifecycle-strategy-report-v2": [
        "report-header",
        "section-number",
        "insight-box",
        "persona-grid",
        "timeline-grid",
        "bundle-grid",
        "phase-grid",
        "risk-grid",
        "sku-table-wrap",
    ],
    "demand-gap-report-v2": [
        "hero",
        "sec",
        "card focus",
        "kano-grid",
        "demand-evidence-grid",
        "chart-interpretation",
    ],
}

TEMPLATE_STRUCTURE_PATTERNS = {
    "market-depth-report-v2": [
        ("竞品主表", r"<table\b[^>]*class=['\"][^'\"]*\bcomp-table\b"),
        ("VOC 双栏", r"<div\b[^>]*class=['\"][^'\"]*\bvoc-grid\b"),
        ("标杆竞品拆解", r"<div\b[^>]*class=['\"][^'\"]*\bcomp-deep-grid\b"),
        ("供应链网格", r"<div\b[^>]*class=['\"][^'\"]*\bsupply-grid\b"),
        ("价格方案", r"<div\b[^>]*class=['\"][^'\"]*\bpricing-grid\b"),
        ("AI 生图 Prompt", r"<div\b[^>]*class=['\"][^'\"]*\bprompt-grid\b"),
    ],
    "lifecycle-strategy-report-v2": [
        ("SKU 执行表", r"<table\b[^>]*id=['\"]skuTable['\"]"),
        ("生命周期时间线", r"<div\b[^>]*class=['\"][^'\"]*\btimeline-grid\b"),
        ("Bundle 策略", r"<div\b[^>]*class=['\"][^'\"]*\bbundle-grid\b"),
        ("风险矩阵", r"<div\b[^>]*class=['\"][^'\"]*\brisk-grid\b"),
    ],
    "demand-gap-report-v2": [
        ("APPEALS 图表", r"<div\b[^>]*id=['\"]appealsRose['\"][^>]*class=['\"][^'\"]*\bdemand-chart\b"),
        ("需求鸿沟图表", r"<div\b[^>]*id=['\"]gapRadar['\"][^>]*class=['\"][^'\"]*\bdemand-chart\b"),
        ("KANO/JTBD 矩阵", r"<div\b[^>]*class=['\"][^'\"]*\bkano-grid\b"),
        ("证据机会卡", r"<div\b[^>]*class=['\"][^'\"]*\bdemand-evidence-grid\b"),
    ],
}

CUSTOMER_HTML_REQUIRED_TERMS = ["证据强度", "数据覆盖", "数据缺口", "置信等级", "建议动作"]
CUSTOMER_HTML_BANNED_PLACEHOLDERS = [
    "样本",
    "样品",
    "补数",
    "待补",
    "待验证",
    "待评分",
    "待修复",
    "待样品",
    "暂无有效数据",
    "暂无数据",
    "未分层",
    "清洗数据",
    "清洗后数据",
    "清洗后的竞品",
    "清洗后的结论",
]
MARKET_DEPTH_BANNED_PLACEHOLDERS = CUSTOMER_HTML_BANNED_PLACEHOLDERS

CUSTOMER_HTML_BANNED_LITERALS = [
    "source_id",
    "source_ids",
    "used_source_ids",
    "Product ID",
    "ProductId",
    "StoreName",
    "Price",
    "Photo",
    "product_id",
    "raw_path",
    "provider",
    "method_id",
    "数据血缘",
    "来源",
    "竞品记录",
    "1688货源",
    "ready_for_normalization",
    "amz-market-research-orchestrated",
    "three-report-index-v2",
    "Type A",
    "Type B",
    "Type C",
    "Type D",
]

CUSTOMER_HTML_BANNED_PATTERNS = [
    re.compile(r"\bcollect_[\w\u4e00-\u9fff-]+\.py\b", re.IGNORECASE),
    re.compile(r"\bsrc[_-][\w\u4e00-\u9fff-]+\b", re.IGNORECASE),
    re.compile(r"\bsf[_-][\w\u4e00-\u9fff-]+\b", re.IGNORECASE),
    re.compile(r"\bB0[A-Z0-9]{8}\b"),
    re.compile(r"参考竞品\s+[^<]{0,48}参考竞品"),
    re.compile(r"\bdata/raw/[^\s<>'\"]+", re.IGNORECASE),
    re.compile(r"[A-Za-z]:\\[^\s<>'\"]+"),
]

REVIEW_TEXT_KEYS = {"title", "text", "content", "body", "comment"}
RAW_CLIENT_TEXT_KEYS = {"title", "name", "description", "summary", "content", "body", "comment"}
CUSTOMER_SAFETY_CACHE: dict[int, dict[str, Any]] = {}


class ValidationError(Exception):
    pass


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{path}: invalid JSON: {exc}") from exc


def slot_contract() -> dict[str, Any]:
    return load_json(HTML_TEMPLATE_SLOT_CONTRACT)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_unique_entity_keys(data_pack: dict[str, Any]) -> None:
    checks = [
        ("products", product_dedupe_key),
        ("keywords", keyword_dedupe_key),
        ("categories", category_dedupe_key),
        ("reviews", review_dedupe_key),
        ("tiktok_products", tiktok_product_dedupe_key),
        ("tiktok_videos", tiktok_video_dedupe_key),
        ("tiktok_authors", tiktok_author_dedupe_key),
        ("suppliers", supplier_dedupe_key),
        ("web_documents", web_document_dedupe_key),
    ]
    for entity_name, key_func in checks:
        seen: dict[str, int] = {}
        for idx, entity in enumerate(data_pack.get(entity_name) or []):
            if not isinstance(entity, dict):
                continue
            key = key_func(dict(entity))
            if not key:
                continue
            if key in seen:
                raise ValidationError(f"Duplicate {entity_name} dedupe key after normalization: {key} at rows {seen[key]} and {idx}")
            seen[key] = idx


def validate_required_files(report_dir: Path) -> None:
    for rel_path in REQUIRED_FILES:
        path = report_dir / rel_path
        require(path.exists(), f"Missing required artifact: {rel_path}")
        require(path.is_file(), f"Required artifact is not a file: {rel_path}")


def validate_sources(data_pack: dict[str, Any]) -> set[str]:
    sources = data_pack.get("sources")
    require(isinstance(sources, list) and sources, "data_pack.sources must be a non-empty list")

    source_ids: set[str] = set()
    for idx, source in enumerate(sources):
        require(isinstance(source, dict), f"data_pack.sources[{idx}] must be an object")
        for key in SOURCE_REQUIRED_KEYS:
            require(source.get(key), f"data_pack.sources[{idx}] missing {key}")
        source_id = str(source["source_id"])
        require(source_id not in source_ids, f"Duplicate source_id: {source_id}")
        source_ids.add(source_id)
    return source_ids


def validate_entity_lineage(data_pack: dict[str, Any], source_ids: set[str]) -> None:
    for key in DATA_PACK_KEYS:
        require(key in data_pack, f"data_pack missing required key: {key}")

    for key in ENTITY_LIST_KEYS:
        entities = data_pack.get(key) or []
        require(isinstance(entities, list), f"data_pack.{key} must be a list")
        for idx, entity in enumerate(entities):
            require(isinstance(entity, dict), f"data_pack.{key}[{idx}] must be an object")
            require(entity.get("source_id"), f"data_pack.{key}[{idx}] missing source_id")
            require(entity["source_id"] in source_ids, f"data_pack.{key}[{idx}] references unknown source_id: {entity['source_id']}")
            require(entity.get("provider"), f"data_pack.{key}[{idx}] missing provider")

    require(
        len(data_pack["keywords"]) >= MIN_KEYWORD_SAMPLE_COUNT,
        f"data_pack.keywords must contain at least {MIN_KEYWORD_SAMPLE_COUNT} keyword samples",
    )

    require(isinstance(data_pack["data_gaps"], list), "data_pack.data_gaps must be a list")
    quality = data_pack["quality"]
    require(isinstance(quality, dict), "data_pack.quality must be an object")
    require("overall_score" in quality, "data_pack.quality missing overall_score")
    require("grade" in quality, "data_pack.quality missing grade")
    score = quality["overall_score"]
    require(isinstance(score, (int, float)) and 0 <= score <= 1, "data_pack.quality.overall_score must be between 0 and 1")

    normalization = data_pack["normalization"]
    require(isinstance(normalization, dict), "data_pack.normalization must be an object")
    require(normalization.get("deduped") is True, "data_pack.normalization.deduped must be true")
    for key in ["before_counts", "after_counts", "removed_counts", "cross_validated_counts"]:
        require(isinstance(normalization.get(key), dict), f"data_pack.normalization missing {key}")
    before_counts = normalization["before_counts"]
    after_counts = normalization["after_counts"]
    removed_counts = normalization["removed_counts"]
    cross_counts = normalization["cross_validated_counts"]
    for key in ENTITY_LIST_KEYS:
        if key in after_counts:
            require(after_counts[key] == len(data_pack.get(key) or []), f"normalization.after_counts.{key} must equal data_pack.{key} length")
        if key in before_counts and key in after_counts and key in removed_counts:
            require(removed_counts[key] == before_counts[key] - after_counts[key], f"normalization.removed_counts.{key} must equal before-after")
        if key in cross_counts and key in after_counts:
            require(cross_counts[key] <= after_counts[key], f"normalization.cross_validated_counts.{key} cannot exceed after_counts")
    validate_unique_entity_keys(data_pack)


def validate_data_gaps_contract(data_pack: dict[str, Any]) -> None:
    for idx, gap in enumerate(data_pack.get("data_gaps") or []):
        if not isinstance(gap, dict):
            continue
        if gap.get("type") != "amazon_product_enrichment_empty_dimensions":
            continue
        require(
            gap.get("module") == "amazon_product_enrichment",
            f"data_gaps[{idx}] amazon product enrichment gap must use module=amazon_product_enrichment",
        )
        evidence = gap.get("retry_evidence")
        require(isinstance(evidence, dict), f"data_gaps[{idx}] amazon product enrichment gap missing retry_evidence")
        asins = evidence.get("asins_attempted")
        require(isinstance(asins, list) and len(asins) >= 2, f"data_gaps[{idx}] retry_evidence.asins_attempted must include multiple ASINs")
        require(
            evidence.get("attempted_asin_count") == len(asins),
            f"data_gaps[{idx}] retry_evidence.attempted_asin_count must match asins_attempted length",
        )
        empty_dimensions = evidence.get("empty_dimensions")
        successful_dimensions = evidence.get("successful_dimensions")
        tool_stats = evidence.get("tool_stats")
        require(isinstance(empty_dimensions, list) and empty_dimensions, f"data_gaps[{idx}] retry_evidence.empty_dimensions must be a non-empty list")
        require(
            isinstance(successful_dimensions, list) and successful_dimensions,
            f"data_gaps[{idx}] retry_evidence.successful_dimensions must be a non-empty list",
        )
        require(isinstance(tool_stats, dict), f"data_gaps[{idx}] retry_evidence.tool_stats must be an object")
        for tool in empty_dimensions:
            stats = tool_stats.get(tool)
            require(isinstance(stats, dict), f"data_gaps[{idx}] retry_evidence.tool_stats missing empty dimension: {tool}")
            require(
                int(stats.get("calls") or 0) >= len(asins) and int(stats.get("rows") or 0) == 0,
                f"data_gaps[{idx}] empty dimension {tool} must show retries across ASINs and zero rows",
            )
        for tool in successful_dimensions:
            stats = tool_stats.get(tool)
            require(isinstance(stats, dict), f"data_gaps[{idx}] retry_evidence.tool_stats missing successful dimension: {tool}")
            require(int(stats.get("rows") or 0) > 0, f"data_gaps[{idx}] successful dimension {tool} must show returned rows")


def validate_normalized_data_pack_consistency(report_dir: Path, data_pack: dict[str, Any]) -> None:
    normalized_path = report_dir / "data/normalized/normalized_data_pack.json"
    normalized_pack = load_json(normalized_path)
    require(isinstance(normalized_pack, dict), "normalized_data_pack.json must be an object")
    require(
        normalized_pack == data_pack,
        "data/normalized/normalized_data_pack.json must match data/data_pack.json after normalization",
    )
    require(
        data_pack.get("cleaning_summary") == data_pack.get("normalization"),
        "data_pack.cleaning_summary must match data_pack.normalization",
    )


def entity_text(entity: dict[str, Any], fields: list[str]) -> str:
    return " ".join(normalized_key(entity.get(field)) for field in fields)


def contains_any(text: str, needles: list[str] | set[str]) -> bool:
    return any(needle in text for needle in needles)


def effective_records(data_pack: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = data_pack.get(f"effective_{key}")
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    value = data_pack.get(key)
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def validate_research_relevance_gate(data_pack: dict[str, Any]) -> None:
    relevance = data_pack.get("research_relevance") or {}
    effective_counts = relevance.get("effective_counts") or {}
    for key in ("products", "keywords", "reviews", "suppliers"):
        require(
            int(effective_counts.get(key, len(effective_records(data_pack, key)))) == len(effective_records(data_pack, key)),
            f"research_relevance.effective_counts.{key} must match effective_{key} length",
        )
    seed_terms = relevance.get("seed_terms") or []
    cabinet_closet_mode = relevance.get("mode") == "cabinet_closet_lighting"
    if cabinet_closet_mode:
        for idx, product in enumerate(effective_records(data_pack, "products")):
            text = entity_text(product, ["title", "title_cn", "brand", "category", "category_cn", "segment", "segment_cn", "positioning_cn"])
            require(not contains_any(text, CABINET_CLOSET_HARD_NOISE), f"effective_products[{idx}] contains cabinet/closet lighting pollution")
            require((product.get("research_relevance") or {}).get("passed") is True, f"effective_products[{idx}] missing passed research_relevance flag")
        seen_keyword_buckets: set[str] = set()
        for idx, keyword in enumerate(effective_records(data_pack, "keywords")):
            keyword_text = normalized_key(keyword.get("keyword"))
            require(not contains_any(keyword_text, CABINET_CLOSET_HARD_NOISE), f"effective_keywords[{idx}] contains cabinet/closet lighting pollution")
            require((keyword.get("research_relevance") or {}).get("passed") is True, f"effective_keywords[{idx}] missing passed research_relevance flag")
            source_type = normalized_key(keyword.get("source_type"))
            asin = normalized_key(keyword.get("asin"))
            bucket = f"traffic:{asin or 'unknown'}" if source_type == "product_traffic_terms" or asin else "market"
            dedupe_key = f"{bucket}|{keyword_text}"
            require(dedupe_key not in seen_keyword_buckets, f"effective_keywords duplicate bucket: {dedupe_key}")
            seen_keyword_buckets.add(dedupe_key)
        categorized_products = [product for product in effective_records(data_pack, "products") if product.get("category") or product.get("category_cn")]
        if categorized_products:
            require(data_pack.get("categories"), "data_pack.categories must be generated from effective product categories")
        return
    lighting_mode = relevance.get("mode") == "lighting" or is_lighting_research([str(term) for term in seed_terms])
    if not lighting_mode:
        return
    for idx, product in enumerate(effective_records(data_pack, "products")):
        text = entity_text(product, ["title", "title_cn", "brand", "category", "category_cn", "segment", "segment_cn", "positioning_cn"])
        has_signal = contains_any(text, LIGHTING_PRODUCT_SIGNALS)
        require(not contains_any(text, LIGHTING_HARD_PRODUCT_NOISE), f"effective_products[{idx}] contains non-lighting pollution")
        require(not (contains_any(text, LIGHTING_NOISE_TOKENS) and not has_signal), f"effective_products[{idx}] contains non-lighting pollution")
        require(has_signal, f"effective_products[{idx}] missing lighting semantic signal")
        require((product.get("research_relevance") or {}).get("passed") is True, f"effective_products[{idx}] missing passed research_relevance flag")
    seen_keyword_buckets: set[str] = set()
    for idx, keyword in enumerate(effective_records(data_pack, "keywords")):
        keyword_text = normalized_key(keyword.get("keyword"))
        require(not contains_any(keyword_text, LIGHTING_NOISE_TOKENS), f"effective_keywords[{idx}] contains non-lighting pollution")
        require(contains_any(keyword_text, LIGHTING_KEYWORD_SIGNALS), f"effective_keywords[{idx}] missing lighting semantic signal")
        require(not str(keyword.get("keyword_cn") or "").startswith("未映射关键词"), f"effective_keywords[{idx}] uses unmapped Chinese label")
        source_type = normalized_key(keyword.get("source_type"))
        asin = normalized_key(keyword.get("asin"))
        bucket = f"traffic:{asin or 'unknown'}" if source_type == "product_traffic_terms" or asin else "market"
        dedupe_key = f"{bucket}|{keyword_text}"
        require(dedupe_key not in seen_keyword_buckets, f"effective_keywords duplicate bucket: {dedupe_key}")
        seen_keyword_buckets.add(dedupe_key)
    categorized_products = [product for product in effective_records(data_pack, "products") if product.get("category") or product.get("category_cn")]
    if categorized_products:
        require(data_pack.get("categories"), "data_pack.categories must be generated from effective product categories")


def validate_quality_consistency(data_pack: dict[str, Any], delivery: dict[str, Any] | None = None) -> None:
    delivery = delivery or {}
    quality = data_pack.get("quality") or {}
    score = float(quality.get("overall_score") or 0)
    review_count = len(data_pack.get("reviews") or [])
    cross_counts = ((data_pack.get("normalization") or {}).get("cross_validated_counts") or {})
    non_keyword_cross = sum(float(value or 0) for key, value in cross_counts.items() if key != "keywords")
    decision = str(delivery.get("decision") or "").strip().lower()
    status = str(delivery.get("status") or "").strip().lower()
    strong_decision = decision == "go"

    require(
        not (review_count < 80 and score >= 0.85),
        "quality score is too high for review sample depth below 80",
    )
    require(
        not (review_count < 80 and strong_decision and score >= 0.75),
        "strong Go decision requires deeper review evidence or lower confidence",
    )
    require(
        not (non_keyword_cross <= 0 and strong_decision and score >= 0.75),
        "strong Go decision requires non-keyword cross-validation evidence",
    )
    require(
        not (status == "partial" and strong_decision),
        "partial delivery status cannot carry an unconditional Go decision",
    )


def validate_data_readiness(report_dir: Path, delivery: dict[str, Any] | None = None) -> None:
    delivery = delivery or {}
    readiness = assess_data_readiness(report_dir, "auto")
    modules = ", ".join(gap.get("module", "unknown") for gap in readiness.get("blocking_gaps") or [])
    delivery_status = str(delivery.get("status") or "").strip().lower()
    delivery_decision = str(delivery.get("decision") or "").strip().lower()
    delivery_blocked = delivery_status == "blocked"
    ready_or_partial = readiness.get("acceptance_ready") is True or readiness.get("partial_report_ready") is True
    require(
        ready_or_partial or delivery_blocked,
        f"data readiness must pass or be partial-ready before final delivery validation: {modules}",
    )
    if delivery_blocked:
        require(not ready_or_partial, "blocked delivery status requires failed readiness")
        require(delivery_decision != "go", "blocked delivery cannot carry an unconditional Go decision")
        require(readiness.get("blocking_gaps"), "blocked delivery must include readiness blocking_gaps")

    recorded_path = report_dir / "data" / "normalized" / "data_readiness_report.json"
    if recorded_path.exists():
        recorded = load_json(recorded_path)
        require(isinstance(recorded, dict), "data_readiness_report.json must be an object")
        recorded_ready_or_partial = recorded.get("acceptance_ready") is True or recorded.get("partial_report_ready") is True
        require(
            recorded_ready_or_partial or delivery_blocked,
            "data_readiness_report.json must be acceptance_ready or partial_report_ready for final delivery validation",
        )
        allowed_sample_classes = {"non_acceptance_sample"} if delivery_blocked else {"acceptance_sample", "partial_acceptance_sample"}
        require(recorded.get("sample_class") in allowed_sample_classes, "data_readiness_report.json sample_class must match delivery status")


def readiness_summary_for_contract(readiness: dict[str, Any]) -> dict[str, Any]:
    supplier_quality = dict(readiness.get("supplier_quality_gate") or {})
    missing_fields = supplier_quality.pop("missing_documented_required_fields", [])
    supplier_quality.pop("observed_fields", None)
    if missing_fields:
        supplier_quality["field_diagnostic"] = "当前1688响应缺少商品标题和商品链接字段"
    return {
        "acceptance_ready": readiness.get("acceptance_ready"),
        "partial_report_ready": readiness.get("partial_report_ready"),
        "supply_conclusion_blocked": readiness.get("supply_conclusion_blocked"),
        "sample_class": readiness.get("sample_class"),
        "depth": readiness.get("depth"),
        "blocking_gap_count": len(readiness.get("blocking_gaps") or []),
        "warning_count": len(readiness.get("warnings") or []),
        "counts": readiness.get("counts") or {},
        "supplier_quote_gate": readiness.get("supplier_quote_gate") or {},
        "supplier_quality_gate": supplier_quality,
    }


def readiness_contract_value_matches(key: str, recorded: Any, expected: Any) -> bool:
    if key != "counts" or not isinstance(recorded, dict) or not isinstance(expected, dict):
        return recorded == expected
    for count_key, expected_value in expected.items():
        if count_key not in recorded:
            if count_key == "tiktok_authors" and expected_value in (0, None):
                continue
            return False
        if recorded.get(count_key) != expected_value:
            return False
    for count_key, recorded_value in recorded.items():
        if count_key not in expected:
            if count_key == "tiktok_authors" and recorded_value in (0, None):
                continue
            return False
    return True


def validate_analysis_plan(analysis_plan: dict[str, Any], source_ids: set[str]) -> None:
    chain = analysis_plan.get("method_chain")
    require(isinstance(chain, list) and chain, "analysis_plan.method_chain must be a non-empty list")
    for idx, method in enumerate(chain):
        require(isinstance(method, dict), f"analysis_plan.method_chain[{idx}] must be an object")
        require(method.get("method_id"), f"analysis_plan.method_chain[{idx}] missing method_id")
        require(method.get("output"), f"analysis_plan.method_chain[{idx}] missing output")
        used_source_ids = method.get("used_source_ids")
        require(isinstance(used_source_ids, list) and used_source_ids, f"analysis_plan.method_chain[{idx}] missing used_source_ids")
        for source_id in used_source_ids:
            require(source_id in source_ids or source_id == "all", f"analysis_plan.method_chain[{idx}] references unknown source_id: {source_id}")

    require("limitations" in analysis_plan, "analysis_plan missing limitations")
    require("confidence" in analysis_plan, "analysis_plan missing confidence")


def technical_values_from_data_pack(data_pack: Any) -> set[str]:
    values: set[str] = set()
    tracked_keys = {"source_id", "source_ids", "provider", "raw_path", "path", "asin", "product_id", "video_id"}

    def visit(value: Any, key: str | None = None) -> None:
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                visit(child_value, str(child_key))
        elif isinstance(value, list):
            for item in value:
                visit(item, key)
        elif key in tracked_keys and value not in (None, ""):
            if isinstance(value, (str, int, float)):
                text = str(value).strip()
                if len(text) >= 3:
                    values.add(text)

    visit(data_pack)
    return values


def customer_safety_context(data_pack: dict[str, Any]) -> dict[str, Any]:
    cache_key = id(data_pack)
    cached = CUSTOMER_SAFETY_CACHE.get(cache_key)
    if cached is not None:
        return cached
    context = {
        "technical_values": technical_values_from_data_pack(data_pack),
        "raw_english_values": raw_english_client_values(data_pack),
        "raw_english_fragments": raw_english_client_fragments(data_pack),
        "allowed_keywords": allowed_english_keyword_text(data_pack),
    }
    CUSTOMER_SAFETY_CACHE[cache_key] = context
    return context


def contains_cjk(text: str) -> bool:
    return re.search(r"[\u4e00-\u9fff]", text) is not None


def raw_english_review_values(data_pack: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for review in data_pack.get("reviews") or []:
        if not isinstance(review, dict):
            continue
        for key in REVIEW_TEXT_KEYS:
            value = review.get(key)
            if value in (None, ""):
                continue
            text = re.sub(r"\s+", " ", str(value)).strip()
            if len(text) < 8 or contains_cjk(text):
                continue
            words = re.findall(r"[A-Za-z][A-Za-z']+", text)
            if len(words) >= 2:
                values.add(text)
    return values


def raw_english_client_values(data_pack: dict[str, Any]) -> set[str]:
    values = set(raw_english_review_values(data_pack))
    for entity_key in ENTITY_LIST_KEYS:
        for entity in data_pack.get(entity_key) or []:
            if not isinstance(entity, dict):
                continue
            for key in RAW_CLIENT_TEXT_KEYS:
                value = entity.get(key)
                if value in (None, ""):
                    continue
                text = re.sub(r"\s+", " ", str(value)).strip()
                if len(text) < 8 or contains_cjk(text) or text.startswith(("http://", "https://")):
                    continue
                words = re.findall(r"[A-Za-z][A-Za-z']+", text)
                if len(words) >= 3:
                    values.add(text)
    return values


def allowed_english_keyword_text(data_pack: dict[str, Any]) -> str:
    values: list[str] = []
    research_object = data_pack.get("research_object") or {}
    if isinstance(research_object, dict):
        values.append(normalized_visible_text(research_object.get("value")))
        values.extend(normalized_visible_text(item) for item in (research_object.get("seed_keywords") or []))
    elif research_object:
        values.append(normalized_visible_text(research_object))
    for keyword in data_pack.get("keywords") or []:
        if isinstance(keyword, dict):
            values.append(normalized_visible_text(keyword.get("keyword")))
    return " | ".join(value.casefold() for value in values if value)


def normalized_visible_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def cosmo_term_supported_by_evidence(term: Any, evidence_text: str) -> bool:
    normalized_term = normalized_visible_text(term)
    normalized_evidence = normalized_visible_text(evidence_text)
    if not normalized_term:
        return True
    if not normalized_evidence:
        return False
    if contains_cjk(normalized_term):
        if normalized_term in normalized_evidence:
            return True
        cjk_text = "".join(re.findall(r"[\u4e00-\u9fff]+", normalized_term))
        cjk_bigrams = {
            cjk_text[idx : idx + 2]
            for idx in range(max(0, len(cjk_text) - 1))
            if len(cjk_text[idx : idx + 2]) == 2
        }
        return any(token in normalized_evidence for token in cjk_bigrams)
    return re.search(rf"\b{re.escape(normalized_term.casefold())}\b", normalized_evidence.casefold()) is not None


def cosmo_evidence_text(source_evidence: Any) -> str:
    if not isinstance(source_evidence, list):
        return ""
    parts: list[str] = []
    for evidence in source_evidence:
        if not isinstance(evidence, dict):
            continue
        for key in ["excerpt", "text", "title", "summary", "field", "source_id"]:
            value = normalized_visible_text(evidence.get(key))
            if value:
                parts.append(value)
        supported_terms = evidence.get("supported_terms")
        if isinstance(supported_terms, list):
            parts.extend(normalized_visible_text(term) for term in supported_terms if normalized_visible_text(term))
    return " ".join(parts)


def is_supplier_or_1688_image_src(src: str) -> bool:
    text = normalized_visible_text(src).casefold()
    return any(
        marker in text
        for marker in [
            "detail.1688.com",
            "1688.com/offer",
            "alicdn.com",
            "alibaba.com",
            "aliexpress.com",
        ]
    )


def is_amazon_competitor_image_src(src: str) -> bool:
    try:
        host = (urlparse(normalized_visible_text(src)).hostname or "").casefold()
    except ValueError:
        return False
    return any(
        host == domain or host.endswith(f".{domain}")
        for domain in [
            "media-amazon.com",
            "ssl-images-amazon.com",
            "images-amazon.com",
        ]
    )


def raw_english_client_fragments(data_pack: dict[str, Any]) -> set[str]:
    fragments: set[str] = set()
    for value in raw_english_client_values(data_pack):
        text = normalized_visible_text(value)
        if not text or contains_cjk(text):
            continue
        for words in english_word_segments(text):
            if len(words) < 3:
                continue
            folded_text = " ".join(words)
            fragments.add(folded_text)
            for size in range(3, min(8, len(words)) + 1):
                for idx in range(0, len(words) - size + 1):
                    fragment = " ".join(words[idx : idx + size])
                    if len(fragment) >= 12:
                        fragments.add(fragment)
    return fragments


def customer_visible_text(text: str) -> str:
    without_scripts = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", text, flags=re.I | re.S)
    visible_attrs = re.findall(r"\b(?:alt|title|aria-label)=['\"]([^'\"]+)['\"]", without_scripts, flags=re.I)
    without_tags = re.sub(r"<[^>]+>", " . ", without_scripts)
    return html.unescape(" ".join([without_tags, *visible_attrs]))


def strip_allowed_customer_exceptions(text: str) -> str:
    text = re.sub(
        r"\bdata-report-style=[\"'](?:three-report-index-v2|market-depth-report-v2|lifecycle-strategy-report-v2|demand-gap-report-v2)[\"']",
        'data-report-style="report-contract"',
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"<span\b(?=[^>]*\bdata-allow-asin=[\"'](?:benchmark-sniper|profit-model|competitor-table|demand-target-anchor|sku-reference)[\"'])[^>]*>\s*B0[A-Z0-9]{8}\s*</span>",
        "竞品ASIN",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"<[^>]+\bdata-allow-english-review=[\"']short[\"'][^>]*>.*?</[^>]+>",
        "英文评论短摘",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return text


def english_word_segments(text: str) -> list[list[str]]:
    segments: list[list[str]] = []
    for segment in re.findall(r"[A-Za-z][A-Za-z'\- ]*[A-Za-z]", normalized_visible_text(text)):
        words = [word.casefold() for word in re.findall(r"[A-Za-z][A-Za-z']+", segment)]
        if words:
            segments.append(words)
    return segments


def visible_word_ngrams(text: str) -> set[str]:
    ngrams: set[str] = set()
    for words in english_word_segments(customer_visible_text(text)):
        for size in range(3, min(8, len(words)) + 1):
            for idx in range(0, len(words) - size + 1):
                fragment = " ".join(words[idx : idx + size])
                if len(fragment) >= 12:
                    ngrams.add(fragment)
    return ngrams


def is_allowed_english_fragment(fragment: str, allowed_keywords: str) -> bool:
    folded = fragment.casefold()
    if folded in allowed_keywords:
        return True
    words = folded.split()
    if len(words) < 3:
        return False
    return all(" ".join(words[idx : idx + 2]) in allowed_keywords for idx in range(0, len(words) - 1))


def validate_no_raw_english_leaks(rel_path: str, text: str, data_pack: dict[str, Any], artifact_label: str) -> None:
    text = strip_allowed_customer_exceptions(text)
    visible_text = customer_visible_text(text)
    normalized_text = normalized_visible_text(visible_text).casefold()
    unescaped_text = html.unescape(visible_text)
    normalized_unescaped = normalized_visible_text(unescaped_text).casefold()
    visible_ngrams = visible_word_ngrams(text)
    visible_ngrams.update(visible_word_ngrams(unescaped_text))
    context = customer_safety_context(data_pack)
    allowed_keywords = context["allowed_keywords"]

    for raw_value in context["raw_english_values"]:
        raw_text = normalized_visible_text(raw_value)
        if not raw_text:
            continue
        raw_folded = raw_text.casefold()
        if not is_allowed_english_fragment(raw_folded, allowed_keywords) and (raw_folded in normalized_text or raw_folded in normalized_unescaped):
            raise ValidationError(f"{rel_path} customer {artifact_label} leaks raw English review/client text fragment: {raw_text[:72]}")

    leaked_fragments = {
        fragment
        for fragment in (visible_ngrams & context["raw_english_fragments"])
        if not is_allowed_english_fragment(fragment, allowed_keywords)
    }
    if leaked_fragments:
        fragment = sorted(leaked_fragments, key=len, reverse=True)[0]
        raise ValidationError(f"{rel_path} customer {artifact_label} leaks raw English review/client text fragment: {fragment[:72]}")


def validate_customer_html(rel_path: str, html_doc: str, data_pack: dict[str, Any]) -> None:
    html_for_safety = strip_allowed_customer_exceptions(html_doc)
    visible_text = normalized_visible_text(customer_visible_text(html_for_safety)).casefold()
    internal_status_patterns = [
        r"\bcollection_in_progress\b",
        r"\bready_for_normalization\b",
        r"\bsuccess\b",
        r"\bwarning\b",
        r"\bscore\s*[0-9]+(?:\.[0-9]+)?\b",
    ]
    for pattern in internal_status_patterns:
        match = re.search(pattern, visible_text)
        if match is not None:
            raise ValidationError(f"{rel_path} customer HTML contains visible internal status: {match.group(0)}")
    if re.search(r"class=['\"][^'\"]*\bkpi-value\b[^'\"]*['\"][^>]*>\s*-\s*</", html_for_safety, flags=re.I):
        raise ValidationError(f"{rel_path} customer HTML contains empty customer KPI")

    for literal in CUSTOMER_HTML_BANNED_LITERALS:
        require(literal not in html_for_safety, f"{rel_path} customer HTML leaks technical identifier: {literal}")

    for placeholder in CUSTOMER_HTML_BANNED_PLACEHOLDERS:
        require(placeholder not in html_for_safety, f"{rel_path} customer HTML contains placeholder or non-final data wording: {placeholder}")

    for pattern in CUSTOMER_HTML_BANNED_PATTERNS:
        match = pattern.search(html_for_safety)
        if match is not None:
            raise ValidationError(f"{rel_path} customer HTML leaks technical identifier: {match.group(0)}")

    for img_match in re.finditer(r"<img\b[^>]*>", html_doc, flags=re.I):
        tag = img_match.group(0)
        src_match = re.search(r"\bsrc\s*=\s*(['\"])(.*?)\1", tag, flags=re.I | re.S)
        require(src_match is not None, f"{rel_path} customer HTML image missing src")
        src = (src_match.group(2) or "").strip()
        require(bool(src), f"{rel_path} customer HTML image has empty src")
        require(re.match(r"^https?://", src, flags=re.I) is not None, f"{rel_path} customer HTML image src must be an http(s) URL")
        class_match = re.search(r"\bclass\s*=\s*(['\"])(.*?)\1", tag, flags=re.I | re.S)
        class_text = class_match.group(2) if class_match else ""
        if any(token in class_text.split() for token in ["comp-product-thumb", "comp-image-thumb", "comp-deep-image", "sku-reference-thumb"]):
            require(
                not is_supplier_or_1688_image_src(src),
                f"{rel_path} customer HTML competitor image must use Amazon competitor image, not 1688/Alibaba supplier image",
            )
            require(
                is_amazon_competitor_image_src(src),
                f"{rel_path} customer HTML competitor image must use Amazon competitor image domain",
            )

    for value in customer_safety_context(data_pack)["technical_values"]:
        require(value not in html_for_safety, f"{rel_path} customer HTML leaks technical identifier: {value}")

    validate_no_raw_english_leaks(rel_path, html_doc, data_pack, "HTML")

    if "market-depth-report.html" not in rel_path:
        for term in CUSTOMER_HTML_REQUIRED_TERMS:
            require(term in html_doc, f"{rel_path} customer HTML missing required analysis term: {term}")
    require(re.search(r"<p>\s*</p>", html_doc, flags=re.I) is None, f"{rel_path} customer HTML contains empty paragraph")
    require(re.search(r"<strong>\s*</strong>", html_doc, flags=re.I) is None, f"{rel_path} customer HTML contains empty strong tag")
    require("Score -" not in html_doc, f"{rel_path} customer HTML contains placeholder score")
    require("趋势：-" not in html_doc, f"{rel_path} customer HTML contains placeholder trend")


def html_class_tokens(html_doc: str) -> set[str]:
    tokens: set[str] = set()
    for class_attr in re.findall(r"class=['\"]([^'\"]+)['\"]", html_doc):
        for token in class_attr.split():
            if re.fullmatch(r"[A-Za-z0-9_-]+", token):
                tokens.add(token)
    return tokens


def html_id_tokens(html_doc: str) -> set[str]:
    return set(re.findall(r"id=['\"]([^'\"]+)['\"]", html_doc))


def validate_template_dom_class_parity(rel_path: str, report_html: str, report_style: str) -> None:
    canonical_path = CANONICAL_TEMPLATE_ASSETS[report_style]
    require(canonical_path.exists(), f"{rel_path} canonical template asset missing: {canonical_path}")
    canonical_html = canonical_path.read_text(encoding="utf-8")
    missing_ids = sorted(html_id_tokens(canonical_html) - html_id_tokens(report_html))
    missing_classes_set = html_class_tokens(canonical_html) - html_class_tokens(report_html)
    if report_style == "market-depth-report-v2":
        missing_classes_set -= {"badge-hot", "badge-growth", "badge-premium", "badge-risk"}
    missing_classes = sorted(missing_classes_set)
    require(not missing_ids, f"{rel_path} missing canonical template ids: {', '.join(missing_ids)}")
    require(not missing_classes, f"{rel_path} missing canonical template classes: {', '.join(missing_classes)}")
    missing_structures = [
        label
        for label, pattern in TEMPLATE_STRUCTURE_PATTERNS.get(report_style, [])
        if re.search(pattern, report_html, flags=re.I | re.S) is None
    ]
    require(not missing_structures, f"{rel_path} missing canonical template structure: {', '.join(missing_structures)}")


def validate_customer_visible_asset(rel_path: str, text: str, data_pack: dict[str, Any]) -> None:
    for literal in CUSTOMER_HTML_BANNED_LITERALS:
        require(literal not in text, f"{rel_path} customer asset leaks technical identifier: {literal}")
    for pattern in CUSTOMER_HTML_BANNED_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            raise ValidationError(f"{rel_path} customer asset leaks technical identifier: {match.group(0)}")
    for value in customer_safety_context(data_pack)["technical_values"]:
        require(value not in text, f"{rel_path} customer asset leaks technical identifier: {value}")
    validate_no_raw_english_leaks(rel_path, text, data_pack, "asset")


def validate_customer_visible_assets(report_dir: Path, data_pack: dict[str, Any]) -> None:
    for rel_path in SITE_ASSETS.values():
        path = report_dir / rel_path
        text = path.read_text(encoding="utf-8")
        if rel_path.endswith("echarts.min.js"):
            require("cdn.jsdelivr" not in text, f"{rel_path} must be a local static library, not a CDN loader")
            continue
        validate_customer_visible_asset(rel_path, text, data_pack)


def validate_cosmo_alexa_tags(report_dir: Path) -> None:
    rel_path = "analysis/cosmo_alexa_tags.json"
    payload = load_json(report_dir / rel_path)
    require(isinstance(payload, dict), f"{rel_path} must be an object")
    relations = payload.get("relations")
    require(isinstance(relations, list), f"{rel_path} relations must be a list")
    relation_types = {str(item.get("relation_type")) for item in relations if isinstance(item, dict)}
    missing = sorted(COSMO_ALEXA_RELATION_TYPES - relation_types)
    require(not missing, f"{rel_path} missing 15-tag relation types: {', '.join(missing)}")
    require(len(relations) >= len(COSMO_ALEXA_RELATION_TYPES), f"{rel_path} must contain all 15 relation entries")
    raw_relation_code_re = re.compile(r"\b(?:USED|CAPABLE|IS_A)[A-Z_]*\b|\bx(?:WANT|INTERSTED_IN|Is_A)\b|\bREL_\d+\b")
    term_signatures: dict[tuple[str, ...], list[str]] = {}
    term_relations: dict[str, set[str]] = {}
    for idx, item in enumerate(relations):
        require(isinstance(item, dict), f"{rel_path} relations[{idx}] must be an object")
        for key in [
            "relation_type",
            "label_cn",
            "display_relation",
            "terms",
            "source_evidence",
            "confidence",
            "evidence_count",
            "listing_label",
            "listing_action",
            "qa_label",
            "qa_action",
            "ad_label",
            "ad_action",
        ]:
            require(key in item, f"{rel_path} relations[{idx}] missing {key}")
        require(not raw_relation_code_re.search(str(item.get("label_cn") or "")), f"{rel_path} relations[{idx}].label_cn leaks raw relation code")
        require(not raw_relation_code_re.search(str(item.get("display_relation") or "")), f"{rel_path} relations[{idx}].display_relation leaks raw relation code")
        require(isinstance(item.get("terms"), list), f"{rel_path} relations[{idx}].terms must be a list")
        require(isinstance(item.get("source_evidence"), list), f"{rel_path} relations[{idx}].source_evidence must be a list")
        if item.get("confidence") != "低" and item.get("terms"):
            evidence_text = cosmo_evidence_text(item.get("source_evidence"))
            unsupported_terms = [
                normalized_visible_text(term)
                for term in item.get("terms")
                if normalized_visible_text(term) and not cosmo_term_supported_by_evidence(term, evidence_text)
            ]
            require(
                not unsupported_terms,
                f"{rel_path} relations[{idx}] COSMO terms lack current evidence support: {', '.join(unsupported_terms[:5])}",
            )
        if item.get("confidence") != "低":
            relation_type = str(item.get("relation_type"))
            normalized_terms = {
                normalized_visible_text(term).casefold()
                for term in item.get("terms")
                if normalized_visible_text(term)
            }
            signature = tuple(
                sorted(
                    normalized_terms
                )
            )
            if len(signature) >= 2:
                term_signatures.setdefault(signature, []).append(relation_type)
            for term in normalized_terms:
                term_relations.setdefault(term, set()).add(relation_type)
    repeated = {signature: rels for signature, rels in term_signatures.items() if len(rels) > 2}
    require(
        not repeated,
        f"{rel_path} COSMO relation terms are over-reused across relation cards; duplicate signatures: "
        + "; ".join(f"{'/'.join(rels)}={','.join(signature[:4])}" for signature, rels in repeated.items()),
    )
    overused_terms = {term: sorted(rels) for term, rels in term_relations.items() if len(rels) > 3}
    require(
        not overused_terms,
        f"{rel_path} COSMO single tag is over-reused across relation cards: "
        + "; ".join(f"{term}=>{'/'.join(rels)}" for term, rels in overused_terms.items()),
    )


def validate_lifecycle_strategy_analysis(report_dir: Path, data_pack: dict[str, Any]) -> None:
    rel_path = "analysis/lifecycle_strategy.json"
    payload = load_json(report_dir / rel_path)
    require(isinstance(payload, dict), f"{rel_path} must be an object")
    pool = payload.get("sku_candidate_pool")
    recommended = payload.get("recommended_skus")
    diagnostics = payload.get("filter_diagnostics")
    require(isinstance(pool, list), f"{rel_path} sku_candidate_pool must be a list")
    require(isinstance(recommended, list), f"{rel_path} recommended_skus must be a list")
    require(isinstance(diagnostics, dict), f"{rel_path} filter_diagnostics must be an object")
    effective_product_count = len(data_pack.get("effective_products") or [])
    if effective_product_count >= 30:
        require(len(pool) > 5, f"{rel_path} must not collapse {effective_product_count} effective products into five fallback SKUs")
        require(len(pool) >= min(30, effective_product_count), f"{rel_path} sku_candidate_pool too small for effective product pool")
    for idx, sku in enumerate(pool[:80]):
        require(isinstance(sku, dict), f"{rel_path} sku_candidate_pool[{idx}] must be an object")
        for key in ["name", "strategy_type_key", "type_label_cn", "target_segment", "reference_competitor", "priority", "ecosystem_path", "ecosystem_segment"]:
            require(sku.get(key) not in (None, "", [], {}), f"{rel_path} sku_candidate_pool[{idx}] missing {key}")
        strategy_type_key = str(sku.get("strategy_type_key") or "").strip()
        require(strategy_type_key in LIFECYCLE_STRATEGY_TYPE_KEYS, f"{rel_path} sku_candidate_pool[{idx}] strategy_type_key must be a semantic key")
        raw_type = str(sku.get("type") or "").strip()
        require(raw_type not in LIFECYCLE_RAW_TYPE_CODES, f"{rel_path} sku_candidate_pool[{idx}] type must not expose raw A/B/C/D codes")
        if raw_type:
            require(raw_type in LIFECYCLE_STRATEGY_TYPE_KEYS, f"{rel_path} sku_candidate_pool[{idx}] type must use semantic strategy key")
    for idx, sku in enumerate(recommended[:15]):
        require(isinstance(sku, dict), f"{rel_path} recommended_skus[{idx}] must be an object")
        strategy_type_key = str(sku.get("strategy_type_key") or "").strip()
        require(strategy_type_key in LIFECYCLE_STRATEGY_TYPE_KEYS, f"{rel_path} recommended_skus[{idx}] strategy_type_key must be a semantic key")
        require(str(sku.get("type") or "").strip() not in LIFECYCLE_RAW_TYPE_CODES, f"{rel_path} recommended_skus[{idx}] type must not expose raw A/B/C/D codes")
    serialized = json.dumps(payload, ensure_ascii=False)
    for term in LIFECYCLE_BANNED_FALLBACK_TERMS:
        require(term not in serialized, f"{rel_path} contains old lifecycle fallback term: {term}")


def validate_site_asset_contract(report_dir: Path) -> None:
    manifest = load_json(TEMPLATE_BASELINE_MANIFEST)
    baselines = manifest.get("baselines") if isinstance(manifest, dict) else None
    require(isinstance(baselines, dict), "template-baseline-manifest.json missing baselines")
    for key, folder in {"market_depth": "143101", "lifecycle_strategy": "143511", "demand_gap": "143645"}.items():
        baseline = baselines.get(key)
        require(isinstance(baseline, dict), f"template baseline missing {key}")
        require(folder in str(baseline.get("download_folder")), f"template baseline {key} must cite downloadpage/{folder}")
        require(re.fullmatch(r"[A-Fa-f0-9]{64}", str(baseline.get("sha256") or "")) is not None, f"template baseline {key} missing sha256")
        require(int(baseline.get("line_count") or 0) > 100, f"template baseline {key} line_count is too small")
        require(isinstance(baseline.get("borrowed_css_signals"), list) and baseline["borrowed_css_signals"], f"template baseline {key} missing borrowed_css_signals")
        require(isinstance(baseline.get("borrowed_js_signals"), list) and baseline["borrowed_js_signals"], f"template baseline {key} missing borrowed_js_signals")

    css_text = (report_dir / SITE_ASSETS["css"]).read_text(encoding="utf-8")
    js_text = (report_dir / SITE_ASSETS["js"]).read_text(encoding="utf-8")
    combined = css_text + "\n" + js_text
    require("http://" not in combined and "https://" not in combined, "site assets must not depend on remote CDN resources")
    for selector in [
        ".site-nav",
        ".table-tools",
        ".tab-button",
        ".evidence-drawer",
        ".mini-chart",
        ".template-market .report-header",
        ".template-lifecycle .report-header",
        ".template-demand .report-header",
        ".template-demand .hero",
        ".persona-grid",
        ".timeline-grid",
        ".bundle-grid",
        ".filter-btn",
        ".sku-table-wrap",
        ".ecosystem-pool-summary",
        ".cosmo-layout",
        ".cosmo-matrix",
        ".cosmo-top-list",
        ".cosmo-gap-panel",
        ".cosmo-action-board",
        ".quote-cn",
        ".chart-interpretation",
        "@media(max-width:760px)",
    ]:
        require(selector in css_text, f"report.css missing required interactive/layout selector: {selector}")
    for snippet in [
        "site-nav-toggle",
        "input.type='search'",
        "querySelectorAll('th')",
        "data-tabs",
        "data-tab-target",
        ".mini-chart .bar-row",
        ".filter-bar",
        "dataset.filter",
        "addEventListener('click'",
        "renderer:isIOSWebKit",
        "priceChart",
        "bubbleChart",
        "growthChart",
        "featureChart",
        "radarChart",
        "marginChart",
        "type:'sunburst'",
        "priorityChart",
        "aovChart",
        "type:'sankey'",
        "appealsRose",
        "gapRadar",
    ]:
        require(snippet in js_text, f"report.js missing required behavior hook: {snippet}")


def validate_view_models(report_dir: Path, data_pack: dict[str, Any]) -> None:
    required_keys = {"kpis", "charts", "tables", "cards", "evidence_strength", "sample_coverage", "limitations", "client_safe_text"}
    for rel_path in ["analysis/market_depth_view.json", "analysis/lifecycle_strategy_view.json", "analysis/demand_gap_view.json"]:
        payload = load_json(report_dir / rel_path)
        require(isinstance(payload, dict), f"{rel_path} must be an object")
        missing = sorted(required_keys - set(payload.keys()))
        require(not missing, f"{rel_path} missing required keys: {', '.join(missing)}")
        require(payload.get("client_safe_text") is True, f"{rel_path} must declare client_safe_text=true")
        validate_customer_visible_asset(rel_path, json.dumps(payload, ensure_ascii=False), data_pack)


def validate_text_artifacts(report_dir: Path, source_ids: set[str], data_pack: dict[str, Any]) -> None:
    report_md = (report_dir / "output/report.md").read_text(encoding="utf-8")
    compat_index_html = (report_dir / COMPAT_INDEX_REPORT).read_text(encoding="utf-8")
    bundle_index_html = (report_dir / BUNDLE_INDEX_REPORT).read_text(encoding="utf-8")
    child_htmls = {
        key: (report_dir / spec["path"]).read_text(encoding="utf-8")
        for key, spec in CHILD_REPORTS.items()
    }
    lineage = (report_dir / "data/lineage.md").read_text(encoding="utf-8")
    all_report_text = "\n".join([report_md, compat_index_html, bundle_index_html, *child_htmls.values()])

    for phrase in BANNED_REPORT_PHRASES:
        require(phrase not in all_report_text, f"Report contains banned phrase: {phrase}")

    if "月销量" in all_report_text:
        require("估算月销量" in all_report_text, "Monthly sales must be labeled as estimated monthly sales")

    require("Go / Watch / No-Go" in report_md or "Go/Watch/No-Go" in report_md, "report.md missing Go / Watch / No-Go section")
    validate_index_report(bundle_index_html, BUNDLE_INDEX_REPORT, BUNDLE_INDEX_REQUIRED_LINKS, data_pack, require_same_folder=True)
    validate_index_report(compat_index_html, COMPAT_INDEX_REPORT, COMPAT_INDEX_REQUIRED_LINKS, data_pack)
    for key, html_doc in child_htmls.items():
        validate_child_report(CHILD_REPORTS[key]["path"], html_doc, CHILD_REPORTS[key], data_pack)
    validate_interactive_dom({BUNDLE_INDEX_REPORT: bundle_index_html, COMPAT_INDEX_REPORT: compat_index_html, **{spec["path"]: child_htmls[key] for key, spec in CHILD_REPORTS.items()}})

    missing_lineage = [source_id for source_id in source_ids if source_id not in lineage]
    require(not missing_lineage, f"lineage.md missing source_id entries: {', '.join(missing_lineage)}")

    if source_ids:
        require(any(source_id in report_md or source_id in lineage for source_id in source_ids), "Audit artifacts do not cite any source_id")


def validate_supply_html_readiness_alignment(report_dir: Path) -> None:
    readiness_path = report_dir / "data/normalized/data_readiness_report.json"
    if not readiness_path.exists():
        return
    readiness = load_json(readiness_path)
    supplier_quote_gate = readiness.get("supplier_quote_gate") or {}
    supplier_quality_gate = readiness.get("supplier_quality_gate") or {}
    customer_visible_quality_passed = supplier_quality_gate.get("customer_visible_passed")
    if customer_visible_quality_passed is None:
        customer_visible_quality_passed = supplier_quality_gate.get("passed")
    supply_passed = (
        readiness.get("supply_conclusion_blocked") is False
        and supplier_quote_gate.get("passed") is True
        and customer_visible_quality_passed is True
    )
    if not supply_passed:
        return
    market_path = report_dir / CHILD_REPORTS["market_depth"]["path"]
    market_html = market_path.read_text(encoding="utf-8")
    contradictory_phrases = [
        "当前数据不能进入毛利率测算",
        "毛利率测算未启用",
        "1688质量门禁未通过",
    ]
    for phrase in contradictory_phrases:
        require(
            phrase not in market_html,
            f"{CHILD_REPORTS['market_depth']['path']} supply chain HTML contradicts passing readiness: {phrase}",
        )
    require(
        re.search(r"供应链状态[\s\S]{0,240}需补采", market_html) is None,
        f"{CHILD_REPORTS['market_depth']['path']} supply chain HTML contradicts passing readiness: 供应链状态=需补采",
    )


def validate_html_basics(rel_path: str, html_doc: str) -> None:
    html_lower = html_doc.lower()
    require("<html" in html_lower or "<!doctype html" in html_lower, f"{rel_path} is not a standalone HTML document")
    require("<pre" not in html_lower, f"{rel_path} must not wrap Markdown in a <pre> block")
    require("markdown-body" not in html_lower, f"{rel_path} must not be a Markdown-rendered wrapper")
    require(
        re.search(r"\n\s*\|.+\|\s*\n\s*\|[-:\s|]+\|", html_doc) is None,
        f"{rel_path} contains raw Markdown table syntax",
    )
    require("assets/report.css" in html_lower, f"{rel_path} must link shared assets/report.css")
    require("assets/report.js" in html_lower, f"{rel_path} must load shared assets/report.js")
    require("<style" in html_lower or "assets/report.css" in html_lower, f"{rel_path} must include CSS")


def validate_index_report(report_html: str, rel_path: str, required_links: list[str], data_pack: dict[str, Any], require_same_folder: bool = False) -> None:
    validate_html_basics(rel_path, report_html)
    validate_customer_html(rel_path, report_html, data_pack)
    require("三合一市场研究报告" in report_html, f"{rel_path} missing index report title")
    require("三合一" in report_html, f"{rel_path} must describe the three-report bundle")
    if require_same_folder:
        require('href="output/' not in report_html and "href='output/" not in report_html, f"{rel_path} child links must be same-folder relative links")
        require('href="html_reports/' not in report_html and "href='html_reports/" not in report_html, f"{rel_path} child links must be same-folder relative links")
    for link in required_links:
        require(
            re.search(rf"href=['\"]{re.escape(link)}['\"]", report_html) is not None,
            f"{rel_path} missing child report link: {link}",
        )


def validate_child_report(rel_path: str, report_html: str, spec: dict[str, Any], data_pack: dict[str, Any]) -> None:
    validate_html_basics(rel_path, report_html)
    validate_customer_html(rel_path, report_html, data_pack)
    require(spec["sections"][0] in report_html, f"{rel_path} missing report identity section: {spec['sections'][0]}")
    template_class = {
        "market-depth-report-v2": "",
        "lifecycle-strategy-report-v2": "template-lifecycle",
        "demand-gap-report-v2": "template-demand",
    }[spec["style"]]
    if template_class:
        require(template_class in report_html, f"{rel_path} missing template class: {template_class}")
    validate_template_dom_class_parity(rel_path, report_html, spec["style"])
    is_market_reference = spec["style"] == "market-depth-report-v2"
    section_count = report_html.count("<section") + len(re.findall(r"class=['\"][^'\"]*\bsection\b", report_html))
    require(section_count >= 7 if is_market_reference else report_html.count("<section") >= len(spec["sections"]), f"{rel_path} must use semantic section blocks")
    require(report_html.count("<table") >= (1 if is_market_reference else 3), f"{rel_path} must render analysis as HTML tables")
    required_dashboard_classes = (
        ["kpi-grid", "comp-table", "strategy-grid", "pricing-grid", "prompt-grid"]
        if is_market_reference
        else STYLE_REQUIRED_DASHBOARD_CLASSES.get(spec["style"], HTML_REQUIRED_CLASSES)
    )
    for class_name in required_dashboard_classes:
        require(class_name in report_html, f"{rel_path} missing required dashboard class: {class_name}")
    for class_name in REPORT_REQUIRED_CLASSES[spec["style"]]:
        require(class_name in report_html, f"{rel_path} missing required report-specific class: {class_name}")

    validate_fixed_template_slots(rel_path, report_html, spec["style"])

    for section_name in spec["sections"]:
        require(section_name in report_html, f"{rel_path} missing required dashboard section: {section_name}")

    for term in spec["terms"]:
        require(term in report_html, f"{rel_path} missing required mapped-data term: {term}")
    if spec["style"] == "market-depth-report-v2":
        for placeholder in MARKET_DEPTH_BANNED_PLACEHOLDERS:
            require(placeholder not in report_html, f"{rel_path} customer HTML contains placeholder or non-final data wording: {placeholder}")
    if spec["style"] == "lifecycle-strategy-report-v2":
        for term in LIFECYCLE_BANNED_FALLBACK_TERMS:
            require(term not in report_html, f"{rel_path} customer HTML contains old lifecycle fallback term: {term}")


def validate_fixed_template_slots(rel_path: str, report_html: str, style: str) -> None:
    if style == "market-depth-report-v2":
        ordered_ids = ["market-dashboard", "cosmo-alexa-tags", "competitor-scan", "voc-deep-dive"]
        positions = []
        for section_id in ordered_ids:
            match = re.search(rf'id=[\'"]{re.escape(section_id)}[\'"]', report_html)
            require(match is not None, f"{rel_path} fixed template slot mismatch: missing section id {section_id}")
            positions.append(match.start())
        require(positions == sorted(positions), f"{rel_path} fixed template slot mismatch: market sections must follow 01/02/03/04 order")
        require(report_html.count('data-cosmo-relation="') >= 15, f"{rel_path} fixed template slot mismatch: COSMO must render all 15 relation cards")
        require(report_html.count('class="cosmo-tag-terms"') >= 15, f"{rel_path} fixed template slot mismatch: COSMO relation cards must render tag chips")
        visible_cosmo_text = normalized_visible_text(
            re.sub(r"<[^>]+>", " ", re.sub(r"<script\b.*?</script>|<style\b.*?</style>", " ", report_html, flags=re.I | re.S))
        )
        raw_relation_code_re = re.compile(r"\b(?:USED_FOR|USED_TO|USED_AS|USED_ON|USED_IN|USED_WITH|USED_BY|CAPABLE_OF|IS_A)[A-Z_]*\b|\bx(?:WANT|INTERSTED_IN|Is_A)\b|\bREL_\d+\b")
        visible_slot_id_re = re.compile(r"\b(?:P0[1-8]|U0[1-9])\b")
        require(raw_relation_code_re.search(visible_cosmo_text) is None, f"{rel_path} fixed template slot mismatch: COSMO relation code must not be visible customer copy")
        require(visible_slot_id_re.search(visible_cosmo_text) is None, f"{rel_path} fixed template slot mismatch: COSMO internal slot IDs must not be visible customer copy")
        require(raw_relation_code_re.search(report_html) is None, f"{rel_path} fixed template slot mismatch: COSMO relation code must not appear in customer HTML attributes")
        require("产品意图" in report_html and "用户意图" in report_html, f"{rel_path} fixed template slot mismatch: COSMO must show 产品意图/用户意图 labels")
        require('class="cosmo-relation-id">产品</b>' in report_html and 'class="cosmo-relation-id">用户</b>' in report_html, f"{rel_path} fixed template slot mismatch: COSMO must show customer-readable product/user markers")
        require('data-dimension="产品标签"' in report_html and 'data-dimension="用户标签"' in report_html, f"{rel_path} fixed template slot mismatch: COSMO must mark product/user dimensions")
        require('class="cosmo-matrix-lanes"' in report_html, f"{rel_path} fixed template slot mismatch: COSMO matrix must use product/user lanes")
        require('class="cosmo-matrix-lane product-lane"' in report_html and 'class="cosmo-matrix-lane user-lane"' in report_html, f"{rel_path} fixed template slot mismatch: COSMO must separate product and user label lanes")
        require("产品标签 · 产品被算法识别为什么" in report_html and "用户标签 · 用户为什么搜索/购买" in report_html, f"{rel_path} fixed template slot mismatch: COSMO lane titles must be customer-readable")
        for cosmo_slot in ["cosmo-matrix", "cosmo-top-list", "cosmo-gap-panel", "cosmo-action-board"]:
            require(cosmo_slot in report_html, f"{rel_path} fixed template slot mismatch: COSMO missing {cosmo_slot}")
        require(report_html.count('class="pricing-card') == 3, f"{rel_path} fixed template slot mismatch: pricing-card must be exactly 3")
        require(report_html.count('class="prompt-card') == 3, f"{rel_path} fixed template slot mismatch: prompt-card must be exactly 3")
        require('id="pricing"' in report_html and 'id="prompt"' in report_html, f"{rel_path} fixed template slot mismatch: pricing and prompt anchors must be present")
        require("<th>ASIN</th>" in report_html, f"{rel_path} fixed template slot mismatch: competitor table must expose ASIN")
        require('data-allow-asin="competitor-table"' in report_html, f"{rel_path} fixed template slot mismatch: competitor ASIN must be whitelisted")
        has_competitor_image_evidence = (
            "comp-image-strip" in report_html
            or "comp-product-thumb" in report_html
            or "comp-deep-image" in report_html
            or "图片维度未返回可展示 URL" in report_html
        )
        require(has_competitor_image_evidence, f"{rel_path} fixed template slot mismatch: 竞品图片或图片诊断槽位缺失")
    elif style == "lifecycle-strategy-report-v2":
        require("ecosystem-chart-grid" in report_html, f"{rel_path} fixed template slot mismatch: ecosystem two-chart grid missing")
        require('id="sunburst"' in report_html and 'id="priorityChart"' in report_html, f"{rel_path} fixed template slot mismatch: lifecycle charts missing")
        require(report_html.count('class="sku-strategy-card') >= 5, f"{rel_path} fixed template slot mismatch: SKU strategy cards must render all five standard slots")
        require(report_html.count('class="phase-card') >= 6, f"{rel_path} fixed template slot mismatch: roadmap phase/action cards must render all six standard slots")
        require("roadmap-phase-grid" in report_html and "roadmap-action-grid" in report_html, f"{rel_path} fixed template slot mismatch: roadmap two-grid layout missing")
        require(report_html.count('class="filter-btn') >= 7, f"{rel_path} fixed template slot mismatch: SKU filter buttons must match seven-slot reference controls")
    elif style == "demand-gap-report-v2":
        require("demand-sentiment-columns" in report_html, f"{rel_path} fixed template slot mismatch: sentiment columns missing")
        require("正面反馈" in report_html and "负面反馈" in report_html, f"{rel_path} fixed template slot mismatch: positive/negative headings missing")
        require(report_html.count('class="demand-evidence-card joy') == 6, f"{rel_path} fixed template slot mismatch: positive voice cards must be exactly 6")
        require(report_html.count('class="demand-evidence-card pain') == 6, f"{rel_path} fixed template slot mismatch: negative voice cards must be exactly 6")
        require("用户原声证据明细表" in report_html and "evidence-drawer" in report_html, f"{rel_path} fixed template slot mismatch: voice evidence drawer missing")
    validate_template_slot_contract(rel_path, report_html, style)


def style_to_slot_report_key(style: str) -> str:
    return {
        "market-depth-report-v2": "market_depth",
        "lifecycle-strategy-report-v2": "lifecycle_strategy",
        "demand-gap-report-v2": "demand_gap",
    }[style]


def count_class_signature(report_html: str, class_signature: str) -> int:
    required_classes = [re.escape(part) for part in class_signature.split() if part]
    if not required_classes:
        return 0
    pattern = r"class=[\"'][^\"']*" + r"[^\"']*".join(rf"\b{part}\b" for part in required_classes) + r"[^\"']*[\"']"
    return len(re.findall(pattern, report_html, flags=re.I))


def validate_template_slot_contract(rel_path: str, report_html: str, style: str) -> None:
    report_key = style_to_slot_report_key(style)
    contract = (slot_contract().get("reports") or {}).get(report_key) or {}
    require(contract, f"{rel_path} missing fixed slot contract for {report_key}")
    for html_id in contract.get("required_ids") or []:
        require(
            re.search(rf"\bid=[\"']{re.escape(str(html_id))}[\"']", report_html, flags=re.I) is not None,
            f"{rel_path} fixed slot contract missing id: {html_id}",
        )
    for text in contract.get("required_text") or []:
        require(str(text) in report_html, f"{rel_path} fixed slot contract missing required text: {text}")
    cursor = -1
    for marker in contract.get("required_ordered_markers") or []:
        marker_text = str(marker)
        marker_pos = report_html.find(marker_text)
        require(marker_pos >= 0, f"{rel_path} fixed slot contract missing ordered marker: {marker_text}")
        require(marker_pos > cursor, f"{rel_path} fixed slot contract marker order regression: {marker_text}")
        cursor = marker_pos
    for class_name, expected in (contract.get("exact_class_counts") or {}).items():
        actual = count_class_signature(report_html, str(class_name))
        require(actual == int(expected), f"{rel_path} fixed slot contract {class_name} count {actual} != {expected}")
    for class_name, minimum in (contract.get("minimum_class_counts") or {}).items():
        actual = count_class_signature(report_html, str(class_name))
        require(actual >= int(minimum), f"{rel_path} fixed slot contract {class_name} count {actual} < {minimum}")
    for group in contract.get("required_component_groups") or []:
        require(str(group) in report_html, f"{rel_path} fixed slot contract missing component group: {group}")
    for scope in contract.get("required_customer_scopes") or []:
        require(str(scope) in report_html, f"{rel_path} fixed slot contract missing scoped customer marker: {scope}")
    for scope in contract.get("allowed_customer_scopes") or []:
        require(str(scope) in report_html, f"{rel_path} fixed slot contract missing allowed customer marker: {scope}")


def validate_interactive_dom(html_docs: dict[str, str]) -> None:
    combined = "\n".join(html_docs.values())
    if "mobile_nav" in INTERACTIVE_FEATURES:
        require("site-nav" in combined and "site-nav-toggle" in combined, "interactive_features declares mobile_nav but site nav DOM is missing")
    if {"table_filter", "table_sort"} & INTERACTIVE_FEATURES:
        require("<table" in combined and "evidence-table" in combined, "interactive_features declares table behavior but report tables are missing")
    if "table_filter" in INTERACTIVE_FEATURES:
        require("filter-bar" in combined and "filter-btn" in combined and "data-filter" in combined, "interactive_features declares table_filter but filter DOM is missing")
    if "tabs" in INTERACTIVE_FEATURES:
        require("data-tabs" in combined and "data-tab-target" in combined and "data-tab-panel" in combined, "interactive_features declares tabs but tab DOM is missing")
    if "evidence_drawer" in INTERACTIVE_FEATURES:
        require("evidence-drawer" in combined, "interactive_features declares evidence_drawer but drawer DOM is missing")
    if "chart_linking" in INTERACTIVE_FEATURES:
        require("mini-chart" in combined and "bar-row" in combined, "interactive_features declares chart_linking but chart DOM is missing")


def validate_critic_outputs(report_dir: Path, data_pack: dict[str, Any]) -> None:
    review = load_json(report_dir / "analysis/critic_review.json")
    plan = load_json(report_dir / "analysis/refinement_plan.json")
    summary_text = (report_dir / "analysis/critic_summary.md").read_text(encoding="utf-8")
    require(isinstance(review, dict), "critic_review.json must be an object")
    for key in ["pass", "score", "grade", "blocking_issues", "report_issues", "data_confidence", "suggestions", "refinement_targets"]:
        require(key in review, f"critic_review.json missing {key}")
    require(isinstance(review["pass"], bool), "critic_review.pass must be boolean")
    require(isinstance(review["score"], (int, float)) and 0 <= review["score"] <= 100, "critic_review.score must be 0-100")
    require(isinstance(review.get("round_id"), int), "critic_review.round_id must be an integer")
    require(isinstance(review.get("findings"), list), "critic_review.findings must be a list")
    require(isinstance(review["blocking_issues"], list), "critic_review.blocking_issues must be a list")
    require(isinstance(review.get("resolved_findings"), list), "critic_review.resolved_findings must be a list")
    require(isinstance(review.get("remaining_findings"), list), "critic_review.remaining_findings must be a list")
    require(isinstance(review["refinement_targets"], list), "critic_review.refinement_targets must be a list")
    require(review["pass"] is True, "critic_review.pass must be true before final delivery validation")
    require(isinstance(plan, dict), "refinement_plan.json must be an object")
    require(plan.get("status") == "accepted", "refinement_plan.json status must be accepted before final delivery validation")
    require(plan.get("max_refinement_rounds") == 2, "refinement_plan.json must cap max_refinement_rounds at 2")
    require(isinstance(plan.get("operations") or [], list), "refinement_plan.json operations must be a list")
    require("data/normalized/normalized_data_pack.json" not in json.dumps(plan.get("refinement_targets") or [], ensure_ascii=False), "refinement targets must not rewrite normalized facts")
    require("data/normalized/normalized_data_pack.json" not in json.dumps(plan.get("operations") or [], ensure_ascii=False), "refinement operations must not rewrite normalized facts")
    for token in ["# Critic Summary", "readiness:", "final_pass:", "final_score:", "final_decision:", "remaining_findings:", "Guardrails"]:
        require(token in summary_text, f"critic_summary.md missing {token}")
    require("must not claim delivery completion" in summary_text, "critic_summary.md must state failed critic rounds cannot be delivered as complete")
    if plan.get("applied_operations"):
        history_path = report_dir / "analysis/refinement_history.jsonl"
        require(history_path.exists(), "applied critic refinements require analysis/refinement_history.jsonl")
        history_text = history_path.read_text(encoding="utf-8")
        require('"pass": false' in history_text and '"pass": true' in history_text, "refinement_history.jsonl must record failed and passing critic rounds")
    if not review["pass"]:
        failed_cases = report_dir / "training_data/failed_cases.jsonl"
        require(failed_cases.exists(), "failed critic review must append training_data/failed_cases.jsonl")


def validate_child_skill_invocations(report_dir: Path, invocations: Any, rel_path: str) -> None:
    require(isinstance(invocations, dict), f"{rel_path} missing child_skill_invocations")
    for key, module_path in CHILD_SKILLS.items():
        payload = invocations.get(key)
        require(isinstance(payload, dict), f"{rel_path} child_skill_invocations missing {key}")
        require(payload.get("module") == module_path, f"{rel_path} child invocation {key}.module mismatch")
        require(payload.get("status") == "rendered", f"{rel_path} child invocation {key}.status must be rendered")
        expected_dispatch = "subprocess_child_renderer" if key in SUBPROCESS_REPORT_KEYS else "subprocess_critic_child"
        require(payload.get("dispatch_mode") == expected_dispatch, f"{rel_path} child invocation {key}.dispatch_mode mismatch")
        require(payload.get("data_policy") == "read_only_normalized_data_pack", f"{rel_path} child invocation {key}.data_policy mismatch")
        require("data/normalized/normalized_data_pack.json" in (payload.get("inputs") or []), f"{rel_path} child invocation {key} missing normalized data input")
        if key in SUBPROCESS_CHILD_KEYS:
            require(payload.get("invocation_log") == "analysis/child_skill_invocation_log.json", f"{rel_path} child invocation {key} missing invocation_log")
        for output in payload.get("outputs") or []:
            require((report_dir / output).exists(), f"{rel_path} child invocation {key} output missing: {output}")
        renderer = payload.get("renderer")
        template = payload.get("template")
        require(renderer and ((SKILL_DIR / renderer).exists() or (SKILL_DIR / "scripts" / Path(renderer).name).exists()), f"{rel_path} child invocation {key} renderer missing: {renderer}")
        require(template and (SKILL_DIR / template).exists(), f"{rel_path} child invocation {key} template missing: {template}")


def validate_child_skill_invocation_log(report_dir: Path) -> None:
    log = load_json(report_dir / "analysis/child_skill_invocation_log.json")
    require(isinstance(log, list), "child_skill_invocation_log.json must be a list")
    require(len(log) == len(SUBPROCESS_CHILD_KEYS), "child_skill_invocation_log.json must contain exactly one entry per subprocess child")
    by_module = {entry.get("module"): entry for entry in log if isinstance(entry, dict)}
    require(len(by_module) == len(log), "child_skill_invocation_log.json contains duplicate module entries")
    for key in SUBPROCESS_CHILD_KEYS:
        module_path = CHILD_SKILLS[key]
        entry = by_module.get(module_path)
        require(isinstance(entry, dict), f"child_skill_invocation_log.json missing module {module_path}")
        expected_dispatch = "subprocess_child_renderer" if key in SUBPROCESS_REPORT_KEYS else "subprocess_critic_child"
        require(entry.get("dispatch_mode") == expected_dispatch, f"child invocation log {key} dispatch_mode mismatch")
        require(entry.get("returncode") == 0, f"child renderer {key} did not exit cleanly")
        renderer = entry.get("renderer")
        require(isinstance(renderer, str) and renderer, f"child invocation log {key} missing renderer")
        renderer_path = SKILL_DIR / renderer
        require(renderer_path.exists(), f"child invocation log {key} renderer missing: {renderer}")
        require(entry.get("renderer_sha256") == file_sha256(renderer_path), f"child invocation log {key} renderer_sha256 mismatch")
        command = entry.get("command")
        require(isinstance(command, list) and renderer in command, f"child invocation log {key} command must include renderer")
        require(entry.get("started_at") and entry.get("finished_at"), f"child invocation log {key} missing timestamps")
        require(entry.get("cwd"), f"child invocation log {key} missing cwd")
        if key in SUBPROCESS_REPORT_KEYS:
            output = entry.get("output")
            require(output == CHILD_REPORTS[key]["path"], f"child invocation log {key} output mismatch")
            output_path = report_dir / str(output)
            require(output_path.exists(), f"child invocation log {key} output missing: {output}")
            require(entry.get("output_sha256") == file_sha256(output_path), f"child invocation log {key} output_sha256 mismatch")
        else:
            outputs = entry.get("outputs")
            output_sha = entry.get("output_sha256")
            require(
                isinstance(outputs, list)
                and "analysis/critic_review.json" in outputs
                and "analysis/refinement_plan.json" in outputs
                and "analysis/critic_summary.md" in outputs,
                "critic invocation log missing outputs",
            )
            require(isinstance(output_sha, dict), "critic invocation log missing output_sha256 map")
            for output in outputs:
                output_path = report_dir / str(output)
                require(output_path.exists(), f"critic invocation output missing: {output}")
                require(output_sha.get(output) == file_sha256(output_path), f"critic invocation output_sha256 mismatch: {output}")


def validate_delivery(report_dir: Path) -> None:
    delivery = load_json(report_dir / "output/delivery_result.json")
    readiness = assess_data_readiness(report_dir, "auto")
    expected_readiness = readiness_summary_for_contract(readiness)
    require(isinstance(delivery, dict), "delivery_result.json must be an object")
    status = delivery.get("status")
    blocked_delivery = status == "blocked"
    require(status in {"complete", "partial", "blocked"}, "delivery_result.json status must be complete, partial, or blocked")
    delivery_readiness = delivery.get("data_readiness")
    require(isinstance(delivery_readiness, dict), "delivery_result.json missing data_readiness summary")
    require(delivery_readiness.get("path") == "data/normalized/data_readiness_report.json", "delivery_result.json data_readiness.path mismatch")
    for key, expected in expected_readiness.items():
        require(readiness_contract_value_matches(key, delivery_readiness.get(key), expected), f"delivery_result.json data_readiness.{key} mismatch")
    if blocked_delivery:
        require(
            not (delivery_readiness.get("acceptance_ready") or delivery_readiness.get("partial_report_ready")),
            "blocked delivery cannot carry ready data_readiness",
        )
        require(str(delivery.get("decision") or "").casefold() != "go", "blocked delivery cannot carry an unconditional Go decision")
        require(delivery_readiness.get("blocking_gap_count", 0) > 0, "blocked delivery must include blocking gaps")
    html_reports = delivery.get("html_reports")
    require(isinstance(html_reports, dict), "delivery_result.json missing html_reports mapping")
    require(html_reports.get("index") == BUNDLE_INDEX_REPORT, f"delivery_result.json html_reports.index must be {BUNDLE_INDEX_REPORT}")
    require(html_reports.get("compat_index") == COMPAT_INDEX_REPORT, f"delivery_result.json html_reports.compat_index must be {COMPAT_INDEX_REPORT}")
    require(delivery.get("html_bundle_dir") == HTML_BUNDLE_DIR, f"delivery_result.json html_bundle_dir must be {HTML_BUNDLE_DIR}")
    for key, spec in CHILD_REPORTS.items():
        require(html_reports.get(key) == spec["path"], f"delivery_result.json html_reports.{key} must be {spec['path']}")
    require(delivery.get("child_skills") == CHILD_SKILLS, "delivery_result.json child_skills must declare internal report modules and critic")
    if blocked_delivery:
        invocations = delivery.get("child_skill_invocations")
        require(isinstance(invocations, dict), "blocked delivery must declare diagnostic child_skill_invocations")
        for key, module_path in CHILD_SKILLS.items():
            entry = invocations.get(key)
            require(isinstance(entry, dict), f"blocked delivery child invocation missing {key}")
            require(entry.get("module") == module_path, f"blocked delivery child invocation {key} module mismatch")
            require(entry.get("status") == "diagnostic_template", f"blocked delivery child invocation {key} must use diagnostic_template status")
            require(entry.get("dispatch_mode") == "main_renderer_diagnostic", f"blocked delivery child invocation {key} dispatch_mode mismatch")
    else:
        validate_child_skill_invocations(report_dir, delivery.get("child_skill_invocations"), "delivery_result.json")
        validate_child_skill_invocation_log(report_dir)
    require(delivery.get("site_assets") == SITE_ASSETS, "delivery_result.json site_assets must declare static site assets")
    critic = delivery.get("critic_review")
    require(isinstance(critic, dict), "delivery_result.json missing critic_review summary")
    require(critic.get("path") == "analysis/critic_review.json", "delivery_result.json critic_review.path mismatch")
    require(critic.get("refinement_plan") == "analysis/refinement_plan.json", "delivery_result.json critic_review.refinement_plan mismatch")
    require(critic.get("summary") == "analysis/critic_summary.md", "delivery_result.json critic_review.summary mismatch")
    require(critic.get("max_refinement_rounds") == 2, "delivery_result.json critic max_refinement_rounds must be 2")
    if blocked_delivery:
        require(critic.get("pass") is False, "blocked delivery critic_review.pass must be false")
    require(
        not (critic.get("pass") is True and not (delivery_readiness.get("acceptance_ready") or delivery_readiness.get("partial_report_ready"))),
        "critic pass cannot override failed data readiness",
    )
    if delivery_readiness.get("partial_report_ready"):
        require(delivery.get("status") == "partial", "partial_report_ready delivery must use partial status")
        require(str(delivery.get("decision") or "").casefold() != "go", "partial_report_ready delivery cannot carry an unconditional Go decision")
    features = set(delivery.get("interactive_features") or [])
    require(INTERACTIVE_FEATURES.issubset(features), "delivery_result.json missing required interactive_features")
    asin_scope = set(delivery.get("asin_display_scope") or [])
    required_asin_scopes = {"competitor_table", "benchmark_sniper", "profit_model", "demand_target_anchor", "sku_reference"}
    missing_asin_scopes = sorted(required_asin_scopes - asin_scope)
    require(
        not missing_asin_scopes,
        f"delivery_result.json asin_display_scope must include {', '.join(missing_asin_scopes)}",
    )
    cleaning = delivery.get("cleaning_summary")
    require(isinstance(cleaning, dict), "delivery_result.json missing cleaning_summary")
    require(isinstance(cleaning.get("removed_counts"), dict), "delivery_result.json cleaning_summary missing removed_counts")
    cosmo_summary = delivery.get("cosmo_alexa_tags")
    require(isinstance(cosmo_summary, dict), "delivery_result.json missing cosmo_alexa_tags summary")
    require(cosmo_summary.get("path") == "analysis/cosmo_alexa_tags.json", "delivery_result.json cosmo_alexa_tags.path mismatch")
    require(cosmo_summary.get("relation_total") == len(COSMO_ALEXA_RELATION_TYPES), "delivery_result.json cosmo_alexa_tags relation_total mismatch")
    lifecycle_summary = delivery.get("lifecycle_sku_pool_summary")
    require(isinstance(lifecycle_summary, dict), "delivery_result.json missing lifecycle_sku_pool_summary")
    require(isinstance(lifecycle_summary.get("sku_candidate_pool"), int), "delivery_result.json lifecycle_sku_pool_summary.sku_candidate_pool must be an integer")

    site_data = load_json(report_dir / SITE_ASSETS["data"])
    require(site_data.get("child_skills") == CHILD_SKILLS, "report-data.json child_skills mismatch")
    site_readiness = site_data.get("readiness")
    require(isinstance(site_readiness, dict), "report-data.json missing readiness summary")
    for key, expected in expected_readiness.items():
        require(readiness_contract_value_matches(key, site_readiness.get(key), expected), f"report-data.json readiness.{key} mismatch")
    require(INTERACTIVE_FEATURES.issubset(set(site_data.get("interactive_features") or [])), "report-data.json missing interactive features")
    for key in ["before_counts", "after_counts", "removed_counts"]:
        require(isinstance((site_data.get("cleaning_summary") or {}).get(key), dict), f"report-data.json cleaning_summary missing {key}")

    report_brief = load_json(report_dir / "report_brief.json")
    require(report_brief.get("child_skills") == CHILD_SKILLS, "report_brief.json child_skills mismatch")
    validate_child_skill_invocations(report_dir, report_brief.get("child_skill_invocations"), "report_brief.json")
    require((report_brief.get("static_site") or {}).get("bundle_dir") == HTML_BUNDLE_DIR, "report_brief.json static_site.bundle_dir mismatch")


def validate(report_dir: Path) -> None:
    validate_required_files(report_dir)
    data_pack = load_json(report_dir / "data/data_pack.json")
    analysis_plan = load_json(report_dir / "analysis/analysis_plan.json")
    delivery = load_json(report_dir / "output/delivery_result.json")
    require(isinstance(data_pack, dict), "data_pack.json must be an object")
    require(isinstance(analysis_plan, dict), "analysis_plan.json must be an object")

    source_ids = validate_sources(data_pack)
    validate_entity_lineage(data_pack, source_ids)
    validate_data_gaps_contract(data_pack)
    validate_data_readiness(report_dir, delivery)
    validate_normalized_data_pack_consistency(report_dir, data_pack)
    validate_research_relevance_gate(data_pack)
    validate_quality_consistency(data_pack, delivery)
    validate_analysis_plan(analysis_plan, source_ids)
    validate_cosmo_alexa_tags(report_dir)
    validate_lifecycle_strategy_analysis(report_dir, data_pack)
    validate_supply_html_readiness_alignment(report_dir)
    validate_text_artifacts(report_dir, source_ids, data_pack)
    validate_site_asset_contract(report_dir)
    validate_customer_visible_assets(report_dir, data_pack)
    validate_view_models(report_dir, data_pack)
    validate_critic_outputs(report_dir, data_pack)
    validate_delivery(report_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate amz-market-research-orchestrated v2 report artifacts.")
    parser.add_argument("--dir", required=True, help="Report directory containing data/, analysis/, and output/.")
    args = parser.parse_args(argv)

    report_dir = Path(args.dir)
    try:
        validate(report_dir)
    except ValidationError as exc:
        print(f"validate_failed: {exc}", file=sys.stderr)
        return 1

    print("validate_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
