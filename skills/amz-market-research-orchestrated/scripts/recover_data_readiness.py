#!/usr/bin/env python3
"""Run targeted Sorftime collection attempts before giving up on readiness."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from check_data_readiness import assess, write_json


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
NORMALIZER = SCRIPT_DIR / "normalize_data_pack.py"
KEYWORDS = SCRIPT_DIR / "collect_sorftime_keywords.py"
PRODUCTS = SCRIPT_DIR / "collect_sorftime_products.py"
PRODUCT_ENRICHMENT = SCRIPT_DIR / "collect_sorftime_product_enrichment.py"
REVIEWS = SCRIPT_DIR / "collect_sorftime_reviews.py"
TIKTOK = SCRIPT_DIR / "collect_sorftime_tiktok_signals.py"
SUPPLIERS = SCRIPT_DIR / "collect_sorftime_1688_suppliers.py"


Runner = Callable[[list[str]], subprocess.CompletedProcess[str]]


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def command_result(name: str, command: list[str], result: subprocess.CompletedProcess[str], started_at: str) -> dict[str, Any]:
    return {
        "name": name,
        "command": command,
        "started_at": started_at,
        "finished_at": utc_now(),
        "returncode": result.returncode,
        "stdout_tail": (result.stdout or "")[-4000:],
        "stderr_tail": (result.stderr or "")[-4000:],
        "pass": result.returncode == 0,
    }


def default_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=str(REPO_ROOT), text=True, capture_output=True, check=False)


def modules(readiness: dict[str, Any]) -> set[str]:
    return {str(gap.get("module") or "") for gap in readiness.get("blocking_gaps") or []}


def target_commands(report_dir: Path, readiness: dict[str, Any]) -> list[tuple[str, list[str]]]:
    failed = modules(readiness)
    depth = readiness.get("depth") or "standard"
    min_products = 60 if depth == "deep" else 30
    commands: list[tuple[str, list[str]]] = []
    report = str(report_dir)

    if "keyword_sample_depth" in failed:
        commands.append(("keywords", [sys.executable, str(KEYWORDS), "--dir", report, "--min-keywords", "1200"]))

    if failed & {"product_sample_depth", "competitor_pool_depth", "market_segment_split"}:
        product_command = [
            sys.executable,
            str(PRODUCTS),
            "--dir",
            report,
            "--min-products",
            str(min_products),
            "--max-seeds",
            "8",
            "--max-pages",
            "3",
            "--site",
            "US",
        ]
        if "market_segment_split" in failed:
            product_command.extend(["--min-segments", "3", "--min-per-segment", "10"])
        commands.append(("products", product_command))
        commands.append(
            (
                "product_enrichment",
                [
                    sys.executable,
                    str(PRODUCT_ENRICHMENT),
                    "--dir",
                    report,
                    "--max-products",
                    "10",
                    "--max-pages",
                    "1",
                    "--site",
                    "US",
                ],
            )
        )

    if failed & {"supplier_quote_depth", "supplier_quote_quality", "supplier_quote_price_spread"}:
        commands.append(
            (
                "suppliers_1688",
                [
                    sys.executable,
                    str(SUPPLIERS),
                    "--dir",
                    report,
                    "--min-valid-quotes",
                    "50",
                    "--max-rounds",
                    "5",
                    "--force-rounds",
                ],
            )
        )

    warning_modules = {str(item.get("module") or "") for item in readiness.get("warnings") or []}
    if "review_sample_depth" in warning_modules and failed - {"source_lineage"}:
        commands.append(("reviews", [sys.executable, str(REVIEWS), "--dir", report, "--review-type", "Both"]))
    if "tiktok_signal_depth" in warning_modules and failed - {"source_lineage"}:
        commands.append(
            (
                "tiktok",
                [
                    sys.executable,
                    str(TIKTOK),
                    "--dir",
                    report,
                    "--site",
                    "US",
                    "--max-seeds",
                    "4",
                    "--max-pages",
                    "1",
                    "--max-products-detail",
                    "3",
                    "--video-pages",
                    "1",
                ],
            )
        )

    if commands:
        commands.append(("normalize", [sys.executable, str(NORMALIZER), "--dir", report]))
    return commands


def recover_readiness(report_dir: Path, depth: str = "auto", max_rounds: int = 2, runner: Runner = default_runner) -> dict[str, Any]:
    report_dir = report_dir.resolve()
    started_at = utc_now()
    initial = assess(report_dir, depth)
    rounds: list[dict[str, Any]] = []
    current = initial

    for round_number in range(1, max_rounds + 1):
        if current.get("acceptance_ready"):
            break
        commands = target_commands(report_dir, current)
        if not commands:
            rounds.append({"round": round_number, "commands": [], "readiness_after": current, "stopped_reason": "no_target_commands"})
            break

        command_results: list[dict[str, Any]] = []
        for name, command in commands:
            command_started = utc_now()
            result = runner(command)
            command_results.append(command_result(name, command, result, command_started))

        current = assess(report_dir, depth)
        write_json(report_dir / "data" / "normalized" / "data_readiness_report.json", current)
        rounds.append({"round": round_number, "commands": command_results, "readiness_after": current})

        previous_modules = modules(rounds[-2]["readiness_after"]) if len(rounds) > 1 else modules(initial)
        if not current.get("acceptance_ready") and modules(current) == previous_modules:
            break

    final = current
    final_ready = bool(final.get("acceptance_ready") or final.get("partial_report_ready"))
    report = {
        "started_at": started_at,
        "finished_at": utc_now(),
        "report_dir": str(report_dir),
        "depth": final.get("depth") or depth,
        "initial_readiness": initial,
        "rounds": rounds,
        "final_readiness": final,
        "recovery_ready": final_ready,
        "acceptance_ready": bool(final.get("acceptance_ready")),
        "partial_report_ready": bool(final.get("partial_report_ready")),
        "unresolved_modules": sorted(modules(final)),
    }
    write_json(report_dir / "data" / "normalized" / "readiness_recovery_report.json", report)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recover report data readiness with targeted Sorftime collectors.")
    parser.add_argument("--dir", required=True, type=Path, help="Report directory containing data/data_pack.json.")
    parser.add_argument("--depth", choices=["auto", "quick", "standard", "deep"], default="auto")
    parser.add_argument("--max-rounds", type=int, default=2)
    args = parser.parse_args(argv)
    report = recover_readiness(args.dir, args.depth, args.max_rounds)
    print(json.dumps({"recovery_ready": report["recovery_ready"], "unresolved_modules": report["unresolved_modules"], "report": "data/normalized/readiness_recovery_report.json"}, ensure_ascii=False))
    return 0 if report["recovery_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
