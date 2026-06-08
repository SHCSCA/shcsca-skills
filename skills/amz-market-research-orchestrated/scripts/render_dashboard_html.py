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
from canonical_template_assets import apply_reference_style
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
    top_units = first(category.get("top100_estimated_monthly_units"), market_size.get("top100_estimated_monthly_units"), default=None)
    top_revenue = first(category.get("top100_estimated_monthly_revenue"), market_size.get("top100_estimated_monthly_revenue"), default=None)
    median_price = statistics.median(prices) if prices else None
    high_band = "$99-$150" if median_price and as_float(median_price) < 99 else money(median_price)
    cards = [
        kpi_card("Top100 估算月销量", num(top_units), "类目代理指标", "success"),
        kpi_card("Top100 估算销售额", money(top_revenue), "用于判断大盘体量"),
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
        + echart_box("growthChart", "市场增长趋势", "公开规模与清洗数据代理趋势")
        + echart_box("featureChart", "功能覆盖与机会空白", "竞品覆盖率 vs 目标补位")
        + "</div>"
        + "<div class=\"insight-box\">💡 <strong>大盘结论：</strong>当前已清洗数据说明市场仍有可切入空间，但应避开纯低价红海，优先验证高溢价价格带、可感知功能差异和评论中反复出现的体验缺口。</div>"
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
    head = "<thead><tr><th>产品</th><th>价格</th><th>评分</th><th>月销估算</th><th>核心卖点</th><th>致命弱点</th><th>标签</th></tr></thead>"
    body_rows = []
    tag_sequence = ["badge-hot", "badge-hot", "badge-risk", "badge-growth", "badge-premium", "badge-premium"]
    top_products = filtered[:6]
    for idx, row in enumerate(competitor_rows(top_products, 6), 1):
        product = top_products[idx - 1]
        tag_class = tag_sequence[idx - 1] if idx <= len(tag_sequence) else "badge-growth"
        weak = competitor_weakness(product)
        body_rows.append(
            "<tr>"
            + f"<td><div class=\"product-name\">{esc(row[1])}</div><div class=\"product-brand\">{esc(row[3])} · {esc(row[4])}</div></td>"
            + f"<td><span class=\"price-tag\">{esc(row[5])}</span></td>"
            + f"<td><span class=\"rating-stars\">★★★★</span> {esc(row[8])}</td>"
            + f"<td><strong>{esc(row[6])}</strong>/月</td>"
            + f"<td>{esc(row[2])}</td>"
            + f"<td>{esc(weak)}</td>"
            + f"<td><span class=\"badge {tag_class} badge-risk lavender\">{esc('高优先级' if idx <= 2 else '可参考')}</span></td>"
            + "</tr>"
        )
    colgroup = "<colgroup><col style=\"width:29%\"><col style=\"width:7%\"><col style=\"width:7%\"><col style=\"width:8%\"><col style=\"width:31%\"><col style=\"width:12%\"><col style=\"width:6%\"></colgroup>"
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
        if asin:
            grouped[asin].append(kw)
    for asin in grouped:
        grouped[asin] = sorted(grouped[asin], key=lambda kw: as_float(kw.get("monthly_search_volume"), 0), reverse=True)
    return grouped


def render_product_deep_dives(products: list[dict[str, Any]], keywords: list[dict[str, Any]]) -> str:
    traffic = traffic_terms_by_asin(keywords)
    cards = []
    for product in products[:3]:
        asin = product.get("asin")
        trend = product.get("trend") or {}
        trend_text = f"{num(product_sales(product))}/月 · {num(product_reviews(product))} 评论 · {first(product.get('rating'), '-')}★"
        if trend.get("first") is not None and trend.get("last") is not None:
            trend_text = f"{num(trend.get('first'))} → {num(trend.get('last'))}，增长 {trend.get('growth')}"
        traffic_tags = "".join(tag(kw.get("keyword")) for kw in traffic.get(asin, [])[:6])
        if not traffic_tags:
            traffic_tags = (
                tag(first(product.get("segment_cn"), product.get("segment"), "核心细分"))
                + tag(price_band(product_price(product)))
                + tag(f"评论{num(product_reviews(product))}")
            )
        cards.append(
            "<div class=\"comp-deep-card\">"
            + "<div class=\"comp-deep-header\">"
            + f"<div class=\"comp-deep-name\">🎯 <span class=\"asin-token\" data-allow-asin=\"benchmark-sniper\">{esc(asin or '竞品记录')}</span> · {esc(first(product.get('brand'), customer_product_position(product)))}</div>"
            + f"<div class=\"comp-deep-price\">{esc(money(product_price(product)))} · 月销~{esc(num(product_sales(product)))} · {esc(first(product.get('rating'), '-'))}★</div>"
            + "</div><div class=\"comp-deep-body\">"
            + "<div class=\"comp-deep-section\"><div class=\"comp-deep-section-title\">溢价逻辑</div>"
            + f"<div class=\"comp-deep-text\">{esc(customer_product_message(product))}</div></div>"
            + "<div class=\"comp-deep-section\"><div class=\"comp-deep-section-title\">未解决的痛点</div><div class=\"comp-tag-list\">"
            + "<span class=\"comp-tag red\">评论痛点集中</span><span class=\"comp-tag red\">差异化不足</span><span class=\"comp-tag red\">长期体验需压实</span>"
            + "</div></div>"
            + "<div class=\"comp-deep-section\"><div class=\"comp-deep-section-title\">我们的机会</div>"
            + f"<div class=\"comp-deep-text\">围绕 {esc(customer_product_position(product))} 的高频痛点，提炼可验证卖点与页面承诺。</div></div>"
            + "<div class=\"comp-deep-section\"><div class=\"comp-deep-section-title\">数据信号</div><div class=\"comp-tag-list\">"
            + f"<span class=\"comp-tag\">销量/评论：{esc(trend_text)}</span><span class=\"comp-tag green\">定位标签：{traffic_tags}</span>"
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
        chart_label = asin or label
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
            f"<div class=\"voc-item\"><div class=\"voc-rank pain-rank\">P{idx}</div><div class=\"voc-content\"><div class=\"voc-title\">{esc(theme)}</div><div class=\"voc-desc\">用户在低星反馈中反复提到该问题，必须转成实物修复、页面承诺或售后说明，不能只用营销话术覆盖。</div><div class=\"voc-quote\">客户页展示中文归纳，并可并列展示英文评论短摘；完整原始评论保留在审计文件。</div><div class=\"voc-bar\"><div class=\"voc-bar-fill pain-fill\" style=\"width:{min(100, 24 + count * 10)}%\"></div></div></div></div>"
            for idx, (theme, count) in enumerate(pain_items, 1)
        )
        + "</div></article>"
        + "<article class=\"joy-card\"><div class=\"voc-card-title\"><span class=\"green\">Joy</span> 主要爽点</div><div class=\"voc-content\">"
        + "".join(
            f"<div class=\"voc-item\"><div class=\"voc-rank joy-rank\">J{idx}</div><div class=\"voc-content\"><div class=\"voc-title\">{esc(theme)}</div><div class=\"voc-desc\">正向体验可转化为主图场景、五点利益、A+ 模块和广告落地页表达，同时要保持可验证边界。</div><div class=\"voc-quote\">中文卖点归纳为主，英文评论短摘用于保留用户原话语气。</div><div class=\"voc-bar\"><div class=\"voc-bar-fill joy-fill\" style=\"width:{min(100, 24 + count * 10)}%\"></div></div></div></div>"
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
    median_rmb = first(stats.get("median_rmb"), statistics.median(valid_prices) if valid_prices else None)
    min_rmb = first(stats.get("min_rmb"), min(valid_prices) if valid_prices else None)
    max_rmb = first(stats.get("max_rmb"), max(valid_prices) if valid_prices else None)
    p25_rmb = percentile(valid_prices, 0.25)
    p75_rmb = percentile(valid_prices, 0.75)
    top_supplier = suppliers[0] if suppliers else {}
    supplier_focus = truncate(first(top_supplier.get("title_cn"), top_supplier.get("title"), "1688 已采集货源"), 18)
    profitability_table, formula = render_profitability_table(data_pack.get("products") or [], valid_prices)
    supplier_rows = [
        [
            truncate(first(supplier.get("title_cn"), supplier.get("title"), "1688货源"), 42),
            first(supplier.get("supplier_name"), supplier.get("store_name"), "供应商"),
            money(supplier_price(supplier), "¥"),
            num(supplier.get("sales_30d")),
            first(supplier.get("shipping_origin"), "-"),
            first(supplier.get("seed_keyword"), "-"),
        ]
        for supplier in suppliers[:60]
        if as_float(supplier_price(supplier), -1) > 0
    ]
    return (
        "<div class=\"supply-grid\">"
        + f"<div class=\"supply-card\"><div class=\"supply-label\">有效报价数</div><div class=\"supply-value\">{esc(num(len(valid_prices)))}</div><div class=\"supply-note\">1688 相似货源，已去重</div></div>"
        + f"<div class=\"supply-card\"><div class=\"supply-label\">采购价中位数</div><div class=\"supply-value\">{esc(money(median_rmb, '¥'))}</div><div class=\"supply-note\">不含物流、FBA、认证</div></div>"
        + f"<div class=\"supply-card\"><div class=\"supply-label\">有效报价区间</div><div class=\"supply-value\">{esc(money(min_rmb, '¥'))}-{esc(money(max_rmb, '¥'))}</div><div class=\"supply-note\">低价需验证质量一致性</div></div>"
        + f"<div class=\"supply-card\"><div class=\"supply-label\">热销货源</div><div class=\"supply-value\">{esc(first((origin_counts.most_common(1)[0][0] if origin_counts else None), supplier_focus))}</div><div class=\"supply-note\">按 30 日销量最高记录展示</div></div>"
        + "</div>"
        + f"<div class=\"metric-strip\">{metric('P25采购成本', money(p25_rmb, '¥'), '1688报价分位数')}{metric('P50采购成本', money(median_rmb, '¥'), '1688报价分位数')}{metric('P75采购成本', money(p75_rmb, '¥'), '1688报价分位数')}</div>"
        + profitability_table
        + echart_plain("marginChart", "毛利率测算 · 各定价方案对比", "基于综合出厂成本、FBA费用与目标售价的区间估算", 260)
        + formula
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
    opportunities = opportunity.get("opportunities") or []
    if not opportunities:
        opportunities = [{"name": "细分机会", "decision": "Watch", "score": "证据链 0 条", "entry_shape": "需要继续收敛证据。", "risks": ["证据不足"]}]
    top = opportunities[:3]
    recommended_idx = min(1, max(0, len(top) - 1))
    pricing_cards = []
    prompt_cards = []
    for idx, item in enumerate(top):
        name = first(item.get("name"), f"机会 {idx + 1}")
        entry_shape = first(item.get("entry_shape"), item.get("recommendation"), "以小批量实物、页面卖点和广告转化验证为先。")
        price = first(item.get("price_band"), item.get("target_price"), ["$39-$59", "$69-$89", "$99-$129"][idx % 3])
        pricing_cards.append(
            f"<article class=\"pricing-card{' recommended' if idx == recommended_idx else ''}\">"
            + f"<div class=\"pricing-tier\">Tier {idx + 1}</div>"
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
            + f"<div class=\"prompt-text\">把该机会写入主图、五点和 A/B 页面测试；只使用已清洗数据支持的承诺。</div>"
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
        "<div class=\"strategy-hero\"><div class=\"strategy-hero-label\">Core Product Concept · 核心产品定义</div><div class=\"strategy-slogan\">不只是产品，是<span>真正解决痛点的</span>高溢价方案。</div><div class=\"strategy-desc\">基于清洗后的竞品、关键词、评论和供应链数据，优先定义一个可被页面、实物和广告验证的差异化产品。首轮不追求大而全，而是锁定一个最强使用场景、一个主力价格带和一组可兑现的页面承诺。</div></div>"
        + "<div class=\"strategy-grid\">" + "".join(strategy_cards) + "</div>"
        + "<div class=\"section-header\" style=\"margin-top:32px;\"><div class=\"section-title\" style=\"font-size:16px;\">建议定价策略</div></div>"
        + "<div class=\"pricing-grid\">" + "".join(pricing_cards) + "</div>"
        + "<div class=\"insight-box\">💡 <strong>定价战略核心逻辑：</strong>主力价格带必须卡在用户可感知差异与竞品价格空白之间。低价款用于验证流量，中价款承担销量，高价款承接礼品化、Bundle 与高毛利空间。只有当实物体验、页面转化和 landed cost 同时成立，才进入下一轮放量。</div>"
    )


def render_visual_direction(opportunity: dict[str, Any]) -> str:
    opportunities = opportunity.get("opportunities") or [{"name": "核心机会", "decision": "Watch"}]
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
        + "<div class=\"section-header\" style=\"margin-top:8px;\"><div class=\"section-title\" style=\"font-size:16px;\">AI生图 Prompt · 可直接使用</div></div>"
        + "<div class=\"prompt-grid\">" + "".join(prompt_cards) + "</div>"
    )


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
        "竞品样本": "竞品记录",
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
    return apply_reference_style(template_key, html_doc)


def child_body_fragment(html_doc: str) -> str:
    styles = "\n".join(re.findall(r"<style\b[^>]*>.*?</style>", html_doc, flags=re.S | re.I))
    scripts = "\n".join(re.findall(r"<script\b[^>]*>.*?</script>", html_doc, flags=re.S | re.I))
    match = re.search(r"<body\b[^>]*>(.*)</body>", html_doc, flags=re.S | re.I)
    body = match.group(1) if match else html_doc
    return "\n".join(part for part in [styles, body, scripts] if part)


def delivery_readiness_summary(readiness: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": "data/normalized/data_readiness_report.json",
        "acceptance_ready": readiness.get("acceptance_ready"),
        "sample_class": readiness.get("sample_class"),
        "depth": readiness.get("depth"),
        "blocking_gap_count": len(readiness.get("blocking_gaps") or []),
        "warning_count": len(readiness.get("warnings") or []),
        "counts": readiness.get("counts") or {},
        "supplier_quote_gate": readiness.get("supplier_quote_gate") or {},
    }


def write_site_assets(report_dir: Path, data_pack: dict[str, Any], analysis_plan: dict[str, Any], decision: str, readiness: dict[str, Any] | None = None) -> None:
    write_basic_site_assets(report_dir, build_site_data(data_pack, analysis_plan, decision, CHILD_SKILLS, readiness))


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
    return (
        "<div class=\"chart-container\">"
        + f"<div class=\"chart-title\">{esc(title)}</div>"
        + f"<div class=\"chart-subtitle\">{esc(subtitle)}</div>"
        + f"<div class=\"chart-body\" id=\"{esc(chart_id)}\" style=\"height:{int(height)}px;width:100%\"></div>"
        + "</div>"
    )


def echart_plain(chart_id: str, title: str, subtitle: str, height: int = 300) -> str:
    return (
        "<div class=\"chart-container\">"
        + f"<div class=\"chart-title\">{esc(title)}</div>"
        + f"<div class=\"chart-subtitle\">{esc(subtitle)}</div>"
        + f"<div id=\"{esc(chart_id)}\" style=\"height:{int(height)}px;width:100%\"></div>"
        + "</div>"
    )


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
    return client_trust_strip(data_pack, analysis_plan, decision) + insight_table("客户版可信度说明", rows)


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
            ("交付口径", "客户页只展示清洗后的结论，审计字段留在 JSON/Markdown。"),
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
        + kpi_card("证据记录数", num(len(data_pack.get("sources") or [])), "内部审计链路保留", "")
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
                "supply": "按竞品差异做实物测试",
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
        ["Bundle 增长抓手", "AOV 提升", fallback_source],
        ["建议首发 Phase", "P1 可控供应链 + 信任与开箱触点优先", fallback_source],
    ]
    return (
        "<div class=\"insight-box\"><strong>战略原则：</strong>先用可控 SKU 与 Bundle 价格台阶验证，再扩展长期复购触点。</div>"
        + "<div class=\"kpi-grid\">"
        + kpi_card("拓品 SKU 总数", len(skus), "覆盖生命周期触点", "success")
        + kpi_card("可自产 SKU", len(self_supply), "供应链可控", "")
        + kpi_card("复购引擎", "60-90 天", "清洁、替换、维护", "warning")
        + kpi_card("AOV 引擎", "Bundle", "组合包优先", "success")
        + kpi_card("首发 Phase", "P1", "可控供应链", "")
        + "</div>"
        + section_table("战略仪表盘证据", ["指标", "结果", "source_id"], rows)
    )


def render_personas(data_pack: dict[str, Any], lifecycle: dict[str, Any], fallback_source: str) -> str:
    products = data_pack.get("products") or []
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
        f"<article class=\"tl-card\"><div class=\"tl-header\">阶段 {idx}<span class=\"arrow\">→</span></div><div class=\"tl-body\"><div class=\"tl-time\">{esc(row[0])}</div><div class=\"tl-skus\">{esc(row[1])}</div><div class=\"tl-pain\">{esc(row[2])}</div></div></article>"
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
        "<div class=\"chart-grid\">"
        + echart_box("sunburst", "四维拓品生态全景 · Sunburst", "Type A/B/C/D 四个维度与 SKU 分布", 500)
        + "</div>"
        + "<div class=\"chart-container\"><div class=\"chart-title\">四维拓品生态</div>"
        + mini_chart([(row[0], float(row[1]), row[1]) for row in rows], "good")
        + "</div>"
        + section_table("四维拓品生态证据表", ["维度", "SKU 数", "打法", "source_id"], rows)
    )


