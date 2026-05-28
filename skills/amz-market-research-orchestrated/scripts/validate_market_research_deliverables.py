#!/usr/bin/env python3
"""Validate amz-market-research-orchestrated v2 report artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


HTML_BUNDLE_DIR = "output/html_reports"
BUNDLE_INDEX_REPORT = f"{HTML_BUNDLE_DIR}/report.html"
COMPAT_INDEX_REPORT = "output/report.html"

REQUIRED_FILES = [
    "data/data_pack.json",
    "data/lineage.md",
    "analysis/analysis_plan.json",
    COMPAT_INDEX_REPORT,
    BUNDLE_INDEX_REPORT,
    f"{HTML_BUNDLE_DIR}/market-depth-report.html",
    f"{HTML_BUNDLE_DIR}/lifecycle-strategy-report.html",
    f"{HTML_BUNDLE_DIR}/demand-gap-report.html",
    "output/report.md",
    "output/delivery_result.json",
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
            "大盘结论",
            "需求结构",
            "竞品格局",
            "VOC 洞察",
            "标杆打法",
            "机会定义",
            "TikTok 内容信号",
            "1688 供应链判断",
            "风险与行动摘要",
        ],
        "terms": ["可进入性评分", "价格带机会", "竞争强度", "关键切入口", "商业含义"],
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
            "$APPEALS 痛点图",
            "满意度鸿沟",
            "KANO × JTBD",
            "用户原声",
            "需求优先级",
        ],
        "terms": ["KANO", "JTBD", "心智断层", "负面触发点", "转化机会"],
    },
}

BUNDLE_INDEX_REQUIRED_LINKS = [spec["filename"] for spec in CHILD_REPORTS.values()]
COMPAT_INDEX_REQUIRED_LINKS = [f"html_reports/{spec['filename']}" for spec in CHILD_REPORTS.values()]

HTML_REQUIRED_CLASSES = [
    "report-header",
    "kpi-grid",
    "section-number",
    "evidence-table",
    "insight-table",
    "mini-chart",
    "chart-container",
    "insight-box",
    "conclusion",
    "deep-dive-grid",
    "comp-deep-card",
]

CUSTOMER_HTML_REQUIRED_TERMS = ["证据强度", "样本覆盖", "数据缺口", "建议动作"]

CUSTOMER_HTML_BANNED_LITERALS = [
    "source_id",
    "source_ids",
    "used_source_ids",
    "Product ID",
    "product_id",
    "raw_path",
    "provider",
    "tool",
    "method_id",
    "ASIN",
    "数据血缘",
    "来源",
]

CUSTOMER_HTML_BANNED_PATTERNS = [
    re.compile(r"\bsrc[_-][A-Za-z0-9_-]+\b", re.IGNORECASE),
    re.compile(r"\bB0[A-Z0-9]{8}\b"),
    re.compile(r"\bdata/raw/[^\s<>'\"]+", re.IGNORECASE),
    re.compile(r"[A-Za-z]:\\[^\s<>'\"]+"),
]

REVIEW_TEXT_KEYS = {"title", "text", "content", "body", "comment"}


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
    tracked_keys = {"source_id", "source_ids", "provider", "tool", "raw_path", "path", "asin", "product_id", "video_id"}

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


def validate_customer_html(rel_path: str, html_doc: str, data_pack: dict[str, Any]) -> None:
    for literal in CUSTOMER_HTML_BANNED_LITERALS:
        require(literal not in html_doc, f"{rel_path} customer HTML leaks technical identifier: {literal}")

    for pattern in CUSTOMER_HTML_BANNED_PATTERNS:
        match = pattern.search(html_doc)
        if match is not None:
            raise ValidationError(f"{rel_path} customer HTML leaks technical identifier: {match.group(0)}")

    for value in technical_values_from_data_pack(data_pack):
        require(value not in html_doc, f"{rel_path} customer HTML leaks technical identifier: {value}")

    for value in raw_english_review_values(data_pack):
        require(value not in html_doc, f"{rel_path} customer HTML leaks raw English review text: {value[:72]}")

    for term in CUSTOMER_HTML_REQUIRED_TERMS:
        require(term in html_doc, f"{rel_path} customer HTML missing required analysis term: {term}")


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
    require(report_html.count("<section") >= len(spec["sections"]), f"{rel_path} must use semantic section blocks")
    require(report_html.count("<table") >= 3, f"{rel_path} must render analysis as HTML tables")
    for class_name in HTML_REQUIRED_CLASSES:
        require(class_name in report_html, f"{rel_path} missing required dashboard class: {class_name}")

    for section_name in spec["sections"]:
        require(section_name in report_html, f"{rel_path} missing required dashboard section: {section_name}")

    for term in spec["terms"]:
        require(term in report_html, f"{rel_path} missing required mapped-data term: {term}")


def validate_delivery(report_dir: Path) -> None:
    delivery = load_json(report_dir / "output/delivery_result.json")
    require(isinstance(delivery, dict), "delivery_result.json must be an object")
    require(delivery.get("status") in {"complete", "partial"}, "delivery_result.json status must be complete or partial")
    html_reports = delivery.get("html_reports")
    require(isinstance(html_reports, dict), "delivery_result.json missing html_reports mapping")
    require(html_reports.get("index") == BUNDLE_INDEX_REPORT, f"delivery_result.json html_reports.index must be {BUNDLE_INDEX_REPORT}")
    require(html_reports.get("compat_index") == COMPAT_INDEX_REPORT, f"delivery_result.json html_reports.compat_index must be {COMPAT_INDEX_REPORT}")
    require(delivery.get("html_bundle_dir") == HTML_BUNDLE_DIR, f"delivery_result.json html_bundle_dir must be {HTML_BUNDLE_DIR}")
    for key, spec in CHILD_REPORTS.items():
        require(html_reports.get(key) == spec["path"], f"delivery_result.json html_reports.{key} must be {spec['path']}")


def validate(report_dir: Path) -> None:
    validate_required_files(report_dir)
    data_pack = load_json(report_dir / "data/data_pack.json")
    analysis_plan = load_json(report_dir / "analysis/analysis_plan.json")
    require(isinstance(data_pack, dict), "data_pack.json must be an object")
    require(isinstance(analysis_plan, dict), "analysis_plan.json must be an object")

    source_ids = validate_sources(data_pack)
    validate_entity_lineage(data_pack, source_ids)
    validate_analysis_plan(analysis_plan, source_ids)
    validate_text_artifacts(report_dir, source_ids, data_pack)
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
