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


def run_step(name: str, command: list[str], cwd: Path) -> dict[str, Any]:
    started_at = utc_now()
    result = subprocess.run(command, cwd=str(cwd), text=True, capture_output=True, check=False)
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


def proof_markdown(proof: dict[str, Any]) -> str:
    lines = [
        "# Acceptance Proof",
        "",
        f"- Report directory: `{proof['report_dir']}`",
        f"- Checked at: `{proof['checked_at']}`",
        f"- Overall pass: `{proof['overall_pass']}`",
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
            "decision": None,
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
    if can_render and not skip_render:
        steps.append(run_step("render", [sys.executable, str(RENDERER), "--dir", str(report_dir)], repo_root))

    if all(step["pass"] for step in steps):
        steps.append(run_step("validate", [sys.executable, str(VALIDATOR), "--dir", str(report_dir)], repo_root))

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

    render_passed = any(step["name"] == "render" and step["pass"] for step in steps)
    validate_passed = any(step["name"] == "validate" and step["pass"] for step in steps)
    can_trust_delivery = render_passed or validate_passed
    delivery = load_json(report_dir / "output" / "delivery_result.json", {}) if can_trust_delivery else {}
    critic = load_json(report_dir / "analysis" / "critic_review.json", {}) if can_trust_delivery else {}
    step_pass = all(step["pass"] for step in steps if not (step["name"] == "readiness" and can_render))
    readiness_pass = readiness.get("acceptance_ready") is True
    critic_pass = critic.get("pass") is True if can_trust_delivery else False
    proof = {
        "report_dir": str(report_dir),
        "checked_at": utc_now(),
        "overall_pass": bool(step_pass and readiness_pass and critic_pass),
        "sample_class": readiness.get("sample_class"),
        "decision": delivery.get("decision"),
        "readiness": readiness,
        "delivery_status": delivery.get("status"),
        "critic_pass": critic.get("pass"),
        "critic_score": critic.get("score"),
        "critic_summary": "analysis/critic_summary.md" if can_trust_delivery and (report_dir / "analysis" / "critic_summary.md").exists() else None,
        "reference_visual_compare": "output/template_reference_visual_compare/template_reference_visual_compare.json"
        if reference_visual and (report_dir / "output/template_reference_visual_compare/template_reference_visual_compare.json").exists()
        else None,
        "stale_delivery_ignored": not can_trust_delivery and (report_dir / "output" / "delivery_result.json").exists(),
        "steps": steps,
    }
    write_json(report_dir / "output" / "acceptance_proof.json", proof)
    (report_dir / "output" / "acceptance_proof.md").write_text(proof_markdown(proof), encoding="utf-8")
    return proof


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run readiness, render, and final validation as one proof bundle.")
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument("--depth", choices=["auto", "quick", "standard", "deep"], default="auto")
    parser.add_argument("--skip-render", action="store_true", help="Use existing rendered artifacts and only run readiness + validator.")
    parser.add_argument("--reference-visual", action="store_true", help="Also compare generated HTML against downloaded reference templates.")
    parser.add_argument("--download-root", type=Path, default=DEFAULT_DOWNLOAD_ROOT, help="Root containing the downloaded template folders.")
    args = parser.parse_args(argv)
    proof = run_proof(args.dir, args.depth, args.skip_render, args.reference_visual, args.download_root)
    print(json.dumps({"overall_pass": proof["overall_pass"], "sample_class": proof.get("sample_class"), "proof": "output/acceptance_proof.json"}, ensure_ascii=False))
    return 0 if proof["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
