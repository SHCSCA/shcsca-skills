#!/usr/bin/env python3
"""Write non-HTML delivery artifacts for the orchestrated market reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from site_assets import COMPAT_INDEX_REPORT, HTML_BUNDLE_DIR, HTML_REPORTS, INTERACTIVE_FEATURES, SITE_ASSETS


CHILD_SKILL_INVOCATION_SPECS = {
    "market_depth": {
        "inputs": ["data/normalized/normalized_data_pack.json", "analysis/analysis_plan.json", "report_brief.json"],
        "outputs": ["analysis/market_depth_view.json", "output/html_reports/market-depth-report.html"],
        "renderer": "child_skills/market-depth-report/scripts/render_market_depth_report.py",
        "template": "child_skills/market-depth-report/templates/market-depth-report.html",
        "dispatch_mode": "subprocess_child_renderer",
    },
    "lifecycle_strategy": {
        "inputs": ["data/normalized/normalized_data_pack.json", "analysis/analysis_plan.json", "report_brief.json"],
        "outputs": ["analysis/lifecycle_strategy_view.json", "output/html_reports/lifecycle-strategy-report.html"],
        "renderer": "child_skills/lifecycle-strategy-report/scripts/render_lifecycle_strategy_report.py",
        "template": "child_skills/lifecycle-strategy-report/templates/lifecycle-strategy-report.html",
        "dispatch_mode": "subprocess_child_renderer",
    },
    "demand_gap": {
        "inputs": ["data/normalized/normalized_data_pack.json", "analysis/analysis_plan.json", "report_brief.json"],
        "outputs": ["analysis/demand_gap_view.json", "output/html_reports/demand-gap-report.html"],
        "renderer": "child_skills/demand-gap-report/scripts/render_demand_gap_report.py",
        "template": "child_skills/demand-gap-report/templates/demand-gap-report.html",
        "dispatch_mode": "subprocess_child_renderer",
    },
    "critic": {
        "inputs": [
            "data/normalized/normalized_data_pack.json",
            "analysis/analysis_plan.json",
            "analysis/market_depth_view.json",
            "analysis/lifecycle_strategy_view.json",
            "analysis/demand_gap_view.json",
            "output/html_reports/market-depth-report.html",
            "output/html_reports/lifecycle-strategy-report.html",
            "output/html_reports/demand-gap-report.html",
        ],
        "outputs": ["analysis/critic_review.json", "analysis/refinement_plan.json"],
        "renderer": "child_skills/market-research-critic/scripts/run_critic.py",
        "template": "child_skills/market-research-critic/references/critic-contract.md",
        "dispatch_mode": "subprocess_critic_child",
    },
}


def first(*values: Any, default: Any = "-") -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return default


def truncate(value: Any, limit: int = 100) -> str:
    text = "" if value is None else str(value)
    return text if len(text) <= limit else text[: limit - 1] + "..."


def child_skill_invocations(child_skills: dict[str, str]) -> dict[str, dict[str, Any]]:
    invocations: dict[str, dict[str, Any]] = {}
    for key, module_path in child_skills.items():
        spec = CHILD_SKILL_INVOCATION_SPECS.get(key, {})
        invocations[key] = {
            "module": module_path,
            "status": "rendered",
            "dispatch_mode": spec.get("dispatch_mode") or "internal_orchestrator",
            "inputs": spec.get("inputs") or [],
            "outputs": spec.get("outputs") or [],
            "renderer": spec.get("renderer"),
            "template": spec.get("template"),
            "data_policy": "read_only_normalized_data_pack",
            "invocation_log": "analysis/child_skill_invocation_log.json" if str(spec.get("dispatch_mode") or "").startswith("subprocess_") else None,
        }
    return invocations


def write_lineage_markdown(data_pack: dict[str, Any], path: Path) -> None:
    lines = ["# Data Lineage", ""]
    for source in data_pack.get("sources", []):
        label = truncate(first(source.get("label"), source.get("query"), source.get("args"), default="-"), 140)
        limitation = truncate(source.get("limitation") or source.get("raw_path") or "", 180)
        lines.append(
            f"- {source.get('source_id')}: {source.get('provider')} / {source.get('tool')} / {label} / confidence={source.get('confidence')} / {limitation}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report_brief(report_dir: Path, data_pack: dict[str, Any], analysis_plan: dict[str, Any], decision: str, child_skills: dict[str, str]) -> None:
    brief = data_pack.get("brief") or {}
    report_brief = {
        "task_id": data_pack.get("task_id") or analysis_plan.get("task_id"),
        "research_object": brief.get("research_object") or data_pack.get("research_object") or {},
        "decision": decision,
        "child_skills": child_skills,
        "child_skill_invocations": child_skill_invocations(child_skills),
        "static_site": {
            "bundle_dir": HTML_BUNDLE_DIR,
            "assets": SITE_ASSETS,
            "interactive_features": INTERACTIVE_FEATURES,
        },
        "data_inputs": {
            "normalized_data_pack": "data/normalized/normalized_data_pack.json",
            "analysis_plan": "analysis/analysis_plan.json",
        },
    }
    (report_dir / "report_brief.json").write_text(json.dumps(report_brief, ensure_ascii=False, indent=2), encoding="utf-8")


def write_delivery_result(report_dir: Path, delivery: dict[str, Any], child_skills: dict[str, str]) -> None:
    output_path = report_dir / "output" / "delivery_result.json"
    delivery = dict(delivery)
    delivery.setdefault("status", "complete")
    formats = list(delivery.get("formats") or [])
    if "html" not in formats:
        formats.append("html")
    delivery["formats"] = formats
    html_reports = dict(HTML_REPORTS)
    html_reports["compat_index"] = COMPAT_INDEX_REPORT
    delivery["html_reports"] = html_reports
    delivery["html_bundle_dir"] = HTML_BUNDLE_DIR
    delivery["child_skills"] = child_skills
    delivery["child_skill_invocations"] = child_skill_invocations(child_skills)
    delivery["site_assets"] = SITE_ASSETS
    delivery["interactive_features"] = INTERACTIVE_FEATURES
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(delivery, ensure_ascii=False, indent=2), encoding="utf-8")
