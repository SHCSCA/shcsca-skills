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
SITE_ASSETS = SCRIPT_DIR / "site_assets.py"
LOCAL_DOWNLOAD_ROOT = Path(r"C:\Users\wz\Downloads\downloadpage")


BASELINES = {
    "market_depth": {
        "folder": "143101",
        "template": SKILL_DIR / "assets" / "market-depth-template.html",
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
        ],
        "required_sections": [
            "研究对象概述",
            "决策看板",
            "$APPEALS 痛点图",
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
]

EXCLUDED_ASSETS = [
    "_next/static/chunks",
    "iframe case shells",
    "cdn.jsdelivr.net echarts runtime",
    "hard-coded sample SKU_DATA",
    "raw English review examples",
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
    site_assets = read(SITE_ASSETS)
    baselines = manifest.get("baselines") or {}

    require(set(BASELINES) <= set(baselines), "template manifest missing one or more report baselines")
    for excluded in EXCLUDED_ASSETS:
        require(excluded in json.dumps(manifest, ensure_ascii=False), f"template manifest missing excluded asset: {excluded}")

    for report_key, spec in BASELINES.items():
        baseline = baselines.get(report_key) or {}
        folder = str(spec["folder"])
        require(folder in str(baseline.get("download_folder") or ""), f"{report_key} baseline download folder mismatch")
        require(folder in checklist, f"checklist missing folder {folder}")
        require(str(spec["report_style"]) in read(spec["template"]), f"{report_key} template missing report style")
        for section in spec["required_sections"]:
            require(section in checklist, f"checklist missing {report_key} section: {section}")
        manifest_css = baseline.get("borrowed_css_signals") or []
        for signal in spec["css_signals"]:
            require(signal in manifest_css or signal in site_assets or signal in read(spec["template"]), f"{report_key} missing css signal: {signal}")
        if require_downloads:
            folder_path = LOCAL_DOWNLOAD_ROOT / folder
            require(folder_path.exists(), f"local downloaded template folder missing: {folder_path}")

    for signal in JS_SIGNALS:
        require(signal in site_assets, f"shared report.js missing interaction signal: {signal}")

    return {
        "template_parity_contract": True,
        "baselines": sorted(BASELINES),
        "require_downloads": require_downloads,
        "checklist": "references/html-template-parity-checklist.md",
        "manifest": "references/template-baseline-manifest.json",
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
