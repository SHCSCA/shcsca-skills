#!/usr/bin/env python3
"""Build customer-safe view models for the orchestrated market reports."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from customer_safety import client_safe_view_payload, customer_safe_asset_text
from normalize_data_pack import THEME_CN
from site_assets import HTML_REPORT_FILENAMES, INTERACTIVE_FEATURES


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        if isinstance(value, str):
            value = re.sub(r"[^0-9.\-]", "", value)
        return float(value)
    except (TypeError, ValueError):
        return default


def money(value: Any, currency: str = "$") -> str:
    number = as_float(value)
    if not number:
        return "-"
    if currency == "¥":
        return f"¥{number:,.0f}"
    return f"{currency}{number:,.2f}".rstrip("0").rstrip(".")


def first(*values: Any, default: Any = "-") -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return default


def has_cjk(value: Any) -> bool:
    return re.search(r"[\u4e00-\u9fff]", clean(value)) is not None


def review_theme_labels(review: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for value in review.get("themes_cn") or review.get("themes") or []:
        labels.append(str(value))
    raw_text = " ".join(
        str(review.get(key) or "")
        for key in ["text", "title", "translated_text", "summary", "content", "body"]
    ).lower()
    for theme, label in THEME_CN.items():
        if theme in raw_text and label not in labels:
            labels.append(label)
    if "隐私" in clean(review) and "隐私/信任" not in labels:
        labels.append("隐私/信任")
    return labels[:5] or ["体验反馈"]


def customer_review_summary(review: dict[str, Any], limit: int = 180) -> str:
    for key in ["summary_cn", "translated_text", "summary"]:
        value = clean(review.get(key))
        if value and has_cjk(value):
            return value[:limit]
    text = " ".join(clean(review.get(key)) for key in ["title", "text", "content", "body"]).lower()
    signals: list[str] = []
    if any(token in text for token in ["privacy", "data", "record", "policy"]):
        signals.append("隐私政策和数据使用说明不够清晰")
    if any(token in text for token in ["stop", "broken", "not working", "battery", "charge"]):
        signals.append("短期使用后出现失效或稳定性问题")
    if any(token in text for token in ["kid", "child", "gift", "sleep", "bed"]):
        signals.append("购买场景集中在儿童陪伴、礼物和睡眠安抚")
    if any(token in text for token in ["voice", "sound", "chat", "ai"]):
        signals.append("用户关注语音互动和智能陪伴体验")
    if not signals:
        signals.append("评论反映了体验落差，需要转成可验证的卖点和风险清单")
    return "；".join(signals)[:limit]


def review_sentiment_label(review: dict[str, Any]) -> str:
    rating = as_float(review.get("rating"), 0)
    if rating and rating <= 2:
        return "负面触发点"
    if rating and rating >= 4:
        return "正向卖点"
    return "中性反馈"


def customer_product_label(product: dict[str, Any]) -> str:
    for key in ["title_cn", "positioning_cn", "segment_cn"]:
        value = clean(product.get(key))
        if value and has_cjk(value):
            return value[:80]
    segment = clean(product.get("segment"))
    if segment:
        return f"{segment} 竞品记录"
    return "竞品记录"


def product_sales(product: dict[str, Any]) -> Any:
    return first(product.get("estimated_monthly_sales"), product.get("monthly_sales"), product.get("sales"), default=0)


def product_price(product: dict[str, Any]) -> Any:
    return first(product.get("price"), product.get("current_price"), product.get("buy_box_price"), default=0)


def relevant_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(products, key=lambda item: (as_float(product_sales(item)), as_float(item.get("review_count"))), reverse=True)


def price_band(price: Any) -> str:
    value = as_float(price)
    if value <= 0:
        return "未知"
    if value < 20:
        return "<$20"
    if value < 50:
        return "$20-$49"
    if value < 100:
        return "$50-$99"
    return "$100+"


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


def confidence_level(data_pack: dict[str, Any], analysis_plan: dict[str, Any] | None = None) -> str:
    score = as_float((data_pack.get("quality") or {}).get("overall_score"), 0)
    if score >= 0.82:
        return "高"
    if score >= 0.62:
        return "中高"
    return "中"


def lifecycle_skus(data_pack: dict[str, Any], lifecycle: dict[str, Any], fallback_source: str) -> list[dict[str, Any]]:
    explicit = lifecycle.get("skus")
    if isinstance(explicit, list) and explicit:
        return [item for item in explicit if isinstance(item, dict)]
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
                "name": f"{customer_product_label(product)} 对标配件",
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


def readiness_summary(readiness: dict[str, Any] | None) -> dict[str, Any]:
    readiness = readiness or {}
    return {
        "acceptance_ready": readiness.get("acceptance_ready"),
        "sample_class": readiness.get("sample_class"),
        "depth": readiness.get("depth"),
        "blocking_gap_count": len(readiness.get("blocking_gaps") or []),
        "warning_count": len(readiness.get("warnings") or []),
        "counts": readiness.get("counts") or {},
        "supplier_quote_gate": readiness.get("supplier_quote_gate") or {},
    }


def build_site_data(data_pack: dict[str, Any], analysis_plan: dict[str, Any], decision: str, child_skills: dict[str, str], readiness: dict[str, Any] | None = None) -> dict[str, Any]:
    normalization = data_pack.get("normalization") or data_pack.get("cleaning_summary") or {}
    return {
        "report_files": {key: filename for key, filename in HTML_REPORT_FILENAMES.items()},
        "child_skills": child_skills,
        "interactive_features": INTERACTIVE_FEATURES,
        "decision": decision,
        "readiness": readiness_summary(readiness),
        "quality": data_pack.get("quality") or {},
        "cleaning_summary": {
            "deduped": normalization.get("deduped"),
            "before_counts": normalization.get("before_counts") or {},
            "after_counts": normalization.get("after_counts") or {},
            "removed_counts": normalization.get("removed_counts") or {},
            "cross_validated_counts": normalization.get("cross_validated_counts") or {},
        },
        "coverage": {
            "products": len(data_pack.get("products") or []),
            "keywords": len(data_pack.get("keywords") or []),
            "reviews": len(data_pack.get("reviews") or []),
            "tiktok_products": len(data_pack.get("tiktok_products") or []),
            "suppliers": len(data_pack.get("suppliers") or []),
            "web_documents": len(data_pack.get("web_documents") or []),
            "method_chain": len(analysis_plan.get("method_chain") or []),
        },
        "data_gaps": [customer_safe_asset_text(gap.get("gap") if isinstance(gap, dict) else gap) for gap in (data_pack.get("data_gaps") or [])],
    }


def view_limitations(data_pack: dict[str, Any], analysis_plan: dict[str, Any]) -> list[str]:
    limitations: list[str] = []
    for gap in data_pack.get("data_gaps") or []:
        if isinstance(gap, dict):
            limitations.append(customer_safe_asset_text(first(gap.get("reason"), gap.get("impact"), gap.get("gap"), default="")))
        else:
            limitations.append(customer_safe_asset_text(gap))
    limitations.extend(customer_safe_asset_text(item) for item in (analysis_plan.get("limitations") or []))
    return [item for item in limitations if item]


def safe_kpis(data_pack: dict[str, Any], decision: str) -> list[dict[str, Any]]:
    category = (data_pack.get("categories") or [{}])[0]
    keywords = [kw for kw in data_pack.get("keywords") or [] if kw.get("monthly_search_volume")]
    keywords = sorted(keywords, key=lambda kw: as_float(kw.get("monthly_search_volume"), 0), reverse=True)
    return [
        {"label": "核心判断", "value": decision, "subtext": "Go / Watch / No-Go"},
        {"label": "Top100 估算月销量", "value": category.get("top100_estimated_monthly_units"), "subtext": "第三方类目代理指标"},
        {"label": "关键词记录", "value": len(data_pack.get("keywords") or []), "subtext": "归一化后数据"},
        {"label": "评论记录", "value": len(data_pack.get("reviews") or []), "subtext": "客户版只展示中文摘要"},
        {"label": "竞品记录", "value": len(data_pack.get("products") or []), "subtext": "Amazon 产品池"},
        {"label": "供应端记录", "value": len(data_pack.get("suppliers") or []), "subtext": "1688 参考"},
        {"label": "TikTok 商品", "value": len(data_pack.get("tiktok_products") or []), "subtext": "内容端信号"},
        {"label": "最大关键词月搜索", "value": keywords[0].get("monthly_search_volume") if keywords else None, "subtext": keywords[0].get("keyword_cn") if keywords else "需增加关键词采集"},
    ]


def build_report_views(data_pack: dict[str, Any], analysis_plan: dict[str, Any], decision: str) -> dict[str, dict[str, Any]]:
    products = relevant_products(data_pack.get("products") or [])
    reviews = data_pack.get("reviews") or []
    suppliers = data_pack.get("suppliers") or []
    keywords = data_pack.get("keywords") or []
    theme_counts: Counter[str] = Counter()
    star_counts: Counter[str] = Counter()
    segment_counts: Counter[str] = Counter()
    for review in reviews:
        theme_counts.update(review_theme_labels(review))
        rating = int(as_float(review.get("rating"), 0))
        if rating:
            star_counts[f"{rating}星"] += 1
    for product in products:
        segment_counts[first(product.get("segment_cn"), product.get("segment"), default="未分层")] += 1

    limitations = view_limitations(data_pack, analysis_plan)
    common = {
        "evidence_strength": confidence_level(data_pack, analysis_plan),
        "sample_coverage": {
            "products": len(products),
            "keywords": len(keywords),
            "reviews": len(reviews),
            "tiktok_products": len(data_pack.get("tiktok_products") or []),
            "tiktok_videos": len(data_pack.get("tiktok_videos") or []),
            "suppliers": len(suppliers),
            "web_documents": len(data_pack.get("web_documents") or []),
        },
        "limitations": limitations,
        "client_safe_text": True,
    }
    market_rows = [
        {
            "segment": first(product.get("segment_cn"), product.get("segment"), default="未分层"),
            "title_cn": customer_product_label(product),
            "brand": product.get("brand"),
            "price": product_price(product),
            "monthly_sales": product_sales(product),
            "rating": product.get("rating"),
            "review_count": product.get("review_count"),
            "positioning_cn": product.get("positioning_cn"),
        }
        for product in products[:40]
    ]
    demand_quotes = [
        {
            "rating": review.get("rating"),
            "sentiment": review_sentiment_label(review),
            "summary_cn": customer_review_summary(review, 180),
            "themes_cn": review_theme_labels(review),
        }
        for review in reviews[:80]
    ]
    lifecycle_sku_rows = lifecycle_skus(data_pack, {}, primary_source_id(data_pack))
    return {
        "market_depth_view": {
            **common,
            "kpis": safe_kpis(data_pack, decision),
            "charts": {
                "segment_counts": [{"label": key, "value": value} for key, value in segment_counts.most_common()],
                "price_bands": [{"label": key, "value": value} for key, value in Counter(price_band(product_price(product)) for product in products).items()],
            },
            "tables": {"competitors": market_rows},
            "cards": {"opportunities": [{"title": row.get("title_cn"), "meaning": row.get("positioning_cn")} for row in market_rows[:8]]},
        },
        "demand_gap_view": {
            **common,
            "kpis": safe_kpis(data_pack, decision),
            "charts": {
                "appeals": [{"label": key, "value": value} for key, value in theme_counts.most_common()],
                "star_distribution": [{"label": key, "value": value} for key, value in sorted(star_counts.items())],
            },
            "tables": {"quotes": demand_quotes},
            "cards": {"top_pains": [{"theme": key, "mentions": value} for key, value in theme_counts.most_common(8)]},
        },
        "lifecycle_strategy_view": {
            **common,
            "kpis": safe_kpis(data_pack, decision),
            "charts": {
                "sku_types": [{"label": key, "value": value} for key, value in Counter(str(sku.get("type", "A")).upper() for sku in lifecycle_sku_rows).items()]
            },
            "tables": {"sku_pool": lifecycle_sku_rows},
            "cards": {"bundles": [{"name": "新手启航套装", "purpose": "降低首购疑虑"}, {"name": "豪华礼品套装", "purpose": "提升 AOV"}]},
        },
    }


def write_report_views(report_dir: Path, data_pack: dict[str, Any], analysis_plan: dict[str, Any], decision: str) -> None:
    views = build_report_views(data_pack, analysis_plan, decision)
    analysis_dir = report_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in views.items():
        (analysis_dir / f"{name}.json").write_text(json.dumps(client_safe_view_payload(payload), ensure_ascii=False, indent=2), encoding="utf-8")
