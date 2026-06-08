#!/usr/bin/env python3
"""Canonical downloaded template assets for customer HTML reports."""

from __future__ import annotations

import re
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
CANONICAL_DIR = SKILL_DIR / "assets" / "canonical_templates"

REFERENCE_HTML = {
    "market_depth": CANONICAL_DIR / "market-depth-reference.html",
    "lifecycle_strategy": CANONICAL_DIR / "lifecycle-strategy-reference.html",
    "demand_gap": CANONICAL_DIR / "demand-gap-reference.html",
}


def read_reference_style(report_key: str) -> str:
    """Return the exact style block from the user's canonical report template."""
    path = REFERENCE_HTML[report_key]
    html = path.read_text(encoding="utf-8")
    match = re.search(r"<style\b[^>]*>(.*?)</style>", html, flags=re.S | re.I)
    if not match:
        raise ValueError(f"canonical template missing style block: {path}")
    return match.group(1).strip()


def apply_reference_style(report_key: str, html_doc: str) -> str:
    """Replace child report inline CSS with the canonical downloaded template CSS."""
    style = read_reference_style(report_key)
    replacement = f"<style>\n{style}\n</style>"
    if re.search(r"<style\b[^>]*>.*?</style>", html_doc, flags=re.S | re.I):
        return re.sub(r"<style\b[^>]*>.*?</style>", replacement, html_doc, count=1, flags=re.S | re.I)
    return html_doc.replace("</head>", replacement + "\n</head>")
