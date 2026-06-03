#!/usr/bin/env python3
"""Reusable HTML and formatting helpers for market research report rendering."""

from __future__ import annotations

import html
import re
from typing import Any


def clean(value: Any) -> str:
    text = "" if value is None else str(value)
    replacements = {
        "\r\n": " ",
        "\n": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return " ".join(text.split())


def esc(value: Any) -> str:
    return html.escape(clean(value), quote=True)


def num(value: Any) -> str:
    if value in (None, ""):
        return "-"
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return esc(value)


def money(value: Any, currency: str = "$") -> str:
    if value in (None, ""):
        return "-"
    try:
        return f"{currency}{float(value):,.2f}"
    except (TypeError, ValueError):
        return esc(value)


def pct(value: Any) -> str:
    if value in (None, ""):
        return "-"
    try:
        return f"{float(value):.1f}%"
    except (TypeError, ValueError):
        return esc(value)


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def first(*values: Any, default: Any = "-") -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return default


def truncate(value: Any, limit: int = 100) -> str:
    text = clean(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def has_cjk(value: Any) -> bool:
    return re.search(r"[\u4e00-\u9fff]", clean(value)) is not None


def table(
    headers: list[str],
    rows: list[list[Any]],
    class_name: str = "evidence-table",
    filter_options: list[tuple[str, str]] | None = None,
    row_filters: list[Any] | None = None,
) -> str:
    head = "".join(f"<th>{esc(header)}</th>" for header in headers)
    body_rows = []
    for idx, row in enumerate(rows):
        row_filter = row_filters[idx] if row_filters and idx < len(row_filters) else ""
        filter_attr = f" data-filter=\"{esc(row_filter)}\"" if row_filter not in (None, "") else ""
        body_rows.append("<tr" + filter_attr + ">" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>")
    body = "\n".join(body_rows)
    rendered_table = f"<table class=\"{class_name}\"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
    if not filter_options:
        return rendered_table
    buttons = []
    for idx, (label, filter_value) in enumerate(filter_options):
        active = " active" if idx == 0 else ""
        pressed = "true" if idx == 0 else "false"
        buttons.append(
            f"<button class=\"filter-btn{active}\" type=\"button\" data-filter=\"{esc(filter_value)}\" aria-pressed=\"{pressed}\">{esc(label)}</button>"
        )
    return f"<div class=\"filterable-table\"><div class=\"filter-bar\">{''.join(buttons)}</div>{rendered_table}</div>"


def table_inner(headers: list[str], rows: list[list[Any]]) -> str:
    rendered = table(headers, rows)
    return rendered.removeprefix("<table class=\"evidence-table\">").removesuffix("</table>")


def kpi_card(label: str, value: Any, sub: Any = "", tone: str = "") -> str:
    tone_class = f" {tone}" if tone else ""
    return (
        f"<article class=\"kpi-card{tone_class}\">"
        f"<div class=\"kpi-label\">{esc(label)}</div>"
        f"<div class=\"kpi-value\">{esc(value)}</div>"
        f"<div class=\"kpi-sub\">{esc(sub)}</div>"
        "</article>"
    )


def kpi_card_html(label: str, value_html: str, sub: Any = "", tone: str = "") -> str:
    tone_class = f" {tone}" if tone else ""
    return (
        f"<article class=\"kpi-card{tone_class}\">"
        f"<div class=\"kpi-label\">{esc(label)}</div>"
        f"<div class=\"kpi-value has-tags\">{value_html}</div>"
        f"<div class=\"kpi-sub\">{esc(sub)}</div>"
        "</article>"
    )


def metric(label: str, value: Any, sub: Any = "") -> str:
    return f"<div class=\"metric\"><b>{esc(value)}</b><span>{esc(label)} · {esc(sub)}</span></div>"


def tag(value: Any, tone: str = "") -> str:
    tone_class = f" {tone}" if tone else ""
    return f"<span class=\"tag{tone_class}\">{esc(value)}</span>"


def mini_chart(items: list[tuple[Any, float, Any]], tone: str = "") -> str:
    if not items:
        return "<div class=\"mini-chart\"><div class=\"bar-row\"><span>无数据</span><div class=\"bar\"><span style=\"--w:0%\"></span></div><b>-</b></div></div>"
    max_value = max(abs(value) for _, value, _ in items) or 1
    rows = []
    for label, value, display in items:
        width = max(3, min(100, abs(value) / max_value * 100))
        rows.append(
            f"<div class=\"bar-row\"><span>{esc(label)}</span>"
            f"<div class=\"bar {tone}\"><span style=\"--w:{width:.1f}%\"></span></div>"
            f"<b>{esc(display)}</b></div>"
        )
    return "<div class=\"mini-chart\">" + "".join(rows) + "</div>"


def details(title: str, body: str, open_attr: bool = False) -> str:
    opened = " open" if open_attr else ""
    return f"<details class=\"evidence-drawer\"{opened}><summary>{esc(title)}</summary><div class=\"drawer-body details-body\">{body}</div></details>"


def product_sales(product: dict[str, Any]) -> Any:
    return first(product.get("estimated_monthly_sales"), product.get("monthly_sales"), product.get("sales"), product.get("月销量"), default=None)


def product_revenue(product: dict[str, Any]) -> Any:
    return first(product.get("estimated_monthly_revenue"), product.get("monthly_revenue"), product.get("月销额"), default=None)


def product_price(product: dict[str, Any]) -> Any:
    return first(product.get("price"), product.get("价格"), default=None)


def product_reviews(product: dict[str, Any]) -> Any:
    return first(product.get("review_count"), product.get("reviews"), product.get("评论数"), default=None)


def relevant_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return products


def price_band(price: Any) -> str:
    value = as_float(price, -1)
    if value < 0:
        return "unknown"
    if value < 20:
        return "<$20"
    if value < 30:
        return "$20-$29"
    if value < 45:
        return "$30-$44"
    if value < 60:
        return "$45-$59"
    return "$60+"
