#!/usr/bin/env python3
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import validate_market_research_deliverables as validator
from delivery_writer import child_skill_invocations


SCRIPT = Path(__file__).with_name("validate_market_research_deliverables.py")
SKILL_DIR = Path(__file__).resolve().parent.parent
ENTITY_LIST_KEYS = [
    "products",
    "keywords",
    "categories",
    "reviews",
    "tiktok_products",
    "tiktok_videos",
    "suppliers",
    "web_documents",
]


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def file_sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def supplier_rows(count=50):
    return [
        {
            "title": f"智能玩具工厂货源 {idx}",
            "supplier_name": f"供应商 {idx}",
            "url": f"https://detail.1688.com/offer/{idx}.html",
            "price_rmb": 12 + idx,
            "sales_30d": 100 + idx,
            "source_id": "src_001",
            "provider": "sorftime",
        }
        for idx in range(count)
    ]


def competitor_rows(count=30):
    segments = ["智能陪伴玩具", "语音互动玩具", "儿童礼品玩具"]
    return [
        {
            "asin": f"B0V{idx:07d}",
            "title": f"Interactive AI Plush Toy Competitor {idx}",
            "title_cn": f"ToyBrand {idx % 8} 智能陪伴玩具",
            "brand": f"ToyBrand {idx % 8}",
            "segment_cn": segments[idx % len(segments)],
            "price": 39 + idx,
            "rating": 4.1 + (idx % 6) / 10,
            "review_count": 500 + idx,
            "estimated_monthly_sales": 1200 + idx,
            "source_id": "src_001",
            "provider": "sorftime",
        }
        for idx in range(count)
    ]


def invocation_entry(root, module, renderer, output=None, outputs=None, dispatch_mode="subprocess_child_renderer"):
    entry = {
        "module": module,
        "renderer": renderer,
        "renderer_sha256": file_sha256(SKILL_DIR / renderer),
        "dispatch_mode": dispatch_mode,
        "command": ["python", renderer, "--dir", str(root)],
        "cwd": str(root.parent),
        "started_at": "2026-05-26T10:00:00Z",
        "finished_at": "2026-05-26T10:00:01Z",
        "returncode": 0,
        "stdout": output or "",
        "stderr": "",
    }
    if output:
        entry["output"] = output
        entry["output_sha256"] = file_sha256(root / output)
    if outputs:
        entry["outputs"] = outputs
        entry["output_sha256"] = {item: file_sha256(root / item) for item in outputs}
    return entry


def refresh_child_output_sha(root, output):
    log_path = root / "analysis" / "child_skill_invocation_log.json"
    log = json.loads(log_path.read_text(encoding="utf-8"))
    for entry in log:
        if entry.get("output") == output:
            entry["output_sha256"] = file_sha256(root / output)
    write_json(log_path, log)