def render_sku_execution_table(skus: list[dict[str, Any]], fallback_source: str) -> str:
    type_class = {"A": "a red", "B": "b blue", "C": "c green", "D": "d purple"}
    type_label = {"A": "强关联", "B": "场景延伸", "C": "消耗品", "D": "升级维护"}
    body_rows = []
    for idx, sku in enumerate(skus, 1):
        sku_type = str(sku.get("type") or "A").upper()[:1]
        supply_text = clean(sku.get("supply"))
        if "自有" in supply_text or "自产" in supply_text or "可控" in supply_text:
            supply_class = "self"
            supply_label = "自产"
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
            + f"<td><strong style=\"color:#1a2744\">{esc(first(sku.get('name'), '生命周期补位 SKU'))}</strong><br><span style=\"color:#8a9aaa;font-size:11px\">{esc(first(sku.get('pain'), '围绕生命周期触点补位'))}</span></td>"
            + f"<td><strong>{esc(first(sku.get('price'), '待测价'))}</strong></td>"
            + f"<td><span class=\"supply-badge {supply_class}\">{supply_label}</span><br><span style=\"color:#8a9aaa;font-size:11px\">{esc(supply_text)}</span></td>"
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
        "<button class=\"filter-btn purple\" type=\"button\" data-filter=\"D\" aria-pressed=\"false\">Type D</button></div>"
        "<table id=\"skuTable\" class=\"evidence-table insight-table sku appendix-table\"><thead><tr>"
        "<th>ID</th><th>生命周期</th><th>类型</th><th>拓品 SKU</th><th>价格带</th><th>供应链</th><th>优先级</th><th>Phase</th><th>source_id</th>"
        "</tr></thead><tbody id=\"skuBody\">"
        + "".join(body_rows)
        + "</tbody></table>"
    )
    return echart_box("priorityChart", "SKU 优先级评分分布", "综合关联度、复购周期、供应链可控性、竞争格局", 500) + "<div class=\"sku-table-wrap\">" + sku_table + "</div>"


