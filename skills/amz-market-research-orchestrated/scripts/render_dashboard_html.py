#!/usr/bin/env python3
"""Render the v2 three-report HTML bundle from a market-research report dir."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from customer_copy import (
    customer_product_message,
    customer_product_position,
    customer_review_summary,
    customer_review_title,
    review_sentiment_label,
    review_theme_labels,
)
from delivery_writer import write_delivery_result, write_lineage_markdown, write_report_brief
from customer_safety import customer_safe_asset_text, redact_customer_html
from html_components import (
    as_float,
    clean,
    details,
    esc,
    first,
    kpi_card,
    kpi_card_html,
    metric,
    mini_chart,
    money,
    num,
    pct,
    price_band,
    product_price,
    product_revenue,
    product_reviews,
    product_sales,
    relevant_products,
    table,
    table_inner,
    tag,
    truncate,
)
from normalize_data_pack import ENTITY_KEYS, infer_seed_terms, normalize as normalize_data_pack, tokens
from report_renderers import build_report_documents
from site_assets import (
    HTML_BUNDLE_DIR,
    COMPAT_INDEX_REPORT,
    HTML_REPORT_FILENAMES,
    HTML_REPORTS,
    attach_site_chrome,
    write_basic_site_assets,
)
from view_model_builder import build_site_data, write_report_views


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
CHILD_SKILLS_DIR = SKILL_DIR / "child_skills"
LEGACY_TEMPLATE_PATHS = {
    "market_depth": SKILL_DIR / "assets" / "market-depth-template.html",
    "lifecycle_strategy": SKILL_DIR / "assets" / "lifecycle-strategy-template.html",
    "demand_gap": SKILL_DIR / "assets" / "demand-gap-template.html",
}
TEMPLATE_PATHS = {
    "index": SKILL_DIR / "assets" / "report-index-template.html",
    "market_depth": CHILD_SKILLS_DIR / "market-depth-report" / "templates" / "market-depth-report.html",
    "lifecycle_strategy": CHILD_SKILLS_DIR / "lifecycle-strategy-report" / "templates" / "lifecycle-strategy-report.html",
    "demand_gap": CHILD_SKILLS_DIR / "demand-gap-report" / "templates" / "demand-gap-report.html",
}

CHILD_SKILLS = {
    "market_depth": "child_skills/market-depth-report",
    "lifecycle_strategy": "child_skills/lifecycle-strategy-report",
    "demand_gap": "child_skills/demand-gap-report",
    "critic": "child_skills/market-research-critic",
}

CHILD_REPORT_RENDERERS = {
    "market_depth": CHILD_SKILLS_DIR / "market-depth-report" / "scripts" / "render_market_depth_report.py",
    "lifecycle_strategy": CHILD_SKILLS_DIR / "lifecycle-strategy-report" / "scripts" / "render_lifecycle_strategy_report.py",
    "demand_gap": CHILD_SKILLS_DIR / "demand-gap-report" / "scripts" / "render_demand_gap_report.py",
}
CRITIC_RENDERER = CHILD_SKILLS_DIR / "market-research-critic" / "scripts" / "run_critic.py"

CHILD_INVOCATION_LOG = Path("analysis") / "child_skill_invocation_log.json"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def relative_to_skill(path: Path) -> str:
    try:
        return path.resolve().relative_to(SKILL_DIR.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def write_invocation_log(report_dir: Path, log: list[dict[str, Any]]) -> None:
    log_path = report_dir / CHILD_INVOCATION_LOG
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def run_child_report_renderers(report_dir: Path) -> list[dict[str, Any]]:
    log: list[dict[str, Any]] = []
    for key, script_path in CHILD_REPORT_RENDERERS.items():
        command = [sys.executable, str(script_path), "--dir", str(report_dir)]
        started_at = utc_now()
        result = subprocess.run(command, text=True, capture_output=True, check=False)
        finished_at = utc_now()
        output_path = report_dir / HTML_REPORTS[key]
        entry = {
            "module": CHILD_SKILLS[key],
            "renderer": relative_to_skill(script_path),
            "renderer_sha256": file_sha256(script_path),
            "dispatch_mode": "subprocess_child_renderer",
            "command": [Path(sys.executable).name, relative_to_skill(script_path), "--dir", str(report_dir)],
            "cwd": str(Path.cwd()),
            "started_at": started_at,
            "finished_at": finished_at,
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "output": HTML_REPORTS[key],
            "output_sha256": file_sha256(output_path) if output_path.exists() else None,
        }
        log.append(entry)
        if result.returncode != 0:
            write_invocation_log(report_dir, log)
            raise RuntimeError(f"Child renderer failed for {key}: {result.stderr or result.stdout}")
    write_invocation_log(report_dir, log)
    return log


def run_critic_child(report_dir: Path, decision: str, log: list[dict[str, Any]], previous_review: Path | None = None, previous_plan: Path | None = None) -> dict[str, Any]:
    command = [sys.executable, str(CRITIC_RENDERER), "--dir", str(report_dir), "--decision", decision]
    command_log = [Path(sys.executable).name, relative_to_skill(CRITIC_RENDERER), "--dir", str(report_dir), "--decision", decision]
    if previous_review and previous_plan:
        command.extend(["--previous-review", str(previous_review), "--previous-plan", str(previous_plan)])
        command_log.extend(["--previous-review", str(previous_review), "--previous-plan", str(previous_plan)])
    started_at = utc_now()
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    finished_at = utc_now()
    outputs = ["analysis/critic_review.json", "analysis/refinement_plan.json", "analysis/critic_decision.json"]
    entry = {
        "module": CHILD_SKILLS["critic"],
        "renderer": relative_to_skill(CRITIC_RENDERER),
        "renderer_sha256": file_sha256(CRITIC_RENDERER),
        "dispatch_mode": "subprocess_critic_child",
        "command": command_log,
        "cwd": str(Path.cwd()),
        "started_at": started_at,
        "finished_at": finished_at,
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "outputs": outputs,
        "output_sha256": {path: file_sha256(report_dir / path) for path in outputs if (report_dir / path).exists()},
    }
    log.append(entry)
    write_invocation_log(report_dir, log)
    if result.returncode != 0:
        raise RuntimeError(f"Critic child failed: {result.stderr or result.stdout}")
    return load_json(report_dir / "analysis" / "critic_decision.json", {})


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
        + "</div><div class=\"card\"><div class=\"card-title\">交叉验证与去重</div>"
        + f"<p>{tag('已去重', 'good')} {tag('已交叉验证', 'warn')}</p><p>同竞品、同关键词、同链接、同供应商先合并，再进入分析和 HTML。多类样本同时命中的实体会提高置信度，冲突字段只保留在审计文件。</p>"
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
        segment_sales[first(product.get("segment_cn"), product.get("segment"), default="unknown")] += as_float(product_sales(product), 0)
        price_band_sales[price_band(product_price(product))] += as_float(product_sales(product), 0)
        seller_origin = first(
            product.get("seller_origin"),
            product.get("seller_country"),
            product.get("seller_source"),
            product.get("seller_location"),
            product.get("merchant_country"),
            default="",
        )
        if seller_origin:
            origin_counts[seller_origin] += 1
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
        ["低评论产品销量占比", pct(first(category.get("low_reviews_sales_share"), category.get("low_review_sales_share"), default=None)), source_id],
        ["高评论产品销量占比", pct(first(category.get("high_reviews_sales_share"), category.get("high_review_sales_share"), default=None)), source_id],
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
        + details("相邻与噪声关键词池（不直接作为进入判断）", adjacent_table)
        + details("关键词来源结构", source_table)
        + details("竞品反查流量词与流量入口", traffic_table)
    )


def competitor_rows(products: list[dict[str, Any]], limit: int | None = None) -> list[list[Any]]:
    rows = []
    for product in products[:limit]:
        rows.append(
            [
                product.get("asin"),
                customer_product_position(product),
                customer_product_message(product),
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
    segment_counts = Counter(first(product.get("segment_cn"), product.get("segment"), default="unknown") for product in filtered)
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
        ["竞品样本", "中文定位", "页面表达归纳", "品牌", "细分", "价格", "估算月销量", "估算销售额", "星级", "评论数", "上架", "source_id"],
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
        trend_text = "待验证"
        if trend.get("first") is not None and trend.get("last") is not None:
            trend_text = f"{num(trend.get('first'))} → {num(trend.get('last'))}，增长 {trend.get('growth')}"
        traffic_tags = "".join(tag(kw.get("keyword")) for kw in traffic.get(asin, [])[:6])
        variations = product.get("variation_samples") or []
        variation_text = "；".join(truncate(item, 42) for item in variations[:3]) or "待补样本"
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
            + f"<div class=\"comp-deep-text\">{esc(customer_product_position(product))}</div></div>"
            + "<div class=\"comp-deep-section\"><div class=\"comp-deep-section-title\">页面表达归纳</div>"
            + f"<div class=\"comp-deep-text\">{esc(customer_product_message(product))}</div></div>"
            + "<div class=\"meta\">"
            + tag(first(product.get("segment_cn"), product.get("segment"), "-"))
            + tag(money(product_price(product)), "warn")
            + tag(f"估算月销量 {num(product_sales(product))}", "good")
            + tag(f"评分 {first(product.get('rating'), '-')}")
            + tag(f"评论 {num(product_reviews(product))}")
            + "</div>"
            + "<div class=\"comp-deep-section\"><div class=\"comp-deep-section-title\">趋势 · 流量 · 变体</div>"
            + f"<div class=\"comp-deep-text\">趋势：{esc(trend_text)}<br>流量词：{traffic_tags or '待补样本'}<br>变体样本：{esc(variation_text)}</div></div>"
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
        themes = review_theme_labels(review)
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
        sentiment = review_sentiment_label(review)
        title = customer_review_title(review)
        summary_cn = customer_review_summary(review, 220)
        quote_cards.append(
            f"<article class=\"quote-card{tone}\"><strong>{esc(sentiment)} · {esc(review.get('rating'))}星 · {esc(title)}</strong>"
            f"<p>{esc(summary_cn)}</p><p>{tag('证据强度：高')}</p></article>"
        )
    theme_rows = [
        [theme, count, low_theme_counts.get(theme, 0), "样本提及频次，不写精确百分比"]
        for theme, count in theme_counts.most_common(16)
    ]
    sample_rows = [
        [f"样本 {idx:03d}", review.get("rating"), review_sentiment_label(review), customer_review_summary(review, 180), "、".join(review_theme_labels(review)), "高"]
        for idx, review in enumerate(reviews[:120], 1)
    ]
    summary = (
        "<div class=\"metric-strip\">"
        + metric("评论样本", len(reviews), "已做中文摘要映射")
        + metric("低星样本", len(low_reviews), "3星及以下")
        + metric("覆盖竞品", len([k for k in asin_counts if k]), "核心样本")
        + metric("主题数", len(theme_counts), "VOC 主题簇")
        + metric("5星样本", star_counts.get(5, 0), "正向购买动机")
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
        + "<div class=\"insight\">评论与 VOC 主题用于识别设计与转化问题；英文原评先转成中文摘要和需求语言，样本不足或偏近期时，只写频次和证据，不写精确市场百分比。</div>"
        + charts
        + "<div class=\"quote-grid\">"
        + "".join(quote_cards)
        + "</div>"
        + table(["主题", "总提及", "低星提及", "限制"], theme_rows)
        + details("评论样本分析表（前120条）", table(["样本", "星级", "情绪", "中文摘要", "主题", "证据强度"], sample_rows))
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


def customer_safe_signal_title(item: dict[str, Any], fallback: str) -> str:
    for key in ("title_cn", "name_cn", "summary_cn"):
        value = clean(item.get(key))
        if value and re.search(r"[\u4e00-\u9fff]", value):
            return truncate(value, 70)
    return fallback


def render_tiktok(data_pack: dict[str, Any]) -> str:
    products = data_pack.get("tiktok_products") or []
    videos = sorted(data_pack.get("tiktok_videos") or [], key=lambda video: as_float(video.get("views"), 0), reverse=True)
    seed_terms = infer_seed_terms(data_pack)
    relevance_counts = Counter(tiktok_relevance(product, seed_terms) for product in products)
    product_rows = [
        [product.get("product_id"), customer_safe_signal_title(product, "内容商品样本"), tiktok_relevance(product, seed_terms), first(product.get("brand"), "-"), money(product.get("price")), num(product.get("estimated_monthly_sales")), num(product.get("review_count")), product.get("source_id")]
        for product in products
    ]
    video_rows = [
        [video.get("product_id"), customer_safe_signal_title(video, "内容视频样本"), num(video.get("views")), num(video.get("likes")), truncate(video.get("author"), 32), "内容标签已归纳", video.get("source_id")]
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

    def supplier_price(supplier: dict[str, Any]) -> Any:
        return first(supplier.get("price_rmb"), supplier.get("factory_price_rmb"), supplier.get("price"), default=None)

    valid_prices = [as_float(supplier_price(supplier), -1) for supplier in suppliers if as_float(supplier_price(supplier), -1) > 0]
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
        [
            truncate(first(supplier.get("title_cn"), supplier.get("title"), supplier.get("name"), supplier.get("supplier_name"), default="-"), 72),
            money(supplier_price(supplier), "¥"),
            num(supplier.get("sales_30d")),
            first(supplier.get("repurchase_rate"), pct(supplier.get("repurchase_rate_pct")), default="-"),
            first(supplier.get("store_name"), "-"),
            first(supplier.get("shipping_origin"), "-"),
            supplier.get("source_id"),
        ]
        for supplier in suppliers[:40]
    ]
    cards = "".join(
        [
            kpi_card("有效价格样本", num(first(stats.get("valid_price_count"), len(valid_prices), default=0)), "1688 相似货源"),
            kpi_card("采购价中位数", money(first(stats.get("median_rmb"), statistics.median(valid_prices) if valid_prices else None), "¥"), "不含物流、FBA、认证", "warning"),
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
    rows = [[customer_safe_signal_title(doc, "公开网页样本"), "网页摘要已归纳到风险和机会判断", "网页链接保留在审计稿", first(doc.get("position"), "-"), doc.get("source_id")] for doc in docs]
    risk_cards = (
        "<div class=\"risk-grid\">"
        "<article class=\"risk-card\"><h3>合规与召回</h3><p>涉及电气、户外、防水、发热、玻璃破损等风险，必须二次核查 CPSC、UL、ETL 和 Amazon policy。</p></article>"
        "<article class=\"risk-card\"><h3>测评口碑</h3><p>公开测评只作为方向线索，不能替代 Sorftime 评论和真实样品测试。</p></article>"
        "<article class=\"risk-card\"><h3>网页证据限制</h3><p>Firecrawl 搜索结果必须保留在 web_documents，不直接写成结论。</p></article>"
        "</div>"
    )
    return "<div class=\"card\"><div class=\"card-title\">公开网页覆盖</div>" + mini_chart([(truncate(k, 36), v, v) for k, v in query_counts.most_common()]) + "</div>" + risk_cards + table(["标题", "摘要", "URL", "排名", "source_id"], rows)


def render_opportunities(opportunity: dict[str, Any]) -> str:
    opportunities = opportunity.get("opportunities") or []
    if not opportunities:
        opportunities = [{"name": "细分机会待验证", "decision": "Watch", "score": "待评分", "entry_shape": "需要继续收敛证据。", "risks": ["证据不足"]}]
    cards = []
    for item in opportunities[:10]:
        decision = str(item.get("decision") or "Watch")
        tone = "nogo" if "No" in decision or "不" in decision else "watch" if "Watch" in decision else ""
        risks = item.get("risks") or []
        evidence = item.get("evidence") or []
        entry_shape = first(
            item.get("entry_shape"),
            item.get("recommendation"),
            "以小批量样品、页面卖点和广告转化验证为先，达标后再扩 SKU。",
        )
        evidence_text = "；".join(str(v) for v in evidence[:4]) or "由关键词需求、竞品销量、VOC 主题和供应端样本共同支撑，需结合打样继续验证。"
        risk_text = "；".join(str(v) for v in risks[:5]) or "主要风险在真实转化、退货率、认证成本和供应端一致性。"
        cards.append(
            f"<article class=\"opportunity-card {tone}\"><h3>{esc(item.get('name'))}</h3>"
            f"<p>{tag(decision)} {tag('Score ' + str(first(item.get('score'), '待评分')), 'warn')}</p>"
            f"<p><strong>建议形态：</strong>{esc(entry_shape)}</p>"
            f"<p><strong>证据：</strong>{esc(evidence_text)}</p>"
            f"<p><strong>风险：</strong>{esc(risk_text)}</p></article>"
        )
    return "".join(cards)


def render_decision(delivery: dict[str, Any]) -> str:
    decision = first(delivery.get("decision"), "Watch", default="Watch")
    return (
        "<div class=\"grid-3\">"
        "<div class=\"card\"><div class=\"card-title\">进入条件</div><ul><li>锁定一个细分，不做泛品类。</li><li>样品解决核心 VOC 问题。</li><li>补齐 landed cost、认证、FBA、退货率、ACOS。</li></ul></div>"
        "<div class=\"card\"><div class=\"card-title\">停止条件</div><ul><li>核心词 CPC 与转化无法覆盖毛利。</li><li>低星问题来自结构性缺陷。</li><li>供应端只能同款搬运，无质量与设计优势。</li></ul></div>"
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
    review_table = table(["ASIN", "星级", "日期", "标题", "评论摘录", "主题", "source_id"], [[r.get("asin"), r.get("rating"), r.get("review_date"), r.get("title_cn"), r.get("summary_cn"), ", ".join(r.get("themes_cn") or []), r.get("source_id")] for r in reviews], "evidence-table appendix-table")
    tk_product_table = table(["Product ID", "标题", "品牌", "价格", "估算月销量", "source_id"], [[p.get("product_id"), customer_safe_signal_title(p, "内容商品样本"), p.get("brand"), money(p.get("price")), num(p.get("estimated_monthly_sales")), p.get("source_id")] for p in tiktok_products], "evidence-table appendix-table")
    tk_video_table = table(["Product ID", "标题", "播放", "点赞", "达人", "URL", "source_id"], [[v.get("product_id"), customer_safe_signal_title(v, "内容视频样本"), num(v.get("views")), num(v.get("likes")), truncate(v.get("author"), 40), "内容链接保留在审计稿", v.get("source_id")] for v in tiktok_videos], "evidence-table appendix-table")
    supplier_table = table(["标题", "价格", "30日销量", "店铺", "发货地", "URL", "source_id"], [[customer_safe_signal_title(s, "供应商样本"), money(s.get("price_rmb"), "¥"), num(s.get("sales_30d")), "供应端店铺样本", s.get("shipping_origin"), "供应链接保留在审计稿", s.get("source_id")] for s in suppliers], "evidence-table appendix-table")
    web_table = table(["标题", "摘要", "URL", "query", "source_id"], [[customer_safe_signal_title(w, "公开网页样本"), "网页摘要已归纳到风险和机会判断", "网页链接保留在审计稿", "检索词保留在审计稿", w.get("source_id")] for w in web_docs], "evidence-table appendix-table")
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


def render_template(template_key: str, replacements: dict[str, Any]) -> str:
    template = TEMPLATE_PATHS[template_key].read_text(encoding="utf-8")
    html_doc = template
    for token, value in replacements.items():
        html_doc = html_doc.replace(token, str(value))
    return html_doc


def render_legacy_child_template(template_key: str, replacements: dict[str, Any]) -> str:
    template = LEGACY_TEMPLATE_PATHS[template_key].read_text(encoding="utf-8")
    html_doc = template
    for token, value in replacements.items():
        html_doc = html_doc.replace(token, str(value))
    return html_doc


def child_body_fragment(html_doc: str) -> str:
    styles = "\n".join(re.findall(r"<style\b[^>]*>.*?</style>", html_doc, flags=re.S | re.I))
    scripts = "\n".join(re.findall(r"<script\b[^>]*>.*?</script>", html_doc, flags=re.S | re.I))
    match = re.search(r"<body\b[^>]*>(.*)</body>", html_doc, flags=re.S | re.I)
    body = match.group(1) if match else html_doc
    return "\n".join(part for part in [styles, body, scripts] if part)


def write_site_assets(report_dir: Path, data_pack: dict[str, Any], analysis_plan: dict[str, Any], decision: str) -> None:
    write_basic_site_assets(report_dir, build_site_data(data_pack, analysis_plan, decision, CHILD_SKILLS))


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


def confidence_level(data_pack: dict[str, Any], analysis_plan: dict[str, Any] | None = None) -> str:
    score = as_float((data_pack.get("quality") or {}).get("overall_score"), 0)
    if score >= 0.82:
        return "高"
    if score >= 0.62:
        return "中高"
    return "中"


def sample_coverage(data_pack: dict[str, Any]) -> str:
    keywords = len(data_pack.get("keywords") or [])
    products = len(data_pack.get("products") or [])
    reviews = len(data_pack.get("reviews") or [])
    suppliers = len(data_pack.get("suppliers") or [])
    return f"关键词 {keywords}；竞品 {products}；评论 {reviews}；供应样本 {suppliers}"


def sample_coverage_tags(data_pack: dict[str, Any]) -> str:
    items = [
        (len(data_pack.get("keywords") or []), "关键词"),
        (len(data_pack.get("products") or []), "竞品"),
        (len(data_pack.get("reviews") or []), "评论"),
        (len(data_pack.get("suppliers") or []), "供应样本"),
    ]
    tags = "".join(f"<span class=\"metric-tag\"><b>{esc(value)}</b><span>{esc(label)}</span></span>" for value, label in items)
    return f"<div class=\"metric-tags\">{tags}</div>"


def client_trust_strip(data_pack: dict[str, Any], analysis_plan: dict[str, Any], decision: str) -> str:
    gaps = len(data_pack.get("data_gaps") or []) + len(analysis_plan.get("limitations") or [])
    next_action = "进入打样与页面卖点验证" if str(decision).lower() == "go" else "补关键缺口后小步验证"
    tabs = (
        "<div class=\"trust-tabs\" data-tabs>"
        "<div class=\"tab-list\" role=\"tablist\">"
        "<button class=\"tab-button\" type=\"button\" data-tab-target=\"evidence\" aria-selected=\"true\">证据</button>"
        "<button class=\"tab-button\" type=\"button\" data-tab-target=\"gaps\" aria-selected=\"false\">缺口</button>"
        "</div>"
        "<div data-tab-panel=\"evidence\">当前结论以归一化样本、交叉验证和方法链为准。</div>"
        "<div data-tab-panel=\"gaps\" hidden>缺失指标会进入数据缺口和下一步验证，不包装成已证实结论。</div>"
        "</div>"
    )
    return (
        "<div class=\"kpi-grid client-trust-grid\">"
        + kpi_card("证据强度", confidence_level(data_pack, analysis_plan), "综合样本质量与方法链", "success")
        + kpi_card_html("样本覆盖", sample_coverage_tags(data_pack), "用于方向判断，不替代财务尽调", "")
        + kpi_card("数据缺口", f"{gaps} 项", "已纳入风险判断", "warning")
        + kpi_card("建议动作", next_action, "客户版执行摘要", "success")
        + "</div>"
        + tabs
    )


def insight_table(title: str, rows: list[list[Any]]) -> str:
    return section_table(title, ["结论", "证据强度", "商业含义", "建议动作"], rows)


def render_client_data_coverage(data_pack: dict[str, Any], analysis_plan: dict[str, Any], decision: str) -> str:
    rows = [
        ["市场判断", confidence_level(data_pack, analysis_plan), "当前样本足以支持 Go / Watch / No-Go 方向判断。", f"按 {decision} 节奏推进验证"],
        ["样本覆盖", "中高", sample_coverage(data_pack), "优先补最影响决策的缺口"],
        ["数据缺口", "已标注", "缺口不会隐藏在报告正文里，会转成风险和下一步动作。", "进入补数或小样本验证"],
    ]
    return client_trust_strip(data_pack, analysis_plan, decision) + insight_table("客户版可信度说明", rows)


def render_client_action_summary(data_pack: dict[str, Any], analysis_plan: dict[str, Any], decision: str, object_value: Any) -> str:
    rows = [
        ["可进入性评分", confidence_level(data_pack, analysis_plan), "市场存在可验证需求，但需用样本和转化继续压实。", "先做最小 SKU 与页面卖点验证"],
        ["价格带机会", "中高", "价格带应围绕用户可感知差异化，而不是单纯低价竞争。", "锁定主推价位与 Bundle 台阶"],
        ["竞争强度", "中", "竞品格局仍有体验与信任表达空位。", "用标杆打法拆出可复制卖点"],
        ["关键切入口", "高", f"{object_value} 应从痛点最集中的场景切入。", "把核心机会写进主图、标题、五点和首批打样"],
    ]
    return insight_table("风险与行动摘要", rows)


def bundle_href(filename: str, link_prefix: str = "") -> str:
    prefix = link_prefix.strip().strip("/")
    return f"{prefix}/{filename}" if prefix else filename


def render_index_cards(report_title: str, decision: str, data_pack: dict[str, Any], link_prefix: str = "") -> str:
    quality = data_pack.get("quality") or {}
    cards = [
        ("市场深度调研报告", HTML_REPORT_FILENAMES["market_depth"], "大盘、需求、竞品、VOC、TikTok、1688、风险与行动摘要。"),
        ("产品全生命周期拓品战略报告", HTML_REPORT_FILENAMES["lifecycle_strategy"], "用户画像、生命周期旅程、SKU、Bundle、路线图和风险矩阵。"),
        ("用户心智断层与需求机会报告", HTML_REPORT_FILENAMES["demand_gap"], "$APPEALS、满意度鸿沟、KANO × JTBD、用户原声和需求优先级。"),
    ]
    report_cards = "".join(
        f"<article class=\"report-card\"><a href=\"{bundle_href(href, link_prefix)}\"><span>{esc(label)}</span><strong>打开报告</strong></a><p>{esc(desc)}</p></article>"
        for label, href, desc in cards
    )
    metrics = (
        "<div class=\"kpi-grid\">"
        + kpi_card("核心判断", decision, "Go / Watch / No-Go", "warning")
        + kpi_card("数据质量", first(quality.get("grade"), "-"), f"score {first(quality.get('overall_score'), '-')}", "success")
        + kpi_card("证据样本数", num(len(data_pack.get("sources") or [])), "内部审计链路保留", "")
        + kpi_card("研究对象", report_title, "三报告共用 Data Pack", "")
        + "</div>"
    )
    return metrics + "<div class=\"report-card-grid\">" + report_cards + "</div>"


def lifecycle_skus(data_pack: dict[str, Any], lifecycle: dict[str, Any], fallback_source: str) -> list[dict[str, Any]]:
    explicit = lifecycle.get("skus")
    if isinstance(explicit, list) and explicit:
        safe_items: list[dict[str, Any]] = []
        for idx, item in enumerate(explicit, 1):
            if not isinstance(item, dict):
                continue
            safe = dict(item)
            name = clean(first(safe.get("name"), safe.get("title"), default=""))
            safe["name"] = name if re.search(r"[\u4e00-\u9fff]", name) else f"拓品方案 {idx}"
            safe_items.append(safe)
        return safe_items
    products = data_pack.get("products") or []
    suppliers = data_pack.get("suppliers") or []
    defaults = [
        {"name": "备用与替换核心配件", "stage": "开箱与替换", "type": "A", "price": "$12-$29", "supply": "自有或可控供应链", "phase": "P1", "priority": 92, "source_id": fallback_source},
        {"name": "信任说明卡 + 快速启动卡", "stage": "0-30 分钟", "type": "A", "price": "$3-$6", "supply": "印刷包装", "phase": "P1", "priority": 88, "source_id": fallback_source},
        {"name": "场景化配件包", "stage": "1-7 天", "type": "B", "price": "$12-$24", "supply": "自有或外协供应链", "phase": "P1", "priority": 84, "source_id": fallback_source},
        {"name": "清洁、保养与维护套装", "stage": "7 天-6 个月", "type": "D", "price": "$9-$19", "supply": "外采耗材", "phase": "P2", "priority": 78, "source_id": fallback_source},
        {"name": "替换充电线与数据线套装", "stage": "维护期", "type": "D", "price": "$8-$12", "supply": "外采电子", "phase": "P2", "priority": 72, "source_id": fallback_source},
    ]
    for product in products[:3]:
        defaults.append(
            {
                "name": f"{customer_safe_signal_title(product, '竞品功能')} 对标配件",
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
                "name": "1688 相似供应端机会",
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
        ["复购维护型 SKU", len([sku for sku in skus if str(sku.get("type")).upper() == "D"]), fallback_source],
        ["建议首发 Phase", "P1 可控供应链 + 信任与开箱触点优先", fallback_source],
    ]
    return (
        "<div class=\"kpi-grid\">"
        + kpi_card("拓品 SKU 总数", len(skus), "覆盖生命周期触点", "success")
        + kpi_card("可自产 SKU", len(self_supply), "供应链可控", "")
        + kpi_card("复购引擎", "60-90 天", "清洁、替换、维护", "warning")
        + kpi_card("主策略", "Bundle 提升 AOV", "先打样 P1", "")
        + "</div>"
        + section_table("战略仪表盘证据", ["指标", "结果", "source_id"], rows)
    )


def render_personas(data_pack: dict[str, Any], lifecycle: dict[str, Any], fallback_source: str) -> str:
    personas = lifecycle.get("personas") or [
        {"name": "礼品与首次购买用户", "need": "信任清晰、开箱体面、上手简单", "price": "按核心价格带上浮 10%-25%", "source_id": fallback_source},
        {"name": "自用与体验升级用户", "need": "持续可用、维护方便、体验稳定", "price": "按高频配件和维护包分层", "source_id": fallback_source},
        {"name": "进阶与专业场景用户", "need": "更强功能、组合方案、明确售后", "price": "按套装和高阶 SKU 溢价", "source_id": fallback_source},
    ]
    cards = "".join(
        f"<article class=\"persona-card\"><div class=\"persona-header\"><span>{esc(item.get('name'))}</span></div>"
        f"<div class=\"persona-body\"><p>{esc(first(item.get('need'), '用户需求仍需补充样本验证'))}</p><strong>{esc(first(item.get('price'), '价格接受带待验证'))}</strong><p>source_id: {esc(source_ids_for(item, fallback_source))}</p></div></article>"
        for item in personas[:6]
    )
    rows = [[item.get("name"), first(item.get("need"), "用户需求仍需补充样本验证"), first(item.get("price"), "价格接受带待验证"), source_ids_for(item, fallback_source)] for item in personas[:12]]
    return "<div class=\"persona-grid\">" + cards + "</div>" + section_table("用户画像证据表", ["画像", "核心需求", "价格接受带", "source_id"], rows)


def render_lifecycle_journey(data_pack: dict[str, Any], fallback_source: str) -> str:
    phases = [
        ["开箱 0-30 分钟", "欢迎卡、信任说明卡、快速启动指南", "降低第一次使用阻力", fallback_source],
        ["第 1-7 天", "场景化配件包、使用任务卡、基础组合包", "完成新鲜感到习惯的过渡", fallback_source],
        ["第 7 天-6 个月", "清洁维护、替换配件、季节与场景主题包", "延长生命周期并制造复购", fallback_source],
        ["每月+", "耗材、主题内容、配件 Bundle", "形成 AOV 与复购飞轮", fallback_source],
        ["6 个月+", "品牌延伸、礼品升级包、二代配件", "从单品进入可持续产品生态", fallback_source],
    ]
    cards = "".join(
        f"<article class=\"tl-card\"><div class=\"tl-header\">阶段 {idx}</div><div class=\"tl-time\">{esc(row[0])}</div><div class=\"tl-skus\">{esc(row[1])}</div><div class=\"tl-pain\">{esc(row[2])}</div></article>"
        for idx, row in enumerate(phases, 1)
    )
    return "<div class=\"timeline-grid\">" + cards + "</div>" + section_table("生命周期旅程证据表", ["阶段", "建议 SKU 与触点", "用户任务", "source_id"], phases)


def render_ecosystem(data_pack: dict[str, Any], skus: list[dict[str, Any]], fallback_source: str) -> str:
    counts = Counter(str(sku.get("type", "A")).upper() for sku in skus)
    rows = [
        ["A 核心体验增强", counts.get("A", 0), "强关联、先随主体打包", fallback_source],
        ["B 场景与人群扩展", counts.get("B", 0), "礼品、节日、细分人群", fallback_source],
        ["C 内容与服务延伸", counts.get("C", 0), "教程、任务、服务权益", fallback_source],
        ["D 清洁维护与耗材", counts.get("D", 0), "复购与售后触点", fallback_source],
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
        ["进阶体验套装", "主体 + 高阶使用任务卡 + 售后与信任引导", "$119-$149", "进阶用户溢价", fallback_source],
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
        ["60 天", "1688 与硬件供应商询价；完成样品质检；收集首批用户反馈", "供应链验证", fallback_source],
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
        ["合规与信任风险", "涉及数据、安全、认证、售后承诺等信任门槛", "按品类核查法规与平台政策；关键承诺前置到页面", fallback_source],
        ["竞品跟进风险", "高溢价卖点被快速复制", "外观、IP、包装体验和评论证据形成组合壁垒", fallback_source],
    ]
    cards = "".join(
        f"<article class=\"risk-card\"><h3>{esc(row[0])}</h3><p class=\"desc\">{esc(row[1])}</p><div class=\"mitigation\"><strong>应对：</strong>{esc(row[2])}</div><p>source_id: {esc(row[3])}</p></article>"
        for row in rows
    )
    return "<div class=\"risk-grid\">" + cards + "</div>" + section_table("风险矩阵证据表", ["风险", "触发原因", "应对策略", "source_id"], rows)


def render_lifecycle_market_intel(data_pack: dict[str, Any], analysis_plan: dict[str, Any], fallback_source: str) -> str:
    rows = [
        ["Amazon 产品页面分析", f"{len(data_pack.get('products') or [])} 个产品样本", fallback_source],
        ["TikTok 与社交媒体信号", f"{len(data_pack.get('tiktok_products') or [])} 个商品；{len(data_pack.get('tiktok_videos') or [])} 条视频", fallback_source],
        ["行业媒体 & 安全报告", f"{len(data_pack.get('web_documents') or [])} 个 Firecrawl 网页", fallback_source],
        ["竞品格局分析", f"{len(analysis_plan.get('method_chain') or [])} 条方法链", fallback_source],
    ]
    return section_table("市场数据验证", ["数据域", "覆盖", "source_id"], rows)


def appeal_rows(data_pack: dict[str, Any], fallback_source: str) -> list[list[Any]]:
    reviews = data_pack.get("reviews") or []
    rows: list[list[Any]] = []
    theme_counts: Counter[str] = Counter()
    for review in reviews:
        theme_counts.update(review_theme_labels(review))
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
        ["研究对象锚点", first(anchor.get("asin"), "未指定竞品锚点，按关键词与品类锚定", default="-"), source_ids_for(anchor, fallback_source) if anchor else fallback_source],
        ["样本范围", f"{len(products)} 个竞品；{len(data_pack.get('reviews') or [])} 条评论；{len(data_pack.get('keywords') or [])} 个关键词", fallback_source],
    ]
    return section_table("研究对象锚点", ["字段", "结果", "source_id"], rows)


def render_decision_board(data_pack: dict[str, Any], demand_gap: dict[str, Any], decision: str, fallback_source: str) -> str:
    opportunities = demand_gap.get("opportunities") or []
    max_opportunity = first((opportunities[0].get("pain") if opportunities else None), "性能（Performance）体验重构", default="-")
    rows = [
        ["最大机会", max_opportunity, fallback_source],
        ["核心判断", decision, fallback_source],
        ["证据密度", f"{len(data_pack.get('reviews') or [])} 条评论；{len(data_pack.get('sources') or [])} 类样本记录", fallback_source],
    ]
    return (
        "<div class=\"kpi-grid\">"
        + kpi_card("最高机会维度", max_opportunity, "Gap Analysis", "success")
        + kpi_card("核心判断", decision, "Go / Watch / No-Go", "warning")
        + kpi_card("评论样本", len(data_pack.get("reviews") or []), "用户原声", "")
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
        ["性能（Performance）", "高", "做不好会直接引发差评或退款", fallback_source],
        ["隐私信任", "高", "需要变成页面可见承诺", fallback_source],
        ["核心体验质感", "中高", "用户最容易感知，也最容易通过差评放大的体验层", fallback_source],
        ["订阅与后续成本", "中", "需明确无强制订阅或分层权益", fallback_source],
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
            ["Must-be", "信任与信息透明", "购买前要确认核心承诺可验证、风险可控", "页面承诺、证据截图、售后与数据处理说明", fallback_source],
            ["Performance", "功能体验与使用场景割裂", "用户想要核心功能可靠，并能适配真实使用场景", "关键场景模式 + 快速上手 + 低门槛配置", fallback_source],
            ["Delighter", "开箱与赠礼表达不足", "购买者希望产品显得体面且有明确价值", "礼盒套装 + 欢迎卡 + 价值说明卡", fallback_source],
        ]
    return table(["KANO属性", "核心痛点", "场景还原 (JTBD)", "创新机会", "source_id"], rows)


def render_voice_theater(data_pack: dict[str, Any], fallback_source: str) -> str:
    reviews = data_pack.get("reviews") or []
    rows = []
    cards = []
    for idx, review in enumerate(reviews[:10], 1):
        text = customer_review_summary(review, 180)
        sentiment = review_sentiment_label(review)
        title = customer_review_title(review)
        rows.append([f"样本 {idx:02d}", review.get("rating"), sentiment, text, "、".join(review_theme_labels(review)), "高"])
        cards.append(
            f"<article class=\"quote-card\"><div class=\"quote-cn\">{esc(text)}</div><div class=\"quote-origin\">{esc(review.get('rating'))}星 · {esc(sentiment)} · {esc(title)}</div></article>"
        )
    if not rows:
        rows = [["-", "-", "样本不足", "评论样本不足，需求判断只能保持 Watch。", "待补充", "数据缺口"]]
        cards = ["<article class=\"quote-card\"><div class=\"quote-cn\">评论样本不足，需求判断只能保持 Watch。</div><div class=\"quote-origin\">数据缺口 · 需要补充评论样本</div></article>"]
    return "<div class=\"quote-grid\">" + "".join(cards) + "</div>" + table(["样本", "星级", "情绪", "中文化用户原声", "主题", "证据强度"], rows)


def render_priority_table(data_pack: dict[str, Any], demand_gap: dict[str, Any], fallback_source: str) -> str:
    rows = [
        ["P0", "信任透明承诺", "降低购买阻力", "Must-be", fallback_source],
        ["P0", "可维护与可替换结构", "解决长期使用焦虑", "Performance", fallback_source],
        ["P1", "无强制订阅表达", "避免后续成本差评", "Performance", fallback_source],
        ["P1", "礼盒开箱与价值说明卡", "提升送礼转化和溢价", "Delighter", fallback_source],
    ]
    for item in (demand_gap.get("opportunities") or [])[:6]:
        rows.append([first(item.get("priority"), "P1"), item.get("pain"), first(item.get("action"), item.get("opportunity"), default="-"), first(item.get("kano"), "-"), source_ids_for(item, fallback_source)])
    return table(["优先级", "需求与痛点", "执行动作", "KANO", "source_id"], rows)


def renderer_callbacks() -> dict[str, Any]:
    return {
        "as_float": as_float,
        "attach_site_chrome": attach_site_chrome,
        "child_body_fragment": child_body_fragment,
        "client_trust_strip": client_trust_strip,
        "confidence_level": confidence_level,
        "esc": esc,
        "first": first,
        "kpi_card": kpi_card,
        "lifecycle_skus": lifecycle_skus,
        "num": num,
        "primary_source_id": primary_source_id,
        "product_sales": product_sales,
        "relevant_products": relevant_products,
        "render_appeals_map": render_appeals_map,
        "render_bundle_strategy": render_bundle_strategy,
        "render_client_action_summary": render_client_action_summary,
        "render_client_data_coverage": render_client_data_coverage,
        "render_competitors": render_competitors,
        "render_data_gaps": render_data_gaps,
        "render_decision": render_decision,
        "render_decision_board": render_decision_board,
        "render_ecosystem": render_ecosystem,
        "render_full_appendix": render_full_appendix,
        "render_gap_analysis": render_gap_analysis,
        "render_index_cards": render_index_cards,
        "render_kano_jtbd": render_kano_jtbd,
        "render_keywords": render_keywords,
        "render_legacy_child_template": render_legacy_child_template,
        "render_lifecycle_journey": render_lifecycle_journey,
        "render_lifecycle_market_intel": render_lifecycle_market_intel,
        "render_lifecycle_risks": render_lifecycle_risks,
        "render_lifecycle_roadmap": render_lifecycle_roadmap,
        "render_lineage": render_lineage,
        "render_market": render_market,
        "render_opportunities": render_opportunities,
        "render_personas": render_personas,
        "render_priority_table": render_priority_table,
        "render_product_deep_dives": render_product_deep_dives,
        "render_sku_execution_table": render_sku_execution_table,
        "render_strategy_dashboard": render_strategy_dashboard,
        "render_supply": render_supply,
        "render_target_anchor": render_target_anchor,
        "render_template": render_template,
        "render_tiktok": render_tiktok,
        "render_voc": render_voc,
        "render_voice_theater": render_voice_theater,
        "render_web_risk": render_web_risk,
    }


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

    output_dir = report_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle_dir = report_dir / HTML_BUNDLE_DIR
    bundle_dir.mkdir(parents=True, exist_ok=True)

    def build_safe_documents(decision_value: str) -> tuple[dict[str, str], str]:
        docs, compat_html = build_report_documents(
            data_pack,
            analysis_plan,
            market_size,
            voc,
            opportunity,
            profitability,
            lifecycle,
            demand_gap,
            delivery,
            decision_value,
            renderer_callbacks(),
        )
        return {key: redact_customer_html(html_doc, data_pack) for key, html_doc in docs.items()}, redact_customer_html(compat_html, data_pack)

    def load_view_models() -> dict[str, dict[str, Any]]:
        return {
            "market_depth_view.json": load_json(report_dir / "analysis" / "market_depth_view.json", {}),
            "lifecycle_strategy_view.json": load_json(report_dir / "analysis" / "lifecycle_strategy_view.json", {}),
            "demand_gap_view.json": load_json(report_dir / "analysis" / "demand_gap_view.json", {}),
        }

    original_decision = str(first(delivery.get("decision"), "Watch", default="Watch"))
    rendered_docs, compat_index_html = build_safe_documents(original_decision)
    write_report_views(report_dir, data_pack, analysis_plan, original_decision)
    (report_dir / HTML_REPORTS["index"]).parent.mkdir(parents=True, exist_ok=True)
    (report_dir / HTML_REPORTS["index"]).write_text(rendered_docs["index"], encoding="utf-8")
    (report_dir / COMPAT_INDEX_REPORT).write_text(redact_customer_html(compat_index_html, data_pack), encoding="utf-8")
    invocation_log = run_child_report_renderers(report_dir)
    critic_decision = run_critic_child(report_dir, original_decision, invocation_log)
    decision = str(critic_decision.get("decision") or original_decision)
    if decision != original_decision:
        draft_review_path = report_dir / "analysis" / "critic_review.draft.json"
        draft_plan_path = report_dir / "analysis" / "refinement_plan.draft.json"
        draft_review_path.write_text((report_dir / "analysis" / "critic_review.json").read_text(encoding="utf-8"), encoding="utf-8")
        draft_plan_path.write_text((report_dir / "analysis" / "refinement_plan.json").read_text(encoding="utf-8"), encoding="utf-8")
        delivery = load_json(report_dir / "output" / "delivery_result.json", delivery)
        rendered_docs, compat_index_html = build_safe_documents(decision)
        write_report_views(report_dir, data_pack, analysis_plan, decision)
        (report_dir / HTML_REPORTS["index"]).write_text(rendered_docs["index"], encoding="utf-8")
        (report_dir / COMPAT_INDEX_REPORT).write_text(redact_customer_html(compat_index_html, data_pack), encoding="utf-8")
        invocation_log = run_child_report_renderers(report_dir)
        critic_decision = run_critic_child(report_dir, decision, invocation_log, draft_review_path, draft_plan_path)
    delivery = load_json(report_dir / "output" / "delivery_result.json", delivery)
    rendered_docs = {
        "index": (report_dir / HTML_REPORTS["index"]).read_text(encoding="utf-8"),
        "market_depth": (report_dir / HTML_REPORTS["market_depth"]).read_text(encoding="utf-8"),
        "lifecycle_strategy": (report_dir / HTML_REPORTS["lifecycle_strategy"]).read_text(encoding="utf-8"),
        "demand_gap": (report_dir / HTML_REPORTS["demand_gap"]).read_text(encoding="utf-8"),
    }
    write_site_assets(report_dir, data_pack, analysis_plan, str(decision))
    write_report_brief(report_dir, data_pack, analysis_plan, str(decision), CHILD_SKILLS)
    delivery["cleaning_summary"] = build_site_data(data_pack, analysis_plan, str(decision), CHILD_SKILLS)["cleaning_summary"]
    critic_review = load_json(report_dir / "analysis" / "critic_review.json", {})
    delivery["critic_review"] = {
        "path": "analysis/critic_review.json",
        "refinement_plan": "analysis/refinement_plan.json",
        "pass": critic_review["pass"],
        "score": critic_review["score"],
        "max_refinement_rounds": critic_review["max_refinement_rounds"],
    }
    write_delivery_result(report_dir, delivery, CHILD_SKILLS)
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