def child_html(style, title, sections, extra_terms=""):
    body_class = {
        "market-depth-report-v2": "",
        "lifecycle-strategy-report-v2": "template-lifecycle",
        "demand-gap-report-v2": "template-demand mode-r3",
    }[style]
    body_attr = f' class="{body_class}"' if body_class else ""
    market_scaffold = ""
    lifecycle_scaffold = ""
    demand_scaffold = ""
    if style == "market-depth-report-v2":
        cosmo_product_cards = "".join(
            f'<article class="cosmo-tag-card cosmo-matrix-cell" data-cosmo-relation="{"P" if idx < 8 else "U"}{(idx + 1) if idx < 8 else (idx - 7):02d}" data-confidence="高" data-dimension="{"产品标签" if idx < 8 else "用户标签"}"><div class="cosmo-relation-lane"><span class="cosmo-relation-kind">{"产品意图" if idx < 8 else "用户意图"}</span><b class="cosmo-relation-id">{"产品" if idx < 8 else "用户"}</b></div><h3>标签</h3><p>{"产品标签" if idx < 8 else "用户标签"} · 已覆盖 · 证据 3</p><div class="cosmo-tag-terms"><span>有效标签</span></div></article>'
            for idx in range(8)
        )
        cosmo_user_cards = "".join(
            f'<article class="cosmo-tag-card cosmo-matrix-cell" data-cosmo-relation="U{idx - 7:02d}" data-confidence="高" data-dimension="用户标签"><div class="cosmo-relation-lane"><span class="cosmo-relation-kind">用户意图</span><b class="cosmo-relation-id">用户</b></div><h3>标签</h3><p>用户标签 · 已覆盖 · 证据 3</p><div class="cosmo-tag-terms"><span>有效标签</span></div></article>'
            for idx in range(8, 15)
        )
        market_scaffold = """
<div class="fixed-template-copy">Strategic Intelligence Report Core Product Concept 新品狙击企划 · Product Definition 建议定价策略 视觉与包装指导 · Visual Direction AI生图 Prompt · 可直接使用 供应链成本估算 · 1688大盘数据 供应链核心结论</div>
<div class="container header-badge subtitle header-meta header-meta-item label value section-title section-desc kpi-label kpi-value kpi-sub kpi-trend up hot success warning lavender card chart-grid chart-title chart-subtitle chart-body product-name product-brand price-tag rating-stars badge voc-card-title voc-item voc-content conclusion-title conclusion-grid conclusion-item conclusion-item-title conclusion-item-text"></div>
<div id="priceChart"></div><div id="bubbleChart"></div><div id="growthChart"></div><div id="featureChart"></div><div id="radarChart"></div><div id="marginChart"></div>
<div class="cosmo-layout"><section class="cosmo-panel cosmo-matrix"><div class="cosmo-panel-title">15 标签矩阵</div><div class="cosmo-matrix-lanes"><div class="cosmo-matrix-lane product-lane"><div class="cosmo-lane-title"><span>产品标签 · 产品被算法识别为什么</span><b>8 类</b></div><div class="cosmo-lane-grid">""" + cosmo_product_cards + """</div></div><div class="cosmo-matrix-lane user-lane"><div class="cosmo-lane-title"><span>用户标签 · 用户为什么搜索/购买</span><b>7 类</b></div><div class="cosmo-lane-grid">""" + cosmo_user_cards + """</div></div></div></section><section class="cosmo-panel cosmo-top-list"><div class="cosmo-panel-title">高置信标签排行</div><ol><li><span>功能·用途</span><strong>有效标签</strong><em>高 · 3 条证据</em></li></ol></section><section class="cosmo-panel cosmo-gap-panel"><div class="cosmo-panel-title">产品标签 / 用户标签缺口</div><p>缺口说明</p><ul><li><span>OK</span><strong>已覆盖</strong><em>继续验证</em></li></ul></section><section class="cosmo-panel cosmo-action-board"><div class="cosmo-panel-title">Listing / QA / 广告动作</div><div class="cosmo-action-grid"><article class="cosmo-action-card"><span>产品意图</span><h3>动作</h3><p>Listing：动作</p></article></div></section></div>
<div class="card comp-image-strip-card"><div class="card-title">竞品图片诊断</div><p>图片维度未返回可展示 URL；已保留图片槽位，采集层返回真实图片字段后自动展示。</p></div>
<table class="comp-table"><tr><th>ASIN</th><th>产品</th></tr><tr><td><span class="asin-token" data-allow-asin="competitor-table">B0TEST1234</span></td><td>数据</td></tr></table>
<div class="market-voc-sentiment-columns"><section class="market-voc-column positive"><div class="market-voc-column-head"><span>Positive Reviews</span><h3>正面好评</h3></div><article class="market-voc-card joy">J1</article><article class="market-voc-card joy">J2</article><article class="market-voc-card joy">J3</article><article class="market-voc-card joy">J4</article><article class="market-voc-card joy">J5</article><article class="market-voc-card joy">J6</article></section><section class="market-voc-column negative"><div class="market-voc-column-head"><span>Negative Reviews</span><h3>负面差评</h3></div><article class="market-voc-card pain">P1</article><article class="market-voc-card pain">P2</article><article class="market-voc-card pain">P3</article><article class="market-voc-card pain">P4</article><article class="market-voc-card pain">P5</article><article class="market-voc-card pain">P6</article></section></div>
<div class="voc-grid"><article class="pain-card"><div class="voc-rank pain-rank">P1</div><div class="voc-title">痛点</div><div class="voc-desc">描述</div><div class="voc-quote">摘要</div><div class="voc-bar"><div class="voc-bar-fill pain-fill"></div></div></article><article class="joy-card"><div class="voc-rank joy-rank">J1</div><div class="voc-title">爽点</div><div class="voc-desc">描述</div><div class="voc-quote">摘要</div><div class="voc-bar"><div class="voc-bar-fill joy-fill"></div></div></article></div>
<div class="comp-deep-grid"><div class="comp-deep-card"><div class="comp-deep-header"><div class="comp-deep-name"><span class="asin-token" data-allow-asin="benchmark-sniper">B0ABCDEF12</span> 标杆</div><div class="comp-deep-price">$89</div></div><div class="comp-deep-body"><div class="comp-deep-section"><div class="comp-deep-section-title">逻辑</div><div class="comp-deep-text">文本</div><div class="comp-tag-list"><span class="comp-tag red">痛点</span><span class="comp-tag green">机会</span></div></div></div></div><div class="comp-deep-card"><div class="comp-deep-header"><div class="comp-deep-name">标杆二</div><div class="comp-deep-price">$99</div></div><div class="comp-deep-body"><div class="comp-deep-section"><div class="comp-deep-section-title">逻辑</div><div class="comp-deep-text">文本</div></div></div></div></div>
<div class="strategy-hero"><div class="strategy-hero-label">Core Product Concept</div><div class="strategy-slogan">不只是产品，是<span>方案</span></div><div class="strategy-desc">定义</div></div>
<div class="strategy-grid"><div class="strategy-card"><div class="strategy-card-icon">1</div><div class="strategy-card-title">支柱</div><div class="strategy-card-text">文本</div><div class="strategy-card-highlight">高</div></div></div>
<div id="pricing" class="section-anchor"></div><div class="pricing-grid"><div class="pricing-card"><div class="pricing-tier">Starter</div><div class="pricing-price">$59</div><div class="pricing-desc">描述</div><div class="pricing-features"><div class="pricing-feature check">功能</div></div></div><div class="pricing-card recommended"><div class="pricing-tier">Core</div><div class="pricing-price">$89</div><div class="pricing-desc">描述</div><div class="pricing-features"><div class="pricing-feature check">功能</div></div></div><div class="pricing-card"><div class="pricing-tier">Premium</div><div class="pricing-price">$129</div><div class="pricing-desc">描述</div><div class="pricing-features"><div class="pricing-feature check">功能</div></div></div></div>
<div class="visual-grid"><div class="visual-card"><div class="visual-card-title">主图</div><div class="visual-item"><div class="visual-item-title">标题</div><div class="visual-item-text">文本</div></div></div></div>
<div id="prompt" class="section-anchor"></div><div class="prompt-grid"><div class="prompt-card"><div class="prompt-number">Prompt 01</div><div class="prompt-scene">场景</div><div class="prompt-text">prompt</div><div class="prompt-note">note</div></div><div class="prompt-card"><div class="prompt-number">Prompt 02</div><div class="prompt-scene">场景</div><div class="prompt-text">prompt</div><div class="prompt-note">note</div></div><div class="prompt-card"><div class="prompt-number">Prompt 03</div><div class="prompt-scene">场景</div><div class="prompt-text">prompt</div><div class="prompt-note">note</div></div></div>
<div class="supply-grid"><div class="supply-card"><div class="supply-label">有效报价数</div><div class="supply-value">50</div><div class="supply-note">说明</div></div><div class="supply-card"><div class="supply-label">采购价中位数</div><div class="supply-value">¥10</div><div class="supply-note">说明</div></div><div class="supply-card"><div class="supply-label">有效报价区间</div><div class="supply-value">¥8-¥20</div><div class="supply-note">说明</div></div><div class="supply-card"><div class="supply-label">热销供应端</div><div class="supply-value">中山市</div><div class="supply-note"><span class="asin-token" data-allow-asin="profit-model">B0GHIJKL34</span> 说明</div></div></div>
<div class="report-footer"><span>footer</span><span>footer</span></div>
"""
    if style == "lifecycle-strategy-report-v2":
        lifecycle_scaffold = """
<div class="fixed-template-copy">Lifecycle Strategy 全生命周期拓品战略 战略仪表盘 用户画像 生命周期旅程 四维拓品生态 拓品方案池 Bundle 策略 30/60/90 天路线图 风险矩阵 市场验证摘要 供应链 复购 AOV LTV</div>
<div class="accent archetype arrow badge blue bundle-body bundle-header bundle-items bundle-pricing bundle-target card chart-grid chart-subtitle chart-title conclusion-grid conclusion-item conclusion-item-text conclusion-item-title conclusion-title container desc detail emoji fill final gold green header-badge header-meta header-meta-item kpi-label kpi-sub kpi-value label mitigation name orig p1 p2 p3 persona-body persona-header persona-price phase-body phase-grid phase-header priority-bar purple quotes red report-footer save section-desc section-title sku-table-wrap source-card source-grid subtitle supply-badge tl-body tl-header tl-pain tl-skus tl-time type-badge value"></div>
<div class="ecosystem-pool-summary">SKU 候选池总数：30；推荐 SKU：5；筛选损耗已在分析文件记录。</div>
<div class="ecosystem-chart-grid"><div id="sunburst"></div><div id="priorityChart"></div></div><div id="aovChart"></div>
<div class="kpi-grid"><article class="kpi-card">KPI1</article><article class="kpi-card">KPI2</article><article class="kpi-card">KPI3</article><article class="kpi-card">KPI4</article><article class="kpi-card">KPI5</article></div>
<div class="persona-grid"><article class="persona-card">画像1</article><article class="persona-card">画像2</article><article class="persona-card">画像3</article></div>
<div class="timeline-grid"><article class="tl-card">阶段1</article><article class="tl-card">阶段2</article><article class="tl-card">阶段3</article><article class="tl-card">阶段4</article><article class="tl-card">阶段5</article></div>
<div class="sku-strategy-grid"><div class="sku-strategy-card">基础款</div><div class="sku-strategy-card">升级款</div><div class="sku-strategy-card">套装款</div><div class="sku-strategy-card">配件款</div><div class="sku-strategy-card">复购耗材</div></div>
<div class="filter-bar"><button class="filter-btn">全部</button><button class="filter-btn">基础款</button><button class="filter-btn">升级款</button><button class="filter-btn">配件款</button><button class="filter-btn">维护款</button><button class="filter-btn">供应链验证</button><button class="filter-btn">P1 立即启动</button></div>
<div class="bundle-grid"><article class="bundle-card">Bundle 1</article><article class="bundle-card">Bundle 2</article><article class="bundle-card">Bundle 3</article><article class="bundle-card">Bundle 4</article></div>
<div class="phase-grid roadmap-phase-grid"><div class="phase-card">Phase 1</div><div class="phase-card">Phase 2</div><div class="phase-card">Phase 3</div></div>
<div class="phase-grid roadmap-action-grid"><div class="phase-card">30天行动清单</div><div class="phase-card">60天行动清单</div><div class="phase-card">90天行动清单</div></div>
<div class="risk-grid"><article class="risk-card">风险1</article><article class="risk-card">风险2</article><article class="risk-card">风险3</article></div>
<details class="evidence-drawer"><summary>证据1</summary><div>详情</div></details><details class="evidence-drawer"><summary>证据2</summary><div>详情</div></details><details class="evidence-drawer"><summary>证据3</summary><div>详情</div></details><details class="evidence-drawer"><summary>证据4</summary><div>详情</div></details><details class="evidence-drawer"><summary>证据5</summary><div>详情</div></details><details class="evidence-drawer"><summary>证据6</summary><div>详情</div></details><details class="evidence-drawer"><summary>证据7</summary><div>详情</div></details>
<details id="skuFullPool" class="evidence-drawer sku-full-pool"><summary>完整候选池</summary><table><tbody><tr><td>候选</td><td data-supply="pending">仅竞品/VOC 候选</td></tr></tbody></table></details>
<table id="skuTable" class="sku"><tbody id="skuBody"></tbody></table>
"""
    if style == "demand-gap-report-v2":
        joy_cards = "".join(
            '<article class="demand-evidence-card joy"><p data-allow-english-review="short">works well</p><dl class="demand-evidence-meta"><dt>需求强度</dt><dd>高</dd></dl></article>'
            for _ in range(6)
        )
        pain_cards = "".join(
            '<article class="demand-evidence-card pain"><p data-allow-english-review="short">fails fast</p><dl class="demand-evidence-meta"><dt>需求强度</dt><dd>高</dd></dl></article>'
            for _ in range(6)
        )
        demand_scaffold = f"""
<div class="fixed-template-copy">Demand Gap Analysis 目标ASIN锚点 决策看板 市场痛点全景图（需求主题） 满意度鸿沟 场景化机会矩阵 KANO × JTBD 真实原声剧场 用户原声 需求优先级 正面反馈 负面反馈</div>
<div class="hero sec card focus kano-grid chart-interpretation chart eyebrow k kpi kpi-grid lead muted ok quote-cn quote-origin sub v warn wrap"></div>
<div class="demand-brief-stack"><div class="chart-interpretation">参考竞品ASIN <span class="asin-token" data-allow-asin="demand-target-anchor">B0TEST1234</span></div></div>
<div hidden data-chart-source="appealsRows"><span data-label="痛点" data-value="5"></span></div><div id="appealsRose" class="chart demand-chart"></div>
<div hidden data-chart-source="gapRows"><span data-label="鸿沟" data-value="90"></span></div><div id="gapRadar" class="chart demand-chart"></div>
<div class="demand-evidence-grid demand-sentiment-columns"><section class="demand-sentiment-column positive"><div class="demand-column-head"><span>Positive</span><h3>正面反馈</h3></div>{joy_cards}</section><section class="demand-sentiment-column negative"><div class="demand-column-head"><span>Negative</span><h3>负面反馈</h3></div>{pain_cards}</section></div>
<details class="evidence-drawer"><summary>用户原声证据明细表</summary><div class="drawer-body">评论证据明细</div></details>
"""
    section_html = "\n".join(
        f'<section id="{slug}" class="section"><div class="section-header"><span class="section-number">{idx:02d}</span><h2 class="section-title">{name}</h2><p class="section-desc">固定模板章节</p></div>'
        f'<div class="chart-container"><div class="mini-chart"><div class="bar-row"><span>数据</span><div class="bar"><span style="--w:50%"></span></div><b>中</b></div></div></div>'
        f'<table class="evidence-table insight-table"><tr><th>结论</th><th>证据强度</th><th>商业含义</th><th>建议动作</th></tr>'
        f'<tr><td>{name}</td><td>高</td><td>数据覆盖足以支撑方向判断</td><td>优先转成页面卖点和实物测试清单</td></tr></table></section>'
        for idx, (slug, name) in enumerate(sections, 1)
    )
    interactions = """
<nav class="site-nav"><button class="site-nav-toggle" type="button">目录</button><a href="report.html">三合一报告</a></nav>
<div data-tabs><button class="tab-button" type="button" data-tab-target="evidence" aria-selected="true">证据</button><div data-tab-panel="evidence">证据强度：高</div></div>
<div class="filter-bar"><button class="filter-btn active" type="button" data-filter="all" aria-pressed="true">全部</button><button class="filter-btn" type="button" data-filter="高" aria-pressed="false">高</button></div>
<details class="evidence-drawer"><summary>证据抽屉</summary><div class="drawer-body">数据覆盖和数据缺口均已标注。</div></details>
"""
    html = f"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><link rel="stylesheet" href="assets/report.css"><style>.report-header{{}}.kpi-grid{{}}.section-number{{}}.evidence-table{{}}.insight-table{{}}.chart-container{{}}.mini-chart{{}}.insight-box{{}}.conclusion{{}}.deep-dive-grid{{}}.comp-deep-card{{}}.opportunity-matrix{{}}</style></head>
