#!/usr/bin/env python3
"""Lightweight critic and refinement loop for market research reports."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


HTML_LEAK_PATTERNS = [
    re.compile(r"\bsource_id\b", re.I),
    re.compile(r"\bprovider\b", re.I),
    re.compile(r"\braw_path\b", re.I),
    re.compile(r"\bB0[A-Z0-9]{8}\b"),
    re.compile(r"\bdata/raw/[^\s<>'\"]+", re.I),
]


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def strip_allowed_customer_exceptions(html_doc: str) -> str:
    html_doc = re.sub(
        r"<span\b(?=[^>]*\bdata-allow-asin=[\"'](?:benchmark-sniper|profit-model)[\"'])[^>]*>\s*B0[A-Z0-9]{8}\s*</span>",
        "竞品ASIN",
        html_doc,
        flags=re.IGNORECASE,
    )
    html_doc = re.sub(
        r"<([a-z0-9]+)\b(?=[^>]*\bdata-allow-english-review=[\"']short[\"'])[^>]*>.*?</\1>",
        "英文评论短摘",
        html_doc,
        flags=re.IGNORECASE | re.DOTALL,
    )
    return html_doc


def evidence_profile(data_pack: dict[str, Any], analysis_plan: dict[str, Any], delivery: dict[str, Any]) -> dict[str, Any]:
    normalization = data_pack.get("normalization") or {}
    cross_counts = normalization.get("cross_validated_counts") or {}
    review_count = len(data_pack.get("reviews") or [])
    non_keyword_cross = sum(as_float(value, 0) for key, value in cross_counts.items() if key != "keywords")
    return {
        "review_count": review_count,
        "gap_count": len(data_pack.get("data_gaps") or []) + len(analysis_plan.get("limitations") or []),
        "quality_score": as_float((data_pack.get("quality") or {}).get("overall_score"), 0),
        "delivery_status": str(delivery.get("status") or "complete").lower(),
        "non_keyword_cross_validated": non_keyword_cross,
        "review_depth": "low" if review_count < 80 else "medium" if review_count < 200 else "high",
        "cross_validation": "low" if non_keyword_cross <= 0 else "medium" if non_keyword_cross < 5 else "high",
    }


def finding(finding_id: str, issue_class: str, severity: str, report_type: str, claim_path: str, evidence_path: str, problem: str, required_refinement: str) -> dict[str, Any]:
    return {
        "id": finding_id,
        "class": issue_class,
        "severity": severity,
        "report_type": report_type,
        "claim_path": claim_path,
        "evidence_path": evidence_path,
        "problem": problem,
        "required_refinement": required_refinement,
    }


def build_critic_review(
    data_pack: dict[str, Any],
    analysis_plan: dict[str, Any],
    delivery: dict[str, Any],
    decision: str,
    *,
    round_id: int = 0,
    previous_review: dict[str, Any] | None = None,
    applied_operations: list[dict[str, Any]] | None = None,
    rendered_docs: dict[str, str] | None = None,
    view_models: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    profile = evidence_profile(data_pack, analysis_plan, delivery)
    strong_decision = str(decision).strip().lower() == "go"
    score = profile["quality_score"]
    findings: list[dict[str, Any]] = []

    if profile["review_count"] < 80 and (strong_decision or score >= 0.75):
        findings.append(
            finding(
                "F-review-depth",
                "evidence_depth",
                "blocking",
                "demand_gap",
                "delivery_result.decision",
                "data_pack.reviews",
                "评论样本不足以支撑高置信 Go 或 B+ 判断。",
                "set_decision_strength=low_confidence_watch; append_limitation=review_sample_depth",
            )
        )
    if profile["non_keyword_cross_validated"] <= 0 and (strong_decision or score >= 0.75):
        findings.append(
            finding(
                "F-cross-validation",
                "decision_consistency",
                "blocking",
                "market_depth",
                "quality.overall_score",
                "normalization.cross_validated_counts",
                "关键词之外的交叉验证不足，当前结论强度过高。",
                "append_limitation=cross_validation_depth; append_recommended_action=补交叉验证",
            )
        )
    if profile["delivery_status"] == "partial" and strong_decision:
        findings.append(
            finding(
                "F-partial-go",
                "decision_consistency",
                "blocking",
                "market_depth",
                "delivery_result.status",
                "delivery_result.decision",
                "交付状态为 partial 时不能输出无保留强 Go。",
                "set_decision=Watch; append_validation_gate=partial_delivery",
            )
        )
    if profile["gap_count"] and score >= 0.85:
        findings.append(
            finding(
                "F-gap-score",
                "decision_consistency",
                "warning",
                "lifecycle_strategy",
                "quality.overall_score",
                "data_pack.data_gaps",
                "存在数据缺口时质量评分不应保持极高分。",
                "surface_limitations=data_gaps",
            )
        )

    rendered_docs = rendered_docs or {}
    combined_html = strip_allowed_customer_exceptions("\n".join(rendered_docs.values()))
    if rendered_docs:
        for pattern in HTML_LEAK_PATTERNS:
            match = pattern.search(combined_html)
            if match:
                findings.append(
                    finding(
                        "F-customer-html-leak",
                        "customer_safety",
                        "blocking",
                        "market_depth",
                        "output/html_reports/*.html",
                        "customer_html",
                        f"客户版 HTML 暴露内部字段或技术标识：{match.group(0)}。",
                        "rerun_customer_redaction; block_delivery_until_safe",
                    )
                )
                break
        for required_term in ["证据强度", "数据覆盖", "数据缺口", "置信等级", "建议动作"]:
            if required_term not in combined_html:
                findings.append(
                    finding(
                        f"F-missing-term-{required_term}",
                        "report_completeness",
                        "blocking",
                        "market_depth",
                        "output/html_reports/*.html",
                        "html_contract",
                        f"客户版 HTML 缺少必备可信度表达：{required_term}。",
                        "rerender_required_client_terms",
                    )
                )
        for report_key in ["market_depth", "lifecycle_strategy", "demand_gap"]:
            if report_key not in rendered_docs:
                findings.append(
                    finding(
                        f"F-missing-report-{report_key}",
                        "report_completeness",
                        "blocking",
                        report_key,
                        "output/html_reports",
                        "html_bundle",
                        f"缺少子报告 HTML：{report_key}。",
                        "rerender_child_report",
                    )
                )
    if view_models:
        for view_name, payload in view_models.items():
            if not payload.get("client_safe_text"):
                findings.append(
                    finding(
                        f"F-view-client-safe-{view_name}",
                        "customer_safety",
                        "blocking",
                        view_name.replace("_view.json", ""),
                        f"analysis/{view_name}",
                        "view_model.client_safe_text",
                        f"展示层 view model 未声明客户安全文本：{view_name}。",
                        "rerender_view_model_with_customer_safe_text",
                    )
                )
    finance_terms = ["成本", "毛利", "利润", "退货", "FBA", "ACOS"]
    present_finance_terms = [term for term in finance_terms if term in combined_html]
    if rendered_docs and len(present_finance_terms) < 3:
        findings.append(
            finding(
                "F-finance-depth",
                "business_depth",
                "warning",
                "lifecycle_strategy",
                "lifecycle/market_depth financial sections",
                "profitability/fba/returns/acos",
                "财务化判断不够完整，成本、毛利、退货、FBA、ACOS 至少应覆盖三个维度。",
                "add_financial_sensitivity_section",
            )
        )

    blocking = [item for item in findings if item["severity"] == "blocking"]
    applied_operations = applied_operations or []
    previous_findings = previous_review.get("findings", []) if previous_review else []
    resolved = [item["id"] for item in previous_findings if item.get("severity") == "blocking" and not blocking]
    critic_score = max(0, min(100, int(score * 100) - len(blocking) * 15 - (len(findings) - len(blocking)) * 5))
    return {
        "pass": not blocking,
        "round_id": round_id,
        "score": critic_score,
        "grade": "A" if critic_score >= 90 else "B" if critic_score >= 75 else "C" if critic_score >= 60 else "D",
        "findings": findings,
        "blocking_issues": [item["problem"] for item in blocking],
        "resolved_findings": resolved,
        "remaining_findings": [item["id"] for item in blocking],
        "report_issues": {
            "market_depth": [item["problem"] for item in findings if item["report_type"] == "market_depth"],
            "lifecycle_strategy": [item["problem"] for item in findings if item["report_type"] == "lifecycle_strategy"],
            "demand_gap": [item["problem"] for item in findings if item["report_type"] == "demand_gap"],
        },
        "data_confidence": {
            "review_depth": profile["review_depth"],
            "cross_validation": profile["cross_validation"],
            "decision_confidence": "overstated" if blocking else "aligned",
        },
        "suggestions": [item["required_refinement"] for item in findings],
        "refinement_targets": [
            {"report_type": item["report_type"], "action": item["required_refinement"], "reason": item["class"]}
            for item in findings
        ],
        "applied_operations": applied_operations,
        "max_refinement_rounds": 2,
    }


def build_refinement_plan(review: dict[str, Any], decision: str) -> dict[str, Any]:
    operations: list[dict[str, Any]] = []
    reason_by_finding = {
        "F-review-depth": "review_sample_depth",
        "F-cross-validation": "cross_validation_depth",
        "F-partial-go": "partial_delivery",
        "F-gap-score": "data_gap_visibility",
    }
    for item in review.get("findings") or []:
        if item["id"] in {"F-review-depth", "F-cross-validation", "F-partial-go"}:
            operations.append(
                {
                    "type": "set_decision",
                    "from": decision,
                    "to": "Watch",
                    "finding_id": item["id"],
                    "reason": reason_by_finding.get(item["id"], item["class"]),
                }
            )
        if item["id"] == "F-review-depth":
            operations.append(
                {
                    "type": "append_limitation",
                    "target": "all_views",
                    "finding_id": item["id"],
                    "text": "评论样本不足 80 条，VOC、APPEALS、KANO/JTBD 只能作为低置信线索，需补评论样本后再升级结论。",
                }
            )
        if item["id"] == "F-cross-validation":
            operations.append(
                {
                    "type": "append_recommended_action",
                    "target": "market_depth_view",
                    "finding_id": item["id"],
                    "text": "补充竞品、评论、供应端或公开 Web 交叉验证；未补齐前保持 Watch。",
                }
            )
    unique_operations: list[dict[str, Any]] = []
    seen = set()
    for op in operations:
        fingerprint = (op.get("type"), op.get("finding_id"), op.get("target"), op.get("to"))
        if fingerprint not in seen:
            seen.add(fingerprint)
            unique_operations.append(op)
    return {
        "status": "needs_refinement" if unique_operations else "accepted",
        "round_id": review.get("round_id", 0),
        "max_refinement_rounds": 2,
        "operations": unique_operations,
        "refinement_targets": review.get("refinement_targets") or [],
        "constraints": [
            "Do not recollect data during critic refinement.",
            "Do not modify data/normalized/normalized_data_pack.json.",
            "Only adjust view models, conclusion strength, limitations, and report expression.",
        ],
    }


def apply_refinement_plan(delivery: dict[str, Any], plan: dict[str, Any], decision: str) -> str:
    next_decision = decision
    reasons: list[str] = []
    for op in plan.get("operations") or []:
        if op.get("type") == "set_decision" and op.get("to"):
            next_decision = str(op["to"])
            reasons.append(str(op.get("reason") or op.get("finding_id")))
    if next_decision != decision:
        delivery["original_decision"] = decision
        delivery["decision"] = next_decision
        delivery["decision_adjustment"] = {
            "from": decision,
            "to": next_decision,
            "reasons": reasons,
            "note": "Strong decision was downgraded by critic refinement because evidence depth could not support unconditional entry.",
        }
    return next_decision


def readiness_label(delivery: dict[str, Any]) -> str:
    readiness = delivery.get("data_readiness") or {}
    if isinstance(readiness, dict) and "acceptance_ready" in readiness:
        return "pass" if readiness.get("acceptance_ready") is True else "fail"
    return "not_recorded"


def write_critic_summary(
    analysis_dir: Path,
    data_pack: dict[str, Any],
    delivery: dict[str, Any],
    final_review: dict[str, Any],
    final_plan: dict[str, Any],
    *,
    draft_review: dict[str, Any] | None = None,
) -> None:
    adjustment = delivery.get("decision_adjustment") or {}
    operations = final_plan.get("applied_operations") or final_plan.get("operations") or []
    remaining = final_review.get("remaining_findings") or []
    resolved = final_review.get("resolved_findings") or []
    lines = [
        "# Critic Summary",
        "",
        f"- task_id: `{data_pack.get('task_id') or 'unknown'}`",
        f"- readiness: `{readiness_label(delivery)}`",
        f"- final_pass: `{str(final_review.get('pass')).lower()}`",
        f"- final_score: `{final_review.get('score')}`",
        f"- final_grade: `{final_review.get('grade')}`",
        f"- round_id: `{final_review.get('round_id')}`",
        f"- original_decision: `{delivery.get('original_decision') or delivery.get('decision') or 'unknown'}`",
        f"- final_decision: `{delivery.get('decision') or 'unknown'}`",
        f"- decision_adjusted: `{str(bool(adjustment)).lower()}`",
        "",
        "## Decision Adjustment",
        "",
    ]
    if adjustment:
        lines.extend(
            [
                f"- from: `{adjustment.get('from')}`",
                f"- to: `{adjustment.get('to')}`",
                f"- reasons: `{', '.join(str(item) for item in adjustment.get('reasons') or [])}`",
                f"- note: {adjustment.get('note') or ''}",
            ]
        )
    else:
        lines.append("- none")
    lines.extend(["", "## Findings", ""])
    if final_review.get("findings"):
        for item in final_review.get("findings") or []:
            lines.append(
                f"- `{item.get('id')}` [{item.get('severity')}] {item.get('problem')} -> {item.get('required_refinement')}"
            )
    else:
        lines.append("- none")
    lines.extend(["", "## Refinement", ""])
    if operations:
        for op in operations:
            lines.append(
                f"- `{op.get('type')}` finding=`{op.get('finding_id')}` target=`{op.get('target') or op.get('to') or 'n/a'}` reason=`{op.get('reason') or 'n/a'}`"
            )
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Resolution State",
            "",
            f"- draft_pass: `{str(draft_review.get('pass')).lower() if draft_review else 'not_recorded'}`",
            f"- resolved_findings: `{', '.join(str(item) for item in resolved) if resolved else 'none'}`",
            f"- remaining_findings: `{', '.join(str(item) for item in remaining) if remaining else 'none'}`",
            "",
            "## Guardrails",
            "",
            "- Critic refinement must not recollect data.",
            "- Critic refinement must not modify `data/normalized/normalized_data_pack.json`.",
            "- If final_pass is false, the orchestrator must not claim delivery completion.",
        ]
    )
    (analysis_dir / "critic_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_critic_outputs(
    report_dir: Path,
    data_pack: dict[str, Any],
    analysis_plan: dict[str, Any],
    delivery: dict[str, Any],
    decision: str,
    *,
    draft_review: dict[str, Any] | None = None,
    refinement_plan: dict[str, Any] | None = None,
    rendered_docs: dict[str, str] | None = None,
    view_models: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if draft_review and not draft_review.get("pass"):
        applied_operations = refinement_plan.get("operations") if refinement_plan else []
        final_review = build_critic_review(
            data_pack,
            analysis_plan,
            delivery,
            decision,
            round_id=int(draft_review.get("round_id", 0)) + 1,
            previous_review=draft_review,
            applied_operations=applied_operations,
            rendered_docs=rendered_docs,
            view_models=view_models,
        )
        final_plan = dict(refinement_plan or {})
        final_plan["status"] = "accepted" if final_review["pass"] else "needs_refinement"
        final_plan["applied_operations"] = applied_operations
        final_plan["round_id"] = final_review["round_id"]
    else:
        final_review = build_critic_review(data_pack, analysis_plan, delivery, decision, round_id=0, rendered_docs=rendered_docs, view_models=view_models)
        final_plan = refinement_plan or build_refinement_plan(final_review, decision)

    analysis_dir = report_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    (analysis_dir / "critic_review.json").write_text(json.dumps(final_review, ensure_ascii=False, indent=2), encoding="utf-8")
    (analysis_dir / "refinement_plan.json").write_text(json.dumps(final_plan, ensure_ascii=False, indent=2), encoding="utf-8")
    write_critic_summary(analysis_dir, data_pack, delivery, final_review, final_plan, draft_review=draft_review)

    if draft_review and not draft_review.get("pass"):
        history_path = analysis_dir / "refinement_history.jsonl"
        with history_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"type": "critic_review", "payload": draft_review}, ensure_ascii=False) + "\n")
            handle.write(json.dumps({"type": "refinement_plan", "payload": refinement_plan}, ensure_ascii=False) + "\n")
            handle.write(json.dumps({"type": "critic_review", "payload": final_review}, ensure_ascii=False) + "\n")
        training_dir = report_dir / "training_data"
        training_dir.mkdir(parents=True, exist_ok=True)
        with (training_dir / "failed_cases.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "task_id": data_pack.get("task_id"),
                        "decision": delivery.get("original_decision") or decision,
                        "quality": data_pack.get("quality") or {},
                        "critic_review": draft_review,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
    return final_review
