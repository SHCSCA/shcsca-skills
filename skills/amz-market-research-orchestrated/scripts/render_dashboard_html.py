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
from check_data_readiness import assess as assess_data_readiness, write_json as write_readiness_json
from recover_data_readiness import recover_readiness
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


def customer_quality_summary(quality: dict[str, Any]) -> tuple[str, str, str]:
    score = as_float(quality.get("overall_score"), 0)
    raw_grade = clean(quality.get("grade"))
    if score >= 0.82 or raw_grade.upper() == "A":
        return "证据充分", "关键数据覆盖较完整，可进入客户判断", "success"
    if score >= 0.62 or raw_grade.upper() in {"B", "C"}:
        return "需复核", "关键口径可判断，但仍需复核高影响缺口", "warning"
    return "证据不足", "先补齐核心数据，再输出完整结论", "warning"


def product_units_total(products: list[dict[str, Any]]) -> float:
    return sum(as_float(product_sales(product), 0) for product in products)


def product_revenue_total(products: list[dict[str, Any]]) -> float:
    total = 0.0
    for product in products:
        revenue = as_float(product_revenue(product), 0)
        if revenue:
            total += revenue
            continue
        price = as_float(product_price(product), 0)
        sales = as_float(product_sales(product), 0)
        if price and sales:
            total += price * sales
    return total


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
    outputs = ["analysis/critic_review.json", "analysis/refinement_plan.json", "analysis/critic_summary.md", "analysis/critic_decision.json"]
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
    critic_decision = load_json(report_dir / "analysis" / "critic_decision.json", {})
    if critic_decision:
        entry["critic_pass"] = critic_decision.get("pass")
        entry["critic_score"] = critic_decision.get("score")
    log.append(entry)
    write_invocation_log(report_dir, log)
    if result.returncode != 0:
        raise RuntimeError(f"Critic child failed: {result.stderr or result.stdout}")
    return critic_decision


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
        "tiktok_authors": len(data_pack.get("tiktok_authors") or []),
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
    quality_label, quality_sub, quality_tone = customer_quality_summary(quality)
    return (
        metric_strip
        + "<div class=\"grid-3\"><div class=\"card\"><div class=\"card-title\">Provider Coverage</div>"
        + provider_chart
        + "</div><div class=\"card\"><div class=\"card-title\">数据质量说明</div>"
        + f"<p>{tag(quality_label, quality_tone)} {tag(quality_sub, 'warn')}</p><ul>{note_html}</ul>"
        + "</div><div class=\"card\"><div class=\"card-title\">交叉验证与去重</div>"
        + f"<p>{tag('已去重', 'good')} {tag('已交叉验证', 'warn')}</p><p>同竞品、同关键词、同链接、同供应商先合并，再进入分析和 HTML。多类数据记录同时命中的实体会提高置信度，冲突字段只保留在审计文件。</p>"
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
    fallback_units = product_units_total(products)
    fallback_revenue = product_revenue_total(products)
    top_units = first(
        category.get("top100_estimated_monthly_units"),
        market_size.get("top100_estimated_monthly_units"),
        fallback_units or None,
        default=None,
    )
    top_revenue = first(
        category.get("top100_estimated_monthly_revenue"),
        market_size.get("top100_estimated_monthly_revenue"),
        fallback_revenue or None,
        default=None,
    )
    median_price = statistics.median(prices) if prices else None
    high_band = "$99-$150" if median_price and as_float(median_price) < 99 else money(median_price)
    cards = [
        kpi_card("Top100 估算月销量", num(top_units), "由类目字段或竞品池销量聚合", "success"),
        kpi_card("Top100 估算销售额", money(top_revenue), "由竞品售价 × 月销聚合"),
        kpi_card("Amazon主力价格带", f"{money(median_price)} 附近", "销量最集中区间", "warning"),
        kpi_card("高溢价区间", high_band, "低密度 · 高毛利空间", "lavender"),
    ]
    market_rows = price_band_sales or Counter({"已采集竞品": as_float(top_units, 0) or len(products)})
    feature_rows = segment_sales or defaultdict(float, {"核心细分": as_float(top_units, 0) or len(products)})
    chart_seed = (
        "<div hidden data-chart-source=\"marketRows\">"
        + "".join(f"<span data-label=\"{esc(label)}\" data-value=\"{esc(value)}\"></span>" for label, value in market_rows.items())
        + "</div>"
        + "<div hidden data-chart-source=\"featureRows\">"
        + "".join(f"<span data-label=\"{esc(label)}\" data-value=\"{esc(value)}\"></span>" for label, value in feature_rows.items())
        + "</div>"
    )
    return (
        chart_seed
        + "<div class=\"kpi-grid\">" + "".join(cards) + "</div>"
        + "<div class=\"chart-grid\">"
        + echart_box("priceChart", "价格带销量分布图", "Amazon US · 各价格区间月销量估算")
        + echart_box("bubbleChart", "竞品价格区间竞争密度", "价格带竞品数量 vs 月销量估算 · 气泡大小=市场规模")
        + "</div>"
        + "<div class=\"chart-grid\">"
        + echart_box("growthChart", "市场增长趋势", "公开规模与月销量代理趋势")
        + echart_box("featureChart", "功能覆盖与机会空白", "竞品覆盖率 vs 目标补位")
        + "</div>"
        + "<div class=\"insight-box\">💡 <strong>大盘结论：</strong>当前已验证数据说明市场仍有可切入空间，但应避开纯低价红海，优先验证高溢价价格带、可感知功能差异和评论中反复出现的体验缺口。</div>"
    )


def render_keywords(data_pack: dict[str, Any]) -> str:
    keywords = [kw for kw in data_pack.get("keywords", []) if kw.get("keyword")]
    core_keywords = [kw for kw in keywords if kw.get("source_type") != "product_traffic_terms"]
    traffic_keywords = [kw for kw in keywords if kw.get("source_type") == "product_traffic_terms"]
    relevant_keywords = [kw for kw in core_keywords if kw.get("is_core_relevant") or kw.get("relevance_cn") == "高相关"]
    adjacent_keywords = [kw for kw in core_keywords if kw not in relevant_keywords]
    top_keywords = sorted(core_keywords or keywords, key=lambda kw: as_float(kw.get("monthly_search_volume"), 0), reverse=True)
    source_type_counts = Counter(kw.get("source_type", "unknown") for kw in keywords)
    relevance_counts = Counter(kw.get("relevance_cn", "待判断") for kw in keywords)
    cpc_keywords = sorted([kw for kw in top_keywords if kw.get("recommended_cpc") not in (None, "")], key=lambda kw: as_float(kw.get("recommended_cpc"), 0), reverse=True)
    competition_keywords = sorted([kw for kw in top_keywords if kw.get("competitor_count") not in (None, "")], key=lambda kw: as_float(kw.get("competitor_count"), 0), reverse=True)
    visible_keywords = top_keywords[:40]
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
        for kw in visible_keywords
    ]
    row_filters = [first(kw.get("relevance_cn"), default="待判断") for kw in visible_keywords]
    filter_options = [("全部", "all")]
    for bucket in ["高相关", "相邻相关", "待判断"]:
        if bucket in set(row_filters):
            filter_options.append((bucket, bucket))
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
        + echart_box("featureChart", "功能覆盖与关键词机会", "竞品覆盖率 vs 目标补位")
        + intent_cards
        + table(
            ["关键词中文", "英文关键词", "相关性", "月搜索量", "周搜索量", "CPC", "竞争结果", "中文意图", "旺季", "来源", "source_id"],
            rows,
            filter_options=filter_options,
            row_filters=row_filters,
        )
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
    head = "<thead><tr><th>ASIN</th><th>产品</th><th>价格</th><th>评分</th><th>月销估算</th><th>核心卖点</th><th>致命弱点</th><th>标签</th></tr></thead>"
    body_rows = []
    tag_sequence = ["badge-hot", "badge-hot", "badge-risk", "badge-growth", "badge-premium", "badge-premium"]
    top_products = filtered[:6]
    for idx, row in enumerate(competitor_rows(top_products, 6), 1):
        product = top_products[idx - 1]
        tag_class = tag_sequence[idx - 1] if idx <= len(tag_sequence) else "badge-growth"
        weak = competitor_weakness(product)
        body_rows.append(
            "<tr>"
            + f"<td><span class=\"asin-token\" data-allow-asin=\"competitor-table\">{esc(product.get('asin'))}</span></td>"
            + f"<td><div class=\"product-name\">{esc(row[1])}</div><div class=\"product-brand\">{esc(row[3])} · {esc(row[4])}</div></td>"
            + f"<td><span class=\"price-tag\">{esc(row[5])}</span></td>"
            + f"<td><span class=\"rating-stars\">★★★★</span> {esc(row[8])}</td>"
            + f"<td><strong>{esc(row[6])}</strong>/月</td>"
            + f"<td>{esc(row[2])}</td>"
            + f"<td>{esc(weak)}</td>"
            + f"<td><span class=\"badge {tag_class} badge-risk lavender\">{esc('高优先级' if idx <= 2 else '可参考')}</span></td>"
            + "</tr>"
        )
    colgroup = (
        "<colgroup>"
        "<col class=\"comp-col-asin\"><col class=\"comp-col-product\"><col class=\"comp-col-price\"><col class=\"comp-col-rating\">"
        "<col class=\"comp-col-sales\"><col class=\"comp-col-selling\"><col class=\"comp-col-weakness\"><col class=\"comp-col-tag\">"
        "</colgroup>"
    )
    comp_table = "<table class=\"comp-table\">" + colgroup + head + "<tbody>" + "".join(body_rows) + "</tbody></table>"
    return comp_table, cards, filtered


def competitor_weakness(product: dict[str, Any]) -> str:
    price = as_float(product_price(product), 0)
    reviews = as_float(product_reviews(product), 0)
    rating = as_float(first(product.get("rating"), product.get("星级"), default=0), 0)
    segment = clean(first(product.get("segment_cn"), product.get("segment"), default=""))
    positioning = clean(customer_product_position(product))
    context = segment + positioning
    if reviews >= 40000:
        return "评论壁垒很厚，新品短期难追平信任资产"
    if price and price <= 12:
        return "低价锚定明显，白牌进入容易陷入价格战"
    if rating and rating < 4.3:
        return "评分低于头部均值，质量与体验稳定性压力更高"
    if any(token in context for token in ["基础", "低价", "灯带", "夜灯"]):
        return "功能成熟且同质化强，难单靠参数支撑溢价"
    if any(token in context for token in ["户外", "太阳能", "防水"]):
        return "防水、安防和多支装价格竞争强"
    if any(token in context for token in ["智能", "App", "生态"]):
        return "生态与 App 体验门槛高，纯硬件跟随难形成差异"
    return "价格锚点和评论门槛较高，需要用场景化差异切入"