<body{body_attr}>
<header class="report-header"><h1>{title}</h1><div class="kpi-grid"><article class="kpi-card">Go / Watch / No-Go</article><article class="kpi-card">证据强度：高</article><article class="kpi-card">数据覆盖：充分</article><article class="kpi-card">数据缺口：已标注</article></div></header>
<main>
<div class="insight-box">客户版 AI 深度分析报告：先给判断，再给原因，最后给建议动作。</div>
{interactions}
{market_scaffold}
{lifecycle_scaffold}
{demand_scaffold}
{section_html}
<section><div class="deep-dive-grid"><div class="comp-deep-card">标杆竞品 · 溢价逻辑 · 未满足需求</div></div></section>
<section><div class="insight-box">置信等级：中高；数据覆盖与数据缺口已进入判断。</div><div class="conclusion">结论：优先执行高确定性动作。</div></section>
{extra_terms}
</main>
<script src="assets/report.js" defer></script>
</body></html>"""
    html = (
        html.replace("样本", "数据")
        .replace("样品", "实物")
        .replace("补数", "成本与转化核对")
        .replace("待补", "数据已采集")
        .replace("待验证", "按真实数据判断")
        .replace("未分层", "已归类")
    )
    return html


def make_valid_report(root):
    write_json(
        root / "data" / "data_pack.json",
        {
            "task_id": "ai_plush_us_20260526",
            "created_at": "2026-05-26T10:00:00+08:00",
            "sources": [
                {
                    "source_id": "src_001",
                    "provider": "sorftime",
                    "tool": "product_search",
                    "fetched_at": "2026-05-26T10:00:00+08:00",
                    "confidence": "medium",
                },
                {
                    "source_id": "src_002",
                    "provider": "firecrawl",
                    "tool": "firecrawl_search",
                    "fetched_at": "2026-05-26T10:01:00+08:00",
                    "confidence": "medium",
                },
            ],
            "products": competitor_rows(30),
            "keywords": [
                {"keyword": f"ai plush keyword {idx}", "source_id": "src_001", "provider": "sorftime"}
                for idx in range(1000)
            ],
            "categories": [{"node_id": "123", "source_id": "src_001", "provider": "sorftime"}],
            "reviews": [
                {
                    "asin": "B0TEST1234",
                    "title": "privacy issue",
                    "text": "This toy stopped working after two days and the privacy policy is confusing.",
                    "source_id": "src_001",
                    "provider": "sorftime",
                }
            ],
            "tiktok_products": [{"product_id": "tk_1", "source_id": "src_001", "provider": "sorftime"}],
            "tiktok_videos": [{"video_id": "v_1", "source_id": "src_001", "provider": "sorftime"}],
            "suppliers": supplier_rows(50),
            "web_documents": [{"url": "https://example.com/report", "source_id": "src_002", "provider": "firecrawl"}],
            "data_gaps": ["Keepa not used in this run"],
            "quality": {"overall_score": 0.82, "grade": "decision_grade"},
            "normalization": {"deduped": True},
        },
    )
    data_pack = json.loads((root / "data" / "data_pack.json").read_text(encoding="utf-8"))
    data_pack["effective_products"] = data_pack["products"]
    data_pack["effective_suppliers"] = data_pack["suppliers"]
    counts = {key: len(data_pack.get(key) or []) for key in ENTITY_LIST_KEYS}
    data_pack["normalization"].update(
        {
            "before_counts": counts,
            "after_counts": counts,
            "removed_counts": {key: 0 for key in ENTITY_LIST_KEYS},
            "cross_validated_counts": {key: 0 for key in ENTITY_LIST_KEYS},
        }
    )
    data_pack["cleaning_summary"] = data_pack["normalization"]
    write_json(root / "data" / "data_pack.json", data_pack)
    write_json(root / "data" / "normalized" / "normalized_data_pack.json", data_pack)
    readiness_counts = {
        "sources": 2,
        "raw_products": 30,
        "products": 30,
        "valid_competitors": 30,
        "market_segments": 3,
        "raw_keywords": 1000,
        "keywords": 1000,
        "categories": 1,
        "raw_reviews": 1,
        "reviews": 1,
        "tiktok_products": 1,
        "tiktok_videos": 1,
        "tiktok_authors": 0,
        "raw_suppliers": 50,
        "suppliers": 50,
        "valid_supplier_quotes": 50,
        "raw_valid_supplier_quotes": 50,
        "web_documents": 1,
        "data_gaps": 1,
    }
    supplier_quote_gate = {
        "required": 50,
        "actual": 50,
        "raw_valid_quotes": 50,
        "raw_finished_valid_quotes": 50,
        "non_finished_filtered": 0,
        "strict_relevance_filtered": 0,
        "passed": True,
        "policy": "1688 去重有效报价必须同时满足数量、字段质量和研究对象相关性，不得用无关报价生成最终供应链毛利率结论。",
    }
    supplier_quality_gate = {
        "required_field_coverage_pct": 70,
        "title_coverage_pct": 100.0,
        "identity_coverage_pct": 100.0,
        "segment_hint_coverage_pct": 0.0,
        "p25_rmb": 24.25,
        "p50_rmb": 36.5,
        "p75_rmb": 48.75,
        "max_rmb": 61.0,
        "max_to_p50_ratio": 1.67,
        "p75_to_p25_ratio": 2.01,
        "field_quality_passed": True,
        "price_spread_passed": True,
        "same_search_bucket_gate": {"passed": False, "bucket": None, "valid_quotes": 0, "quality": None},
        "global_passed": True,
        "effective_passed": True,
        "customer_visible_passed": True,
        "raw_finished_valid_quotes": 50,
        "strict_relevant_valid_quotes": 50,
        "strict_relevance_filtered": 0,
        "raw_quality_gate": {
            "required_field_coverage_pct": 70,
            "title_coverage_pct": 100.0,
            "identity_coverage_pct": 100.0,
            "segment_hint_coverage_pct": 0.0,
            "p25_rmb": 24.25,
            "p50_rmb": 36.5,
            "p75_rmb": 48.75,
            "max_rmb": 61.0,
            "max_to_p50_ratio": 1.67,
            "p75_to_p25_ratio": 2.01,
            "field_quality_passed": True,
            "price_spread_passed": True,
            "passed": True,
        },
        "passed": True,
    }
    competitor_gate = {
        "minimum_total": 30,
        "valid_total": 30,
        "minimum_per_primary_segment": 0,
        "segments": {"智能陪伴玩具": 10, "语音互动玩具": 10, "儿童礼品玩具": 10},
        "underfilled_segments": {},
        "passed": True,
    }
    segment_gate = {
        "broad_research": False,
        "required_segments": 0,
        "segments": {"智能陪伴玩具": 10, "语音互动玩具": 10, "儿童礼品玩具": 10},
        "underfilled_segments": {},
        "passed": True,
    }
    readiness = {
        "report_dir": str(root),
        "checked_at": "2026-05-26T10:00:00Z",
        "depth": "standard",
        "data_pack": "data/normalized/normalized_data_pack.json",
        "sample_class": "acceptance_sample",
        "acceptance_ready": True,
        "partial_report_ready": False,
        "supply_conclusion_blocked": False,
        "blocking_gaps": [],
        "warnings": [{"module": "review_sample_depth", "current": 1, "recommended": 80}],
        "counts": readiness_counts,
        "supplier_quote_gate": supplier_quote_gate,
        "supplier_quality_gate": supplier_quality_gate,
        "competitor_gate": competitor_gate,
        "segment_gate": segment_gate,
        "collector_commands": [],
    }
    readiness_summary = {
        "acceptance_ready": True,
        "partial_report_ready": False,
        "supply_conclusion_blocked": False,
        "sample_class": "acceptance_sample",
        "depth": "standard",
        "blocking_gap_count": 0,
        "warning_count": 1,
        "counts": readiness_counts,
        "supplier_quote_gate": supplier_quote_gate,
        "supplier_quality_gate": supplier_quality_gate,
        "competitor_gate": competitor_gate,
        "segment_gate": segment_gate,
    }
    delivery_readiness = {"path": "data/normalized/data_readiness_report.json", **readiness_summary}
    write_json(root / "data" / "normalized" / "data_readiness_report.json", readiness)
    child_skills = {
        "market_depth": "child_skills/market-depth-report",
        "lifecycle_strategy": "child_skills/lifecycle-strategy-report",
        "demand_gap": "child_skills/demand-gap-report",
        "critic": "child_skills/market-research-critic",
    }
    site_assets = {
        "css": "output/html_reports/assets/report.css",
        "js": "output/html_reports/assets/report.js",
        "data": "output/html_reports/assets/report-data.json",
        "echarts": "output/html_reports/assets/echarts.min.js",
    }
    interactive_features = ["table_filter", "table_sort", "tabs", "evidence_drawer", "chart_linking", "pc_anchor_nav"]
    child_invocations = child_skill_invocations(child_skills)
    write_json(
        root / "report_brief.json",
        {
            "task_id": "ai_plush_us_20260526",
            "child_skills": child_skills,
            "child_skill_invocations": child_invocations,
            "static_site": {"bundle_dir": "output/html_reports", "assets": site_assets, "interactive_features": interactive_features},
            "data_inputs": {
                "normalized_data_pack": "data/normalized/normalized_data_pack.json",
                "analysis_plan": "analysis/analysis_plan.json",
            },
        },
    )
    write_json(
        root / "analysis" / "analysis_plan.json",
        {
            "task_id": "ai_plush_us_20260526",
            "method_chain": [
                {
                    "method_id": "market.top100_competitor_scan",
                    "name": "Top100 competitor scan",
                    "used_source_ids": ["src_001"],
                    "output": "competitor matrix",
                },
                {
                    "method_id": "decision.go_watch_nogo",
                    "name": "Go / Watch / No-Go",
                    "used_source_ids": ["src_001", "src_002"],
                    "output": "Watch",
                },
            ],
            "confidence": {"final_decision": "medium"},
            "limitations": ["Sorftime estimates are not official Amazon sales."],
        },
    )
    view_model = {
        "kpis": [{"label": "核心判断", "value": "Watch"}],
        "charts": {},
        "tables": {},
        "cards": {},
        "evidence_strength": "中",
        "sample_coverage": {"products": 1, "keywords": 1000, "reviews": 1},
        "limitations": ["评论样本需要继续补充"],
        "client_safe_text": True,
    }
    write_json(root / "analysis" / "market_depth_view.json", view_model)
    write_json(root / "analysis" / "lifecycle_strategy_view.json", view_model)
    write_json(root / "analysis" / "demand_gap_view.json", view_model)
    cosmo_relation_labels = {
        "USED_FOR_FUNC": "功能 / 用途",
        "USED_FOR_EVE": "事件 / 活动",
        "USED_FOR_AUD": "受众",
        "CAPABLE_OF": "能力 / 可完成任务",
        "USED_TO": "使用目的",
        "USED_AS": "概念 / 产品类型",
        "IS_A": "品类归属",
        "USED_ON": "时间 / 季节 / 事件",
        "USED_IN_LOC": "位置 / 场所",
        "USED_IN_BODY": "身体部位",
        "USED_WITH": "互补搭配",
        "USED_BY": "使用者",
        "xINTERSTED_IN": "兴趣偏好",
        "xIs_A": "人群身份",
        "xWANT": "用户想要达成",
    }
    cosmo_relation_terms = {
        "USED_FOR_FUNC": ["语音互动", "情绪陪伴", "儿童安抚"],
        "USED_FOR_EVE": ["生日礼物", "睡前陪伴", "节日赠礼"],
        "USED_FOR_AUD": ["儿童家庭", "礼品买家", "亲子用户"],
        "CAPABLE_OF": ["多轮对话", "故事播放", "安全互动"],
        "USED_TO": ["陪孩子聊天", "安抚入睡", "提升互动感"],
        "USED_AS": ["智能陪伴玩具", "AI 毛绒玩具", "儿童互动礼物"],
        "IS_A": ["儿童智能玩具", "陪伴型礼品", "语音互动产品"],
        "USED_ON": ["睡前场景", "生日季", "家庭陪伴时段"],
        "USED_IN_LOC": ["儿童房", "客厅互动区", "家庭礼品场景"],
        "USED_IN_BODY": ["手部抱握", "柔软接触", "儿童拥抱"],
        "USED_WITH": ["充电线", "故事内容包", "礼盒包装"],
        "USED_BY": ["儿童用户", "父母购买者", "亲子家庭"],
        "xINTERSTED_IN": ["AI 陪伴", "互动玩具", "礼品创意"],
        "xIs_A": ["新手父母", "礼品决策者", "儿童玩具买家"],
        "xWANT": ["更安全互动", "更自然对话", "更持久陪伴"],
    }
    write_json(
        root / "analysis" / "cosmo_alexa_tags.json",
        {
            "schema_version": "cosmo_alexa_tags.v1",
            "coverage_summary": {
                "relation_total": len(validator.COSMO_ALEXA_RELATION_TYPES),
                "high_confidence_relations": len(validator.COSMO_ALEXA_RELATION_TYPES),
                "evidence_records": 30,
            },
            "relations": [
                {
                    "relation_type": relation_type,
                    "label_cn": cosmo_relation_labels[relation_type],
                    "display_relation": cosmo_relation_labels[relation_type].replace(" / ", "·"),
                    "dimension": "产品标签",
                    "terms": cosmo_relation_terms[relation_type],
                    "source_evidence": [
                        {
                            "source_type": "effective_products",
                            "source_id": "B0VALID0001",
                            "field": "title",
                            "excerpt": " ".join(cosmo_relation_terms[relation_type]),
                        }
                    ],
                    "confidence": "高",
                    "coverage_status": "已覆盖",
                    "evidence_count": 3,
                    "listing_label": "首屏承诺",
                    "listing_action": "标题与五点写入核心场景词。",
                    "qa_label": "证据问答",
                    "qa_action": "QA 补充用户使用场景。",
                    "ad_label": "精准投放",
                    "ad_action": "广告分组按场景词拆分。",
                }
                for relation_type in sorted(validator.COSMO_ALEXA_RELATION_TYPES)
            ],
        },
    )
    lifecycle_pool = [
        {
            "name": f"智能陪伴玩具 候选SKU {idx}",
            "type": ["core_validation", "scenario_upgrade", "accessory_gap", "maintenance_repurchase"][idx % 4],
            "strategy_type_key": ["core_validation", "scenario_upgrade", "accessory_gap", "maintenance_repurchase"][idx % 4],
            "type_label_cn": ["基础验证款", "场景升级款", "配件补位款", "维护复购款"][idx % 4],
            "target_segment": ["智能陪伴玩具", "语音互动玩具", "儿童礼品玩具"][idx % 3],
            "reference_competitor": f"ToyBrand {idx % 8} 智能陪伴玩具",
            "reference_asin": f"B0V{idx:07d}",
            "priority": 90 - idx % 30,
            "ecosystem_path": ["关联度", "场景", "消耗", "维护"][idx % 4],
            "ecosystem_segment": ["智能陪伴玩具", "语音互动玩具", "儿童礼品玩具"][idx % 3],
            "source_id": "src_001",
        }
        for idx in range(30)
    ]
    write_json(
        root / "analysis" / "lifecycle_strategy.json",
        {
            "schema_version": "lifecycle_strategy.v1",
            "sku_candidate_pool": lifecycle_pool,
            "recommended_skus": lifecycle_pool[:5],
            "ecosystem_nodes": [],
            "filter_diagnostics": {
                "effective_products": 30,
                "effective_suppliers": 50,
                "finished_suppliers": 50,
                "sku_candidate_pool": 30,
                "recommended_skus": 5,
                "filtered_reason": "测试样本保留具备竞品锚点和供应证据的候选。",
            },
        },
    )
    write_text(root / "data" / "lineage.md", "# Data Lineage\n\n- src_001: Sorftime product_search\n- src_002: Firecrawl search\n")
    write_text(root / "output" / "report.md", "# Report\n\n估算月销量（Sorftime）来自 src_001。\n\n## Go / Watch / No-Go\nWatch\n")
    write_text(
        root / "output" / "report.html",
        """<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><link rel="stylesheet" href="html_reports/assets/report.css"><style>.report-index{}.report-card{}</style></head>
