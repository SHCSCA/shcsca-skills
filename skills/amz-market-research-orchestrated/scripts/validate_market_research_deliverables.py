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

from normalize_data_pack import (
    category_dedupe_key,
    keyword_dedupe_key,
    product_dedupe_key,
    review_dedupe_key,
    supplier_dedupe_key,
    tiktok_product_dedupe_key,
    tiktok_video_dedupe_key,
    web_document_dedupe_key,
)
from check_data_readiness import assess as assess_data_readiness
from site_assets import COMPAT_INDEX_REPORT, HTML_BUNDLE_DIR, INTERACTIVE_FEATURES as SITE_INTERACTIVE_FEATURES, SITE_ASSETS

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATE_BASELINE_MANIFEST = SKILL_DIR / "references" / "template-baseline-manifest.json"
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

INDEX_STYLE_MARKER = "three-report-index-v2"
MIN_KEYWORD_SAMPLE_COUNT = 1000

CHILD_REPORTS = {
    "market_depth": {
        "path": f"{HTML_BUNDLE_DIR}/market-depth-report.html",
        "filename": "market-depth-report.html",
        "style": "market-depth-report-v2",
        "sections": [
            "大盘仪表盘 · Market Dashboard",
            "Top 竞品全景扫描",
            "VOC 体验深潜 · 痛点 × 爽点雷达",
            "标杆竞品狙击拆解",
            "新品狙击企划 · Product Definition",
            "建议定价策略",
            "视觉与包装指导 · Visual Direction",
            "AI生图 Prompt · 可直接使用",
            "供应链成本估算 · 1688大盘数据",
        ],
        "terms": ["价格带销量分布图", "竞品狙击结论", "定价战略核心逻辑", "AI生图 Prompt", "供应链核心结论"],
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
            "研究对象概述",
            "决策看板",
            "市场痛点全景图（$APPEALS）",
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
        "grid-3",
        "chart-interpretation",
    ],
}

CUSTOMER_HTML_REQUIRED_TERMS = ["证据强度", "数据覆盖", "数据缺口", "置信等级", "建议动作"]
MARKET_DEPTH_BANNED_PLACEHOLDERS = ["样本", "样品", "补数", "待补", "待验证", "待评分", "待修复", "待样品"]

CUSTOMER_HTML_BANNED_LITERALS = [
    "source_id",
    "source_ids",
    "used_source_ids",
    "Product ID",
    "product_id",
    "raw_path",
    "provider",
    "method_id",
    "数据血缘",
    "来源",
]

