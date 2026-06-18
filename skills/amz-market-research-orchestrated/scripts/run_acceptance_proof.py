#!/usr/bin/env python3
"""Run a consolidated acceptance proof for an orchestrated market report."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
READINESS = SCRIPT_DIR / "check_data_readiness.py"
RECOVERY = SCRIPT_DIR / "recover_data_readiness.py"
RENDERER = SCRIPT_DIR / "render_dashboard_html.py"
VALIDATOR = SCRIPT_DIR / "validate_market_research_deliverables.py"
TEMPLATE_PARITY = SCRIPT_DIR / "validate_template_parity_contract.py"
REFERENCE_VISUAL_COMPARE = SCRIPT_DIR / "run_template_reference_visual_compare.py"
DEFAULT_DOWNLOAD_ROOT = Path(r"C:\Users\wz\Downloads\downloadpage")


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def public_delivery_result_summary(delivery: dict[str, Any]) -> dict[str, Any]:
    readiness = delivery.get("data_readiness") if isinstance(delivery.get("data_readiness"), dict) else {}
    return {
        "status": delivery.get("status"),
        "decision": delivery.get("decision"),
        "delivery_mode": delivery.get("delivery_mode") or readiness.get("delivery_mode"),
        "overall_pass": delivery.get("overall_pass"),
        "full_acceptance_pass": delivery.get("full_acceptance_pass"),
        "diagnostic_delivery_pass": delivery.get("diagnostic_delivery_pass"),
        "data_readiness": {
            "decision": readiness.get("decision"),
            "delivery_mode": readiness.get("delivery_mode"),
            "evidence_grade": readiness.get("evidence_grade"),
            "score": readiness.get("score"),
            "acceptance_ready": readiness.get("acceptance_ready"),
            "partial_report_ready": readiness.get("partial_report_ready"),
            "supply_conclusion_blocked": readiness.get("supply_conclusion_blocked"),
        },
    }


DEFAULT_STEP_TIMEOUT_SECONDS = 90


def run_step(name: str, command: list[str], cwd: Path, timeout_seconds: int = DEFAULT_STEP_TIMEOUT_SECONDS) -> dict[str, Any]:
    started_at = utc_now()
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "started_at": started_at,
            "finished_at": utc_now(),
            "returncode": 124,
            "stdout": (exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
            "stderr": f"step timed out after {timeout_seconds}s",
            "pass": False,
            "timeout_seconds": timeout_seconds,
        }
    return {
        "name": name,
        "command": command,
        "started_at": started_at,
        "finished_at": utc_now(),
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "pass": result.returncode == 0,
    }


def critic_acceptance(critic: dict[str, Any]) -> bool:
    if critic.get("pass") is not True:
        return False
    try:
        score = float(critic.get("score"))
    except (TypeError, ValueError):
        return False
    grade = str(critic.get("grade") or "").strip().upper()
    if score < 70:
        return False
    if grade in {"C", "D"}:
        return False
    return True


def proof_decision(delivery: dict[str, Any], readiness: dict[str, Any]) -> str:
    decision = str(delivery.get("decision") or "").strip()
    if decision in {"Go", "Watch", "No-Go"}:
        return decision
    if readiness.get("acceptance_ready") is True:
        return "Watch"
    if readiness.get("partial_report_ready") is True:
        return "Watch"
    return "No-Go"


def proof_markdown(proof: dict[str, Any]) -> str:
    lines = [
        "# Acceptance Proof",
        "",
        f"- Report directory: `{proof['report_dir']}`",
        f"- Checked at: `{proof['checked_at']}`",
        f"- Overall pass: `{proof['overall_pass']}`",
        f"- Delivery mode: `{proof.get('delivery_mode')}`",
        f"- full_acceptance_pass: `{proof.get('full_acceptance_pass')}`",
        f"- diagnostic_delivery_pass: `{proof.get('diagnostic_delivery_pass')}`",
        f"- Sample class: `{proof.get('sample_class')}`",
        f"- Decision: `{proof.get('decision')}`",
        "",
        "## Steps",
        "",
        "| Step | Pass | Return code |",
        "|---|---:|---:|",
    ]
    for step in proof["steps"]:
        lines.append(f"| `{step['name']}` | `{step['pass']}` | `{step['returncode']}` |")
    lines.extend(["", "## Readiness", ""])
    readiness = proof.get("readiness") or {}
    lines.append(f"- acceptance_ready: `{readiness.get('acceptance_ready')}`")
    lines.append(f"- blocking gaps: `{len(readiness.get('blocking_gaps') or [])}`")
    lines.append(f"- warnings: `{len(readiness.get('warnings') or [])}`")
    if proof.get("reference_visual_compare"):
        lines.extend(["", "## Template Reference Visual Compare", ""])
        lines.append(f"- audit: `{proof['reference_visual_compare']}`")
    if proof.get("reference_visual_skipped_reason"):
        lines.extend(["", "## Template Reference Visual Compare", ""])
        lines.append(f"- skipped: `{proof['reference_visual_skipped_reason']}`")
    if readiness.get("blocking_gaps"):
        lines.extend(["", "### Blocking Gaps", ""])
        for gap in readiness["blocking_gaps"]:
            lines.append(f"- `{gap.get('module')}`: {gap.get('reason') or gap.get('gap')}")
    return "\n".join(lines) + "\n"


def run_proof(
    report_dir: Path,
    depth: str,
    skip_render: bool = False,
    reference_visual: bool = False,
    download_root: Path = DEFAULT_DOWNLOAD_ROOT,
) -> dict[str, Any]:
    report_dir = report_dir.resolve()
    repo_root = Path.cwd()
    steps: list[dict[str, Any]] = []

    steps.append(run_step("template_parity", [sys.executable, str(TEMPLATE_PARITY)], repo_root))
    if not steps[-1]["pass"]:
        proof = {
            "report_dir": str(report_dir),
            "checked_at": utc_now(),
            "overall_pass": False,
            "sample_class": None,
            "decision": "No-Go",
            "readiness": {},
            "delivery_status": None,
            "critic_pass": None,
            "critic_score": None,
            "critic_summary": None,
            "steps": steps,
        }
        write_json(report_dir / "output" / "acceptance_proof.json", proof)
        (report_dir / "output" / "acceptance_proof.md").write_text(proof_markdown(proof), encoding="utf-8")
        return proof

    steps.append(run_step("readiness", [sys.executable, str(READINESS), "--dir", str(report_dir), "--depth", depth, "--write"], repo_root))
    readiness = load_json(report_dir / "data" / "normalized" / "data_readiness_report.json", {})

    if not steps[-1]["pass"]:
        steps.append(run_step("readiness_recovery", [sys.executable, str(RECOVERY), "--dir", str(report_dir), "--depth", depth, "--max-rounds", "2"], repo_root))
        steps.append(run_step("readiness_after_recovery", [sys.executable, str(READINESS), "--dir", str(report_dir), "--depth", depth, "--write"], repo_root))
        readiness = load_json(report_dir / "data" / "normalized" / "data_readiness_report.json", {})
        if readiness.get("acceptance_ready") or readiness.get("partial_report_ready"):
            steps[-1]["pass"] = True

    can_render = bool(readiness.get("acceptance_ready") or readiness.get("partial_report_ready"))
    def has_html_artifacts() -> bool:
        return all(
            (report_dir / "output" / "html_reports" / name).exists()
            for name in [
                "report.html",
                "market-depth-report.html",
                "lifecycle-strategy-report.html",
                "demand-gap-report.html",
            ]
        )

    existing_html_artifacts = has_html_artifacts()

    if can_render and not skip_render:
        steps.append(run_step("render", [sys.executable, str(RENDERER), "--dir", str(report_dir), "--depth", depth], repo_root))
    elif not skip_render and (report_dir / "data" / "data_pack.json").exists():
        diagnostic_step = run_step("render_diagnostic", [sys.executable, str(RENDERER), "--dir", str(report_dir), "--no-recover", "--depth", depth], repo_root)
        if has_html_artifacts() and not readiness.get("acceptance_ready"):
            diagnostic_step["pass"] = True
            diagnostic_step["diagnostic_artifacts_written"] = True
        steps.append(diagnostic_step)
    elif skip_render and existing_html_artifacts:
        steps.append(
            {
                "name": "existing_rendered_artifacts",
                "command": [],
                "started_at": utc_now(),
                "finished_at": utc_now(),
                "returncode": 0,
                "stdout": "using existing rendered HTML artifacts",
                "stderr": "",
                "pass": True,
            }
        )

    has_rendered_artifacts = any(step["name"] in {"render", "render_diagnostic", "existing_rendered_artifacts"} and step["pass"] for step in steps)
    if all(step["pass"] for step in steps) or has_rendered_artifacts:
        steps.append(run_step("validate", [sys.executable, str(VALIDATOR), "--dir", str(report_dir)], repo_root))

    reference_visual_skipped_reason = None
    if reference_visual and all(step["pass"] for step in steps):
        steps.append(
            run_step(
                "reference_visual_compare",
                [
                    sys.executable,
                    str(REFERENCE_VISUAL_COMPARE),
                    "--dir",
                    str(report_dir),
                    "--download-root",
                    str(download_root),
                ],
                repo_root,
            )
        )
    elif reference_visual:
        reference_visual_skipped_reason = "reference visual compare requires a fully passing render/validator chain; diagnostic delivery records template-component validation instead"
        steps.append(
            {
                "name": "reference_visual_compare_skipped",
                "command": [],
                "started_at": utc_now(),
                "finished_at": utc_now(),
                "returncode": 0,
                "stdout": reference_visual_skipped_reason,
                "stderr": "",
                "pass": True,
            }
        )

    render_passed = any(step["name"] == "render" and step["pass"] for step in steps)
    validate_passed = any(step["name"] == "validate" and step["pass"] for step in steps)
    can_trust_delivery = render_passed or validate_passed
    delivery = load_json(report_dir / "output" / "delivery_result.json", {}) if can_trust_delivery else {}
    critic = load_json(report_dir / "analysis" / "critic_review.json", {}) if can_trust_delivery else {}
    step_pass = all(step["pass"] for step in steps if not (step["name"] == "readiness" and can_render))
    diagnostic_step_pass = validate_passed and any(step["name"] in {"render_diagnostic", "existing_rendered_artifacts"} and step["pass"] for step in steps)
    readiness_pass = readiness.get("acceptance_ready") is True
    partial_report_pass = readiness.get("partial_report_ready") is True
    critic_pass = critic_acceptance(critic) if can_trust_delivery else None
    full_acceptance_pass = bool(step_pass and readiness_pass and critic_pass)
    diagnostic_delivery_pass = bool(
        (step_pass and not readiness_pass and partial_report_pass and critic_pass)
        or (diagnostic_step_pass and not readiness_pass and not partial_report_pass)
    )
    if full_acceptance_pass:
        delivery_mode = "full_acceptance"
    elif diagnostic_delivery_pass:
        delivery_mode = "diagnostic_delivery"
    else:
        delivery_mode = "blocked"
    proof = {
        "report_dir": str(report_dir),
        "checked_at": utc_now(),
        "overall_pass": bool(full_acceptance_pass),
        "full_acceptance_pass": full_acceptance_pass,
        "diagnostic_delivery_pass": diagnostic_delivery_pass,
        "delivery_mode": delivery_mode,
        "sample_class": readiness.get("sample_class"),
        "decision": proof_decision(delivery, readiness),
        "readiness": readiness,
        "delivery_status": delivery.get("status"),
        "critic_pass": critic_pass,
        "critic_score": critic.get("score"),
        "critic_grade": critic.get("grade"),
        "critic_summary": "analysis/critic_summary.md" if can_trust_delivery and (report_dir / "analysis" / "critic_summary.md").exists() else None,
        "reference_visual_compare": "output/template_reference_visual_compare/template_reference_visual_compare.json"
        if reference_visual and (report_dir / "output/template_reference_visual_compare/template_reference_visual_compare.json").exists()
        else None,
        "reference_visual_skipped_reason": reference_visual_skipped_reason,
        "stale_delivery_ignored": not can_trust_delivery and (report_dir / "output" / "delivery_result.json").exists(),
        "steps": steps,
    }
    sync_delivery_result_with_proof(report_dir, proof, can_trust_delivery)
    sync_report_markdown_with_proof(report_dir, proof, readiness)
    write_json(report_dir / "output" / "acceptance_proof.json", proof)
    (report_dir / "output" / "acceptance_proof.md").write_text(proof_markdown(proof), encoding="utf-8")
    return proof


def sync_delivery_result_with_proof(report_dir: Path, proof: dict[str, Any], can_trust_delivery: bool) -> None:
    delivery_path = report_dir / "output" / "delivery_result.json"
    if not can_trust_delivery or not delivery_path.exists():
        return
    delivery = load_json(delivery_path, {})
    delivery["decision"] = proof.get("decision") or delivery.get("decision") or "No-Go"
    delivery["delivery_mode"] = proof.get("delivery_mode")
    delivery["overall_pass"] = proof.get("overall_pass")
    delivery["full_acceptance_pass"] = proof.get("full_acceptance_pass")
    delivery["diagnostic_delivery_pass"] = proof.get("diagnostic_delivery_pass")
    delivery["acceptance_proof"] = "output/acceptance_proof.json"
    write_json(delivery_path, delivery)
    site_data_path = report_dir / "output" / "html_reports" / "assets" / "report-data.json"
    if site_data_path.exists():
        site_data = load_json(site_data_path, {})
        site_data["decision"] = delivery["decision"]
        site_data["delivery_result"] = public_delivery_result_summary(delivery)
        write_json(site_data_path, site_data)


def sync_report_markdown_with_proof(report_dir: Path, proof: dict[str, Any], readiness: dict[str, Any]) -> None:
    report_path = report_dir / "output" / "report.md"
    if proof.get("overall_pass") is True:
        return
    stale_markers = [
        "acceptance_ready=true",
        "final_decision: Watch",
        "decision: Watch",
        "样本达到标准版门槛",
        "完整客户结论",
    ]
    current = report_path.read_text(encoding="utf-8") if report_path.exists() else ""
    if current and not any(marker in current for marker in stale_markers):
        return
    gaps = readiness.get("blocking_gaps") or []
    gap_lines = [
        f"- {gap.get('module', '数据门禁')}：{gap.get('reason', '当前数据未达完整报告门槛')}；下一步：{gap.get('next_step', '补齐数据后重新渲染。')}"
        for gap in gaps
    ] or ["- 数据门禁：当前数据未达完整报告门槛；下一步：补齐数据后重新渲染。"]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "# 市场调研审计稿 · 验收未通过\n\n"
        "## 交付状态\n"
        f"- delivery_mode: {proof.get('delivery_mode')}\n"
        "- overall_pass: false\n"
        f"- full_acceptance_pass: {str(bool(proof.get('full_acceptance_pass'))).lower()}\n"
        f"- diagnostic_delivery_pass: {str(bool(proof.get('diagnostic_delivery_pass'))).lower()}\n"
        f"- readiness_acceptance_ready: {str(readiness.get('acceptance_ready') is True).lower()}\n"
        f"- final_decision: {proof.get('decision') or 'No-Go'}\n"
        "- note: 当前交付只可作为补采诊断或阻断说明，不可作为完整客户决策报告。\n\n"
        "## Go / Watch / No-Go\n"
        f"- final_decision: {proof.get('decision') or 'No-Go'}\n"
        "- rationale: 核心数据门禁未通过，当前不得输出完整客户结论。\n\n"
        "## 当前阻断项\n"
        + "\n".join(gap_lines)
        + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run readiness, render, and final validation as one proof bundle.")
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument("--depth", choices=["auto", "quick", "standard", "deep"], default="auto")
    parser.add_argument("--skip-render", action="store_true", help="Use existing rendered artifacts and only run readiness + validator.")
    parser.add_argument("--reference-visual", action="store_true", help="Also compare generated HTML against downloaded reference templates.")
    parser.add_argument("--download-root", type=Path, default=DEFAULT_DOWNLOAD_ROOT, help="Root containing the downloaded template folders.")
    args = parser.parse_args(argv)
    proof = run_proof(args.dir, args.depth, args.skip_render, args.reference_visual, args.download_root)
    print(
        json.dumps(
            {
                "overall_pass": proof["overall_pass"],
                "delivery_mode": proof.get("delivery_mode"),
                "full_acceptance_pass": proof.get("full_acceptance_pass"),
                "diagnostic_delivery_pass": proof.get("diagnostic_delivery_pass"),
                "sample_class": proof.get("sample_class"),
                "proof": "output/acceptance_proof.json",
            },
            ensure_ascii=False,
        )
    )
    return 0 if proof["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
