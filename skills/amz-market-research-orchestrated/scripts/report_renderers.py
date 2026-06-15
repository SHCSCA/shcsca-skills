#!/usr/bin/env python3
"""Assemble customer HTML report documents from section render callbacks."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable


RenderFns = dict[str, Callable[..., Any]]


def call(fns: RenderFns, name: str, *args: Any, **kwargs: Any) -> Any:
    return fns[name](*args, **kwargs)


def customer_report_object(data_pack: dict[str, Any], analysis_plan: dict[str, Any], fallback: Any, fns: RenderFns) -> Any:
    profile = analysis_plan.get("report_label_profile") or data_pack.get("report_label_profile") or {}
    product_labels = profile.get("product_title_labels") if isinstance(profile, dict) else {}
    if not isinstance(product_labels, dict):
        product_labels = {}
    research_object = data_pack.get("research_object") or {}
    target_value = ""
    if isinstance(research_object, dict):
        target_value = str(research_object.get("value") or "").upper()
    if target_value and product_labels.get(target_value):
        return product_labels[target_value]
    products = call(fns, "effective_products", data_pack)
    for product in products:
        asin = str(product.get("asin") or "").upper()
        if target_value and asin == target_value:
            label = product_labels.get(asin) or call(fns, "customer_product_position", product)
            if label:
                return label
    if products:
        first_product = products[0]
        asin = str(first_product.get("asin") or "").upper()
        label = product_labels.get(asin) or call(fns, "customer_product_position", first_product)
        if label:
            return label
    return fallback


def build_report_documents(
    data_pack: dict[str, Any],
    analysis_plan: dict[str, Any],
    market_size: dict[str, Any],
    voc: dict[str, Any],
    opportunity: dict[str, Any],
    profitability: dict[str, Any],
    lifecycle: dict[str, Any],
    demand_gap: dict[str, Any],
    delivery: dict[str, Any],
    decision: str,
    fns: RenderFns,
) -> tuple[dict[str, str], str]:
    brief = data_pack.get("brief") or {}
    research_object = brief.get("research_object") or data_pack.get("research_object") or {}
    raw_object_value = call(
        fns,
        "first",
        research_object.get("value") if isinstance(research_object, dict) else research_object,
        data_pack.get("task_id"),
        default="Amazon Market",
    )
    object_value = customer_report_object(data_pack, analysis_plan, raw_object_value, fns)
    quality = data_pack.get("quality") or {}
    categories = data_pack.get("categories") or []
    category = categories[0] if categories else {}
    keyword_pool = [kw for kw in call(fns, "effective_keywords", data_pack) if kw.get("monthly_search_volume")]
    core_keyword_pool = [
        kw
        for kw in keyword_pool
        if kw.get("source_type") != "product_traffic_terms"
        and (kw.get("is_core_relevant") or kw.get("relevance_cn") == "高相关")
    ]
    keywords = sorted(core_keyword_pool or keyword_pool, key=lambda kw: call(fns, "as_float", kw.get("monthly_search_volume"), 0), reverse=True)
    products = call(
        fns,
        "relevant_products",
        sorted(call(fns, "effective_products", data_pack), key=lambda product: call(fns, "as_float", call(fns, "product_sales", product), 0), reverse=True),
    )
    competitor_table, competitor_cards, competitor_products = call(fns, "render_competitors", data_pack)
    fallback_source = call(fns, "primary_source_id", data_pack)
    report_date = datetime.now().strftime("%Y-%m-%d")
    target_market = call(
        fns,
        "first",
        (brief.get("market_scope") or {}).get("amazon") if isinstance(brief.get("market_scope"), dict) else None,
        "Amazon US",
    )
    data_depth = call(
        fns,
        "first",
        brief.get("data_depth"),
        (brief.get("data_scope") or {}).get("depth") if isinstance(brief.get("data_scope"), dict) else None,
        "标准版",
    )
    report_title = f"{object_value} · 三合一市场研究报告"
    readiness_view = data_pack.get("report_readiness_view") if isinstance(data_pack.get("report_readiness_view"), dict) else {}
    display_decision = str(readiness_view.get("decision") or decision or "Watch")
    confidence_label = str(readiness_view.get("evidence_strength") or call(fns, "confidence_level", data_pack, analysis_plan))

    market_kpis = [
        call(fns, "kpi_card", "核心判断", display_decision, readiness_view.get("delivery_state") or "Go / Watch / No-Go", "warning"),
        call(fns, "kpi_card", "Top100 估算月销量", call(fns, "num", category.get("top100_estimated_monthly_units")), "类目代理指标", "success"),
        call(
            fns,
            "kpi_card",
            "最大关键词月搜索",
            call(fns, "num", keywords[0].get("monthly_search_volume") if keywords else None),
            keywords[0].get("keyword") if keywords else "keyword gap",
        ),
        call(fns, "kpi_card", "相关竞品池", call(fns, "num", len(products)), "过滤泛词噪声后", ""),
    ]

    common = {
        "{{REPORT_TITLE}}": report_title,
        "{{REPORT_OBJECT}}": call(fns, "esc", object_value),
        "{{REPORT_DATE}}": report_date,
        "{{TARGET_MARKET}}": target_market,
        "{{DATA_DEPTH}}": data_depth,
        "{{DECISION}}": display_decision,
        "{{PRIMARY_SOURCE_ID}}": fallback_source,
        "{{CONFIDENCE_LEVEL}}": confidence_label,
        "{{CLIENT_TRUST_STRIP}}": call(fns, "client_trust_strip", data_pack, analysis_plan, display_decision),
    }
    market_replacements = {
        **common,
        "{{OBJECT_VALUE}}": object_value,
        "{{MARKET_REPORT_TITLE}}": f"{object_value} · 市场深度调研报告",
        "{{REPORT_SUBTITLE}}": "客户版 AI 深度分析 · 大盘判断、需求结构、竞品格局、内容信号、供应链判断与行动建议",
        "{{KPI_CARDS}}": "".join(market_kpis),
        "{{EXECUTIVE_INSIGHT_WITH_SOURCE_IDS}}": f"核心判断：{call(fns, 'esc', display_decision)}；置信等级：{call(fns, 'esc', confidence_label)}。当前有效数据覆盖 {len(call(fns, 'effective_products', data_pack))} 个竞品、{len(call(fns, 'effective_keywords', data_pack))} 个关键词、{len(call(fns, 'effective_reviews', data_pack))} 条评论、{len(data_pack.get('tiktok_videos', []))} 条内容视频、{len(call(fns, 'effective_suppliers', data_pack))} 条供应端记录。报告只呈现可执行分析，内部审计链路保留在 Markdown 与 JSON 文件中。",
        "{{MARKET_DASHBOARD}}": call(fns, "render_market", data_pack, market_size),
        "{{COSMO_ALEXA_TAGS}}": call(fns, "render_cosmo_alexa_tags", data_pack, analysis_plan),
        "{{KEYWORD_TABLE_AND_INTENT_CARDS}}": call(fns, "render_keywords", data_pack),
        "{{COMPETITOR_TABLE}}": competitor_table,
        "{{COMPETITOR_SEGMENT_CARDS}}": competitor_cards,
        "{{COMPETITOR_DEEP_DIVES}}": call(fns, "render_product_deep_dives", competitor_products, call(fns, "effective_keywords", data_pack)),
        "{{VOC_CARDS_AND_TABLE}}": call(fns, "render_voc", data_pack, voc),
        "{{TIKTOK_VALIDATION}}": call(fns, "render_tiktok", data_pack),
        "{{SUPPLIER_TABLE_AND_COST_THRESHOLDS}}": call(fns, "render_supply", data_pack, profitability),
        "{{WEB_RISK_SUPPLEMENT}}": call(fns, "render_web_risk", data_pack),
        "{{CLIENT_ACTION_SUMMARY}}": call(fns, "render_market_conclusion", data_pack, analysis_plan, display_decision, object_value),
        "{{PRODUCT_DEFINITION}}": call(fns, "render_opportunities", opportunity),
        "{{VISUAL_DIRECTION}}": call(fns, "render_visual_direction", opportunity),
        "{{OPPORTUNITY_CARDS}}": call(fns, "render_opportunities", opportunity),
        "{{DECISION_ROADMAP}}": call(fns, "render_decision", {**delivery, "decision": display_decision}),
        "{{FULL_DATA_APPENDIX}}": call(fns, "render_full_appendix", data_pack, analysis_plan),
        "{{LINEAGE_TABLE}}": call(fns, "render_lineage", data_pack),
        "{{REPORT_FOOTER}}": f"<span>{call(fns, 'esc', object_value)} 市场深度调研报告 · 数据覆盖：Amazon US · 1688 · 已验证市场证据</span><span>Confidential · Client Use Only</span>",
    }
    skus = call(fns, "lifecycle_skus", data_pack, lifecycle, fallback_source)
    lifecycle_replacements = {
        **common,
        "{{LIFECYCLE_REPORT_TITLE}}": f"{object_value} · 产品全生命周期拓品战略报告",
        "{{STRATEGY_DASHBOARD}}": call(fns, "render_strategy_dashboard", data_pack, lifecycle, fallback_source),
        "{{USER_PERSONAS}}": call(fns, "render_personas", data_pack, lifecycle, fallback_source),
        "{{LIFECYCLE_JOURNEY}}": call(fns, "render_lifecycle_journey", data_pack, fallback_source),
        "{{FOUR_DIMENSION_ECOSYSTEM}}": call(fns, "render_ecosystem", data_pack, skus, fallback_source),
        "{{SKU_EXECUTION_TABLE}}": call(fns, "render_sku_execution_table", skus, fallback_source),
        "{{BUNDLE_STRATEGY}}": call(fns, "render_bundle_strategy", skus, fallback_source),
        "{{IMPLEMENTATION_ROADMAP}}": call(fns, "render_lifecycle_roadmap", skus, fallback_source),
        "{{RISK_MATRIX}}": call(fns, "render_lifecycle_risks", fallback_source),
        "{{MARKET_INTELLIGENCE}}": call(fns, "render_lifecycle_market_intel", data_pack, analysis_plan, fallback_source),
        "{{LIFECYCLE_LINEAGE}}": call(fns, "render_lineage", data_pack),
        "{{REPORT_FOOTER}}": f"{call(fns, 'esc', object_value)} · 产品全生命周期拓品战略报告 · Client Use Only",
    }
    demand_anchor_product = products[0] if products else {}
    demand_anchor_value = call(
        fns,
        "first",
        demand_anchor_product.get("asin") if isinstance(demand_anchor_product, dict) else None,
        call(fns, "first", demand_anchor_product.get("title_cn") if isinstance(demand_anchor_product, dict) else None, default=None),
        object_value,
    )
    demand_anchor_asin = demand_anchor_product.get("asin") if isinstance(demand_anchor_product, dict) else None
    if demand_anchor_asin:
        target_anchor_title = (
            "目标ASIN锚点（"
            f"<span class=\"asin-token\" data-allow-asin=\"demand-target-anchor\">{call(fns, 'esc', demand_anchor_asin)}</span>"
            "）"
        )
    else:
        target_anchor_title = f"目标ASIN锚点（{call(fns, 'esc', demand_anchor_value)}）"
    demand_replacements = {
        **common,
        "{{DEMAND_REPORT_TITLE}}": f"{object_value} · 用户心智断层与需求机会报告",
        "{{TARGET_ANCHOR_TITLE}}": target_anchor_title,
        "{{TARGET_ANCHOR}}": call(fns, "render_target_anchor", data_pack, object_value, fallback_source),
        "{{DECISION_BOARD}}": call(fns, "render_decision_board", data_pack, demand_gap, display_decision, fallback_source),
        "{{APPEALS_MAP}}": call(fns, "render_appeals_map", data_pack, fallback_source),
        "{{GAP_ANALYSIS}}": call(fns, "render_gap_analysis", data_pack, fallback_source),
        "{{KANO_JTBD_MATRIX}}": call(fns, "render_kano_jtbd", demand_gap, fallback_source),
        "{{VOICE_THEATER}}": call(fns, "render_voice_theater", data_pack, fallback_source),
        "{{PRIORITY_TABLE}}": call(fns, "render_priority_table", data_pack, demand_gap, fallback_source),
        "{{DEMAND_LINEAGE}}": call(fns, "render_lineage", data_pack),
        "{{REPORT_FOOTER}}": f"{call(fns, 'esc', object_value)} · 用户心智断层与需求机会报告 · Client Use Only",
    }
    index_replacements = {
        **common,
        "{{INDEX_CARDS}}": call(fns, "render_index_cards", str(object_value), display_decision, data_pack),
        "{{DATA_COVERAGE}}": call(fns, "render_client_data_coverage", data_pack, analysis_plan, display_decision),
        "{{DATA_GAPS}}": call(fns, "render_data_gaps", data_pack, analysis_plan),
        "{{REPORT_FOOTER}}": f"{call(fns, 'esc', object_value)} · 三合一市场研究报告 · Client Use Only",
    }
    compat_index_replacements = {
        **index_replacements,
        "{{INDEX_CARDS}}": call(fns, "render_index_cards", str(object_value), display_decision, data_pack, link_prefix="html_reports"),
    }

    market_shell = call(fns, "render_legacy_child_template", "market_depth", market_replacements)
    lifecycle_shell = call(fns, "render_legacy_child_template", "lifecycle_strategy", lifecycle_replacements)
    demand_shell = call(fns, "render_legacy_child_template", "demand_gap", demand_replacements)

    rendered_docs = {
        "index": call(fns, "attach_site_chrome", call(fns, "render_template", "index", index_replacements)),
        "market_depth": call(fns, "attach_site_chrome", market_shell),
        "lifecycle_strategy": call(fns, "attach_site_chrome", lifecycle_shell),
        "demand_gap": call(fns, "attach_site_chrome", demand_shell),
    }
    compat_index_html = call(
        fns,
        "attach_site_chrome",
        call(fns, "render_template", "index", compat_index_replacements),
        "html_reports/",
    )
    return rendered_docs, compat_index_html