CUSTOMER_HTML_BANNED_PATTERNS = [
    re.compile(r"\bsrc[_-][\w\u4e00-\u9fff-]+\b", re.IGNORECASE),
    re.compile(r"\bsf[_-][\w\u4e00-\u9fff-]+\b", re.IGNORECASE),
    re.compile(r"\bB0[A-Z0-9]{8}\b"),
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
        entities = data_pack[key]
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


def validate_data_readiness(report_dir: Path) -> None:
    readiness = assess_data_readiness(report_dir, "auto")
    modules = ", ".join(gap.get("module", "unknown") for gap in readiness.get("blocking_gaps") or [])
    require(
        readiness.get("acceptance_ready") is True,
        f"data readiness must pass before final delivery validation: {modules}",
    )

    recorded_path = report_dir / "data" / "normalized" / "data_readiness_report.json"
    if recorded_path.exists():
        recorded = load_json(recorded_path)
        require(isinstance(recorded, dict), "data_readiness_report.json must be an object")
        require(recorded.get("acceptance_ready") is True, "data_readiness_report.json cannot be false for final delivery validation")
        require(recorded.get("sample_class") == "acceptance_sample", "data_readiness_report.json sample_class must be acceptance_sample")


def readiness_summary_for_contract(readiness: dict[str, Any]) -> dict[str, Any]:
    return {
        "acceptance_ready": readiness.get("acceptance_ready"),
        "sample_class": readiness.get("sample_class"),
        "depth": readiness.get("depth"),
        "blocking_gap_count": len(readiness.get("blocking_gaps") or []),
        "warning_count": len(readiness.get("warnings") or []),
        "counts": readiness.get("counts") or {},
        "supplier_quote_gate": readiness.get("supplier_quote_gate") or {},
    }


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
        r"<span\b(?=[^>]*\bdata-allow-asin=[\"'](?:benchmark-sniper|profit-model)[\"'])[^>]*>\s*B0[A-Z0-9]{8}\s*</span>",
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
    for literal in CUSTOMER_HTML_BANNED_LITERALS:
        require(literal not in html_for_safety, f"{rel_path} customer HTML leaks technical identifier: {literal}")

    for pattern in CUSTOMER_HTML_BANNED_PATTERNS:
        match = pattern.search(html_for_safety)
        if match is not None:
            raise ValidationError(f"{rel_path} customer HTML leaks technical identifier: {match.group(0)}")

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


def validate_html_basics(rel_path: str, html_doc: str) -> None:
    html_lower = html_doc.lower()
    require("<html" in html_lower or "<!doctype html" in html_lower, f"{rel_path} is not a standalone HTML document")
    require("<pre" not in html_lower, f"{rel_path} must not wrap Markdown in a <pre> block")
    require("markdown-body" not in html_lower, f"{rel_path} must not be a Markdown-rendered wrapper")
    require(
        re.search(r"\n\s*\|.+\|\s*\n\s*\|[-:\s|]+\|", html_doc) is None,
        f"{rel_path} contains raw Markdown table syntax",
    )
    require("<style" in html_lower, f"{rel_path} must include self-contained CSS")
    require("assets/report.css" in html_lower, f"{rel_path} must link shared assets/report.css")
    require("assets/report.js" in html_lower, f"{rel_path} must load shared assets/report.js")


def validate_index_report(report_html: str, rel_path: str, required_links: list[str], data_pack: dict[str, Any], require_same_folder: bool = False) -> None:
    validate_html_basics(rel_path, report_html)
    validate_customer_html(rel_path, report_html, data_pack)
    require(
        re.search(r"data-report-style=['\"]three-report-index-v2['\"]", report_html) is not None,
        f"{rel_path} missing data-report-style=\"{INDEX_STYLE_MARKER}\"",
    )
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
    require(
        re.search(rf"data-report-style=['\"]{re.escape(spec['style'])}['\"]", report_html) is not None,
        f"{rel_path} missing data-report-style=\"{spec['style']}\"",
    )
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

    for section_name in spec["sections"]:
        require(section_name in report_html, f"{rel_path} missing required dashboard section: {section_name}")

    for term in spec["terms"]:
        require(term in report_html, f"{rel_path} missing required mapped-data term: {term}")
    if spec["style"] == "market-depth-report-v2":
        for placeholder in MARKET_DEPTH_BANNED_PLACEHOLDERS:
            require(placeholder not in report_html, f"{rel_path} customer HTML contains placeholder or non-final data wording: {placeholder}")


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
    require(delivery.get("status") in {"complete", "partial"}, "delivery_result.json status must be complete or partial")
    delivery_readiness = delivery.get("data_readiness")
    require(isinstance(delivery_readiness, dict), "delivery_result.json missing data_readiness summary")
    require(delivery_readiness.get("path") == "data/normalized/data_readiness_report.json", "delivery_result.json data_readiness.path mismatch")
    for key, expected in expected_readiness.items():
        require(delivery_readiness.get(key) == expected, f"delivery_result.json data_readiness.{key} mismatch")
    html_reports = delivery.get("html_reports")
    require(isinstance(html_reports, dict), "delivery_result.json missing html_reports mapping")
    require(html_reports.get("index") == BUNDLE_INDEX_REPORT, f"delivery_result.json html_reports.index must be {BUNDLE_INDEX_REPORT}")
    require(html_reports.get("compat_index") == COMPAT_INDEX_REPORT, f"delivery_result.json html_reports.compat_index must be {COMPAT_INDEX_REPORT}")
    require(delivery.get("html_bundle_dir") == HTML_BUNDLE_DIR, f"delivery_result.json html_bundle_dir must be {HTML_BUNDLE_DIR}")
    for key, spec in CHILD_REPORTS.items():
        require(html_reports.get(key) == spec["path"], f"delivery_result.json html_reports.{key} must be {spec['path']}")
    require(delivery.get("child_skills") == CHILD_SKILLS, "delivery_result.json child_skills must declare internal report modules and critic")
    validate_child_skill_invocations(report_dir, delivery.get("child_skill_invocations"), "delivery_result.json")
    validate_child_skill_invocation_log(report_dir)
    require(delivery.get("site_assets") == SITE_ASSETS, "delivery_result.json site_assets must declare static site assets")
    critic = delivery.get("critic_review")
    require(isinstance(critic, dict), "delivery_result.json missing critic_review summary")
    require(critic.get("path") == "analysis/critic_review.json", "delivery_result.json critic_review.path mismatch")
    require(critic.get("refinement_plan") == "analysis/refinement_plan.json", "delivery_result.json critic_review.refinement_plan mismatch")
    require(critic.get("summary") == "analysis/critic_summary.md", "delivery_result.json critic_review.summary mismatch")
    require(critic.get("max_refinement_rounds") == 2, "delivery_result.json critic max_refinement_rounds must be 2")
    require(not (critic.get("pass") is True and not delivery_readiness.get("acceptance_ready")), "critic pass cannot override failed data readiness")
    features = set(delivery.get("interactive_features") or [])
    require(INTERACTIVE_FEATURES.issubset(features), "delivery_result.json missing required interactive_features")
    cleaning = delivery.get("cleaning_summary")
    require(isinstance(cleaning, dict), "delivery_result.json missing cleaning_summary")
    require(isinstance(cleaning.get("removed_counts"), dict), "delivery_result.json cleaning_summary missing removed_counts")

    site_data = load_json(report_dir / SITE_ASSETS["data"])
    require(site_data.get("child_skills") == CHILD_SKILLS, "report-data.json child_skills mismatch")
    site_readiness = site_data.get("readiness")
    require(isinstance(site_readiness, dict), "report-data.json missing readiness summary")
    for key, expected in expected_readiness.items():
        require(site_readiness.get(key) == expected, f"report-data.json readiness.{key} mismatch")
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
    validate_data_readiness(report_dir)
    validate_normalized_data_pack_consistency(report_dir, data_pack)
    validate_quality_consistency(data_pack, delivery)
    validate_analysis_plan(analysis_plan, source_ids)
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
