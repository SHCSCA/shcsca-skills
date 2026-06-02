#!/usr/bin/env python3
"""Static site asset contract for the three-report HTML bundle."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


HTML_BUNDLE_DIR = "output/html_reports"
COMPAT_INDEX_REPORT = "output/report.html"
ASSET_DIR = f"{HTML_BUNDLE_DIR}/assets"
HTML_REPORT_FILENAMES = {
    "index": "report.html",
    "market_depth": "market-depth-report.html",
    "lifecycle_strategy": "lifecycle-strategy-report.html",
    "demand_gap": "demand-gap-report.html",
}
HTML_REPORTS = {key: f"{HTML_BUNDLE_DIR}/{filename}" for key, filename in HTML_REPORT_FILENAMES.items()}
SITE_ASSETS = {
    "css": f"{ASSET_DIR}/report.css",
    "js": f"{ASSET_DIR}/report.js",
    "data": f"{ASSET_DIR}/report-data.json",
}
INTERACTIVE_FEATURES = [
    "table_filter",
    "table_sort",
    "tabs",
    "evidence_drawer",
    "chart_linking",
    "mobile_nav",
]

TEMPLATE_REFERENCE_REPORTS = {
    "market_depth": "downloadpage/143101 AI plush market scan template",
    "lifecycle_strategy": "downloadpage/143511 AI plush lifecycle strategy template",
    "demand_gap": "downloadpage/143645 demand gap report template",
}

REPORT_CSS = """
:root{--site-bg:#f6f7f9;--site-ink:#172033;--site-muted:#667085;--site-line:#d7dde7;--site-accent:#2f6f8f;--site-accent-2:#b7791f;--site-danger:#b42318;--site-ok:#2f7d55}
.site-nav{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:12px;justify-content:space-between;padding:12px 22px;background:rgba(255,255,255,.94);border-bottom:1px solid var(--site-line);backdrop-filter:blur(10px)}
.site-nav a{color:var(--site-ink);text-decoration:none;font-size:13px;font-weight:800}.site-nav-links{display:flex;gap:8px;flex-wrap:wrap}.site-nav-links a{padding:7px 10px;border:1px solid transparent}.site-nav-links a:hover,.site-nav-links a:focus{border-color:var(--site-line);background:#f0f4f8}.site-nav-toggle{display:none}
.table-tools{display:flex;justify-content:flex-end;margin:8px 0}.table-tools input{width:min(320px,100%);border:1px solid var(--site-line);padding:9px 11px;font:13px/1.4 inherit;background:#fff;color:var(--site-ink)}
th[data-sortable]{cursor:pointer;user-select:none}th[data-sortable]::after{content:" ↕";color:rgba(255,255,255,.65);font-size:11px}.is-filtered-out{display:none!important}
.chart-container,.mini-chart,.evidence-table,.insight-table,.kpi-grid,.deep-dive-grid,.comp-deep-card,.opportunity-matrix{scroll-margin-top:76px}
.bar-row{transition:background .18s ease}.bar-row:hover{background:rgba(47,111,143,.08)}.bar-row.is-linked{outline:2px solid rgba(47,111,143,.22)}
.tab-list{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 16px}.tab-button{border:1px solid var(--site-line);background:#fff;color:var(--site-ink);padding:8px 12px;font-weight:800;cursor:pointer}.tab-button[aria-selected=true]{background:var(--site-ink);color:#fff}
.evidence-drawer{border:1px solid var(--site-line);background:#fff;margin:14px 0}.evidence-drawer summary{cursor:pointer;padding:12px 14px;font-weight:900;color:var(--site-ink)}.evidence-drawer .drawer-body{padding:0 14px 14px;color:var(--site-muted)}
body.template-market,body.template-lifecycle{background:#f4f2ef;color:#1a2744}
body.template-demand{background:#0b1220;color:#e6edf8}
.template-market .report-header,.template-lifecycle .report-header{background:linear-gradient(135deg,#1a2744 0%,#243460 52%,#3d6b9e 100%);color:#fff;border-bottom:6px solid #c8b8a6}
.template-demand .report-header,.template-demand .hero{background:radial-gradient(circle at 20% 0%,rgba(77,163,255,.25),transparent 35%),linear-gradient(135deg,#0b1220 0%,#111d31 62%,#173153 100%);color:#e6edf8;border-bottom:1px solid #2b4266}
.template-market .container,.template-lifecycle .container,.template-demand .container,.template-demand .wrap{width:min(1180px,calc(100% - 32px));margin:0 auto}
.template-market .section,.template-lifecycle .section,.template-demand .section,.template-demand .sec{margin:28px 0;padding:26px;border:1px solid rgba(26,39,68,.12);background:rgba(255,255,255,.9);box-shadow:0 10px 30px rgba(26,39,68,.06)}
.template-demand .section,.template-demand .sec{background:#111d31;border-color:#2b4266;box-shadow:0 12px 34px rgba(0,0,0,.28)}
.section-header{display:flex;align-items:flex-start;gap:14px;margin-bottom:18px}.section-number{display:inline-grid;place-items:center;min-width:34px;height:34px;background:#1a2744;color:#fff;font-weight:900}.template-demand .section-number{background:#4da3ff;color:#06111f}.section-title{margin:0;font-size:clamp(22px,3vw,34px);line-height:1.15;letter-spacing:0}.section-desc{margin:6px 0 0;color:#667085;max-width:860px}.template-demand .section-desc{color:#9fb3c8}
.kpi-grid,.chart-grid,.persona-grid,.bundle-grid,.phase-grid,.risk-grid,.summary-grid,.insight-grid,.supply-grid,.pricing-grid,.visual-grid,.prompt-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}
.kpi-card,.kpi,.card,.strategy-card,.bundle-card,.risk-card,.persona-card,.phase-card,.tl-card,.comp-deep-card,.pain-card,.joy-card{border:1px solid rgba(26,39,68,.12);background:#fff;padding:18px;min-width:0}
.template-demand .kpi-card,.template-demand .kpi,.template-demand .card,.template-demand .focus,.template-demand .warn,.template-demand .ok{background:#13243d;border-color:#2b4266;color:#e6edf8}
.kpi-value,.kpi b{display:block;font-size:clamp(24px,3vw,40px);line-height:1;font-weight:900;color:#3d6b9e}.template-demand .kpi-value,.template-demand .kpi b{color:#4da3ff}.kpi-label,.card-title,.chart-title{font-weight:900;color:#1a2744}.template-demand .kpi-label,.template-demand .card-title,.template-demand .chart-title{color:#e6edf8}.chart-subtitle,.muted,.quote-origin{color:#667085}.template-demand .chart-subtitle,.template-demand .muted,.template-demand .quote-origin{color:#9fb3c8}
.chart-container,.chart,.mini-chart{border:1px solid rgba(26,39,68,.12);background:#fff;padding:18px;min-height:220px}.template-demand .chart-container,.template-demand .chart,.template-demand .mini-chart{background:#13243d;border-color:#2b4266}
.chart-interpretation,.insight-box,.conclusion{border-left:4px solid #3d6b9e;background:#eef4f8;padding:16px;color:#1a2744}.template-demand .chart-interpretation,.template-demand .insight-box,.template-demand .conclusion{border-left-color:#4da3ff;background:#10213a;color:#dfe9f7}
.sku-table-wrap{overflow:auto;border:1px solid rgba(26,39,68,.14);background:#fff}table.sku,.comp-table{width:100%;border-collapse:collapse}table.sku th,table.sku td,.comp-table th,.comp-table td{padding:12px;border-bottom:1px solid rgba(26,39,68,.1);vertical-align:top}table.sku th,.comp-table th{background:#1a2744;color:#fff;text-align:left;position:relative}.type-badge,.supply-badge,.badge{display:inline-flex;align-items:center;gap:6px;padding:4px 8px;border:1px solid rgba(61,107,158,.25);background:#eef4f8;color:#1a2744;font-size:12px;font-weight:800}.template-demand .badge{background:#173153;border-color:#4da3ff;color:#e6edf8}
.filter-bar{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.filter-btn{border:1px solid rgba(26,39,68,.18);background:#fff;color:#1a2744;padding:8px 12px;font-weight:900;cursor:pointer}.filter-btn.active,.filter-btn[aria-pressed=true]{background:#1a2744;color:#fff}.template-demand .filter-btn{background:#13243d;color:#e6edf8;border-color:#2b4266}.template-demand .filter-btn.active,.template-demand .filter-btn[aria-pressed=true]{background:#4da3ff;color:#06111f}
.timeline-grid{position:relative}.timeline-grid:before{content:"";position:absolute;left:18px;top:8px;bottom:8px;width:2px;background:rgba(61,107,158,.22)}.timeline-grid>.tl-card{position:relative;margin-left:26px}.priority-bar{height:8px;background:#d9e3ec;overflow:hidden}.priority-bar span{display:block;height:100%;background:#3d6b9e}.template-demand .priority-bar{background:#263a59}.template-demand .priority-bar span{background:#4da3ff}
.quote-grid,.voc-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}.quote-cn{font-size:16px;font-weight:900;line-height:1.55}.template-demand .mode-r2,.template-demand .mode-r3,.template-demand .mode-r4,.template-demand .mode-r5{border-color:#2b4266}
@media(max-width:760px){.site-nav{align-items:flex-start}.site-nav-toggle{display:block;border:1px solid var(--site-line);background:#fff;padding:7px 10px;font-weight:800}.site-nav-links{display:none;width:100%;padding-top:8px}.site-nav.is-open{flex-wrap:wrap}.site-nav.is-open .site-nav-links{display:flex;flex-direction:column}.table-tools{justify-content:stretch}.site-nav a{font-size:12px}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}}
""".strip()

REPORT_JS = """
(function(){
  const nav=document.querySelector('.site-nav');
  const toggle=document.querySelector('.site-nav-toggle');
  if(toggle&&nav){toggle.addEventListener('click',()=>nav.classList.toggle('is-open'));}
  document.querySelectorAll('table').forEach((table,idx)=>{
    if(table.dataset.enhanced)return;
    table.dataset.enhanced='true';
    const wrap=document.createElement('div');
    wrap.className='table-tools';
    const input=document.createElement('input');
    input.type='search';
    input.placeholder='筛选当前表格';
    input.setAttribute('aria-label','筛选当前表格');
    wrap.appendChild(input);
    table.parentNode.insertBefore(wrap,table);
    input.addEventListener('input',()=>{
      const q=input.value.trim().toLowerCase();
      table.querySelectorAll('tbody tr').forEach(row=>{
        row.classList.toggle('is-filtered-out',q&&!row.textContent.toLowerCase().includes(q));
      });
    });
    table.querySelectorAll('th').forEach((th,col)=>{
      th.dataset.sortable='true';
      th.addEventListener('click',()=>{
        const tbody=table.tBodies[0];
        if(!tbody)return;
        const dir=th.dataset.sortDir==='asc'?'desc':'asc';
        th.dataset.sortDir=dir;
        [...tbody.rows].sort((a,b)=>{
          const av=a.cells[col]?.textContent.trim()||'';
          const bv=b.cells[col]?.textContent.trim()||'';
          const an=parseFloat(av.replace(/[^0-9.-]/g,''));
          const bn=parseFloat(bv.replace(/[^0-9.-]/g,''));
          const cmp=Number.isFinite(an)&&Number.isFinite(bn)?an-bn:av.localeCompare(bv,'zh-CN');
          return dir==='asc'?cmp:-cmp;
        }).forEach(row=>tbody.appendChild(row));
      });
    });
  });
  document.querySelectorAll('[data-tabs]').forEach(group=>{
    const buttons=[...group.querySelectorAll('[data-tab-target]')];
    buttons.forEach(button=>button.addEventListener('click',()=>{
      buttons.forEach(btn=>btn.setAttribute('aria-selected',String(btn===button)));
      group.querySelectorAll('[data-tab-panel]').forEach(panel=>{
        panel.hidden=panel.dataset.tabPanel!==button.dataset.tabTarget;
      });
    }));
  });
  document.querySelectorAll('.filter-bar').forEach(bar=>{
    const buttons=[...bar.querySelectorAll('.filter-btn')];
    const targetId=bar.dataset.target;
    const table=targetId?document.getElementById(targetId):bar.parentNode.querySelector('table');
    if(!table)return;
    buttons.forEach(button=>button.addEventListener('click',()=>{
      const filter=button.dataset.filter||'all';
      buttons.forEach(btn=>{btn.classList.toggle('active',btn===button);btn.setAttribute('aria-pressed',String(btn===button));});
      table.querySelectorAll('tbody tr').forEach(row=>{
        const bucket=(row.dataset.filter||row.dataset.type||row.textContent).toLowerCase();
        row.classList.toggle('is-filtered-out',filter!=='all'&&!bucket.includes(filter.toLowerCase()));
      });
    }));
  });
  document.querySelectorAll('.mini-chart .bar-row').forEach(row=>{
    row.addEventListener('mouseenter',()=>row.classList.add('is-linked'));
    row.addEventListener('mouseleave',()=>row.classList.remove('is-linked'));
  });
})();
""".strip()


def site_nav_html(asset_prefix: str = "") -> str:
    return (
        "<nav class=\"site-nav\" aria-label=\"报告导航\">"
        "<button class=\"site-nav-toggle\" type=\"button\">目录</button>"
        "<a class=\"site-nav-brand\" href=\"" + asset_prefix + "report.html\">三合一报告</a>"
        "<div class=\"site-nav-links\">"
        "<a href=\"" + asset_prefix + "market-depth-report.html\">市场深度</a>"
        "<a href=\"" + asset_prefix + "lifecycle-strategy-report.html\">生命周期拓品</a>"
        "<a href=\"" + asset_prefix + "demand-gap-report.html\">需求断层</a>"
        "</div></nav>"
    )


def attach_site_chrome(html_doc: str, asset_prefix: str = "") -> str:
    css_href = f"{asset_prefix}assets/report.css"
    js_src = f"{asset_prefix}assets/report.js"
    if "assets/report.css" not in html_doc:
        html_doc = html_doc.replace("</head>", f"<link rel=\"stylesheet\" href=\"{css_href}\">\n</head>")
    if "site-nav" not in html_doc:
        html_doc = re.sub(r"<body\b([^>]*)>", lambda match: f"<body{match.group(1)}>\n{site_nav_html(asset_prefix)}", html_doc, count=1, flags=re.I)
    if "assets/report.js" not in html_doc:
        html_doc = html_doc.replace("</body>", f"<script src=\"{js_src}\" defer></script>\n</body>")
    return html_doc


def write_basic_site_assets(report_dir: Path, report_data: dict[str, Any] | None = None) -> None:
    asset_dir = report_dir / ASSET_DIR
    asset_dir.mkdir(parents=True, exist_ok=True)
    (asset_dir / "report.css").write_text(REPORT_CSS + "\n", encoding="utf-8")
    (asset_dir / "report.js").write_text(REPORT_JS + "\n", encoding="utf-8")
    if report_data is not None:
        (asset_dir / "report-data.json").write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8")
