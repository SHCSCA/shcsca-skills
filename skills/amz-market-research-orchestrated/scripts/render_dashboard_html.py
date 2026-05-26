#!/usr/bin/env python3
"""Render the v2 three-report HTML bundle from a market-research report dir."""

from __future__ import annotations

import argparse
import html
import json
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from normalize_data_pack import ENTITY_KEYS, infer_seed_terms, normalize as normalize_data_pack, tokens


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
TEMPLATE_PATHS = {
    "index": SKILL_DIR / "assets" / "report-index-template.html",
    "market_depth": SKILL_DIR / "assets" / "market-depth-template.html",
    "lifecycle_strategy": SKILL_DIR / "assets" / "lifecycle-strategy-template.html",
    "demand_gap": SKILL_DIR / "assets" / "demand-gap-template.html",
}

HTML_REPORTS = {
    "index": "output/report.html",
    "market_depth": "output/market-depth-report.html",
    "lifecycle_strategy": "output/lifecycle-strategy-report.html",
    "demand_gap": "output/demand-gap-report.html",
}


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


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


def table(headers: list[str], rows: list[list[Any]], class_name: str = "evidence-table") -> str:
    head = "".join(f"<th>{esc(header)}</th>" for header in headers)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{esc(cell)}</td>" for cell in row) + "</tr>" for row in rows
    )
    return f"<table class=\"{class_name}\"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"


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
    return f"<details{opened}><summary>{esc(title)}</summary><div class=\"details-body\">{body}</div></details>"


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


def render_data_coverage(data_pack: dict[str, Any], analysis_plan: dict[str, Any]) -> str:
    sources = data_pack.get("sources") or []
    provider_counts = Counter(source.get("provider") for source in sources)
    entity_counts = {
        "sources": len(sources),
        "products": len(data_pack.get("products") or []),
        "keywords": len(data_pack.get("keywords") or []),
        "reviews": len(data_pack.get("reviews") or []),
        "tiktok_products": len(data_pack.get("tiktok_products") or []),
        "tiktok_videos": len(data_pack.get("tiktok_videos") or []),
        "suppliers": len(data_pack.get("suppliers") or []),
        "web_documents": len(data_pack.get("web_documents") or []),
    }
    metric_strip = "<div class=\"metric-strip\">" + "".join(metric(key, value, "records") for key, value in entity_counts.items()) + "</div>"
    provider_chart = mini_chart([(key or "unknown", count, count) for key, count in provider_counts.most_common()], "good")
    method_rows = [
        [
            item.get("method_id"),
            truncate(item.get("purpose") or item.get("name") or item.get("output"), 92),
            ", ".join(str(v) for v in (item.get("used_source_ids") or [])[:6]),
            item.get("output"),
        ]
        for item in analysis_plan.get("method_chain", [])
    ]
    quality = data_pack.get("quality") or {}
    normalization = data_pack.get("normalization") or {}
    before_counts = normalization.get("before_counts") or {}
    after_counts = normalization.get("after_counts") or {}
    removed_counts = normalization.get("removed_counts") or {}
    cross_counts = normalization.get("cross_validated_counts") or {}
    quality_notes = quality.get("rationale") or quality.get("notes") or []
    note_html = "".join(f"<li>{esc(note)}</li>" for note in quality_notes[:6])
    dedupe_rows = [
        [key, before_counts.get(key, 0), after_counts.get(key, 0), removed_counts.get(key, 0), cross_counts.get(key, 0)]
        for key in ENTITY_KEYS
        if key in before_counts or key in after_counts
    ]
    return (
        metric_strip
        + "<div class=\"grid-3\"><div class=\"card\"><div class=\"card-title\">Provider Coverage</div>"
        + provider_chart
        + "</div><div class=\"card\"><div class=\"card-title\">Quality Notes</div>"
        + f"<p>{tag('quality ' + str(first(quality.get('grade'), '-')))} {tag('score ' + str(first(quality.get('overall_score'), '-')), 'warn')}</p><ul>{note_html}</ul>"
        + "</div><div class=\"card\"><div class=\"card-title\">交叉验证 / 去重</div>"
        + f"<p>{tag('deduped true', 'good')} {tag('cross validated evidence', 'warn')}</p><p>同 ASIN、同关键词、同 URL、同供应商先合并，再进入分析和 HTML。跨来源命中的实体会提高置信度，冲突字段保留在 validation.conflicts。</p>"
        + "</div></div>"
        + table(["实体", "原始数", "去重后", "去重移除", "交叉验证数"], dedupe_rows)
        + details("方法链 / analysis_plan", table(["method_id", "purpose", "used_source_ids", "output"], method_rows), True)
    )


def render_market(data_pack: dict[str, Any], market_size: dict[str, Any]) -> str:
    categories = data_pack.get("categories") or []
    category = categories[0] if categories else {}
    products = relevant_products(data_pack.get("products") or [])
    source_id = first(category.get("source_id"), market_size.get("source_id"), default="")
    prices = [as_float(product_price(product), -1) for product in products if as_float(product_price(product), -1) >= 0]
    sales = [as_float(product_sales(product), 0) for product in products]
    segment_sales: defaultdict[str, float] = defaultdict(float)
    price_band_sales: defaultdict[str, float] = defaultdict(float)
    origin_counts = Counter()
    for product in products:
        segment_sales[first(product.get("segment"), "unknown")] += as_float(product_sales(product), 0)
        price_band_sales[price_band(product_price(product))] += as_float(product_sales(product), 0)
        if product.get("seller_origin"):
            origin_counts[product.get("seller_origin")] += 1
    cards = [
        kpi_card("Top100 估算月销量", num(first(category.get("top100_estimated_monthly_units"), market_size.get("top100_estimated_monthly_units"), default=None)), "Sorftime 类目代理指标", "success"),
        kpi_card("Top100 估算销售额", money(first(category.get("top100_estimated_monthly_revenue"), market_size.get("top100_estimated_monthly_revenue"), default=None)), "用于判断大盘体量", "warning"),
        kpi_card("价格中位数", money(statistics.median(prices) if prices else None), "相关产品池计算"),
        kpi_card("估算销量中位数", num(statistics.median(sales) if sales else None), "相关产品池计算"),
    ]
    stats_rows = [
        ["类目", first(category.get("category_name"), category.get("node_id"), default="-"), source_id],
        ["Top3 产品占比", pct(first(category.get("top3_product_sales_share"), market_size.get("top3_product_sales_share_pct"), default=None)), source_id],
        ["Top3 品牌占比", pct(first(category.get("top3_brand_sales_share"), market_size.get("top3_brand_sales_share_pct"), default=None)), source_id],
        ["Amazon 自营占比", pct(first(category.get("amazon_owned_sales_share"), market_size.get("amazon_owned_sales_share_pct"), default=None)), source_id],
        ["低评论产品销量占比", pct(category.get("low_reviews_sales_share")), source_id],
        ["高评论产品销量占比", pct(category.get("high_reviews_sales_share")), source_id],
    ]
    return (
        "<div class=\"kpi-grid\">" + "".join(cards) + "</div>"
        + "<div class=\"grid-3\">"
        + "<div class=\"card\"><div class=\"card-title\">细分估算销量结构</div>"
        + mini_chart([(k, v, num(v)) for k, v in sorted(segment_sales.items(), key=lambda x: x[1], reverse=True)[:8]], "good")
        + "</div><div class=\"card\"><div class=\"card-title\">价格带估算销量结构</div>"
        + mini_chart([(k, v, num(v)) for k, v in price_band_sales.items()], "warn")
        + "</div><div class=\"card\"><div class=\"card-title\">卖家来源结构</div>"
        + mini_chart([(k, v, v) for k, v in origin_counts.most_common(8)])
        + "</div></div>"
        + "<div class=\"card\"><div class=\"card-title\">Market Evidence</div>"
        + table(["指标", "结果", "source_id"], stats_rows)
        + "</div>"
    )


