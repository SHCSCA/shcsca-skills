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
from urllib.parse import urlparse

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


def report_readiness_view(readiness: dict[str, Any], quality: dict[str, Any] | None = None, decision: str | None = None) -> dict[str, Any]:
    quality = quality or {}
    raw_decision = clean(decision) or "Watch"
    acceptance_ready = readiness.get("acceptance_ready") is True
    partial_ready = readiness.get("partial_report_ready") is True
    supply_blocked = readiness.get("supply_conclusion_blocked") is True
    if acceptance_ready:
        delivery_state = "完整可交付"
        final_decision = raw_decision or "Watch"
        evidence_strength = customer_quality_summary(quality)[0]
        quality_label = evidence_strength
        quality_sub = "关键门禁已通过，可输出完整决策报告"
        quality_tone = "success"
    elif partial_ready:
        delivery_state = "诊断交付"
        final_decision = "Watch" if raw_decision.casefold() == "go" else raw_decision or "Watch"
        evidence_strength = "中 / 诊断交付"
        quality_label = "诊断交付"
        quality_sub = "局部门禁未通过，只输出可用结论和中文诊断"
        quality_tone = "warning"
    else:
        delivery_state = "阻断交付"
        final_decision = "No-Go" if raw_decision.casefold() == "go" else raw_decision or "No-Go"
        evidence_strength = "低 / 阻断交付"
        quality_label = "阻断交付"
        quality_sub = "核心门禁未通过，不能输出完整客户结论"
        quality_tone = "warning"
    if supply_blocked and evidence_strength == "证据充分":
        evidence_strength = "中 / 诊断交付"
        quality_label = "诊断交付"
        quality_sub = "供应链测算未达门槛，成本与毛利结论已阻断"
        quality_tone = "warning"
    gaps = []
    for gap in readiness.get("blocking_gaps") or []:
        if not isinstance(gap, dict):
            continue
        gaps.append(
            {
                "module": customer_safe_gap_text(gap.get("module")),
                "reason": customer_safe_gap_text(first(gap.get("reason"), gap.get("gap"), default="当前门禁未通过")),
                "impact": customer_safe_gap_text(first(gap.get("impact"), default="不能输出对应模块的完整结论")),
                "next_step": customer_safe_gap_text(first(gap.get("next_step"), gap.get("next_action"), default="补齐数据后重新渲染")),
            }
        )
    if supply_blocked and not any("供应" in str(item.get("module")) or "1688" in str(item.get("reason")) for item in gaps):
        gaps.insert(
            0,
            {
                "module": "供应链测算",
                "reason": "严格相关 1688 成品报价未达到 50 条或质量门禁未通过",
                "impact": "不能输出毛利率、成本分位数和供应链可控结论",
                "next_step": "继续用细分赛道中文词补采 1688，并保留标题、供应商、价格和链接",
            },
        )
    return {
        "delivery_state": delivery_state,
        "decision": final_decision if final_decision in {"Go", "Watch", "No-Go"} else "Watch",
        "evidence_strength": evidence_strength,
        "quality_label": quality_label,
        "quality_sub": quality_sub,
        "quality_tone": quality_tone,
        "supply_blocked": supply_blocked,
        "supply_status": "供应链测算未达门槛" if supply_blocked else "供应链测算门禁通过",
        "blocking_gaps": gaps,
        "counts": readiness.get("counts") or {},
        "sample_class": readiness.get("sample_class"),
    }


def current_readiness_view(data_pack: dict[str, Any], analysis_plan: dict[str, Any] | None = None, decision: str | None = None) -> dict[str, Any]:
    view = data_pack.get("report_readiness_view")
    if isinstance(view, dict) and view:
        return view
    readiness = data_pack.get("report_readiness") or {}
    if isinstance(readiness, dict) and readiness:
        return report_readiness_view(readiness, data_pack.get("quality") or {}, decision or "Watch")
    label, sub, tone = customer_quality_summary(data_pack.get("quality") or {})
    return {
        "delivery_state": "完整可交付",
        "decision": clean(decision) or "Watch",
        "evidence_strength": label,
        "quality_label": label,
        "quality_sub": sub,
        "quality_tone": tone,
        "supply_blocked": False,
        "supply_status": "供应链测算门禁通过",
        "blocking_gaps": [],
    }


def has_cjk_text(value: Any) -> bool:
    return re.search(r"[\u4e00-\u9fff]", clean(value)) is not None


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


