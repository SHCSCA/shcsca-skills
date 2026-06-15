#!/usr/bin/env python3
"""Static site asset contract for the three-report HTML bundle."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from canonical_template_assets import reference_css_bundle


SCRIPT_DIR = Path(__file__).resolve().parent
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
    "echarts": f"{ASSET_DIR}/echarts.min.js",
}
INTERACTIVE_FEATURES = [
    "table_filter",
    "table_sort",
    "tabs",
    "chart_linking",
    "pc_anchor_nav",
    "evidence_drawer",
]

TEMPLATE_REFERENCE_REPORTS = {
    "market_depth": "downloadpage/143101 AI plush market scan template",
    "lifecycle_strategy": "downloadpage/143511 AI plush lifecycle strategy template",
    "demand_gap": "downloadpage/143645 demand gap report template",
}

REPORT_CSS = """
:root{--site-bg:#f6f7f9;--site-ink:#172033;--site-muted:#667085;--site-line:#d7dde7;--site-accent:#2f6f8f;--site-accent-2:#b7791f;--site-danger:#b42318;--site-ok:#2f7d55}
*{box-sizing:border-box}html,body{max-width:100%;overflow-x:hidden}body{overflow-wrap:anywhere}
.site-nav{position:absolute;top:18px;right:32px;left:auto;z-index:20;display:flex;align-items:center;gap:12px;justify-content:flex-end;padding:0;background:transparent;border:0;backdrop-filter:none}
.site-nav a{color:rgba(255,255,255,.82);text-decoration:none;font-size:13px;font-weight:800}.site-nav-brand{display:none}.site-nav-links{display:flex;gap:8px;flex-wrap:wrap}.site-nav-links a{padding:7px 10px;border:1px solid transparent}.site-nav-links a:hover,.site-nav-links a:focus{border-color:rgba(255,255,255,.28);background:rgba(255,255,255,.08)}.site-nav-toggle{display:none}
.table-tools{display:flex;justify-content:flex-end;margin:8px 0}.table-tools input{width:min(320px,100%);border:1px solid var(--site-line);padding:9px 11px;font:13px/1.4 inherit;background:#fff;color:var(--site-ink)}
th[data-sortable]{cursor:pointer;user-select:none}th[data-sortable]::after{content:" ↕";color:rgba(255,255,255,.65);font-size:11px}.is-filtered-out{display:none!important}
.chart-container,.mini-chart,.evidence-table,.insight-table,.kpi-grid,.deep-dive-grid,.comp-deep-card,.opportunity-matrix{scroll-margin-top:76px;max-width:100%}
.grid-2,.grid-3,.grid-4,.metric-strip{display:grid;gap:16px}.grid-2{grid-template-columns:repeat(2,minmax(0,1fr))}.grid-3,.metric-strip{grid-template-columns:repeat(3,minmax(0,1fr))}.grid-4{grid-template-columns:repeat(4,minmax(0,1fr))}
.bar-row{display:grid;grid-template-columns:minmax(120px,1.1fr) minmax(120px,2fr) 48px;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid rgba(26,39,68,.08);transition:background .18s ease}.bar-row:last-child{border-bottom:0}.bar-row>span:first-child{font-weight:800;color:#1a2744}.bar-row>b{font-variant-numeric:tabular-nums;text-align:right;color:#1a2744}.bar{height:8px;background:#ece7df;overflow:hidden}.bar span{display:block;height:100%;width:0;min-width:2px;background:#3d6b9e}.bar.good span{background:#6a9a7a}.bar.bad span{background:#c4705a}.bar.warn span{background:#c9a05a}.bar-row:hover{background:rgba(47,111,143,.08)}.bar-row.is-linked{outline:2px solid rgba(47,111,143,.22)}
.tab-list{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 16px}.tab-button{border:1px solid var(--site-line);background:#fff;color:var(--site-ink);padding:8px 12px;font-weight:800;cursor:pointer}.tab-button[aria-selected=true]{background:var(--site-ink);color:#fff}
.evidence-drawer{border:1px solid var(--site-line);background:#fff;margin:14px 0}.evidence-drawer summary{cursor:pointer;padding:12px 14px;font-weight:900;color:var(--site-ink)}.evidence-drawer .drawer-body{padding:0 14px 14px;color:var(--site-muted)}
body.template-index,body.template-market,body.template-lifecycle{background:#f4f2ef;color:#1a2744}
body.template-demand{background:#0b1220;color:#e6edf8}
.template-market .report-header,.template-lifecycle .report-header{background:linear-gradient(135deg,#1a2744 0%,#243460 52%,#3d6b9e 100%);color:#fff;border-bottom:6px solid #c8b8a6}
.template-index .report-header{background:#1a2744;color:#fff;padding:52px 60px 44px}.template-index .header-badge{display:inline-block;margin-bottom:18px;padding:5px 12px;border:1px solid rgba(168,200,232,.45);color:#a8c8e8;font-size:11px;letter-spacing:2px;text-transform:uppercase}.template-index h1{margin:0 0 12px;font-size:38px;line-height:1.16;letter-spacing:0}.template-index .subtitle{margin:0;color:rgba(255,255,255,.68);font-size:15px}.template-index .container{max-width:1200px;margin:0 auto;padding:36px 40px 56px}.template-index .report-index>.kpi-grid,.template-index .client-trust-grid{grid-template-columns:repeat(4,minmax(0,1fr));margin-bottom:24px}.template-index .report-card-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;margin-bottom:28px}.template-index .report-card{background:#fff;border:1px solid #e0ddd8;padding:24px;min-height:176px}.template-index .report-card a{display:flex;justify-content:space-between;gap:16px;color:#1a2744;text-decoration:none;font-size:19px;font-weight:900}.template-index .report-card strong{color:#3d6b9e;white-space:nowrap;font-size:13px}.template-index .report-card p{color:#657485;font-size:13px}.template-index .section{padding-top:28px}.template-index .section>.section-number{display:inline-flex;width:34px;height:34px;align-items:center;justify-content:center;background:#1a2744;color:#fff;font-size:13px;font-weight:800}.template-index .section>.section-title{display:inline-block;margin-left:10px;font-size:22px;font-weight:900}.template-index .footer{padding:20px 60px;color:#94a3b8;background:#111827;font-size:11px}
.template-index .kpi-card .kpi-value{font-size:30px;line-height:1.08;overflow-wrap:anywhere}.template-index .kpi-card:nth-child(2) .kpi-value,.template-index .kpi-card:nth-child(4) .kpi-value,.template-index .client-trust-grid .kpi-card:nth-child(4) .kpi-value{font-size:22px;line-height:1.15}.template-index .kpi-value.has-tags{font-size:13px;line-height:1.25}.template-index .metric-tags{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;margin:8px 0}.template-index .metric-tag{display:flex;align-items:baseline;gap:5px;padding:6px 8px;min-width:0}.template-index .metric-tag b{font-size:18px;line-height:1;color:#1a2744}.template-index .metric-tag span{font-size:11px;color:#657485}
.template-demand .report-header,.template-demand .hero{background:radial-gradient(circle at 20% 0%,rgba(77,163,255,.25),transparent 35%),linear-gradient(135deg,#0b1220 0%,#111d31 62%,#173153 100%);color:#e6edf8;border-bottom:1px solid #2b4266}
.template-market .container,.template-lifecycle .container,.template-demand .container,.template-demand .wrap{width:min(1200px,calc(100% - 32px));margin:0 auto}
.template-market .report-header,.template-lifecycle .report-header{padding:56px 60px 46px}
.template-market .report-header,.template-lifecycle .report-header{max-width:100%;overflow:hidden;position:relative}
.template-market .report-header h1,.template-lifecycle .report-header h1{max-width:min(100%,1180px);overflow-wrap:break-word;text-wrap:balance}
.template-market .report-header .subtitle,.template-lifecycle .report-header .subtitle{max-width:calc(100% - 260px)}
.template-market .report-header .header-meta,.template-lifecycle .report-header .header-meta{max-width:100%;min-width:0}
.template-market .site-nav,.template-lifecycle .site-nav{max-width:min(520px,calc(100% - 64px))}
.template-market #market-dashboard>.kpi-grid{grid-template-columns:repeat(4,minmax(0,1fr))}
.template-lifecycle #strategy-dashboard>.kpi-grid{grid-template-columns:repeat(5,minmax(0,1fr))}
.template-lifecycle .lifecycle-kpi-secondary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin:16px 0 18px}
.template-demand .wrap{max-width:1360px;padding:42px 0 56px}
.template-demand .hero{border:1px solid #2b4266;margin:0 0 28px;padding:44px 48px;background:radial-gradient(circle at 82% 18%,rgba(77,163,255,.2),transparent 34%),#101a2e}
.template-demand .hero .header-meta{grid-template-columns:repeat(4,minmax(0,1fr))}
.template-demand .container{width:100%;padding:0}
.template-market .section,.template-lifecycle .section,.template-demand .section,.template-demand .sec{margin:28px 0;padding:26px;border:1px solid rgba(26,39,68,.12);background:rgba(255,255,255,.9);box-shadow:0 10px 30px rgba(26,39,68,.06)}
.template-demand .section,.template-demand .sec{background:#111d31;border-color:#2b4266;box-shadow:0 12px 34px rgba(0,0,0,.28)}
.section-header{display:flex;align-items:flex-start;gap:14px;margin-bottom:18px}.section-number{display:inline-grid;place-items:center;min-width:34px;height:34px;background:#1a2744;color:#fff;font-weight:900}.template-demand .section-number{background:#4da3ff;color:#06111f}.section-title{margin:0;font-size:clamp(22px,3vw,34px);line-height:1.15;letter-spacing:0}.section-desc{margin:6px 0 0;color:#667085;max-width:860px}.template-demand .section-desc{color:#9fb3c8}
.kpi-grid,.chart-grid,.persona-grid,.bundle-grid,.phase-grid,.risk-grid,.summary-grid,.insight-grid,.supply-grid,.pricing-grid,.visual-grid,.prompt-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}
.kpi-card,.kpi,.card,.metric,.supply-card,.strategy-card,.bundle-card,.risk-card,.persona-card,.phase-card,.tl-card,.comp-deep-card,.pain-card,.joy-card{border:1px solid rgba(26,39,68,.12);background:#fff;padding:18px;min-width:0}
.prompt-card{max-height:260px;overflow:hidden;display:flex;flex-direction:column}.prompt-text{display:-webkit-box;-webkit-line-clamp:7;line-clamp:7;-webkit-box-orient:vertical;overflow:hidden}.prompt-note{margin-top:auto}
.template-demand .kpi-card,.template-demand .kpi,.template-demand .card,.template-demand .focus,.template-demand .warn,.template-demand .ok{background:#13243d;border-color:#2b4266;color:#e6edf8}
.kpi-value,.kpi b{display:block;font-size:clamp(24px,3vw,40px);line-height:1;font-weight:900;color:#3d6b9e}.template-demand .kpi-value,.template-demand .kpi b{color:#4da3ff}.kpi-label,.card-title,.chart-title{font-weight:900;color:#1a2744}.template-demand .kpi-label,.template-demand .card-title,.template-demand .chart-title{color:#e6edf8}.template-demand .sec .card-title,.template-demand .sec .chart-title{color:#1a2744}.chart-subtitle,.muted,.quote-origin{color:#667085}.template-demand .chart-subtitle,.template-demand .muted,.template-demand .quote-origin{color:#9fb3c8}.template-demand .sec .muted,.template-demand .sec .quote-origin{color:#667085}.section-header-spaced{margin-top:32px}.section-header-tight{margin-top:8px}.section-title-sm{font-size:16px}
.metric-strip{margin:16px 0}.metric b,.supply-value{display:block;font-size:26px;line-height:1.1;font-weight:900;color:#1a2744}.metric span,.supply-label,.supply-note{display:block;margin-top:8px;color:#667085;font-size:13px;line-height:1.45}.supply-value{margin-top:10px}.supply-card{min-height:112px}.supply-note{font-size:12px}
.template-market .pricing-grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:20px;margin-bottom:20px}.template-market .pricing-card{background:#fff;border:2px solid #e0ddd8;padding:28px 24px;text-align:center;position:relative;min-height:360px}.template-market .pricing-card.recommended{border-color:#3d6b9e}.template-market .pricing-card.recommended::before{content:"推荐切入";position:absolute;top:-12px;left:50%;transform:translateX(-50%);background:#3d6b9e;color:#fff;font-size:11px;font-weight:900;padding:3px 12px;letter-spacing:1px}.template-market .pricing-tier{font-size:12px;color:#8a9aaa;margin-bottom:8px;letter-spacing:1px;text-transform:uppercase}.template-market .pricing-price{font-size:36px;font-weight:900;color:#1a2744;letter-spacing:0;line-height:1.1}.template-market .pricing-desc{font-size:12px;color:#5a6a7a;margin:12px 0;line-height:1.55}.template-market .pricing-features{text-align:left;margin-top:16px}.template-market .pricing-feature{font-size:12px;color:#5a6a7a;padding:7px 0;border-bottom:1px solid #e0ddd8;display:flex;align-items:center;gap:8px}.template-market .pricing-feature:last-child{border-bottom:0}.template-market .pricing-feature::before{content:"-";color:#8a9aaa;font-size:10px}.template-market .pricing-feature.check::before{content:"✓";color:#6a9a7a;font-weight:900}
.template-market .visual-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:20px;margin-bottom:20px}.template-market .visual-card{background:#fff;border:1px solid #e0ddd8;padding:24px;min-width:0}.template-market .visual-card-title{font-size:14px;font-weight:900;color:#1a2744;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid #e0ddd8;display:flex;align-items:center;gap:8px}.template-market .visual-item{margin-bottom:14px;padding-bottom:14px;border-bottom:1px solid #e0ddd8}.template-market .visual-item:last-child{border-bottom:0;margin-bottom:0;padding-bottom:0}.template-market .visual-item-title{font-size:13px;font-weight:900;color:#1a2744;margin-bottom:4px}.template-market .visual-item-text{font-size:12px;color:#5a6a7a;line-height:1.65}
.template-market .prompt-grid{grid-template-columns:repeat(3,minmax(0,1fr));gap:20px;margin-bottom:20px}.template-market .prompt-card{background:#1a2744;color:#fff;padding:24px;position:relative;overflow:hidden;min-height:260px;max-height:260px;border:0}.template-market .prompt-card::before{content:"";position:absolute;right:-40px;bottom:-40px;width:120px;height:120px;border-radius:50%;background:rgba(255,255,255,.04)}.template-market .prompt-number{font-size:11px;letter-spacing:2px;color:rgba(255,255,255,.35);text-transform:uppercase;margin-bottom:10px}.template-market .prompt-scene{font-size:14px;font-weight:900;color:#7ab8e8;margin-bottom:12px}.template-market .prompt-text{font-size:11.5px;color:rgba(255,255,255,.7);line-height:1.7;font-family:"Courier New",monospace;background:rgba(0,0,0,.2);padding:12px;border-left:2px solid rgba(122,184,232,.4);position:relative;z-index:1}.template-market .prompt-note{font-size:11px;color:rgba(255,255,255,.45);margin-top:10px;font-style:italic;position:relative;z-index:1}
.template-market .supply-grid{grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;margin-bottom:20px}.template-market .supply-card{background:#fff;border:1px solid #e0ddd8;padding:20px;min-height:132px}.template-market .supply-label{font-size:11px;color:#8a9aaa;letter-spacing:.5px;margin:0 0 6px;text-transform:uppercase}.template-market .supply-value{font-size:20px;font-weight:900;color:#1a2744;margin:0 0 4px;line-height:1.18}.template-market .supply-note{font-size:11px;color:#5a6a7a;line-height:1.45;margin:0}
.chart-container,.chart{border:1px solid rgba(26,39,68,.12);background:#fff;padding:18px;min-height:220px}.chart-body{width:100%}.chart-h-260{height:260px}.chart-h-300{height:300px}.chart-h-320{height:320px}.chart-h-360{height:360px}.chart-h-500{height:500px}.mini-chart{border:1px solid rgba(26,39,68,.12);background:#fff;padding:14px;min-height:0}.card>.mini-chart{margin-top:12px;border-color:rgba(26,39,68,.1);background:#fbfcfd}.template-demand .chart-container,.template-demand .chart,.template-demand .mini-chart{background:#13243d;border-color:#2b4266}
.chart-interpretation,.insight-box,.conclusion{border-left:4px solid #3d6b9e;background:#eef4f8;padding:16px;color:#1a2744}.template-demand .chart-interpretation,.template-demand .insight-box,.template-demand .conclusion{border-left-color:#4da3ff;background:#10213a;color:#dfe9f7}
.sku-table-wrap,.filterable-table,.drawer-body,.details-body{max-width:100%;overflow-x:auto}.evidence-table,.insight-table{width:100%;max-width:100%;border-collapse:collapse;table-layout:auto;background:#fff}.evidence-table th,.evidence-table td,.insight-table th,.insight-table td{padding:12px 14px;border-bottom:1px solid rgba(26,39,68,.1);vertical-align:top;color:#1a2744;line-height:1.55}.evidence-table th,.insight-table th{background:#1a2744;color:#fff;text-align:left;font-weight:900}.evidence-table tbody tr:nth-child(even),.insight-table tbody tr:nth-child(even){background:#fbfaf8}.sku-table-wrap{overflow:auto;border:1px solid rgba(26,39,68,.14);background:#fff}table.sku,.comp-table{width:100%;border-collapse:collapse}table.sku th,table.sku td,.comp-table th,.comp-table td{padding:12px;border-bottom:1px solid rgba(26,39,68,.1);vertical-align:top}table.sku th,.comp-table th{background:#1a2744;color:#fff;text-align:left;position:relative}table.sku th:nth-child(5),table.sku td:nth-child(5){min-width:116px;white-space:nowrap;overflow-wrap:normal;word-break:normal;font-variant-numeric:tabular-nums}.supply-diagnostic-table{margin:18px 0 20px;border:1px solid #e0ddd8}.supply-diagnostic-table th:nth-child(2),.supply-diagnostic-table td:nth-child(2){width:120px;text-align:right;font-weight:900;font-variant-numeric:tabular-nums;white-space:nowrap}.supply-diagnostic-table th:nth-child(3),.supply-diagnostic-table td:nth-child(3){width:180px;white-space:nowrap}.type-badge,.supply-badge,.badge{display:inline-flex;align-items:center;gap:6px;padding:4px 8px;border:1px solid rgba(61,107,158,.25);background:#eef4f8;color:#1a2744;font-size:12px;font-weight:800}.template-demand .badge{background:#173153;border-color:#4da3ff;color:#e6edf8}
.comp-col-product{width:29%}.comp-col-price{width:7%}.comp-col-rating{width:7%}.comp-col-sales{width:8%}.comp-col-selling{width:31%}.comp-col-weakness{width:12%}.comp-col-tag{width:6%}.comp-table th:first-child,.comp-table td:first-child{width:112px;min-width:112px;white-space:nowrap;overflow-wrap:normal;word-break:normal}.comp-table .asin-token{display:inline-block;white-space:nowrap;overflow-wrap:normal;word-break:normal}.price-tag,.rating-stars,.comp-table th:nth-child(3),.comp-table td:nth-child(3),.comp-table th:nth-child(4),.comp-table td:nth-child(4),.comp-table th:nth-child(5),.comp-table td:nth-child(5),.comp-table td:nth-child(8){white-space:nowrap}.comp-table th:nth-child(5),.comp-table td:nth-child(5){min-width:96px}.comp-table td:nth-child(5){font-variant-numeric:tabular-nums}
.comp-product-cell{display:grid;grid-template-columns:64px minmax(0,1fr);gap:12px;align-items:start;min-width:0}.comp-product-thumb{width:64px;height:64px;object-fit:contain;background:#f8fafc;border:1px solid rgba(26,39,68,.1);display:block}.comp-product-thumb-diagnostic{width:64px;height:64px;display:grid;place-items:center;text-align:center;background:#fbfaf8;border:1px dashed rgba(201,160,90,.55);color:#667085;font-size:10px;line-height:1.25;font-weight:800;padding:4px}.comp-product-thumb-diagnostic span,.comp-deep-image-diagnostic span{display:block;color:#1a2744;font-weight:900}.comp-product-thumb-diagnostic em,.comp-deep-image-diagnostic em{display:block;margin-top:2px;color:#8a9aaa;font-style:normal;font-size:10px;font-weight:700;line-height:1.3}.comp-image-strip-card,.comp-image-diagnostic-card{margin:16px 0 0}.comp-image-diagnostic-card{border-left:4px solid #c9a05a;background:#fbfaf8}.comp-image-diagnostic-card p{margin:8px 0 0;color:#5a6a7a;font-size:13px;line-height:1.6}.comp-image-diagnostic-card strong{color:#1a2744}.comp-image-strip{display:grid;grid-template-columns:repeat(8,minmax(0,1fr));gap:10px}.comp-image-item{margin:0;min-width:0}.comp-image-thumb{width:100%;aspect-ratio:1/1;object-fit:contain;background:#f8fafc;border:1px solid rgba(26,39,68,.1);display:block}.comp-image-item figcaption{margin-top:6px;color:#5a6a7a;font-size:11px;line-height:1.35;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.comp-deep-image{width:100%;height:168px;object-fit:contain;background:#f8fafc;border-bottom:1px solid rgba(26,39,68,.1);display:block}.comp-deep-image-diagnostic{height:168px;display:grid;place-items:center;text-align:center;background:#fbfaf8;border-bottom:1px dashed rgba(201,160,90,.55);color:#667085;font-size:12px;line-height:1.45;padding:16px}
.filter-bar{display:flex;gap:8px;flex-wrap:wrap;margin:12px 0}.filter-btn{border:1px solid rgba(26,39,68,.18);background:#fff;color:#1a2744;padding:8px 12px;font-weight:900;cursor:pointer}.filter-btn.active,.filter-btn[aria-pressed=true]{background:#1a2744;color:#fff}.template-demand .filter-btn{background:#13243d;color:#e6edf8;border-color:#2b4266}.template-demand .filter-btn.active,.template-demand .filter-btn[aria-pressed=true]{background:#4da3ff;color:#06111f}
.sku-strategy-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;margin-bottom:22px}.sku-strategy-card{border:1px solid rgba(26,39,68,.14);background:#fff;padding:0;min-width:0;border-top:4px solid #3d6b9e;min-height:252px;display:flex;flex-direction:column;overflow:hidden}.sku-reference-thumb{width:100%;height:118px;object-fit:contain;background:#f8fafc;border:0;border-bottom:1px solid rgba(26,39,68,.1);display:block}.sku-reference-thumb.table-thumb{width:58px;height:58px;flex:0 0 58px;margin:0;border:1px solid rgba(26,39,68,.1)}.sku-title-cell{display:flex;align-items:flex-start;gap:10px;min-width:0}.sku-title-cell>div{min-width:0}.sku-strategy-head{display:flex;justify-content:space-between;gap:12px;align-items:center;color:#667085;font-size:12px;font-weight:900;padding:14px 16px;background:#f8fafc;border-bottom:1px solid rgba(26,39,68,.1)}.sku-strategy-head b{display:inline-grid;place-items:center;min-width:38px;height:38px;background:#1a2744;color:#fff}.sku-strategy-card h3{margin:16px 18px 14px;color:#1a2744;font-size:20px;line-height:1.25}.sku-strategy-meta{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0;margin:0 18px;border-top:1px solid rgba(26,39,68,.1);border-left:1px solid rgba(26,39,68,.08)}.sku-strategy-meta div{border-right:1px solid rgba(26,39,68,.08);border-bottom:1px solid rgba(26,39,68,.08);padding:10px 12px;min-height:70px}.sku-strategy-meta dt{font-size:11px;color:#667085;font-weight:900}.sku-strategy-meta dd{margin:4px 0 0;color:#1a2744;font-size:13px;line-height:1.45}.sku-strategy-card p{margin:auto 18px 18px;color:#5a6a7a;font-size:13px;line-height:1.65}.sku-title-text{color:#1a2744}.sku-muted{color:#8a9aaa;font-size:11px;line-height:1.45}.lifecycle-evidence-drawer{margin:16px 0 0}.lifecycle-evidence-drawer summary{background:#f8fafc;border-bottom:1px solid rgba(26,39,68,.08)}
.timeline-grid{position:relative}.timeline-grid:before{content:"";position:absolute;left:18px;top:8px;bottom:8px;width:2px;background:rgba(61,107,158,.22)}.timeline-grid>.tl-card{position:relative;margin-left:26px}.priority-bar{height:8px;background:#d9e3ec;overflow:hidden}.priority-bar span{display:block;height:100%;background:#3d6b9e}.template-demand .priority-bar{background:#263a59}.template-demand .priority-bar span{background:#4da3ff}
.persona-header,.tl-header,.bundle-header,.phase-header,.comp-deep-header{background:#1a2744;color:#fff;padding:14px 16px;font-weight:900}.persona-body,.phase-body,.tl-body,.bundle-body{padding:18px}.persona-price,.tag{display:inline-flex;align-items:center;width:max-content;margin-top:10px;padding:4px 10px;background:#eef4f8;color:#3d6b9e;font-size:12px;font-weight:900}.tl-time{font-size:11px;color:#667085;letter-spacing:.5px;text-transform:uppercase;margin-bottom:8px}.tl-skus,.bundle-items{font-size:13px;color:#5a6a7a;line-height:1.9}.tl-pain{font-size:12px;color:#667085;margin-top:10px;padding-top:10px;border-top:1px solid rgba(26,39,68,.1);font-style:italic}.bundle-pricing{display:flex;gap:14px;align-items:baseline;margin-top:16px;padding-top:16px;border-top:1px solid rgba(26,39,68,.1)}.bundle-pricing .orig{color:#8a9aaa;text-decoration:line-through}.bundle-pricing .final{font-size:24px;font-weight:900;color:#1a2744}.bundle-pricing .save{font-size:12px;color:#2f7d55;font-weight:900}.risk-card h3{font-size:15px;margin:0 0 8px;color:#1a2744}.risk-card .desc{font-size:13px;color:#5a6a7a;line-height:1.65}.risk-card .mitigation{margin-top:14px;font-size:12px;padding:12px;background:#eaf5ee;border-left:3px solid #2f7d55;color:#5a6a7a;line-height:1.6}.source-grid,.conclusion-grid,.kano-grid,.row2,.summary-grid,.thumb-wall{display:grid;gap:16px}.source-grid,.row2{grid-template-columns:repeat(2,minmax(0,1fr))}.conclusion-grid,.kano-grid,.insight-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.summary-grid,.thumb-wall{grid-template-columns:repeat(4,minmax(0,1fr))}.source-card{background:#fff;border:1px solid rgba(26,39,68,.12);padding:18px}.source-card h3{font-size:14px;color:#1a2744;margin:0 0 10px}.source-card .quotes{list-style:none;margin:0;padding:0;color:#5a6a7a;font-size:13px;line-height:1.8}.conclusion-item-title{font-weight:900;color:#7ab8e8;margin-bottom:8px}.conclusion-item-text{color:rgba(255,255,255,.72);font-size:13px;line-height:1.7}.pricing-grid,.prompt-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.prompt-card{min-height:260px}.comp-col-asin{width:104px}.ecosystem-kicker{margin:0 0 14px;color:#8a9aaa;font-size:12px;font-weight:900;letter-spacing:1.4px;text-transform:uppercase}.ecosystem-pool-summary{display:flex;align-items:center;gap:14px;justify-content:space-between;margin:0 0 14px;padding:12px 14px;border:1px solid rgba(61,107,158,.2);background:#eef4f8;color:#1a2744}.ecosystem-pool-summary strong{font-size:15px}.ecosystem-pool-summary span{font-size:12px;color:#667085}.ecosystem-chart-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.ecosystem-summary-card{margin-top:16px}.cosmo-tag-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.cosmo-tag-card{border:1px solid rgba(26,39,68,.12);background:#fff;padding:14px;min-height:176px}.cosmo-tag-head{display:flex;justify-content:space-between;gap:12px;margin-bottom:10px}.cosmo-tag-head strong{color:#1a2744}.cosmo-tag-head span{font-size:11px;font-weight:900;color:#3d6b9e}.cosmo-tag-terms{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}.cosmo-tag-terms span{background:#eef4f8;color:#1a2744;padding:4px 7px;font-size:12px;font-weight:800}.cosmo-tag-action{font-size:12px;color:#5a6a7a;line-height:1.55;border-top:1px solid rgba(26,39,68,.1);padding-top:10px}.demand-chart{min-height:360px}.quote-grid,.voc-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}.market-voc-sentiment-columns{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin:18px 0}.market-voc-column{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;align-content:start}.market-voc-column-head{grid-column:1/-1;border:1px solid rgba(26,39,68,.12);background:#fff;padding:14px 16px;color:#1a2744}.market-voc-column.positive .market-voc-column-head{border-top:4px solid #6a9a7a}.market-voc-column.negative .market-voc-column-head{border-top:4px solid #c4705a}.market-voc-column-head span{display:block;color:#3d6b9e;font-size:11px;font-weight:900;letter-spacing:1.2px;text-transform:uppercase}.market-voc-column-head h3{margin:4px 0;color:#1a2744;font-size:18px}.market-voc-column-head p{margin:0;color:#5a6a7a;font-size:12px;line-height:1.6}.market-voc-card{border:1px solid rgba(26,39,68,.12);background:#fff;padding:14px;min-height:228px;display:flex;flex-direction:column;color:#1a2744}.market-voc-card.joy{border-left:4px solid #6a9a7a}.market-voc-card.pain{border-left:4px solid #c4705a}.market-voc-card.diagnostic{background:#fbfaf8}.market-voc-card-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:10px;font-weight:900}.market-voc-card-head span{min-width:28px;color:#3d6b9e}.market-voc-card-head b{font-size:12px;color:#1a2744;text-align:right}.market-voc-title{font-size:13px;font-weight:900;color:#1a2744;margin-bottom:8px;line-height:1.45}.market-voc-card .quote-cn{font-size:13px;line-height:1.55;margin:0 0 8px;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}.market-voc-excerpt{font-size:12px;line-height:1.45;-webkit-line-clamp:3}.market-voc-card .voc-desc{margin-top:auto}.demand-brief-stack{display:grid;gap:10px;margin-bottom:14px}.template-demand.mode-r3 .section-number{display:none}.template-demand.mode-r3 .section-header{display:block}.demand-evidence-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}.demand-sentiment-columns{align-items:start}.demand-sentiment-column{display:grid;gap:12px;align-content:start}.demand-column-head{border:1px solid #e0ddd8;background:#fff;color:#1a2744;padding:14px 16px}.demand-sentiment-column.positive .demand-column-head{border-top:4px solid #6a9a7a}.demand-sentiment-column.negative .demand-column-head{border-top:4px solid #c4705a}.demand-column-head span{display:block;color:#3d6b9e;font-size:11px;font-weight:900;letter-spacing:1.2px;text-transform:uppercase}.demand-column-head h3{margin:4px 0;color:#1a2744;font-size:18px}.demand-column-head p{margin:0;color:#5a6a7a;font-size:12px;line-height:1.6}.quote-cn{font-size:16px;font-weight:900;line-height:1.55}.demand-evidence-card,.sentiment-empty-card{border:1px solid #e0ddd8;background:#fff;color:#1a2744;padding:16px;min-height:236px;display:flex;flex-direction:column}.demand-evidence-card.pain,.sentiment-empty-card.pain{border-left:4px solid #c4705a}.demand-evidence-card.joy,.sentiment-empty-card.joy{border-left:4px solid #6a9a7a}.demand-evidence-card.neutral{border-left:4px solid #4da3ff}.evidence-card-head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:12px;font-weight:900}.evidence-card-head span{font-size:12px;color:#667085}.evidence-card-head b{font-size:13px;color:#1a2744}.review-excerpt-label{margin:0 0 4px;color:#3d6b9e;font-size:12px;font-weight:900}.review-excerpt-en{margin:0 0 12px;color:#6f87a1;font-size:13px;line-height:1.55;display:-webkit-box;-webkit-line-clamp:4;-webkit-box-orient:vertical;overflow:hidden}.review-excerpt-en strong,.quote-cn strong{color:#3d6b9e}.template-demand .demand-evidence-card .quote-cn,.template-demand .sentiment-empty-card .quote-cn{color:#1a2744}.demand-evidence-meta{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:14px 0 0}.demand-evidence-meta div{border-top:1px solid rgba(26,39,68,.12);padding-top:8px}.demand-evidence-meta dt{font-size:11px;color:#667085;font-weight:900}.demand-evidence-meta dd{margin:3px 0 0;color:#1a2744;font-size:13px;line-height:1.45}.template-demand .demand-evidence-card .quote-origin{margin-top:auto;color:#667085}.template-demand .evidence-drawer{background:#fff;border-color:#e0ddd8}.template-demand .evidence-drawer summary{color:#1a2744}.template-demand .evidence-drawer .drawer-body{color:#5a6a7a}.template-demand .mode-r2,.template-demand .mode-r3,.template-demand .mode-r4,.template-demand .mode-r5{border-color:#2b4266}
.cosmo-tag-module{display:grid;gap:16px}.cosmo-layout{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(320px,.65fr);gap:18px;align-items:start}.cosmo-panel{border:1px solid #d9d5cf;background:#fff;padding:18px}.cosmo-panel-title{display:flex;align-items:center;gap:8px;margin:-2px 0 14px;padding-bottom:12px;border-bottom:1px solid #e0ddd8;color:#1a2744;font-size:15px;font-weight:900}.cosmo-panel-title:before{content:"";display:block;width:8px;height:18px;background:#1a2744}.cosmo-matrix{grid-row:span 2}.cosmo-matrix-lanes{display:grid;gap:14px}.cosmo-matrix-lane{border:1px solid #e0ddd8;background:#fff;padding:12px 12px 14px;box-shadow:0 10px 24px rgba(26,39,68,.035)}.cosmo-matrix-lane.product-lane{border-left:4px solid #3d6b9e}.cosmo-matrix-lane.user-lane{border-left:4px solid #6a9a7a}.cosmo-lane-title{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin:0 0 10px;padding-bottom:10px;border-bottom:1px solid #e0ddd8;color:#1a2744}.cosmo-lane-title span{font-size:14px;font-weight:900}.cosmo-lane-title b{margin-left:auto;display:inline-grid;place-items:center;min-width:42px;height:24px;background:#1a2744;color:#fff;font-size:11px}.cosmo-lane-title em{flex:1 1 100%;color:#667085;font-size:11px;font-style:normal;line-height:1.35}.cosmo-lane-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.cosmo-matrix-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.cosmo-matrix-cell{border:1px solid rgba(26,39,68,.12);background:#fbfcfd;padding:12px;min-height:188px;display:grid;grid-template-rows:auto auto auto auto 1fr;align-content:start;gap:7px;overflow:visible;box-shadow:0 8px 18px rgba(26,39,68,.045)}.cosmo-matrix-cell[data-dimension="产品标签"]{border-left:4px solid #3d6b9e}.cosmo-matrix-cell[data-dimension="用户标签"]{border-left:4px solid #6a9a7a}.cosmo-matrix-cell[data-confidence="高"]{border-top:4px solid #6a9a7a}.cosmo-matrix-cell[data-confidence="中"]{border-top:4px solid #c9a05a}.cosmo-matrix-cell[data-confidence="低"]{border-top:4px solid #c4705a;background:#fffaf8}.cosmo-matrix-cell[data-confidence="高"] .cosmo-confidence-pill{background:#eaf5ee;color:#2f7d55;border-color:rgba(47,125,85,.25)}.cosmo-matrix-cell[data-confidence="中"] .cosmo-confidence-pill{background:#fff7e8;color:#9a6a17;border-color:rgba(201,160,90,.32)}.cosmo-matrix-cell[data-confidence="低"] .cosmo-confidence-pill{background:#fff1ed;color:#b42318;border-color:rgba(196,112,90,.32)}.cosmo-card-top{display:flex;justify-content:space-between;gap:8px;align-items:flex-start;margin:0}.cosmo-relation-lane{display:inline-flex;align-items:center;gap:6px;margin-bottom:5px}.cosmo-relation-kind{font-size:10.5px;font-weight:900;color:#3d6b9e;letter-spacing:.4px}.cosmo-relation-id{display:inline-grid;place-items:center;min-width:30px;height:20px;background:#1a2744;color:#fff;font-size:10px;line-height:1}.cosmo-matrix-cell[data-dimension="用户标签"] .cosmo-relation-id{background:#2f7d55}.cosmo-relation-title{margin:4px 0 0;font-size:15px;line-height:1.25;color:#1a2744}.cosmo-confidence-pill{flex:0 0 auto;border:1px solid rgba(26,39,68,.14);padding:2px 6px;font-size:10.5px;font-weight:900;white-space:nowrap}.cosmo-relation-meta{margin:0!important;color:#667085;font-size:11px;line-height:1.35}.cosmo-tag-terms{display:flex;flex-wrap:wrap;gap:5px;margin:0}.cosmo-tag-terms span{padding:3px 6px;background:#eef4f8;color:#1a2744;border:1px solid rgba(61,107,158,.12);font-size:10.5px;font-weight:800;line-height:1.25;max-width:100%;overflow:hidden;text-overflow:ellipsis}.cosmo-evidence-strip{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:0;padding:5px 8px;background:#f7f6f2;border:1px solid #e0ddd8}.cosmo-evidence-strip span{font-size:11px;color:#667085;font-weight:900}.cosmo-evidence-strip b{color:#1a2744;font-size:14px}.cosmo-business-meaning{margin:0!important;padding-top:8px;border-top:1px solid rgba(26,39,68,.1);color:#5a6a7a!important;font-size:11.5px!important;line-height:1.45!important}.cosmo-business-meaning b{color:#1a2744}.cosmo-top-list ol,.cosmo-gap-panel ul{list-style:none;margin:0;padding:0;display:grid;gap:9px}.cosmo-top-list li,.cosmo-gap-panel li{display:grid;grid-template-columns:88px minmax(0,1fr);gap:8px;padding:9px 0;border-bottom:1px solid #e0ddd8}.cosmo-top-list li:last-child,.cosmo-gap-panel li:last-child{border-bottom:0}.cosmo-top-list li span,.cosmo-gap-panel li span{color:#3d6b9e;font-size:11px;font-weight:900}.cosmo-top-list li strong,.cosmo-gap-panel li strong{color:#1a2744;font-size:13px;line-height:1.35}.cosmo-top-list li em,.cosmo-gap-panel li em{grid-column:2;color:#667085;font-size:11px;font-style:normal}.cosmo-gap-panel p{margin:0 0 12px;color:#5a6a7a;font-size:13px;line-height:1.65}.cosmo-action-board{grid-column:1/-1}.cosmo-action-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.cosmo-action-card{border:1px solid rgba(26,39,68,.12);background:#fbfcfd;padding:14px;min-height:190px;border-top:4px solid #3d6b9e}.cosmo-action-card[data-action-kind="用户标签"]{border-top-color:#6a9a7a}.cosmo-action-card span{font-size:11px;color:#3d6b9e;font-weight:900;letter-spacing:.4px}.cosmo-action-card h3{margin:6px 0 10px;color:#1a2744;font-size:14px}.cosmo-action-list{list-style:none;margin:0;padding:0;display:grid;gap:8px}.cosmo-action-list li{display:grid;grid-template-columns:72px minmax(0,1fr);gap:8px;border-top:1px solid rgba(26,39,68,.08);padding-top:8px}.cosmo-action-list li:first-child{border-top:0;padding-top:0}.cosmo-action-list b,.cosmo-action-label{font-size:11px;color:#1a2744}.cosmo-action-list span{font-size:12px!important;color:#5a6a7a!important;font-weight:500!important;letter-spacing:0!important;line-height:1.5}
.diagnostic-chart-container{background:#fbfaf8}.diagnostic-chart-body{height:auto!important;min-height:190px;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;align-content:start}.diagnostic-chart-item{border:1px solid rgba(26,39,68,.12);background:#fff;padding:14px;min-width:0}.diagnostic-chart-item span{display:block;color:#667085;font-size:11px;font-weight:900}.diagnostic-chart-item b{display:block;margin:8px 0 6px;color:#1a2744;font-size:22px;line-height:1}.diagnostic-chart-item em{display:block;color:#5a6a7a;font-size:12px;font-style:normal;line-height:1.5}
@media(max-width:760px){.site-nav{top:12px;right:12px;align-items:flex-start;max-width:calc(100vw - 24px);padding:0}.site-nav-toggle{display:block;border:1px solid rgba(255,255,255,.24);background:rgba(26,39,68,.72);color:#fff;padding:7px 10px;font-weight:800}.site-nav-links{display:none;width:100%;padding-top:8px}.site-nav.is-open{flex-wrap:wrap;background:rgba(26,39,68,.88);padding:10px}.site-nav.is-open .site-nav-links{display:flex;flex-direction:column}.table-tools{justify-content:stretch}.site-nav a{font-size:12px;color:#fff}.template-market .container,.template-lifecycle .container,.template-demand .container,.template-demand .wrap{width:min(100% - 20px,1200px)!important}.template-demand .wrap{padding:20px 0 36px!important}.template-demand .hero{padding:32px 18px!important;margin-bottom:20px!important}.template-market .section,.template-lifecycle .section,.template-demand .section,.template-demand .sec{padding:16px!important;margin:18px 0!important}.template-market #market-dashboard>.kpi-grid,.template-lifecycle #strategy-dashboard>.kpi-grid,.template-demand .hero .header-meta{grid-template-columns:1fr!important}.grid-2,.grid-3,.grid-4,.metric-strip,.chart-grid,.persona-grid,.bundle-grid,.phase-grid,.risk-grid,.source-grid,.conclusion-grid,.kano-grid,.row2,.summary-grid,.insight-grid,.thumb-wall,.supply-grid,.pricing-grid,.visual-grid,.prompt-grid,.deep-dive-grid,.opportunity-matrix,.demand-evidence-grid{grid-template-columns:1fr!important}.mini-chart .bar-row{grid-template-columns:minmax(0,1fr) 64px!important;gap:8px!important}.mini-chart .bar-row>span:first-child{grid-column:1/-1;min-width:0;white-space:normal;overflow-wrap:anywhere}.mini-chart .bar-row>b{justify-self:end}.evidence-table,.insight-table{display:block!important;width:100%!important;max-width:100%!important;overflow-x:auto!important}.evidence-table th,.evidence-table td,.insight-table th,.insight-table td{min-width:96px}.kpi-card,.kpi,.card,.source-card,.strategy-card,.bundle-card,.risk-card,.persona-card,.phase-card,.tl-card,.comp-deep-card,.pain-card,.joy-card,.demand-evidence-card{padding:14px!important;max-width:100%!important}.section-header{gap:10px!important}.section-number{min-width:30px!important}.section-title{font-size:22px!important}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto!important;transition:none!important}}
""".strip()

REPORT_JS = """
(function(){
  const nav=document.querySelector('.site-nav');
  const toggle=document.querySelector('.site-nav-toggle');
  if(toggle&&nav){toggle.addEventListener('click',()=>nav.classList.toggle('is-open'));}
  function applyTableFilters(table){
    const q=(table.dataset.searchQuery||'').trim().toLowerCase();
    const activeFilter=(table.dataset.activeFilter||'all').toLowerCase();
    table.querySelectorAll('tbody tr').forEach(row=>{
      const bucket=[row.dataset.filter,row.dataset.type,row.dataset.supply,row.dataset.phase,row.textContent].filter(Boolean).join(' ').toLowerCase();
      const text=row.textContent.toLowerCase();
      const matchesSearch=!q||text.includes(q);
      const matchesButton=activeFilter==='all'||bucket.includes(activeFilter);
      row.classList.toggle('is-filtered-out',!(matchesSearch&&matchesButton));
    });
  }
  document.querySelectorAll('[data-width]').forEach(el=>{
    const n=Number(el.dataset.width||0);
    el.style.width=`${Math.max(0,Math.min(100,n))}%`;
  });
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
      table.dataset.searchQuery=input.value;
      applyTableFilters(table);
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
      table.dataset.activeFilter=filter;
      applyTableFilters(table);
    }));
  });
  document.querySelectorAll('.mini-chart .bar-row').forEach(row=>{
    row.addEventListener('mouseenter',()=>row.classList.add('is-linked'));
    row.addEventListener('mouseleave',()=>row.classList.remove('is-linked'));
  });
  function shortLabel(value,limit=12){
    const text=String(value||'').trim();
    return text.length>limit?text.slice(0,limit)+'…':text;
  }
  function shortSkuLabel(value){
    const text=String(value||'').replace(/\\s+/g,' ').trim();
    const cleaned=text
      .replace(/目标赛道[:：]?/g,' ')
      .replace(/参考竞品[:：]?/g,' ')
      .replace(/供应链风险[:：]?/g,' ')
      .replace(/1688成品供应验证[:：]?/g,' ')
      .replace(/\\s+/g,' ')
      .trim();
    const match=cleaned.match(/([^，。；;:：]{2,18}(基础款|升级款|套装款|配件款|维护复购款|复购款))/);
    if(match)return match[1];
    return shortLabel(cleaned,12);
  }
  function datasetRows(section,name){
    const source=section.querySelector(`[data-chart-source="${name}"]`);
    if(!source)return [];
    return [...source.querySelectorAll('[data-label]')].map((el,idx)=>{
      const value=parseFloat(el.dataset.value||'');
      return {label:el.dataset.label||('数据指标 '+(idx+1)),value:Number.isFinite(value)?value:idx+1};
    });
  }
  function sectionRows(el){
    const section=el.closest('section,.section')||document;
    const rows=[...section.querySelectorAll('tbody tr')].slice(0,10).map((row,idx)=>{
      const cells=[...row.cells].map(cell=>cell.textContent.trim()).filter(Boolean);
      const label=cells[0]||('数据指标 '+(idx+1));
      const numeric=cells.map(text=>parseFloat(text.replace(/[^0-9.-]/g,''))).find(Number.isFinite);
      return {label,value:Number.isFinite(numeric)?numeric:idx+1};
    });
    if(rows.length)return rows;
    return [...section.querySelectorAll('.bar-row')].slice(0,10).map((row,idx)=>{
      const label=row.querySelector('span')?.textContent.trim()||('数据指标 '+(idx+1));
      const numeric=parseFloat(row.querySelector('b')?.textContent.replace(/[^0-9.-]/g,'')||'');
      return {label,value:Number.isFinite(numeric)?numeric:idx+1};
    });
  }
  const morandiColors=['#7a9bb5','#8fa89a','#c4a09a','#c9b99a','#9a8fb5','#8aab8a','#b5a07a','#a09ab5'];
  const primaryColor='#1a2744';
  const accentColor='#3d6b9e';
  const dangerColor='#c4705a';
  const successColor='#6a9a7a';
  const warningColor='#c9a05a';
  const lavenderColor='#9a8fb5';
  const titleStyle={fontSize:14,fontWeight:700,color:primaryColor,textBorderWidth:0,textShadowBlur:0,textShadowColor:'transparent'};
  const axisLabelStyle={fontSize:11,color:'#8a9aaa'};
  const hasChart=id=>typeof document.getElementById==='function'&&!!document.getElementById(id);
  function setupEchartsRenderer(){
    if(typeof window==='undefined'||!window.echarts||echarts.__amzTemplateRendererPatched)return;
    const isIOSWebKit=/iP(ad|hone|od)/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
    const originalInit=echarts.init.bind(echarts);
    echarts.init=(dom,theme,opts)=>{
      const chart=originalInit(dom,theme,{...(opts||{}),renderer:isIOSWebKit?'svg':(opts&&opts.renderer)||'canvas',useDirtyRect:!isIOSWebKit});
      const originalSetOption=chart.setOption.bind(chart);
      chart.setOption=(option,...args)=>originalSetOption({animation:!isIOSWebKit,animationDuration:isIOSWebKit?0:300,animationDurationUpdate:isIOSWebKit?0:300,...option},...args);
      return chart;
    };
    echarts.__amzTemplateRendererPatched=true;
  }
  function chart(id,option){
    if(!window.echarts)return null;
    if(typeof document.getElementById!=='function')return null;
    const el=document.getElementById(id);
    if(!el)return null;
    const instance=echarts.init(el);
    instance.setOption(option);
    window.addEventListener('resize',()=>instance.resize());
    return instance;
  }
  function normalizeRows(rows,minCount=4){
    const base=rows.filter(row=>row.label&&Number.isFinite(row.value));
    return base.slice(0,12);
  }
  function tableRows(id){
    const table=document.getElementById(id);
    if(!table)return [];
    return [...table.querySelectorAll('tbody tr')].map((row,idx)=>{
      const cells=[...row.cells].map(cell=>cell.textContent.trim());
      const score=parseFloat(row.dataset.score||'');
      const value=Number.isFinite(score)?score:cells.map(text=>parseFloat(text.replace(/[^0-9.-]/g,''))).find(Number.isFinite);
      const label=cells[3]||cells[1]||cells[0]||('拓品方案 '+(idx+1));
      const rowType=(row.dataset.type||row.getAttribute('data-filter')||cells[2]||'core_validation').trim();
      return {
        label,
        shortSku:shortSkuLabel(label),
        type:rowType,
        ecosystemPath:row.dataset.ecosystemPath||cells[2]||'拓品路径',
        segment:row.dataset.segment||cells[1]||'赛道归类',
        phase:cells[0]||'-',
        value:Number.isFinite(value)?value:idx+1
      };
    });
  }
  function marketCharts(){
    if(!hasChart('priceChart'))return;
    const marketSection=document.getElementById('priceChart').closest('section,.section')||document;
    const marketRows=normalizeRows(datasetRows(marketSection,'marketRows').length?datasetRows(marketSection,'marketRows'):sectionRows(document.getElementById('priceChart')),6);
    const labels=marketRows.map(row=>shortLabel(row.label,10));
    const values=marketRows.map(row=>row.value);
    chart('priceChart',{tooltip:{trigger:'axis',axisPointer:{type:'shadow'}},grid:{left:'3%',right:'4%',bottom:'3%',containLabel:true},xAxis:{type:'category',data:labels,axisLabel:axisLabelStyle,axisLine:{lineStyle:{color:'#e0ddd8'}}},yAxis:{type:'value',name:'月销量估算',nameTextStyle:axisLabelStyle,axisLabel:axisLabelStyle,splitLine:{lineStyle:{color:'#f0ede8'}}},series:[{name:'月销量估算',type:'bar',barMaxWidth:48,data:values.map((value,idx)=>({value,itemStyle:{color:idx===1?dangerColor:morandiColors[idx%morandiColors.length]}})),label:{show:true,position:'top',fontSize:10,color:'#5a6a7a'}}]});
    chart('bubbleChart',{tooltip:{confine:true,formatter:p=>`${p.data[4]}<br>竞品数量: ${p.data[1]}<br>月销量估算: ${p.data[2]}`},grid:{left:'10%',right:'16%',bottom:'12%',top:'10%',containLabel:true},xAxis:{type:'value',name:'价格带排序',nameLocation:'middle',nameGap:30,min:0,max:marketRows.length*20+35,axisLabel:{...axisLabelStyle,formatter:'${value}'},splitLine:{lineStyle:{color:'#f0ede8'}}},yAxis:{type:'value',name:'竞品数量',nameLocation:'middle',nameGap:42,axisLabel:axisLabelStyle,splitLine:{lineStyle:{color:'#f0ede8'}}},series:[{type:'scatter',symbolSize:data=>Math.max(22,Math.min(86,Math.sqrt(Math.max(data[2],1))*2.1)),data:marketRows.map((row,idx)=>[idx*20+20,idx+8,row.value,shortLabel(row.label,8),row.label]),itemStyle:{color:p=>p.data[2]===Math.max(...values)?dangerColor:accentColor,opacity:.8},label:{show:true,formatter:p=>p.data[3],fontSize:10,color:'#1a2744',position:'inside'}}]});
    chart('growthChart',{tooltip:{trigger:'axis'},grid:{left:'3%',right:'4%',bottom:'3%',containLabel:true},xAxis:{type:'category',data:labels,axisLabel:axisLabelStyle,axisLine:{lineStyle:{color:'#e0ddd8'}}},yAxis:{type:'value',name:'趋势值',axisLabel:axisLabelStyle,splitLine:{lineStyle:{color:'#f0ede8'}}},series:[{name:'市场规模',type:'line',smooth:true,data:values,lineStyle:{color:accentColor,width:2.5},itemStyle:{color:accentColor},areaStyle:{color:{type:'linear',x:0,y:0,x2:0,y2:1,colorStops:[{offset:0,color:'rgba(61,107,158,0.25)'},{offset:1,color:'rgba(61,107,158,0.02)'}]}},label:{show:true,fontSize:10,color:'#5a6a7a'}}]});
    const featureRows=normalizeRows(datasetRows(marketSection,'featureRows').length?datasetRows(marketSection,'featureRows'):sectionRows(document.getElementById('featureChart')),7).slice(0,8);
    chart('featureChart',{tooltip:{trigger:'axis',axisPointer:{type:'shadow'}},grid:{left:'3%',right:'15%',bottom:'3%',containLabel:true},xAxis:{type:'value',max:100,axisLabel:{formatter:'{value}%',...axisLabelStyle},splitLine:{lineStyle:{color:'#f0ede8'}}},yAxis:{type:'category',data:featureRows.map(row=>shortLabel(row.label,9)),axisLabel:{fontSize:11,color:'#5a6a7a'}},series:[{name:'竞品覆盖率',type:'bar',data:featureRows.map(row=>Math.min(95,Math.max(5,row.value))),itemStyle:{color:'#c4a09a'},barMaxWidth:20,label:{show:true,position:'right',fontSize:10,color:dangerColor,formatter:'{c}%'}},{name:'我们的目标',type:'bar',data:featureRows.map(row=>Math.min(98,Math.max(65,row.value+20))),itemStyle:{color:accentColor},barMaxWidth:20,label:{show:true,position:'right',fontSize:10,color:accentColor,formatter:'{c}%'}}],legend:{data:['竞品覆盖率','我们的目标'],top:0,right:0,textStyle:{fontSize:11}}});
    const radarSection=document.getElementById('radarChart').closest('section,.section')||document;
    const radarPainRows=normalizeRows(datasetRows(radarSection,'radarPainRows').length?datasetRows(radarSection,'radarPainRows'):sectionRows(document.getElementById('radarChart')),8).slice(0,10);
    const radarJoyRows=normalizeRows(datasetRows(radarSection,'radarJoyRows').length?datasetRows(radarSection,'radarJoyRows'):radarPainRows.map(row=>({label:row.label,value:Math.max(8,100-Math.min(90,row.value))})),8).slice(0,10);
    chart('radarChart',{tooltip:{},legend:{data:['低星痛点强度','正向爽点强度'],bottom:0,textStyle:{fontSize:12}},radar:{indicator:radarPainRows.map(row=>({name:row.label,max:100})),center:['50%','50%'],radius:'65%',axisName:{color:'#5a6a7a',fontSize:11},splitLine:{lineStyle:{color:'#e8e5e0'}},splitArea:{areaStyle:{color:['rgba(244,242,239,0.5)','rgba(244,242,239,0.2)']}}},series:[{type:'radar',data:[{value:radarPainRows.map(row=>Math.min(100,Math.max(0,row.value))),name:'低星痛点强度',lineStyle:{color:dangerColor,width:2},itemStyle:{color:dangerColor},areaStyle:{color:'rgba(196,112,90,0.15)'}},{value:radarJoyRows.map(row=>Math.min(100,Math.max(0,row.value))),name:'正向爽点强度',lineStyle:{color:successColor,width:2},itemStyle:{color:successColor},areaStyle:{color:'rgba(106,154,122,0.15)'}}]}]});
    const marginEl=document.getElementById('marginChart');
    if(marginEl&&marginEl.dataset.chartDisabled==='true')return;
    const marginSection=marginEl.closest('section,.section')||document;
    const marginRows=normalizeRows(datasetRows(marginSection,'marginChartRows').length?datasetRows(marginSection,'marginChartRows'):sectionRows(document.getElementById('marginChart')),3).slice(0,4);
    chart('marginChart',{tooltip:{trigger:'axis',axisPointer:{type:'shadow'}},legend:{data:['出厂成本','FBA+物流费','目标毛利率'],bottom:0,textStyle:{fontSize:11}},grid:{left:'3%',right:'4%',bottom:'12%',containLabel:true},xAxis:{type:'category',data:marginRows.map(row=>row.label),axisLabel:{fontSize:12,color:'#5a6a7a'},axisLine:{lineStyle:{color:'#e0ddd8'}}},yAxis:{type:'value',name:'美元 / 毛利率%',axisLabel:axisLabelStyle,splitLine:{lineStyle:{color:'#f0ede8'}}},series:[{name:'出厂成本',type:'bar',stack:'cost',data:marginRows.map(row=>Math.max(5,Math.round(row.value*.35))),itemStyle:{color:'#c4a09a'},barMaxWidth:60},{name:'FBA+物流费',type:'bar',stack:'cost',data:marginRows.map(row=>Math.max(5,Math.round(row.value*.22))),itemStyle:{color:'#c9b99a'},barMaxWidth:60},{name:'目标毛利率',type:'line',data:marginRows.map(row=>Math.min(75,Math.max(25,Math.round(row.value)))),itemStyle:{color:successColor},lineStyle:{color:successColor,width:3}}]});
  }
  function lifecycleCharts(){
    if(!hasChart('sunburst'))return;
    const skuRows=tableRows('skuTable');
    const typeColors={core_validation:dangerColor,scenario_upgrade:accentColor,accessory_gap:successColor,maintenance_repurchase:lavenderColor};
    const pathColors=[dangerColor,accentColor,successColor,lavenderColor,warningColor];
    const pathMap=new Map();
    skuRows.forEach(row=>{
      const path=row.ecosystemPath||'拓品路径';
      const segment=row.segment||'赛道归类';
      if(!pathMap.has(path))pathMap.set(path,new Map());
      const segmentMap=pathMap.get(path);
      if(!segmentMap.has(segment))segmentMap.set(segment,[]);
      segmentMap.get(segment).push(row);
    });
    const rootName=(document.querySelector('.report-header h1')?.textContent||'当前研究对象').replace(/\\s+/g,' ').trim();
    const sunburstData=[...pathMap.entries()].map(([path,segmentMap],pathIdx)=>{
      const pathRows=[...segmentMap.values()].flat();
      return {
        name:shortLabel(path,14),
        value:pathRows.length,
        itemStyle:{color:pathColors[pathIdx%pathColors.length]},
        children:[...segmentMap.entries()].map(([segment,rows])=>({
          name:shortLabel(segment,14),
          value:rows.length,
          children:rows.slice(0,8).map(row=>({name:shortSkuLabel(row.label),value:1,itemStyle:{color:typeColors[row.type]||pathColors[pathIdx%pathColors.length]}}))
        }))
      };
    });
    chart('sunburst',{tooltip:{trigger:'item',formatter:p=>`${p.name}<br/>SKU：${p.value}`},nodeClick:false,series:[{name:shortLabel(rootName,16),type:'sunburst',data:sunburstData,radius:[0,'86%'],sort:null,label:{show:false},levels:[{}, {r0:'0%',r:'22%',label:{show:true,rotate:0,fontSize:12,color:'#fff',overflow:'truncate'},itemStyle:{borderWidth:3,borderColor:'#fff'}}, {r0:'22%',r:'58%',label:{show:true,rotate:'tangential',fontSize:11,color:primaryColor,overflow:'truncate'},itemStyle:{borderWidth:2,borderColor:'#fff'}}, {r0:'58%',r:'86%',label:{show:false},itemStyle:{borderWidth:1,borderColor:'#fff'}}]}]});
    const sortedAll=skuRows.slice().sort((a,b)=>b.value-a.value);
    const sorted=sortedAll.slice(0,skuRows.length>20?15:20).reverse();
    const maxScore=Math.max(10,...sorted.map(row=>Math.min(100,Math.max(1,row.value))));
    const axisMax=skuRows.length<=8?Math.ceil(maxScore/5)*5:100;
    const chartTitle=skuRows.length<=8?'SKU 紧凑评分卡':(skuRows.length>20?'Top 15 SKU 优先级':'SKU 优先级全量榜');
    chart('priorityChart',{title:{text:chartTitle,left:8,top:0,textStyle:{fontSize:12,color:'#5a6a7a',fontWeight:700}},tooltip:{trigger:'axis',axisPointer:{type:'shadow'},formatter:items=>{const item=Array.isArray(items)?items[0]:items;const row=sorted[item.dataIndex]||{};return `${row.shortSku||row.label}<br/>优先级：${item.value}<br/>路径：${row.ecosystemPath||'-'}<br/>赛道：${row.segment||'-'}`;}},grid:{left:190,right:56,bottom:26,top:34,containLabel:false},xAxis:{type:'value',max:axisMax,axisLabel:{fontSize:10,color:'#8a9aaa'},splitLine:{lineStyle:{color:'#f0ede8'}}},yAxis:{type:'category',data:sorted.map(row=>shortSkuLabel(row.label)),axisLabel:{fontSize:11,color:'#5a6a7a',width:170,overflow:'truncate'}},series:[{type:'bar',data:sorted.map(row=>({value:Math.min(100,Math.max(1,row.value)),itemStyle:{color:typeColors[row.type]||accentColor}})),barMaxWidth:skuRows.length<=8?22:16,label:{show:true,position:'right',fontSize:10,color:'#5a6a7a'}}]});
    const bundleRows=normalizeRows(sectionRows(document.getElementById('aovChart')),4).slice(0,6);
    chart('aovChart',{tooltip:{trigger:'axis'},legend:{data:['单买主体','Bundle 价格','AOV 提升'],textStyle:{color:'#5a6a7a',fontSize:11},top:0},grid:{left:60,right:40,top:40,bottom:40},xAxis:{type:'category',data:bundleRows.map(row=>row.label),axisLabel:{color:'#5a6a7a',fontSize:12},axisLine:{lineStyle:{color:'#e0ddd8'}}},yAxis:{type:'value',name:'USD',axisLabel:{color:'#8a9aaa'},splitLine:{lineStyle:{color:'#f0ede8'}}},series:[{name:'单买主体',type:'bar',data:bundleRows.map(()=>60),itemStyle:{color:'#d0cdc8'},barWidth:36},{name:'Bundle 价格',type:'bar',data:bundleRows.map(row=>Math.max(20,row.value)),itemStyle:{color:accentColor},barWidth:36},{name:'AOV 提升',type:'line',data:bundleRows.map(row=>Math.max(5,row.value-60)),itemStyle:{color:successColor},lineStyle:{color:successColor,width:3},symbol:'circle',symbolSize:10,label:{show:true,fontSize:10,color:successColor}}]});
  }
  function demandCharts(){
    if(!hasChart('appealsRose'))return;
    const appealsSection=document.getElementById('appealsRose').closest('section,.section,.sec')||document;
    const appealRows=normalizeRows(datasetRows(appealsSection,'appealsRows').length?datasetRows(appealsSection,'appealsRows'):sectionRows(document.getElementById('appealsRose')),5).slice(0,8);
    const nodeMap=new Map([['需求主题',{name:'需求主题'}]]);
    const links=[];
    const addNode=name=>{if(!nodeMap.has(name))nodeMap.set(name,{name});};
    appealRows.forEach((row,idx)=>{
      const dim=row.label.length>10?row.label.slice(0,10):row.label;
      const action=idx<3?'优先修复':'页面转化';
      addNode(dim);
      addNode(action);
      links.push({source:'需求主题',target:dim,value:Math.max(1,row.value),raw:row.value},{source:dim,target:action,value:Math.max(1,Math.round(row.value*.7)),raw:row.value});
    });
    chart('appealsRose',{textStyle:{color:primaryColor},title:{text:'市场痛点全景图（需求主题）',left:'center',top:6,textStyle:titleStyle},tooltip:{trigger:'item',triggerOn:'mousemove',backgroundColor:'#fff',borderColor:'#e0e0e0',borderWidth:1,textStyle:{color:primaryColor,fontSize:13},formatter:p=>p.dataType==='edge'?`${p.data.source} → ${p.data.target}<br/>评论记录：${p.data.raw||p.value}`:`${p.name}<br/>评论记录：${p.data.raw||p.value||0}`},series:[{type:'sankey',layout:'none',nodeAlign:'left',emphasis:{focus:'adjacency'},levels:[{depth:0,itemStyle:{color:accentColor}},{depth:1,itemStyle:{color:dangerColor}},{depth:2,itemStyle:{color:successColor}}],lineStyle:{color:'gradient',curveness:.52,opacity:.34},label:{color:primaryColor,fontSize:12,width:230,overflow:'truncate'},edgeLabel:{show:false},data:[...nodeMap.values()],links}]});
    const gapSection=document.getElementById('gapRadar').closest('section,.section,.sec')||document;
    const gapRows=normalizeRows(datasetRows(gapSection,'gapRows').length?datasetRows(gapSection,'gapRows'):sectionRows(document.getElementById('gapRadar')),5).slice(0,6);
    chart('gapRadar',{textStyle:{color:primaryColor},title:{text:'满意度鸿沟雷达（Gap Analysis）',left:'center',top:6,textStyle:titleStyle},tooltip:{trigger:'item',confine:true,backgroundColor:'#fff',borderColor:'#e0e0e0',borderWidth:1,textStyle:{color:primaryColor,fontSize:13}},legend:{data:['用户期望','竞品实测'],bottom:2,textStyle:{...axisLabelStyle,color:primaryColor}},radar:{indicator:gapRows.map(row=>({name:row.label,max:100})),center:['50%','52%'],radius:'62%',nameFormatter:value=>value.length>4?`${value.slice(0,2)}\n${value.slice(2)}`:value,splitArea:{areaStyle:{color:['rgba(61,107,158,0.08)','rgba(61,107,158,0.03)']}},axisName:{color:primaryColor,fontSize:12},splitLine:{lineStyle:{color:'#d7dce5'}},axisLine:{lineStyle:{color:'#d7dce5'}}},series:[{type:'radar',data:[{name:'用户期望',value:gapRows.map(row=>Math.min(100,Math.max(50,row.value+35))),areaStyle:{color:'rgba(196,112,90,0.16)'},lineStyle:{color:dangerColor,width:2},itemStyle:{color:dangerColor}},{name:'竞品实测',value:gapRows.map(row=>Math.max(10,Math.min(90,row.value))),areaStyle:{color:'rgba(61,107,158,0.16)'},lineStyle:{color:accentColor,width:2},itemStyle:{color:accentColor}}]}]});
  }
  setupEchartsRenderer();
  marketCharts();
  lifecycleCharts();
  demandCharts();
})();
""".strip()

REPORT_POST_REFERENCE_CSS = """
body.template-demand .wrap{max-width:1360px;width:min(1360px,calc(100% - 48px));margin:0 auto;padding:24px}
body.template-market .report-header,body.template-lifecycle .report-header{max-width:100%;overflow:hidden}
body.template-market .report-header::before,body.template-market .report-header::after,body.template-lifecycle .report-header::before,body.template-lifecycle .report-header::after{display:none!important}
body.template-market .mini-chart,body.template-lifecycle .mini-chart{overflow:hidden}
body.template-market .mini-chart .bar-row,body.template-lifecycle .mini-chart .bar-row{grid-template-columns:minmax(0,1.2fr) minmax(72px,1.8fr) 42px;gap:8px}
body.template-market .mini-chart .bar-row>span:first-child,body.template-lifecycle .mini-chart .bar-row>span:first-child{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
body.template-lifecycle .sku-strategy-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px;margin-bottom:22px}
body.template-lifecycle .sku-strategy-card{border:1px solid rgba(26,39,68,.14);background:#fff;padding:0;min-width:0;border-top:4px solid #3d6b9e;min-height:252px;display:flex;flex-direction:column;overflow:hidden}
body.template-lifecycle .sku-strategy-head{display:flex;justify-content:space-between;gap:12px;align-items:center;color:#667085;font-size:12px;font-weight:900;padding:14px 16px;background:#f8fafc;border-bottom:1px solid rgba(26,39,68,.1)}
body.template-lifecycle .sku-strategy-head b{display:inline-grid;place-items:center;min-width:38px;height:38px;background:#1a2744;color:#fff}
body.template-lifecycle .sku-strategy-card h3{margin:16px 18px 14px;color:#1a2744;font-size:20px;line-height:1.25}
body.template-lifecycle .sku-strategy-meta{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0;margin:0 18px;border-top:1px solid rgba(26,39,68,.1);border-left:1px solid rgba(26,39,68,.08)}
body.template-lifecycle .sku-strategy-meta div{border-right:1px solid rgba(26,39,68,.08);border-bottom:1px solid rgba(26,39,68,.08);padding:10px 12px;min-height:70px}
body.template-lifecycle .sku-strategy-meta dt{font-size:11px;color:#667085;font-weight:900}
body.template-lifecycle .sku-strategy-meta dd{margin:4px 0 0;color:#1a2744;font-size:13px;line-height:1.45}
body.template-lifecycle .sku-strategy-card p{margin:auto 18px 18px;color:#5a6a7a;font-size:13px;line-height:1.65}
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
    echarts_src = f"{asset_prefix}assets/echarts.min.js"
    js_src = f"{asset_prefix}assets/report.js"
    html_doc = re.sub(
        r"<script\s+src=\"https://cdn\.jsdelivr\.net/npm/echarts[^\"']*\"[^>]*></script>",
        f"<script src=\"{echarts_src}\" defer></script>",
        html_doc,
        flags=re.I,
    )
    is_child_template = re.search(r"<html\b[^>]*data-report-style=\"(?:market-depth-report-v2|lifecycle-strategy-report-v2|demand-gap-report-v2)\"", html_doc, flags=re.I) is not None or re.search(r"<body\b[^>]*class=\"[^\"]*\btemplate-(market|lifecycle|demand)\b", html_doc, flags=re.I) is not None
    if "assets/report.css" not in html_doc:
        css_link = f"<link rel=\"stylesheet\" href=\"{css_href}\">\n"
        if "<style" in html_doc.lower():
            html_doc = re.sub(r"<style\b", css_link + "<style", html_doc, count=1, flags=re.I)
        else:
            html_doc = html_doc.replace("</head>", css_link + "</head>")
    if is_child_template:
        html_doc = re.sub(r"\s*<style\b[^>]*>.*?</style>\s*", "\n", html_doc, flags=re.S | re.I)
    if "site-nav" not in html_doc:
        html_doc = re.sub(r"<body\b([^>]*)>", lambda match: f"<body{match.group(1)}>\n{site_nav_html(asset_prefix)}", html_doc, count=1, flags=re.I)
    if "assets/echarts.min.js" not in html_doc:
        html_doc = html_doc.replace("</body>", f"<script src=\"{echarts_src}\" defer></script>\n</body>")
    if "assets/report.js" not in html_doc:
        html_doc = html_doc.replace("</body>", f"<script src=\"{js_src}\" defer></script>\n</body>")
    return html_doc


def write_basic_site_assets(report_dir: Path, report_data: dict[str, Any] | None = None) -> None:
    asset_dir = report_dir / ASSET_DIR
    asset_dir.mkdir(parents=True, exist_ok=True)
    (asset_dir / "report.css").write_text(REPORT_CSS + "\n\n" + reference_css_bundle() + "\n\n" + REPORT_POST_REFERENCE_CSS + "\n", encoding="utf-8")
    (asset_dir / "report.js").write_text(REPORT_JS + "\n", encoding="utf-8")
    canonical_echarts = SCRIPT_DIR.parent / "assets" / "canonical_templates" / "echarts.min.js"
    if canonical_echarts.exists():
        shutil.copyfile(canonical_echarts, asset_dir / "echarts.min.js")
    if report_data is not None:
        (asset_dir / "report-data.json").write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8")