<body><main class="report-index">
<h1>三合一市场研究报告</h1>
<a href="html_reports/market-depth-report.html">市场深度调研报告</a>
<a href="html_reports/lifecycle-strategy-report.html">产品全生命周期拓品战略报告</a>
<a href="html_reports/demand-gap-report.html">用户心智断层与需求机会报告</a>
<p>Go / Watch / No-Go · 证据强度 · 数据覆盖 · 数据缺口 · 置信等级 · 建议动作</p>
</main><script src="html_reports/assets/report.js" defer></script></body></html>""",
    )
    write_text(
        root / "output" / "html_reports" / "report.html",
        """<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><link rel="stylesheet" href="assets/report.css"><style>.report-index{}.report-card{}</style></head>
<body><main class="report-index">
<h1>三合一市场研究报告</h1>
<a href="market-depth-report.html">市场深度调研报告</a>
<a href="lifecycle-strategy-report.html">产品全生命周期拓品战略报告</a>
<a href="demand-gap-report.html">用户心智断层与需求机会报告</a>
<p>Go / Watch / No-Go · 证据强度 · 数据覆盖 · 数据缺口 · 置信等级 · 建议动作</p>
</main><script src="assets/report.js" defer></script></body></html>""",
    )
    write_text(
        root / "output" / "html_reports" / "market-depth-report.html",
        child_html(
            "market-depth-report-v2",
            "市场深度调研报告",
            [
                ("market-dashboard", "大盘仪表盘 · Market Dashboard"),
                ("cosmo-alexa-tags", "COSMO + Alexa 标签识别 · 产品标签 × 用户标签"),
                ("competitor-scan", "Top 竞品全景扫描"),
                ("voc-deep-dive", "VOC 体验深潜 · 痛点 × 爽点雷达"),
                ("competitor-deep-dive", "标杆竞品狙击拆解"),
                ("opportunity", "新品狙击企划 · Product Definition"),
                ("pricing", "建议定价策略"),
                ("visual-direction", "视觉与包装指导 · Visual Direction"),
                ("prompt", "AI生图 Prompt · 可直接使用"),
                ("supply-chain", "供应链成本估算 · 1688大盘数据"),
            ],
            "价格带销量分布图 COSMO + Alexa 15 类核心标签 竞品狙击结论 定价战略核心逻辑 AI生图 Prompt 供应链核心结论",
        ),
    )
    write_text(
        root / "output" / "html_reports" / "lifecycle-strategy-report.html",
        child_html(
            "lifecycle-strategy-report-v2",
            "产品全生命周期拓品战略报告",
            [
                ("strategy-dashboard", "战略仪表盘"),
                ("personas", "用户画像"),
                ("lifecycle-journey", "生命周期旅程"),
                ("ecosystem", "四维拓品生态"),
                ("sku-table", "拓品方案池"),
                ("bundle-strategy", "Bundle 策略"),
                ("roadmap", "30/60/90 天路线图"),
                ("risk-matrix", "风险矩阵"),
                ("market-intelligence", "市场验证摘要"),
            ],
            "SKU Bundle 供应链 复购 AOV LTV",
        ),
    )
    write_text(
        root / "output" / "html_reports" / "demand-gap-report.html",
        child_html(
            "demand-gap-report-v2",
            "用户心智断层与需求机会报告",
            [
                ("target-anchor", "目标ASIN锚点"),
                ("decision-board", "决策看板"),
                ("appeals-map", "市场痛点全景图（需求主题）"),
                ("gap-analysis", "满意度鸿沟"),
                ("kano-jtbd", "KANO × JTBD"),
                ("voice-theater", "用户原声"),
                ("priority-table", "需求优先级"),
            ],
            "KANO JTBD 心智断层 负面触发点 转化机会",
        ),
    )
    write_json(
        root / "output" / "delivery_result.json",
        {
            "status": "complete",
            "decision": "Watch",
            "formats": ["html", "markdown", "json"],
            "html_reports": {
                "index": "output/html_reports/report.html",
                "compat_index": "output/report.html",
                "market_depth": "output/html_reports/market-depth-report.html",
                "lifecycle_strategy": "output/html_reports/lifecycle-strategy-report.html",
                "demand_gap": "output/html_reports/demand-gap-report.html",
            },
            "html_bundle_dir": "output/html_reports",
            "child_skills": child_skills,
            "child_skill_invocations": child_invocations,
            "site_assets": site_assets,
            "interactive_features": interactive_features,
            "cleaning_summary": data_pack["normalization"],
            "cosmo_alexa_tags": {
                "path": "analysis/cosmo_alexa_tags.json",
                "relation_total": len(validator.COSMO_ALEXA_RELATION_TYPES),
                "high_confidence_relations": len(validator.COSMO_ALEXA_RELATION_TYPES),
            },
            "lifecycle_sku_pool_summary": {
                "effective_products": 30,
                "effective_suppliers": 50,
                "finished_suppliers": 50,
                "sku_candidate_pool": 30,
                "recommended_skus": 5,
                "filtered_reason": "测试样本保留具备竞品锚点和供应证据的候选。",
            },
            "data_readiness": delivery_readiness,
            "asin_display_scope": ["competitor_table", "benchmark_sniper", "profit_model", "demand_target_anchor", "sku_reference"],
            "critic_review": {
                "path": "analysis/critic_review.json",
                "refinement_plan": "analysis/refinement_plan.json",
                "summary": "analysis/critic_summary.md",
                "pass": True,
                "score": 82,
                "max_refinement_rounds": 2,
            },
        },
    )
    write_text(
        root / "output" / "html_reports" / "assets" / "report.css",
        ".site-nav{}.table-tools{}.tab-button{}.evidence-drawer{}.mini-chart{}"
        ".template-market .report-header{}.template-lifecycle .report-header{}"
        ".template-demand .report-header{}.template-demand .hero{}"
        ".persona-grid{}.timeline-grid{}.bundle-grid{}.filter-btn{}.sku-table-wrap{}"
        ".ecosystem-pool-summary{}.cosmo-layout{}.cosmo-matrix{}.cosmo-top-list{}.cosmo-gap-panel{}.cosmo-action-board{}.quote-cn{}.chart-interpretation{}@media(max-width:760px){}\n",
    )
    write_text(
        root / "output" / "html_reports" / "assets" / "report.js",
        "document.querySelector('.site-nav-toggle');input.type='search';document.querySelectorAll('th');"
        "document.querySelector('[data-tabs]');document.querySelector('[data-tab-target]');"
        "document.querySelectorAll('.mini-chart .bar-row');document.querySelector('.filter-bar');"
        "row.dataset.filter;addEventListener('click',()=>{});"
        "renderer:isIOSWebKit;priceChart;bubbleChart;growthChart;featureChart;radarChart;marginChart;"
        "type:'sunburst';priorityChart;aovChart;type:'sankey';appealsRose;gapRadar;\n",
    )
    write_json(
        root / "output" / "html_reports" / "assets" / "report-data.json",
        {
            "child_skills": child_skills,
            "interactive_features": interactive_features,
            "readiness": readiness_summary,
            "cleaning_summary": data_pack["normalization"],
        },
    )
    write_text(root / "output" / "html_reports" / "assets" / "echarts.min.js", "window.echarts=window.echarts||{};\n")
    write_json(
        root / "analysis" / "critic_review.json",
        {
            "pass": True,
            "round_id": 0,
            "score": 82,
            "grade": "B",
            "findings": [],
            "blocking_issues": [],
            "resolved_findings": [],
            "remaining_findings": [],
            "report_issues": {"market_depth": [], "lifecycle_strategy": [], "demand_gap": []},
            "data_confidence": {"review_depth": "low", "cross_validation": "low", "decision_confidence": "aligned"},
            "suggestions": [],
            "refinement_targets": [],
            "applied_operations": [],
        },
    )
    write_json(
        root / "analysis" / "refinement_plan.json",
        {
            "status": "accepted",
            "round_id": 0,
            "max_refinement_rounds": 2,
            "operations": [],
            "refinement_targets": [],
            "applied_operations": [],
            "constraints": ["Do not recollect data during critic refinement."],
        },
    )
    write_text(
        root / "analysis" / "critic_summary.md",
        "# Critic Summary\n\n"
        "- readiness: `pass`\n"
        "- final_pass: `true`\n"
        "- final_score: `82`\n"
        "- final_decision: `Watch`\n"
        "- remaining_findings: `none`\n\n"
        "## Guardrails\n\n"
        "- If final_pass is false, the orchestrator must not claim delivery completion.\n",
    )
    write_json(
        root / "analysis" / "child_skill_invocation_log.json",
        [
            invocation_entry(root, "child_skills/market-depth-report", "child_skills/market-depth-report/scripts/render_market_depth_report.py", "output/html_reports/market-depth-report.html"),
            invocation_entry(root, "child_skills/lifecycle-strategy-report", "child_skills/lifecycle-strategy-report/scripts/render_lifecycle_strategy_report.py", "output/html_reports/lifecycle-strategy-report.html"),
            invocation_entry(root, "child_skills/demand-gap-report", "child_skills/demand-gap-report/scripts/render_demand_gap_report.py", "output/html_reports/demand-gap-report.html"),
            invocation_entry(
                root,
                "child_skills/market-research-critic",
                "child_skills/market-research-critic/scripts/run_critic.py",
                outputs=["analysis/critic_review.json", "analysis/refinement_plan.json", "analysis/critic_summary.md"],
                dispatch_mode="subprocess_critic_child",
            ),
        ],
    )


class ValidateMarketResearchDeliverablesTest(unittest.TestCase):
    def test_customer_html_rejects_empty_or_non_http_image_src(self):
        data_pack = {"products": [], "keywords": [], "reviews": [], "suppliers": []}
        broken_images = [
            '<section><img class="comp-product-thumb" src="" alt="竞品图片"></section>',
            '<section><img class="comp-product-thumb" src="data:image/png;base64,abc" alt="竞品图片"></section>',
        ]

        for html_doc in broken_images:
            with self.subTest(html_doc=html_doc):
                with self.assertRaises(validator.ValidationError):
                    validator.validate_customer_html("output/html_reports/market-depth-report.html", html_doc, data_pack)

    def test_customer_html_rejects_1688_or_alibaba_images_in_competitor_modules(self):
        data_pack = {"products": [], "keywords": [], "reviews": [], "suppliers": []}
        html_doc = (
            '<section id="competitor-scan">'
            '<img class="comp-product-thumb" src="https://cbu01.alicdn.com/img/ibank/example.jpg" alt="竞品图片">'
            "</section>"
        )

        with self.assertRaisesRegex(validator.ValidationError, "1688|Alibaba|竞品图片"):
            validator.validate_customer_html("output/html_reports/market-depth-report.html", html_doc, data_pack)

    def test_customer_html_rejects_1688_images_in_lifecycle_reference_sku_modules(self):
        data_pack = {"products": [], "keywords": [], "reviews": [], "suppliers": []}
        html_doc = (
            '<section id="sku-strategy">'
            '<img class="sku-reference-thumb table-thumb" src="https://cbu01.alicdn.com/img/ibank/example.jpg" alt="参考竞品图片">'
            "<p>证据强度 高 数据覆盖 已记录 数据缺口 已记录 置信等级 中 建议动作 继续核验</p>"
            "</section>"
        )

        with self.assertRaisesRegex(validator.ValidationError, "1688|Alibaba|竞品图片"):
            validator.validate_customer_html("output/html_reports/lifecycle-strategy-report.html", html_doc, data_pack)

    def test_customer_html_rejects_non_amazon_competitor_image_domains(self):
        data_pack = {"products": [], "keywords": [], "reviews": [], "suppliers": []}
        html_doc = (
            '<section id="competitor-scan">'
            '<img class="comp-deep-image" src="https://cdn.example-shop.com/product/example.jpg" alt="竞品图片">'
            "</section>"
        )

        with self.assertRaisesRegex(validator.ValidationError, "Amazon|竞品图片"):
            validator.validate_customer_html("output/html_reports/market-depth-report.html", html_doc, data_pack)

    def test_market_template_requires_competitor_image_or_image_diagnostic(self):
        cosmo_products = "".join(
            f'<article data-cosmo-relation="{"P" if idx < 8 else "U"}{(idx + 1) if idx < 8 else (idx - 7):02d}" data-dimension="{"产品标签" if idx < 8 else "用户标签"}"><div class="cosmo-relation-lane"><span>{"产品意图" if idx < 8 else "用户意图"}</span><b class="cosmo-relation-id">{"产品" if idx < 8 else "用户"}</b></div><div class="cosmo-tag-terms">标签</div></article>'
            for idx in range(8)
        )
        cosmo_users = "".join(
            f'<article data-cosmo-relation="U{idx - 7:02d}" data-dimension="用户标签"><div class="cosmo-relation-lane"><span>用户意图</span><b class="cosmo-relation-id">用户</b></div><div class="cosmo-tag-terms">标签</div></article>'
            for idx in range(8, 15)
        )
        pricing = "".join('<div class="pricing-card">价格</div>' for _ in range(3))
        prompts = "".join('<div class="prompt-card">Prompt</div>' for _ in range(3))
        html_doc = (
            '<section id="market-dashboard"></section>'
            '<section id="cosmo-alexa-tags">'
            '<div class="cosmo-matrix"><div class="cosmo-matrix-lanes">'
            '<div class="cosmo-matrix-lane product-lane"><div class="cosmo-lane-title"><span>产品标签 · 产品被算法识别为什么</span></div>'
            f"{cosmo_products}</div>"
            '<div class="cosmo-matrix-lane user-lane"><div class="cosmo-lane-title"><span>用户标签 · 用户为什么搜索/购买</span></div>'
            f"{cosmo_users}</div></div></div>"
            '<div class="cosmo-top-list"></div><div class="cosmo-gap-panel"></div><div class="cosmo-action-board"></div></section>'
            '<section id="competitor-scan"><table><tr><th>ASIN</th></tr><tr><td data-allow-asin="competitor-table">B0TEST1234</td></tr></table></section>'
            '<section id="voc-deep-dive"></section>'
            '<div id="pricing"></div><div id="prompt"></div>'
            f"{pricing}{prompts}"
        )

        with self.assertRaisesRegex(validator.ValidationError, "competitor image|竞品图片|图片诊断"):
            validator.validate_fixed_template_slots("output/html_reports/market-depth-report.html", html_doc, "market-depth-report-v2")

    def test_market_template_rejects_visible_cosmo_relation_codes_and_missing_intent_slots(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            html_path = report_dir / "output" / "html_reports" / "market-depth-report.html"
            html_doc = html_path.read_text(encoding="utf-8")
            html_doc = html_doc.replace("产品意图", "USED_FOR_FUNC")
            html_doc = html_doc.replace('class="cosmo-relation-id">产品</b>', "")
            html_path.write_text(html_doc, encoding="utf-8")

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("COSMO", result.stderr + result.stdout)

    def test_market_template_requires_cosmo_product_and_user_lanes(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            html_path = report_dir / "output" / "html_reports" / "market-depth-report.html"
            html_doc = html_path.read_text(encoding="utf-8")
            html_doc = html_doc.replace('class="cosmo-matrix-lane product-lane"', 'class="cosmo-matrix-lane"')
            html_doc = html_doc.replace("产品标签 · 产品被算法识别为什么", "15 标签矩阵")
            html_path.write_text(html_doc, encoding="utf-8")
            refresh_child_output_sha(report_dir, "output/html_reports/market-depth-report.html")

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("COSMO", result.stderr + result.stdout)

    def test_market_template_rejects_visible_internal_cosmo_placeholders(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            html_path = report_dir / "output" / "html_reports" / "market-depth-report.html"
            html_doc = html_path.read_text(encoding="utf-8")
            html_doc = html_doc.replace("产品意图", "产品意图 P01")
            html_path.write_text(html_doc, encoding="utf-8")
            refresh_child_output_sha(report_dir, "output/html_reports/market-depth-report.html")

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("COSMO", result.stderr + result.stdout)

    def test_market_template_rejects_internal_cosmo_codes_in_data_attributes(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            html_path = report_dir / "output" / "html_reports" / "market-depth-report.html"
            html_doc = html_path.read_text(encoding="utf-8")
            html_doc = html_doc.replace('data-cosmo-relation="P01"', 'data-cosmo-relation="USED_FOR_FUNC"')
            html_path.write_text(html_doc, encoding="utf-8")
            refresh_child_output_sha(report_dir, "output/html_reports/market-depth-report.html")

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("COSMO", result.stderr + result.stdout)

    def test_rejects_cosmo_relations_with_repeated_term_signatures(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            cosmo_path = report_dir / "analysis" / "cosmo_alexa_tags.json"
            payload = json.loads(cosmo_path.read_text(encoding="utf-8"))
            for item in payload["relations"][:10]:
                item["terms"] = ["通用标签", "泛化场景", "有效标签"]
                item["confidence"] = "高"
                item["evidence_count"] = 12
            write_json(cosmo_path, payload)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("COSMO", result.stderr + result.stdout)

    def test_rejects_cosmo_relations_with_overused_single_term(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            cosmo_path = report_dir / "analysis" / "cosmo_alexa_tags.json"
            payload = json.loads(cosmo_path.read_text(encoding="utf-8"))
            for idx, item in enumerate(payload["relations"][:8]):
                item["terms"] = [f"专属标签{idx}", "重复泛词", f"证据词{idx}"]
                item["confidence"] = "高"
                item["evidence_count"] = 10
            write_json(cosmo_path, payload)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("COSMO", result.stderr + result.stdout)

    def test_rejects_cosmo_terms_without_current_evidence_support(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            cosmo_path = report_dir / "analysis" / "cosmo_alexa_tags.json"
            payload = json.loads(cosmo_path.read_text(encoding="utf-8"))
            payload["relations"][0]["terms"] = ["语音互动", "宠物饮水机"]
            payload["relations"][0]["source_evidence"] = [
                {
                    "source_type": "effective_products",
                    "source_id": "B0VALID0001",
                    "field": "title",
                    "excerpt": "语音互动 情绪陪伴 儿童安抚",
                }
            ]
            write_json(cosmo_path, payload)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("COSMO", result.stderr + result.stdout)

    def test_customer_safety_context_is_cached_per_data_pack(self):
        data_pack = {
            "sources": [{"source_id": "src_001", "provider": "sorftime"}],
            "reviews": [{"title": "privacy issue", "text": "This toy stopped working after two days."}],
        }

        validator.CUSTOMER_SAFETY_CACHE.clear()
        first = validator.customer_safety_context(data_pack)
        second = validator.customer_safety_context(data_pack)

        self.assertIs(first, second)
        self.assertIn("src_001", first["technical_values"])
        self.assertTrue(any("stopped working" in value for value in first["raw_english_values"]))

    def test_raw_english_scan_ignores_non_visible_html_structure(self):
        data_pack = {
            "products": [{"title": "BesLowe Outdoor Wall Light Fixture"}],
            "reviews": [],
            "keywords": [],
        }

        validator.validate_no_raw_english_leaks(
            "output/html_reports/report.html",
            '<div class="light outdoor wall report-shell"><span>中文报告正文</span></div>',
            data_pack,
            "HTML",
        )

    def test_allowed_keyword_bigrams_can_form_category_phrase(self):
        allowed = "outdoor wall | wall lantern"

        self.assertTrue(validator.is_allowed_english_fragment("outdoor wall lantern", allowed))
        self.assertTrue(validator.is_allowed_english_fragment("wall lantern", allowed))
        self.assertFalse(validator.is_allowed_english_fragment("privacy policy confusing", allowed))

    def test_visible_ngrams_do_not_cross_cjk_or_punctuation_boundaries(self):
        ngrams = validator.visible_word_ngrams("备选方向：picture light、outdoor wall lantern")

        self.assertIn("outdoor wall lantern", ngrams)
        self.assertNotIn("light outdoor wall", ngrams)

    def test_visible_ngrams_do_not_cross_html_tag_boundaries(self):
        ngrams = validator.visible_word_ngrams("<td>plug into wall</td><td>night light</td>")

        self.assertIn("plug into wall", ngrams)
        self.assertNotIn("into wall night", ngrams)

    def run_validator(self, report_dir):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--dir", str(report_dir)],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_valid_three_report_bundle_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)

            result = self.run_validator(report_dir)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("validate_ok", result.stdout)

    def test_rejects_passing_supply_readiness_with_failed_supply_html_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            html_path = report_dir / "output" / "html_reports" / "market-depth-report.html"
            write_text(
                html_path,
                html_path.read_text(encoding="utf-8")
                + """
