#!/usr/bin/env python3
"""Validate the static template parity contract for HTML market reports."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
MANIFEST = SKILL_DIR / "references" / "template-baseline-manifest.json"
CHECKLIST = SKILL_DIR / "references" / "html-template-parity-checklist.md"
SLOT_CONTRACT = SKILL_DIR / "references" / "html-template-slot-contract.json"
SITE_ASSETS = SCRIPT_DIR / "site_assets.py"
REFERENCE_VISUAL_COMPARE = SCRIPT_DIR / "run_template_reference_visual_compare.py"
ACCEPTANCE_PROOF = SCRIPT_DIR / "run_acceptance_proof.py"
LOCAL_DOWNLOAD_ROOT = Path(r"C:\Users\wz\Downloads\downloadpage")
CANONICAL_DIR = SKILL_DIR / "assets" / "canonical_templates"


BASELINES = {
    "market_depth": {
        "folder": "143101",
        "template": SKILL_DIR / "assets" / "market-depth-template.html",
        "canonical_asset": CANONICAL_DIR / "market-depth-reference.html",
        "report_style": "market-depth-report-v2",
        "css_signals": [
            "report-header",
            "header-meta",
            "kpi-grid",
            "kpi-card",
            "chart-container",
            "comp-table",
            "voc-grid",
            "deep-dive-grid",
            "comp-deep-card",
            "opportunity-matrix",
            "pricing-grid",
            "pricing-card",
            "prompt-grid",
            "prompt-card",
            "comp-col-asin",
        ],
        "required_sections": [
            "大盘结论",
            "需求结构",
            "竞品格局",
            "VOC 洞察",
            "机会定义",
            "TikTok 内容信号",
            "1688 供应链判断",
        ],
    },
    "lifecycle_strategy": {
        "folder": "143511",
        "template": SKILL_DIR / "assets" / "lifecycle-strategy-template.html",
        "canonical_asset": CANONICAL_DIR / "lifecycle-strategy-reference.html",
        "report_style": "lifecycle-strategy-report-v2",
        "css_signals": [
            "persona-grid",
            "timeline-grid",
            "sku-table-wrap",
            "type-badge",
            "supply-badge",
            "priority-bar",
            "filter-bar",
            "filter-btn",
            "bundle-grid",
            "phase-grid",
            "risk-grid",
            "ecosystem-chart-grid",
            "sku-strategy-grid",
            "sku-strategy-card",
            "roadmap-phase-grid",
            "roadmap-action-grid",
        ],
        "required_sections": [
            "战略仪表盘",
            "用户画像",
            "生命周期旅程",
            "拓品方案池",
            "Bundle 策略",
            "30/60/90 天路线图",
            "风险矩阵",
        ],
    },
    "demand_gap": {
        "folder": "143645",
        "template": SKILL_DIR / "assets" / "demand-gap-template.html",
        "canonical_asset": CANONICAL_DIR / "demand-gap-reference.html",
        "report_style": "demand-gap-report-v2",
        "css_signals": [
            "mode-r3",
            "wrap",
            "hero",
            "kpi-grid",
            "chart",
            "chart-interpretation",
            "focus",
            "warn",
            "ok",
            "quote-cn",
            "demand-sentiment-columns",
            "demand-column-head",
            "demand-evidence-card",
            "review-excerpt-en",
        ],
        "required_sections": [
            "目标ASIN锚点",
            "决策看板",
            "市场痛点全景图（需求主题）",
            "满意度鸿沟",
            "KANO",
            "JTBD",
            "用户原声",
            "需求优先级",
        ],
    },
}

JS_SIGNALS = [
    "site-nav-toggle",
    "input.type='search'",
    "querySelectorAll('th')",
    "data-tabs",
    "data-tab-target",
    "filter-bar",
    "dataset.filter",
    "mini-chart .bar-row",
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
]

EXCLUDED_ASSETS = [
    "_next/static/chunks",
    "iframe case shells",
    "cdn.jsdelivr.net echarts runtime",
    "hard-coded sample SKU_DATA",
    "raw English review examples",
]

FIXED_SLOT_CONTRACT_SIGNALS = [
    "exactly 3 pricing strategy cards",
    "exactly 3 AI image prompt cards",
    "five fixed SKU slots",
    "exactly 6 cards",
    "data-allow-asin=\"competitor-table\"",
    "data-allow-asin=\"demand-target-anchor\"",
]


class ContractError(Exception):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def read(path: Path) -> str:
    require(path.exists(), f"missing file: {path}")
    return path.read_text(encoding="utf-8")


def validate_contract(require_downloads: bool = False) -> dict[str, object]:
    manifest = json.loads(read(MANIFEST))
    checklist = read(CHECKLIST)
    slot_contract = json.loads(read(SLOT_CONTRACT))
    site_assets = read(SITE_ASSETS)
    reference_visual_compare = read(REFERENCE_VISUAL_COMPARE)
    acceptance_proof = read(ACCEPTANCE_PROOF)
    baselines = manifest.get("baselines") or {}
    slot_reports = slot_contract.get("reports") or {}

    require(set(BASELINES) <= set(baselines), "template manifest missing one or more report baselines")
    require(set(BASELINES) <= set(slot_reports), "slot contract missing one or more report baselines")
    for excluded in EXCLUDED_ASSETS:
        require(excluded in json.dumps(manifest, ensure_ascii=False), f"template manifest missing excluded asset: {excluded}")

    for report_key, spec in BASELINES.items():
        baseline = baselines.get(report_key) or {}
        folder = str(spec["folder"])
        require(folder in str(baseline.get("download_folder") or ""), f"{report_key} baseline download folder mismatch")
        require(str(baseline.get("canonical_asset") or "") == str(spec["canonical_asset"].relative_to(SKILL_DIR)).replace("\\", "/"), f"{report_key} canonical asset mismatch")
        require(spec["canonical_asset"].exists(), f"{report_key} canonical reference HTML missing")
        require("<style" in read(spec["canonical_asset"]), f"{report_key} canonical reference missing inline style")
        require(folder in checklist, f"checklist missing folder {folder}")
        require(str(spec["report_style"]) in read(spec["template"]), f"{report_key} template missing report style")
        for section in spec["required_sections"]:
            require(section in checklist, f"checklist missing {report_key} section: {section}")
        manifest_css = baseline.get("borrowed_css_signals") or []
        for signal in spec["css_signals"]:
            require(signal in manifest_css or signal in site_assets or signal in read(spec["template"]), f"{report_key} missing css signal: {signal}")
        report_slots = slot_reports.get(report_key) or {}
        require(str(spec["folder"]) in str(report_slots.get("reference_folder") or ""), f"{report_key} slot contract reference folder mismatch")
        for bucket_name in ["exact_class_counts", "minimum_class_counts"]:
            bucket = report_slots.get(bucket_name)
            require(isinstance(bucket, dict) and bucket, f"{report_key} slot contract missing {bucket_name}")
        for group in report_slots.get("required_component_groups") or []:
            require(group in checklist or group in site_assets, f"{report_key} slot contract group not represented in checklist or assets: {group}")
        for required_id in report_slots.get("required_ids") or []:
            require(required_id in site_assets or required_id in read(spec["template"]) or required_id in checklist, f"{report_key} slot contract id not represented: {required_id}")
        if require_downloads:
            folder_path = LOCAL_DOWNLOAD_ROOT / folder
            require(folder_path.exists(), f"local downloaded template folder missing: {folder_path}")

    for signal in JS_SIGNALS:
        require(signal in site_assets, f"shared report.js missing interaction signal: {signal}")
    require((CANONICAL_DIR / "echarts.min.js").exists(), "canonical local echarts runtime missing")
    require("echarts.min.js" in site_assets, "site asset writer must copy local echarts runtime")
    require("<script src=\"https://cdn.jsdelivr.net" not in site_assets, "site asset writer must not inject CDN echarts")
    require("canonical_asset_policy" in manifest, "template manifest missing canonical asset policy")
    for signal in [
        "REFERENCE_COMPARE_CASES",
        "referenceScreenshot",
        "generatedScreenshot",
        "signalScore",
        "layoutScore",
        "screenshotByteRatio",
        "pixelDistance",
        "screenshotDistance",
        "max_pixel_distance",
        "width ratio",
        "left delta",
        "center delta",
        "pc-1366",
        "pc-1440",
    ]:
        require(signal in reference_visual_compare, f"reference visual compare script missing signal: {signal}")
    for signal in ["--reference-visual", "reference_visual_compare", "REFERENCE_VISUAL_COMPARE"]:
        require(signal in acceptance_proof, f"acceptance proof missing reference visual signal: {signal}")
    checklist_lower = checklist.lower()
    for signal in FIXED_SLOT_CONTRACT_SIGNALS:
        require(signal.lower() in checklist_lower, f"checklist missing fixed slot contract signal: {signal}")

    return {
        "template_parity_contract": True,
        "baselines": sorted(BASELINES),
        "require_downloads": require_downloads,
        "checklist": "references/html-template-parity-checklist.md",
        "manifest": "references/template-baseline-manifest.json",
        "slot_contract": "references/html-template-slot-contract.json",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate local HTML template parity contract.")
    parser.add_argument("--require-downloads", action="store_true", help="Also require the user's downloaded template folders to exist locally.")
    args = parser.parse_args(argv)
    try:
        result = validate_contract(args.require_downloads)
    except ContractError as exc:
        print(f"template_parity_failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