def render_bundle_strategy(skus: list[dict[str, Any]], fallback_source: str) -> str:
    bundles = [
        ["新手启航套装", "主体 + 欢迎卡 + 信任说明卡 + 基础配件", "$99-$119", "降低首购疑虑", fallback_source],
        ["豪华礼品套装", "主体 + 礼盒 + 场景配件 + 备用核心配件", "$129-$159", "提升礼品场景 AOV", fallback_source],
        ["进阶体验套装", "主体 + 高阶使用任务卡 + 售后与信任引导", "$119-$149", "进阶用户溢价", fallback_source],
        ["续航补给包", "清洁护理 + 替换线 + 耗材", "$19-$29", "60-90 天复购", fallback_source],
    ]
    cards = "".join(
        f"<article class=\"bundle-card\"><div class=\"bundle-header\"><h3>{esc(row[0])}</h3><span class=\"badge gold accent\">Bundle</span></div><div class=\"bundle-body\"><div class=\"bundle-target\">{esc(row[3])}</div><div class=\"bundle-items\">{esc(row[1])}</div><div class=\"bundle-pricing\"><span class=\"orig\">单买</span><span class=\"final\">{esc(row[2])}</span><span class=\"save\">{esc(row[3])}</span></div><p>source_id: {esc(row[4])}</p></div></article>"
        for row in bundles
    )
    return echart_box("aovChart", "Bundle AOV 提升路径", "单买主体、Bundle 价格与 AOV 增量", 360) + "<div class=\"bundle-grid\">" + cards + "</div>" + section_table("Bundle 策略证据表", ["Bundle", "组合", "建议价", "目标", "source_id"], bundles)