<section id="supply-chain-regression">
  <div class="supply-card">
    <div class="supply-label">供应链状态</div>
    <div class="supply-value">需补采</div>
    <div class="supply-note">当前数据不能进入毛利率测算</div>
  </div>
  <div id="marginChart">毛利率测算未启用 · 1688质量门禁未通过</div>
</section>
""",
            )
            invocation_log_path = report_dir / "analysis" / "child_skill_invocation_log.json"
            invocation_log = json.loads(invocation_log_path.read_text(encoding="utf-8"))
            for entry in invocation_log:
                if entry.get("module") == "child_skills/market-depth-report":
                    entry["output_sha256"] = file_sha256(html_path)
            write_json(invocation_log_path, invocation_log)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("supply chain HTML contradicts passing readiness", result.stderr + result.stdout)

    def test_rejects_normalized_data_pack_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            normalized_path = report_dir / "data" / "normalized" / "normalized_data_pack.json"
            normalized_pack = json.loads(normalized_path.read_text(encoding="utf-8"))
            normalized_pack["quality"]["overall_score"] = 0.99
            write_json(normalized_path, normalized_pack)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("normalized_data_pack.json must match", result.stderr + result.stdout)

    def test_rejects_missing_child_html_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            (report_dir / "output" / "html_reports" / "demand-gap-report.html").unlink()

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("demand-gap-report.html", result.stderr + result.stdout)

    def test_rejects_missing_critic_child_invocation_log_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            log_path = report_dir / "analysis" / "child_skill_invocation_log.json"
            log = json.loads(log_path.read_text(encoding="utf-8"))
            write_json(log_path, [entry for entry in log if entry["module"] != "child_skills/market-research-critic"])

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("exactly one entry per subprocess child", result.stderr + result.stdout)

    def test_rejects_child_invocation_sha_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            log_path = report_dir / "analysis" / "child_skill_invocation_log.json"
            log = json.loads(log_path.read_text(encoding="utf-8"))
            log[0]["output_sha256"] = "0" * 64
            write_json(log_path, log)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("output_sha256 mismatch", result.stderr + result.stdout)

    def test_rejects_child_invocation_returncode_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            log_path = report_dir / "analysis" / "child_skill_invocation_log.json"
            log = json.loads(log_path.read_text(encoding="utf-8"))
            log[1]["returncode"] = 1
            write_json(log_path, log)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("did not exit cleanly", result.stderr + result.stdout)

    def test_rejects_index_without_child_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            html_path = report_dir / "output" / "html_reports" / "report.html"
            write_text(html_path, html_path.read_text(encoding="utf-8").replace("lifecycle-strategy-report.html", "lifecycle.html"))

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("lifecycle-strategy-report.html", result.stderr + result.stdout)

    def test_rejects_bundle_index_with_output_prefixed_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            html_path = report_dir / "output" / "html_reports" / "report.html"
            html_doc = html_path.read_text(encoding="utf-8").replace('href="market-depth-report.html"', 'href="output/market-depth-report.html"')
            write_text(html_path, html_doc)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("same-folder relative links", result.stderr + result.stdout)

    def test_rejects_child_report_missing_required_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            html_path = report_dir / "output" / "html_reports" / "market-depth-report.html"
            write_text(html_path, html_path.read_text(encoding="utf-8").replace("AI生图 Prompt · 可直接使用", "AI生图"))

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("AI生图 Prompt · 可直接使用", result.stderr + result.stdout)

    def test_rejects_market_report_missing_fixed_pricing_or_prompt_slot(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            rel_path = "output/html_reports/market-depth-report.html"
            html_path = report_dir / rel_path
            html_doc = html_path.read_text(encoding="utf-8")
            html_doc = html_doc.replace('<div class="prompt-card"><div class="prompt-number">Prompt 03</div><div class="prompt-scene">场景</div><div class="prompt-text">prompt</div><div class="prompt-note">note</div></div>', "")
            write_text(html_path, html_doc)
            refresh_child_output_sha(report_dir, rel_path)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("fixed template slot mismatch: prompt-card must be exactly 3", result.stderr + result.stdout)

    def test_rejects_lifecycle_report_missing_fixed_ecosystem_grid(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            rel_path = "output/html_reports/lifecycle-strategy-report.html"
            html_path = report_dir / rel_path
            html_doc = html_path.read_text(encoding="utf-8").replace("ecosystem-chart-grid", "ecosystem-chart")
            write_text(html_path, html_doc)
            refresh_child_output_sha(report_dir, rel_path)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("fixed template slot mismatch: ecosystem two-chart grid missing", result.stderr + result.stdout)

    def test_rejects_demand_report_missing_fixed_sentiment_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            rel_path = "output/html_reports/demand-gap-report.html"
            html_path = report_dir / rel_path
            html_doc = html_path.read_text(encoding="utf-8").replace("demand-sentiment-columns", "demand-evidence-columns")
            write_text(html_path, html_doc)
            refresh_child_output_sha(report_dir, rel_path)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("fixed template slot mismatch: sentiment columns missing", result.stderr + result.stdout)

    def test_rejects_demand_report_section_order_regression(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            rel_path = "output/html_reports/demand-gap-report.html"
            html_path = report_dir / rel_path
            html_doc = html_path.read_text(encoding="utf-8")
            html_doc = (
                html_doc.replace('id="target-anchor"', 'id="__target_anchor_tmp__"', 1)
                .replace('id="decision-board"', 'id="target-anchor"', 1)
                .replace('id="__target_anchor_tmp__"', 'id="decision-board"', 1)
            )
            write_text(html_path, html_doc)
            refresh_child_output_sha(report_dir, rel_path)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("fixed slot contract marker order regression", result.stderr + result.stdout)

    def test_rejects_report_missing_fixed_reference_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            rel_path = "output/html_reports/market-depth-report.html"
            html_path = report_dir / rel_path
            html_doc = html_path.read_text(encoding="utf-8").replace("Core Product Concept", "Product Concept")
            write_text(html_path, html_doc)
            refresh_child_output_sha(report_dir, rel_path)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("fixed slot contract missing required text: Core Product Concept", result.stderr + result.stdout)

    def test_rejects_template_class_token_dump_without_real_structure(self):
        canonical = (SKILL_DIR / "assets" / "canonical_templates" / "market-depth-reference.html").read_text(encoding="utf-8")
        classes = " ".join(sorted(validator.html_class_tokens(canonical)))
        ids = "".join(f'<div id="{token}"></div>' for token in sorted(validator.html_id_tokens(canonical)))
        fake_html = f'<!doctype html><html><body><div class="{classes}"></div>{ids}</body></html>'

        with self.assertRaises(validator.ValidationError) as ctx:
            validator.validate_template_dom_class_parity("output/html_reports/market-depth-report.html", fake_html, "market-depth-report-v2")

        self.assertIn("missing canonical template structure", str(ctx.exception))

    def test_rejects_customer_html_leaking_technical_identifiers(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            html_path = report_dir / "output" / "html_reports" / "demand-gap-report.html"
            write_text(
                html_path,
                html_path.read_text(encoding="utf-8")
                + "<p>source_id src_001 Product ID product_id raw_path provider tool B0TEST1234 data/raw/file.json 来源</p>",
            )

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("customer HTML leaks technical identifier", result.stderr + result.stdout)

    def test_rejects_customer_html_leaking_collector_script_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            html_path = report_dir / "output" / "html_reports" / "report.html"
            write_text(
                html_path,
                html_path.read_text(encoding="utf-8") + "<p>运行 collect_市场数据_keywords.py 补到 1200 条采集目标。</p>",
            )

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("customer HTML leaks technical identifier", result.stderr + result.stdout)

    def test_rejects_customer_html_placeholder_wording(self):
        for placeholder in ["样本", "待补", "暂无有效数据", "未分层", "清洗数据", "清洗后数据", "清洗后的竞品"]:
            with self.subTest(placeholder=placeholder):
                with tempfile.TemporaryDirectory() as tmp:
                    report_dir = Path(tmp)
                    make_valid_report(report_dir)
                    html_path = report_dir / "output" / "html_reports" / "lifecycle-strategy-report.html"
                    write_text(html_path, html_path.read_text(encoding="utf-8") + f"<section>{placeholder}</section>")

                    result = self.run_validator(report_dir)

                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("placeholder or non-final data wording", result.stderr + result.stdout)

    def test_rejects_customer_html_with_reference_competitor_redaction_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            html_path = report_dir / "output" / "html_reports" / "lifecycle-strategy-report.html"
            write_text(html_path, html_path.read_text(encoding="utf-8") + "<p>参考竞品 MCGOR 参考竞品</p>")

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("customer HTML leaks technical identifier", result.stderr + result.stdout)

    def test_rejects_customer_html_visible_internal_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            html_path = report_dir / "output" / "html_reports" / "report.html"
            write_text(
                html_path,
                html_path.read_text(encoding="utf-8")
                + "<section><p>collection_in_progress</p><p>score 0.62</p><p>success</p><p>warning</p></section>",
            )

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("visible internal status", result.stderr + result.stdout)

    def test_rejects_customer_html_empty_kpi_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            html_path = report_dir / "output" / "html_reports" / "report.html"
            write_text(
                html_path,
                html_path.read_text(encoding="utf-8")
                + '<article class="kpi-card"><div class="kpi-label">Top100 估算月销量</div><div class="kpi-value">-</div></article>',
            )

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("empty customer KPI", result.stderr + result.stdout)

    def test_rejects_customer_html_without_analysis_terms(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            html_path = report_dir / "output" / "report.html"
            write_text(html_path, html_path.read_text(encoding="utf-8").replace("证据强度", "证据"))

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("证据强度", result.stderr + result.stdout)

    def test_rejects_raw_english_review_copied_into_customer_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            html_path = report_dir / "output" / "html_reports" / "demand-gap-report.html"
            write_text(
                html_path,
                html_path.read_text(encoding="utf-8")
                + "<p>This toy stopped working after two days and the privacy policy is confusing.</p>",
            )

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("raw English review", result.stderr + result.stdout)

    def test_rejects_raw_english_review_fragment_in_customer_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            html_path = report_dir / "output" / "html_reports" / "demand-gap-report.html"
            write_text(html_path, html_path.read_text(encoding="utf-8") + "<p>stopped working after two days</p>")

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("raw English review/client text fragment", result.stderr + result.stdout)

    def test_rejects_html_escaped_raw_english_review_fragment(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            html_path = report_dir / "output" / "html_reports" / "demand-gap-report.html"
            write_text(html_path, html_path.read_text(encoding="utf-8") + "<p>privacy&nbsp;policy&nbsp;is&nbsp;confusing</p>")

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("raw English review/client text fragment", result.stderr + result.stdout)

    def test_rejects_raw_english_product_title_copied_into_customer_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            html_path = report_dir / "output" / "report.html"
            html = html_path.read_text(encoding="utf-8").replace("</main>", "<p>AI Plush Toy</p></main>")
            write_text(html_path, html)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("raw English review/client text fragment", result.stderr + result.stdout)

    def test_rejects_duplicate_product_key_after_normalization(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            data_path = report_dir / "data" / "data_pack.json"
            data_pack = json.loads(data_path.read_text(encoding="utf-8"))
            data_pack["products"].append(dict(data_pack["products"][0]))
            data_pack["normalization"]["before_counts"]["products"] = len(data_pack["products"])
            data_pack["normalization"]["after_counts"]["products"] = len(data_pack["products"])
            data_pack["normalization"]["removed_counts"]["products"] = 0
            data_pack["cleaning_summary"] = data_pack["normalization"]
            write_json(data_path, data_pack)
            write_json(report_dir / "data" / "normalized" / "normalized_data_pack.json", data_pack)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Duplicate products dedupe key", result.stderr + result.stdout)

    def test_rejects_customer_visible_json_leaking_technical_identifiers(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            asset_path = report_dir / "output" / "html_reports" / "assets" / "report-data.json"
            payload = json.loads(asset_path.read_text(encoding="utf-8"))
            payload["leak"] = "src_评论_under"
            write_json(asset_path, payload)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("customer asset leaks technical identifier", result.stderr + result.stdout)

    def test_rejects_customer_visible_json_leaking_collector_script_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            asset_path = report_dir / "output" / "html_reports" / "assets" / "report-data.json"
            payload = json.loads(asset_path.read_text(encoding="utf-8"))
            payload.setdefault("report_readiness_view", {})["next_step"] = "运行 collect_市场数据_keywords.py 补到 1200 条采集目标。"
            write_json(asset_path, payload)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("customer asset leaks technical identifier", result.stderr + result.stdout)

    def test_rejects_low_sample_high_score_strong_go(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            data_pack_path = report_dir / "data" / "data_pack.json"
            data_pack = json.loads(data_pack_path.read_text(encoding="utf-8"))
            data_pack["quality"]["overall_score"] = 0.9
            data_pack["quality"]["grade"] = "A"
            data_pack["normalization"]["cross_validated_counts"] = {"keywords": 1000, "products": 0, "reviews": 0}
            data_pack["cleaning_summary"] = data_pack["normalization"]
            write_json(data_pack_path, data_pack)
            write_json(report_dir / "data" / "normalized" / "normalized_data_pack.json", data_pack)
            delivery_path = report_dir / "output" / "delivery_result.json"
            delivery = json.loads(delivery_path.read_text(encoding="utf-8"))
            delivery["decision"] = "Go"
            write_json(delivery_path, delivery)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("review sample depth", result.stderr + result.stdout)

    def test_rejects_keyword_samples_below_1000(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            data_pack_path = report_dir / "data" / "data_pack.json"
            data_pack = json.loads(data_pack_path.read_text(encoding="utf-8"))
            data_pack["keywords"] = data_pack["keywords"][:999]
            data_pack["normalization"]["after_counts"]["keywords"] = 999
            write_json(data_pack_path, data_pack)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("at least 1000", result.stderr + result.stdout)

    def test_rejects_amazon_enrichment_gap_without_retry_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            data_pack_path = report_dir / "data" / "data_pack.json"
            data_pack = json.loads(data_pack_path.read_text(encoding="utf-8"))
            data_pack["data_gaps"] = [
                {
                    "type": "amazon_product_enrichment_empty_dimensions",
                    "module": "amazon_product_enrichment",
                    "gap": "Sorftime Amazon ASIN enrichment tools returned no rows for: product_detail.",
                }
            ]
            data_pack["normalization"]["after_counts"]["data_gaps"] = 1
            data_pack["cleaning_summary"] = data_pack["normalization"]
            write_json(data_pack_path, data_pack)
            write_json(report_dir / "data" / "normalized" / "normalized_data_pack.json", data_pack)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("amazon product enrichment gap missing retry_evidence", result.stderr + result.stdout)

    def test_rejects_complete_delivery_when_data_readiness_is_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            data_pack_path = report_dir / "data" / "data_pack.json"
            data_pack = json.loads(data_pack_path.read_text(encoding="utf-8"))
            data_pack["products"] = []
            data_pack["normalization"]["after_counts"]["products"] = 0
            data_pack["normalization"]["removed_counts"]["products"] = data_pack["normalization"]["before_counts"]["products"]
            data_pack["cleaning_summary"] = data_pack["normalization"]
            write_json(data_pack_path, data_pack)
            write_json(report_dir / "data" / "normalized" / "normalized_data_pack.json", data_pack)
            write_json(
                report_dir / "data" / "normalized" / "data_readiness_report.json",
                {
                    "acceptance_ready": False,
                    "sample_class": "non_acceptance_sample",
                    "blocking_gaps": [{"module": "product_sample_depth", "current": 0, "required": 1}],
                },
            )

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("acceptance_ready or partial_report_ready", result.stderr + result.stdout)

    def test_data_readiness_allows_blocked_diagnostic_delivery(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            readiness = {
                "acceptance_ready": False,
                "partial_report_ready": False,
                "sample_class": "non_acceptance_sample",
                "blocking_gaps": [{"module": "keyword_sample_depth", "reason": "关键词不足"}],
            }
            write_json(report_dir / "data" / "normalized" / "data_readiness_report.json", readiness)

            with patch.object(validator, "assess_data_readiness", return_value=readiness):
                validator.validate_data_readiness(report_dir, {"status": "blocked", "decision": "No-Go"})

    def test_delivery_allows_blocked_diagnostic_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            readiness = {
                "acceptance_ready": False,
                "partial_report_ready": False,
                "supply_conclusion_blocked": False,
                "sample_class": "non_acceptance_sample",
                "blocking_gaps": [{"module": "keyword_sample_depth", "reason": "关键词不足"}],
                "warnings": [],
                "counts": {"keywords": 50},
                "supplier_quote_gate": {"passed": True},
                "supplier_quality_gate": {"passed": True},
                "competitor_gate": {"passed": False},
                "segment_gate": {"passed": False},
            }
            write_json(report_dir / "data" / "normalized" / "data_readiness_report.json", readiness)
            delivery_path = report_dir / "output" / "delivery_result.json"
            delivery = json.loads(delivery_path.read_text(encoding="utf-8"))
            delivery["status"] = "blocked"
            delivery["decision"] = "No-Go"
            delivery["data_readiness"] = {
                "path": "data/normalized/data_readiness_report.json",
                **validator.readiness_summary_for_contract(readiness),
            }
            delivery["critic_review"]["pass"] = False
            delivery["critic_review"]["score"] = 0
            for entry in delivery["child_skill_invocations"].values():
                entry["status"] = "diagnostic_template"
                entry["dispatch_mode"] = "main_renderer_diagnostic"
                entry["invocation_log"] = None
            write_json(delivery_path, delivery)
            asset_path = report_dir / "output" / "html_reports" / "assets" / "report-data.json"
            site_data = json.loads(asset_path.read_text(encoding="utf-8"))
            site_data["readiness"] = validator.readiness_summary_for_contract(readiness)
            write_json(asset_path, site_data)

            with patch.object(validator, "assess_data_readiness", return_value=readiness):
                validator.validate_delivery(report_dir)

    def test_rejects_forged_delivery_readiness_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            delivery_path = report_dir / "output" / "delivery_result.json"
            delivery = json.loads(delivery_path.read_text(encoding="utf-8"))
            delivery["data_readiness"]["counts"]["keywords"] = 42
            write_json(delivery_path, delivery)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("delivery_result.json data_readiness.counts mismatch", result.stderr + result.stdout)

    def test_rejects_delivery_missing_competitor_table_asin_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            delivery_path = report_dir / "output" / "delivery_result.json"
            delivery = json.loads(delivery_path.read_text(encoding="utf-8"))
            delivery["asin_display_scope"] = ["benchmark_sniper", "profit_model"]
            write_json(delivery_path, delivery)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("asin_display_scope must include competitor_table", result.stderr + result.stdout)

    def test_rejects_delivery_missing_demand_target_anchor_asin_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            delivery_path = report_dir / "output" / "delivery_result.json"
            delivery = json.loads(delivery_path.read_text(encoding="utf-8"))
            delivery["asin_display_scope"] = ["competitor_table", "benchmark_sniper", "profit_model"]
            write_json(delivery_path, delivery)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("asin_display_scope must include demand_target_anchor", result.stderr + result.stdout)

    def test_rejects_forged_report_data_readiness_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            asset_path = report_dir / "output" / "html_reports" / "assets" / "report-data.json"
            payload = json.loads(asset_path.read_text(encoding="utf-8"))
            payload["readiness"]["sample_class"] = "non_acceptance_sample"
            write_json(asset_path, payload)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("report-data.json readiness.sample_class mismatch", result.stderr + result.stdout)

    def test_entity_without_source_id_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            data_pack_path = report_dir / "data" / "data_pack.json"
            data_pack = json.loads(data_pack_path.read_text(encoding="utf-8"))
            del data_pack["products"][0]["source_id"]
            write_json(data_pack_path, data_pack)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("source_id", result.stderr + result.stdout)

    def test_missing_delivery_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            (report_dir / "output" / "delivery_result.json").unlink()

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("delivery_result.json", result.stderr + result.stdout)

    def test_markdown_wrapped_child_html_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            write_text(
                report_dir / "output" / "html_reports" / "market-depth-report.html",
                """<!doctype html><html><body><pre># Report

| 关键词 | 月销量 |
|---|---:|
| test | 10 |

## Go / Watch / No-Go
估算月销量（Sorftime）来自 src_001。
</pre></body></html>""",
            )

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("market-depth-report.html", result.stderr + result.stdout)

    def test_lifecycle_strategy_requires_semantic_strategy_type_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            lifecycle_path = report_dir / "analysis" / "lifecycle_strategy.json"
            payload = json.loads(lifecycle_path.read_text(encoding="utf-8"))
            payload["sku_candidate_pool"][0].pop("strategy_type_key", None)
            lifecycle_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("strategy_type_key", result.stderr + result.stdout)

    def test_lifecycle_strategy_rejects_raw_letter_type_as_customer_strategy_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            lifecycle_path = report_dir / "analysis" / "lifecycle_strategy.json"
            payload = json.loads(lifecycle_path.read_text(encoding="utf-8"))
            payload["sku_candidate_pool"][0]["strategy_type_key"] = "A"
            lifecycle_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("strategy_type_key", result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
