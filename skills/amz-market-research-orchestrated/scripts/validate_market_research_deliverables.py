#!/usr/bin/env python3
"""Validate amz-market-research-orchestrated v2 report artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REQUIRED_FILES = [
    "data/data_pack.json",
    "data/lineage.md",
    "analysis/analysis_plan.json",
    "output/report.html",
    "output/market-depth-report.html",
    "output/lifecycle-strategy-report.html",
    "output/demand-gap-report.html",
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
        "path": "output/market-depth-report.html",
        "style": "market-depth-report-v2",
        "sections": [
            "大盘仪表盘",
            "关键词需求",
            "Top 竞品",
            "VOC 痛点/爽点",
            "标杆竞品深挖",
            "机会判断",
            "TikTok 验证",
            "1688 供应链",
            "Web 风险",
            "数据血缘",
        ],
        "terms": ["关键词中文", "英文关键词", "中文定位", "英文标题", "相关性", "去重"],
    },
    "lifecycle_strategy": {
        "path": "output/lifecycle-strategy-report.html",
        "style": "lifecycle-strategy-report-v2",
        "sections": [
            "战略仪表盘",
            "用户画像",
            "生命周期旅程",
            "四维拓品生态",
            "SKU 执行总表",
            "Bundle 策略",
            "30/60/90 天路线图",
            "风险矩阵",
            "市场数据验证",
        ],
        "terms": ["SKU", "Bundle", "供应链", "复购"],
    },
    "demand_gap": {
        "path": "output/demand-gap-report.html",
        "style": "demand-gap-report-v2",
        "sections": [
            "目标 ASIN/研究对象锚点",
            "决策看板",
            "$APPEALS 痛点全景",
            "满意度鸿沟",
            "KANO × JTBD 机会矩阵",
            "用户原声",
            "需求优先级与证据表",
        ],
        "terms": ["KANO", "JTBD", "source_id"],
    },
}

INDEX_REQUIRED_LINKS = [spec["path"].removeprefix("output/") for spec in CHILD_REPORTS.values()]

HTML_REQUIRED_CLASSES = [
    "report-header",
    "kpi-grid",
    "section-number",
    "evidence-table",
    "mini-chart",
    "chart-container",
    "insight-box",
    "conclusion",
    "deep-dive-grid",
    "comp-deep-card",
    "appendix-table",
]


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


def validate_text_artifacts(report_dir: Path, source_ids: set[str]) -> None:
    report_md = (report_dir / "output/report.md").read_text(encoding="utf-8")
    index_html = (report_dir / "output/report.html").read_text(encoding="utf-8")
    child_htmls = {
        key: (report_dir / spec["path"]).read_text(encoding="utf-8")
        for key, spec in CHILD_REPORTS.items()
    }
    lineage = (report_dir / "data/lineage.md").read_text(encoding="utf-8")
    all_report_text = "\n".join([report_md, index_html, *child_htmls.values()])

    for phrase in BANNED_REPORT_PHRASES:
        require(phrase not in all_report_text, f"Report contains banned phrase: {phrase}")

    if "月销量" in all_report_text:
        require("估算月销量" in all_report_text, "Monthly sales must be labeled as estimated monthly sales")

    require("Go / Watch / No-Go" in report_md or "Go/Watch/No-Go" in report_md, "report.md missing Go / Watch / No-Go section")
    validate_index_report(index_html)
    for key, html_doc in child_htmls.items():
        validate_child_report(CHILD_REPORTS[key]["path"], html_doc, CHILD_REPORTS[key], source_ids)

    missing_lineage = [source_id for source_id in source_ids if source_id not in lineage]
    require(not missing_lineage, f"lineage.md missing source_id entries: {', '.join(missing_lineage)}")

    if source_ids:
        report_texts = [report_md, index_html, *child_htmls.values()]
        require(any(any(source_id in text for text in report_texts) for source_id in source_ids), "Report does not cite any source_id")


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


def validate_index_report(report_html: str) -> None:
    validate_html_basics("output/report.html", report_html)
    require(
        re.search(r"data-report-style=['\"]three-report-index-v2['\"]", report_html) is not None,
        f"output/report.html missing data-report-style=\"{INDEX_STYLE_MARKER}\"",
    )
    require("三合一" in report_html, "output/report.html must describe the three-report bundle")
    for link in INDEX_REQUIRED_LINKS:
        require(link in report_html, f"output/report.html missing child report link: {link}")


def validate_child_report(rel_path: str, report_html: str, spec: dict[str, Any], source_ids: set[str]) -> None:
    validate_html_basics(rel_path, report_html)
    require(
        re.search(rf"data-report-style=['\"]{re.escape(spec['style'])}['\"]", report_html) is not None,
        f"{rel_path} missing data-report-style=\"{spec['style']}\"",
    )
    require(report_html.count("<section") >= len(spec["sections"]), f"{rel_path} must use semantic section blocks")
    require(report_html.count("<table") >= len(spec["sections"]), f"{rel_path} must render evidence as HTML tables")
    for class_name in HTML_REQUIRED_CLASSES:
        require(class_name in report_html, f"{rel_path} missing required dashboard class: {class_name}")

    for section_name in spec["sections"]:
        require(section_name in report_html, f"{rel_path} missing required dashboard section: {section_name}")

    for term in spec["terms"]:
        require(term in report_html, f"{rel_path} missing required mapped-data term: {term}")

    require("source_id" in report_html, f"{rel_path} missing visible source_id label")
    require(
        any(source_id in report_html for source_id in source_ids),
        f"{rel_path} missing visible source_id evidence",
    )


def validate_delivery(report_dir: Path) -> None:
    delivery = load_json(report_dir / "output/delivery_result.json")
    require(isinstance(delivery, dict), "delivery_result.json must be an object")
    require(delivery.get("status") in {"complete", "partial"}, "delivery_result.json status must be complete or partial")
    html_reports = delivery.get("html_reports")
    require(isinstance(html_reports, dict), "delivery_result.json missing html_reports mapping")
    require(html_reports.get("index") == "output/report.html", "delivery_result.json html_reports.index must be output/report.html")
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
    validate_text_artifacts(report_dir, source_ids)
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