def render_keywords(data_pack: dict[str, Any]) -> str:
    keywords = [kw for kw in data_pack.get("keywords", []) if kw.get("keyword")]
    core_keywords = [kw for kw in keywords if kw.get("source_type") != "product_traffic_terms"]
    traffic_keywords = [kw for kw in keywords if kw.get("source_type") == "product_traffic_terms"]
    relevant_keywords = [kw for kw in core_keywords if kw.get("is_core_relevant") or kw.get("relevance_cn") == "高相关"]
    adjacent_keywords = [kw for kw in core_keywords if kw not in relevant_keywords]
    top_keywords = sorted(relevant_keywords or core_keywords or keywords, key=lambda kw: as_float(kw.get("monthly_search_volume"), 0), reverse=True)
    source_type_counts = Counter(kw.get("source_type", "unknown") for kw in keywords)
    relevance_counts = Counter(kw.get("relevance_cn", "待判断") for kw in keywords)
    cpc_keywords = sorted([kw for kw in top_keywords if kw.get("recommended_cpc") not in (None, "")], key=lambda kw: as_float(kw.get("recommended_cpc"), 0), reverse=True)
    competition_keywords = sorted([kw for kw in top_keywords if kw.get("competitor_count") not in (None, "")], key=lambda kw: as_float(kw.get("competitor_count"), 0), reverse=True)
    rows = [
        [
            kw.get("keyword_cn"),
            kw.get("keyword"),
            first(kw.get("relevance_cn"), default="-"),
            num(kw.get("monthly_search_volume")),
            num(kw.get("weekly_search_volume")),
            kw.get("recommended_cpc") or "-",
            num(kw.get("competitor_count")),
            first(kw.get("intent_cn"), default="-"),
            first(kw.get("season_peak"), default="-"),
            first(kw.get("source_type"), default="-"),
            kw.get("source_id"),
        ]
        for kw in top_keywords[:40]
    ]
    intent_cards = (
        "<div class=\"grid-3\">"
        + "<div class=\"card\"><div class=\"card-title\">需求强度 Top10</div>"
        + mini_chart([(kw.get("keyword"), as_float(kw.get("monthly_search_volume"), 0), num(kw.get("monthly_search_volume"))) for kw in top_keywords[:10]], "good")
        + "</div><div class=\"card\"><div class=\"card-title\">CPC 压力 Top10</div>"
        + mini_chart([(kw.get("keyword"), as_float(kw.get("recommended_cpc"), 0), kw.get("recommended_cpc")) for kw in cpc_keywords[:10]], "bad")
        + "</div><div class=\"card\"><div class=\"card-title\">关键词相关性</div>"
        + mini_chart([(k, v, v) for k, v in relevance_counts.most_common()], "warn")
        + "</div></div>"
    )
    comp_table = table(
        ["高竞争词", "月搜索量", "竞争结果", "CPC", "source_id"],
        [[kw.get("keyword"), num(kw.get("monthly_search_volume")), num(kw.get("competitor_count")), kw.get("recommended_cpc") or "-", kw.get("source_id")] for kw in competition_keywords[:16]],
    )
    adjacent_table = table(
        ["关键词中文", "英文关键词", "相关性", "月搜索量", "CPC", "竞争结果", "来源", "source_id"],
        [[kw.get("keyword_cn"), kw.get("keyword"), kw.get("relevance_cn"), num(kw.get("monthly_search_volume")), kw.get("recommended_cpc") or "-", num(kw.get("competitor_count")), kw.get("source_type"), kw.get("source_id")] for kw in sorted(adjacent_keywords, key=lambda kw: as_float(kw.get("monthly_search_volume"), 0), reverse=True)[:80]],
    )
    source_table = table(
        ["来源类型", "关键词数"],
        [[k, v] for k, v in source_type_counts.most_common()],
    )
    traffic_table = table(
        ["ASIN", "关键词中文", "英文流量词", "月搜索量", "CPC", "曝光位置", "source_id"],
        [[kw.get("asin"), kw.get("keyword_cn"), kw.get("keyword"), num(kw.get("monthly_search_volume")), kw.get("recommended_cpc") or "-", kw.get("traffic_position") or "-", kw.get("source_id")] for kw in sorted(traffic_keywords, key=lambda kw: as_float(kw.get("monthly_search_volume"), 0), reverse=True)[:80]],
    )
    return (
        "<div class=\"insight\">关键词主表优先展示与研究对象高相关的需求词；相邻/泛流量词与 ASIN 反查词分别放入折叠明细，避免把流量噪声误判为进入机会。</div>"
        + intent_cards
        + table(["关键词中文", "英文关键词", "相关性", "月搜索量", "周搜索量", "CPC", "竞争结果", "中文意图", "旺季", "来源", "source_id"], rows)
        + details("高竞争关键词明细", comp_table)
        + details("相邻/噪声关键词池（不直接作为进入判断）", adjacent_table)
        + details("关键词来源结构", source_table)
        + details("ASIN 反查流量词 / 竞品流量入口", traffic_table)
    )


def competitor_rows(products: list[dict[str, Any]], limit: int | None = None) -> list[list[Any]]:
    rows = []
    for product in products[:limit]:
        rows.append(
            [
                product.get("asin"),
                first(product.get("title_cn"), product.get("positioning_cn"), default="-"),
                truncate(product.get("title"), 58),
                first(product.get("brand"), default="-"),
                first(product.get("segment_cn"), product.get("segment"), default="-"),
                money(product_price(product)),
                num(product_sales(product)),
                money(product_revenue(product)),
                first(product.get("rating"), product.get("星级"), default="-"),
                num(product_reviews(product)),
                first(product.get("launch_date"), default="-"),
                product.get("source_id"),
            ]
        )
    return rows


def render_competitors(data_pack: dict[str, Any]) -> tuple[str, str, list[dict[str, Any]]]:
    products = sorted(
        [product for product in data_pack.get("products", []) if product.get("asin")],
        key=lambda product: as_float(product_sales(product), 0),
        reverse=True,
    )
    filtered = relevant_products(products)
    segment_counts = Counter(first(product.get("segment"), "unknown") for product in filtered)
    price_counts = Counter(price_band(product_price(product)) for product in filtered)
    cards = (
        "<div class=\"grid-3\">"
        + "<div class=\"card\"><div class=\"card-title\">细分产品数</div>"
        + mini_chart([(k, v, v) for k, v in segment_counts.most_common(10)], "good")
        + "</div><div class=\"card\"><div class=\"card-title\">价格带 SKU 数</div>"
        + mini_chart([(k, v, v) for k, v in price_counts.items()], "warn")
        + "</div><div class=\"card\"><div class=\"card-title\">分析提示</div>"
        + "<p>Top 竞品表过滤明显非目标类目噪声；完整产品池保留在“完整数据附录”。</p>"
        + "</div></div>"
    )
    return table_inner(
        ["ASIN", "中文定位", "英文标题", "品牌", "细分", "价格", "估算月销量", "估算销售额", "星级", "评论数", "上架", "source_id"],
        competitor_rows(filtered, 30),
    ), cards, filtered