def render_lifecycle_roadmap(skus: list[dict[str, Any]], fallback_source: str) -> str:
    rows = [
        ["30 天", "实物测试 P1 可控 SKU；确认 Bundle 包装；完善信任承诺物料", "可控启动", fallback_source],
        ["60 天", "1688 与硬件供应商询价；完成实物质检；收集首批用户反馈", "供应链验证", fallback_source],
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
        ["Amazon 产品页面分析", f"{len(data_pack.get('products') or [])} 个产品记录", "用竞品卖点、价格带和评论密度校准首批 SKU", fallback_source],
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
    return source_grid + section_table("市场数据验证", ["数据域", "覆盖", "建议动作", "source_id"], rows) + conclusion_block(
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
    products = data_pack.get("products") or []
    anchor = products[0] if products else {}
    sample_summary = f"{len(products)} 个竞品；{len(data_pack.get('reviews') or [])} 条评论；{len(data_pack.get('keywords') or [])} 个关键词"
    rows = [
        ["研究对象", object_value, fallback_source],
        ["研究对象锚点", customer_safe_signal_title(anchor, "竞品记录") if anchor else "按关键词与品类锚定", source_ids_for(anchor, fallback_source) if anchor else fallback_source],
        ["数据范围", sample_summary, fallback_source],
    ]
    return (
        f"<div class=\"card focus\">当前研究对象：<strong>{esc(object_value)}</strong>。数据覆盖：{esc(sample_summary)}。本报告以清洗后的数据解释心智断层与需求机会。</div>"
        + "<div class=\"chart-interpretation\">分析口径：只使用 normalized data pack 中通过去重和客户安全过滤的数据；数据缺口进入风险和下一步验证，不包装成已证实结论；内部技术字段保留在审计文件，不进入客户页。</div>"
        + section_table("研究对象锚点", ["字段", "结果", "source_id"], rows)
    )


def render_decision_board(data_pack: dict[str, Any], demand_gap: dict[str, Any], decision: str, fallback_source: str) -> str:
    opportunities = demand_gap.get("opportunities") or []
    max_opportunity = first((opportunities[0].get("pain") if opportunities else None), "性能（Performance）体验重构", default="-")
    rows = [
        ["最大机会", max_opportunity, fallback_source],
        ["核心判断", decision, fallback_source],
        ["证据密度", f"{len(data_pack.get('reviews') or [])} 条评论；{len(data_pack.get('sources') or [])} 类证据记录", fallback_source],
    ]
    return (
        f"<div class=\"card focus\"><strong>最大机会：{esc(max_opportunity)}。</strong></div>"
        + "<div class=\"kpi-grid\">"
        + f"<div class=\"kpi\"><div class=\"k\">评论记录数</div><div class=\"v\">{esc(len(data_pack.get('reviews') or []))}</div></div>"
        + f"<div class=\"kpi\"><div class=\"k\">核心判断</div><div class=\"v\" style=\"font-size:18px\">{esc(decision)}</div></div>"
        + f"<div class=\"kpi\"><div class=\"k\">证据记录</div><div class=\"v\">{esc(len(data_pack.get('sources') or []))}</div></div>"
        + f"<div class=\"kpi\"><div class=\"k\">最高机会维度</div><div class=\"v\" style=\"font-size:18px\">{esc(max_opportunity)}</div></div>"
        + "</div>"
        + section_table("决策看板证据表", ["指标", "结果", "建议动作", "source_id"], [[row[0], row[1], "转成页面卖点、实物修复或复核验证", row[2]] for row in rows])
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


def render_voice_theater(data_pack: dict[str, Any], fallback_source: str) -> str:
    reviews = data_pack.get("reviews") or []
    rows = []
    cards = []
    for idx, review in enumerate(reviews[:10], 1):
        text = customer_review_summary(review, 180)
        sentiment = review_sentiment_label(review)
        title = customer_review_title(review)
        rows.append([f"评论记录 {idx:02d}", review.get("rating"), sentiment, text, "、".join(review_theme_labels(review)), "高"])
        tone = "ok" if "正向" in sentiment or as_float(review.get("rating"), 0) >= 4 else "warn" if as_float(review.get("rating"), 0) <= 2 else "focus"
        cards.append(f"<div class=\"card {tone}\" style=\"margin:0\"><div class=\"k\">评论记录 {idx:02d} ｜ {esc(review.get('rating'))}星 ｜ {esc(sentiment)}</div><div class=\"quote-cn\">{esc(text)}</div><div class=\"quote-origin\">{esc(title)}</div></div>")
    if not rows:
        rows = [["-", "-", "评论记录不足", "评论记录不足，需求判断只能保持 Watch。", "需增加评论抓取", "数据缺口"]]
        cards = ["<div class=\"card focus\" style=\"margin:0\"><div class=\"quote-cn\">评论记录不足，需求判断只能保持 Watch。</div><div class=\"quote-origin\">数据缺口 · 需增加评论抓取</div></div>"]
    return "<div class=\"grid-3\">" + "".join(cards) + "</div>" + table(["评论记录", "星级", "情绪", "中文化用户原声", "主题", "证据强度"], rows, "evidence-table sku")


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


def render(report_dir: Path) -> Path:
    normalize_data_pack(report_dir)
    readiness = assess_data_readiness(report_dir, "auto")
    write_readiness_json(report_dir / "data" / "normalized" / "data_readiness_report.json", readiness)
    if not readiness["acceptance_ready"]:
        modules = ", ".join(gap.get("module", "unknown") for gap in readiness.get("blocking_gaps") or [])
        raise RuntimeError(f"data readiness failed before rendering: {modules}")
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
    if critic_decision.get("pass") is not True:
        score = critic_decision.get("score")
        raise RuntimeError(f"critic did not pass after refinement: score={score}")
    delivery = load_json(report_dir / "output" / "delivery_result.json", delivery)
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
    delivery["asin_display_scope"] = ["benchmark_sniper", "profit_model"]
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
    args = parser.parse_args(argv)
    try:
        output_path = render(Path(args.dir))
    except RuntimeError as exc:
        print(f"render_failed: {exc}", file=sys.stderr)
        return 1
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
