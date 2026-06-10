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


def _matching_brace(css: str, open_index: int) -> int:
    depth = 0
    for index in range(open_index, len(css)):
        char = css[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return len(css) - 1


def _scope_selector(selector: str, scope: str) -> str:
    leading = re.match(r"\s*", selector).group(0)
    stripped = selector.strip()
    if not stripped:
        return selector
    scoped: list[str] = []
    for part in stripped.split(","):
        item = part.strip()
        if not item:
            continue
        if item == ":root" or item == "body":
            scoped.append(scope)
        elif item.startswith("body."):
            scoped.append(item)
        elif item.startswith("html"):
            scoped.append(scope)
        else:
            scoped.append(f"{scope} {item}")
    return leading + ", ".join(scoped)


def scope_reference_style(css: str, scope: str) -> str:
    """Scope a downloaded template stylesheet to a report body class."""
    output: list[str] = []
    position = 0
    while position < len(css):
        open_index = css.find("{", position)
        if open_index == -1:
            output.append(css[position:])
            break
        selector = css[position:open_index]
        close_index = _matching_brace(css, open_index)
        body = css[open_index + 1 : close_index]
        stripped = selector.strip()
        if stripped.startswith("@"):
            output.append(selector + "{" + scope_reference_style(body, scope) + "}")
        else:
            output.append(_scope_selector(selector, scope) + "{" + body + "}")
        position = close_index + 1
    return "".join(output).strip()


def reference_css_bundle() -> str:
    body_scopes = {
        "market_depth": "body.template-market",
        "lifecycle_strategy": "body.template-lifecycle",
        "demand_gap": "body.template-demand",
    }
    sections = []
    for report_key, scope in body_scopes.items():
        sections.append(f"/* canonical reference template: {report_key} */\n{scope_reference_style(read_reference_style(report_key), scope)}")
    return "\n\n".join(sections)


def apply_reference_style(report_key: str, html_doc: str) -> str:
    """Replace child report inline CSS with the canonical downloaded template CSS."""
    style = read_reference_style(report_key)
    replacement = f"<style>\n{style}\n</style>"
    if re.search(r"<style\b[^>]*>.*?</style>", html_doc, flags=re.S | re.I):
        return re.sub(r"<style\b[^>]*>.*?</style>", replacement, html_doc, count=1, flags=re.S | re.I)
    return html_doc.replace("</head>", replacement + "\n</head>")