def effective_records(data_pack: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = data_pack.get(f"effective_{key}")
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    value = data_pack.get(key)
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def effective_products(data_pack: dict[str, Any]) -> list[dict[str, Any]]:
    return relevant_products(effective_records(data_pack, "products"))


def effective_keywords(data_pack: dict[str, Any]) -> list[dict[str, Any]]:
    return effective_records(data_pack, "keywords")


def effective_reviews(data_pack: dict[str, Any]) -> list[dict[str, Any]]:
    return effective_records(data_pack, "reviews")


def customer_visible_reviews(data_pack: dict[str, Any]) -> list[dict[str, Any]]:
    reviews = effective_reviews(data_pack)
    products = effective_products(data_pack)
    product_asins = {
        clean(first(product.get("asin"), product.get("product_asin"), product.get("parent_asin"), product.get("product_id"), default="")).upper()
        for product in products
        if isinstance(product, dict)
    }
    product_asins.discard("")
    if not product_asins:
        return reviews
    visible = []
    for review in reviews:
        asin = clean(first(review.get("asin"), review.get("product_asin"), review.get("parent_asin"), review.get("product_id"), default="")).upper()
        if not asin or asin in product_asins:
            visible.append(review)
    return visible


def effective_suppliers(data_pack: dict[str, Any]) -> list[dict[str, Any]]:
    return effective_records(data_pack, "suppliers")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def report_label_profile(data_pack: dict[str, Any]) -> dict[str, Any]:
    profile = data_pack.get("report_label_profile") or {}
    return profile if isinstance(profile, dict) else {}


def attach_report_label_profile(data_pack: dict[str, Any], analysis_plan: dict[str, Any]) -> None:
    profile = analysis_plan.get("report_label_profile") or data_pack.get("report_label_profile") or {}
    if not isinstance(profile, dict):
        profile = {}
    data_pack["report_label_profile"] = profile
    product_labels = profile.get("product_title_labels") or {}
    segment_labels = profile.get("segment_labels") or {}
    keyword_labels = profile.get("traffic_tag_labels") or profile.get("keyword_labels") or {}
    if not isinstance(product_labels, dict):
        product_labels = {}
    if not isinstance(segment_labels, dict):
        segment_labels = {}
    if not isinstance(keyword_labels, dict):
        keyword_labels = {}

    for product in effective_products(data_pack):
        asin = clean(product.get("asin")).upper()
        raw_title = clean(product.get("title"))
        raw_segment = clean(first(product.get("segment_cn"), product.get("segment"), product.get("category_cn"), product.get("category"), default=""))
        customer_title = clean(product_labels.get(asin) or product_labels.get(raw_title) or "")
        customer_segment = clean(segment_labels.get(raw_segment) or "")
        if customer_title:
            product["customer_title_cn"] = customer_title
        if customer_segment:
            product["customer_segment_cn"] = customer_segment

    for keyword in effective_keywords(data_pack):
        raw_keyword = clean(keyword.get("keyword"))
        label = clean(keyword_labels.get(raw_keyword.casefold()) or keyword_labels.get(raw_keyword) or "")
        if label:
            keyword["customer_label_cn"] = label


def profile_lifecycle_type_labels(data_pack: dict[str, Any]) -> dict[str, str]:
    labels = report_label_profile(data_pack).get("lifecycle_type_labels") or {}
    if not isinstance(labels, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, value in labels.items():
        label = clean(value)
        if label:
            normalized[lifecycle_strategy_type_key(key)] = label
    return normalized


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
    products = effective_products(data_pack)
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
    pool_label = "Top100" if len(products) >= 100 else "当前有效竞品池"
    readiness = current_readiness_view(data_pack)
    supply_notice = ""
    market_conclusion = "当前已验证数据说明市场仍有可切入空间，但应避开纯低价红海，优先验证高溢价价格带、可感知功能差异和评论中反复出现的体验缺口。"
    if readiness.get("supply_blocked"):
        supply_notice = (
            "<div class=\"insight-box warning-box\"><strong>供应链测算未达门槛：</strong>"
            "本页市场、竞品、VOC 和内容信号可继续阅读；成本、毛利率和供应链可控结论已降级为诊断，必须补齐严格相关 1688 成品报价后恢复测算。</div>"
        )
        market_conclusion = "当前市场与需求证据可支持继续观察和补采，但供应链测算未达门槛，不能输出完整进入或毛利率结论。"
    cards = [
        kpi_card(f"{pool_label}估算月销量", num(top_units), "由类目字段或有效竞品池销量聚合", "success"),
        kpi_card(f"{pool_label}估算销售额", money(top_revenue), "由有效竞品售价 × 月销聚合"),
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
        + supply_notice
        + "<div class=\"chart-grid\">"
        + echart_box("priceChart", "价格带销量分布图", "Amazon US · 各价格区间月销量估算")
        + echart_box("bubbleChart", "竞品价格区间竞争密度", "价格带竞品数量 vs 月销量估算 · 气泡大小=市场规模")
        + "</div>"
        + "<div class=\"chart-grid\">"
        + echart_box("growthChart", "市场增长趋势", "公开规模与月销量代理趋势")
        + echart_box("featureChart", "功能覆盖与机会空白", "竞品覆盖率 vs 目标补位")
        + "</div>"
        + f"<div class=\"insight-box\">💡 <strong>大盘结论：</strong>{esc(market_conclusion)}</div>"
    )


def render_keywords(data_pack: dict[str, Any]) -> str:
    keywords = [kw for kw in effective_keywords(data_pack) if kw.get("keyword")]
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
                customer_brand_label(product),
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


def customer_brand_label(product: dict[str, Any]) -> str:
    brand = clean(product.get("brand"))
    segment = clean(first(product.get("customer_segment_cn"), product.get("segment_cn"), product.get("segment"), customer_product_position(product), default="目标赛道"))
    if not brand:
        return f"{segment}竞品" if segment else "目标竞品"
    ascii_words = re.findall(r"[A-Za-z]{2,}", brand)
    if not has_cjk_text(brand) and len(ascii_words) >= 3:
        return f"{segment}竞品" if segment else "标杆竞品"
    return brand[:40]


def is_supplier_image_url(url: str) -> bool:
    text = clean(url).casefold()
    return any(
        marker in text
        for marker in [
            "detail.1688.com",
            "1688.com/offer",
            "alicdn.com",
            "alibaba.com",
            "aliexpress.com",
        ]
    )


def is_amazon_competitor_image_url(url: str) -> bool:
    try:
        host = (urlparse(clean(url)).hostname or "").casefold()
    except ValueError:
        return False
    return any(
        host == domain or host.endswith(f".{domain}")
        for domain in [
            "media-amazon.com",
            "ssl-images-amazon.com",
            "images-amazon.com",
        ]
    )


def product_image_url(product: dict[str, Any]) -> str:
    enrichment = product.get("sorftime_enrichment") if isinstance(product.get("sorftime_enrichment"), dict) else {}
    candidates: list[Any] = [
        product.get("image_url"),
        product.get("main_image"),
        product.get("main_image_url"),
        product.get("thumbnail"),
        product.get("thumbnail_url"),
        product.get("photo"),
        product.get("Photo"),
        product.get("image"),
        product.get("img"),
        enrichment.get("detail_image_url"),
        enrichment.get("image_url"),
        enrichment.get("main_image"),
        enrichment.get("main_image_url"),
        enrichment.get("thumbnail"),
        enrichment.get("thumbnail_url"),
        enrichment.get("photo"),
        enrichment.get("Photo"),
    ]
    images = product.get("images") or product.get("image_urls") or product.get("photos")
    if isinstance(images, list):
        candidates.extend(images)
    elif images:
        candidates.append(images)
    for candidate in candidates:
        if isinstance(candidate, dict):
            candidate = first(
                candidate.get("url"),
                candidate.get("src"),
                candidate.get("image_url"),
                candidate.get("large"),
                candidate.get("medium"),
                default="",
            )
        url = clean(candidate)
        if re.match(r"^https?://", url, flags=re.I) and not is_supplier_image_url(url) and is_amazon_competitor_image_url(url):
            return url
    return ""


def image_with_load_fallback_html(url: str, class_name: str, alt: str, fallback_label: str) -> str:
    return (
        "<span class=\"image-frame\">"
        f"<img class=\"{esc(class_name)}\" src=\"{esc(url)}\" alt=\"{esc(alt)}\" "
        "loading=\"lazy\" decoding=\"async\" "
        "onerror=\"this.hidden=true;this.nextElementSibling.hidden=false;\">"
        "<span class=\"image-load-fallback\" hidden "
        "style=\"display:inline-flex;align-items:center;justify-content:center;min-width:72px;min-height:72px;"
        "padding:8px;border:1px solid #d9dee8;background:#f7f9fc;color:#6f8198;font-size:12px;text-align:center;\">"
        f"{esc(fallback_label)}加载失败</span>"
        "</span>"
    )


def product_image_html(product: dict[str, Any], class_name: str, fallback_alt: str = "竞品图片") -> str:
    url = product_image_url(product)
    if not url:
        return ""
    alt = first(customer_product_position(product), product.get("title_cn"), product.get("title"), fallback_alt, default=fallback_alt)
    return image_with_load_fallback_html(url, class_name, alt, fallback_alt)


def product_image_or_diagnostic_html(
    product: dict[str, Any],
    image_class: str,
    diagnostic_class: str,
    fallback_alt: str = "竞品图片",
) -> str:
    image = product_image_html(product, image_class, fallback_alt)
    if image:
        return image
    return (
        f"<div class=\"{esc(diagnostic_class)}\" role=\"img\" aria-label=\"{esc(fallback_alt)}\">"
        f"<span>{esc(fallback_alt)}未返回</span>"
        "<em>采集层未返回 Amazon 可展示主图</em>"
        "</div>"
    )


def product_image_or_empty_html(
    product: dict[str, Any],
    image_class: str,
    empty_class: str,
    fallback_alt: str = "竞品图片",
) -> str:
    image = product_image_html(product, image_class, fallback_alt)
    if image:
        return image
    return f"<div class=\"{esc(empty_class)}\" role=\"img\" aria-label=\"{esc(fallback_alt)}未采集\"></div>"


def sku_reference_image_html(sku: dict[str, Any], class_name: str = "sku-reference-thumb") -> str:
    url = clean(sku.get("reference_image_url"))
    if not url or not re.match(r"^https?://", url, flags=re.I):
        return ""
    if is_supplier_image_url(url) or not is_amazon_competitor_image_url(url):
        return ""
    alt = first(sku.get("reference_competitor"), sku.get("name"), "参考竞品图片", default="参考竞品图片")
    return image_with_load_fallback_html(url, class_name, alt, "参考竞品图片")


def render_competitors(data_pack: dict[str, Any]) -> tuple[str, str, list[dict[str, Any]]]:
    products = sorted(
        [product for product in effective_products(data_pack) if product.get("asin")],
        key=lambda product: as_float(product_sales(product), 0),
        reverse=True,
    )
    filtered = products
    segment_counts = Counter(first(product.get("segment_cn"), product.get("segment"), default="unknown") for product in filtered)
    price_counts = Counter(price_band(product_price(product)) for product in filtered)
    image_items = "".join(
        "<figure class=\"comp-image-item\">"
        + product_image_html(product, "comp-image-thumb", "竞品图片")
        + f"<figcaption>{esc(customer_product_position(product))}</figcaption>"
        + "</figure>"
        for product in filtered[:8]
        if product_image_url(product)
    )
    image_strip = (
        "<div class=\"card comp-image-strip-card\"><div class=\"card-title\">竞品图片全景</div>"
        + f"<div class=\"comp-image-strip\">{image_items}</div>"
        + "</div>"
        if image_items
        else (
            "<div class=\"card comp-image-diagnostic-card\"><div class=\"card-title\">竞品图片全景</div>"
            "<p><strong>图片维度未返回可展示 URL。</strong></p>"
            "<p>已保留竞品图片槽位；需在采集层补齐商品主图链接或可展示图片后，竞品全景、竞品表和标杆拆解会自动展示真实图片。</p>"
            "</div>"
        )
    )
    image_note = (
        "已获取竞品图片 URL，竞品表和标杆拆解将同步展示真实图片。"
        if image_items
        else "图片维度未返回可展示 URL；已保留图片槽位，需在采集层补齐商品主图链接或可展示图片后自动展示。"
    )
    cards = (
        "<div class=\"grid-3\">"
        + "<div class=\"card\"><div class=\"card-title\">细分产品数</div>"
        + mini_chart([(k, v, v) for k, v in segment_counts.most_common(10)], "good")
        + "</div><div class=\"card\"><div class=\"card-title\">价格带 SKU 数</div>"
        + mini_chart([(k, v, v) for k, v in price_counts.items()], "warn")
        + "</div><div class=\"card\"><div class=\"card-title\">分析提示</div>"
        + "<p>Top 竞品表过滤明显非目标类目噪声；完整产品池保留在“完整数据附录”。</p>"
        + f"<p>{esc(image_note)}</p>"
        + "</div></div>"
        + image_strip
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
            + "<td><div class=\"comp-product-cell\">"
            + product_image_or_empty_html(product, "comp-product-thumb", "comp-product-thumb-empty", "竞品图片")
            + f"<div><div class=\"product-name\">{esc(row[1])}</div><div class=\"product-brand\">{esc(row[3])} · {esc(row[4])}</div></div>"
            + "</div></td>"
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
    raw_context = clean(" ".join(str(product.get(key) or "") for key in ("title", "category", "subcategory", "seed_keyword", "segment", "segment_cn"))).casefold()
    if any(token in raw_context for token in ["hunting", "blind", "camouflage", "deer blind", "狩猎", "盲棚"]):
        return "尺寸、视野、耐候和搭建体验会直接影响评价稳定性"
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
    generated_label = clean(keyword.get("customer_label_cn"))
    if generated_label:
        return generated_label
    keyword_cn = clean(keyword.get("keyword_cn"))
    keyword_raw = clean(keyword.get("keyword"))
    if (
        keyword_cn
        and "未映射关键词" not in keyword_cn
        and re.search(r"[\u4e00-\u9fff]", keyword_cn)
        and keyword_cn.casefold() != keyword_raw.casefold()
    ):
        return keyword_cn
    return ""


def traffic_tag_html(terms: list[dict[str, Any]], limit: int = 4) -> str:
    labels: list[str] = []
    for keyword in terms:
        label = keyword_customer_label(keyword)
        if not label:
            continue
        if label not in labels:
            labels.append(label)
        if len(labels) >= limit:
            break
    return "".join(tag(label, "green") for label in labels)


COSMO_ALEXA_RELATIONS = [
    ("USED_FOR_FUNC", "功能 / 用途", "product", ["function", "feature", "use", "used for", "用途", "功能", "解决", "适合"]),
    ("USED_FOR_EVE", "事件 / 活动", "user", ["for ", "hunting", "camping", "party", "event", "活动", "狩猎", "露营", "场景"]),
    ("USED_FOR_AUD", "受众", "user", ["men", "women", "kids", "adult", "deer", "hunter", "audience", "用户", "人群", "猎人"]),
    ("CAPABLE_OF", "能力 / 可完成任务", "product", ["can ", "capable", "hold", "fit", "support", "portable", "可", "支持", "容纳", "便携"]),
    ("USED_TO", "使用目的", "product", ["to ", "install", "setup", "hide", "cover", "build", "用于", "安装", "遮蔽", "搭建"]),
    ("USED_AS", "概念 / 产品类型", "product", ["as ", "kit", "bundle", "blind", "tent", "产品", "套装", "棚", "帐篷"]),
    ("IS_A", "品类归属", "product", ["is a", "category", "type", "类目", "品类", "赛道"]),
    ("USED_ON", "时间 / 季节 / 事件", "user", ["winter", "season", "morning", "night", "day", "fall", "季节", "冬", "夜", "白天"]),
    ("USED_IN_LOC", "位置 / 场所", "user", ["outdoor", "indoor", "field", "woods", "ground", "yard", "户外", "室内", "地面", "树林"]),
    ("USED_IN_BODY", "身体部位", "user", ["skin", "hand", "face", "eye", "body", "身体", "手", "眼", "皮肤"]),
    ("USED_WITH", "互补搭配", "product", ["with ", "compatible", "accessory", "bag", "stake", "搭配", "配件", "收纳", "固定"]),
    ("USED_BY", "使用者", "user", ["by ", "owner", "hunter", "worker", "parent", "buyer", "使用者", "买家", "猎人"]),
    ("xINTERSTED_IN", "兴趣偏好", "user", ["interest", "enthusiast", "outdoor", "hobby", "sport", "兴趣", "爱好", "户外"]),
    ("xIs_A", "人群身份", "user", ["hunter", "owner", "beginner", "professional", "user", "身份", "新手", "专业", "猎人"]),
    ("xWANT", "用户想要达成", "user", ["want", "need", "wish", "problem", "pain", "希望", "需要", "痛点", "想要"]),
]

COSMO_BODY_CUES = {"身体", "手", "眼", "皮肤", "面部", "头部", "腰", "背", "肩", "skin", "hand", "face", "eye", "body"}
COSMO_GENERIC_TAGS = {
    "其他体验问题",
    "内容信号",
    "产品记录",
    "供应端商品",
    "质量与耐用",
    "价格与订阅",
    "尺寸与外观",
    "易用性",
    "其他",
}

COSMO_ENGLISH_TERM_TRANSLATIONS = {
    "see through": "透视观察",
    "see-through": "透视观察",
    "see thru": "透视观察",
    "ground blind": "地面盲棚",
    "hunting blind": "狩猎盲棚",
    "hunting blinds": "狩猎盲棚",
    "deer blind": "鹿猎盲棚",
    "deer hunting": "鹿猎场景",
    "pop up": "弹出式结构",
    "pop-up": "弹出式结构",
    "camouflage": "迷彩隐蔽",
    "camo": "迷彩隐蔽",
    "lumbar support": "腰背支撑",
    "office chair": "办公椅",
    "ergonomic office chair": "人体工学办公椅",
    "mesh back": "网布透气",
    "breathable mesh": "网布透气",
    "adjustable armrest": "扶手调节",
    "bluetooth speaker": "蓝牙音箱",
    "waterproof speaker": "防水音箱",
    "cat water fountain": "猫咪饮水机",
    "pet drinking fountain": "宠物自动饮水",
}


def cosmo_text_records(data_pack: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    research_context = cosmo_research_context_text(data_pack)
    for product in effective_products(data_pack):
        label = customer_product_position(product)
        text = " ".join(
            clean(product.get(key))
            for key in ("title", "title_cn", "brand", "category", "category_cn", "segment", "segment_cn", "positioning_cn")
        )
        records.append(
            {
                "term": label,
                "text": f"{label} {text}",
                "research_context": research_context,
                "source_type": "effective_products",
                "source_id": source_ids_for(product, ""),
                "field": "title/segment",
            }
        )
    for keyword in effective_keywords(data_pack):
        relevance = clean(keyword.get("relevance_cn"))
        if "待判断" in relevance or "相邻相关" in relevance:
            continue
        label = keyword_customer_label(keyword) or clean(keyword.get("keyword_cn")) or clean(keyword.get("keyword"))
        text = " ".join(clean(keyword.get(key)) for key in ("keyword", "keyword_cn", "intent_cn", "relevance_cn", "source_type"))
        records.append(
            {
                "term": label,
                "text": f"{label} {text}",
                "research_context": research_context,
                "source_type": "effective_keywords",
                "source_id": source_ids_for(keyword, ""),
                "field": "keyword",
            }
        )
    for review in customer_visible_reviews(data_pack):
        themes = " ".join(review_theme_labels(review))
        summary = customer_review_summary(review, 120)
        text = " ".join(clean(review.get(key)) for key in ("title", "text", "content", "body", "comment", "summary_cn"))
        records.append(
            {
                "term": themes or summary,
                "text": f"{themes} {summary} {text}",
                "research_context": research_context,
                "source_type": "effective_reviews",
                "source_id": source_ids_for(review, ""),
                "field": "review",
            }
        )
    for item in (data_pack.get("tiktok_products") or []) + (data_pack.get("tiktok_videos") or []):
        label = customer_safe_signal_title(item, "内容信号")
        text = " ".join(clean(item.get(key)) for key in ("title", "title_cn", "name", "caption", "brand", "category"))
        records.append(
            {
                "term": label,
                "text": f"{label} {text}",
                "research_context": research_context,
                "source_type": "tiktok_signals",
                "source_id": source_ids_for(item, ""),
                "field": "content_signal",
            }
        )
    for supplier in effective_suppliers(data_pack):
        if not supplier_matches_lifecycle_context(supplier, data_pack):
            continue
        label = customer_safe_signal_title(supplier, supplier_title_text(supplier) or "供应端商品")
        text = " ".join(clean(supplier.get(key)) for key in ("title", "title_cn", "name", "product_name", "seed_keyword", "search_term", "category"))
        records.append(
            {
                "term": label,
                "text": f"{label} {text}",
                "research_context": research_context,
                "source_type": "effective_suppliers",
                "source_id": source_ids_for(supplier, ""),
                "field": "supplier_title",
            }
        )
    return [record for record in records if clean(record.get("term")) or clean(record.get("text"))]


def cosmo_research_context_text(data_pack: dict[str, Any]) -> str:
    parts: list[str] = []
    research_object = data_pack.get("research_object")
    if isinstance(research_object, dict):
        parts.append(clean(research_object.get("value")))
        parts.extend(clean(item) for item in research_object.get("seed_keywords") or [])
    else:
        parts.append(clean(research_object))
    for product in effective_products(data_pack)[:20]:
        parts.extend(
            clean(product.get(key))
            for key in ("title", "title_cn", "category", "category_cn", "segment", "segment_cn", "positioning_cn")
        )
    for category in data_pack.get("categories") or []:
        if isinstance(category, dict):
            parts.extend(clean(category.get(key)) for key in ("name", "name_cn", "category", "category_cn"))
    return " ".join(part for part in parts if part)


def normalize_cosmo_term(value: Any) -> str:
    text = clean(value)
    text = re.sub(r"\bB0[A-Z0-9]{8,12}\b", "", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" ·-:：,，")
    text = COSMO_ENGLISH_TERM_TRANSLATIONS.get(text.casefold(), text)
    if re.search(r"[\u4e00-\u9fff]", text):
        text = re.sub(r"^(高价|中价|低价|通用|热销|畅销|基础|升级|套装|普通|高端)+", "", text)
        text = text.strip(" ·-:：,，")
    if text.startswith("未映射关键词") or text.startswith("污染关键词"):
        return ""
    if re.search(r"[A-Za-z]{3,}", text) and not re.search(r"[\u4e00-\u9fff]", text):
        return ""
    return truncate(text, 36)


def cosmo_display_relation(relation_type: str, label_cn: str) -> str:
    return clean(label_cn).replace(" / ", "·")


def add_unique_cosmo_candidate(candidates: list[str], value: Any) -> None:
    term = normalize_cosmo_term(value)
    if not term or term in COSMO_GENERIC_TAGS:
        return
    if re.fullmatch(r"[A-Z_]{3,}", term):
        return
    if term not in candidates:
        candidates.append(term)


def cosmo_term_variant_family_key(term: str) -> str:
    text = normalize_cosmo_term(term)
    cjk = "".join(re.findall(r"[\u4e00-\u9fff]+", text))
    if len(cjk) < 4:
        return ""
    return cjk[-2:]


def cosmo_term_semantic_family_key(term: str) -> str:
    text = normalize_cosmo_term(term)
    if not re.search(r"[\u4e00-\u9fff]", text):
        return ""
    semantic_groups = {
        "安装搭建": ["安装", "搭建", "设置", "展开"],
        "质量耐用": ["耐用", "质量", "材质", "结实", "牢固"],
        "空间尺寸": ["空间", "尺寸", "容纳", "多人"],
        "隐蔽遮蔽": ["隐蔽", "遮蔽", "隐藏"],
        "便携收纳": ["便携", "收纳", "携带"],
        "防护防水": ["防水", "抗风", "耐候"],
    }
    for group, cues in semantic_groups.items():
        if any(cue in text for cue in cues):
            return group
    return ""


def cosmo_profile_terms(analysis_plan: dict[str, Any], relation_type: str) -> list[str]:
    profile = analysis_plan.get("report_label_profile") if isinstance(analysis_plan, dict) else {}
    if not isinstance(profile, dict):
        return []
    raw_terms: Any = None
    for key in ("cosmo_relation_terms", "cosmo_alexa_relation_terms", "cosmo_tags"):
        candidate = profile.get(key)
        if isinstance(candidate, dict) and relation_type in candidate:
            raw_terms = candidate.get(relation_type)
            break
    if isinstance(raw_terms, dict):
        raw_terms = raw_terms.get("terms") or raw_terms.get("labels") or raw_terms.get("tag_terms")
    if isinstance(raw_terms, str):
        raw_terms = [raw_terms]
    if not isinstance(raw_terms, list):
        return []
    terms: list[str] = []
    for value in raw_terms:
        add_unique_cosmo_candidate(terms, value)
        if len(terms) >= 5:
            break
    return terms


def cosmo_records_matching_profile_terms(records: list[dict[str, Any]], terms: list[str], limit: int = 12) -> list[dict[str, Any]]:
    if not terms:
        return []
    matches: list[dict[str, Any]] = []
    normalized_terms = [normalize_cosmo_term(term) for term in terms if normalize_cosmo_term(term)]
    for record in records:
        if any(cosmo_record_supports_profile_term(record, term) for term in normalized_terms):
            matches.append(record)
        if len(matches) >= limit:
            break
    return matches


def cosmo_record_supports_profile_term(record: dict[str, Any], term: str) -> bool:
    normalized = normalize_cosmo_term(term)
    if not normalized:
        return False
    text = clean(record.get("text"))
    lower = text.casefold()
    if cosmo_cue_matches(text, lower, normalized):
        return True
    has_cjk = re.search(r"[\u4e00-\u9fff]", normalized) is not None
    cjk_bigrams: set[str] = set()
    if has_cjk:
        cjk_text = "".join(re.findall(r"[\u4e00-\u9fff]+", normalized))
        cjk_bigrams = {cjk_text[idx : idx + 2] for idx in range(max(0, len(cjk_text) - 1)) if len(cjk_text[idx : idx + 2]) == 2}
    if cjk_bigrams and any(token in text for token in cjk_bigrams):
        return True
    return False


def cosmo_profile_term_supported(records: list[dict[str, Any]], term: str) -> bool:
    for record in records:
        if cosmo_record_supports_profile_term(record, term):
            return True
    return False


def supported_cosmo_profile_terms(records: list[dict[str, Any]], terms: list[str]) -> list[str]:
    supported: list[str] = []
    for term in terms:
        if cosmo_profile_term_supported(records, term):
            add_unique_cosmo_candidate(supported, term)
    return supported


def merge_cosmo_terms(primary_terms: list[str], secondary_terms: list[str], limit: int = 5) -> list[str]:
    merged: list[str] = []
    family_counts: Counter[str] = Counter()
    semantic_counts: Counter[str] = Counter()
    for term in [*primary_terms, *secondary_terms]:
        normalized = normalize_cosmo_term(term)
        semantic_key = cosmo_term_semantic_family_key(normalized)
        if semantic_key and semantic_counts[semantic_key] >= 1:
            continue
        family_key = cosmo_term_variant_family_key(normalized)
        if family_key and family_counts[family_key] >= 2:
            continue
        before = len(merged)
        add_unique_cosmo_candidate(merged, normalized)
        if len(merged) > before and family_key:
            family_counts[family_key] += 1
        if len(merged) > before and semantic_key:
            semantic_counts[semantic_key] += 1
        if len(merged) >= limit:
            break
    return merged


def cosmo_cue_matches(text: str, lower_text: str, cue: str) -> bool:
    cue_text = clean(cue)
    if not cue_text:
        return False
    if re.search(r"[\u4e00-\u9fff]", cue_text):
        return cue_text in text
    cue_lower = cue_text.casefold()
    if re.fullmatch(r"[a-z0-9]+(?: [a-z0-9]+)*", cue_lower):
        return re.search(rf"(?<![a-z0-9]){re.escape(cue_lower)}(?![a-z0-9])", lower_text) is not None
    return cue_lower in lower_text


def compact_cosmo_product_type(term: str) -> str:
    text = normalize_cosmo_term(term)
    if not text:
        return ""
    for pattern in [
        r"[\u4e00-\u9fff]{0,6}饮水机",
        r"[\u4e00-\u9fff]{0,6}饮水器",
        r"[\u4e00-\u9fff]{0,6}地面盲棚",
        r"[\u4e00-\u9fff]{0,6}狩猎盲棚",
        r"[\u4e00-\u9fff]{0,6}灯带",
        r"[\u4e00-\u9fff]{0,6}感应灯",
        r"[\u4e00-\u9fff]{0,6}玩具",
        r"[\u4e00-\u9fff]{0,6}收纳盒",
        r"[\u4e00-\u9fff]{0,6}水泵",
    ]:
        match = re.search(pattern, text)
        if match:
            phrase = re.sub(r"^(不锈钢|智能|自动|无线|便携|户外|室内|跨境|新款|厂家|工厂|猫咪)", "", match.group(0))
            return normalize_cosmo_term(phrase or match.group(0))
    words = [part for part in re.split(r"[ ·,，/|]+", text) if part]
    for word in words:
        if 2 <= len(word) <= 12 and re.search(r"机|器|灯|棚|包|盒|杯|瓶|玩具|配件|滤芯|水泵", word):
            return normalize_cosmo_term(word)
    return text if len(text) <= 12 else ""


def add_generic_relation_terms(
    candidates: list[str],
    relation_type: str,
    text: str,
    raw_term: str,
    child_product_context: bool = False,
) -> None:
    lower = text.casefold()
    if relation_type in {"USED_AS", "IS_A"}:
        compact = compact_cosmo_product_type(raw_term) or compact_cosmo_product_type(text)
        add_unique_cosmo_candidate(candidates, compact)
    if relation_type in {"USED_FOR_FUNC", "CAPABLE_OF"}:
        for label, cues in [
            ("静音水泵", ["静音水泵", "quiet pump", "低噪水泵"]),
            ("自动循环饮水", ["自动循环", "循环饮水", "water fountain", "drinking fountain"]),
            ("易清洁结构", ["easy to clean", "容易清洁", "易清洁", "清洁方便"]),
            ("耐用材质", ["stainless", "durable", "耐用", "不锈钢", "材质"]),
            ("便携收纳", ["portable", "carry", "foldable", "便携", "收纳", "折叠"]),
            ("快速安装", ["easy to set up", "install", "setup", "安装", "搭建"]),
        ]:
            if any(cosmo_cue_matches(text, lower, cue) for cue in cues):
                add_unique_cosmo_candidate(candidates, label)
    if relation_type == "USED_TO":
        for label, cues in [
            ("宠物补水", ["宠物补水", "drink more water", "饮水量", "补水"]),
            ("猫咪饮水", ["cat water", "猫咪饮水", "猫咪饮水机"]),
            ("自动循环饮水", ["自动循环饮水", "pet drinking", "饮水器"]),
            ("清洁维护", ["clean", "清洁", "维护"]),
            ("快速安装", ["setup", "install", "安装", "搭建"]),
            ("隐蔽观察", ["conceal", "hide", "观察", "隐蔽"]),
        ]:
            if any(cosmo_cue_matches(text, lower, cue) for cue in cues):
                add_unique_cosmo_candidate(candidates, label)
    if relation_type in {"USED_FOR_AUD", "USED_BY", "xIs_A"}:
        child_audience_label = "儿童使用场景" if child_product_context else "家庭安全关注场景"
        child_user_label = "父母购买者" if child_product_context else "家庭照护者"
        child_identity_label = "儿童礼品决策者" if child_product_context else "家庭安全决策者"
        user_label_sets = {
            "USED_FOR_AUD": [
                ("宠物家庭", ["pet", "宠物", "猫", "狗"]),
                ("猫咪家庭", ["cat", "猫咪", "猫"]),
                ("家庭使用场景", ["home", "家庭", "家用"]),
                (child_audience_label, ["kids", "children", "儿童"]),
                ("户外人群", ["outdoor", "户外"]),
                ("专业使用场景", ["professional", "专业"]),
            ],
            "USED_BY": [
                ("宠物主人", ["pet", "宠物", "猫", "狗"]),
                ("养猫用户", ["cat", "猫咪", "猫"]),
                ("家庭用户", ["home", "家庭", "家用"]),
                (child_user_label, ["kids", "children", "儿童"]),
                ("户外使用者", ["outdoor", "户外"]),
                ("专业用户", ["professional", "专业"]),
            ],
            "xIs_A": [
                ("养宠家庭", ["pet", "宠物", "猫", "狗"]),
                ("猫咪照护者", ["cat", "猫咪", "猫"]),
                ("家庭采购者", ["home", "家庭", "家用"]),
                (child_identity_label, ["kids", "children", "儿童"]),
                ("户外运动用户", ["outdoor", "户外"]),
                ("专业买家", ["professional", "专业"]),
            ],
        }
        for label, cues in user_label_sets.get(relation_type, []):
            if any(cosmo_cue_matches(text, lower, cue) for cue in cues):
                add_unique_cosmo_candidate(candidates, label)
    if relation_type == "USED_WITH":
        for label, cues in [
            ("滤芯", ["filter", "滤芯"]),
            ("水泵", ["pump", "水泵"]),
            ("电源线", ["cord", "cable", "电源线"]),
            ("收纳包", ["bag", "收纳包"]),
            ("固定件", ["stake", "tie down", "固定件"]),
        ]:
            if any(cosmo_cue_matches(text, lower, cue) for cue in cues):
                add_unique_cosmo_candidate(candidates, label)
    if relation_type == "xWANT":
        for label, cues in [
            ("更容易清洁", ["easy to clean", "容易清洁", "易清洁", "清洁"]),
            ("安静运行", ["quiet", "静音", "低噪"]),
            ("饮水更主动", ["drink more water", "饮水量", "补水"]),
            ("滤芯更换清晰", ["filter replacement", "滤芯更换", "滤芯"]),
            ("材质更耐用", ["durable", "stainless", "耐用", "材质", "不锈钢"]),
            ("安装更简单", ["easy to set up", "setup", "install", "安装"]),
        ]:
            if any(cosmo_cue_matches(text, lower, cue) for cue in cues):
                add_unique_cosmo_candidate(candidates, label)


def is_hunting_cosmo_context(text: str) -> bool:
    lower = clean(text).casefold()
    return any(
        cue in lower
        for cue in [
            "hunting",
            "hunter",
            "deer",
            "turkey",
            "ground blind",
            "hunting blind",
            "camouflage",
            "camo",
            "狩猎",
            "打猎",
            "猎人",
            "鹿猎",
            "火鸡",
            "盲棚",
            "地面盲棚",
            "迷彩",
        ]
    )


def is_audio_cosmo_context(text: str) -> bool:
    lower = clean(text).casefold()
    return any(
        cue in lower
        for cue in [
            "speaker",
            "bluetooth speaker",
            "wireless speaker",
            "portable speaker",
            "soundbox",
            "music",
            "audio",
            "音箱",
            "蓝牙音箱",
            "播放",
            "音乐",
            "音频",
        ]
    )


def is_child_product_cosmo_context(text: str) -> bool:
    lower = clean(text).casefold()
    return any(
        cue in lower
        for cue in [
            "kids toy",
            "children toy",
            "baby toy",
            "plush toy",
            "stuffed animal",
            "interactive toy",
            "companion toy",
            "toy for kids",
            "toy gift",
            "儿童玩具",
            "儿童礼品",
            "毛绒玩具",
            "智能陪伴玩具",
            "陪伴玩具",
            "亲子玩具",
            "礼品玩具",
        ]
    )


def cosmo_domain_context(record: dict[str, Any], detector) -> bool:
    context_text = clean(record.get("research_context"))
    record_text = clean(record.get("text"))
    if context_text:
        return detector(context_text) and detector(record_text)
    return detector(record_text)


def cosmo_term_candidates(record: dict[str, Any], relation_type: str, dimension: str) -> list[str]:
    source_type = clean(record.get("source_type"))
    text = clean(record.get("text"))
    lower = text.casefold()
    hunting_context = cosmo_domain_context(record, is_hunting_cosmo_context)
    audio_context = cosmo_domain_context(record, is_audio_cosmo_context)
    child_product_context = is_child_product_cosmo_context(clean(record.get("research_context"))) or is_child_product_cosmo_context(text)
    raw_term = normalize_cosmo_term(record.get("term"))
    candidates: list[str] = []

    def add(value: Any) -> None:
        add_unique_cosmo_candidate(candidates, value)

    def add_when(label: str, *needles: str) -> None:
        if any(needle and cosmo_cue_matches(text, lower, needle) for needle in needles):
            add(label)

    if relation_type == "USED_IN_BODY":
        for cue in COSMO_BODY_CUES:
            if cue == "手":
                continue
            if re.search(r"[\u4e00-\u9fff]", cue) and cue in text:
                add(cue if re.search(r"[\u4e00-\u9fff]", cue) else {"skin": "皮肤接触", "hand": "手部操作", "face": "面部", "eye": "视线/眼部", "body": "身体接触"}.get(cue, cue))
        return candidates

    if relation_type == "USED_FOR_FUNC":
        if hunting_context:
            add_when("隐蔽观察", "blind", "conceal", "hide", "隐蔽", "遮蔽", "观察")
            add_when("单向透视", "see through", "透视")
            add_when("快速展开", "pop up", "弹出", "快速")
        add_when("防水抗风", "waterproof", "wind", "防水", "抗风")
    elif relation_type == "USED_FOR_EVE":
        if hunting_context:
            add_when("鹿猎场景", "deer", "鹿")
            add_when("火鸡狩猎", "turkey", "火鸡")
            add_when("户外狩猎活动", "hunting", "狩猎", "打猎")
        add_when("户外使用场景", "outdoor", "户外")
        add_when("露营/野外观察", "camping", "露营", "野外")
    elif relation_type == "USED_FOR_AUD":
        if hunting_context:
            add_when("猎人用户", "hunter", "hunting", "猎人", "狩猎")
        add_when("多人使用者", "two person", "three person", "多人")
        add_when("户外爱好者", "outdoor", "户外")
    elif relation_type == "CAPABLE_OF":
        add_when("快速搭建", "easy to set up", "setup", "install", "弹出", "安装", "搭建")
        if hunting_context:
            add_when("保持隐蔽", "concealed", "conceal", "hide", "隐蔽")
            add_when("容纳多人", "2 person", "3 person", "多人", "容纳")
        add_when("便携收纳", "portable", "carry", "便携", "收纳")
    elif relation_type == "USED_TO":
        if hunting_context:
            add_when("隐藏身形", "conceal", "hide", "隐蔽", "遮蔽")
            add_when("观察猎物", "deer", "turkey", "watch", "观察", "狩猎")
            add_when("快速搭建临时掩体", "pop up", "setup", "弹出", "搭建")
        add_when("户外使用", "outdoor", "户外")
        if audio_context:
            add_when("户外播放", "speaker", "music", "音箱", "播放")
        add_when("防水使用", "waterproof", "防水")
    elif relation_type == "USED_AS":
        if hunting_context:
            add_when("弹出式地面盲棚", "pop up", "ground blind", "弹出式", "地面盲棚")
            add_when("透视地面盲棚", "see through", "透视")
            add_when("塔式/箱式盲棚", "tower", "box", "塔式", "箱式")
    elif relation_type == "IS_A":
        if hunting_context:
            add_when("狩猎盲棚", "hunting blind", "狩猎盲棚", "打猎")
            add_when("户外隐蔽装备", "outdoor", "conceal", "户外", "隐蔽")
            add_when("弹出式帐篷类装备", "tent", "pop up", "帐篷", "弹出式")
    elif relation_type == "USED_ON":
        if hunting_context:
            add_when("狩猎季", "hunting season", "season", "季")
        add_when("清晨/傍晚观察", "morning", "evening", "dawn", "清晨", "傍晚")
        add_when("户外活动日", "day", "outdoor", "户外")
    elif relation_type == "USED_IN_LOC":
        add_when("户外地面" if hunting_context else "户外场景", "ground", "outdoor", "地面", "户外")
        if hunting_context:
            add_when("树林/野外", "woods", "field", "树林", "野外", "猎场")
            add_when("后院/农场", "yard", "farm", "后院", "农场")
    elif relation_type == "USED_WITH":
        if hunting_context:
            add_when("地钉/固定件", "stake", "tie down", "固定", "地钉")
            add_when("迷彩遮蔽配件", "camo", "camouflage", "迷彩")
            add_when("椅子/三脚架", "chair", "tripod", "椅", "三脚架")
        add_when("收纳包", "bag", "carry", "收纳包", "收纳")
    elif relation_type == "USED_BY":
        if hunting_context:
            add_when("狩猎用户", "hunter", "hunting", "猎人", "狩猎")
        add_when("户外使用者", "outdoor", "户外")
        add_when("新手用户", "beginner", "easy", "新手", "易用")
    elif relation_type == "xINTERSTED_IN":
        if hunting_context:
            add_when("狩猎体验", "hunting", "deer", "turkey", "狩猎")
            add_when("户外隐蔽装备", "outdoor", "conceal", "户外", "隐蔽")
            add_when("便携搭建", "portable", "easy to set up", "便携", "安装")
        elif audio_context:
            add_when("户外音乐", "speaker", "music", "音箱", "播放")
            add_when("便携户外使用", "portable", "outdoor", "便携", "户外")
        else:
            add_when("便携户外使用", "portable", "outdoor", "便携", "户外")
    elif relation_type == "xIs_A":
        if hunting_context:
            add_when("猎人", "hunter", "hunting", "猎人", "狩猎")
        add_when("户外运动用户", "outdoor", "sport", "户外")
        add_when("价格敏感买家", "price", "value", "价格")
    elif relation_type == "xWANT":
        add_when("更容易安装", "easy to set up", "setup", "install", "易安装", "安装", "易用")
        add_when("隐蔽性更稳定", "conceal", "hide", "隐蔽", "遮蔽")
        add_when("材质更耐用", "durable", "quality", "sturdy", "耐用", "质量", "材质")
        add_when("空间更充足", "roomy", "space", "spacious", "空间", "尺寸")

    add_generic_relation_terms(candidates, relation_type, text, raw_term, child_product_context)

    if candidates:
        return candidates

    if relation_type in {"USED_FOR_EVE", "USED_ON", "USED_IN_LOC", "USED_FOR_AUD", "USED_BY", "xINTERSTED_IN", "xIs_A", "xWANT"}:
        return candidates

    if (
        relation_type in {"USED_AS", "IS_A"}
        and dimension == "product"
        and source_type in {"effective_products", "effective_keywords", "effective_suppliers"}
    ):
        add(raw_term)
    elif raw_term and dimension != "product":
        add(raw_term)
    return candidates


def unique_relation_terms(matches: list[dict[str, Any]], relation_type: str, dimension: str, limit: int = 5) -> list[str]:
    terms: list[str] = []
    for match in matches:
        for term in cosmo_term_candidates(match, relation_type, dimension):
            if term not in terms:
                terms.append(term)
            if len(terms) >= limit:
                return terms
    return terms


def cosmo_business_meaning(relation_type: str, label_cn: str, terms: list[str], confidence: str) -> str:
    if confidence == "低" or not terms:
        return f"当前「{label_cn}」证据不足，客户页只保留诊断，不把它写成页面承诺或广告定向依据。"
    joined = "、".join(terms[:3])
    templates = {
        "USED_FOR_FUNC": f"把「{joined}」作为页面首屏功能承诺，必须用图片、五点和 QA 同时解释真实使用边界。",
        "USED_FOR_EVE": f"围绕「{joined}」组织场景图和关键词组，避免把户外大词泛化成无差别流量。",
        "USED_FOR_AUD": f"把「{joined}」作为人群识别口径，用于评论筛选、广告人群和主图人物/场景选择。",
        "CAPABLE_OF": f"将「{joined}」转成可验证能力点，优先通过实拍、尺寸图和安装步骤证明。",
        "USED_TO": f"页面要回答用户为什么使用该产品：围绕「{joined}」写清目标任务和限制条件。",
        "USED_AS": f"把「{joined}」作为产品类型锚点，标题和类目表达应保持一致，减少算法误分流。",
        "IS_A": f"用「{joined}」建立品类归属，Listing 不应混入无关类目词。",
        "USED_ON": f"围绕「{joined}」安排季节/事件表达，广告节奏和内容素材要匹配使用窗口。",
        "USED_IN_LOC": f"把「{joined}」转成使用地点证据，主图和 A+ 页面需要展示真实环境。",
        "USED_IN_BODY": f"若「{joined}」属实，需要补充人体接触、安全或佩戴相关说明；否则不应强写。",
        "USED_WITH": f"围绕「{joined}」设计 Bundle、配件图和问答，避免用户误解配件是否包含。",
        "USED_BY": f"将「{joined}」映射到买家语言，评论摘要和广告人群需要保持一致。",
        "xINTERSTED_IN": f"把「{joined}」作为内容兴趣锚点，用于短视频脚本和站内场景词。",
        "xIs_A": f"围绕「{joined}」识别用户身份，页面语气和售后承诺要匹配该身份。",
        "xWANT": f"把「{joined}」转成最小可验证卖点，先用产品事实和评论证据支撑，再进入广告承诺。",
    }
    return templates.get(relation_type, f"围绕「{joined}」形成页面标签和广告标签的一致表达。")


def cosmo_action_copy(relation_type: str, label_cn: str, terms: list[str], dimension: str, confidence: str) -> dict[str, str]:
    if confidence == "低" or not terms:
        return {
            "listing_label": "暂不承诺",
            "listing_action": f"当前「{label_cn}」证据不足，标题、五点和 A+ 不写成确定卖点。",
            "qa_label": "补证问答",
            "qa_action": f"下一轮优先补采评论、QA 和关键词，确认「{label_cn}」是否真实存在。",
            "ad_label": "暂停扩词",
            "ad_action": f"广告端暂不扩展「{label_cn}」相关词，避免无证据流量污染。",
        }
    primary = terms[0]
    joined = "、".join(terms[:3])
    product_listing_target = "标题、五点、A+ 模块"
    user_listing_target = "场景图、QA 摘要、广告人群包"
    listing_target = product_listing_target if dimension == "产品标签" else user_listing_target
    relation_actions: dict[str, tuple[str, str, str, str, str, str]] = {
        "USED_FOR_FUNC": (
            "首屏承诺",
            f"把「{joined}」放到首屏卖点层，配真实图片或结构图说明边界。",
            "证据问答",
            f"围绕「{primary}」回答适用条件、不能解决的问题和对比竞品差异。",
            "精准投放",
            f"只投与「{primary}」强相关的功能词，低置信功能词留在否词观察池。",
        ),
        "USED_FOR_EVE": (
            "场景素材",
            f"围绕「{joined}」组织场景图，不把泛户外词直接写成主承诺。",
            "场景问答",
            f"补充「{primary}」在何时使用、适用环境和限制条件。",
            "场景词组",
            f"广告按事件/活动拆组，单独观察「{primary}」转化。",
        ),
        "USED_FOR_AUD": (
            "人群入口",
            f"在{listing_target}中明确「{joined}」是谁在用，而不是只堆产品词。",
            "人群问答",
            f"回答「{primary}」是否适合新手、多人或专业用户。",
            "人群定向",
            f"站内广告先用「{primary}」相关窄人群词，避免泛兴趣扩量过早。",
        ),
        "CAPABLE_OF": (
            "能力证明",
            f"把「{joined}」拆成可验证动作，用步骤图、尺寸图或实测图证明。",
            "能力边界",
            f"QA 写清「{primary}」在什么条件下成立，避免售后争议。",
            "能力词",
            f"广告优先跑「{primary}」能力词，观察点击后转化和差评风险。",
        ),
        "USED_TO": (
            "任务叙事",
            f"页面围绕「{joined}」解释用户完成什么任务，而不是只描述材质。",
            "任务限制",
            f"补问答说明「{primary}」的使用步骤、准备条件和失败场景。",
            "任务词",
            f"广告按任务词建组，先验证「{primary}」是否能带来高意向点击。",
        ),
        "USED_AS": (
            "类型锚点",
            f"标题和类目表达围绕「{joined}」统一，减少算法误分流。",
            "类型澄清",
            f"QA 说明「{primary}」与相邻类型的差别，降低误购。",
            "类型投放",
            f"广告以「{primary}」类型词为核心，暂不混投跨类型泛词。",
        ),
        "IS_A": (
            "类目定位",
            f"用「{joined}」固定品类归属，页面不混入无关大类词。",
            "类目问答",
            f"回答「{primary}」属于什么类目、适合哪些替代场景。",
            "类目控词",
            f"广告以类目词验证基本盘，观察无关搜索词并及时否词。",
        ),
        "USED_ON": (
            "时机表达",
            f"在{listing_target}中说明「{joined}」对应的季节、日期或使用窗口。",
            "时机问答",
            f"QA 回答「{primary}」是否受天气、时段或季节限制。",
            "时机排期",
            f"按「{primary}」建立季节性预算，不在淡季强拉宽泛流量。",
        ),
        "USED_IN_LOC": (
            "地点证据",
            f"主图/A+ 展示「{joined}」真实地点，不只写抽象用途。",
            "地点限制",
            f"QA 写清「{primary}」对地面、空间、安装环境的要求。",
            "地点词",
            f"广告单独测试「{primary}」地点词，避免与无关室内/户外词混跑。",
        ),
        "USED_IN_BODY": (
            "安全表述",
            f"如果「{joined}」成立，页面必须写清接触、安全和舒适边界。",
            "安全问答",
            f"QA 回答「{primary}」是否涉及人体接触、佩戴或敏感人群。",
            "安全控投",
            f"广告暂不放大「{primary}」相关词，先确认合规和差评风险。",
        ),
        "USED_WITH": (
            "搭配关系",
            f"把「{joined}」做成配件/Bundle 说明，明确是否随箱包含。",
            "搭配问答",
            f"QA 回答「{primary}」是否兼容、是否需要另购、安装是否冲突。",
            "搭配扩展",
            f"广告用「{primary}」搭配词做小预算验证，再决定是否做套装。",
        ),
        "USED_BY": (
            "买家语言",
            f"页面语气和卖点顺序贴近「{joined}」的真实使用语言。",
            "买家顾虑",
            f"QA 回答「{primary}」最常问的上手、维护和售后问题。",
            "买家分组",
            f"广告按「{primary}」拆买家意图组，避免新手和专业用户混投。",
        ),
        "xINTERSTED_IN": (
            "内容钩子",
            f"短视频和 A+ 内容围绕「{joined}」建立兴趣入口。",
            "兴趣验证",
            f"QA/评论摘要确认「{primary}」是购买动机还是浏览兴趣。",
            "内容投放",
            f"广告先用「{primary}」做内容词测试，转化不足则降级为素材方向。",
        ),
        "xIs_A": (
            "身份表达",
            f"页面避免泛称用户，改用「{joined}」的身份语言组织卖点。",
            "身份问答",
            f"QA 说明「{primary}」是否适合不同经验层级或使用频次。",
            "身份分层",
            f"广告把「{primary}」与高意图产品词组合，不单独泛投身份词。",
        ),
        "xWANT": (
            "需求主张",
            f"把「{joined}」转成最小可验证承诺，先放在五点和对比图。",
            "需求证据",
            f"QA 用真实限制回答「{primary}」能做到什么、不能做到什么。",
            "需求放量",
            f"广告只放大已被评论和竞品验证的「{primary}」需求词。",
        ),
    }
    listing_label, listing_action, qa_label, qa_action, ad_label, ad_action = relation_actions.get(
        relation_type,
        (
            "语义承接",
            f"在{listing_target}中围绕「{joined}」建立一致表达。",
            "证据补强",
            f"用 QA 和评论摘要确认「{primary}」是否能成为页面事实。",
            "小量验证",
            f"广告先小预算测试「{primary}」相关词，再决定是否扩展。",
        ),
    )
    return {
        "listing_label": listing_label,
        "listing_action": listing_action,
        "qa_label": qa_label,
        "qa_action": qa_action,
        "ad_label": ad_label,
        "ad_action": ad_action,
    }


def cosmo_low_coverage_hint(label_cn: Any) -> str:
    label = clean(label_cn).replace(" / ", "与").replace("/", "与")
    label = re.sub(r"\s+", "", label)
    return f"需补强：{label or '该关系'}证据"


def generate_cosmo_alexa_tags(data_pack: dict[str, Any], analysis_plan: dict[str, Any]) -> dict[str, Any]:
    records = cosmo_text_records(data_pack)
    relation_items = []
    product_slot = 0
    user_slot = 0
    for relation_type, cn_name, dimension, cues in COSMO_ALEXA_RELATIONS:
        if dimension == "product":
            product_slot += 1
            slot_id = f"P{product_slot:02d}"
            slot_label = "产品意图"
        else:
            user_slot += 1
            slot_id = f"U{user_slot:02d}"
            slot_label = "用户意图"
        matches = []
        profile_terms = cosmo_profile_terms(analysis_plan, relation_type)
        supported_profile_terms = supported_cosmo_profile_terms(records, profile_terms)
        profile_matches = cosmo_records_matching_profile_terms(records, supported_profile_terms)
        cue_set = [cue.casefold() for cue in cues]
        for record in records:
            text = clean(record.get("text")).casefold()
            if relation_type == "USED_IN_BODY" and not any(cue in text or cue in clean(record.get("text")) for cue in COSMO_BODY_CUES):
                continue
            if dimension == "product" and record.get("source_type") == "effective_reviews" and relation_type not in {"USED_FOR_FUNC", "CAPABLE_OF"}:
                continue
            candidates = cosmo_term_candidates(record, relation_type, dimension)
            if candidates and (any(cue in text for cue in cue_set) or relation_type in {"USED_FOR_FUNC", "USED_FOR_EVE", "USED_FOR_AUD", "CAPABLE_OF", "USED_TO", "USED_AS", "IS_A", "USED_ON", "USED_IN_LOC", "USED_WITH", "USED_BY", "xINTERSTED_IN", "xIs_A", "xWANT"}):
                matches.append(record)
            if len(matches) >= 12:
                break
        if profile_matches:
            seen_match_keys = {
                (match.get("source_type"), match.get("source_id"), match.get("field"), match.get("text"))
                for match in matches
            }
            for match in profile_matches:
                key = (match.get("source_type"), match.get("source_id"), match.get("field"), match.get("text"))
                if key not in seen_match_keys:
                    matches.append(match)
                    seen_match_keys.add(key)
                if len(matches) >= 12:
                    break
        if matches:
            terms = merge_cosmo_terms(supported_profile_terms, unique_relation_terms(matches, relation_type, dimension))
            evidence = []
            covered_terms: set[str] = set()
            deferred_evidence: list[dict[str, Any]] = []
            for match in matches:
                match_terms = set(cosmo_term_candidates(match, relation_type, dimension))
                supported_terms = [
                    term
                    for term in terms
                    if term in match_terms or cosmo_record_supports_profile_term(match, term)
                ]
                evidence_item = {
                    "source_type": match.get("source_type"),
                    "source_id": match.get("source_id"),
                    "field": match.get("field"),
                    "excerpt": truncate(match.get("text"), 120),
                    "supported_terms": supported_terms,
                }
                if supported_terms and any(term not in covered_terms for term in supported_terms):
                    evidence.append(evidence_item)
                    covered_terms.update(supported_terms)
                else:
                    deferred_evidence.append(evidence_item)
                if len(evidence) >= 8 and all(term in covered_terms for term in terms):
                    break
            for evidence_item in deferred_evidence:
                if len(evidence) >= 8:
                    break
                evidence.append(evidence_item)
            confidence = "高" if len(matches) >= 8 and len(terms) >= 3 else "中" if len(matches) >= 3 and terms else "低"
            coverage_status = "已覆盖" if confidence != "低" else "低覆盖"
        elif profile_terms:
            terms = []
            evidence = [
                {
                    "source_type": "analysis_plan",
                    "source_id": "report_label_profile.cosmo_relation_terms",
                    "field": relation_type,
                    "excerpt": "AI 标签画像已给出业务标签，但当前有效数据文本匹配不足，需在 Listing/QA/评论中继续补证。",
                }
            ]
            confidence = "低"
            coverage_status = "低覆盖"
        else:
            terms = []
            evidence = []
            confidence = "低"
            coverage_status = "需补强"
        business_meaning = cosmo_business_meaning(relation_type, cn_name, terms, confidence)
        action_copy = cosmo_action_copy(
            relation_type,
            cn_name,
            terms,
            "产品标签" if dimension == "product" else "用户标签",
            confidence,
        )
        relation_items.append(
            {
                "relation_type": relation_type,
                "label_cn": cn_name,
                "display_relation": cosmo_display_relation(relation_type, cn_name),
                "dimension": "产品标签" if dimension == "product" else "用户标签",
                "slot_id": slot_id,
                "slot_label": slot_label,
                "terms": terms,
                "confidence": confidence,
                "coverage_status": coverage_status,
                "evidence_count": len(matches),
                "business_meaning": business_meaning,
                "source_evidence": evidence[:6],
                **action_copy,
            }
        )
    covered = len([item for item in relation_items if item["evidence_count"] > 0])
    return {
        "schema_version": "cosmo_alexa_tags.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "basis": "由当前 normalized data pack 的有效竞品、关键词、评论、TikTok 信号和 1688 供应标题生成；模板不得写死类目标签。",
        "coverage_summary": {
            "relation_total": len(COSMO_ALEXA_RELATIONS),
            "covered_relations": covered,
            "low_confidence_relations": len([item for item in relation_items if item["confidence"] == "低"]),
            "evidence_records": len(records),
        },
        "relations": relation_items,
    }


def cosmo_customer_source_label(source_type: Any) -> str:
    label = clean(source_type)
    mapping = {
        "effective_products": "竞品",
        "effective_keywords": "关键词",
        "effective_reviews": "评论",
        "effective_suppliers": "供应链",
        "tiktok_signals": "TikTok",
        "web_documents": "网页资料",
        "analysis_plan": "分析画像",
    }
    return mapping.get(label, "业务证据")


def cosmo_evidence_sources_html(item: dict[str, Any]) -> str:
    counts: Counter[str] = Counter()
    for evidence in item.get("source_evidence") or []:
        label = cosmo_customer_source_label(evidence.get("source_type"))
        counts[label] += 1
    if not counts:
        return (
            "<div class=\"cosmo-evidence-sources\"><b>证据来源</b>"
            "<span>需补充客户可验证证据</span></div>"
        )
    chips = "".join(
        f"<span>{esc(label)}<em>{esc(count)}</em></span>"
        for label, count in counts.most_common(4)
    )
    return f"<div class=\"cosmo-evidence-sources\"><b>证据来源</b>{chips}</div>"


def render_cosmo_alexa_tags(data_pack: dict[str, Any], analysis_plan: dict[str, Any]) -> str:
    payload = generate_cosmo_alexa_tags(data_pack, analysis_plan)
    summary = payload.get("coverage_summary") or {}
    relations = payload.get("relations") or []
    cards = [
        kpi_card("标签维度", summary.get("relation_total", 15), "15 类意图关系", "success"),
        kpi_card("已覆盖标签", summary.get("covered_relations", 0), "由当前有效数据命中", "success"),
        kpi_card("低置信标签", summary.get("low_confidence_relations", 0), "需 Listing / QA 补强", "warning"),
        kpi_card("证据记录", summary.get("evidence_records", 0), "竞品、关键词、评论、内容和供应端", ""),
    ]

    def matrix_cell(item: dict[str, Any]) -> str:
        marker = "产品" if item.get("dimension") == "产品标签" else "用户"
        terms = list((item.get("terms") or [])[:4])
        if item.get("confidence") == "低":
            hint = cosmo_low_coverage_hint(item.get("label_cn"))
            if hint not in terms:
                terms.append(hint)
        action_direction = " / ".join(
            part
            for part in [
                clean(item.get("listing_label")),
                clean(item.get("qa_label")),
                clean(item.get("ad_label")),
            ]
            if part
        ) or "补证后再进入页面承诺"
        return (
            "<article class=\"cosmo-tag-card cosmo-matrix-cell\" "
            + f"data-cosmo-relation=\"{esc(item.get('slot_id'))}\" data-confidence=\"{esc(item.get('confidence'))}\" data-dimension=\"{esc(item.get('dimension'))}\">"
            + "<div class=\"cosmo-card-top\"><div>"
            + "<div class=\"cosmo-relation-lane\">"
            + f"<span class=\"cosmo-relation-kind\">{esc(item.get('slot_label') or item.get('dimension'))}</span>"
            + f"<b class=\"cosmo-relation-id\">{esc(marker)}</b>"
            + "</div>"
            + f"<h3 class=\"cosmo-relation-title\">{esc(item.get('label_cn'))}</h3>"
            + "</div>"
            + f"<span class=\"cosmo-confidence-pill\">{esc(item.get('confidence'))}置信</span></div>"
            + f"<p class=\"cosmo-relation-meta\">{esc(item.get('dimension'))} · {esc(item.get('coverage_status'))}</p>"
            + "<dl class=\"cosmo-card-meta-grid\">"
            + f"<div><dt>标签对象</dt><dd>{esc(marker)}标签</dd></div>"
            + f"<div><dt>证据强度</dt><dd>{esc(item.get('confidence'))} · {esc(item.get('evidence_count'))} 条</dd></div>"
            + "</dl>"
            + "<div class=\"cosmo-term-block\"><div class=\"cosmo-block-label\">核心标签</div>"
            + "<div class=\"cosmo-tag-terms\">"
            + "".join(f"<span>{esc(term)}</span>" for term in terms)
            + "</div></div>"
            + f"<div class=\"cosmo-evidence-strip\"><span>证据强度</span><b>{esc(item.get('evidence_count'))}</b><em>{esc(item.get('coverage_status'))}</em></div>"
            + cosmo_evidence_sources_html(item)
            + f"<p class=\"cosmo-business-meaning\"><b>业务解释：</b>{esc(item.get('business_meaning'))}</p>"
            + f"<div class=\"cosmo-action-direction\"><span>动作方向</span><b>{esc(action_direction)}</b></div>"
            + "</article>"
        )

    product_relations = [item for item in relations if item.get("dimension") == "产品标签"]
    user_relations = [item for item in relations if item.get("dimension") == "用户标签"]
    matrix_lanes = (
        "<div class=\"cosmo-matrix-lanes\">"
        + "<div class=\"cosmo-matrix-lane product-lane\">"
        + "<div class=\"cosmo-lane-title\"><span>产品标签 · 产品被算法识别为什么</span>"
        + f"<b>{esc(len(product_relations))} 类</b><em>用于标题、类目、卖点和页面承诺</em></div>"
        + "<div class=\"cosmo-lane-grid\">"
        + "".join(matrix_cell(item) for item in product_relations)
        + "</div></div>"
        + "<div class=\"cosmo-matrix-lane user-lane\">"
        + "<div class=\"cosmo-lane-title\"><span>用户标签 · 用户为什么搜索/购买</span>"
        + f"<b>{esc(len(user_relations))} 类</b><em>用于人群、场景、QA 和广告定向</em></div>"
        + "<div class=\"cosmo-lane-grid\">"
        + "".join(matrix_cell(item) for item in user_relations)
        + "</div></div>"
        + "</div>"
    )
    top_items = sorted(relations, key=lambda item: (as_float(item.get("evidence_count"), 0), clean(item.get("relation_type"))), reverse=True)
    top_rows = "".join(
        "<li>"
        + f"<span>{esc(item.get('display_relation') or item.get('label_cn'))}</span>"
        + f"<strong>{esc('、'.join((item.get('terms') or [])[:3]) or item.get('label_cn'))}</strong>"
        + f"<em>{esc(item.get('confidence'))} · {esc(item.get('evidence_count'))} 条证据</em>"
        + "</li>"
        for item in top_items[:8]
    )
    low_items = [item for item in relations if item.get("confidence") == "低"]
    gap_rows = "".join(
        "<li>"
        + f"<span>{esc(item.get('display_relation') or item.get('label_cn'))}</span>"
        + f"<strong>{esc('需补充证据' if clean(item.get('display_relation')) == clean(item.get('label_cn')) else item.get('label_cn'))}</strong>"
        + "<em>当前类目语义覆盖弱，不强行写成高置信标签</em>"
        + "</li>"
        for item in low_items[:6]
    )
    action_cards = "".join(
        f"<article class=\"cosmo-action-card\" data-action-kind=\"{esc(item.get('dimension'))}\">"
        + f"<span>{esc(item.get('display_relation') or item.get('label_cn'))}</span>"
        + f"<h3>{esc(item.get('label_cn'))}</h3>"
        + "<ul class=\"cosmo-action-list\">"
        + f"<li><b class=\"cosmo-action-label\">{esc(item.get('listing_label') or 'Listing')}</b><span>{esc(item.get('listing_action'))}</span></li>"
        + f"<li><b class=\"cosmo-action-label\">{esc(item.get('qa_label') or 'QA')}</b><span>{esc(item.get('qa_action'))}</span></li>"
        + f"<li><b class=\"cosmo-action-label\">{esc(item.get('ad_label') or '广告')}</b><span>{esc(item.get('ad_action'))}</span></li>"
        + "</ul>"
        + "</article>"
        for item in top_items[:6]
    )
    product_count = len([item for item in relations if item.get("dimension") == "产品标签" and item.get("evidence_count", 0) > 0])
    user_count = len([item for item in relations if item.get("dimension") == "用户标签" and item.get("evidence_count", 0) > 0])
    high_count = len([item for item in relations if item.get("confidence") == "高"])
    low_count = len([item for item in relations if item.get("confidence") == "低"])
    summary_strip = (
        "<div class=\"cosmo-summary-strip\">"
        + "<div class=\"cosmo-summary-item product\"><span>产品标签覆盖</span>"
        + f"<b>{esc(product_count)}/6</b><em>标题、类目、卖点承诺</em></div>"
        + "<div class=\"cosmo-summary-item user\"><span>用户标签覆盖</span>"
        + f"<b>{esc(user_count)}/9</b><em>人群、场景、QA 和广告</em></div>"
        + "<div class=\"cosmo-summary-item strong\"><span>高置信关系</span>"
        + f"<b>{esc(high_count)}</b><em>可进入页面和广告动作</em></div>"
        + "<div class=\"cosmo-summary-item weak\"><span>低覆盖关系</span>"
        + f"<b>{esc(low_count)}</b><em>只保留诊断，不写成承诺</em></div>"
        + "</div>"
    )
    gap_text = (
        f"产品标签已覆盖 {product_count} 类，用户标签已覆盖 {user_count} 类。"
        "若用户标签少于产品标签，下一轮应优先补充适用人群、使用场景、季节/地点和 QA 问答。"
    )
    return (
        "<div class=\"cosmo-tag-module\">"
        + "<div class=\"kpi-grid\">"
        + "".join(cards)
        + "</div>"
        + summary_strip
        + "<div class=\"cosmo-layout\">"
        + "<section class=\"cosmo-panel cosmo-matrix\"><div class=\"cosmo-panel-title\">15 标签矩阵</div>"
        + matrix_lanes
        + "</section>"
        + "<section class=\"cosmo-panel cosmo-top-list\"><div class=\"cosmo-panel-title\">高置信标签排行</div><ol>"
        + top_rows
        + "</ol></section>"
        + "<section class=\"cosmo-panel cosmo-gap-panel\"><div class=\"cosmo-panel-title\">产品标签 / 用户标签缺口</div><p>"
        + esc(gap_text)
        + "</p><ul>"
        + (gap_rows or "<li><span>OK</span><strong>关键标签已覆盖</strong><em>继续用评论和 QA 压实表达</em></li>")
        + "</ul></section>"
        + "<section class=\"cosmo-panel cosmo-action-board\"><div class=\"cosmo-panel-title\">Listing / QA / 广告动作</div><div class=\"cosmo-action-grid\">"
        + action_cards
        + "</div></section>"
        + "</div>"
        + "</div>"
    )


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
            segment_label = first(customer_product_position(product), product.get("segment_cn"), product.get("segment"), "核心细分")
            traffic_tags = (
                tag(segment_label, "green")
                + tag(price_band(product_price(product)), "green")
                + tag(f"评论{num(product_reviews(product))}")
            )
        cards.append(
            "<div class=\"comp-deep-card\">"
            + product_image_or_empty_html(product, "comp-deep-image", "comp-deep-image-empty", "标杆竞品图片")
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
    prices = sorted(as_float(product_price(product), 0) for product in candidates)
    if len(prices) >= 6:
        p75 = percentile(prices, 0.75) or prices[-1]
        median = statistics.median(prices)
        ceiling = max(99.0, min(p75 * 3, median * 6))
        candidates = [product for product in candidates if as_float(product_price(product), 0) <= ceiling]
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


SUPPLIER_CONTEXT_GENERIC_TERMS = {
    "户外",
    "露营",
    "野营",
    "便携",
    "帐篷",
    "篷",
    "用品",
    "装备",
    "跨境",
    "现货",
    "批发",
    "厂家",
    "工厂",
    "家用",
    "室内",
    "室外",
    "自动",
    "全自动",
    "折叠",
    "加厚",
    "防晒",
    "防雨",
    "防水",
    "多人",
}


SUPPLIER_CONTEXT_NOISE_TERMS = {
    "儿童",
    "亲子",
    "游戏屋",
    "吊床",
    "吊篮",
    "急救",
    "应急",
    "厕所",
    "洗澡",
    "更衣",
    "淋浴",
    "沙滩",
    "野炊",
    "餐具",
    "背包",
    "捕虫",
    "民宿",
    "酒店",
    "广告",
    "展销",
    "婚礼",
    "蒙古包",
    "印第安",
}


def supplier_title_text(supplier: dict[str, Any]) -> str:
    return clean(
        " ".join(
            str(supplier.get(key) or "")
            for key in ["title", "title_cn", "name", "product_name", "supplier_name", "seed_keyword"]
        )
    ).casefold()


def supplier_product_text(supplier: dict[str, Any]) -> str:
    return clean(
        " ".join(
            str(supplier.get(key) or "")
            for key in ["title", "title_cn", "name", "product_name"]
        )
    ).casefold()


def cjk_terms(value: Any) -> set[str]:
    terms: set[str] = set()
    for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", clean(value)):
        if chunk not in SUPPLIER_CONTEXT_GENERIC_TERMS and len(chunk) <= 12:
            terms.add(chunk)
        max_len = min(5, len(chunk))
        for size in range(2, max_len + 1):
            for idx in range(0, len(chunk) - size + 1):
                term = chunk[idx : idx + size]
                if term not in SUPPLIER_CONTEXT_GENERIC_TERMS:
                    terms.add(term)
    return terms


def lifecycle_base_context_terms(data_pack: dict[str, Any]) -> set[str]:
    cache_key = "_runtime_lifecycle_base_context_terms"
    cached = data_pack.get(cache_key)
    if isinstance(cached, set):
        return cached
    texts: list[str] = []
    research_object = data_pack.get("research_object")
    if isinstance(research_object, dict):
        texts.append(clean(research_object.get("value")))
    elif research_object:
        texts.append(clean(research_object))
    for product in effective_products(data_pack)[:80]:
        texts.extend(
            clean(product.get(key))
            for key in (
                "customer_segment_cn",
                "segment_cn",
                "segment",
                "title_cn",
                "customer_label_cn",
                "category_cn",
            )
        )
    for keyword in effective_keywords(data_pack)[:120]:
        keyword_cn = clean(first(keyword.get("keyword_cn"), keyword.get("label_cn"), default=""))
        if keyword_cn and "未映射关键词" not in keyword_cn:
            texts.append(keyword_cn)
    terms: set[str] = set()
    for text in texts:
        terms.update(cjk_terms(text))
    cached_terms = {term for term in terms if len(term) >= 2 and term not in SUPPLIER_CONTEXT_GENERIC_TERMS}
    data_pack[cache_key] = cached_terms
    return cached_terms


def lifecycle_context_terms(data_pack: dict[str, Any], segment: str = "") -> set[str]:
    terms = set(lifecycle_base_context_terms(data_pack))
    terms.update(cjk_terms(segment))
    return {term for term in terms if len(term) >= 2 and term not in SUPPLIER_CONTEXT_GENERIC_TERMS}


def supplier_matches_lifecycle_context(supplier: dict[str, Any], data_pack: dict[str, Any], segment: str = "") -> bool:
    text = supplier_product_text(supplier) or supplier_title_text(supplier)
    if not text:
        return False
    context_terms = lifecycle_context_terms(data_pack, segment)
    has_context_hit = any(term in text for term in context_terms)
    has_noise = any(term in text for term in SUPPLIER_CONTEXT_NOISE_TERMS)
    if context_terms:
        return has_context_hit and not (has_noise and not has_context_hit)
    if has_noise:
        return False
    segment_tokens = tokens(segment)
    supplier_tokens = tokens(text)
    return bool(segment_tokens and segment_tokens & supplier_tokens)


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
    diagnostic_items = [
        ("有效报价", f"{num(snapshot['valid_count'])} / 50", "未达到毛利率测算最低报价数"),
        ("标题覆盖", f"{snapshot['title_pct']}% / 70%", "用于判断供应记录是否同类商品"),
        ("链接指纹", f"{snapshot['identity_pct']}% / 70%", "用于去重、复核和回溯"),
        ("价格离散", f"P75/P25 {snapshot['p75_to_p25']:.2f}" if snapshot["p75_to_p25"] else "未形成分位数", "用于判断报价池是否可测算"),
    ]
    diagnostic_panel = (
        "<div class=\"chart-container diagnostic-chart-container\">"
        "<div class=\"chart-title\">毛利率测算未启用 · 1688质量门禁未通过</div>"
        "<div class=\"chart-subtitle\">保留模板图表槽位；当前只展示供应链补采诊断，不输出毛利率结论</div>"
        "<div id=\"marginChart\" class=\"chart-body chart-h-260 diagnostic-chart-body\" data-chart-disabled=\"true\">"
        + "".join(
            "<div class=\"diagnostic-chart-item\">"
            + f"<span>{esc(label)}</span><b>{esc(value)}</b><em>{esc(note)}</em>"
            + "</div>"
            for label, value, note in diagnostic_items
        )
        + "</div></div>"
    )
    return (
        "<div class=\"supply-grid\">"
        + f"<div class=\"supply-card\"><div class=\"supply-label\">供应链状态</div><div class=\"supply-value\">需补采</div><div class=\"supply-note\">当前数据不能进入毛利率测算</div></div>"
        + f"<div class=\"supply-card\"><div class=\"supply-label\">有效报价数</div><div class=\"supply-value\">{esc(num(snapshot['valid_count']))}</div><div class=\"supply-note\">要求 50 条以上且字段完整</div></div>"
        + f"<div class=\"supply-card\"><div class=\"supply-label\">标题覆盖率</div><div class=\"supply-value\">{esc(snapshot['title_pct'])}%</div><div class=\"supply-note\">用于判断是否同类商品</div></div>"
        + f"<div class=\"supply-card\"><div class=\"supply-label\">链接/指纹覆盖率</div><div class=\"supply-value\">{esc(snapshot['identity_pct'])}%</div><div class=\"supply-note\">用于去重和复核</div></div>"
        + "</div>"
        + "<div class=\"insight-box\"><strong>供应链核心结论：</strong><span>供应链测算未达门槛。</span> 当前 1688 数据没有达到客户报告毛利率测算门槛。系统已阻断最终成本结论，需要用细分赛道中文词继续采集，并保留商品标题、供应商、价格、链接或稳定商品指纹。</div>"
        + "<span class=\"asin-token template-scope-marker\" data-allow-asin=\"profit-model\" hidden></span>"
        + table(["检查项", "当前值", "通过标准"], reason_rows, "evidence-table insight-table sku supply-diagnostic-table")
        + diagnostic_panel
        + details("已尝试搜索词", table(["搜索词", "记录数"], seed_rows), True)
    )


def render_voc(data_pack: dict[str, Any], voc: dict[str, Any]) -> str:
    reviews = customer_visible_reviews(data_pack)
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

    def market_voc_card(review: dict[str, Any], kind: str, idx: int) -> str:
        card_prefix = "J" if kind == "joy" else "P"
        sentiment = review_sentiment_label(review)
        title = customer_review_title(review)
        summary_cn = customer_review_summary(review, 220)
        raw_excerpt = truncate(first(review.get("text"), review.get("content"), review.get("body"), review.get("comment"), default=""), 160)
        excerpt_html = (
            f"<p class=\"review-excerpt-en market-voc-excerpt\" data-allow-english-review=\"short\">{esc(raw_excerpt)}</p>"
            if raw_excerpt and not re.search(r"[\u4e00-\u9fff]", raw_excerpt)
            else ""
        )
        return (
            f"<article class=\"market-voc-card {kind}\">"
            f"<div class=\"market-voc-card-head\"><span>{card_prefix}{idx}</span><b>{esc(sentiment)} · {esc(review.get('rating'))}星</b></div>"
            f"<div class=\"market-voc-title\">{esc(title)}</div>"
            f"<p class=\"voc-quote quote-cn\">{esc(summary_cn)}</p>"
            f"{excerpt_html}"
            f"<p class=\"voc-desc\">{tag('证据强度：高')}</p>"
            f"</article>"
        )

    def market_voc_diagnostic_card(kind: str, idx: int) -> str:
        card_prefix = "J" if kind == "joy" else "P"
        title = "正面评论证据不足" if kind == "joy" else "负面评论证据不足"
        action = "继续补采 4-5 星评论，验证可转化为卖点的真实表达。" if kind == "joy" else "继续补采 1-3 星评论，锁定必须修复的产品与页面承诺。"
        return (
            f"<article class=\"market-voc-card {kind} diagnostic\">"
            f"<div class=\"market-voc-card-head\"><span>{card_prefix}{idx}</span><b>本栏未达可决策门槛</b></div>"
            f"<div class=\"market-voc-title\">{title}</div>"
            f"<p class=\"voc-quote quote-cn\">{action}</p>"
            f"<p class=\"voc-desc\">{tag('需补采真实评论')}</p>"
            f"</article>"
        )

    positive_cards = [market_voc_card(review, "joy", idx) for idx, review in enumerate(positive_reviews[:6], 1)]
    negative_cards = [market_voc_card(review, "pain", idx) for idx, review in enumerate(low_reviews[:6], 1)]
    while len(positive_cards) < 6:
        positive_cards.append(market_voc_diagnostic_card("joy", len(positive_cards) + 1))
    while len(negative_cards) < 6:
        negative_cards.append(market_voc_diagnostic_card("pain", len(negative_cards) + 1))
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
    quote_grid = (
        "<div class=\"market-voc-sentiment-columns\">"
        + "<section class=\"market-voc-column positive\"><div class=\"market-voc-column-head\"><span>高星证据</span><h3>正面好评</h3><p>左侧只放可转化为主图、五点、A+ 和广告落地页的高星证据。</p></div>"
        + "".join(positive_cards)
        + "</section>"
        + "<section class=\"market-voc-column negative\"><div class=\"market-voc-column-head\"><span>低星证据</span><h3>负面差评</h3><p>右侧只放必须转成产品修复、页面承诺或售后动作的低星证据。</p></div>"
        + "".join(negative_cards)
        + "</section></div>"
    )
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
    raw_suppliers = sorted(effective_suppliers(data_pack), key=lambda supplier: as_float(supplier.get("sales_30d"), 0), reverse=True)
    suppliers = [
        supplier
        for supplier in finished_supplier_records(raw_suppliers)
        if supplier_matches_lifecycle_context(supplier, data_pack)
    ]
    quality = supplier_quality_snapshot(suppliers)
    if current_readiness_view(data_pack).get("supply_blocked"):
        return render_supply_diagnostic(suppliers, quality)
    bucket_label = ""
    if not quality["passed"]:
        bucket = passing_supplier_bucket(raw_suppliers)
        if not bucket:
            return render_supply_diagnostic(suppliers, quality)
        bucket_label, bucket_suppliers, _bucket_quality = bucket
        suppliers = sorted(
            [
                supplier
                for supplier in bucket_suppliers
                if supplier_matches_lifecycle_context(supplier, data_pack)
            ],
            key=lambda supplier: as_float(supplier.get("sales_30d"), 0),
            reverse=True,
        )
        quality = supplier_quality_snapshot(suppliers)
        if not quality["passed"]:
            return render_supply_diagnostic(suppliers, quality)

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
    profitability_table, formula = render_profitability_table(effective_products(data_pack), valid_prices)
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
        else "<div class=\"insight-box\"><strong>测算口径：</strong>已先剔除非成品、配件散料和非同类工程件报价，再用剩余 1688 成品报价进行成本分位数和毛利率测算。</div>"
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
        + details("1688 供应商报价明细（去重后 Top60）", table(["商品标题", "供应商", "报价", "30日销量", "发货地", "搜索词"], supplier_rows), False)
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
    prompt_templates = [
        (
            "生成一张低价流量验证款首图：画面只保留一个清晰日常使用场景，背景干净，产品轮廓完整可识别，预留一个核心利益点标注区域；避免豪华道具和复杂布景，重点验证搜索结果页点击率、首屏理解速度和页面承诺是否成立。",
            "适用于：低价流量验证款，先验证点击率、核心场景和页面承诺边界。",
        ),
        (
            "生成一张主力差异化对比图：用真实生活化场景展示产品如何解决核心痛点，画面可包含轻量前后对比或竞品差异对照，突出材质、安装细节和可信承诺区域；质感要高于低价款，但不能脱离实物能力。",
            "适用于：主力差异化款，突出实物差异、竞品对比和可验证卖点。",
        ),
        (
            "生成一张高溢价套装款主图：完整展示主品、配件、包装、说明卡和升级使用场景，用有秩序的开箱构图表达套装完整度、礼品感和价值堆叠；光线真实温和，重点验证高毛利价格带是否有足够感知价值。",
            "适用于：高溢价套装款，验证 Bundle 价值感、礼品化和高毛利空间。",
        ),
    ]
    prompt_cards = []
    for idx, item in enumerate(opportunities[:3]):
        name = first(item.get("name"), f"机会 {idx + 1}")
        prompt_text, prompt_note = prompt_templates[idx % len(prompt_templates)]
        contextual_prompt = f"商品方向：{name}。{prompt_text}"
        prompt_cards.append(
            "<article class=\"prompt-card\">"
            + f"<div class=\"prompt-number\">Prompt {idx + 1:02d}</div>"
            + f"<div class=\"prompt-scene\">{esc(name)}</div>"
            + f"<div class=\"prompt-text\">{esc(contextual_prompt)}</div>"
            + f"<div class=\"prompt-note\">{esc(prompt_note)} 需结合实物照片和实测表现再二次修订。</div>"
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
    readiness = current_readiness_view(data_pack, analysis_plan)
    readiness_gaps = readiness.get("blocking_gaps") if isinstance(readiness, dict) else []
    if readiness_gaps:
        rows = [
            [
                customer_safe_gap_text(gap.get("module")),
                customer_safe_gap_text(gap.get("reason")),
                customer_safe_gap_text(gap.get("impact")),
                customer_safe_gap_text(gap.get("next_step")),
            ]
            for gap in readiness_gaps
            if isinstance(gap, dict)
        ]
        return table(["模块", "原因", "影响", "下一步"], rows)
    gaps = data_pack.get("data_gaps") or analysis_plan.get("limitations") or []
    rows = []
    for gap in gaps:
        if isinstance(gap, dict):
            rows.append(
                [
                    customer_safe_gap_text(first(gap.get("area"), gap.get("module"), default="数据门禁")),
                    customer_safe_gap_text(first(gap.get("gap"), gap.get("reason"), default="该维度存在缺口")),
                    customer_safe_gap_text(first(gap.get("impact"), default="影响对应结论强度")),
                    customer_safe_gap_text(first(gap.get("next_action"), gap.get("next_step"), default="补齐后重新渲染")),
                ]
            )
        else:
            rows.append(["数据限制", customer_safe_gap_text(gap), "影响对应结论强度", "补齐后重新渲染"])
    if not rows:
        rows = [["数据门禁", "当前无核心阻断项", "不影响完整报告输出", "按计划推进验证"]]
    return table(["模块", "原因", "影响", "下一步"], rows)


def customer_safe_gap_text(value: Any) -> str:
    text = clean(value)
    if "MCP returned Unauthorized" in text:
        text = text.replace("MCP returned Unauthorized, so public web evidence was collected with web search and marked separately.", "公开网页补充接口本轮未授权，已改用公开网页搜索结果并单独标注。")
    lower = text.casefold()
    if "returned no rows" in lower:
        text = "对应数据维度本轮未返回可验证结果，不能用于页面事实承诺；需要更换 ASIN 或关键词再次采集。"
    if "product_detail" in lower:
        text = text.replace("product_detail", "产品详情维度")
    if "product_trend" in lower:
        text = text.replace("product_trend", "产品趋势维度")
    if "product_reviews" in lower:
        text = text.replace("product_reviews", "评论维度")
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
    return customer_safe_asset_text(text)


def render_full_appendix(data_pack: dict[str, Any], analysis_plan: dict[str, Any]) -> str:
    products = effective_products(data_pack)
    keywords = effective_keywords(data_pack)
    reviews = effective_reviews(data_pack)
    tiktok_products = data_pack.get("tiktok_products") or []
    tiktok_videos = data_pack.get("tiktok_videos") or []
    suppliers = effective_suppliers(data_pack)
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
    decision = "No-Go"
    readiness_view = report_readiness_view(readiness, data_pack.get("quality") or {}, decision)
    data_pack["report_readiness"] = readiness
    data_pack["report_readiness_view"] = readiness_view
    write_lineage_markdown(data_pack, report_dir / "data" / "lineage.md")
    cosmo_tags, lifecycle = ensure_generated_analysis_artifacts(report_dir, data_pack, analysis_plan)
    write_report_views(report_dir, data_pack, analysis_plan, decision)
    write_site_assets(report_dir, data_pack, analysis_plan, decision, readiness)
    write_report_brief(report_dir, data_pack, analysis_plan, decision, CHILD_SKILLS)
    delivery = load_json(report_dir / "output" / "delivery_result.json", {})
    site_data = build_site_data(data_pack, analysis_plan, decision, CHILD_SKILLS, readiness)
    delivery["status"] = "blocked"
    delivery["decision"] = decision
    delivery["cleaning_summary"] = site_data["cleaning_summary"]
    delivery["cosmo_alexa_tags"] = {
        "path": "analysis/cosmo_alexa_tags.json",
        "relation_total": (cosmo_tags.get("coverage_summary") or {}).get("relation_total"),
        "covered_relations": (cosmo_tags.get("coverage_summary") or {}).get("covered_relations"),
    }
    delivery["lifecycle_sku_pool_summary"] = lifecycle_sku_pool_summary(lifecycle, data_pack)
    delivery["data_readiness"] = delivery_readiness_summary(readiness)
    delivery["supplier_quote_gate"] = readiness.get("supplier_quote_gate") or {}
    delivery["asin_display_scope"] = ["competitor_table", "benchmark_sniper", "profit_model", "demand_target_anchor", "sku_reference"]
    delivery["review_display_policy"] = "cn_summary_plus_en_excerpt"
    delivery["critic_review"] = {
        "path": "analysis/critic_review.json",
        "refinement_plan": "analysis/refinement_plan.json",
        "summary": "analysis/critic_summary.md",
        "pass": False,
        "score": 0,
        "max_refinement_rounds": 2,
        "status": "not_run_data_readiness_blocked",
    }
    write_delivery_result(report_dir, delivery, CHILD_SKILLS)
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
    trust_rows = [
        ["证据强度", readiness_view.get("evidence_strength", "低 / 阻断交付"), "当前只允许输出补采诊断，不输出完整结论"],
        ["数据覆盖", sample_coverage(data_pack), "用于定位补采方向，不作为客户决策结论"],
        ["数据缺口", f"{len(readiness.get('blocking_gaps') or [])} 项阻断", "所有缺口必须补齐后重新渲染"],
        ["置信等级", readiness_view.get("delivery_state", "阻断交付"), "诊断页保留模板槽位，但不伪造结论"],
        ["建议动作", "补齐门禁后重新渲染", "先完成数据补采，再恢复市场深度、生命周期和需求断层报告"],
    ]
    def diagnostic_links_html(link_prefix: str = "") -> str:
        return (
        "<div class=\"report-grid diagnostic-report-grid\">"
        f"<article class=\"report-card\"><a href=\"{link_prefix}market-depth-report.html\"><span>市场深度调研报告</span><strong>查看诊断</strong></a><p>当前只展示市场数据门禁、阻断原因和补采动作。</p></article>"
        f"<article class=\"report-card\"><a href=\"{link_prefix}lifecycle-strategy-report.html\"><span>产品全生命周期拓品战略报告</span><strong>查看诊断</strong></a><p>生命周期策略在数据补齐前不输出 SKU 结论。</p></article>"
        f"<article class=\"report-card\"><a href=\"{link_prefix}demand-gap-report.html\"><span>用户心智断层与需求机会报告</span><strong>查看诊断</strong></a><p>需求机会在评论和关键词门禁通过后恢复。</p></article>"
        "</div>"
        )

    def diagnostic_panel(link_prefix: str = "") -> str:
        return (
        "<section class=\"section\"><div class=\"section-header\"><span class=\"section-number\">00</span><div><h1 class=\"section-title\">三合一市场研究报告 · 补采诊断</h1><p class=\"section-desc\">当前数据未达到完整客户报告门槛，系统已阻断市场深度、生命周期和需求机会的最终交付。</p></div></div>"
        "<div class=\"insight-box\"><strong>当前判断：</strong>不能生成完整客户版结论。请先补齐以下门禁，再重新运行报告生成。</div>"
        + diagnostic_links_html(link_prefix)
        + table(["检查项", "当前值", "业务含义"], trust_rows)
        + table(["门禁项", "当前值", "通过标准", "状态"], gate_rows)
        + "</section><section class=\"section\"><div class=\"section-header\"><span class=\"section-number\">01</span><div><h2 class=\"section-title\">当前阻断项</h2></div></div>"
        + table(["模块", "原因", "下一步动作"], blocking_rows)
        + "</section><section class=\"section\"><div class=\"section-header\"><span class=\"section-number\">02</span><div><h2 class=\"section-title\">风险提醒</h2></div></div>"
        + table(["模块", "影响", "下一步动作"], warning_rows)
        + "</section>"
        )

    def inject_diagnostic_panel(html_doc: str, link_prefix: str = "") -> str:
        panel = diagnostic_panel(link_prefix)
        if "</main>" in html_doc:
            return html_doc.replace("</main>", panel + "</main>", 1)
        if "</body>" in html_doc:
            return html_doc.replace("</body>", panel + "</body>", 1)
        return html_doc + panel

    market_size = load_json(report_dir / "analysis" / "market_size.json", {})
    voc = load_json(report_dir / "analysis" / "voc.json", {})
    opportunity = load_json(report_dir / "analysis" / "opportunity.json", {})
    profitability = load_json(report_dir / "analysis" / "profitability.json", {})
    demand_gap = load_json(report_dir / "analysis" / "demand_gap.json", {})
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
        decision,
        renderer_callbacks(),
    )
    safe_docs = {key: redact_customer_html(inject_diagnostic_panel(html_doc), data_pack) for key, html_doc in docs.items()}
    for key in HTML_REPORTS:
        path = report_dir / HTML_REPORTS[key]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(safe_docs[key], encoding="utf-8")
    compat_path = report_dir / COMPAT_INDEX_REPORT
    compat_path.parent.mkdir(parents=True, exist_ok=True)
    compat_path.write_text(redact_customer_html(inject_diagnostic_panel(compat_html, "html_reports/"), data_pack), encoding="utf-8")
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
    keywords = len(effective_keywords(data_pack))
    products = len(effective_products(data_pack))
    reviews = len(customer_visible_reviews(data_pack))
    suppliers = len(effective_suppliers(data_pack))
    return f"关键词 {keywords}；竞品 {products}；评论 {reviews}；供应记录 {suppliers}"


def sample_coverage_tags(data_pack: dict[str, Any]) -> str:
    items = [
        (len(effective_keywords(data_pack)), "关键词"),
        (len(effective_products(data_pack)), "竞品"),
        (len(customer_visible_reviews(data_pack)), "评论"),
        (len(effective_suppliers(data_pack)), "供应记录"),
    ]
    tags = "".join(f"<span class=\"metric-tag\"><b>{esc(value)}</b><span>{esc(label)}</span></span>" for value, label in items)
    return f"<div class=\"metric-tags\">{tags}</div>"


def client_trust_strip(data_pack: dict[str, Any], analysis_plan: dict[str, Any], decision: str) -> str:
    gaps = len(data_pack.get("data_gaps") or []) + len(analysis_plan.get("limitations") or [])
    readiness = current_readiness_view(data_pack, analysis_plan, decision)
    if readiness.get("blocking_gaps"):
        gaps = max(gaps, len(readiness.get("blocking_gaps") or []))
    next_action = "进入实物测试与页面卖点验证" if str(readiness.get("decision")).lower() == "go" else "核实关键缺口后小步验证"
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
        + kpi_card("证据强度", readiness.get("evidence_strength", confidence_level(data_pack, analysis_plan)), "综合数据质量与方法链", "warning" if readiness.get("supply_blocked") else "success")
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
    readiness = current_readiness_view(data_pack, analysis_plan, decision)
    coverage_message = "当前数据足以支持 Go / Watch / No-Go 方向判断。"
    action = f"按 {readiness.get('decision', decision)} 节奏推进验证"
    if readiness.get("supply_blocked"):
        coverage_message = "市场、VOC 和生命周期候选可读；供应链测算未达门槛，不能输出毛利率或可控结论。"
        action = "先补采严格相关 1688 成品报价，再恢复成本测算"
    rows = [
        ["市场判断", readiness.get("evidence_strength", confidence_level(data_pack, analysis_plan)), coverage_message, action],
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
    readiness = current_readiness_view(data_pack, analysis_plan, decision)
    if readiness.get("supply_blocked"):
        items = [
            ("市场与需求", f"{object_value} 的市场、竞品和 VOC 证据可继续用于机会判断。"),
            ("供应链阻断", "供应链测算未达门槛，成本、毛利率和可打样结论不得输出。"),
            ("当前决策", "保持 Watch，先补采严格相关 1688 成品报价和字段完整供应记录。"),
            ("下一步动作", "补齐供应链后重跑毛利率，再决定是否进入实物测试和扩 SKU。"),
        ]
        return conclusion_block(items, "Strategic Summary · 诊断交付")
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
    readiness = current_readiness_view(data_pack, None, decision)
    quality_label = readiness.get("quality_label") or customer_quality_summary(data_pack.get("quality") or {})[0]
    quality_sub = readiness.get("quality_sub") or "关键数据覆盖较完整，可进入客户判断"
    quality_tone = readiness.get("quality_tone") or "warning"
    cards = [
        ("市场深度调研报告", HTML_REPORT_FILENAMES["market_depth"], "大盘、需求、竞品、VOC、TikTok、1688、风险与行动摘要。"),
        ("产品全生命周期拓品战略报告", HTML_REPORT_FILENAMES["lifecycle_strategy"], "用户画像、生命周期旅程、SKU、Bundle、路线图和风险矩阵。"),
        ("用户心智断层与需求机会报告", HTML_REPORT_FILENAMES["demand_gap"], "需求主题、满意度鸿沟、KANO × JTBD、用户原声和需求优先级。"),
    ]
    report_cards = "".join(
        f"<article class=\"report-card\"><a href=\"{bundle_href(href, link_prefix)}\"><span>{esc(label)}</span><strong>打开报告</strong></a><p>{esc(desc)}</p></article>"
        for label, href, desc in cards
    )
    metrics = (
        "<div class=\"kpi-grid\">"
        + kpi_card("核心判断", readiness.get("decision", decision), readiness.get("delivery_state", "Go / Watch / No-Go"), "warning")
        + kpi_card("数据质量", quality_label, quality_sub, quality_tone)
        + kpi_card("供应链状态", readiness.get("supply_status", "供应链测算门禁通过"), "成本和毛利率结论按门禁动态降级", "warning" if readiness.get("supply_blocked") else "success")
        + kpi_card("证据记录数", num(len(data_pack.get("sources") or [])), "内部审计链路保留", "")
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
        effective_products(data_pack),
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


def lifecycle_supplier_hint(data_pack: dict[str, Any], segment: str = "", offset: int = 0) -> str:
    suppliers = [
        supplier
        for supplier in effective_suppliers(data_pack)
        if supplier_matches_lifecycle_context(supplier, data_pack, segment)
    ]
    segment_text = clean(segment).casefold()
    if segment_text:
        matched = [
            supplier
            for supplier in suppliers
            if segment_text in clean(" ".join(str(supplier.get(key) or "") for key in ("title", "title_cn", "seed_keyword", "search_term"))).casefold()
        ]
        if matched:
            suppliers = matched
    if suppliers:
        supplier = suppliers[offset % len(suppliers)]
        title = clean(first(supplier.get("title_cn"), supplier.get("title"), supplier.get("seed_keyword"), default=""))
        price = first(supplier.get("price_rmb"), supplier.get("price"), default="")
        if title:
            return f"1688成品供应验证：{truncate(title, 28)} · {money(price, '¥')}"
    return "供应链需按成品报价、质检、包装和FBA费用复核"


LIFECYCLE_TYPE_KEY_BY_LETTER = {
    "A": "core_validation",
    "B": "scenario_upgrade",
    "C": "accessory_gap",
    "D": "maintenance_repurchase",
}
LIFECYCLE_LETTER_BY_TYPE_KEY = {value: key for key, value in LIFECYCLE_TYPE_KEY_BY_LETTER.items()}
LIFECYCLE_TYPE_ORDER = ["core_validation", "scenario_upgrade", "accessory_gap", "maintenance_repurchase"]


def lifecycle_strategy_type_key(value: Any, default: str = "core_validation") -> str:
    if isinstance(value, dict):
        value = first(value.get("strategy_type_key"), value.get("type"), default=default)
    raw = clean(value)
    if not raw:
        return default
    legacy = raw.upper()[:1]
    if len(raw) == 1 and legacy in LIFECYCLE_TYPE_KEY_BY_LETTER:
        return LIFECYCLE_TYPE_KEY_BY_LETTER[legacy]
    normalized = re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")
    if normalized in LIFECYCLE_LETTER_BY_TYPE_KEY:
        return normalized
    return default


def lifecycle_legacy_type_code(value: Any) -> str:
    return LIFECYCLE_LETTER_BY_TYPE_KEY.get(lifecycle_strategy_type_key(value), "A")


LIFECYCLE_PATH_BY_TYPE = {
    "core_validation": "关联度",
    "scenario_upgrade": "场景",
    "accessory_gap": "消耗",
    "maintenance_repurchase": "维护",
}


LIFECYCLE_SUFFIX_BY_TYPE = {
    "core_validation": "基础验证款",
    "scenario_upgrade": "场景升级款",
    "accessory_gap": "配件补位款",
    "maintenance_repurchase": "维护复购款",
}


def lifecycle_priority(product: dict[str, Any], supplier: dict[str, Any] | None, idx: int) -> int:
    sales = as_float(product_sales(product), 0)
    reviews = as_float(product_reviews(product), 0)
    rating = as_float(first(product.get("rating"), product.get("星级"), default=0), 0)
    sales_score = min(22, sales / 2500 * 22) if sales else 0
    review_score = min(12, reviews / 5000 * 12) if reviews else 0
    rating_score = min(12, max(0, rating - 3.8) * 12) if rating else 4
    supplier_score = 10 if supplier else 0
    rank_penalty = min(16, idx * 0.25)
    return max(45, min(98, round(58 + sales_score + review_score + rating_score + supplier_score - rank_penalty)))


def supplier_for_segment(suppliers: list[dict[str, Any]], segment: str, data_pack: dict[str, Any], offset: int = 0) -> dict[str, Any] | None:
    if not suppliers:
        return None
    matched = [
        supplier
        for supplier in suppliers
        if supplier_matches_lifecycle_context(supplier, data_pack, segment)
    ]
    segment_tokens = tokens(segment)
    for supplier in suppliers:
        supplier_tokens = tokens(supplier_product_text(supplier) or supplier_title_text(supplier))
        if segment_tokens and segment_tokens & supplier_tokens and supplier not in matched:
            matched.append(supplier)
    pool = matched or suppliers
    return pool[offset % len(pool)] if pool else None


def supplier_hint_from_record(supplier: dict[str, Any] | None) -> str:
    if not supplier:
        return "供应链需按成品报价、质检、包装和FBA费用复核"
    title = clean(first(supplier.get("title_cn"), supplier.get("title"), supplier.get("name"), supplier.get("product_name"), supplier.get("seed_keyword"), default=""))
    price = first(supplier.get("price_rmb"), supplier.get("price"), default="")
    if not title:
        return "供应链需按成品报价、质检、包装和FBA费用复核"
    return f"1688成品供应验证：{truncate(title, 34)} · {money(price, '¥')}"


def lifecycle_candidate_type(product: dict[str, Any], idx: int) -> str:
    price = as_float(product_price(product), 0)
    reviews = as_float(product_reviews(product), 0)
    if idx % 5 == 0:
        return "core_validation"
    if idx % 5 == 4:
        return "maintenance_repurchase"
    if price >= 80 or idx % 5 in {1, 2}:
        return "scenario_upgrade"
    if reviews >= 1200 or idx % 5 == 3:
        return "accessory_gap"
    return "maintenance_repurchase"


def generated_lifecycle_skus(data_pack: dict[str, Any], fallback_source: str) -> list[dict[str, Any]]:
    lifecycle = build_lifecycle_strategy_analysis(data_pack, {}, fallback_source)
    return lifecycle.get("sku_candidate_pool") or []


def build_lifecycle_strategy_analysis(data_pack: dict[str, Any], analysis_plan: dict[str, Any], fallback_source: str) -> dict[str, Any]:
    attach_report_label_profile(data_pack, analysis_plan)
    products = sorted(effective_products(data_pack), key=lambda product: as_float(product_sales(product), 0), reverse=True)
    suppliers = [
        supplier
        for supplier in finished_supplier_records(effective_suppliers(data_pack))
        if supplier_matches_lifecycle_context(supplier, data_pack)
    ]
    type_labels = profile_lifecycle_type_labels(data_pack)
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    max_candidates = 80
    for idx, product in enumerate(products):
        if len(candidates) >= max_candidates:
            break
        segment = clean(first(product.get("customer_segment_cn"), product.get("segment_cn"), product.get("segment"), customer_product_position(product), default="核心赛道"))
        if not segment or segment in {"未知", "未分层"}:
            segment = customer_product_position(product)
        sku_type = lifecycle_candidate_type(product, idx)
        suffix = type_labels.get(sku_type) or LIFECYCLE_SUFFIX_BY_TYPE[sku_type]
        name = f"{segment} {suffix}"
        reference_asin = clean(product.get("asin"))
        dedupe_key = f"{reference_asin}|{name}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        supplier = supplier_for_segment(suppliers, segment, data_pack, idx)
        base_price = as_float(product_price(product), 19.99) or 19.99
        if sku_type == "core_validation":
            price = f"{money(max(9.99, base_price * 0.86))}"
            stage = "首购转化"
            pain = "用标杆竞品的主销价格带做首发锚点，聚焦最强需求赛道"
        elif sku_type == "scenario_upgrade":
            price = f"{money(max(12.99, base_price * 1.18))}"
            stage = "体验升级"
            pain = "围绕高频痛点强化规格、材质、安装或真实场景体验"
        elif sku_type == "accessory_gap":
            price = f"{money(max(6.99, base_price * 0.24))}-{money(max(9.99, base_price * 0.42))}"
            stage = "竞品补位"
            pain = "围绕安装、固定、收纳、替换等评论痛点形成低风险扩展"
        else:
            price = f"{money(max(6.99, base_price * 0.18))}-{money(max(9.99, base_price * 0.34))}"
            stage = "复购维护"
            pain = "把维护、替换和售后承诺产品化，延长生命周期"
        reference_label = lifecycle_reference_competitor_label(first(product.get("brand"), ""), segment)
        priority = lifecycle_priority(product, supplier, idx)
        candidates.append(
            {
                "id": f"SKU-{len(candidates)+1:03d}",
                "name": name,
                "stage": stage,
                "type": sku_type,
                "strategy_type_key": sku_type,
                "type_label_cn": suffix,
                "ecosystem_path": LIFECYCLE_PATH_BY_TYPE[sku_type],
                "ecosystem_segment": segment,
                "price": price,
                "supply": supplier_hint_from_record(supplier),
                "phase": "P1" if priority >= 82 else "P2",
                "priority": priority,
                "pain": f"对标 {reference_label}：{pain}",
                "target_segment": segment,
                "reference_competitor": reference_label,
                "reference_asin": reference_asin,
                "reference_price": money(base_price),
                "reference_rating": first(product.get("rating"), "-"),
                "reference_reviews": num(product_reviews(product)),
                "reference_sales": num(product_sales(product)),
                "reference_image_url": product_image_url(product),
                "supplier_title": truncate(first((supplier or {}).get("title_cn"), (supplier or {}).get("title"), default=""), 80),
                "source_id": source_ids_for(product, fallback_source),
            }
        )
    supplier_only_count = 0
    for supplier in suppliers:
        if len(candidates) >= max_candidates:
            break
        if not supplier_matches_lifecycle_context(supplier, data_pack):
            continue
        title = clean(first(supplier.get("title_cn"), supplier.get("title"), supplier.get("name"), supplier.get("product_name"), supplier.get("seed_keyword"), default=""))
        if not title:
            continue
        segment = truncate(title, 16)
        sku_type = "accessory_gap" if supplier_only_count % 2 == 0 else "maintenance_repurchase"
        suffix = type_labels.get(sku_type) or LIFECYCLE_SUFFIX_BY_TYPE[sku_type]
        name = f"{segment} {suffix}"
        dedupe_key = f"supplier|{normalize_cosmo_term(name)}"
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        candidates.append(
            {
                "id": f"SKU-{len(candidates)+1:03d}",
                "name": name,
                "stage": "供应链验证",
                "type": sku_type,
                "strategy_type_key": sku_type,
                "type_label_cn": suffix,
                "ecosystem_path": LIFECYCLE_PATH_BY_TYPE[sku_type],
                "ecosystem_segment": segment,
                "price": money(first(supplier.get("price_rmb"), supplier.get("price"), default=""), "¥"),
                "supply": supplier_hint_from_record(supplier),
                "phase": "P2",
                "priority": max(52, 70 - supplier_only_count),
                "pain": "供应端存在可验证候选，但需要与 Amazon 参考竞品二次匹配后再进入打样。",
                "target_segment": segment,
                "reference_competitor": "供应端候选",
                "reference_asin": "",
                "reference_price": "",
                "reference_rating": "",
                "reference_reviews": "",
                "reference_sales": "",
                "supplier_title": truncate(title, 80),
                "source_id": source_ids_for(supplier, fallback_source),
            }
        )
        supplier_only_count += 1
    candidates.sort(key=lambda item: as_float(item.get("priority"), 0), reverse=True)
    recommended = candidates[:8]
    path_counts = Counter(clean(item.get("ecosystem_path")) for item in candidates)
    segment_counts = Counter(clean(item.get("ecosystem_segment")) for item in candidates)
    return {
        "schema_version": "lifecycle_strategy.v2",
        "generated_at": datetime.now(UTC).isoformat(),
        "basis": "由当前有效竞品、VOC、关键词和 1688 成品供应记录生成 SKU 候选池；模板槽位不代表完整 SKU 池。",
        "sku_candidate_pool": candidates,
        "recommended_skus": recommended,
        "ecosystem_nodes": {
            "root": first((data_pack.get("research_object") or {}).get("value") if isinstance(data_pack.get("research_object"), dict) else "", "当前研究对象"),
            "paths": [{"label": key, "count": value} for key, value in path_counts.items() if key],
            "segments": [{"label": key, "count": value} for key, value in segment_counts.most_common(24) if key],
        },
        "filter_diagnostics": {
            "effective_products": len(products),
            "effective_suppliers": len(effective_suppliers(data_pack)),
            "finished_suppliers": len(suppliers),
            "sku_candidate_pool": len(candidates),
            "recommended_skus": len(recommended),
            "filtered_reason": "仅保留具备有效竞品锚点或 1688 成品供应证据的 SKU 候选；配件散料和非同类供应记录只进入审计。",
        },
    }


def ensure_generated_analysis_artifacts(report_dir: Path, data_pack: dict[str, Any], analysis_plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    fallback_source = primary_source_id(data_pack)
    cosmo_tags = generate_cosmo_alexa_tags(data_pack, analysis_plan)
    lifecycle = build_lifecycle_strategy_analysis(data_pack, analysis_plan, fallback_source)
    data_pack["cosmo_alexa_tags"] = cosmo_tags
    data_pack["lifecycle_strategy"] = lifecycle
    write_json(report_dir / "analysis" / "cosmo_alexa_tags.json", cosmo_tags)
    write_json(report_dir / "analysis" / "lifecycle_strategy.json", lifecycle)
    return cosmo_tags, lifecycle


def lifecycle_sku_pool_summary(lifecycle: dict[str, Any], data_pack: dict[str, Any]) -> dict[str, Any]:
    diagnostics = lifecycle.get("filter_diagnostics") or {}
    return {
        "effective_products": diagnostics.get("effective_products", len(effective_products(data_pack))),
        "effective_suppliers": diagnostics.get("effective_suppliers", len(effective_suppliers(data_pack))),
        "finished_suppliers": diagnostics.get("finished_suppliers"),
        "sku_candidate_pool": diagnostics.get("sku_candidate_pool", len(lifecycle.get("sku_candidate_pool") or [])),
        "recommended_skus": diagnostics.get("recommended_skus", len(lifecycle.get("recommended_skus") or [])),
        "filtered_reason": diagnostics.get("filtered_reason", ""),
    }


def lifecycle_reference_competitor_label(brand: Any, segment: Any = "") -> str:
    brand_text = re.sub(r"\bB0[A-Z0-9]{8,12}\b", "", clean(brand), flags=re.I)
    brand_text = brand_text.replace("参考竞品", "").strip(" ·-")
    segment_text = re.sub(r"\bB0[A-Z0-9]{8,12}\b", "", clean(segment), flags=re.I)
    segment_text = segment_text.replace("参考竞品", "").strip(" ·-")
    if brand_text and not has_cjk_text(brand_text) and len(re.findall(r"[A-Za-z]{2,}", brand_text)) >= 3:
        brand_text = ""
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
    candidate_pool = lifecycle.get("sku_candidate_pool")
    recommended = lifecycle.get("recommended_skus")
    if isinstance(candidate_pool, list) and candidate_pool:
        ordered: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in (recommended if isinstance(recommended, list) else []) + candidate_pool:
            if not isinstance(item, dict):
                continue
            key = clean(first(item.get("id"), item.get("reference_asin"), item.get("name"), default=""))
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            ordered.append(item)
        return ordered
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
    readiness = current_readiness_view(data_pack)
    supply_blocked = readiness.get("supply_blocked") is True
    supplier_count = len(finished_supplier_records(effective_suppliers(data_pack)))
    if supply_blocked:
        supply_metric_label = "供应链测算状态"
        p1_metric_label = "P1 候选 SKU"
        supply_control = "供应链测算未达门槛"
        supply_risk = "供应链测算未达门槛，不能输出成本、毛利率或可打样结论"
        supply_style = "warning"
        phase_subtext = "补齐供应链后再定首发"
        p1_subtext = "供应链补采前仅为候选"
        phase_row = "P1 候选验证 + 供应链补采优先"
        strategy_conclusion = "当前生命周期 SKU 只能作为候选池阅读：目标赛道、参考竞品和页面承诺可以继续推演，但供应链测算未达门槛，不能把任何 SKU 写成可打样或可控结论。下一步必须先补齐严格相关成品报价，再恢复成本、毛利率和首发优先级判断。"
    elif supplier_count >= 50:
        supply_metric_label = "供应链可控度"
        p1_metric_label = "P1 首发 SKU"
        supply_control = "门禁通过"
        supply_risk = "严格相关供应端报价已通过数量和字段质量门禁，可进入实物复核"
        supply_style = "success"
        phase_subtext = "可控供应链"
        p1_subtext = "可先进入验证"
        phase_row = "P1 可控供应链 + 信任与开箱触点优先"
        strategy_conclusion = "以首发可控 SKU 为核心，围绕高优先级赛道做 Bundle 价格台阶验证；每个 SKU 必须绑定目标赛道、参考竞品、供应链风险和页面承诺，先验证转化与退货风险，再扩展长期复购触点。"
    elif supplier_count > 0:
        supply_metric_label = "供应链复核状态"
        p1_metric_label = "P1 候选 SKU"
        supply_control = "需复核"
        supply_risk = "供应链风险：中，需要继续补齐报价、质检、认证和包装验证"
        supply_style = "warning"
        phase_subtext = "报价复核后再定首发"
        p1_subtext = "先补质检与报价"
        phase_row = "P1 候选验证 + 报价复核优先"
        strategy_conclusion = "当前 SKU 池具备拓品方向参考价值，但供应链仍需复核报价、质检、认证和包装口径。先把候选 SKU 与成品报价一一绑定，再决定首发优先级和 Bundle 放量节奏。"
    else:
        supply_metric_label = "供应链证据状态"
        p1_metric_label = "P1 候选 SKU"
        supply_control = "需验证"
        supply_risk = "供应链风险：高，缺少可复核成品报价"
        supply_style = "warning"
        phase_subtext = "先补供应链证据"
        p1_subtext = "仅为方向候选"
        phase_row = "P1 候选验证 + 供应链证据补齐"
        strategy_conclusion = "当前生命周期策略只保留方向推演：缺少可复核成品报价时，不能输出首发、成本或可控供应结论。需要先补采供应链证据，再进入 SKU 打样判断。"
    type_counts = Counter(str(sku.get("type") or "").upper() for sku in skus)
    bundle_count = len([sku for sku in skus if str(sku.get("type")).upper() == "B" or "套装" in clean(sku.get("name"))])
    p1_count = len([sku for sku in skus if clean(sku.get("phase")).upper() == "P1"])
    high_priority = len([sku for sku in skus if as_float(sku.get("priority"), 0) >= 80])
    rows = [
        ["拓品 SKU 总数", len(skus), fallback_source],
        [supply_metric_label, supply_control, fallback_source],
        ["供应链风险", supply_risk, fallback_source],
        ["复购维护型 SKU", len([sku for sku in skus if str(sku.get("type")).upper() == "D"]), fallback_source],
        ["Bundle 增长抓手", "AOV 提升", fallback_source],
        ["建议首发 Phase", phase_row, fallback_source],
    ]
    return (
        "<div class=\"kpi-grid lifecycle-kpi-primary\">"
        + kpi_card("拓品 SKU 总数", len(skus), "覆盖生命周期触点", "success")
        + kpi_card(supply_metric_label, supply_control, supply_risk, supply_style)
        + kpi_card("复购引擎", "60-90 天", "清洁、替换、维护", "warning")
        + kpi_card("AOV 引擎", "Bundle", "组合包优先", "success")
        + kpi_card("首发 Phase", "P1", phase_subtext, "warning" if supply_blocked else "")
        + "</div>"
        + "<div class=\"lifecycle-kpi-secondary\">"
        + kpi_card(p1_metric_label, p1_count, p1_subtext, "warning" if supply_blocked else "success")
        + kpi_card("高优先级 SKU", high_priority, "优先级 ≥ 80", "warning")
        + kpi_card("套装/升级 SKU", bundle_count, "承担 AOV 提升", "")
        + kpi_card("策略类型覆盖", len([key for key, count in type_counts.items() if key and count]), "主品验证 / 场景升级 / 配件补位 / 维护复购", "")
        + "</div>"
        + f"<div class=\"insight-box\"><strong>战略结论：</strong>{esc(strategy_conclusion)}</div>"
        + lifecycle_evidence_drawer("战略仪表盘证据", ["指标", "结果", "source_id"], rows)
    )


def render_personas(data_pack: dict[str, Any], lifecycle: dict[str, Any], fallback_source: str) -> str:
    products = effective_products(data_pack)
    reviews = customer_visible_reviews(data_pack)
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
        ["开箱 0-30 分钟", "尺寸确认卡、搭建步骤卡、页面承诺核对卡", "降低第一次使用阻力", fallback_source],
        ["第 1-7 天", "场景固定清单、使用任务卡、基础组合包", "完成新鲜感到习惯的过渡", fallback_source],
        ["第 7 天-6 个月", "清洁维护、替换配件、季节与场景主题包", "延长生命周期并制造复购", fallback_source],
        ["每月+", "耗材、主题内容、配件 Bundle", "形成 AOV 与复购飞轮", fallback_source],
        ["6 个月+", "品牌延伸、礼品升级包、二代配件", "从单品进入可持续产品生态", fallback_source],
    ]
    cards = "".join(
        f"<article class=\"tl-card\"><div class=\"tl-header\">阶段 {idx}<span class=\"arrow\">→</span></div><div class=\"tl-body\"><div class=\"tl-time\">{esc(row[0])}</div><div class=\"tl-skus\">{esc(row[1])}</div><div class=\"tl-pain\">{esc(row[2])}</div></div></article>"
        for idx, row in enumerate(phases, 1)
    )
    return "<div class=\"timeline-grid\">" + cards + "</div>" + lifecycle_evidence_drawer("生命周期旅程证据表", ["阶段", "建议 SKU 与触点", "用户任务", "source_id"], phases)


LIFECYCLE_TYPE_DESCRIPTIONS = {
    "core_validation": "与主产品强关联，适合首发验证",
    "scenario_upgrade": "用于规格、场景或人群扩展",
    "accessory_gap": "用于配件、耗材或低风险补位",
    "maintenance_repurchase": "用于维护、替换和售后复购",
}


def infer_lifecycle_type_labels(skus: list[dict[str, Any]]) -> dict[str, str]:
    labels: dict[str, str] = {}
    suffix_pattern = re.compile(r"(基础款|升级款|套装款|配件款|耗材款|复购耗材|复购款|维护款|维护复购款)$")
    grouped: dict[str, list[str]] = defaultdict(list)
    for sku in skus:
        sku_type = lifecycle_strategy_type_key(sku)
        explicit = clean(sku.get("type_label_cn"))
        if explicit:
            labels[sku_type] = explicit
            continue
        name = clean(sku.get("name"))
        match = suffix_pattern.search(name)
        if match:
            grouped[sku_type].append(match.group(1))
    for sku_type, suffixes in grouped.items():
        unique = list(dict.fromkeys(suffixes))
        if len(unique) == 1:
            labels.setdefault(sku_type, unique[0])
        elif unique:
            labels.setdefault(sku_type, " / ".join(unique[:2]))
    return labels


def lifecycle_type_label(value: Any, type_labels: dict[str, str] | None = None) -> str:
    sku_type = lifecycle_strategy_type_key(value)
    labels = type_labels or {}
    return labels.get(sku_type) or LIFECYCLE_SUFFIX_BY_TYPE.get(sku_type) or "拓品路径"


def render_ecosystem(data_pack: dict[str, Any], skus: list[dict[str, Any]], fallback_source: str) -> str:
    counts = Counter(lifecycle_strategy_type_key(sku) for sku in skus)
    type_labels = {**infer_lifecycle_type_labels(skus), **profile_lifecycle_type_labels(data_pack)}
    total_skus = len(skus)
    rows = [
        [lifecycle_type_label(key, type_labels), counts.get(key, 0), LIFECYCLE_TYPE_DESCRIPTIONS[key], fallback_source]
        for key in LIFECYCLE_TYPE_ORDER
    ]
    return (
        "<div class=\"ecosystem-kicker\">四维拓品生态 · 4D Ecosystem</div>"
        + f"<div class=\"ecosystem-pool-summary\"><strong>SKU 候选池总数：{total_skus}</strong><span>图表按当前候选池动态生成，策略卡只展示 Top 推荐，不代表完整候选池数量。</span></div>"
        + "<div class=\"chart-grid ecosystem-chart-grid\">"
        + echart_box("sunburst", "四维拓品生态全景 · Sunburst", "研究对象 → 四维路径 → 赛道/场景 → SKU 候选", 500)
        + echart_box("priorityChart", "Top SKU 优先级评分", "≤8 个使用紧凑尺度；9-20 个显示全量；>20 个展示 Top 15", 500)
        + "</div>"
        + "<div class=\"card ecosystem-summary-card\"><div class=\"chart-title\">四维拓品生态</div>"
        + mini_chart([(row[0], float(row[1]), row[1]) for row in rows], "good")
        + "</div>"
        + lifecycle_evidence_drawer("四维拓品生态证据表", ["维度", "SKU 数", "打法", "source_id"], rows)
    )


LIFECYCLE_SKU_TEMPLATE_SLOTS = [
    {
        "type": "core_validation",
        "strategy_type_key": "core_validation",
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
        "type": "scenario_upgrade",
        "strategy_type_key": "scenario_upgrade",
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
        "type": "scenario_upgrade",
        "strategy_type_key": "scenario_upgrade",
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
        "type": "accessory_gap",
        "strategy_type_key": "accessory_gap",
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
        "type": "maintenance_repurchase",
        "strategy_type_key": "maintenance_repurchase",
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
    type_class = {
        "core_validation": "a red",
        "scenario_upgrade": "b blue",
        "accessory_gap": "c green",
        "maintenance_repurchase": "d purple",
    }
    body_rows = []
    full_body_rows = []
    strategy_cards = []
    strategy_skus = fixed_lifecycle_sku_slots(skus)
    table_skus = skus if len(skus) >= len(LIFECYCLE_SKU_TEMPLATE_SLOTS) else strategy_skus
    visible_table_skus = table_skus[:15] if len(table_skus) > 15 else table_skus
    type_labels = {**infer_lifecycle_type_labels(table_skus), **infer_lifecycle_type_labels(strategy_skus)}
    for sku in strategy_skus:
        sku_type = lifecycle_strategy_type_key(sku)
        supply_text = clean(sku.get("supply"))
        target_segment = lifecycle_customer_text(sku.get("target_segment"), "-")
        reference_competitor = lifecycle_reference_competitor_label(sku.get("reference_competitor"), target_segment)
        reference_asin = clean(sku.get("reference_asin"))
        reference_asin_html = (
            f"<span class=\"asin-token\" data-allow-asin=\"sku-reference\">{esc(reference_asin)}</span>"
            if reference_asin
            else "<span class=\"diagnostic-inline\">未达有效竞品 ASIN 绑定门槛</span>"
        )
        reference_metrics = " / ".join(
            part
            for part in [
                clean(sku.get("reference_price")),
                f"{clean(sku.get('reference_rating'))}星" if clean(sku.get("reference_rating")) else "",
                f"{clean(sku.get('reference_reviews'))}评" if clean(sku.get("reference_reviews")) else "",
                f"{clean(sku.get('reference_sales'))}/月" if clean(sku.get("reference_sales")) else "",
            ]
            if part
        )
        sku_pain = lifecycle_customer_text(sku.get("pain"), "围绕生命周期触点补位")
        if "仅竞品" in supply_text or "待核实" in supply_text or "待验证" in supply_text:
            supply_class = "pending"
            supply_label = "候选"
        elif "自有" in supply_text or "自产" in supply_text or "可控" in supply_text:
            supply_class = "self"
            supply_label = "供应锚点"
        elif "混合" in supply_text:
            supply_class = "mix"
            supply_label = "混合"
        else:
            supply_class = "ext"
            supply_label = "外采"
        priority = max(1, min(100, int(as_float(sku.get("priority"), 50))))
        bar_color = "#c9a05a" if priority >= 70 else "#3d6b9e" if priority >= 55 else "#c9c9c9"
        reference_image = sku_reference_image_html(sku)
        strategy_cards.append(
            "<article class=\"sku-strategy-card\">"
            + reference_image
            + f"<div class=\"sku-strategy-head\"><span>{esc(lifecycle_type_label(sku_type, type_labels))} · {esc(first(sku.get('phase'), '-'))}</span><b>{priority}</b></div>"
            + f"<h3>{esc(first(sku.get('name'), '基础款'))}</h3>"
            + "<dl class=\"sku-strategy-meta\">"
            + f"<div><dt>目标赛道</dt><dd>{esc(target_segment)}</dd></div>"
            + f"<div><dt>参考竞品</dt><dd>{esc(reference_competitor)}</dd></div>"
            + f"<div><dt>参考ASIN</dt><dd>{reference_asin_html}</dd></div>"
            + f"<div><dt>竞品指标</dt><dd>{esc(reference_metrics or '未达可决策门槛')}</dd></div>"
            + f"<div><dt>价格带</dt><dd>{esc(first(sku.get('price'), '$19-$29'))}</dd></div>"
            + f"<div><dt>供应链风险</dt><dd>{esc(supply_text or '按成品报价复核')}</dd></div>"
            + "</dl>"
            + f"<p>{esc(sku_pain)}</p>"
            + "</article>"
        )
    def sku_row_html(sku: dict[str, Any], idx: int) -> str:
        sku_type = lifecycle_strategy_type_key(sku)
        supply_text = clean(sku.get("supply"))
        target_segment = lifecycle_customer_text(sku.get("target_segment"), "-")
        reference_competitor = lifecycle_reference_competitor_label(sku.get("reference_competitor"), target_segment)
        reference_asin = clean(sku.get("reference_asin"))
        reference_asin_html = (
            f"<span class=\"asin-token\" data-allow-asin=\"sku-reference\">{esc(reference_asin)}</span>"
            if reference_asin
            else "<span class=\"diagnostic-inline\">需补有效竞品ASIN</span>"
        )
        reference_metrics = " / ".join(
            part
            for part in [
                clean(sku.get("reference_price")),
                f"{clean(sku.get('reference_rating'))}星" if clean(sku.get("reference_rating")) else "",
                f"{clean(sku.get('reference_reviews'))}评" if clean(sku.get("reference_reviews")) else "",
                f"{clean(sku.get('reference_sales'))}/月" if clean(sku.get("reference_sales")) else "",
            ]
            if part
        )
        sku_pain = lifecycle_customer_text(sku.get("pain"), "围绕生命周期触点补位")
        if "仅竞品" in supply_text or "待核实" in supply_text or "待验证" in supply_text:
            supply_class = "pending"
            supply_label = "候选"
        elif "自有" in supply_text or "自产" in supply_text or "可控" in supply_text:
            supply_class = "self"
            supply_label = "供应锚点"
        elif "混合" in supply_text:
            supply_class = "mix"
            supply_label = "混合"
        else:
            supply_class = "ext"
            supply_label = "外采"
        priority = max(1, min(100, int(as_float(sku.get("priority"), 50))))
        bar_color = "#c9a05a" if priority >= 70 else "#3d6b9e" if priority >= 55 else "#c9c9c9"
        ecosystem_path = first(sku.get("ecosystem_path"), lifecycle_type_label(sku_type, type_labels))
        ecosystem_segment = first(sku.get("ecosystem_segment"), target_segment)
        reference_image = sku_reference_image_html(sku, "sku-reference-thumb table-thumb")
        sku_title_block = (
            "<div class=\"sku-title-cell\">"
            + reference_image
            + "<div>"
            + f"<strong class=\"sku-title-text\">{esc(first(sku.get('name'), '基础款'))}</strong><br><span class=\"sku-muted\">目标赛道：{esc(target_segment)}；参考竞品：{esc(reference_competitor)}；ASIN：{reference_asin_html}</span><br><span class=\"sku-muted\">竞品指标：{esc(reference_metrics or '未达可决策门槛')}</span><br><span class=\"sku-muted\">{esc(sku_pain)}</span>"
            + "</div></div>"
        )
        return (
            f"<tr data-filter=\"{esc(sku_type)}\" data-type=\"{esc(sku_type)}\" data-supply=\"{esc(supply_class)}\" data-phase=\"{esc(sku.get('phase'))}\" data-score=\"{priority}\" data-ecosystem-path=\"{esc(ecosystem_path)}\" data-segment=\"{esc(ecosystem_segment)}\">"
            + f"<td>{idx}</td>"
            + f"<td>{esc(sku.get('stage'))}</td>"
            + f"<td><span class=\"type-badge {esc(type_class.get(sku_type, 'a red'))}\">{esc(lifecycle_type_label(sku_type, type_labels))}</span></td>"
            + f"<td>{sku_title_block}</td>"
            + f"<td><strong>{esc(first(sku.get('price'), '$19-$29'))}</strong></td>"
            + f"<td><span class=\"supply-badge {supply_class}\">{supply_label}</span><br><span class=\"sku-muted\">{esc(supply_text)}</span></td>"
            + f"<td><div class=\"priority-bar\"><div class=\"fill\" style=\"width:{priority}%;background:{bar_color}\"></div></div><span>{priority}</span></td>"
            + f"<td>{esc(sku.get('phase'))}</td>"
            + "<td>审计文件保留</td>"
            + "</tr>"
        )
    for idx, sku in enumerate(visible_table_skus, 1):
        body_rows.append(sku_row_html(sku, idx))
    for idx, sku in enumerate(table_skus, 1):
        full_body_rows.append(sku_row_html(sku, idx))
    full_pool = ""
    if len(table_skus) > len(visible_table_skus):
        full_pool = (
            "<details id=\"skuFullPool\" class=\"lifecycle-evidence-drawer evidence-drawer card sku-full-pool\"><summary>"
            + f"完整候选池（{len(table_skus)} 个，默认展示 Top {len(visible_table_skus)}）"
            + "</summary><div class=\"drawer-body\"><table class=\"evidence-table insight-table sku appendix-table\"><thead><tr>"
            + "<th>ID</th><th>生命周期</th><th>类型</th><th>拓品 SKU</th><th>价格带</th><th>供应链</th><th>优先级</th><th>Phase</th><th>证据口径</th>"
            + "</tr></thead><tbody>"
            + "".join(full_body_rows)
            + "</tbody></table></div></details>"
        )
    sku_table = (
        "<div class=\"filter-bar\"><button class=\"filter-btn active\" type=\"button\" data-filter=\"all\" aria-pressed=\"true\">全部</button>"
        f"<button class=\"filter-btn red\" type=\"button\" data-filter=\"core_validation\" aria-pressed=\"false\">{esc(lifecycle_type_label('core_validation', type_labels))}</button>"
        f"<button class=\"filter-btn blue\" type=\"button\" data-filter=\"scenario_upgrade\" aria-pressed=\"false\">{esc(lifecycle_type_label('scenario_upgrade', type_labels))}</button>"
        f"<button class=\"filter-btn green\" type=\"button\" data-filter=\"accessory_gap\" aria-pressed=\"false\">{esc(lifecycle_type_label('accessory_gap', type_labels))}</button>"
        f"<button class=\"filter-btn purple\" type=\"button\" data-filter=\"maintenance_repurchase\" aria-pressed=\"false\">{esc(lifecycle_type_label('maintenance_repurchase', type_labels))}</button>"
        "<button class=\"filter-btn\" type=\"button\" data-filter=\"ext\" aria-pressed=\"false\">供应链验证</button>"
        "<button class=\"filter-btn\" type=\"button\" data-filter=\"P1\" aria-pressed=\"false\">P1 立即启动</button></div>"
        + f"<div class=\"insight-box sku-pool-note\"><strong>默认展示 Top {len(visible_table_skus)}：</strong>完整候选池共 {len(table_skus)} 个，展开下方折叠表查看全量；“候选”表示只有竞品/VOC 证据，尚未绑定严格相关供应链锚点。</div>"
        "<table id=\"skuTable\" class=\"evidence-table insight-table sku appendix-table\"><thead><tr>"
        "<th>ID</th><th>生命周期</th><th>类型</th><th>拓品 SKU</th><th>价格带</th><th>供应链</th><th>优先级</th><th>Phase</th><th>证据口径</th>"
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
        + full_pool
    )


def render_bundle_strategy(skus: list[dict[str, Any]], fallback_source: str) -> str:
    top_segments = [clean(sku.get("target_segment")) for sku in skus if clean(sku.get("target_segment"))]
    primary_segment = top_segments[0] if top_segments else "核心产品"
    secondary_segment = next((segment for segment in top_segments[1:] if segment != primary_segment), primary_segment)
    accessory_segment = next((clean(sku.get("name")) for sku in skus if lifecycle_strategy_type_key(sku) == "accessory_gap"), f"{primary_segment} 配件")
    maintenance_segment = next((clean(sku.get("name")) for sku in skus if lifecycle_strategy_type_key(sku) == "maintenance_repurchase"), f"{primary_segment} 维护包")
    bundles = [
        {
            "name": f"{primary_segment} 入门验证套装",
            "badge": "STARTER",
            "tone": "danger",
            "target": "目标用户：首次购买用户 · 降低上手门槛 · 高转化",
            "items": [primary_segment, "尺寸确认卡", "搭建步骤卡", "基础安装/使用配件", "收纳或保护件"],
            "orig": "$105-$128",
            "final": "$89-$99",
            "save": "节省约 20% · AOV +$30-$40",
            "source_id": fallback_source,
        },
        {
            "name": f"{secondary_segment} 高配场景套装",
            "badge": "PREMIUM",
            "tone": "accent",
            "target": "目标用户：送礼场景 · 开箱即高级 · 高溢价",
            "items": [secondary_segment, "场景固定清单", "备用核心配件", "包装/收纳方案", "售后承诺卡"],
            "orig": "$120-$152",
            "final": "$109-$129",
            "save": "节省约 15% · AOV +$50-$70",
            "source_id": fallback_source,
        },
        {
            "name": f"{accessory_segment} 场景补位包",
            "badge": "ADD-ON",
            "tone": "success",
            "target": "目标用户：已明确场景用户 · 补齐安装/固定/收纳 · 提升 AOV",
            "items": [accessory_segment, "固定/安装补强件", "场景说明卡", "内容引导页", "便携收纳件"],
            "orig": "$135-$174",
            "final": "$119-$139",
            "save": "节省约 18% · AOV +$60-$80",
            "source_id": fallback_source,
        },
        {
            "name": f"{maintenance_segment} 维护替换包",
            "badge": "REFILL",
            "tone": "warning",
            "target": "目标用户：所有已购用户 · LTV 引擎 · 60-90 天复购",
            "items": [maintenance_segment, "清洁护理件", "替换配件", "维护说明卡"],
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
        "四组套装分别承担流量入口、场景溢价、补位增购和复购维护。先用入门验证套装确认转化，"
        "再用高配场景与补位包拉高 AOV，最后用维护替换包延长 LTV。"
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


def render_lifecycle_risks(data_pack: dict[str, Any], fallback_source: str) -> str:
    readiness = current_readiness_view(data_pack)
    if readiness.get("supply_blocked"):
        supply_mitigation = "Phase 1 先补齐严格相关成品报价、质检和包装复核；供应链测算恢复前不输出可控或可打样结论"
    else:
        supply_mitigation = "Phase 1 优先可控供应链；外采至少 2 家备选"
    rows = [
        ["供应链风险", "电子件/外采件质量不稳定", supply_mitigation, fallback_source],
        ["合规与信任风险", "涉及数据、安全、认证、售后承诺等信任门槛", "按品类核查法规与平台政策；关键承诺前置到页面", fallback_source],
        ["竞品跟进风险", "高溢价卖点被快速复制", "外观、IP、包装体验和评论证据形成组合壁垒", fallback_source],
    ]
    cards = "".join(
        f"<article class=\"risk-card\"><h3>{esc(row[0])}</h3><p class=\"desc\">{esc(row[1])}</p><div class=\"mitigation\"><strong>应对：</strong>{esc(row[2])}</div><p>source_id: {esc(row[3])}</p></article>"
        for row in rows
    )
    return "<div class=\"risk-grid\">" + cards + "</div>" + lifecycle_evidence_drawer("风险矩阵证据表", ["风险", "触发原因", "应对策略", "source_id"], rows)


def render_lifecycle_market_intel(data_pack: dict[str, Any], analysis_plan: dict[str, Any], fallback_source: str) -> str:
    products = effective_products(data_pack)
    readiness = current_readiness_view(data_pack)
    if readiness.get("supply_blocked"):
        launch_priority = "P1 候选 SKU 先补供应链证据；成本和毛利率恢复前不进入可打样判断。"
    else:
        launch_priority = "P1 可控供应链、低风险触点和 Bundle 组合优先。"
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
            ("首发优先级", launch_priority),
            ("生命周期", "用开箱、7 天、60-90 天复购触点组织 SKU。"),
            ("AOV", "通过新手套装、礼品套装和补给包形成价格台阶。"),
        ],
        "Lifecycle Recommendation",
    )


def appeal_rows(data_pack: dict[str, Any], fallback_source: str) -> list[list[Any]]:
    reviews = customer_visible_reviews(data_pack)
    rows: list[list[Any]] = []
    theme_counts: Counter[str] = Counter()
    for review in reviews:
        theme_counts.update(review_theme_labels(review))
    if not theme_counts:
        theme_counts.update(["性能（Performance）", "隐私信任", "材质手感"])
    for theme, count in theme_counts.most_common(8):
        rows.append(["体验需求" if "性能" in theme or "其他" in theme else "需求主题", theme, count, "转成可感知卖点或设计修复项", fallback_source])
    return rows


def render_target_anchor(data_pack: dict[str, Any], object_value: Any, fallback_source: str) -> str:
    products = effective_products(data_pack)
    anchor = products[0] if products else {}
    sample_summary = f"{len(products)} 个竞品；{len(customer_visible_reviews(data_pack))} 条评论；{len(effective_keywords(data_pack))} 个关键词"
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
    products = effective_products(data_pack)
    data_gaps = data_pack.get("data_gaps") or []
    rows = [
        ["最大机会", max_opportunity, fallback_source],
        ["核心判断", decision, fallback_source],
        ["证据密度", f"{len(customer_visible_reviews(data_pack))} 条评论；{len(data_pack.get('sources') or [])} 类证据记录", fallback_source],
        ["数据覆盖", f"{len(products)} 个去重有效竞品；{len(effective_keywords(data_pack))} 个有效关键词；{len(data_gaps)} 个数据缺口", fallback_source],
    ]
    return (
        f"<div class=\"card focus\"><strong>最大机会：{esc(max_opportunity)}。</strong></div>"
        + "<div class=\"kpi-grid\">"
        + f"<div class=\"kpi\"><div class=\"k\">评论记录数</div><div class=\"v\">{esc(len(customer_visible_reviews(data_pack)))}</div></div>"
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
        + "<div class=\"chart-interpretation\">算法与结论：按需求主题聚合评论信号，优先把高频负面触发点转成页面承诺、产品修复或售后解释。</div>"
        + table(["需求主题", "核心痛点", "评论提及", "动作", "source_id"], rows, "evidence-table sku")
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
    reviews = customer_visible_reviews(data_pack)
    products_by_asin = {
        clean(first(product.get("asin"), product.get("product_asin"), product.get("parent_asin"), product.get("product_id"), default="")).upper(): product
        for product in effective_products(data_pack)
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
        direction = "正面卖点验证" if tone == "joy" else "负面痛点验证"
        next_step = "继续采集同赛道评论原声，并优先补齐带星级、标题和正文的可引用评论。"
        action = "原声数量达标后再生成可执行卖点" if tone == "joy" else "原声数量达标后再生成结构修复动作"
        return (
            f"<article class=\"demand-evidence-card {esc(tone)} diagnostic\">"
            + f"<div class=\"evidence-card-head\"><span>{idx:02d} · {esc(label)}</span><b>评论证据槽位</b></div>"
            + f"<p class=\"review-excerpt-en\"><strong>英文评论短摘：</strong>{esc(next_step)}</p>"
            + f"<p class=\"quote-cn\"><strong>中文洞察：</strong>当前{esc(label)}原声数量不足以生成稳定结论；该卡位只用于提示下一轮采集方向，不写成产品承诺。</p>"
            + "<dl class=\"demand-evidence-meta\">"
            + "<div><dt>需求强度</dt><dd>数据缺口</dd></div>"
            + f"<div><dt>主题</dt><dd>{esc(direction)}</dd></div>"
            + "<div><dt>竞品未满足点</dt><dd>评论原声覆盖不足，不能稳定判断竞品缺口</dd></div>"
            + f"<div><dt>可落地产品机会</dt><dd>{esc(action)}</dd></div>"
            + "</dl>"
            + "<div class=\"quote-origin\">证据锚点：下一轮评论采集</div>"
            + "</article>"
        )

    while len(positive_cards) < 6:
        positive_cards.append(diagnostic_card("joy", "正面反馈", len(positive_cards) + 1))
    while len(negative_cards) < 6:
        negative_cards.append(diagnostic_card("pain", "负面反馈", len(negative_cards) + 1))
    if not rows:
        rows = [["-", "-", "评论证据槽位", "继续采集同赛道评论原声", "评论证据未达到固定展示门槛，需求判断保持 Watch。", "数据缺口", "增加评论抓取轮次", "原声数量达标后再生成需求机会"]]
    evidence_table = table(["评论记录", "星级", "情绪", "英文评论短摘", "中文洞察", "需求强度", "竞品未满足点", "可落地产品机会"], rows, "evidence-table sku")
    return (
        "<div class=\"demand-evidence-grid demand-sentiment-columns\">"
        + "<section class=\"demand-sentiment-column positive\"><div class=\"demand-column-head\"><span>高星证据</span><h3>正面反馈</h3><p>左侧只呈现可转化为卖点、主图和五点表达的高星证据。</p></div>"
        + "".join(positive_cards)
        + "</section>"
        + "<section class=\"demand-sentiment-column negative\"><div class=\"demand-column-head\"><span>低星证据</span><h3>负面反馈</h3><p>右侧只呈现必须转成结构修复、页面承诺和售后方案的低星证据。</p></div>"
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
        "customer_product_position": customer_product_position,
        "effective_keywords": effective_keywords,
        "effective_products": effective_products,
        "effective_reviews": effective_reviews,
        "effective_suppliers": effective_suppliers,
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
        "render_cosmo_alexa_tags": render_cosmo_alexa_tags,
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
    attach_report_label_profile(data_pack, analysis_plan)
    recovery_report: dict[str, Any] | None = None
    if not readiness["acceptance_ready"] and recover:
        recovery_report = recover_readiness(report_dir, "auto", recovery_rounds)
        normalize_data_pack(report_dir)
        readiness = assess_data_readiness(report_dir, "auto")
        write_readiness_json(report_dir / "data" / "normalized" / "data_readiness_report.json", readiness)
        data_pack = load_json(report_dir / "data" / "data_pack.json", {})
        analysis_plan = load_json(report_dir / "analysis" / "analysis_plan.json", {})
        attach_report_label_profile(data_pack, analysis_plan)
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
    cosmo_tags, lifecycle = ensure_generated_analysis_artifacts(report_dir, data_pack, analysis_plan)
    demand_gap = load_json(report_dir / "analysis" / "demand_gap.json", {})
    delivery = load_json(report_dir / "output" / "delivery_result.json", {})
    initial_decision = str(first(delivery.get("decision"), "Watch", default="Watch"))
    readiness_view = report_readiness_view(readiness, data_pack.get("quality") or {}, initial_decision)
    data_pack["report_readiness"] = readiness
    data_pack["report_readiness_view"] = readiness_view

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

    original_decision = str(readiness_view.get("decision") or "Watch")
    rendered_docs, compat_index_html = build_safe_documents(original_decision)
    write_report_views(report_dir, data_pack, analysis_plan, original_decision)
    (report_dir / HTML_REPORTS["index"]).parent.mkdir(parents=True, exist_ok=True)
    (report_dir / HTML_REPORTS["index"]).write_text(rendered_docs["index"], encoding="utf-8")
    (report_dir / COMPAT_INDEX_REPORT).write_text(redact_customer_html(compat_index_html, data_pack), encoding="utf-8")
    invocation_log = run_child_report_renderers(report_dir)
    critic_decision = run_critic_child(report_dir, original_decision, invocation_log)
    decision = str(critic_decision.get("decision") or original_decision)
    decision_view = report_readiness_view(readiness, data_pack.get("quality") or {}, decision)
    decision = str(decision_view.get("decision") or "Watch")
    data_pack["report_readiness_view"] = decision_view
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
    delivery["decision"] = decision if decision in {"Go", "Watch", "No-Go"} else "Watch"
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
    delivery["cosmo_alexa_tags"] = {
        "path": "analysis/cosmo_alexa_tags.json",
        "relation_total": (cosmo_tags.get("coverage_summary") or {}).get("relation_total"),
        "covered_relations": (cosmo_tags.get("coverage_summary") or {}).get("covered_relations"),
    }
    delivery["lifecycle_sku_pool_summary"] = lifecycle_sku_pool_summary(lifecycle, data_pack)
    delivery["data_readiness"] = delivery_readiness_summary(readiness)
    delivery["supplier_quote_gate"] = readiness.get("supplier_quote_gate") or {}
    delivery["asin_display_scope"] = ["competitor_table", "benchmark_sniper", "profit_model", "demand_target_anchor", "sku_reference"]
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
