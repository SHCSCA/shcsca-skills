#!/usr/bin/env python3
from pathlib import Path
import argparse
import json
import sys


SCRIPT_DIR = Path(__file__).resolve().parent
ORCHESTRATOR_SCRIPTS = SCRIPT_DIR.parents[2] / "scripts"
sys.path.insert(0, str(ORCHESTRATOR_SCRIPTS))

import critic_runner


HTML_DOCS = {
    "market_depth": "output/html_reports/market-depth-report.html",
    "lifecycle_strategy": "output/html_reports/lifecycle-strategy-report.html",
    "demand_gap": "output/html_reports/demand-gap-report.html",
}


def load_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_rendered_docs(report_dir: Path) -> dict[str, str]:
    docs = {}
    for key, rel_path in HTML_DOCS.items():
        path = report_dir / rel_path
        if path.exists():
            docs[key] = path.read_text(encoding="utf-8")
    index_path = report_dir / "output/html_reports/report.html"
    if index_path.exists():
        docs["index"] = index_path.read_text(encoding="utf-8")
    compat_path = report_dir / "output/report.html"
    if compat_path.exists():
        docs["compat_index"] = compat_path.read_text(encoding="utf-8")
    return docs


def load_view_models(report_dir: Path) -> dict[str, dict]:
    return {
        "market_depth_view.json": load_json(report_dir / "analysis/market_depth_view.json", {}),
        "lifecycle_strategy_view.json": load_json(report_dir / "analysis/lifecycle_strategy_view.json", {}),
        "demand_gap_view.json": load_json(report_dir / "analysis/demand_gap_view.json", {}),
    }


def run(report_dir: Path, decision: str, previous_review_path: Path | None = None, previous_plan_path: Path | None = None) -> dict:
    data_pack = load_json(report_dir / "data/normalized/normalized_data_pack.json", {})
    if not data_pack:
        data_pack = load_json(report_dir / "data/data_pack.json", {})
    analysis_plan = load_json(report_dir / "analysis/analysis_plan.json", {})
    delivery_path = report_dir / "output/delivery_result.json"
    delivery = load_json(delivery_path, {})
    rendered_docs = load_rendered_docs(report_dir)
    view_models = load_view_models(report_dir)

    previous_review = load_json(previous_review_path, None) if previous_review_path else None
    previous_plan = load_json(previous_plan_path, None) if previous_plan_path else None
    if previous_review and previous_plan:
        critic_review = critic_runner.write_critic_outputs(
            report_dir,
            data_pack,
            analysis_plan,
            delivery,
            decision,
            draft_review=previous_review,
            refinement_plan=previous_plan,
            rendered_docs=rendered_docs,
            view_models=view_models,
        )
        next_decision = decision
    else:
        critic_review = critic_runner.build_critic_review(
            data_pack,
            analysis_plan,
            delivery,
            decision,
            round_id=0,
            rendered_docs=rendered_docs,
            view_models=view_models,
        )
        refinement_plan = critic_runner.build_refinement_plan(critic_review, decision)
        next_decision = critic_runner.apply_refinement_plan(delivery, refinement_plan, decision)
        write_json(report_dir / "analysis/critic_review.json", critic_review)
        write_json(report_dir / "analysis/refinement_plan.json", refinement_plan)
        if next_decision != decision:
            write_json(delivery_path, delivery)

    result = {
        "decision": next_decision,
        "pass": critic_review.get("pass"),
        "score": critic_review.get("score"),
        "critic_review": "analysis/critic_review.json",
        "refinement_plan": "analysis/refinement_plan.json",
    }
    write_json(report_dir / "analysis/critic_decision.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the internal market research critic child module.")
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument("--decision", required=True)
    parser.add_argument("--previous-review", type=Path)
    parser.add_argument("--previous-plan", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(run(args.dir, args.decision, args.previous_review, args.previous_plan), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
