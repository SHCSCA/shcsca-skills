#!/usr/bin/env python3
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
ORCHESTRATOR_SCRIPTS = SCRIPT_DIR.parents[2] / "scripts"
sys.path.insert(0, str(ORCHESTRATOR_SCRIPTS))

from child_report_renderer import render_child_report


def render(report_dir: Path) -> Path:
    return render_child_report(
        report_dir,
        SCRIPT_DIR.parent,
        "market_depth_view.json",
        "market-depth-report.html",
        "市场深度调研报告",
        "{{MARKET_REPORT_TITLE}}",
        "{{MARKET_DEPTH_REPORT_BODY}}",
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", required=True, type=Path)
    args = parser.parse_args()
    print(render(args.dir))
