#!/usr/bin/env python3
"""Shared renderer for internal amz market research child modules."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

from site_assets import attach_site_chrome, write_basic_site_assets

REPORT_KEY_BY_OUTPUT = {
    "market-depth-report.html": "market_depth",
    "lifecycle-strategy-report.html": "lifecycle_strategy",
    "demand-gap-report.html": "demand_gap",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_default(path: Path, default: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def table_from_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p>数据缺口：当前 view model 没有可展示表格行，需补充样本后再细化。</p>"
    headers = list(rows[0].keys())[:8]
    head = "".join(f"<th>{esc(header)}</th>" for header in headers)
    body = "".join("<tr>" + "".join(f"<td>{esc(row.get(header, ''))}</td>" for header in headers) + "</tr>" for row in rows[:30])
    return f"<table class=\"evidence-table insight-table\"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


def body_from_view(title: str, view: dict[str, Any]) -> str:
    kpis = "".join(
        f"<article class=\"kpi-card\"><div class=\"kpi-label\">{esc(item.get('label'))}</div><div class=\"kpi-value\">{esc(item.get('value'))}</div><div class=\"kpi-sub\">{esc(item.get('subtext'))}</div></article>"
        for item in (view.get("kpis") or [])[:8]
        if isinstance(item, dict)
    )
    limitations = "".join(f"<li>{esc(item)}</li>" for item in (view.get("limitations") or [])[:12])
    tables = []
    for rows in (view.get("tables") or {}).values():
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            tables.append(table_from_rows(rows))
    table_html = "".join(tables) or table_from_rows([])
    return f"""
<main class="child-report">
  <header class="report-header">
    <h1>{esc(title)}</h1>
    <div class="kpi-grid">{kpis}</div>
  </header>
  <section>
    <span class="section-number">01</span>
    <h2>客户安全视图</h2>
    <div class="insight-box">证据强度：{esc(view.get('evidence_strength'))}；样本覆盖和数据缺口来自主控 view model。</div>
  </section>
  <section>
    <span class="section-number">02</span>
    <h2>样本覆盖</h2>
    {table_html}
  </section>
  <section>
    <span class="section-number">03</span>
    <h2>数据缺口</h2>
    <details class="evidence-drawer" open><summary>建议动作</summary><div class="drawer-body"><ul>{limitations or '<li>暂无新增缺口。</li>'}</ul></div></details>
  </section>
</main>
""".strip()


def render_child_report(report_dir: Path, module_dir: Path, view_file: str, output_file: str, title: str, title_token: str, body_token: str) -> Path:
    report_key = REPORT_KEY_BY_OUTPUT.get(output_file)
    html_doc = ""
    if report_key:
        try:
            from customer_safety import redact_customer_html
            from render_dashboard_html import renderer_callbacks
            from report_renderers import build_report_documents

            data_pack = load_json_default(report_dir / "data" / "normalized" / "normalized_data_pack.json", {})
            if not data_pack:
                data_pack = load_json_default(report_dir / "data" / "data_pack.json", {})
            analysis_plan = load_json_default(report_dir / "analysis" / "analysis_plan.json", {})
            market_size = load_json_default(report_dir / "analysis" / "market_size.json", {})
            voc = load_json_default(report_dir / "analysis" / "voc.json", {})
            opportunity = load_json_default(report_dir / "analysis" / "opportunity.json", {})
            profitability = load_json_default(report_dir / "analysis" / "profitability.json", {})
            lifecycle = load_json_default(report_dir / "analysis" / "lifecycle_strategy.json", {})
            demand_gap = load_json_default(report_dir / "analysis" / "demand_gap.json", {})
            delivery = load_json_default(report_dir / "output" / "delivery_result.json", {})
            decision = str(delivery.get("decision") or "Watch")
            docs, _ = build_report_documents(
                data_pack,
                analysis_plan,
                market_size,
                voc,
                opportunity,
                profitability,
                lifecycle,
                demand_gap,
                delivery,
                decision,
                renderer_callbacks(),
            )
            html_doc = redact_customer_html(docs[report_key], data_pack)
        except Exception:
            html_doc = ""
    if not html_doc:
        view = load_json(report_dir / "analysis" / view_file)
        template = next((module_dir / "templates").glob("*.html")).read_text(encoding="utf-8")
        html_doc = template.replace(title_token, esc(title)).replace(body_token, body_from_view(title, view))
        html_doc = attach_site_chrome(html_doc)
    write_basic_site_assets(report_dir)
    output_path = report_dir / "output" / "html_reports" / output_file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html_doc, encoding="utf-8")
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument("--module-dir", required=True, type=Path)
    parser.add_argument("--view-file", required=True)
    parser.add_argument("--output-file", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--title-token", required=True)
    parser.add_argument("--body-token", required=True)
    args = parser.parse_args(argv)
    print(render_child_report(args.dir, args.module_dir, args.view_file, args.output_file, args.title, args.title_token, args.body_token))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