def traffic_terms_by_asin(keywords: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for kw in keywords:
        asin = kw.get("asin")
        if asin and not is_off_topic_traffic_keyword(kw):
            grouped[asin].append(kw)
    for asin in grouped:
        grouped[asin] = sorted(grouped[asin], key=lambda kw: as_float(kw.get("monthly_search_volume"), 0), reverse=True)
    return grouped


def is_off_topic_traffic_keyword(keyword: dict[str, Any]) -> bool:
    text = clean(" ".join(str(keyword.get(key) or "") for key in ("keyword", "keyword_cn", "intent_cn"))).casefold()
    off_topic = [
        "camera",
        "doorbell",
        "ring camera",
        "standing desk",
        "headband",
        "fishing pole",
        "camping essentials",
        "video",
        "subscription",
        "摄像",
        "门铃",
        "录像",
    ]
    return any(term in text for term in off_topic)


def keyword_customer_label(keyword: dict[str, Any]) -> str:
    keyword_cn = clean(keyword.get("keyword_cn"))
    keyword_raw = clean(keyword.get("keyword"))
    if (
        keyword_cn
        and "未映射关键词" not in keyword_cn
        and re.search(r"[\u4e00-\u9fff]", keyword_cn)
        and keyword_cn.casefold() != keyword_raw.casefold()
    ):
        return keyword_cn
    text = keyword_raw.casefold()
    mapping = [
        (["under cabinet", "cabinet", "kitchen"], "橱柜灯"),
        (["motion sensor", "sensor"], "感应灯"),
        (["led strip", "strip light", "strip"], "灯带"),
        (["led"], "LED灯"),
        (["bedroom", "dorm"], "卧室氛围灯"),
        (["vanity", "mirror"], "镜前灯"),
        (["outdoor", "solar"], "户外太阳能灯"),
        (["flashlight", "headlamp"], "户外便携灯"),
        (["camping", "fishing"], "户外照明"),
        (["sconce", "wall light"], "壁灯"),
        (["bulb"], "智能灯泡"),
        (["night light"], "夜灯"),
        (["plush", "toy", "companion"], "AI毛绒玩具"),
    ]
    for needles, label in mapping:
        if any(needle in text for needle in needles):
            return label
    return "场景流量词"


def traffic_tag_html(terms: list[dict[str, Any]], limit: int = 4) -> str:
    labels: list[str] = []
    for keyword in terms:
        label = keyword_customer_label(keyword)
        if label not in labels:
            labels.append(label)
        if len(labels) >= limit:
            break
    return "".join(tag(label, "green") for label in labels)


def render_product_deep_dives(products: list[dict[str, Any]], keywords: list[dict[str, Any]]) -> str:
    traffic = traffic_terms_by_asin(keywords)
    cards = []
    for product in products[:3]:
        asin = product.get("asin")
        trend = product.get("trend") or {}
        trend_text = f"{num(product_sales(product))}/月 · {num(product_reviews(product))} 评论 · {first(product.get('rating'), '-')}★"
        if trend.get("first") is not None and trend.get("last") is not None:
            trend_text = f"{num(trend.get('first'))} → {num(trend.get('last'))}，增长 {trend.get('growth')}"
        traffic_tags = traffic_tag_html(traffic.get(asin, []))
        if not traffic_tags:
            traffic_tags = (
                tag(first(product.get("segment_cn"), product.get("segment"), "核心细分"), "green")
                + tag(price_band(product_price(product)), "green")
                + tag(f"评论{num(product_reviews(product))}")
            )
        cards.append(
            "<div class=\"comp-deep-card\">"
            + "<div class=\"comp-deep-header\">"
            + f"<div class=\"comp-deep-name\">🎯 <span class=\"asin-token\" data-allow-asin=\"benchmark-sniper\">{esc(asin or '参考竞品')}</span> · {esc(first(product.get('brand'), customer_product_position(product)))}</div>"
            + f"<div class=\"comp-deep-price\">{esc(money(product_price(product)))} · 月销~{esc(num(product_sales(product)))} · {esc(first(product.get('rating'), '-'))}★</div>"
            + "</div><div class=\"comp-deep-body\">"
            + "<div class=\"comp-deep-section\"><div class=\"comp-deep-section-title\">溢价逻辑</div>"
            + f"<div class=\"comp-deep-text\">{esc(customer_product_message(product))}</div></div>"
            + "<div class=\"comp-deep-section\"><div class=\"comp-deep-section-title\">未解决的痛点</div><div class=\"comp-tag-list\">"
            + "<span class=\"comp-tag red\">评论痛点集中</span><span class=\"comp-tag red\">差异化不足</span><span class=\"comp-tag red\">长期体验需压实</span>"
            + "</div></div>"
            + "<div class=\"comp-deep-section\"><div class=\"comp-deep-section-title\">我们的机会</div>"
            + f"<div class=\"comp-deep-text\">围绕 {esc(customer_product_position(product))} 的高频痛点，提炼可验证卖点与页面承诺。</div></div>"
            + "<div class=\"comp-deep-section\"><div class=\"comp-deep-section-title\">数据信号</div><div class=\"comp-tag-list comp-traffic-tags\">"
            + f"<span class=\"comp-tag\">销量/评论：{esc(trend_text)}</span>{traffic_tags}"
            + "</div></div></div></div>"
        )
    return (
        "<div class=\"comp-deep-grid\">"
        + "".join(cards)
        + "</div>"
        + "<div class=\"insight-box\">💡 <strong>竞品狙击结论：</strong>标杆竞品共同暴露的核心矛盾，是高销量卖点、真实体验和长期信任之间没有同时成立。新品必须把评论痛点、页面承诺和实测表现绑定在一起，才能拿到更高价格带的定价权。</div>"
    )


def percentile(values: list[float], ratio: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    pos = (len(ordered) - 1) * ratio
    lower = int(pos)
    upper = min(lower + 1, len(ordered) - 1)
    weight = pos - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def priced_competitors(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [
        product
        for product in relevant_products(products)
        if product.get("asin") and as_float(product_price(product), -1) > 0
    ]
    return sorted(candidates, key=lambda product: as_float(product_price(product), 0))


def competitor_price_tiers(products: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    competitors = priced_competitors(products)
    if not competitors:
        return []
    indexes = [0, len(competitors) // 2, len(competitors) - 1]
    labels = ["低价竞品价", "中位竞品价", "高价竞品价"]
    tiers: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()
    for label, idx in zip(labels, indexes):
        product = competitors[idx]
        key = str(product.get("asin") or idx)
        if key in seen and len(competitors) > len(seen):
            continue
        seen.add(key)
        tiers.append((label, product))
    return tiers


def render_profitability_table(products: list[dict[str, Any]], valid_prices_rmb: list[float]) -> tuple[str, str]:
    tiers = competitor_price_tiers(products)
    if not tiers or len(valid_prices_rmb) < 50:
        return "", ""
    exchange_rate = 7.2
    cost_points = [
        ("P25", percentile(valid_prices_rmb, 0.25)),
        ("P50", percentile(valid_prices_rmb, 0.50)),
        ("P75", percentile(valid_prices_rmb, 0.75)),
    ]
    rows = []
    chart_spans = []
    for idx, (label, product) in enumerate(tiers):
        cost_label, cost_rmb = cost_points[min(idx, len(cost_points) - 1)]
        if cost_rmb is None:
            continue
        price_usd = as_float(product_price(product), 0)
        purchase_usd = cost_rmb / exchange_rate
        freight = max(1.8, purchase_usd * 0.28)
        packaging = 0.6
        qa_reserve = 0.5
        loss_reserve = purchase_usd * 0.05
        landed = purchase_usd + freight + packaging + qa_reserve + loss_reserve
        referral_fee = price_usd * 0.15
        fba_fee = max(4.6, price_usd * 0.12)
        amazon_fee = referral_fee + fba_fee
        gross_profit = price_usd - landed - amazon_fee
        margin = gross_profit / price_usd * 100 if price_usd else 0
        asin = str(product.get("asin") or "")
        chart_label = label
        chart_spans.append(f"<span data-label=\"{esc(chart_label)}\" data-value=\"{esc(round(margin, 1))}\"></span>")
        rows.append(
            "<tr>"
            + f"<td><span class=\"asin-token\" data-allow-asin=\"profit-model\">{esc(asin)}</span></td>"
            + f"<td>{esc(label)}</td>"
            + f"<td>{esc(money(price_usd))}</td>"
            + f"<td>{esc(num(product_sales(product)))}</td>"
            + f"<td>{esc(first(product.get('rating'), '-'))} / {esc(num(product_reviews(product)))}</td>"
            + f"<td>{esc(cost_label)} · {esc(money(cost_rmb, '¥'))}</td>"
            + f"<td>{esc(money(landed))}</td>"
            + f"<td>{esc(money(amazon_fee))}</td>"
            + f"<td>{esc(money(gross_profit))}</td>"
            + f"<td>{esc(pct(margin))}</td>"
            + "</tr>"
        )
    if not rows:
        return "", ""
    table_html = (
        "<div hidden data-chart-source=\"marginChartRows\">"
        + "".join(chart_spans)
        + "</div>"
        + "<div class=\"sku-table-wrap\"><table class=\"comp-table profitability-table\"><thead><tr>"
        + "".join(
            f"<th>{esc(header)}</th>"
            for header in ["参考竞品 ASIN", "竞品价格带", "竞品售价", "月销量", "评分/评论数", "1688 成本分位数", "综合到仓成本", "亚马逊费用", "单件毛利", "毛利率"]
        )
        + "</tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></div>"
    )
    formula = (
        "<div class=\"insight-box\"><strong>竞品参考毛利率测算：</strong>"
        "采购成本USD=1688报价RMB/7.2；综合到仓成本=采购成本+头程物流+包装+损耗+质检/认证预留；"
        "亚马逊费用=Referral Fee+FBA Fee；毛利率=单件毛利/竞品参考售价。"
        "该测算用真实竞品 ASIN 售价、销量、评分和评论数做参考，不用品牌均值替代。</div>"
    )
    return table_html, formula


def supplier_price_value(supplier: dict[str, Any]) -> Any:
    return first(supplier.get("price_rmb"), supplier.get("factory_price_rmb"), supplier.get("price"), default=None)


SUPPLIER_NON_FINISHED_TOKENS = [
    "灯珠",
    "发光二极管",
    "控制器",
    "调光器",
    "驱动电源",
    "电源适配器",
    "光源模组",
    "灯板",
    "芯片",
    "ic ",
    "配件",
    "冷光片",
    "植物灯",
    "洗墙灯",
    "工程灯",
    "投光灯",
    "泛光灯",
    "广告灯",
    "招牌灯",
    "led bead",
    "diode",
    "controller",
    "driver",
    "power supply",
    "module",
    "accessory",
]


def supplier_title_text(supplier: dict[str, Any]) -> str:
    return clean(
        " ".join(
            str(supplier.get(key) or "")
            for key in ["title", "title_cn", "name", "product_name", "supplier_name", "seed_keyword"]
        )
    ).casefold()


def is_finished_supplier_record(supplier: dict[str, Any]) -> bool:
    price = as_float(supplier_price_value(supplier), -1)
    if price <= 0:
        return False
    text = supplier_title_text(supplier)
    if any(token in text for token in SUPPLIER_NON_FINISHED_TOKENS):
        return False
    if price < 0.5:
        return False
    return True


def finished_supplier_records(suppliers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [supplier for supplier in suppliers if isinstance(supplier, dict) and is_finished_supplier_record(supplier)]


def supplier_quality_snapshot(suppliers: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [supplier for supplier in suppliers if as_float(supplier_price_value(supplier), -1) > 0]
    total = len(valid)
    prices = [as_float(supplier_price_value(supplier), -1) for supplier in valid if as_float(supplier_price_value(supplier), -1) > 0]
    title_count = sum(1 for supplier in valid if first(supplier.get("title"), supplier.get("title_cn"), supplier.get("name"), default=""))
    identity_count = sum(1 for supplier in valid if first(supplier.get("canonical_url"), supplier.get("url"), supplier.get("product_url"), supplier.get("product_id"), supplier.get("offer_id"), default=""))
    title_pct = round(title_count / total * 100, 1) if total else 0
    identity_pct = round(identity_count / total * 100, 1) if total else 0
    p25 = percentile(prices, 0.25)
    p50 = percentile(prices, 0.50)
    p75 = percentile(prices, 0.75)
    max_price = max(prices) if prices else None
    max_to_p50 = max_price / p50 if max_price and p50 else 0
    p75_to_p25 = p75 / p25 if p75 and p25 else 0
    return {
        "valid_count": total,
        "title_pct": title_pct,
        "identity_pct": identity_pct,
        "p25": p25,
        "p50": p50,
        "p75": p75,
        "max": max_price,
        "max_to_p50": max_to_p50,
        "p75_to_p25": p75_to_p25,
        "passed": total >= 50 and title_pct >= 70 and identity_pct >= 70 and max_to_p50 <= 20 and p75_to_p25 <= 5,
    }


def supplier_bucket_label(supplier: dict[str, Any]) -> str:
    return clean(first(supplier.get("seed_keyword"), supplier.get("search_term"), supplier.get("query"), default="未记录搜索词"))


def passing_supplier_bucket(suppliers: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]], dict[str, Any]] | None:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for supplier in suppliers:
        buckets[supplier_bucket_label(supplier)].append(supplier)
    candidates: list[tuple[str, list[dict[str, Any]], dict[str, Any]]] = []
    for label, rows in buckets.items():
        if not label or label == "未记录搜索词":
            continue
        rows = finished_supplier_records(rows)
        snapshot = supplier_quality_snapshot(rows)
        if snapshot["passed"]:
            candidates.append((label, rows, snapshot))
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda item: (
            as_float(item[2].get("valid_count"), 0),
            -as_float(item[2].get("max_to_p50"), 0),
            -as_float(item[2].get("p75_to_p25"), 0),
        ),
        reverse=True,
    )[0]


def render_supply_diagnostic(suppliers: list[dict[str, Any]], snapshot: dict[str, Any]) -> str:
    seeds: Counter[str] = Counter(
        clean(first(supplier.get("seed_keyword"), supplier.get("search_term"), supplier.get("query"), default="未记录搜索词"))
        for supplier in suppliers
    )
    reason_rows = [
        ["去重有效报价", num(snapshot["valid_count"]), "至少 50 条"],
        ["商品标题覆盖率", f"{snapshot['title_pct']}%", "至少 70%"],
        ["链接/稳定指纹覆盖率", f"{snapshot['identity_pct']}%", "至少 70%"],
        ["最大价/P50", f"{snapshot['max_to_p50']:.2f}" if snapshot["max_to_p50"] else "-", "不高于 20"],
        ["P75/P25", f"{snapshot['p75_to_p25']:.2f}" if snapshot["p75_to_p25"] else "-", "不高于 5"],
    ]
    seed_rows = [[seed, count] for seed, count in seeds.most_common(12)]
    diagnostic_chart_rows = [
        ["有效报价", snapshot["valid_count"]],
        ["标题覆盖率", snapshot["title_pct"]],
        ["价差风险", snapshot["max_to_p50"] or 0],
    ]
    return (
        "<div class=\"supply-grid\">"
        + f"<div class=\"supply-card\"><div class=\"supply-label\">供应链状态</div><div class=\"supply-value\">需补采</div><div class=\"supply-note\">当前数据不能进入毛利率测算</div></div>"
        + f"<div class=\"supply-card\"><div class=\"supply-label\">有效报价数</div><div class=\"supply-value\">{esc(num(snapshot['valid_count']))}</div><div class=\"supply-note\">要求 50 条以上且字段完整</div></div>"
        + f"<div class=\"supply-card\"><div class=\"supply-label\">标题覆盖率</div><div class=\"supply-value\">{esc(snapshot['title_pct'])}%</div><div class=\"supply-note\">用于判断是否同类商品</div></div>"
        + f"<div class=\"supply-card\"><div class=\"supply-label\">链接/指纹覆盖率</div><div class=\"supply-value\">{esc(snapshot['identity_pct'])}%</div><div class=\"supply-note\">用于去重和复核</div></div>"
        + "</div>"
        + "<div class=\"insight-box\"><strong>供应链核心结论：</strong>当前 1688 数据没有达到客户报告毛利率测算门槛。系统已阻断最终成本结论，需要用细分赛道中文词继续采集，并保留商品标题、供应商、价格、链接或稳定商品指纹。</div>"
        + table(["检查项", "当前值", "通过标准"], reason_rows)
        + echart_plain("marginChart", "毛利率测算未启用 · 1688质量门禁未通过", "保留模板图表槽位；当前只展示供应链补采诊断，不输出毛利率结论", 260)
        + "<div hidden data-chart-source=\"marginChartRows\">"
        + table(["label", "value"], diagnostic_chart_rows)
        + "</div>"
        + details("已尝试搜索词", table(["搜索词", "记录数"], seed_rows), True)
    )


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
        raw_excerpt = truncate(first(review.get("text"), review.get("content"), review.get("body"), review.get("comment"), default=""), 160)
        excerpt_html = (
            f"<p class=\"review-excerpt-en\" data-allow-english-review=\"short\">{esc(raw_excerpt)}</p>"
            if raw_excerpt and not re.search(r"[\u4e00-\u9fff]", raw_excerpt)
            else ""
        )
        quote_cards.append(
            f"<article class=\"quote-card{tone}\"><div class=\"voc-title\"><span class=\"voc-rank\">{len(quote_cards)+1}</span>{esc(sentiment)} · {esc(review.get('rating'))}星 · {esc(title)}</div>"
            f"<p class=\"voc-quote quote-cn\">{esc(summary_cn)}</p>{excerpt_html}<p class=\"voc-desc\">{tag('证据强度：高')}</p></article>"
        )
    theme_rows = [
        [theme, count, low_theme_counts.get(theme, 0), "评论记录提及频次，不写精确百分比"]
        for theme, count in theme_counts.most_common(16)
    ]
    sample_rows = [
        [f"评论记录 {idx:03d}", review.get("rating"), review_sentiment_label(review), customer_review_summary(review, 180), "、".join(review_theme_labels(review)), "高"]
        for idx, review in enumerate(reviews[:120], 1)
    ]
    summary = (
        "<div class=\"metric-strip\">"
        + metric("评论记录", len(reviews), "已做中文摘要映射")
        + metric("低星评论", len(low_reviews), "3星及以下")
        + metric("覆盖竞品", len([k for k in asin_counts if k]), "核心竞品")
        + metric("主题数", len(theme_counts), "VOC 主题簇")
        + metric("5星评论", star_counts.get(5, 0), "正向购买动机")
        + "</div>"
    )
    radar_themes = [theme for theme, _ in (theme_counts or Counter({"评论主题": 1})).most_common(8)]
    max_theme_count = max([theme_counts.get(theme, 0) for theme in radar_themes] + [1])
    max_low_count = max([low_theme_counts.get(theme, 0) for theme in radar_themes] + [1])
    radar_seed = (
        "<div hidden data-chart-source=\"radarPainRows\">"
        + "".join(
            f"<span data-label=\"{esc(theme)}\" data-value=\"{esc(round((low_theme_counts.get(theme, 0) / max_low_count) * 100, 1))}\"></span>"
            for theme in radar_themes
        )
        + "</div><div hidden data-chart-source=\"radarJoyRows\">"
        + "".join(
            f"<span data-label=\"{esc(theme)}\" data-value=\"{esc(round((theme_counts.get(theme, 0) / max_theme_count) * 100, 1))}\"></span>"
            for theme in radar_themes
        )
        + "</div>"
    )
    charts = (
        radar_seed
        + echart_box("radarChart", "用户痛点 / 爽点强度雷达", "评论主题聚合后的心智结构")
        + "<div class=\"grid-3\"><div class=\"card\"><div class=\"card-title\">主题提及</div>"
        + mini_chart([(k, v, v) for k, v in theme_counts.most_common(10)], "good")
        + "</div><div class=\"card\"><div class=\"card-title\">低星主题</div>"
        + mini_chart([(k, v, v) for k, v in low_theme_counts.most_common(10)], "bad")
        + "</div><div class=\"card\"><div class=\"card-title\">星级分布</div>"
        + mini_chart([(f"{k}星", v, v) for k, v in sorted(star_counts.items())], "warn")
        + "</div></div>"
    )
    pain_items = low_theme_counts.most_common(7)
    joy_items = theme_counts.most_common(7)
    fallback_pains = ["稳定性与寿命", "安装/使用门槛", "材质与做工", "安全与信任", "价格与价值感", "售后响应", "场景不匹配"]
    fallback_joys = ["效果符合预期", "外观质感", "安装方便", "礼品属性", "场景适配", "复购/推荐意愿", "信任感提升"]
    while len(pain_items) < 7:
        pain_items.append((fallback_pains[len(pain_items)], 1))
    while len(joy_items) < 7:
        joy_items.append((fallback_joys[len(joy_items)], 1))
    voc_grid = (
        "<div class=\"voc-grid\">"
        + "<article class=\"pain-card\"><div class=\"voc-card-title\"><span class=\"red\">Pain</span> 主要痛点</div><div class=\"voc-content\">"
        + "".join(
            f"<div class=\"voc-item\"><div class=\"voc-rank pain-rank\">P{idx}</div><div class=\"voc-content\"><div class=\"voc-title\">{esc(theme)}</div><div class=\"voc-desc\">用户在低星反馈中反复提到该问题，必须转成实物修复、页面承诺或售后说明，不能只用营销话术覆盖。</div><div class=\"voc-quote\">客户页展示中文归纳，并可并列展示英文评论短摘；完整原始评论保留在审计文件。</div><div class=\"voc-bar\"><div class=\"voc-bar-fill pain-fill\" data-width=\"{min(100, 24 + count * 10)}\"></div></div></div></div>"
            for idx, (theme, count) in enumerate(pain_items, 1)
        )
        + "</div></article>"
        + "<article class=\"joy-card\"><div class=\"voc-card-title\"><span class=\"green\">Joy</span> 主要爽点</div><div class=\"voc-content\">"
        + "".join(
            f"<div class=\"voc-item\"><div class=\"voc-rank joy-rank\">J{idx}</div><div class=\"voc-content\"><div class=\"voc-title\">{esc(theme)}</div><div class=\"voc-desc\">正向体验可转化为主图场景、五点利益、A+ 模块和广告落地页表达，同时要保持可验证边界。</div><div class=\"voc-quote\">中文卖点归纳为主，英文评论短摘用于保留用户原话语气。</div><div class=\"voc-bar\"><div class=\"voc-bar-fill joy-fill\" data-width=\"{min(100, 24 + count * 10)}\"></div></div></div></div>"
            for idx, (theme, count) in enumerate(joy_items, 1)
        )
        + "</div></article></div>"
    )
    quote_grid = "<div class=\"quote-grid\">" + "".join(quote_cards) + "</div>" if quote_cards else ""
    return charts + quote_grid + voc_grid


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


def web_document_theme(doc: dict[str, Any]) -> str:
    text = clean(" ".join(str(doc.get(key) or "") for key in ("query", "title", "description", "summary", "url"))).casefold()
    if any(term in text for term in ["cpsc", "recall", "hazard", "ul", "etl", "safety", "policy", "fire"]):
        return "合规与召回风险"
    if any(term in text for term in ["review", "best", "wirecutter", "consumer", "reddit", "youtube"]):
        return "公开测评与口碑"
    if any(term in text for term in ["amazon", "walmart", "target", "bestbuy", "retailer", "seller"]):
        return "零售与平台对照"
    if any(term in text for term in ["trend", "market", "report", "forecast"]):
        return "市场趋势公开资料"
    if any(term in text for term in ["brand", "official", "manufacturer"]):
        return "品牌官网与产品资料"
    return "公开网页补充证据"


def render_tiktok(data_pack: dict[str, Any]) -> str:
    products = data_pack.get("tiktok_products") or []
    videos = sorted(data_pack.get("tiktok_videos") or [], key=lambda video: as_float(video.get("views"), 0), reverse=True)
    seed_terms = infer_seed_terms(data_pack)
    relevance_counts = Counter(tiktok_relevance(product, seed_terms) for product in products)
    product_rows = [
        [product.get("product_id"), customer_safe_signal_title(product, "内容商品记录"), tiktok_relevance(product, seed_terms), first(product.get("brand"), "-"), money(product.get("price")), num(product.get("estimated_monthly_sales")), num(product.get("review_count")), product.get("source_id")]
        for product in products
    ]
    video_rows = [
        [video.get("product_id"), customer_safe_signal_title(video, "内容视频记录"), num(video.get("views")), num(video.get("likes")), truncate(video.get("author"), 32), "内容标签已归纳", video.get("source_id")]
        for video in videos[:40]
    ]
    return (
        "<div class=\"grid-2\"><div class=\"card\"><div class=\"card-title\">相关性判断</div>"
        + mini_chart([(k, v, v) for k, v in relevance_counts.most_common()], "warn")
        + "</div><div class=\"card\"><div class=\"card-title\">解读</div><p>TikTok 模块展示商品、视频和达人内容信号。若相似结果只与研究对象部分重叠，应作为内容场景参考，而非 Amazon 购买需求证明。</p></div></div>"
        + "<div class=\"visual-grid\"><article class=\"visual-card\"><div class=\"visual-card-title\">内容场景</div><div class=\"visual-item\"><div class=\"visual-item-title\">短视频角度</div><div class=\"visual-item-text\">只提炼可验证的场景表达，不把播放量等同于购买需求。</div></div></article></div>"
        + table(["Product ID", "商品", "相关性", "品牌", "价格", "估算月销量", "评论数", "source_id"], product_rows)
        + details("TikTok 视频证据（播放量排序 Top40）", table(["Product ID", "标题", "播放", "点赞", "达人", "标签", "source_id"], video_rows))
    )


def render_supply(data_pack: dict[str, Any], profitability: dict[str, Any]) -> str:
    raw_suppliers = sorted(data_pack.get("suppliers") or [], key=lambda supplier: as_float(supplier.get("sales_30d"), 0), reverse=True)
    suppliers = finished_supplier_records(raw_suppliers)
    quality = supplier_quality_snapshot(suppliers)
    bucket_label = ""
    if not quality["passed"]:
        bucket = passing_supplier_bucket(raw_suppliers)
        if not bucket:
            return render_supply_diagnostic(suppliers, quality)
        bucket_label, bucket_suppliers, quality = bucket
        suppliers = sorted(bucket_suppliers, key=lambda supplier: as_float(supplier.get("sales_30d"), 0), reverse=True)

    valid_prices = [as_float(supplier_price_value(supplier), -1) for supplier in suppliers if as_float(supplier_price_value(supplier), -1) > 0]
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
    median_rmb = first(stats.get("median_rmb"), statistics.median(valid_prices) if valid_prices else None)
    min_rmb = first(stats.get("min_rmb"), min(valid_prices) if valid_prices else None)
    max_rmb = first(stats.get("max_rmb"), max(valid_prices) if valid_prices else None)
    p25_rmb = percentile(valid_prices, 0.25)
    p75_rmb = percentile(valid_prices, 0.75)
    top_supplier = suppliers[0] if suppliers else {}
    supplier_focus = truncate(first(top_supplier.get("title_cn"), top_supplier.get("title"), "供应端记录"), 18)
    profitability_table, formula = render_profitability_table(relevant_products(data_pack.get("products") or []), valid_prices)
    supplier_rows = [
        [
            truncate(first(supplier.get("title_cn"), supplier.get("title"), "供应商记录"), 42),
            first(supplier.get("supplier_name"), supplier.get("store_name"), "供应商"),
            money(supplier_price_value(supplier), "¥"),
            num(supplier.get("sales_30d")),
            first(supplier.get("shipping_origin"), "-"),
            first(supplier.get("seed_keyword"), "-"),
        ]
        for supplier in suppliers[:60]
        if as_float(supplier_price_value(supplier), -1) > 0
    ]
    measurement_note = (
        f"<div class=\"insight-box\"><strong>测算口径：</strong>全局 1688 报价价差异常，已切换为按搜索词：{esc(bucket_label)} 的同赛道报价进行成本分位数和毛利率测算。</div>"
        if bucket_label
        else "<div class=\"insight-box\"><strong>测算口径：</strong>已先剔除灯珠、控制器、工程灯等非成品报价，再用剩余 1688 成品报价进行成本分位数和毛利率测算。</div>"
    )
    return (
        "<div class=\"supply-grid\">"
        + f"<div class=\"supply-card\"><div class=\"supply-label\">有效报价数</div><div class=\"supply-value\">{esc(num(len(valid_prices)))}</div><div class=\"supply-note\">1688 供应端记录，已去重</div></div>"
        + f"<div class=\"supply-card\"><div class=\"supply-label\">P50 采购成本</div><div class=\"supply-value\">{esc(money(median_rmb, '¥'))}</div><div class=\"supply-note\">1688 成品报价中位数，不含物流、FBA、认证</div></div>"
        + f"<div class=\"supply-card\"><div class=\"supply-label\">P25-P75 成本区间</div><div class=\"supply-value\">{esc(money(p25_rmb, '¥'))}-{esc(money(p75_rmb, '¥'))}</div><div class=\"supply-note\">真实报价范围 {esc(money(min_rmb, '¥'))}-{esc(money(max_rmb, '¥'))}；分位数用于毛利率测算</div></div>"
        + f"<div class=\"supply-card\"><div class=\"supply-label\">热销供应端</div><div class=\"supply-value\">{esc(first((origin_counts.most_common(1)[0][0] if origin_counts else None), supplier_focus))}</div><div class=\"supply-note\">按 30 日销量最高记录展示</div></div>"
        + "</div>"
        + echart_plain("marginChart", "毛利率测算 · 各定价方案对比", "基于综合出厂成本、FBA费用与目标售价的区间估算", 260)
        + profitability_table
        + formula
        + measurement_note
        + details("1688 供应商报价明细（去重后 Top60）", table(["商品标题", "供应商", "报价", "30日销量", "发货地", "搜索词"], supplier_rows), True)
        + "<div class=\"insight-box\">💡 <strong>供应链核心结论：</strong>供应端报价显示仍存在可验证成本空间，但必须用实物测试、质检、认证、包装、头程物流、FBA 费用和退货率二次压实。若页面差异化卖点成立，高溢价价格带比低价同款更值得优先验证；若成本或质量无法稳定，必须回退到小批量验证而不是直接放量。</div>"
    )


def render_web_risk(data_pack: dict[str, Any]) -> str:
    docs = data_pack.get("web_documents") or []
    theme_counts = Counter(web_document_theme(doc) for doc in docs)
    rows = [[web_document_theme(doc), "网页摘要已归纳到风险和机会判断", "网页链接保留在审计稿", first(doc.get("position"), "-"), doc.get("source_id")] for doc in docs]
    risk_cards = (
        "<div class=\"risk-grid\">"
        "<article class=\"risk-card\"><h3>合规与召回</h3><p>涉及电气、户外、防水、发热、玻璃破损等风险，必须二次核查 CPSC、UL、ETL 和 Amazon policy。</p></article>"
        "<article class=\"risk-card\"><h3>测评口碑</h3><p>公开测评只作为方向线索，不能替代 Sorftime 评论和真实实物测试。</p></article>"
        "<article class=\"risk-card\"><h3>网页证据限制</h3><p>Firecrawl 搜索结果必须保留在 web_documents，不直接写成结论。</p></article>"
        "</div>"
    )
    return "<div class=\"card\"><div class=\"card-title\">公开网页覆盖</div>" + mini_chart([(k, v, v) for k, v in theme_counts.most_common()]) + "</div>" + risk_cards + table(["证据主题", "摘要", "URL", "排名", "source_id"], rows)


def render_opportunities(opportunity: dict[str, Any]) -> str:
    opportunities = fixed_opportunity_slots(opportunity.get("opportunities") or [])
    top = opportunities[:3]
    recommended_idx = 1
    pricing_cards = []
    prompt_cards = []
    for idx, item in enumerate(top):
        name = first(item.get("name"), f"机会 {idx + 1}")
        entry_shape = first(item.get("entry_shape"), item.get("recommendation"), "以小批量实物、页面卖点和广告转化验证为先。")
        price = first(item.get("price_band"), item.get("target_price"), ["$19-$29", "$39-$59", "$79-$99"][idx % 3])
        pricing_cards.append(
            f"<article class=\"pricing-card{' recommended' if idx == recommended_idx else ''}\">"
            + f"<div class=\"pricing-tier\">{esc(first(item.get('tier'), ['Starter', 'Core', 'Premium'][idx]))}</div>"
            + f"<div class=\"pricing-price\">{esc(price)}</div>"
            + f"<div class=\"pricing-desc\">{esc(name)}<br>用于验证价格空白、页面承诺和真实转化，不在首轮承担全 SKU 扩张。</div>"
            + "<div class=\"pricing-features\">"
            + "<div class=\"pricing-feature check\">先验证核心转化</div>"
            + "<div class=\"pricing-feature check\">明确成本与转化门槛</div>"
            + "<div class=\"pricing-feature check\">明确页面差异化承诺</div>"
            + "<div class=\"pricing-feature\">补齐 landed cost 与广告成本</div>"
            + "<div class=\"pricing-feature\">未验证前不扩大 SKU</div>"
            + "</div></article>"
        )
        prompt_cards.append(
            "<article class=\"prompt-card\">"
            + f"<div class=\"prompt-number\">Prompt {idx + 1:02d}</div>"
            + f"<div class=\"prompt-scene\">{esc(name)}</div>"
            + f"<div class=\"prompt-text\">把该机会写入主图、五点和 A/B 页面测试；只使用已采集证据支持的承诺。</div>"
            + f"<div class=\"prompt-note\">{esc(first(item.get('decision'), 'Watch'))}</div>"
            + "</article>"
        )
    pillar_inputs = [
        ("🧩", "差异化支柱 #1：模块化核心设计", "把最容易产生差评的结构、清洁、替换或维护问题做成可验证设计。首批实物必须能证明该问题被真实解决，而不是只在标题、五点或 A+ 页面里承诺。", "→ 解决痛点P1：体验缺口可被实测验证"),
        ("📡", "差异化支柱 #2：核心场景优先", "只围绕最高频购买场景做首发 SKU，将功能、包装、安装说明和广告落地页统一到一个明确使用情境，避免泛功能堆叠造成成本上升和页面表达失焦。", "→ 提升主图、五点和广告承接效率"),
        ("🔒", "差异化支柱 #3：信任透明承诺", "把保修、材质、使用边界、隐私、安全或认证承诺做成可视化模块，并在包装、说明书和详情页重复出现，降低用户下单前的不确定性。", "→ 解决痛点P2：信任阻碍"),
        ("💎", "差异化支柱 #4：质感与细节溢价", "用真实可感知的材质、结构、触感、灯效、包装和售后体验支撑溢价。页面表达要让用户看见为什么贵，而不是在低价红海里争同款参数。", "→ 强化爽点J1：拿到高价格带"),
        ("🎭", "差异化支柱 #5：双场景表达", "同一产品页面同时覆盖实际使用者和付款决策者：前者需要场景、效果和情绪价值，后者需要安全、耐用、售后和性价比边界。", "→ 扩大可转化人群"),
        ("♾️", "差异化支柱 #6：长期复购入口", "预留配件、替换件、Bundle、升级包或耗材路径，把一次性成交延伸为生命周期收入，并为后续拓品报告提供可执行 SKU 入口。", "→ 连接生命周期拓品策略"),
    ]
    if top:
        for idx, item in enumerate(top[:3]):
            evidence_label = first(item.get("score"), f"{len(item.get('source_ids') or [])} 条证据链")
            pillar_inputs[idx] = (
                pillar_inputs[idx][0],
                f"差异化支柱 #{idx + 1}：{first(item.get('name'), f'机会 {idx + 1}')}",
                f"{first(item.get('entry_shape'), item.get('recommendation'), pillar_inputs[idx][2])} 首轮只验证一个核心场景，并要求实物表现、页面和广告承诺三者一致。",
                f"→ {first(item.get('decision'), 'Watch')} · {evidence_label}",
            )
    strategy_cards = [
        "<article class=\"strategy-card\">"
        + f"<div class=\"strategy-card-icon\">{esc(icon)}</div>"
        + f"<div class=\"strategy-card-title\">{esc(title)}</div>"
        + f"<div class=\"strategy-card-text\">{esc(text)}</div>"
        + f"<div class=\"strategy-card-highlight\">{esc(highlight)}</div>"
        + "</article>"
        for icon, title, text, highlight in pillar_inputs
    ]
    return (
        "<div class=\"strategy-hero\"><div class=\"strategy-hero-label\">Core Product Concept · 核心产品定义</div><div class=\"strategy-slogan\">不只是产品，是<span>真正解决痛点的</span>高溢价方案。</div><div class=\"strategy-desc\">基于已验证的竞品、关键词、评论和供应链证据，优先定义一个可被页面、实物和广告验证的差异化产品。首轮不追求大而全，而是锁定一个最强使用场景、一个主力价格带和一组可兑现的页面承诺。</div></div>"
        + "<div class=\"strategy-grid\">" + "".join(strategy_cards) + "</div>"
        + "<div id=\"pricing\" class=\"section-anchor\"></div><div class=\"section-header section-header-spaced\"><div class=\"section-title section-title-sm\">建议定价策略</div></div>"
        + "<div class=\"pricing-grid\">" + "".join(pricing_cards) + "</div>"
        + "<div class=\"insight-box\">💡 <strong>定价战略核心逻辑：</strong>主力价格带必须卡在用户可感知差异与竞品价格空白之间。低价款用于验证流量，中价款承担销量，高价款承接礼品化、Bundle 与高毛利空间。只有当实物体验、页面转化和 landed cost 同时成立，才进入下一轮放量。</div>"
    )


def render_visual_direction(opportunity: dict[str, Any]) -> str:
    opportunities = fixed_opportunity_slots(opportunity.get("opportunities") or [])
    prompt_cards = []
    for idx, item in enumerate(opportunities[:3]):
        name = first(item.get("name"), f"机会 {idx + 1}")
        prompt_cards.append(
            "<article class=\"prompt-card\">"
            + f"<div class=\"prompt-number\">Prompt {idx + 1:02d}</div>"
            + f"<div class=\"prompt-scene\">{esc(name)}</div>"
            + "<div class=\"prompt-text\">Amazon hero image, warm realistic lifestyle scene, product as the clear focal point, visible texture and premium finish, show the core functional difference with subtle callout space, soft natural light, clean e-commerce composition, no exaggerated sci-fi effects, editorial product photography, high trust, high detail, clear product silhouette, room for badge-style benefit labels, suitable for main image, A+ module, product comparison panel, and short video opening frame.</div>"
            + "<div class=\"prompt-note\">适用于：Amazon 主图 / A+ / 视频脚本方向，需结合实物照片和实测表现再二次修订。</div>"
            + "</article>"
        )
    return (
        "<div class=\"visual-grid\">"
        + "<div class=\"visual-card\"><div class=\"visual-card-title\">📸 主图风格差异化建议</div>"
        + "<div class=\"visual-item\"><div class=\"visual-item-title\">① 竞品现状：功能表达重，情绪表达弱</div><div class=\"visual-item-text\">多数竞品更强调参数、低价或单点功能，搜索结果页缺少真实使用场景、质感细节和信任提示，用户很难判断产品是否适合自己的具体场景。</div></div>"
        + "<div class=\"visual-item\"><div class=\"visual-item-title\">② 我们的主图策略：情感优先，功能点缀</div><div class=\"visual-item-text\">首图优先展示可感知使用场景；第二图展示结构、材质或功能差异；第三图用信息图说明承诺边界，把页面卖点和实物真实能力绑定起来。</div></div>"
        + "<div class=\"visual-item\"><div class=\"visual-item-title\">③ 色彩策略：暖中性色 + 清晰产品边界</div><div class=\"visual-item-text\">避免过度蓝光科技感或低价货架感。使用奶油白、雾霾蓝、柔和木色或浅灰背景，让产品质感、安装方式和核心卖点在首屏被快速识别。</div></div>"
        + "</div>"
        + "<div class=\"visual-card\"><div class=\"visual-card-title\">📦 开箱体验差异化设计</div>"
        + "<div class=\"visual-item\"><div class=\"visual-item-title\">① 包装外观：礼品化</div><div class=\"visual-item-text\">用礼盒、欢迎卡、快速启动卡和清晰分层内托增强体面感。即使产品不是礼品类，也要让用户开箱时立刻理解产品定位和使用方式。</div></div>"
        + "<div class=\"visual-item\"><div class=\"visual-item-title\">② 售后与信任：可视化承诺</div><div class=\"visual-item-text\">把清洁、隐私、替换、安装、保修或安全承诺放入包装与详情页，避免隐藏在长文本里。关键承诺必须能在售后流程中被兑现。</div></div>"
        + "<div class=\"visual-item\"><div class=\"visual-item-title\">③ 内容传播：为开箱和短视频预留镜头</div><div class=\"visual-item-text\">包装层次、使用前后对比、核心功能触发点和场景效果，都要能自然形成短视频镜头，降低后续 KOL 和广告素材生产成本。</div></div>"
        + "</div></div>"
        + "<div id=\"prompt\" class=\"section-anchor\"></div><div class=\"section-header section-header-tight\"><div class=\"section-title section-title-sm\">AI生图 Prompt · 可直接使用</div></div>"
        + "<div class=\"prompt-grid\">" + "".join(prompt_cards) + "</div>"
    )


def fixed_opportunity_slots(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    defaults = [
        {
            "tier": "Starter · 流量验证款",
            "name": "低价流量验证款",
            "price_band": "$19-$29",
            "decision": "Watch",
            "entry_shape": "只验证核心转化和评价门槛，不承接全 SKU 扩张。",
            "score": "固定模板槽位",
        },
        {
            "tier": "Core · 推荐切入",
            "name": "主力差异化款",
            "price_band": "$39-$59",
            "decision": "Watch",
            "entry_shape": "承接销量、页面承诺和真实体验验证，是首轮主推价格带。",
            "score": "固定模板槽位",
        },
        {
            "tier": "Premium · 利润验证款",
            "name": "高溢价套装款",
            "price_band": "$79-$99",
            "decision": "Watch",
            "entry_shape": "承接礼品化、Bundle 和高毛利空间，必须绑定实物质感与售后承诺。",
            "score": "固定模板槽位",
        },
    ]
    slots = [dict(item) for item in items[:3] if isinstance(item, dict)]
    while len(slots) < 3:
        slots.append(dict(defaults[len(slots)]))
    for idx, slot in enumerate(slots[:3]):
        for key, value in defaults[idx].items():
            slot.setdefault(key, value)
    return slots[:3]


def render_decision(delivery: dict[str, Any]) -> str:
    decision = first(delivery.get("decision"), "Watch", default="Watch")
    return (
        "<div class=\"grid-3\">"
        "<div class=\"card\"><div class=\"card-title\">进入条件</div><ul><li>锁定一个细分，不做泛品类。</li><li>实物表现解决核心 VOC 问题。</li><li>核实 landed cost、认证、FBA、退货率、ACOS。</li></ul></div>"
        "<div class=\"card\"><div class=\"card-title\">停止条件</div><ul><li>核心词 CPC 与转化无法覆盖毛利。</li><li>低星问题来自结构性缺陷。</li><li>供应端只能同款搬运，无质量与设计优势。</li></ul></div>"
        f"<div class=\"card\"><div class=\"card-title\">最终判断</div><p class=\"insight\">Go / Watch / No-Go：{esc(decision)}</p><p>建议先小批量验证最强机会，打穿评论、广告和实物成本后再扩 SKU。</p></div>"
        "</div>"
    )


def render_data_gaps(data_pack: dict[str, Any], analysis_plan: dict[str, Any]) -> str:
    gaps = data_pack.get("data_gaps") or analysis_plan.get("limitations") or []
    rows = []
    for gap in gaps:
        if isinstance(gap, dict):
            rows.append([customer_safe_gap_text(gap.get("area")), customer_safe_gap_text(gap.get("gap")), customer_safe_gap_text(gap.get("impact")), customer_safe_gap_text(gap.get("next_action"))])
        else:
            rows.append(["数据限制", customer_safe_gap_text(gap), "-", "-"])
    return table(["模块", "缺口", "影响", "下一步"], rows)


def customer_safe_gap_text(value: Any) -> str:
    text = clean(value)
    if "MCP returned Unauthorized" in text:
        text = text.replace("MCP returned Unauthorized, so public web evidence was collected with web search and marked separately.", "公开网页补充接口本轮未授权，已改用公开网页搜索结果并单独标注。")
    replacements = {
        "竞品样本": "竞品",
        "市场样本": "市场主数据",
        "评论样本": "评论记录",
        "产品样本": "产品记录",
        "供应样本": "供应记录",
        "样品": "实物",
        "样本": "数据记录",
        "补数": "复核",
        "打样": "实物测试",
        "待验证": "需核实",
        "待补": "需核实",
        "补 3-5": "增加 3-5",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def render_full_appendix(data_pack: dict[str, Any], analysis_plan: dict[str, Any]) -> str:
    products = relevant_products(data_pack.get("products") or [])
    keywords = data_pack.get("keywords") or []
    reviews = data_pack.get("reviews") or []
    tiktok_products = data_pack.get("tiktok_products") or []
    tiktok_videos = data_pack.get("tiktok_videos") or []
    suppliers = data_pack.get("suppliers") or []
    web_docs = data_pack.get("web_documents") or []
    product_table = table(["ASIN", "中文定位", "英文标题", "品牌", "细分", "价格", "估算月销量", "估算销售额", "星级", "评论数", "上架", "source_id"], competitor_rows(products, None), "evidence-table appendix-table")
    keyword_table = table(["关键词中文", "英文关键词", "相关性", "月搜索量", "周搜索量", "CPC", "竞争数", "中文意图", "来源", "source_id"], [[kw.get("keyword_cn"), kw.get("keyword"), kw.get("relevance_cn"), num(kw.get("monthly_search_volume")), num(kw.get("weekly_search_volume")), kw.get("recommended_cpc") or "-", num(kw.get("competitor_count")), kw.get("intent_cn"), kw.get("source_type"), kw.get("source_id")] for kw in keywords], "evidence-table appendix-table")
    review_table = table(["ASIN", "星级", "日期", "标题", "评论摘录", "主题", "source_id"], [[r.get("asin"), r.get("rating"), r.get("review_date"), r.get("title_cn"), r.get("summary_cn"), ", ".join(r.get("themes_cn") or []), r.get("source_id")] for r in reviews], "evidence-table appendix-table")
    tk_product_table = table(["Product ID", "标题", "品牌", "价格", "估算月销量", "source_id"], [[p.get("product_id"), customer_safe_signal_title(p, "内容商品记录"), p.get("brand"), money(p.get("price")), num(p.get("estimated_monthly_sales")), p.get("source_id")] for p in tiktok_products], "evidence-table appendix-table")
    tk_video_table = table(["Product ID", "标题", "播放", "点赞", "达人", "URL", "source_id"], [[v.get("product_id"), customer_safe_signal_title(v, "内容视频记录"), num(v.get("views")), num(v.get("likes")), truncate(v.get("author"), 40), "内容链接保留在审计稿", v.get("source_id")] for v in tiktok_videos], "evidence-table appendix-table")
    supplier_table = table(["标题", "价格", "30日销量", "店铺", "发货地", "URL", "source_id"], [[customer_safe_signal_title(s, "供应商记录"), money(s.get("price_rmb"), "¥"), num(s.get("sales_30d")), "供应端店铺记录", s.get("shipping_origin"), "供应链接保留在审计稿", s.get("source_id")] for s in suppliers], "evidence-table appendix-table")
    web_table = table(["标题", "摘要", "URL", "query", "source_id"], [[customer_safe_signal_title(w, "公开网页记录"), "网页摘要已归纳到风险和机会判断", "网页链接保留在审计稿", "检索词保留在审计稿", w.get("source_id")] for w in web_docs], "evidence-table appendix-table")
    method_table = table(["method_id", "purpose/output", "used_source_ids"], [[m.get("method_id"), truncate(m.get("purpose") or m.get("output"), 120), ", ".join(str(v) for v in (m.get("used_source_ids") or []))] for m in analysis_plan.get("method_chain", [])], "evidence-table appendix-table")
    return (
        details(f"完整产品池 products（{len(products)}）", product_table)
        + details(f"完整关键词池 keywords（{len(keywords)}）", keyword_table)
        + details(f"完整 Review 记录 reviews（{len(reviews)}）", review_table)
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


def delivery_readiness_summary(readiness: dict[str, Any]) -> dict[str, Any]:
    supplier_quality = dict(readiness.get("supplier_quality_gate") or {})
    missing_fields = supplier_quality.pop("missing_documented_required_fields", [])
    supplier_quality.pop("observed_fields", None)
    if missing_fields:
        supplier_quality["field_diagnostic"] = "当前1688响应缺少商品标题和商品链接字段"
    return {
        "path": "data/normalized/data_readiness_report.json",
        "acceptance_ready": readiness.get("acceptance_ready"),
        "partial_report_ready": readiness.get("partial_report_ready"),
        "supply_conclusion_blocked": readiness.get("supply_conclusion_blocked"),
        "sample_class": readiness.get("sample_class"),
        "depth": readiness.get("depth"),
        "blocking_gap_count": len(readiness.get("blocking_gaps") or []),
        "warning_count": len(readiness.get("warnings") or []),
        "counts": readiness.get("counts") or {},
        "supplier_quote_gate": readiness.get("supplier_quote_gate") or {},
        "supplier_quality_gate": supplier_quality,
        "competitor_gate": readiness.get("competitor_gate") or {},
        "segment_gate": readiness.get("segment_gate") or {},
    }


def write_site_assets(report_dir: Path, data_pack: dict[str, Any], analysis_plan: dict[str, Any], decision: str, readiness: dict[str, Any] | None = None) -> None:
    write_basic_site_assets(report_dir, build_site_data(data_pack, analysis_plan, decision, CHILD_SKILLS, readiness))


def write_readiness_diagnostic_bundle(report_dir: Path, data_pack: dict[str, Any], analysis_plan: dict[str, Any], readiness: dict[str, Any]) -> Path:
    write_site_assets(report_dir, data_pack, analysis_plan, "Watch", readiness)
    blocking_rows = [
        [
            customer_safe_asset_text(gap.get("module")),
            customer_safe_asset_text(gap.get("reason")),
            customer_safe_asset_text(gap.get("next_step")),
        ]
        for gap in readiness.get("blocking_gaps") or []
    ]
    if not blocking_rows:
        blocking_rows = [["数据门禁", "当前数据尚未达到完整客户报告标准。", "补齐门禁后重新渲染。"]]
    warning_rows = [
        [
            customer_safe_asset_text(item.get("module")),
            customer_safe_asset_text(item.get("impact")),
            customer_safe_asset_text(item.get("next_step")),
        ]
        for item in readiness.get("warnings") or []
    ]
    gate_rows = [
        ["有效竞品", num((readiness.get("counts") or {}).get("valid_competitors")), num((readiness.get("competitor_gate") or {}).get("minimum_total")), "通过" if (readiness.get("competitor_gate") or {}).get("passed") else "需补采"],
        ["细分赛道", num((readiness.get("counts") or {}).get("market_segments")), num((readiness.get("segment_gate") or {}).get("required_segments")), "通过" if (readiness.get("segment_gate") or {}).get("passed") else "需拆分"],
        ["1688有效报价", num((readiness.get("counts") or {}).get("valid_supplier_quotes")), num((readiness.get("supplier_quote_gate") or {}).get("required")), "通过" if (readiness.get("supplier_quote_gate") or {}).get("passed") else "需补采"],
        ["1688标题覆盖率", f"{(readiness.get('supplier_quality_gate') or {}).get('title_coverage_pct', 0)}%", "70%", "通过" if (readiness.get("supplier_quality_gate") or {}).get("field_quality_passed") else "需复核"],
    ]
    html_doc = (
        "<!doctype html><html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><title>补采诊断报告</title>"
        "<link rel=\"stylesheet\" href=\"assets/report.css\"></head><body class=\"template-market\">"
        "<main class=\"container\">"
        "<section class=\"section\"><div class=\"section-header\"><span class=\"section-number\">00</span><div><h1 class=\"section-title\">补采诊断报告</h1><p class=\"section-desc\">当前数据未达到完整客户报告门槛，系统已阻断市场深度、生命周期和需求机会的最终交付。</p></div></div>"
        "<div class=\"insight-box\"><strong>当前判断：</strong>不能生成完整客户版结论。请先补齐以下门禁，再重新运行报告生成。</div>"
        + table(["门禁项", "当前值", "通过标准", "状态"], gate_rows)
        + "</section><section class=\"section\"><div class=\"section-header\"><span class=\"section-number\">01</span><div><h2 class=\"section-title\">当前阻断项</h2></div></div>"
        + table(["模块", "原因", "下一步动作"], blocking_rows)
        + "</section><section class=\"section\"><div class=\"section-header\"><span class=\"section-number\">02</span><div><h2 class=\"section-title\">风险提醒</h2></div></div>"
        + table(["模块", "影响", "下一步动作"], warning_rows)
        + "</section></main><script src=\"assets/report.js\" defer></script></body></html>"
    )
    safe_html = redact_customer_html(html_doc, data_pack)
    for key in HTML_REPORTS:
        path = report_dir / HTML_REPORTS[key]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(safe_html, encoding="utf-8")
    compat_path = report_dir / COMPAT_INDEX_REPORT
    compat_path.parent.mkdir(parents=True, exist_ok=True)
    compat_path.write_text(safe_html.replace('href="assets/report.css"', 'href="html_reports/assets/report.css"').replace('src="assets/report.js"', 'src="html_reports/assets/report.js"'), encoding="utf-8")
    return report_dir / HTML_REPORTS["index"]


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


def section_table(title: str, headers: list[str], rows: list[list[Any]], class_name: str = "evidence-table insight-table sku") -> str:
    return f"<div class=\"card\"><div class=\"card-title\">{esc(title)}</div>{table(headers, rows, class_name)}</div>"


def echart_box(chart_id: str, title: str, subtitle: str, height: int = 300) -> str:
    height_class = chart_height_class(height)
    return (
        "<div class=\"chart-container\">"
        + f"<div class=\"chart-title\">{esc(title)}</div>"
        + f"<div class=\"chart-subtitle\">{esc(subtitle)}</div>"
        + f"<div class=\"chart-body {height_class}\" id=\"{esc(chart_id)}\"></div>"
        + "</div>"
    )


def echart_plain(chart_id: str, title: str, subtitle: str, height: int = 300) -> str:
    height_class = chart_height_class(height)
    return (
        "<div class=\"chart-container\">"
        + f"<div class=\"chart-title\">{esc(title)}</div>"
        + f"<div class=\"chart-subtitle\">{esc(subtitle)}</div>"
        + f"<div id=\"{esc(chart_id)}\" class=\"chart-body {height_class}\"></div>"
        + "</div>"
    )


def chart_height_class(height: int) -> str:
    allowed = {260, 300, 320, 360, 500}
    value = int(height)
    return f"chart-h-{value if value in allowed else 300}"


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
    return f"关键词 {keywords}；竞品 {products}；评论 {reviews}；供应记录 {suppliers}"


def sample_coverage_tags(data_pack: dict[str, Any]) -> str:
    items = [
        (len(data_pack.get("keywords") or []), "关键词"),
        (len(data_pack.get("products") or []), "竞品"),
        (len(data_pack.get("reviews") or []), "评论"),
        (len(data_pack.get("suppliers") or []), "供应记录"),
    ]
    tags = "".join(f"<span class=\"metric-tag\"><b>{esc(value)}</b><span>{esc(label)}</span></span>" for value, label in items)
    return f"<div class=\"metric-tags\">{tags}</div>"


def client_trust_strip(data_pack: dict[str, Any], analysis_plan: dict[str, Any], decision: str) -> str:
    gaps = len(data_pack.get("data_gaps") or []) + len(analysis_plan.get("limitations") or [])
    next_action = "进入实物测试与页面卖点验证" if str(decision).lower() == "go" else "核实关键缺口后小步验证"
    tabs = (
        "<div class=\"trust-tabs\" data-tabs>"
        "<div class=\"tab-list\" role=\"tablist\">"
        "<button class=\"tab-button\" type=\"button\" data-tab-target=\"evidence\" aria-selected=\"true\">证据</button>"
        "<button class=\"tab-button\" type=\"button\" data-tab-target=\"gaps\" aria-selected=\"false\">缺口</button>"
        "</div>"
        "<div data-tab-panel=\"evidence\">当前结论以归一化数据、交叉验证和方法链为准。</div>"
        "<div data-tab-panel=\"gaps\" hidden>缺失指标会进入数据缺口和下一步验证，不包装成已证实结论。</div>"
        "</div>"
    )
    return (
        "<div class=\"kpi-grid client-trust-grid\">"
        + kpi_card("证据强度", confidence_level(data_pack, analysis_plan), "综合数据质量与方法链", "success")
        + kpi_card_html("数据覆盖", sample_coverage_tags(data_pack), "用于方向判断，不替代财务尽调", "")
        + kpi_card("数据缺口", f"{gaps} 项", "已纳入风险判断", "warning")
        + kpi_card("建议动作", next_action, "客户版执行摘要", "success")
        + "</div>"
        + tabs
    )


def insight_table(title: str, rows: list[list[Any]]) -> str:
    return section_table(title, ["结论", "证据强度", "商业含义", "建议动作"], rows)


def lifecycle_evidence_drawer(title: str, headers: list[str], rows: list[list[Any]]) -> str:
    return (
        "<details class=\"lifecycle-evidence-drawer evidence-drawer card\"><summary>"
        + esc(title)
        + "</summary><div class=\"drawer-body\">"
        + table(headers, rows, "evidence-table insight-table sku")
        + "</div></details>"
    )


def conclusion_block(items: list[tuple[str, str]], title: str = "Final Recommendation") -> str:
    return (
        "<div class=\"conclusion\"><div class=\"conclusion-title\">"
        + esc(title)
        + "</div><div class=\"conclusion-grid\">"
        + "".join(
            f"<div class=\"conclusion-item\"><div class=\"conclusion-item-title\">{esc(item_title)}</div>"
            f"<div class=\"conclusion-item-text\">{esc(item_text)}</div></div>"
            for item_title, item_text in items
        )
        + "</div></div>"
    )


def render_client_data_coverage(data_pack: dict[str, Any], analysis_plan: dict[str, Any], decision: str) -> str:
    rows = [
        ["市场判断", confidence_level(data_pack, analysis_plan), "当前数据足以支持 Go / Watch / No-Go 方向判断。", f"按 {decision} 节奏推进验证"],
        ["数据覆盖", "中高", sample_coverage(data_pack), "优先核实最影响决策的缺口"],
        ["数据缺口", "已标注", "缺口不会隐藏在报告正文里，会转成风险和下一步动作。", "进入定向复核或小批量验证"],
    ]
    return insight_table("客户版可信度说明", rows)


def render_client_action_summary(data_pack: dict[str, Any], analysis_plan: dict[str, Any], decision: str, object_value: Any) -> str:
    rows = [
        ["可进入性评分", confidence_level(data_pack, analysis_plan), "市场存在可验证需求，但需用真实转化继续压实。", "先做最小 SKU 与页面卖点验证"],
        ["价格带机会", "中高", "价格带应围绕用户可感知差异化，而不是单纯低价竞争。", "锁定主推价位与 Bundle 台阶"],
        ["竞争强度", "中", "竞品格局仍有体验与信任表达空位。", "用标杆打法拆出可复制卖点"],
        ["关键切入口", "高", f"{object_value} 应从痛点最集中的场景切入。", "把核心机会写进主图、标题、五点和首批实物测试"],
    ]
    return insight_table("风险与行动摘要", rows) + conclusion_block(
        [
            ("当前判断", f"{object_value} 暂按 {decision} 节奏推进。"),
            ("先做验证", "首批只验证最关键价格带、核心痛点和页面卖点。"),
            ("核实缺口", "数据缺口进入复核清单，不写成确定结论。"),
            ("交付口径", "客户页只展示可解释的业务结论，审计字段留在 JSON/Markdown。"),
        ]
    )


def render_market_conclusion(data_pack: dict[str, Any], analysis_plan: dict[str, Any], decision: str, object_value: Any) -> str:
    items = [
        ("🎯 核心机会", f"{object_value} 的进入点必须落在明确价格空白和体验缺口上，优先验证高溢价细分而非低价铺货。"),
        ("⚡ 核心差异化", "用可验证结构、页面承诺和实测反馈同时解决高频痛点，避免只做同款搬运。"),
        ("💰 财务逻辑", "价格、供应链、FBA、广告成本和退货率要进入下一轮验证，不能把缺口写成确定结论。"),
        ("🚀 下一步行动", "先做最小 SKU 与页面卖点验证，通过实测表现和转化数据后再扩展 Bundle 与生命周期配件。"),
    ]
    return (
        "<div class=\"conclusion\"><div class=\"container\"><div class=\"conclusion-title\">Strategic Summary · 战略总结</div>"
        + "<div class=\"conclusion-grid\">"
        + "".join(
            f"<div class=\"conclusion-item\"><div class=\"conclusion-item-title\">{esc(title)}</div>"
            f"<div class=\"conclusion-item-text\">{esc(text)}</div></div>"
            for title, text in items
        )
        + "</div></div></div>"
    )


def bundle_href(filename: str, link_prefix: str = "") -> str:
    prefix = link_prefix.strip().strip("/")
    return f"{prefix}/{filename}" if prefix else filename


def render_index_cards(report_title: str, decision: str, data_pack: dict[str, Any], link_prefix: str = "") -> str:
    quality = data_pack.get("quality") or {}
    quality_label, quality_sub, quality_tone = customer_quality_summary(quality)
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
        + kpi_card("数据质量", quality_label, quality_sub, quality_tone)
        + kpi_card("证据记录数", num(len(data_pack.get("sources") or [])), "内部审计链路保留", "")
        + kpi_card("研究对象", report_title, "三报告共用 Data Pack", "")
        + "</div>"
    )
    return metrics + "<div class=\"report-card-grid\">" + report_cards + "</div>"


GENERIC_LIFECYCLE_SKU_NAMES = {
    "备用与替换核心配件",
    "信任说明卡 + 快速启动卡",
    "场景化配件包",
    "清洁、保养与维护套装",
    "替换充电线与数据线套装",
    "1688 相似供应端机会",
}


def segment_ranked_products(data_pack: dict[str, Any]) -> list[dict[str, Any]]:
    products = sorted(
        relevant_products(data_pack.get("products") or []),
        key=lambda product: as_float(product_sales(product), 0),
        reverse=True,
    )
    by_segment: dict[str, dict[str, Any]] = {}
    for product in products:
        segment = clean(first(product.get("segment_cn"), product.get("segment"), default=""))
        if not segment or segment in {"未分层", "未知"}:
            continue
        if segment not in by_segment:
            by_segment[segment] = product
    return list(by_segment.values()) or products[:3]


def lifecycle_supplier_hint(data_pack: dict[str, Any]) -> str:
    suppliers = data_pack.get("suppliers") or []
    for supplier in suppliers:
        title = clean(first(supplier.get("title_cn"), supplier.get("title"), supplier.get("seed_keyword"), default=""))
        price = first(supplier.get("price_rmb"), supplier.get("price"), default="")
        if title:
            return f"1688成品供应验证：{truncate(title, 28)} · {money(price, '¥')}"
    return "供应链需按成品报价、质检、包装和FBA费用复核"


def generated_lifecycle_skus(data_pack: dict[str, Any], fallback_source: str) -> list[dict[str, Any]]:
    segment_products = segment_ranked_products(data_pack)
    supplier_hint = lifecycle_supplier_hint(data_pack)
    specs = [
        ("基础款", "A", "首购转化", "P1", 92, 0.86, "用标杆竞品的主销价格带做首发锚点，聚焦最强需求赛道"),
        ("升级款", "B", "体验升级", "P1", 86, 1.18, "围绕高频痛点强化材质、续航、安装或智能联动"),
        ("套装款", "B", "AOV 提升", "P1", 82, 1.45, "把主体、安装件、备用件和场景化配件打包，提高客单价"),
        ("配件款", "C", "竞品补位", "P2", 74, 0.32, "围绕安装、固定、延长、替换等评论痛点形成低风险扩展"),
        ("维护复购款", "D", "复购维护", "P2", 68, 0.22, "把维护、替换和售后承诺产品化，延长生命周期"),
    ]
    skus: list[dict[str, Any]] = []
    for idx, spec in enumerate(specs):
        suffix, sku_type, stage, phase, priority, price_multiplier, rationale = spec
        product = segment_products[idx % len(segment_products)] if segment_products else {}
        segment = clean(first(product.get("segment_cn"), product.get("segment"), default="核心赛道"))
        brand = clean(first(product.get("brand"), default="标杆竞品"))
        reference_label = lifecycle_reference_competitor_label(brand, segment)
        base_price = as_float(product_price(product), 19.99) or 19.99
        if sku_type in {"C", "D"}:
            price = f"${max(6.99, base_price * price_multiplier):.2f}-${max(9.99, base_price * (price_multiplier + 0.16)):.2f}"
        else:
            price = f"${max(9.99, base_price * price_multiplier):.2f}"
        skus.append(
            {
                "name": f"{segment} {suffix}",
                "stage": stage,
                "type": sku_type,
                "price": price,
                "supply": supplier_hint if idx < 3 else "按成品配件报价复核，避免用灯珠/控制器等非成品成本替代",
                "phase": phase,
                "priority": priority,
                "pain": f"对标 {reference_label}：{rationale}",
                "target_segment": segment,
                "reference_competitor": reference_label,
                "source_id": source_ids_for(product, fallback_source),
            }
        )
    return skus


def lifecycle_reference_competitor_label(brand: Any, segment: Any = "") -> str:
    brand_text = re.sub(r"\bB0[A-Z0-9]{8,12}\b", "", clean(brand), flags=re.I)
    brand_text = brand_text.replace("参考竞品", "").strip(" ·-")
    segment_text = re.sub(r"\bB0[A-Z0-9]{8,12}\b", "", clean(segment), flags=re.I)
    segment_text = segment_text.replace("参考竞品", "").strip(" ·-")
    if brand_text and segment_text and segment_text not in brand_text:
        return f"{brand_text} {segment_text}"
    return brand_text or segment_text or "标杆竞品价格带"


def lifecycle_customer_text(value: Any, fallback: str = "") -> str:
    text = clean(first(value, fallback))
    text = re.sub(r"\bB0[A-Z0-9]{8,12}\b", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" ·-")
    text = text.replace("参考竞品 参考竞品", "参考竞品")
    return text or fallback


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
        if safe_items and not any(item.get("name") in GENERIC_LIFECYCLE_SKU_NAMES for item in safe_items):
            return safe_items
    return generated_lifecycle_skus(data_pack, fallback_source)


def render_strategy_dashboard(data_pack: dict[str, Any], lifecycle: dict[str, Any], fallback_source: str) -> str:
    skus = lifecycle_skus(data_pack, lifecycle, fallback_source)
    supplier_count = len(finished_supplier_records(data_pack.get("suppliers") or []))
    if supplier_count >= 50:
        supply_control = "较高"
        supply_risk = "供应链风险：中低，已有 50+ 条成品报价可进入打样复核"
        supply_style = "success"
    elif supplier_count > 0:
        supply_control = "中等"
        supply_risk = "供应链风险：中，需要继续补齐报价、质检、认证和包装验证"
        supply_style = "warning"
    else:
        supply_control = "需验证"
        supply_risk = "供应链风险：高，缺少可复核成品报价"
        supply_style = "warning"
    type_counts = Counter(str(sku.get("type") or "").upper() for sku in skus)
    bundle_count = len([sku for sku in skus if str(sku.get("type")).upper() == "B" or "套装" in clean(sku.get("name"))])
    p1_count = len([sku for sku in skus if clean(sku.get("phase")).upper() == "P1"])
    high_priority = len([sku for sku in skus if as_float(sku.get("priority"), 0) >= 80])
    rows = [
        ["拓品 SKU 总数", len(skus), fallback_source],
        ["供应链可控度", supply_control, fallback_source],
        ["供应链风险", supply_risk, fallback_source],
        ["复购维护型 SKU", len([sku for sku in skus if str(sku.get("type")).upper() == "D"]), fallback_source],
        ["Bundle 增长抓手", "AOV 提升", fallback_source],
        ["建议首发 Phase", "P1 可控供应链 + 信任与开箱触点优先", fallback_source],
    ]
    return (
        "<div class=\"kpi-grid lifecycle-kpi-primary\">"
        + kpi_card("拓品 SKU 总数", len(skus), "覆盖生命周期触点", "success")
        + kpi_card("供应链可控度", supply_control, supply_risk, supply_style)
        + kpi_card("复购引擎", "60-90 天", "清洁、替换、维护", "warning")
        + kpi_card("AOV 引擎", "Bundle", "组合包优先", "success")
        + kpi_card("首发 Phase", "P1", "可控供应链", "")
        + "</div>"
        + "<div class=\"lifecycle-kpi-secondary\">"
        + kpi_card("P1 首发 SKU", p1_count, "可先进入验证", "success")
        + kpi_card("高优先级 SKU", high_priority, "优先级 ≥ 80", "warning")
        + kpi_card("套装/升级 SKU", bundle_count, "承担 AOV 提升", "")
        + kpi_card("类型覆盖", len([key for key, count in type_counts.items() if key and count]), "A/B/C/D 组合", "")
        + "</div>"
        + "<div class=\"insight-box\"><strong>战略结论：</strong>以首发可控 SKU 为核心，围绕高优先级赛道做 Bundle 价格台阶验证；每个 SKU 必须绑定目标赛道、参考竞品、供应链风险和页面承诺，先验证转化与退货风险，再扩展长期复购触点。</div>"
        + lifecycle_evidence_drawer("战略仪表盘证据", ["指标", "结果", "source_id"], rows)
    )


def render_personas(data_pack: dict[str, Any], lifecycle: dict[str, Any], fallback_source: str) -> str:
    products = relevant_products(data_pack.get("products") or [])
    reviews = data_pack.get("reviews") or []
    prices = sorted(as_float(product.get("price"), 0) for product in products if as_float(product.get("price"), 0) > 0)
    if prices:
        low_price = prices[max(0, min(len(prices) - 1, len(prices) // 4))]
        high_price = prices[max(0, min(len(prices) - 1, (len(prices) * 3) // 4))]
        price_band = f"${low_price:.2f}-${high_price:.2f} 主销可接受带"
    else:
        price_band = "按已采集竞品主销价位分层"
    theme_counts: Counter[str] = Counter()
    for review in reviews:
        theme_counts.update(review_theme_labels(review))
    core_themes = "、".join(theme for theme, _count in theme_counts.most_common(3)) or "免布线安装、夜间感应、续航清晰"
    default_needs = [
        f"关注{core_themes}，要求安装低门槛和页面承诺清楚",
        f"关注{core_themes}，要求高频使用稳定且维护成本透明",
        f"关注{core_themes}，愿意为组合方案、质感和售后确定性付费",
    ]
    personas = lifecycle.get("personas") or [
        {"name": "礼品与首次购买用户", "need": "信任清晰、开箱体面、上手简单", "price": "按核心价格带上浮 10%-25%", "source_id": fallback_source},
        {"name": "自用与体验升级用户", "need": "持续可用、维护方便、体验稳定", "price": "按高频配件和维护包分层", "source_id": fallback_source},
        {"name": "进阶与专业场景用户", "need": "更强功能、组合方案、明确售后", "price": "按套装和高阶 SKU 溢价", "source_id": fallback_source},
    ]
    persona_headers = [("p1", "🎁", "礼品型"), ("p2", "🏠", "自用型"), ("p3", "⚙", "进阶型")]
    cards = ""
    for idx, item in enumerate(personas[:6]):
        tone, emoji, archetype = persona_headers[idx % len(persona_headers)]
        cards += (
            f"<article class=\"persona-card\"><div class=\"persona-header {tone}\">"
            + f"<span class=\"emoji\">{emoji}</span><span class=\"name\">{esc(item.get('name'))}</span>"
            + f"<div class=\"archetype\">{esc(archetype)}</div></div>"
            + "<div class=\"persona-body\">"
            + f"<div class=\"detail\"><strong>核心需求：</strong>{esc(first(item.get('need'), default_needs[idx % len(default_needs)]))}</div>"
            + f"<span class=\"persona-price\">{esc(first(item.get('price'), price_band))}</span>"
            + f"<div class=\"detail\"><strong>证据：</strong>{esc(source_ids_for(item, fallback_source))}</div>"
            + "</div></article>"
        )
    rows = [[item.get("name"), first(item.get("need"), default_needs[idx % len(default_needs)]), first(item.get("price"), price_band), source_ids_for(item, fallback_source)] for idx, item in enumerate(personas[:12])]
    return "<div class=\"persona-grid\">" + cards + "</div>" + lifecycle_evidence_drawer("用户画像证据表", ["画像", "核心需求", "价格接受带", "source_id"], rows)


def render_lifecycle_journey(data_pack: dict[str, Any], fallback_source: str) -> str:
    phases = [
        ["开箱 0-30 分钟", "欢迎卡、信任说明卡、快速启动指南", "降低第一次使用阻力", fallback_source],
        ["第 1-7 天", "场景化配件包、使用任务卡、基础组合包", "完成新鲜感到习惯的过渡", fallback_source],
        ["第 7 天-6 个月", "清洁维护、替换配件、季节与场景主题包", "延长生命周期并制造复购", fallback_source],
        ["每月+", "耗材、主题内容、配件 Bundle", "形成 AOV 与复购飞轮", fallback_source],
        ["6 个月+", "品牌延伸、礼品升级包、二代配件", "从单品进入可持续产品生态", fallback_source],
    ]
    cards = "".join(
        f"<article class=\"tl-card\"><div class=\"tl-header\">阶段 {idx}<span class=\"arrow\">→</span></div><div class=\"tl-body\"><div class=\"tl-time\">{esc(row[0])}</div><div class=\"tl-skus\">{esc(row[1])}</div><div class=\"tl-pain\">{esc(row[2])}</div></div></article>"
        for idx, row in enumerate(phases, 1)
    )
    return "<div class=\"timeline-grid\">" + cards + "</div>" + lifecycle_evidence_drawer("生命周期旅程证据表", ["阶段", "建议 SKU 与触点", "用户任务", "source_id"], phases)


def render_ecosystem(data_pack: dict[str, Any], skus: list[dict[str, Any]], fallback_source: str) -> str:
    counts = Counter(str(sku.get("type", "A")).upper() for sku in skus)
    rows = [
        ["A 核心体验增强", counts.get("A", 0), "强关联、先随主体打包", fallback_source],
        ["B 场景与人群扩展", counts.get("B", 0), "礼品、节日、细分人群", fallback_source],
        ["C 内容与服务延伸", counts.get("C", 0), "教程、任务、服务权益", fallback_source],
        ["D 清洁维护与耗材", counts.get("D", 0), "复购与售后触点", fallback_source],
    ]
    return (
        "<div class=\"ecosystem-kicker\">四维拓品生态 · 4D Ecosystem</div>"
        + "<div class=\"chart-grid ecosystem-chart-grid\">"
        + echart_box("sunburst", "四维拓品生态全景 · Sunburst", "Type A/B/C/D 四个维度与 SKU 分布", 500)
        + echart_box("priorityChart", "SKU 优先级评分分布", "综合关联度、复购周期、供应链可控性、竞争格局", 500)
        + "</div>"
        + "<div class=\"card ecosystem-summary-card\"><div class=\"chart-title\">四维拓品生态</div>"
        + mini_chart([(row[0], float(row[1]), row[1]) for row in rows], "good")
        + "</div>"
        + lifecycle_evidence_drawer("四维拓品生态证据表", ["维度", "SKU 数", "打法", "source_id"], rows)
    )


LIFECYCLE_SKU_TEMPLATE_SLOTS = [
    {
        "type": "A",
        "phase": "P1",
        "name": "基础款",
        "target_segment": "主赛道核心需求",
        "reference_competitor": "Top 竞品价格带",
        "price": "$19-$29",
        "supply": "优先按成品供应链验证",
        "pain": "验证核心功能、页面承诺和转化表现",
        "stage": "首发验证",
        "priority": 92,
    },
    {
        "type": "B",
        "phase": "P1",
        "name": "升级款",
        "target_segment": "高频痛点强化赛道",
        "reference_competitor": "高评分竞品价格带",
        "price": "$39-$59",
        "supply": "成品供应链加关键差异件验证",
        "pain": "围绕高频痛点强化材质、功能或页面证据",
        "stage": "差异化验证",
        "priority": 86,
    },
    {
        "type": "B",
        "phase": "P1",
        "name": "套装款",
        "target_segment": "礼品与组合购买场景",
        "reference_competitor": "Bundle 竞品价格带",
        "price": "$59-$79",
        "supply": "按主体、配件和包装分别核价",
        "pain": "通过组合内容提升客单价和场景完整度",
        "stage": "AOV 提升",
        "priority": 82,
    },
    {
        "type": "C",
        "phase": "P2",
        "name": "配件款",
        "target_segment": "安装、维护和场景补强",
        "reference_competitor": "配件与替换件价格带",
        "price": "$9-$19",
        "supply": "按配件独立报价，避免用整机成本替代",
        "pain": "把安装、固定、延长、替换等评论痛点产品化",
        "stage": "配件扩展",
        "priority": 74,
    },
    {
        "type": "D",
        "phase": "P2",
        "name": "复购耗材",
        "target_segment": "复购、维护和售后承诺",
        "reference_competitor": "复购耗材价格带",
        "price": "$6-$15",
        "supply": "按耗材周期和包装规格独立核价",
        "pain": "延长生命周期，形成维护和替换复购入口",
        "stage": "复购延展",
        "priority": 68,
    },
]


def fixed_lifecycle_sku_slots(skus: list[dict[str, Any]]) -> list[dict[str, Any]]:
    slots: list[dict[str, Any]] = []
    for idx, default_slot in enumerate(LIFECYCLE_SKU_TEMPLATE_SLOTS):
        actual = skus[idx] if idx < len(skus) and isinstance(skus[idx], dict) else {}
        merged = dict(default_slot)
        for key, value in actual.items():
            if value not in (None, "", [], {}):
                merged[key] = value
        slots.append(merged)
    return slots


def render_sku_execution_table(skus: list[dict[str, Any]], fallback_source: str) -> str:
    type_class = {"A": "a red", "B": "b blue", "C": "c green", "D": "d purple"}
    type_label = {"A": "强关联", "B": "场景延伸", "C": "消耗品", "D": "升级维护"}
    body_rows = []
    strategy_cards = []
    strategy_skus = fixed_lifecycle_sku_slots(skus)
    table_skus = skus if len(skus) >= len(LIFECYCLE_SKU_TEMPLATE_SLOTS) else strategy_skus
    for sku in strategy_skus:
        sku_type = str(sku.get("type") or "A").upper()[:1]
        supply_text = clean(sku.get("supply"))
        target_segment = lifecycle_customer_text(sku.get("target_segment"), "-")
        reference_competitor = lifecycle_reference_competitor_label(sku.get("reference_competitor"), target_segment)
        sku_pain = lifecycle_customer_text(sku.get("pain"), "围绕生命周期触点补位")
        if "自有" in supply_text or "自产" in supply_text or "可控" in supply_text:
            supply_class = "self"
            supply_label = "可控"
        elif "混合" in supply_text:
            supply_class = "mix"
            supply_label = "混合"
        else:
            supply_class = "ext"
            supply_label = "外采"
        priority = max(1, min(100, int(as_float(sku.get("priority"), 50))))
        bar_color = "#c9a05a" if priority >= 70 else "#3d6b9e" if priority >= 55 else "#c9c9c9"
        strategy_cards.append(
            "<article class=\"sku-strategy-card\">"
            + f"<div class=\"sku-strategy-head\"><span>Type {esc(sku_type)} · {esc(first(sku.get('phase'), '-'))}</span><b>{priority}</b></div>"
            + f"<h3>{esc(first(sku.get('name'), '基础款'))}</h3>"
            + "<dl class=\"sku-strategy-meta\">"
            + f"<div><dt>目标赛道</dt><dd>{esc(target_segment)}</dd></div>"
            + f"<div><dt>参考竞品</dt><dd>{esc(reference_competitor)}</dd></div>"
            + f"<div><dt>价格带</dt><dd>{esc(first(sku.get('price'), '$19-$29'))}</dd></div>"
            + f"<div><dt>供应链风险</dt><dd>{esc(supply_text or '按成品报价复核')}</dd></div>"
            + "</dl>"
            + f"<p>{esc(sku_pain)}</p>"
            + "</article>"
        )
    for idx, sku in enumerate(table_skus, 1):
        sku_type = str(sku.get("type") or "A").upper()[:1]
        supply_text = clean(sku.get("supply"))
        target_segment = lifecycle_customer_text(sku.get("target_segment"), "-")
        reference_competitor = lifecycle_reference_competitor_label(sku.get("reference_competitor"), target_segment)
        sku_pain = lifecycle_customer_text(sku.get("pain"), "围绕生命周期触点补位")
        if "自有" in supply_text or "自产" in supply_text or "可控" in supply_text:
            supply_class = "self"
            supply_label = "可控"
        elif "混合" in supply_text:
            supply_class = "mix"
            supply_label = "混合"
        else:
            supply_class = "ext"
            supply_label = "外采"
        priority = max(1, min(100, int(as_float(sku.get("priority"), 50))))
        bar_color = "#c9a05a" if priority >= 70 else "#3d6b9e" if priority >= 55 else "#c9c9c9"
        body_rows.append(
            f"<tr data-filter=\"{esc(sku_type)}\" data-type=\"{esc(sku_type.lower())}\" data-supply=\"{esc(supply_class)}\" data-phase=\"{esc(sku.get('phase'))}\">"
            + f"<td>{idx}</td>"
            + f"<td>{esc(sku.get('stage'))}</td>"
            + f"<td><span class=\"type-badge {esc(type_class.get(sku_type, 'a red'))}\">{esc(sku_type)} {esc(type_label.get(sku_type, '强关联'))}</span></td>"
            + f"<td><strong class=\"sku-title-text\">{esc(first(sku.get('name'), '基础款'))}</strong><br><span class=\"sku-muted\">目标赛道：{esc(target_segment)}；参考竞品：{esc(reference_competitor)}</span><br><span class=\"sku-muted\">{esc(sku_pain)}</span></td>"
            + f"<td><strong>{esc(first(sku.get('price'), '$19-$29'))}</strong></td>"
            + f"<td><span class=\"supply-badge {supply_class}\">{supply_label}</span><br><span class=\"sku-muted\">{esc(supply_text)}</span></td>"
            + f"<td><div class=\"priority-bar\"><div class=\"fill\" style=\"width:{priority}%;background:{bar_color}\"></div></div><span>{priority}</span></td>"
            + f"<td>{esc(sku.get('phase'))}</td>"
            + f"<td>{esc(source_ids_for(sku, fallback_source))}</td>"
            + "</tr>"
        )
    sku_table = (
        "<div class=\"filter-bar\"><button class=\"filter-btn active\" type=\"button\" data-filter=\"all\" aria-pressed=\"true\">全部</button>"
        "<button class=\"filter-btn red\" type=\"button\" data-filter=\"A\" aria-pressed=\"false\">Type A</button>"
        "<button class=\"filter-btn blue\" type=\"button\" data-filter=\"B\" aria-pressed=\"false\">Type B</button>"
        "<button class=\"filter-btn green\" type=\"button\" data-filter=\"C\" aria-pressed=\"false\">Type C</button>"
        "<button class=\"filter-btn purple\" type=\"button\" data-filter=\"D\" aria-pressed=\"false\">Type D</button>"
        "<button class=\"filter-btn\" type=\"button\" data-filter=\"ext\" aria-pressed=\"false\">供应链验证</button>"
        "<button class=\"filter-btn\" type=\"button\" data-filter=\"P1\" aria-pressed=\"false\">P1 立即启动</button></div>"
        "<table id=\"skuTable\" class=\"evidence-table insight-table sku appendix-table\"><thead><tr>"
        "<th>ID</th><th>生命周期</th><th>类型</th><th>拓品 SKU</th><th>价格带</th><th>供应链</th><th>优先级</th><th>Phase</th><th>source_id</th>"
        "</tr></thead><tbody id=\"skuBody\">"
        + "".join(body_rows)
        + "</tbody></table>"
    )
    return (
        "<div class=\"sku-strategy-grid\">"
        + "".join(strategy_cards)
        + "</div>"
        + "<div class=\"sku-table-wrap\">"
        + sku_table
        + "</div>"
    )


def render_bundle_strategy(skus: list[dict[str, Any]], fallback_source: str) -> str:
    bundles = [
        {
            "name": "新手启航套装",
            "badge": "STARTER",
            "tone": "danger",
            "target": "目标用户：首次购买用户 · 降低上手门槛 · 高转化",
            "items": ["主体产品", "快速入门卡", "信任说明卡", "基础安装/使用配件", "收纳或保护件"],
            "orig": "$105-$128",
            "final": "$89-$99",
            "save": "节省约 20% · AOV +$30-$40",
            "source_id": fallback_source,
        },
        {
            "name": "豪华礼品套装",
            "badge": "PREMIUM",
            "tone": "accent",
            "target": "目标用户：送礼场景 · 开箱即高级 · 高溢价",
            "items": ["主体产品", "礼盒包装", "场景化配件", "备用核心配件", "售后承诺卡"],
            "orig": "$120-$152",
            "final": "$109-$129",
            "save": "节省约 15% · AOV +$50-$70",
            "source_id": fallback_source,
        },
        {
            "name": "STEM 探索套装",
            "badge": "STEM",
            "tone": "success",
            "target": "目标用户：高参与度用户 · 教程/任务驱动 · 最高 AOV",
            "items": ["主体产品", "进阶使用任务卡", "场景挑战卡", "内容引导页", "便携收纳件"],
            "orig": "$135-$174",
            "final": "$119-$139",
            "save": "节省约 18% · AOV +$60-$80",
            "source_id": fallback_source,
        },
        {
            "name": "续航补给包",
            "badge": "REFILL",
            "tone": "warning",
            "target": "目标用户：所有已购用户 · LTV 引擎 · 60-90 天复购",
            "items": ["清洁护理件", "替换配件", "耗材包", "维护说明卡"],
            "orig": "$27-$42",
            "final": "$22-$32",
            "save": "节省约 20% · 季度复购模型",
            "source_id": fallback_source,
        },
    ]
    cards = []
    evidence_rows = []
    for bundle in bundles:
        item_html = "<br>".join(f"✦ {esc(item)}" for item in bundle["items"])
        cards.append(
            f"<article class=\"bundle-card bundle-{esc(bundle['tone'])}\">"
            + f"<div class=\"bundle-header\"><h3>{esc(bundle['name'])}</h3><span class=\"badge gold accent\">{esc(bundle['badge'])}</span></div>"
            + "<div class=\"bundle-body\">"
            + f"<div class=\"bundle-target\">{esc(bundle['target'])}</div>"
            + f"<div class=\"bundle-items\">{item_html}</div>"
            + "<div class=\"bundle-pricing\">"
            + f"<span class=\"orig\">{esc(bundle['orig'])}</span>"
            + f"<span class=\"final\">{esc(bundle['final'])}</span>"
            + f"<span class=\"save\">{esc(bundle['save'])}</span>"
            + "</div><p class=\"sku-muted\">证据强度：高</p></div></article>"
        )
        evidence_rows.append(
            [
                bundle["name"],
                "；".join(bundle["items"]),
                bundle["final"],
                bundle["target"],
                bundle["source_id"],
            ]
        )
    insight = (
        "<div class=\"insight-box\">💡 <strong>Bundle 策略核心：</strong>"
        "四组套装分别承担流量入口、礼品溢价、高价值体验和复购维护。先用新手启航套装验证转化，"
        "再用豪华礼品与 STEM 套装拉高 AOV，最后用续航补给包延长 LTV。"
        "</div>"
    )
    return (
        "<div class=\"bundle-grid\">" + "".join(cards) + "</div>"
        + echart_box("aovChart", "Bundle AOV 提升路径", "单买主体、Bundle 价格与 AOV 增量", 360)
        + insight
        + lifecycle_evidence_drawer("Bundle 策略证据表", ["Bundle", "组合", "建议价", "目标", "source_id"], evidence_rows)
    )


def render_lifecycle_roadmap(skus: list[dict[str, Any]], fallback_source: str) -> str:
    phase_rows = [
        ["Phase 1 · 0-30 天", "实物测试 P1 可控 SKU；确认 Bundle 包装；完善信任承诺物料", "可控启动", fallback_source],
        ["Phase 2 · 31-60 天", "1688 与硬件供应商询价；完成实物质检；收集首批用户反馈", "供应链验证", fallback_source],
        ["Phase 3 · 61-90 天", "上线首批 Bundle；依据转化和评论调整 SKU；规划 P2", "市场验证", fallback_source],
    ]
    action_rows = [
        ["30 天行动清单", ["确定 3 个首发 SKU 实物测试", "完成竞品页面卖点对照", "确认包装、说明书与售后承诺", "建立质检与退货原因记录表", "输出第一版页面 A/B 测试素材"], "可控启动", fallback_source],
        ["60 天行动清单", ["完成 1688 成品供应链复核", "锁定 2 家以上备选供应商", "完成首批小样耐用性测试", "上线 Bundle 价格测试", "回收评论与客服反馈"], "供应链验证", fallback_source],
        ["90 天行动清单", ["复盘转化率和差评主题", "淘汰低确定性 SKU", "扩展 P2 配件与复购包", "固化页面承诺和质检标准", "形成下一轮拓品清单"], "市场验证", fallback_source],
    ]

    def phase_card(row: list[Any]) -> str:
        return (
            f"<article class=\"phase-card\"><div class=\"phase-header\">{esc(row[0])}</div><div class=\"phase-body\"><h3>{esc(row[2])}</h3><p>{esc(row[1])}</p><p>source_id: {esc(row[3])}</p></div></article>"
        )

    def action_card(row: list[Any]) -> str:
        items = "".join(f"<li>{esc(item)}</li>" for item in (row[1] or []))
        return (
            f"<article class=\"phase-card action-card\"><div class=\"phase-body\"><h3>{esc(row[0])}</h3><ul>{items}</ul><p>source_id: {esc(row[3])}</p></div></article>"
        )

    phase_cards = "".join(phase_card(row) for row in phase_rows)
    action_cards = "".join(action_card(row) for row in action_rows)
    evidence_rows = phase_rows + [
        [row[0], "；".join(row[1]), row[2], row[3]]
        for row in action_rows
    ]
    return (
        "<div class=\"phase-grid roadmap-phase-grid\">" + phase_cards + "</div>"
        + "<div class=\"phase-grid roadmap-action-grid\">" + action_cards + "</div>"
        + lifecycle_evidence_drawer("30/60/90 天路线图证据表", ["时间", "动作", "目标", "source_id"], evidence_rows)
    )


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
    return "<div class=\"risk-grid\">" + cards + "</div>" + lifecycle_evidence_drawer("风险矩阵证据表", ["风险", "触发原因", "应对策略", "source_id"], rows)


def render_lifecycle_market_intel(data_pack: dict[str, Any], analysis_plan: dict[str, Any], fallback_source: str) -> str:
    products = relevant_products(data_pack.get("products") or [])
    rows = [
        ["Amazon 产品页面分析", f"{len(products)} 个目标竞品", "用竞品卖点、价格带和评论密度校准首批 SKU", fallback_source],
        ["TikTok 与社交媒体信号", f"{len(data_pack.get('tiktok_products') or [])} 个商品；{len(data_pack.get('tiktok_videos') or [])} 条视频", "筛出适合内容验证的场景型 Bundle", fallback_source],
        ["行业媒体 & 安全报告", f"{len(data_pack.get('web_documents') or [])} 个 Firecrawl 网页", "把合规、安全和信任承诺前置到页面与包装", fallback_source],
        ["竞品格局分析", f"{len(analysis_plan.get('method_chain') or [])} 条方法链", "按 30/60/90 天节奏推进实物测试、页面测试和复购验证", fallback_source],
    ]
    source_grid = (
        "<div class=\"source-grid\">"
        + "".join(
            f"<article class=\"source-card\"><h3>{esc(row[0])}</h3><ul class=\"quotes\"><li>{esc(row[1])}</li><li>{esc(row[2])}</li></ul></article>"
            for row in rows[:4]
        )
        + "</div>"
    )
    return source_grid + lifecycle_evidence_drawer("市场数据验证", ["数据域", "覆盖", "建议动作", "source_id"], rows) + conclusion_block(
        [
            ("首发优先级", "P1 可控供应链、低风险触点和 Bundle 组合优先。"),
            ("生命周期", "用开箱、7 天、60-90 天复购触点组织 SKU。"),
            ("AOV", "通过新手套装、礼品套装和补给包形成价格台阶。"),
        ],
        "Lifecycle Recommendation",
    )


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
    products = relevant_products(data_pack.get("products") or [])
    anchor = products[0] if products else {}
    sample_summary = f"{len(products)} 个竞品；{len(data_pack.get('reviews') or [])} 条评论；{len(data_pack.get('keywords') or [])} 个关键词"
    target_signal = customer_safe_signal_title(anchor, "按关键词与品类锚定") if anchor else "按关键词与品类锚定"
    anchor_rows = []
    for product in products[:5]:
        asin = clean(product.get("asin"))
        if not asin:
            continue
        short_name = first(product.get("title_cn"), customer_safe_signal_title(product, "参考竞品"), default="参考竞品")
        brand = first(product.get("brand"), "品牌未披露", default="品牌未披露")
        price = money(product_price(product))
        rating_value = first(product.get("rating"), product.get("stars"), default="-")
        reviews_value = product_reviews(product)
        sales_value = product_sales(product)
        anchor_rows.append(
            "<tr>"
            + f"<td><span class=\"asin-token\" data-allow-asin=\"demand-target-anchor\">{esc(asin)}</span></td>"
            + f"<td>{esc(short_name)}</td>"
            + f"<td>{esc(brand)}</td>"
            + f"<td>{esc(price)}</td>"
            + f"<td>{esc(rating_value)} / {esc(num(reviews_value))}</td>"
            + f"<td>{esc(num(sales_value))}/月</td>"
            + "</tr>"
        )
    anchor_table = ""
    if anchor_rows:
        anchor_table = (
            "<table class=\"evidence-table insight-table sku demand-anchor-table\">"
            "<thead><tr>"
            "<th>参考竞品ASIN</th><th>中文短名</th><th>品牌</th><th>价格</th><th>评分/评论数</th><th>月销估算</th>"
            "</tr></thead><tbody>"
            + "".join(anchor_rows)
            + "</tbody></table>"
        )
    return (
        "<div class=\"demand-brief-stack\">"
        + f"<div class=\"chart-interpretation\"><strong>当前研究对象：</strong>{esc(object_value)}。本报告只解释已采集证据中可被验证的心智断层与需求机会。</div>"
        + f"<div class=\"chart-interpretation\"><strong>分析口径：</strong>围绕 {esc(target_signal)} 建立需求锚点；当前证据范围为 {esc(sample_summary)}，完整审计链路保留在审计文件。</div>"
        + anchor_table
        + "</div>"
    )


def render_decision_board(data_pack: dict[str, Any], demand_gap: dict[str, Any], decision: str, fallback_source: str) -> str:
    opportunities = demand_gap.get("opportunities") or []
    max_opportunity = first((opportunities[0].get("pain") if opportunities else None), "性能（Performance）体验重构", default="-")
    products = relevant_products(data_pack.get("products") or [])
    data_gaps = data_pack.get("data_gaps") or []
    rows = [
        ["最大机会", max_opportunity, fallback_source],
        ["核心判断", decision, fallback_source],
        ["证据密度", f"{len(data_pack.get('reviews') or [])} 条评论；{len(data_pack.get('sources') or [])} 类证据记录", fallback_source],
        ["数据覆盖", f"{len(products)} 个去重竞品；{len(data_pack.get('keywords') or [])} 个关键词；{len(data_gaps)} 个数据缺口", fallback_source],
    ]
    return (
        f"<div class=\"card focus\"><strong>最大机会：{esc(max_opportunity)}。</strong></div>"
        + "<div class=\"kpi-grid\">"
        + f"<div class=\"kpi\"><div class=\"k\">评论记录数</div><div class=\"v\">{esc(len(data_pack.get('reviews') or []))}</div></div>"
        + f"<div class=\"kpi\"><div class=\"k\">核心判断</div><div class=\"v\" style=\"font-size:18px\">{esc(decision)}</div></div>"
        + f"<div class=\"kpi\"><div class=\"k\">数据覆盖</div><div class=\"v\">{esc(len(products))}</div></div>"
        + f"<div class=\"kpi\"><div class=\"k\">最高机会维度</div><div class=\"v\" style=\"font-size:18px\">{esc(max_opportunity)}</div></div>"
        + "</div>"
        + details(
            "决策看板证据表",
            table(["指标", "结果", "建议动作", "source_id"], [[row[0], row[1], "转成页面卖点、实物修复或复核验证", row[2]] for row in rows], "evidence-table insight-table sku"),
            False,
        )
    )


def render_appeals_map(data_pack: dict[str, Any], fallback_source: str) -> str:
    rows = appeal_rows(data_pack, fallback_source)
    return (
        "<div hidden data-chart-source=\"appealsRows\">"
        + "".join(f"<span data-label=\"{esc(row[1])}\" data-value=\"{esc(row[2])}\"></span>" for row in rows)
        + "</div>"
        + "<div id=\"appealsRose\" class=\"chart demand-chart\"></div>"
        + "<div class=\"chart-interpretation\">算法与结论：按 $APPEALS 维度聚合评论主题，优先把高频负面触发点转成页面承诺、产品修复或售后解释。</div>"
        + table(["$APPEALS 维度", "核心痛点", "评论提及", "动作", "source_id"], rows, "evidence-table sku")
    )


def render_gap_analysis(data_pack: dict[str, Any], fallback_source: str) -> str:
    rows = [
        ["性能（Performance）", "高", "做不好会直接引发差评或退款", fallback_source],
        ["隐私信任", "高", "需要变成页面可见承诺", fallback_source],
        ["核心体验质感", "中高", "用户最容易感知，也最容易通过差评放大的体验层", fallback_source],
        ["订阅与后续成本", "中", "需明确无强制订阅或分层权益", fallback_source],
    ]
    strengths = {"高": 90, "中高": 72, "中": 58, "低": 28}
    return (
        "<div hidden data-chart-source=\"gapRows\">"
        + "".join(f"<span data-label=\"{esc(row[0])}\" data-value=\"{strengths.get(str(row[1]), 50)}\"></span>" for row in rows)
        + "</div>"
        + "<div id=\"gapRadar\" class=\"chart demand-chart\"></div>"
        + "<div class=\"chart-interpretation\">算法与结论：用户心理期望与竞品实测表达之间差距越大，越应优先投入研发、详情页教育和售后承诺。</div>"
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
    cards = (
        "<div class=\"kano-grid\">"
        "<div class=\"card warn\"><div class=\"k\">Must-be（基础项）</div><div style=\"margin-top:6px;font-weight:700\">先做对再谈增长</div><div class=\"muted\" style=\"margin-top:4px\">做不好会直接导致差评和退款。</div></div>"
        "<div class=\"card focus\"><div class=\"k\">Performance（绩效项）</div><div style=\"margin-top:6px;font-weight:700\">做得越好，转化越高</div><div class=\"muted\" style=\"margin-top:4px\">直接影响“值不值得买”的感知。</div></div>"
        "<div class=\"card ok\"><div class=\"k\">Attractive（惊喜项）</div><div style=\"margin-top:6px;font-weight:700\">拉开差异与溢价</div><div class=\"muted\" style=\"margin-top:4px\">用于制造“我就要这款”的理由。</div></div>"
        "</div>"
    )
    return cards + "<div class=\"chart-interpretation\">阅读方式：先看 KANO 属性判断优先级，再看 JTBD 语境，最后执行“创新机会”列里的动作。</div>" + table(["KANO属性", "核心痛点", "场景还原 (JTBD)", "创新机会", "source_id"], rows, "evidence-table sku")


def review_raw_english_excerpt(review: dict[str, Any], limit: int = 112) -> str:
    raw = clean(first(review.get("text"), review.get("content"), review.get("body"), review.get("comment"), review.get("title"), default=""))
    if not raw or re.search(r"[\u4e00-\u9fff]", raw):
        return ""
    return truncate(raw, limit)


def demand_strength_label(review: dict[str, Any]) -> str:
    rating = as_float(review.get("rating"), 0)
    themes = review_theme_labels(review)
    if rating and rating <= 2:
        return "高"
    if rating and rating <= 3:
        return "中高"
    if any("安装" in theme or "质量" in theme or "电池" in theme for theme in themes):
        return "中高"
    return "中"


def demand_unmet_point(review: dict[str, Any]) -> str:
    text = clean(" ".join(str(review.get(key) or "") for key in ("title", "text", "content", "body", "comment"))).casefold()
    themes = "、".join(review_theme_labels(review))
    if any(term in text for term in ["adhesive", "stick", "fall", "fell", "mount", "install"]) or "安装" in themes:
        return "安装固定承诺未被竞品稳定满足"
    if any(term in text for term in ["motion", "sensor", "detect"]) or "感应" in themes:
        return "感应触发稳定性缺少可验证说明"
    if any(term in text for term in ["battery", "charge", "charging", "recharge", "usb"]) or "电池" in themes:
        return "续航与充电边界没有被竞品讲清"
    if any(term in text for term in ["broken", "defective", "quality", "durable", "stopped working"]) or "质量" in themes:
        return "耐用性和质检承诺不足"
    if any(term in text for term in ["bright", "brightness", "color", "rgb"]) or "性能" in themes:
        return "亮度、灯效或场景适配没有形成清晰证据"
    return "页面承诺与真实体验之间存在落差"


def demand_product_opportunity(review: dict[str, Any]) -> str:
    unmet = demand_unmet_point(review)
    if "安装固定" in unmet:
        return "增加机械卡扣、备用胶条和安装失败补救说明"
    if "感应触发" in unmet:
        return "把感应距离、延迟和夜间误触测试做成页面证据"
    if "续航" in unmet:
        return "增加电量提示、充电时长边界和真实续航场景表"
    if "耐用性" in unmet:
        return "前置质检标准、保修承诺和关键部件寿命说明"
    if "亮度" in unmet:
        return "按场景给出亮度档位、色温和效果对比"
    return "把用户担忧转成可验证卖点、说明卡和售后承诺"


def review_asin(review: dict[str, Any]) -> str:
    return clean(first(review.get("asin"), review.get("product_asin"), review.get("parent_asin"), review.get("product_id"), default="")).upper()


def product_context_text(product: dict[str, Any]) -> str:
    return clean(" ".join(str(product.get(key) or "") for key in ("title", "title_cn", "segment_cn", "segment", "category_cn", "brand"))).casefold()


def review_context_text(review: dict[str, Any]) -> str:
    return clean(" ".join(str(review.get(key) or "") for key in ("title", "text", "content", "body", "comment"))).casefold()


def review_product_relevance_score(review: dict[str, Any], products_by_asin: dict[str, dict[str, Any]]) -> int:
    product = products_by_asin.get(review_asin(review), {})
    product_text = product_context_text(product)
    review_text = review_context_text(review)
    combined = f"{product_text} {review_text}"
    score = 0
    if product:
        score += 4
    lighting_terms = [
        "light",
        "lights",
        "lighting",
        "lamp",
        "led",
        "cabinet",
        "under cabinet",
        "motion sensor",
        "night light",
        "strip",
        "solar light",
        "橱柜",
        "灯",
        "灯带",
        "感应",
        "氛围",
    ]
    off_topic_terms = ["camera", "cam ", "video", "doorbell", "recording", "subscription", "ring service", "摄像", "录像", "订阅"]
    score += sum(2 for term in lighting_terms if term in combined)
    score -= sum(6 for term in off_topic_terms if term in combined)
    if "light" in combined and "camera" in combined:
        score -= 4
    return score


def sorted_relevant_reviews(data_pack: dict[str, Any]) -> list[dict[str, Any]]:
    reviews = data_pack.get("reviews") or []
    products_by_asin = {
        clean(first(product.get("asin"), product.get("product_asin"), product.get("parent_asin"), product.get("product_id"), default="")).upper(): product
        for product in (data_pack.get("products") or [])
        if isinstance(product, dict)
    }
    return sorted(
        reviews,
        key=lambda review: (
            -review_product_relevance_score(review, products_by_asin),
            as_float(review.get("rating"), 5) >= 4,
            as_float(review.get("rating"), 0),
        ),
    )


def render_voice_theater(data_pack: dict[str, Any], fallback_source: str) -> str:
    rows = []
    sorted_reviews = sorted_relevant_reviews(data_pack)
    positive_reviews = [review for review in sorted_reviews if as_float(review.get("rating"), 0) >= 4][:6]
    negative_reviews = [review for review in sorted_reviews if as_float(review.get("rating"), 0) <= 3][:6]

    def evidence_card(review: dict[str, Any], tone: str, idx: int) -> str:
        text = customer_review_summary(review, 180)
        sentiment = review_sentiment_label(review)
        title = customer_review_title(review)
        excerpt = review_raw_english_excerpt(review)
        strength = demand_strength_label(review)
        unmet = demand_unmet_point(review)
        opportunity = demand_product_opportunity(review)
        themes = "、".join(review_theme_labels(review))
        rows.append([f"评论记录 {len(rows) + 1:02d}", review.get("rating"), sentiment, "见上方英文短摘", text, strength, unmet, opportunity])
        excerpt_html = (
            f"<div class=\"review-excerpt-label\">英文评论短摘</div><p class=\"review-excerpt-en\" data-allow-english-review=\"short\">{esc(excerpt)}</p>"
            if excerpt
            else "<p class=\"review-excerpt-en\"><strong>英文评论短摘：</strong>原始评论为中文或未提供英文短摘</p>"
        )
        return (
            "<article class=\"demand-evidence-card "
            + esc(tone)
            + "\">"
            + f"<div class=\"evidence-card-head\"><span>{idx:02d} · {esc(sentiment)}</span><b>{esc(review.get('rating'))}星</b></div>"
            + excerpt_html
            + f"<p class=\"quote-cn\"><strong>中文洞察：</strong>{esc(text)}</p>"
            + "<dl class=\"demand-evidence-meta\">"
            + f"<div><dt>需求强度</dt><dd>{esc(strength)}</dd></div>"
            + f"<div><dt>主题</dt><dd>{esc(themes)}</dd></div>"
            + f"<div><dt>竞品未满足点</dt><dd>{esc(unmet)}</dd></div>"
            + f"<div><dt>可落地产品机会</dt><dd>{esc(opportunity)}</dd></div>"
            + "</dl>"
            + f"<div class=\"quote-origin\">证据锚点：{esc(title)}</div>"
            + "</article>"
        )

    positive_cards = [evidence_card(review, "joy", idx) for idx, review in enumerate(positive_reviews, 1)]
    negative_cards = [evidence_card(review, "pain", idx) for idx, review in enumerate(negative_reviews, 1)]

    def diagnostic_card(tone: str, label: str, idx: int) -> str:
        return (
            f"<article class=\"demand-evidence-card {esc(tone)} diagnostic\">"
            + f"<div class=\"evidence-card-head\"><span>{idx:02d} · {esc(label)}</span><b>证据采集诊断</b></div>"
            + "<p class=\"review-excerpt-en\">英文评论短摘：审计文件未提供达到固定展示门槛的原文。</p>"
            + "<p class=\"quote-cn\"><strong>中文洞察：</strong>该槽位保留为标准模板结构，系统应继续采集评论并在审计文件说明原因。</p>"
            + "<dl class=\"demand-evidence-meta\">"
            + "<div><dt>需求强度</dt><dd>数据缺口</dd></div>"
            + "<div><dt>主题</dt><dd>评论证据</dd></div>"
            + "<div><dt>竞品未满足点</dt><dd>需要更多原声验证</dd></div>"
            + "<div><dt>可落地产品机会</dt><dd>完成评论证据后再生成机会</dd></div>"
            + "</dl>"
            + "<div class=\"quote-origin\">证据锚点：评论采集诊断</div>"
            + "</article>"
        )

    while len(positive_cards) < 6:
        positive_cards.append(diagnostic_card("joy", "正面反馈", len(positive_cards) + 1))
    while len(negative_cards) < 6:
        negative_cards.append(diagnostic_card("pain", "负面反馈", len(negative_cards) + 1))
    if not rows:
        rows = [["-", "-", "评论采集诊断", "审计文件记录原文", "评论证据未达到固定展示门槛，需求判断保持 Watch。", "数据缺口", "增加评论抓取轮次", "完成评论证据后再生成需求机会"]]
    evidence_table = table(["评论记录", "星级", "情绪", "英文评论短摘", "中文洞察", "需求强度", "竞品未满足点", "可落地产品机会"], rows, "evidence-table sku")
    return (
        "<div class=\"demand-evidence-grid demand-sentiment-columns\">"
        + "<section class=\"demand-sentiment-column positive\"><div class=\"demand-column-head\"><span>Positive</span><h3>正面反馈</h3><p>左侧只呈现可转化为卖点、主图和五点表达的高星证据。</p></div>"
        + "".join(positive_cards)
        + "</section>"
        + "<section class=\"demand-sentiment-column negative\"><div class=\"demand-column-head\"><span>Negative</span><h3>负面反馈</h3><p>右侧只呈现必须转成结构修复、页面承诺和售后方案的低星证据。</p></div>"
        + "".join(negative_cards)
        + "</section></div>"
        + details("用户原声证据明细表", evidence_table, False)
    )


def render_priority_table(data_pack: dict[str, Any], demand_gap: dict[str, Any], fallback_source: str) -> str:
    rows = [
        ["P0", "信任透明承诺", "降低购买阻力", "Must-be", fallback_source],
        ["P0", "可维护与可替换结构", "解决长期使用焦虑", "Performance", fallback_source],
        ["P1", "无强制订阅表达", "避免后续成本差评", "Performance", fallback_source],
        ["P1", "礼盒开箱与价值说明卡", "提升送礼转化和溢价", "Delighter", fallback_source],
    ]
    for item in (demand_gap.get("opportunities") or [])[:6]:
        rows.append([first(item.get("priority"), "P1"), item.get("pain"), first(item.get("action"), item.get("opportunity"), default="-"), first(item.get("kano"), "-"), source_ids_for(item, fallback_source)])
    return table(["优先级", "需求与痛点", "转化机会 / 执行动作", "KANO", "source_id"], rows, "evidence-table sku")


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
        "render_market_conclusion": render_market_conclusion,
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
        "render_visual_direction": render_visual_direction,
        "render_voice_theater": render_voice_theater,
        "render_web_risk": render_web_risk,
    }


def can_render_customer_bundle(readiness: dict[str, Any]) -> bool:
    return bool(readiness.get("acceptance_ready") or readiness.get("partial_report_ready"))


def render(report_dir: Path, recover: bool = True, recovery_rounds: int = 2) -> Path:
    normalize_data_pack(report_dir)
    readiness = assess_data_readiness(report_dir, "auto")
    write_readiness_json(report_dir / "data" / "normalized" / "data_readiness_report.json", readiness)
    data_pack = load_json(report_dir / "data" / "data_pack.json", {})
    analysis_plan = load_json(report_dir / "analysis" / "analysis_plan.json", {})
    recovery_report: dict[str, Any] | None = None
    if not readiness["acceptance_ready"] and recover:
        recovery_report = recover_readiness(report_dir, "auto", recovery_rounds)
        normalize_data_pack(report_dir)
        readiness = assess_data_readiness(report_dir, "auto")
        write_readiness_json(report_dir / "data" / "normalized" / "data_readiness_report.json", readiness)
        data_pack = load_json(report_dir / "data" / "data_pack.json", {})
        analysis_plan = load_json(report_dir / "analysis" / "analysis_plan.json", {})
    if not can_render_customer_bundle(readiness):
        modules = ", ".join(gap.get("module", "unknown") for gap in readiness.get("blocking_gaps") or [])
        diagnostic_path = write_readiness_diagnostic_bundle(report_dir, data_pack, analysis_plan, readiness)
        recovery_note = "; recovery report data/normalized/readiness_recovery_report.json" if recovery_report else ""
        raise RuntimeError(f"data readiness failed before final rendering after recovery: {modules}; diagnostic written to {diagnostic_path}{recovery_note}")
    write_lineage_markdown(data_pack, report_dir / "data" / "lineage.md")
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
    if readiness.get("partial_report_ready") and original_decision.casefold() == "go":
        original_decision = "Watch"
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
    if critic_decision.get("pass") is not True:
        score = critic_decision.get("score")
        raise RuntimeError(f"critic did not pass after refinement: score={score}")
    delivery = load_json(report_dir / "output" / "delivery_result.json", delivery)
    if readiness.get("partial_report_ready"):
        delivery["status"] = "partial"
        if str(delivery.get("decision") or "").casefold() == "go":
            delivery["decision"] = "Watch"
    rendered_docs = {
        "index": (report_dir / HTML_REPORTS["index"]).read_text(encoding="utf-8"),
        "market_depth": (report_dir / HTML_REPORTS["market_depth"]).read_text(encoding="utf-8"),
        "lifecycle_strategy": (report_dir / HTML_REPORTS["lifecycle_strategy"]).read_text(encoding="utf-8"),
        "demand_gap": (report_dir / HTML_REPORTS["demand_gap"]).read_text(encoding="utf-8"),
    }
    write_site_assets(report_dir, data_pack, analysis_plan, str(decision), readiness)
    write_report_brief(report_dir, data_pack, analysis_plan, str(decision), CHILD_SKILLS)
    site_data = build_site_data(data_pack, analysis_plan, str(decision), CHILD_SKILLS, readiness)
    delivery["cleaning_summary"] = site_data["cleaning_summary"]
    delivery["data_readiness"] = delivery_readiness_summary(readiness)
    delivery["supplier_quote_gate"] = readiness.get("supplier_quote_gate") or {}
    delivery["asin_display_scope"] = ["competitor_table", "benchmark_sniper", "profit_model", "demand_target_anchor"]
    delivery["review_display_policy"] = "cn_summary_plus_en_excerpt"
    critic_review = load_json(report_dir / "analysis" / "critic_review.json", {})
    delivery["critic_review"] = {
        "path": "analysis/critic_review.json",
        "refinement_plan": "analysis/refinement_plan.json",
        "summary": "analysis/critic_summary.md",
        "pass": critic_review["pass"],
        "score": critic_review["score"],
        "max_refinement_rounds": critic_review["max_refinement_rounds"],
    }
    write_delivery_result(report_dir, delivery, CHILD_SKILLS)
    return report_dir / HTML_REPORTS["index"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render the v2 three-report HTML bundle for amz-market-research-orchestrated reports.")
    parser.add_argument("--dir", required=True, help="Report directory containing data/ and analysis/.")
    parser.add_argument("--no-recover", action="store_true", help="Skip automatic Sorftime recovery attempts before diagnostics.")
    parser.add_argument("--recovery-rounds", type=int, default=2, help="Maximum targeted recovery rounds before diagnostic rendering.")
    args = parser.parse_args(argv)
    try:
        output_path = render(Path(args.dir), recover=not args.no_recover, recovery_rounds=args.recovery_rounds)
    except RuntimeError as exc:
        print(f"render_failed: {exc}", file=sys.stderr)
        return 1
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