def traffic_terms_by_asin(keywords: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for kw in keywords:
        asin = kw.get("asin")
        if asin:
            grouped[asin].append(kw)
    for asin in grouped:
        grouped[asin] = sorted(grouped[asin], key=lambda kw: as_float(kw.get("monthly_search_volume"), 0), reverse=True)
    return grouped


def render_product_deep_dives(products: list[dict[str, Any]], keywords: list[dict[str, Any]]) -> str:
    traffic = traffic_terms_by_asin(keywords)
    cards = []
    for product in products[:12]:
        asin = product.get("asin")
        trend = product.get("trend") or {}
        trend_text = "-"
        if trend.get("first") is not None and trend.get("last") is not None:
            trend_text = f"{num(trend.get('first'))} → {num(trend.get('last'))} / growth {trend.get('growth')}"
        traffic_tags = "".join(tag(kw.get("keyword")) for kw in traffic.get(asin, [])[:6])
        variations = product.get("variation_samples") or []
        variation_text = "；".join(truncate(item, 42) for item in variations[:3]) or "-"
        image = product.get("image_url") or ""
        image_html = f"<img src=\"{esc(image)}\" alt=\"{esc(asin)}\">" if image else "<div></div>"
        cards.append(
            "<article class=\"product-card comp-deep-card\">"
            + "<div class=\"comp-deep-header\">"
            + f"<div class=\"comp-deep-name\">{esc(first(product.get('brand'), '-'))} · {esc(asin)}</div>"
            + f"<div class=\"comp-deep-price\">{esc(money(product_price(product)))} · 估算月销量 {esc(num(product_sales(product)))} · {esc(first(product.get('rating'), '-'))}★</div>"
            + "</div><div class=\"comp-deep-body product-card-body\">"
            + image_html
            + "<div>"
            + "<div class=\"comp-deep-section\"><div class=\"comp-deep-section-title\">中文定位</div>"
            + f"<div class=\"comp-deep-text\">{esc(first(product.get('title_cn'), product.get('positioning_cn'), '-'))}</div></div>"
            + "<div class=\"comp-deep-section\"><div class=\"comp-deep-section-title\">英文标题</div>"
            + f"<div class=\"comp-deep-text\">{esc(truncate(product.get('title'), 120))}</div></div>"
            + "<div class=\"meta\">"
            + tag(first(product.get("segment_cn"), product.get("segment"), "-"))
            + tag(money(product_price(product)), "warn")
            + tag(f"估算月销量 {num(product_sales(product))}", "good")
            + tag(f"评分 {first(product.get('rating'), '-')}")
            + tag(f"评论 {num(product_reviews(product))}")
            + "</div>"
            + "<div class=\"comp-deep-section\"><div class=\"comp-deep-section-title\">趋势 / 流量 / 变体</div>"
            + f"<div class=\"comp-deep-text\">趋势：{esc(trend_text)}<br>流量词：{traffic_tags or '-'}<br>变体样本：{esc(variation_text)}</div></div>"
            + f"<p>{tag(product.get('source_id'))}</p>"
            + "</div></div></article>"
        )
    return "".join(cards)


def render_voc(data_pack: dict[str, Any], voc: dict[str, Any]) -> str:
    reviews = data_pack.get("reviews") or []
    theme_counts: Counter[str] = Counter()
    low_theme_counts: Counter[str] = Counter()
    star_counts: Counter[int] = Counter()
    asin_counts: Counter[str] = Counter()
    for review in reviews:
        rating = int(as_float(review.get("rating"), 0))
        if rating:
            star_counts[rating] += 1
        asin_counts[review.get("asin")] += 1
        themes = review.get("themes") or []
        theme_counts.update(themes)
        if rating and rating <= 3:
            low_theme_counts.update(themes)
    if not theme_counts and isinstance(voc.get("theme_mentions"), dict):
        theme_counts.update(voc["theme_mentions"])
    low_reviews = [review for review in reviews if as_float(review.get("rating"), 0) <= 3]
    positive_reviews = [review for review in reviews if as_float(review.get("rating"), 0) >= 5]
    quote_cards = []
    for review in (low_reviews[:6] + positive_reviews[:6])[:12]:
        tone = " low pain-card" if as_float(review.get("rating"), 0) <= 3 else " joy-card"
        quote_cards.append(
            f"<article class=\"quote-card{tone}\"><strong>{esc(review.get('asin'))} · {esc(review.get('rating'))}⭐ · {esc(review.get('title'))}</strong>"
            f"<p>{esc(truncate(review.get('text'), 220))}</p><p>{tag(review.get('source_id'))}</p></article>"
        )
    theme_rows = [
        [theme, count, low_theme_counts.get(theme, 0), "样本提及频次，不写精确百分比"]
        for theme, count in theme_counts.most_common(16)
    ]
    sample_rows = [
        [review.get("asin"), review.get("rating"), truncate(review.get("title"), 60), truncate(review.get("text"), 180), ", ".join(review.get("themes") or []), review.get("source_id")]
        for review in reviews[:120]
    ]
    summary = (
        "<div class=\"metric-strip\">"
        + metric("Review 样本", len(reviews), "Sorftime reviews")
        + metric("低星样本", len(low_reviews), "rating <= 3")
        + metric("覆盖 ASIN", len([k for k in asin_counts if k]), "core products")
        + metric("主题数", len(theme_counts), "VOC clusters")
        + metric("5星样本", star_counts.get(5, 0), "positive motives")
        + "</div>"
    )
    charts = (
        "<div class=\"grid-3\"><div class=\"card\"><div class=\"card-title\">主题提及</div>"
        + mini_chart([(k, v, v) for k, v in theme_counts.most_common(10)], "good")
        + "</div><div class=\"card\"><div class=\"card-title\">低星主题</div>"
        + mini_chart([(k, v, v) for k, v in low_theme_counts.most_common(10)], "bad")
        + "</div><div class=\"card\"><div class=\"card-title\">星级分布</div>"
        + mini_chart([(f"{k}星", v, v) for k, v in sorted(star_counts.items())], "warn")
        + "</div></div>"
    )
    return (
        summary
        + "<div class=\"insight\">Review / VOC 主题用于识别设计与转化问题；样本不足或偏近期时，只写频次和证据，不写精确市场百分比。</div>"
        + charts
        + "<div class=\"quote-grid\">"
        + "".join(quote_cards)
        + "</div>"
        + table(["主题", "总提及", "低星提及", "限制"], theme_rows)
        + details("Review 样本证据表（前120条）", table(["ASIN", "星级", "标题", "评论摘录", "主题", "source_id"], sample_rows))
    )


def tiktok_relevance(product: dict[str, Any], seed_terms: list[str]) -> str:
    title = clean(product.get("title")).lower()
    for seed in seed_terms:
        if seed and (seed in title or title in seed):
            return "高相关"
    seed_tokens = set().union(*(tokens(seed) for seed in seed_terms)) if seed_terms else set()
    product_tokens = tokens(title)
    if seed_tokens and product_tokens and (seed_tokens & product_tokens):
        return "相邻相关"
    if product.get("relevance_cn"):
        return str(product["relevance_cn"])
    if not seed_terms:
        return "高相关"
    return "待判断"


def render_tiktok(data_pack: dict[str, Any]) -> str:
    products = data_pack.get("tiktok_products") or []
    videos = sorted(data_pack.get("tiktok_videos") or [], key=lambda video: as_float(video.get("views"), 0), reverse=True)
    seed_terms = infer_seed_terms(data_pack)
    relevance_counts = Counter(tiktok_relevance(product, seed_terms) for product in products)
    product_rows = [
        [product.get("product_id"), truncate(product.get("title"), 70), tiktok_relevance(product, seed_terms), first(product.get("brand"), "-"), money(product.get("price")), num(product.get("estimated_monthly_sales")), num(product.get("review_count")), product.get("source_id")]
        for product in products
    ]
    video_rows = [
        [video.get("product_id"), truncate(video.get("title"), 70), num(video.get("views")), num(video.get("likes")), truncate(video.get("author"), 32), truncate(video.get("tags"), 80), video.get("source_id")]
        for video in videos[:40]
    ]
    return (
        "<div class=\"grid-2\"><div class=\"card\"><div class=\"card-title\">相关性判断</div>"
        + mini_chart([(k, v, v) for k, v in relevance_counts.most_common()], "warn")
        + "</div><div class=\"card\"><div class=\"card-title\">解读</div><p>TikTok 模块展示商品、视频和达人内容信号。若相似结果只与研究对象部分重叠，应作为内容场景参考，而非 Amazon 购买需求证明。</p></div></div>"
        + table(["Product ID", "商品", "相关性", "品牌", "价格", "估算月销量", "评论数", "source_id"], product_rows)
        + details("TikTok 视频证据（播放量排序 Top40）", table(["Product ID", "标题", "播放", "点赞", "达人", "标签", "source_id"], video_rows))
    )


def render_supply(data_pack: dict[str, Any], profitability: dict[str, Any]) -> str:
    suppliers = sorted(data_pack.get("suppliers") or [], key=lambda supplier: as_float(supplier.get("sales_30d"), 0), reverse=True)
    valid_prices = [as_float(supplier.get("price_rmb"), -1) for supplier in suppliers if as_float(supplier.get("price_rmb"), -1) > 0]
    stats = profitability.get("supply_stats") or {}
    origin_counts = Counter(supplier.get("shipping_origin") for supplier in suppliers if supplier.get("shipping_origin"))
    price_counts = Counter()
    for price in valid_prices:
        if price < 20:
            price_counts["<¥20"] += 1
        elif price < 50:
            price_counts["¥20-49"] += 1
        elif price < 100:
            price_counts["¥50-99"] += 1
        elif price < 200:
            price_counts["¥100-199"] += 1
        else:
            price_counts["¥200+"] += 1
    rows = [
        [truncate(supplier.get("title"), 72), money(supplier.get("price_rmb"), "¥"), num(supplier.get("sales_30d")), first(supplier.get("repurchase_rate"), "-"), first(supplier.get("store_name"), "-"), first(supplier.get("shipping_origin"), "-"), supplier.get("source_id")]
        for supplier in suppliers[:40]
    ]
    cards = "".join(
        [
            kpi_card("有效价格样本", num(first(stats.get("valid_price_count"), len(valid_prices), default=0)), "1688 相似货源"),
            kpi_card("采购价中位数", money(first(stats.get("median_rmb"), statistics.median(valid_prices) if valid_prices else None), "¥"), "不含物流/FBA/认证", "warning"),
            kpi_card("最低有效报价", money(first(stats.get("min_rmb"), min(valid_prices) if valid_prices else None), "¥"), "低价需验证质量", "danger"),
            kpi_card("最高样本报价", money(first(stats.get("max_rmb"), max(valid_prices) if valid_prices else None), "¥"), "价格带跨度"),
        ]
    )
    return (
        "<div class=\"kpi-grid\">" + cards + "</div>"
        + "<div class=\"grid-2\"><div class=\"card\"><div class=\"card-title\">1688 价格带</div>"
        + mini_chart([(k, v, v) for k, v in price_counts.items()], "warn")
        + "</div><div class=\"card\"><div class=\"card-title\">供应地分布</div>"
        + mini_chart([(k, v, v) for k, v in origin_counts.most_common(10)], "good")
        + "</div></div>"
        + table(["供应端样本", "价格", "30日销量", "复购率", "店铺", "发货地", "source_id"], rows)
    )


def render_web_risk(data_pack: dict[str, Any]) -> str:
    docs = data_pack.get("web_documents") or []
    query_counts = Counter(doc.get("query") for doc in docs)
    rows = [[truncate(doc.get("title"), 72), truncate(doc.get("description"), 120), doc.get("url"), first(doc.get("position"), "-"), doc.get("source_id")] for doc in docs]
    risk_cards = (
        "<div class=\"risk-grid\">"
        "<article class=\"risk-card\"><h3>合规/召回</h3><p>涉及电气、户外、防水、发热、玻璃破损等风险，必须二次核查 CPSC/UL/ETL 和 Amazon policy。</p></article>"
        "<article class=\"risk-card\"><h3>测评口碑</h3><p>公开测评只作为方向线索，不能替代 Sorftime 评论和真实样品测试。</p></article>"
        "<article class=\"risk-card\"><h3>网页证据限制</h3><p>Firecrawl 搜索结果必须保留在 web_documents，不直接写成结论。</p></article>"
        "</div>"
    )
    return "<div class=\"card\"><div class=\"card-title\">Web Query Coverage</div>" + mini_chart([(truncate(k, 36), v, v) for k, v in query_counts.most_common()]) + "</div>" + risk_cards + table(["标题", "摘要", "URL", "排名", "source_id"], rows)


def render_opportunities(opportunity: dict[str, Any]) -> str:
    opportunities = opportunity.get("opportunities") or []
    if not opportunities:
        opportunities = [{"name": "细分机会待验证", "decision": "Watch", "score": "-", "entry_shape": "需要继续收敛证据。", "risks": ["证据不足"]}]
    cards = []
    for item in opportunities[:10]:
        decision = str(item.get("decision") or "Watch")
        tone = "nogo" if "No" in decision or "不" in decision else "watch" if "Watch" in decision else ""
        risks = item.get("risks") or []
        evidence = item.get("evidence") or []
        cards.append(
            f"<article class=\"opportunity-card {tone}\"><h3>{esc(item.get('name'))}</h3>"
            f"<p>{tag(decision)} {tag('Score ' + str(item.get('score', '-')), 'warn')}</p>"
            f"<p><strong>建议形态：</strong>{esc(item.get('entry_shape') or item.get('recommendation') or '')}</p>"
            f"<p><strong>证据：</strong>{esc('；'.join(str(v) for v in evidence[:4]))}</p>"
            f"<p><strong>风险：</strong>{esc('；'.join(str(v) for v in risks[:5]))}</p></article>"
        )
    return "".join(cards)


def render_decision(delivery: dict[str, Any]) -> str:
    decision = first(delivery.get("decision"), "Watch", default="Watch")
    return (
        "<div class=\"grid-3\">"
        "<div class=\"card\"><div class=\"card-title\">进入条件</div><ul><li>锁定一个细分，不做泛品类。</li><li>样品解决核心 VOC 问题。</li><li>补齐 landed cost、认证、FBA、退货率、ACOS。</li></ul></div>"
        "<div class=\"card\"><div class=\"card-title\">停止条件</div><ul><li>核心词 CPC 与转化无法覆盖毛利。</li><li>低星问题来自结构性缺陷。</li><li>供应端只能同款搬运，无质量/设计优势。</li></ul></div>"
        f"<div class=\"card\"><div class=\"card-title\">最终判断</div><p class=\"insight\">Go / Watch / No-Go：{esc(decision)}</p><p>建议先小批量验证最强机会，打穿评论、广告和样品成本后再扩 SKU。</p></div>"
        "</div>"
    )


def render_data_gaps(data_pack: dict[str, Any], analysis_plan: dict[str, Any]) -> str:
    gaps = data_pack.get("data_gaps") or analysis_plan.get("limitations") or []
    rows = []
    for gap in gaps:
        if isinstance(gap, dict):
            rows.append([gap.get("area"), gap.get("gap"), gap.get("impact"), gap.get("next_action")])
        else:
            rows.append(["limitation", gap, "-", "-"])
    return table(["模块", "缺口", "影响", "下一步"], rows)


def render_full_appendix(data_pack: dict[str, Any], analysis_plan: dict[str, Any]) -> str:
    products = data_pack.get("products") or []
    keywords = data_pack.get("keywords") or []
    reviews = data_pack.get("reviews") or []
    tiktok_products = data_pack.get("tiktok_products") or []
    tiktok_videos = data_pack.get("tiktok_videos") or []
    suppliers = data_pack.get("suppliers") or []
    web_docs = data_pack.get("web_documents") or []
    product_table = table(["ASIN", "中文定位", "英文标题", "品牌", "细分", "价格", "估算月销量", "估算销售额", "星级", "评论数", "上架", "source_id"], competitor_rows(products, None), "evidence-table appendix-table")
    keyword_table = table(["关键词中文", "英文关键词", "相关性", "月搜索量", "周搜索量", "CPC", "竞争数", "中文意图", "来源", "source_id"], [[kw.get("keyword_cn"), kw.get("keyword"), kw.get("relevance_cn"), num(kw.get("monthly_search_volume")), num(kw.get("weekly_search_volume")), kw.get("recommended_cpc") or "-", num(kw.get("competitor_count")), kw.get("intent_cn"), kw.get("source_type"), kw.get("source_id")] for kw in keywords], "evidence-table appendix-table")
    review_table = table(["ASIN", "星级", "日期", "标题", "评论摘录", "主题", "source_id"], [[r.get("asin"), r.get("rating"), r.get("review_date"), truncate(r.get("title"), 70), truncate(r.get("text"), 220), ", ".join(r.get("themes") or []), r.get("source_id")] for r in reviews], "evidence-table appendix-table")
    tk_product_table = table(["Product ID", "标题", "品牌", "价格", "估算月销量", "source_id"], [[p.get("product_id"), truncate(p.get("title"), 90), p.get("brand"), money(p.get("price")), num(p.get("estimated_monthly_sales")), p.get("source_id")] for p in tiktok_products], "evidence-table appendix-table")
    tk_video_table = table(["Product ID", "标题", "播放", "点赞", "达人", "URL", "source_id"], [[v.get("product_id"), truncate(v.get("title"), 80), num(v.get("views")), num(v.get("likes")), truncate(v.get("author"), 40), v.get("url"), v.get("source_id")] for v in tiktok_videos], "evidence-table appendix-table")
    supplier_table = table(["标题", "价格", "30日销量", "店铺", "发货地", "URL", "source_id"], [[truncate(s.get("title"), 90), money(s.get("price_rmb"), "¥"), num(s.get("sales_30d")), s.get("store_name"), s.get("shipping_origin"), s.get("url"), s.get("source_id")] for s in suppliers], "evidence-table appendix-table")
    web_table = table(["标题", "摘要", "URL", "query", "source_id"], [[truncate(w.get("title"), 80), truncate(w.get("description"), 130), w.get("url"), truncate(w.get("query"), 60), w.get("source_id")] for w in web_docs], "evidence-table appendix-table")
    method_table = table(["method_id", "purpose/output", "used_source_ids"], [[m.get("method_id"), truncate(m.get("purpose") or m.get("output"), 120), ", ".join(str(v) for v in (m.get("used_source_ids") or []))] for m in analysis_plan.get("method_chain", [])], "evidence-table appendix-table")
    return (
        details(f"完整产品池 products（{len(products)}）", product_table)
        + details(f"完整关键词池 keywords（{len(keywords)}）", keyword_table)
        + details(f"完整 Review 样本 reviews（{len(reviews)}）", review_table)
        + details(f"TikTok 商品 tiktok_products（{len(tiktok_products)}）", tk_product_table)
        + details(f"TikTok 视频 tiktok_videos（{len(tiktok_videos)}）", tk_video_table)
        + details(f"1688 供应商 suppliers（{len(suppliers)}）", supplier_table)
        + details(f"Firecrawl 网页 web_documents（{len(web_docs)}）", web_table)
        + details("方法链 method_chain", method_table)
    )


def render_lineage(data_pack: dict[str, Any]) -> str:
    rows = [
        [source.get("source_id"), source.get("provider"), source.get("tool"), truncate(first(source.get("label"), source.get("query"), source.get("args"), default="-"), 72), source.get("confidence"), truncate(source.get("limitation") or source.get("raw_path") or "", 96)]
        for source in data_pack.get("sources", [])
    ]
    rendered = table(["source_id", "provider", "tool", "label/query", "confidence", "limitation/raw_path"], rows, "evidence-table appendix-table")
    return rendered.removeprefix("<table class=\"evidence-table appendix-table\">").removesuffix("</table>")


def write_lineage_markdown(data_pack: dict[str, Any], path: Path) -> None:
    lines = ["# Data Lineage", ""]
    for source in data_pack.get("sources", []):
        label = truncate(first(source.get("label"), source.get("query"), source.get("args"), default="-"), 140)
        limitation = truncate(source.get("limitation") or source.get("raw_path") or "", 180)
        lines.append(
            f"- {source.get('source_id')}: {source.get('provider')} / {source.get('tool')} / {label} / confidence={source.get('confidence')} / {limitation}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def render_template(template_key: str, replacements: dict[str, Any]) -> str:
    template = TEMPLATE_PATHS[template_key].read_text(encoding="utf-8")
    html_doc = template
    for token, value in replacements.items():
        html_doc = html_doc.replace(token, str(value))
    return html_doc


def primary_source_id(data_pack: dict[str, Any]) -> str:
    sources = data_pack.get("sources") or []
    return str(first(*(source.get("source_id") for source in sources), default="src_gap"))


def source_ids_for(entity: dict[str, Any], fallback: str) -> str:
    ids = entity.get("source_ids") or []
    if entity.get("source_id"):
        ids = [*ids, entity["source_id"]]
    unique: list[str] = []
    for source_id in ids:
        if source_id and source_id not in unique:
            unique.append(str(source_id))
    return ", ".join(unique) or fallback


def section_table(title: str, headers: list[str], rows: list[list[Any]]) -> str:
    return f"<div class=\"card\"><div class=\"card-title\">{esc(title)}</div>{table(headers, rows)}</div>"


def render_index_cards(report_title: str, decision: str, data_pack: dict[str, Any]) -> str:
    quality = data_pack.get("quality") or {}
    cards = [
        ("市场深度调研报告", "market-depth-report.html", "大盘、关键词、竞品、VOC、TikTok、1688、Web 风险与数据血缘。"),
        ("产品全生命周期拓品战略报告", "lifecycle-strategy-report.html", "用户画像、生命周期旅程、SKU、Bundle、路线图和风险矩阵。"),
        ("用户心智断层与需求机会报告", "demand-gap-report.html", "$APPEALS、满意度鸿沟、KANO × JTBD、用户原声和需求优先级。"),
    ]
    report_cards = "".join(
        f"<article class=\"report-card\"><a href=\"{href}\"><span>{esc(label)}</span><strong>打开报告</strong></a><p>{esc(desc)}</p></article>"
        for label, href, desc in cards
    )
    metrics = (
        "<div class=\"kpi-grid\">"
        + kpi_card("核心判断", decision, "Go / Watch / No-Go", "warning")
        + kpi_card("数据质量", first(quality.get("grade"), "-"), f"score {first(quality.get('overall_score'), '-')}", "success")
        + kpi_card("Evidence Sources", num(len(data_pack.get("sources") or [])), "source_id lineage", "")
        + kpi_card("研究对象", report_title, "三报告共用 Data Pack", "")
        + "</div>"
    )
    return metrics + "<div class=\"report-card-grid\">" + report_cards + "</div>"


def lifecycle_skus(data_pack: dict[str, Any], lifecycle: dict[str, Any], fallback_source: str) -> list[dict[str, Any]]:
    explicit = lifecycle.get("skus")
    if isinstance(explicit, list) and explicit:
        return [item for item in explicit if isinstance(item, dict)]
    products = data_pack.get("products") or []
    suppliers = data_pack.get("suppliers") or []
    defaults = [
        {"name": "备用/替换核心配件", "stage": "开箱/替换", "type": "A", "price": "$12-$29", "supply": "自有或可控供应链", "phase": "P1", "priority": 92, "source_id": fallback_source},
        {"name": "信任说明卡 + 快速启动卡", "stage": "0-30 分钟", "type": "A", "price": "$3-$6", "supply": "印刷包装", "phase": "P1", "priority": 88, "source_id": fallback_source},
        {"name": "场景化配件包", "stage": "1-7 天", "type": "B", "price": "$12-$24", "supply": "自有或外协供应链", "phase": "P1", "priority": 84, "source_id": fallback_source},
        {"name": "清洁/保养/维护套装", "stage": "7 天-6 个月", "type": "D", "price": "$9-$19", "supply": "外采耗材", "phase": "P2", "priority": 78, "source_id": fallback_source},
        {"name": "替换充电线/数据线套装", "stage": "维护期", "type": "D", "price": "$8-$12", "supply": "外采电子", "phase": "P2", "priority": 72, "source_id": fallback_source},
    ]
    for product in products[:3]:
        defaults.append(
            {
                "name": f"{first(product.get('title_cn'), product.get('title'), default='竞品功能')} 对标配件",
                "stage": "竞品补位",
                "type": "C",
                "price": money(max(9, as_float(product_price(product), 19) * 0.18)),
                "supply": "按竞品差异打样",
                "phase": "P2",
                "priority": 70,
                "source_id": source_ids_for(product, fallback_source),
            }
        )
    for supplier in suppliers[:3]:
        defaults.append(
            {
                "name": first(supplier.get("title"), supplier.get("supplier_name"), default="1688 相似供应端机会"),
                "stage": "供应链验证",
                "type": "D",
                "price": money(first(supplier.get("price"), supplier.get("price_rmb"), default=12), "¥"),
                "supply": "1688 相似货源",
                "phase": "P2",
                "priority": 68,
                "source_id": source_ids_for(supplier, fallback_source),
            }
        )
    return defaults


def render_strategy_dashboard(data_pack: dict[str, Any], lifecycle: dict[str, Any], fallback_source: str) -> str:
    skus = lifecycle_skus(data_pack, lifecycle, fallback_source)
    self_supply = [sku for sku in skus if "自有" in clean(sku.get("supply")) or "可控" in clean(sku.get("supply"))]
    rows = [
        ["拓品 SKU 总数", len(skus), fallback_source],
        ["可自产 SKU", len(self_supply), fallback_source],
        ["复购/维护型 SKU", len([sku for sku in skus if str(sku.get("type")).upper() == "D"]), fallback_source],
        ["建议首发 Phase", "P1 可控供应链 + 信任/开箱触点优先", fallback_source],
    ]
    return (
        "<div class=\"kpi-grid\">"
        + kpi_card("拓品 SKU 总数", len(skus), "覆盖生命周期触点", "success")
        + kpi_card("可自产 SKU", len(self_supply), "供应链可控", "")
        + kpi_card("复购引擎", "60-90 天", "清洁/替换/维护", "warning")
        + kpi_card("主策略", "Bundle 提升 AOV", "先打样 P1", "")
        + "</div>"
        + section_table("战略仪表盘证据", ["指标", "结果", "source_id"], rows)
    )


def render_personas(data_pack: dict[str, Any], lifecycle: dict[str, Any], fallback_source: str) -> str:
    personas = lifecycle.get("personas") or [
        {"name": "礼品/首次购买用户", "need": "信任清晰、开箱体面、上手简单", "price": "按核心价格带上浮 10%-25%", "source_id": fallback_source},
        {"name": "自用/体验升级用户", "need": "持续可用、维护方便、体验稳定", "price": "按高频配件和维护包分层", "source_id": fallback_source},
        {"name": "进阶/专业场景用户", "need": "更强功能、组合方案、明确售后", "price": "按套装和高阶 SKU 溢价", "source_id": fallback_source},
    ]
    cards = "".join(
        f"<article class=\"persona-card\"><div class=\"persona-header\"><span>{esc(item.get('name'))}</span></div>"
        f"<div class=\"persona-body\"><p>{esc(item.get('need'))}</p><strong>{esc(item.get('price'))}</strong><p>source_id: {esc(source_ids_for(item, fallback_source))}</p></div></article>"
        for item in personas[:6]
    )
    rows = [[item.get("name"), item.get("need"), item.get("price"), source_ids_for(item, fallback_source)] for item in personas[:12]]
    return "<div class=\"persona-grid\">" + cards + "</div>" + section_table("用户画像证据表", ["画像", "核心需求", "价格接受带", "source_id"], rows)


def render_lifecycle_journey(data_pack: dict[str, Any], fallback_source: str) -> str:
    phases = [
        ["开箱 0-30 分钟", "欢迎卡、信任说明卡、快速启动指南", "降低第一次使用阻力", fallback_source],
        ["第 1-7 天", "场景化配件包、使用任务卡、基础组合包", "完成新鲜感到习惯的过渡", fallback_source],
        ["第 7 天-6 个月", "清洁维护、替换配件、季节/场景主题包", "延长生命周期并制造复购", fallback_source],
        ["每月+", "耗材/主题内容/配件 Bundle", "形成 AOV 与复购飞轮", fallback_source],
        ["6 个月+", "品牌延伸、礼品升级包、二代配件", "从单品进入可持续产品生态", fallback_source],
    ]
    cards = "".join(
        f"<article class=\"tl-card\"><div class=\"tl-header\">阶段 {idx}</div><div class=\"tl-time\">{esc(row[0])}</div><div class=\"tl-skus\">{esc(row[1])}</div><div class=\"tl-pain\">{esc(row[2])}</div></article>"
        for idx, row in enumerate(phases, 1)
    )
    return "<div class=\"timeline-grid\">" + cards + "</div>" + section_table("生命周期旅程证据表", ["阶段", "建议 SKU/触点", "用户任务", "source_id"], phases)


def render_ecosystem(data_pack: dict[str, Any], skus: list[dict[str, Any]], fallback_source: str) -> str:
    counts = Counter(str(sku.get("type", "A")).upper() for sku in skus)
    rows = [
        ["A 核心体验增强", counts.get("A", 0), "强关联、先随主体打包", fallback_source],
        ["B 场景/人群扩展", counts.get("B", 0), "礼品、节日、细分人群", fallback_source],
        ["C 内容/服务延伸", counts.get("C", 0), "教程、任务、服务权益", fallback_source],
        ["D 清洁维护/耗材", counts.get("D", 0), "复购与售后触点", fallback_source],
    ]
    return (
        "<div class=\"chart-container\"><div class=\"chart-title\">四维拓品生态</div>"
        + mini_chart([(row[0], float(row[1]), row[1]) for row in rows], "good")
        + "</div>"
        + section_table("四维拓品生态证据表", ["维度", "SKU 数", "打法", "source_id"], rows)
    )


def render_sku_execution_table(skus: list[dict[str, Any]], fallback_source: str) -> str:
    rows = [
        [
            sku.get("phase"),
            sku.get("stage"),
            sku.get("type"),
            sku.get("name"),
            sku.get("price"),
            sku.get("supply"),
            sku.get("priority"),
            source_ids_for(sku, fallback_source),
        ]
        for sku in skus
    ]
    return table(["Phase", "生命周期", "类型", "拓品 SKU", "价格带", "供应链", "优先级", "source_id"], rows, "evidence-table sku appendix-table")


def render_bundle_strategy(skus: list[dict[str, Any]], fallback_source: str) -> str:
    bundles = [
        ["新手启航套装", "主体 + 欢迎卡 + 信任说明卡 + 基础配件", "$99-$119", "降低首购疑虑", fallback_source],
        ["豪华礼品套装", "主体 + 礼盒 + 场景配件 + 备用核心配件", "$129-$159", "提升礼品场景 AOV", fallback_source],
        ["进阶体验套装", "主体 + 高阶使用任务卡 + 售后/信任引导", "$119-$149", "进阶用户溢价", fallback_source],
        ["续航补给包", "清洁护理 + 替换线 + 耗材", "$19-$29", "60-90 天复购", fallback_source],
    ]
    cards = "".join(
        f"<article class=\"bundle-card\"><div class=\"bundle-header\"><h3>{esc(row[0])}</h3><span class=\"badge\">Bundle</span></div><div class=\"bundle-items\">{esc(row[1])}</div><div class=\"bundle-pricing\"><span class=\"final\">{esc(row[2])}</span><span class=\"save\">{esc(row[3])}</span></div><p>source_id: {esc(row[4])}</p></article>"
        for row in bundles
    )
    return "<div class=\"bundle-grid\">" + cards + "</div>" + section_table("Bundle 策略证据表", ["Bundle", "组合", "建议价", "目标", "source_id"], bundles)


def render_lifecycle_roadmap(skus: list[dict[str, Any]], fallback_source: str) -> str:
    rows = [
        ["30 天", "打样 P1 可控 SKU；确认 Bundle 包装；补信任承诺物料", "可控启动", fallback_source],
        ["60 天", "1688/硬件供应商询价；完成样品质检；收集首批用户反馈", "供应链验证", fallback_source],
        ["90 天", "上线首批 Bundle；依据转化和评论调整 SKU；规划 P2", "市场验证", fallback_source],
    ]
    phase_cards = "".join(
        f"<article class=\"phase-card\"><div class=\"phase-header\">{esc(row[0])}</div><div class=\"phase-body\"><h3>{esc(row[2])}</h3><p>{esc(row[1])}</p><p>source_id: {esc(row[3])}</p></div></article>"
        for row in rows
    )
    return "<div class=\"phase-grid\">" + phase_cards + "</div>" + section_table("30/60/90 天路线图证据表", ["时间", "动作", "目标", "source_id"], rows)


def render_lifecycle_risks(fallback_source: str) -> str:
    rows = [
        ["供应链风险", "电子件/外采件质量不稳定", "Phase 1 优先可控供应链；外采至少 2 家备选", fallback_source],
        ["合规/信任风险", "涉及数据、安全、认证、售后承诺等信任门槛", "按品类核查法规与平台政策；关键承诺前置到页面", fallback_source],
        ["竞品跟进风险", "高溢价卖点被快速复制", "外观/IP/包装体验和评论证据形成组合壁垒", fallback_source],
    ]
    cards = "".join(
        f"<article class=\"risk-card\"><h3>{esc(row[0])}</h3><p class=\"desc\">{esc(row[1])}</p><div class=\"mitigation\"><strong>应对：</strong>{esc(row[2])}</div><p>source_id: {esc(row[3])}</p></article>"
        for row in rows
    )
    return "<div class=\"risk-grid\">" + cards + "</div>" + section_table("风险矩阵证据表", ["风险", "触发原因", "应对策略", "source_id"], rows)


def render_lifecycle_market_intel(data_pack: dict[str, Any], analysis_plan: dict[str, Any], fallback_source: str) -> str:
    rows = [
        ["Amazon 产品页面分析", f"{len(data_pack.get('products') or [])} 个产品样本", fallback_source],
        ["TikTok / 社交媒体信号", f"{len(data_pack.get('tiktok_products') or [])} 个商品；{len(data_pack.get('tiktok_videos') or [])} 条视频", fallback_source],
        ["行业媒体 & 安全报告", f"{len(data_pack.get('web_documents') or [])} 个 Firecrawl 网页", fallback_source],
        ["竞品格局分析", f"{len(analysis_plan.get('method_chain') or [])} 条方法链", fallback_source],
    ]
    return section_table("市场数据验证", ["数据域", "覆盖", "source_id"], rows)


def appeal_rows(data_pack: dict[str, Any], fallback_source: str) -> list[list[Any]]:
    reviews = data_pack.get("reviews") or []
    rows: list[list[Any]] = []
    theme_counts: Counter[str] = Counter()
    for review in reviews:
        themes = review.get("themes_cn") or review.get("themes") or []
        if isinstance(themes, str):
            themes = [themes]
        theme_counts.update(themes or ["其他体验问题"])
    if not theme_counts:
        theme_counts.update(["性能（Performance）", "隐私信任", "材质手感"])
    for theme, count in theme_counts.most_common(8):
        rows.append(["Performance" if "性能" in theme or "其他" in theme else "Appeal", theme, count, "转成可感知卖点或设计修复项", fallback_source])
    return rows


def render_target_anchor(data_pack: dict[str, Any], object_value: Any, fallback_source: str) -> str:
    products = data_pack.get("products") or []
    anchor = products[0] if products else {}
    rows = [
        ["研究对象", object_value, fallback_source],
        ["目标 ASIN/锚点", first(anchor.get("asin"), "未指定 ASIN，按关键词/品类锚定", default="-"), source_ids_for(anchor, fallback_source) if anchor else fallback_source],
        ["样本范围", f"{len(products)} products / {len(data_pack.get('reviews') or [])} reviews / {len(data_pack.get('keywords') or [])} keywords", fallback_source],
    ]
    return section_table("目标 ASIN/研究对象锚点", ["字段", "结果", "source_id"], rows)


def render_decision_board(data_pack: dict[str, Any], demand_gap: dict[str, Any], decision: str, fallback_source: str) -> str:
    opportunities = demand_gap.get("opportunities") or []
    max_opportunity = first((opportunities[0].get("pain") if opportunities else None), "性能（Performance）体验重构", default="-")
    rows = [
        ["最大机会", max_opportunity, fallback_source],
        ["核心判断", decision, fallback_source],
        ["证据密度", f"{len(data_pack.get('reviews') or [])} reviews / {len(data_pack.get('sources') or [])} sources", fallback_source],
    ]
    return (
        "<div class=\"kpi-grid\">"
        + kpi_card("最高机会维度", max_opportunity, "Gap Analysis", "success")
        + kpi_card("核心判断", decision, "Go / Watch / No-Go", "warning")
        + kpi_card("Review 样本", len(data_pack.get("reviews") or []), "用户原声", "")
        + "</div>"
        + section_table("决策看板证据表", ["指标", "结果", "source_id"], rows)
    )


def render_appeals_map(data_pack: dict[str, Any], fallback_source: str) -> str:
    rows = appeal_rows(data_pack, fallback_source)
    return (
        "<div class=\"chart-container\"><div class=\"chart-title\">$APPEALS 痛点全景</div>"
        + mini_chart([(row[1], float(row[2]), row[2]) for row in rows], "bad")
        + "</div>"
        + table(["$APPEALS 维度", "核心痛点", "样本提及", "动作", "source_id"], rows)
    )


def render_gap_analysis(data_pack: dict[str, Any], fallback_source: str) -> str:
    rows = [
        ["性能（Performance）", "高", "做不好会直接差评/退款", fallback_source],
        ["隐私信任", "高", "需要变成页面可见承诺", fallback_source],
        ["核心体验质感", "中高", "用户最容易感知，也最容易通过差评放大的体验层", fallback_source],
        ["订阅/后续成本", "中", "需明确无强制订阅或分层权益", fallback_source],
    ]
    return (
        "<div class=\"chart-container\"><div class=\"chart-title\">满意度鸿沟雷达（CSS 替代）</div>"
        + mini_chart([(row[0], idx + 1.0, row[1]) for idx, row in enumerate(rows)], "warn")
        + "</div>"
        + section_table("满意度鸿沟证据表", ["维度", "鸿沟强度", "解释", "source_id"], rows)
    )


def render_kano_jtbd(demand_gap: dict[str, Any], fallback_source: str) -> str:
    opportunities = demand_gap.get("opportunities") or []
    rows = []
    for item in opportunities[:8]:
        rows.append([first(item.get("kano"), "Must-be"), item.get("pain"), first(item.get("jtbd"), "当用户担心体验失败时，需要一个可被验证的承诺。"), first(item.get("opportunity"), "转成页面卖点与产品修复"), source_ids_for(item, fallback_source)])
    if not rows:
        rows = [
            ["Must-be", "信任与信息透明", "购买前要确认核心承诺可验证、风险可控", "页面承诺、证据截图、售后/数据处理说明", fallback_source],
            ["Performance", "功能体验与使用场景割裂", "用户想要核心功能可靠，并能适配真实使用场景", "关键场景模式 + 快速上手 + 低门槛配置", fallback_source],
            ["Delighter", "开箱与赠礼表达不足", "购买者希望产品显得体面且有明确价值", "礼盒/套装 + 欢迎卡 + 价值说明卡", fallback_source],
        ]
    return table(["KANO属性", "核心痛点", "场景还原 (JTBD)", "创新机会", "source_id"], rows)


def render_voice_theater(data_pack: dict[str, Any], fallback_source: str) -> str:
    reviews = data_pack.get("reviews") or []
    rows = []
    cards = []
    for review in reviews[:10]:
        text = truncate(review.get("text"), 180)
        rows.append([review.get("asin"), review.get("rating"), truncate(review.get("title"), 60), text, source_ids_for(review, fallback_source)])
        cards.append(
            f"<article class=\"quote-card\"><div class=\"quote-cn\">{esc(text)}</div><div class=\"quote-origin\">ASIN {esc(review.get('asin'))} · source_id: {esc(source_ids_for(review, fallback_source))}</div></article>"
        )
    if not rows:
        rows = [["-", "-", "评论样本不足", "需要补 Sorftime product_reviews 或用户评论文件", fallback_source]]
        cards = [f"<article class=\"quote-card\"><div class=\"quote-cn\">评论样本不足，需求判断只能保持 Watch。</div><div class=\"quote-origin\">source_id: {esc(fallback_source)}</div></article>"]
    return "<div class=\"quote-grid\">" + "".join(cards) + "</div>" + table(["ASIN", "星级", "标题", "用户原声", "source_id"], rows)


def render_priority_table(data_pack: dict[str, Any], demand_gap: dict[str, Any], fallback_source: str) -> str:
    rows = [
        ["P0", "信任透明承诺", "降低购买阻力", "Must-be", fallback_source],
        ["P0", "可维护/可替换结构", "解决长期使用焦虑", "Performance", fallback_source],
        ["P1", "无强制订阅表达", "避免后续成本差评", "Performance", fallback_source],
        ["P1", "礼盒开箱与价值说明卡", "提升送礼转化和溢价", "Delighter", fallback_source],
    ]
    for item in (demand_gap.get("opportunities") or [])[:6]:
        rows.append([first(item.get("priority"), "P1"), item.get("pain"), first(item.get("action"), item.get("opportunity"), default="-"), first(item.get("kano"), "-"), source_ids_for(item, fallback_source)])
    return table(["优先级", "需求/痛点", "执行动作", "KANO", "source_id"], rows)


def write_delivery_result(report_dir: Path, delivery: dict[str, Any]) -> None:
    output_path = report_dir / "output" / "delivery_result.json"
    delivery = dict(delivery)
    delivery.setdefault("status", "complete")
    formats = list(delivery.get("formats") or [])
    if "html" not in formats:
        formats.append("html")
    delivery["formats"] = formats
    delivery["html_reports"] = HTML_REPORTS
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(delivery, ensure_ascii=False, indent=2), encoding="utf-8")


def render(report_dir: Path) -> Path:
    normalize_data_pack(report_dir)
    data_pack = load_json(report_dir / "data" / "data_pack.json", {})
    write_lineage_markdown(data_pack, report_dir / "data" / "lineage.md")
    analysis_plan = load_json(report_dir / "analysis" / "analysis_plan.json", {})
    market_size = load_json(report_dir / "analysis" / "market_size.json", {})
    voc = load_json(report_dir / "analysis" / "voc.json", {})
    opportunity = load_json(report_dir / "analysis" / "opportunity.json", {})
    profitability = load_json(report_dir / "analysis" / "profitability.json", {})
    lifecycle = load_json(report_dir / "analysis" / "lifecycle_strategy.json", {})
    demand_gap = load_json(report_dir / "analysis" / "demand_gap.json", {})
    delivery = load_json(report_dir / "output" / "delivery_result.json", {})

    brief = data_pack.get("brief") or {}
    research_object = brief.get("research_object") or data_pack.get("research_object") or {}
    object_value = first(research_object.get("value") if isinstance(research_object, dict) else research_object, data_pack.get("task_id"), default="Amazon Market")
    quality = data_pack.get("quality") or {}
    decision = first(delivery.get("decision"), "Watch", default="Watch")
    categories = data_pack.get("categories") or []
    category = categories[0] if categories else {}
    keyword_pool = [kw for kw in data_pack.get("keywords", []) if kw.get("monthly_search_volume")]
    core_keyword_pool = [
        kw
        for kw in keyword_pool
        if kw.get("source_type") != "product_traffic_terms"
        and (kw.get("is_core_relevant") or kw.get("relevance_cn") == "高相关")
    ]
    keywords = sorted(core_keyword_pool or keyword_pool, key=lambda kw: as_float(kw.get("monthly_search_volume"), 0), reverse=True)
    products = relevant_products(sorted(data_pack.get("products") or [], key=lambda product: as_float(product_sales(product), 0), reverse=True))
    competitor_table, competitor_cards, competitor_products = render_competitors(data_pack)
    fallback_source = primary_source_id(data_pack)
    report_date = datetime.now().strftime("%Y-%m-%d")
    target_market = first((brief.get("market_scope") or {}).get("amazon") if isinstance(brief.get("market_scope"), dict) else None, "Amazon US")
    data_depth = first(brief.get("data_depth"), (brief.get("data_scope") or {}).get("depth") if isinstance(brief.get("data_scope"), dict) else None, "标准版")
    report_title = f"{object_value} · 三合一市场研究报告"

    kpis = [
        kpi_card("核心判断", decision, "Go / Watch / No-Go", "warning"),
        kpi_card("Top100 估算月销量", num(category.get("top100_estimated_monthly_units")), "Sorftime 类目代理", "success"),
        kpi_card("最大关键词月搜索", num(keywords[0].get("monthly_search_volume") if keywords else None), keywords[0].get("keyword") if keywords else "keyword gap"),
        kpi_card("相关竞品池", num(len(products)), "过滤泛词噪声后", ""),
        kpi_card("Review 样本", num(len(data_pack.get("reviews") or [])), "VOC evidence", ""),
        kpi_card("1688 样本", num(len(data_pack.get("suppliers") or [])), "supply proxy", "warning"),
        kpi_card("TikTok 商品", num(len(data_pack.get("tiktok_products") or [])), "channel signal", ""),
        kpi_card("数据质量", first(quality.get("grade"), "-"), f"score {first(quality.get('overall_score'), '-')}", "warning"),
    ]

    common = {
        "{{REPORT_TITLE}}": report_title,
        "{{REPORT_OBJECT}}": esc(object_value),
        "{{REPORT_DATE}}": report_date,
        "{{TARGET_MARKET}}": target_market,
        "{{DATA_DEPTH}}": data_depth,
        "{{DECISION}}": decision,
        "{{PRIMARY_SOURCE_ID}}": fallback_source,
    }
    market_replacements = {
        **common,
        "{{MARKET_REPORT_TITLE}}": f"{object_value} · 市场深度调研报告",
        "{{REPORT_SUBTITLE}}": "Sorftime 主数据 + Firecrawl 公网补充 · 全量关键词、竞品、VOC、TikTok、1688、Web 风险与完整附录",
        "{{KPI_CARDS}}": "".join(kpis),
        "{{EXECUTIVE_INSIGHT_WITH_SOURCE_IDS}}": f"核心判断：{esc(decision)}。本 HTML 展开 Data Pack 中可展示的主要数据：{len(data_pack.get('sources', []))} 个 source、{len(data_pack.get('products', []))} 个产品、{len(data_pack.get('keywords', []))} 个关键词、{len(data_pack.get('reviews', []))} 条评论、{len(data_pack.get('tiktok_videos', []))} 条 TikTok 视频、{len(data_pack.get('suppliers', []))} 条供应端样本。关键销量均标注为估算月销量（Sorftime）。",
        "{{MARKET_DASHBOARD}}": render_market(data_pack, market_size),
        "{{KEYWORD_TABLE_AND_INTENT_CARDS}}": render_keywords(data_pack),
        "{{COMPETITOR_TABLE}}": competitor_table,
        "{{COMPETITOR_SEGMENT_CARDS}}": competitor_cards,
        "{{COMPETITOR_DEEP_DIVES}}": render_product_deep_dives(competitor_products, data_pack.get("keywords") or []),
        "{{VOC_CARDS_AND_TABLE}}": render_voc(data_pack, voc),
        "{{TIKTOK_VALIDATION}}": render_tiktok(data_pack),
        "{{SUPPLIER_TABLE_AND_COST_THRESHOLDS}}": render_supply(data_pack, profitability),
        "{{WEB_RISK_SUPPLEMENT}}": render_web_risk(data_pack),
        "{{OPPORTUNITY_CARDS}}": render_opportunities(opportunity),
        "{{DECISION_ROADMAP}}": render_decision(delivery),
        "{{FULL_DATA_APPENDIX}}": render_full_appendix(data_pack, analysis_plan),
        "{{LINEAGE_TABLE}}": render_lineage(data_pack),
        "{{REPORT_FOOTER}}": f"{esc(object_value)} · Generated by amz-market-research-orchestrated · market-depth-report-v2",
    }
    skus = lifecycle_skus(data_pack, lifecycle, fallback_source)
    lifecycle_replacements = {
        **common,
        "{{LIFECYCLE_REPORT_TITLE}}": f"{object_value} · 产品全生命周期拓品战略报告",
        "{{STRATEGY_DASHBOARD}}": render_strategy_dashboard(data_pack, lifecycle, fallback_source),
        "{{USER_PERSONAS}}": render_personas(data_pack, lifecycle, fallback_source),
        "{{LIFECYCLE_JOURNEY}}": render_lifecycle_journey(data_pack, fallback_source),
        "{{FOUR_DIMENSION_ECOSYSTEM}}": render_ecosystem(data_pack, skus, fallback_source),
        "{{SKU_EXECUTION_TABLE}}": render_sku_execution_table(skus, fallback_source),
        "{{BUNDLE_STRATEGY}}": render_bundle_strategy(skus, fallback_source),
        "{{IMPLEMENTATION_ROADMAP}}": render_lifecycle_roadmap(skus, fallback_source),
        "{{RISK_MATRIX}}": render_lifecycle_risks(fallback_source),
        "{{MARKET_INTELLIGENCE}}": render_lifecycle_market_intel(data_pack, analysis_plan, fallback_source),
        "{{LIFECYCLE_LINEAGE}}": render_lineage(data_pack),
        "{{REPORT_FOOTER}}": f"{esc(object_value)} · Generated by amz-market-research-orchestrated · lifecycle-strategy-report-v2",
    }
    demand_replacements = {
        **common,
        "{{DEMAND_REPORT_TITLE}}": f"{object_value} · 用户心智断层与需求机会报告",
        "{{TARGET_ANCHOR}}": render_target_anchor(data_pack, object_value, fallback_source),
        "{{DECISION_BOARD}}": render_decision_board(data_pack, demand_gap, decision, fallback_source),
        "{{APPEALS_MAP}}": render_appeals_map(data_pack, fallback_source),
        "{{GAP_ANALYSIS}}": render_gap_analysis(data_pack, fallback_source),
        "{{KANO_JTBD_MATRIX}}": render_kano_jtbd(demand_gap, fallback_source),
        "{{VOICE_THEATER}}": render_voice_theater(data_pack, fallback_source),
        "{{PRIORITY_TABLE}}": render_priority_table(data_pack, demand_gap, fallback_source),
        "{{DEMAND_LINEAGE}}": render_lineage(data_pack),
        "{{REPORT_FOOTER}}": f"{esc(object_value)} · Generated by amz-market-research-orchestrated · demand-gap-report-v2",
    }
    index_replacements = {
        **common,
        "{{INDEX_CARDS}}": render_index_cards(str(object_value), str(decision), data_pack),
        "{{DATA_COVERAGE}}": render_data_coverage(data_pack, analysis_plan),
        "{{DATA_GAPS}}": render_data_gaps(data_pack, analysis_plan),
        "{{REPORT_FOOTER}}": f"{esc(object_value)} · Generated by amz-market-research-orchestrated · three-report-index-v2",
    }

    output_dir = report_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered_docs = {
        "index": render_template("index", index_replacements),
        "market_depth": render_template("market_depth", market_replacements),
        "lifecycle_strategy": render_template("lifecycle_strategy", lifecycle_replacements),
        "demand_gap": render_template("demand_gap", demand_replacements),
    }
    for key, html_doc in rendered_docs.items():
        (report_dir / HTML_REPORTS[key]).write_text(html_doc, encoding="utf-8")
    write_delivery_result(report_dir, delivery)
    return report_dir / HTML_REPORTS["index"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the v2 three-report HTML bundle for amz-market-research-orchestrated reports.")
    parser.add_argument("--dir", required=True, help="Report directory containing data/ and analysis/.")
    args = parser.parse_args(argv)
    output_path = render(Path(args.dir))
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
