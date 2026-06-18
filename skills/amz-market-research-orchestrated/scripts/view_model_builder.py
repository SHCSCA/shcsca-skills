#!/usr/bin/env python3
"""Build customer-safe view models for the orchestrated market reports."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from customer_safety import client_safe_view_payload, customer_safe_asset_text
from html_components import relevant_products as filter_relevant_products
from normalize_data_pack import THEME_CN
from site_assets import HTML_REPORT_FILENAMES, INTERACTIVE_FEATURES


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def effective_records(data_pack: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = data_pack.get(f"effective_{key}")
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    value = data_pack.get(key)
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


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


def review_context_family(review: dict[str, Any]) -> str:
    text = " ".join(clean(review.get(key)) for key in ["title", "text", "content", "body", "summary_cn", "translated_text"]).casefold()
    if any(token in text for token in ["cupping", "suction", "massage", "massager", "lymphatic", "cellulite", "gua sha", "拔罐", "吸力", "负压", "热敷", "红光", "按摩", "刮痧"]):
        return "therapy_massager"
    if any(token in text for token in ["light", "brightness", "rgb", "lamp", "lumens", "照明", "灯", "亮度"]):
        return "lighting"
    return "generic"


def customer_review_summary(review: dict[str, Any], limit: int = 180) -> str:
    rating = as_float(review.get("rating"), 0)
    text = " ".join(clean(review.get(key)) for key in ["title", "text", "content", "body"]).lower()
    context = review_context_family(review)
    negative_summary_phrases = ["没有达到预期", "需要加强", "出现失效", "信任下降", "不够清晰", "稳定性问题"]
    for key in ["summary_cn", "translated_text", "summary"]:
        value = clean(review.get(key))
        if value and has_cjk(value):
            if rating >= 4 and any(phrase in value for phrase in negative_summary_phrases):
                break
            return value[:limit]
    if rating >= 4:
        positive_signals: list[str] = []
        if context == "therapy_massager":
            if any(token in text for token in ["heat", "warm", "red light", "therapy", "红光", "热敷"]):
                positive_signals.append("热敷和红光理疗体验获得正向反馈")
            if any(token in text for token in ["suction", "cup", "cupping", "pressure", "吸力", "负压"]):
                positive_signals.append("吸力和拔罐稳定性获得正向反馈")
            if any(token in text for token in ["pain", "relief", "muscle", "back", "sore", "疼痛", "酸痛"]):
                positive_signals.append("疼痛缓解和肌肉放松效果获得正向反馈")
            if any(token in text for token in ["easy", "simple", "button", "use", "操作"]):
                positive_signals.append("操作和上手体验获得正向反馈")
        else:
            if context == "lighting" and any(token in text for token in ["bright", "brightness", "light", "color", "rgb"]):
                positive_signals.append("亮度和灯效获得正向反馈")
            if any(token in text for token in ["easy", "install", "setup", "stick", "adhesive"]):
                positive_signals.append("安装和上手体验获得正向反馈")
            if context == "lighting" and any(token in text for token in ["motion", "sensor", "detect"]):
                positive_signals.append("感应触发体验获得正向反馈")
        if any(token in text for token in ["battery", "charge", "charging", "last", "long time"]):
            positive_signals.append("续航和充电便利性获得正向反馈")
        if any(token in text for token in ["love", "great", "works well", "perfect", "recommend"]):
            positive_signals.append("整体使用满意度形成正向反馈")
        fallback = "用户正向反馈集中在理疗效果、吸力稳定和操作便利" if context == "therapy_massager" else "用户正向反馈集中在功能效果、安装便利和场景适配"
        return "；".join(dict.fromkeys(positive_signals or [fallback]))[:limit]
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


SEGMENT_LABEL_RULES = [
    ("热敷红光电动拔罐器", ["red light cupping", "heated cupping", "cupping massager with heat", "red light", "heat and suction", "热敷", "红光"]),
    ("电动拔罐按摩器", ["electric cupping", "smart cupping", "cupping massager", "vacuum cupping", "拔罐", "负压"]),
    ("筋膜放松拔罐套装", ["myofascial", "cupping therapy set", "multi-sized vacuum cup", "therapy set", "筋膜", "套装"]),
    ("淋巴引流负压按摩器", ["lymphatic", "cellulite", "drainage massager", "淋巴", "美体", "橘皮"]),
    ("弹出式地面盲棚", ["hunting blind", "ground blind", "deer blind", "pop up blind", "地面盲棚", "狩猎棚"]),
    ("橱柜感应灯", ["under cabinet", "cabinet light", "motion sensor", "puck light", "磁吸", "橱柜", "感应"]),
    ("RGB 灯带", ["rgbic", "rgb led strip", "led strip", "strip lights", "light strip", "灯带"]),
    ("智能灯泡", ["smart bulb", "a19", "light bulb", "灯泡"]),
    ("氛围灯", ["ambient", "table lamp", "night light", "sunset", "床头", "夜灯", "氛围"]),
    ("户外感应灯", ["outdoor", "solar", "flood light", "security light", "wall sconce", "户外", "太阳能", "壁灯"]),
]


def infer_segment_cn(product: dict[str, Any]) -> str:
    for key in ["segment_cn", "segment", "category_cn"]:
        value = clean(product.get(key))
        if value and has_cjk(value) and value not in {"未分层", "未知"}:
            return value
    text = " ".join(clean(product.get(key)).lower() for key in ["title", "title_cn", "category", "segment"])
    for label, needles in SEGMENT_LABEL_RULES:
        if any(needle in text for needle in needles):
            return label
    return ""


def customer_safe_brand(value: Any) -> str:
    brand = clean(value)
    if not brand or brand in {"竞品记录", "未命名竞品"}:
        return ""
    title_like_terms = ["electric", "cupping", "massager", "therapy", "choose the color", "with ", " for "]
    if len(brand) > 24 or any(term in brand.casefold() for term in title_like_terms):
        return ""
    return brand


def customer_product_label(product: dict[str, Any]) -> str:
    brand = customer_safe_brand(product.get("brand"))
    segment = infer_segment_cn(product)
    if brand and segment:
        return f"{brand} {segment}"[:80]
    for key in ["title_cn", "positioning_cn", "segment_cn"]:
        value = clean(product.get(key))
        if value and has_cjk(value) and "竞品记录" not in value and value not in {"未分层", "未知"}:
            return value[:80]
    if segment:
        return f"{segment}竞品"[:80]
    title = clean(product.get("title"))
    if brand and title:
        return f"{brand} 竞品"[:80]
    return brand or "目标类目竞品"


def product_sales(product: dict[str, Any]) -> Any:
    return first(product.get("estimated_monthly_sales"), product.get("monthly_sales"), product.get("sales"), default=0)


def product_price(product: dict[str, Any]) -> Any:
    return first(product.get("price"), product.get("current_price"), product.get("buy_box_price"), default=0)


def relevant_products(products: list[dict[str, Any]], research_object: Any = None) -> list[dict[str, Any]]:
    filtered = filter_relevant_products(products, research_object)
    return sorted(filtered, key=lambda item: (as_float(product_sales(item)), as_float(item.get("review_count"))), reverse=True)


def keyword_is_customer_relevant(keyword: dict[str, Any], research_object: Any = None) -> bool:
    keyword_cn = clean(keyword.get("keyword_cn"))
    keyword_raw = clean(keyword.get("keyword"))
    combined = f"{keyword_raw} {keyword_cn} {clean(keyword.get('intent_cn'))}".casefold()
    if not keyword_raw and not keyword_cn:
        return False
    if keyword_cn.startswith("未映射关键词") or keyword_cn.startswith("污染关键词"):
        return False
    off_topic_terms = [
        "stanley cup",
        "owala",
        "water bottle",
        "protein",
        "energy drink",
        "camera",
        "doorbell",
        "paper towel",
        "toilet paper",
        "theragun",
    ]
    if any(term in combined for term in off_topic_terms):
        return False
    if keyword.get("is_core_relevant") or keyword.get("relevance_cn") == "高相关":
        return True
    if has_cjk(keyword_cn) and keyword_cn.casefold() != keyword_raw.casefold():
        return True
    if isinstance(research_object, dict):
        research_text = " ".join([clean(research_object.get("value")), *[clean(item) for item in research_object.get("seed_keywords") or []]]).casefold()
    else:
        research_text = clean(research_object).casefold()
    research_tokens = {token for token in re.split(r"[^a-z0-9\u4e00-\u9fff]+", research_text) if len(token) >= 3}
    keyword_tokens = {token for token in re.split(r"[^a-z0-9\u4e00-\u9fff]+", combined) if len(token) >= 3}
    return bool(research_tokens and keyword_tokens and research_tokens & keyword_tokens)


def customer_relevant_keywords(data_pack: dict[str, Any]) -> list[dict[str, Any]]:
    keywords = effective_records(data_pack, "keywords")
    research_object = data_pack.get("research_object")
    filtered = [kw for kw in keywords if keyword_is_customer_relevant(kw, research_object)]
    return filtered


def keyword_customer_intent_key(keyword: dict[str, Any]) -> str:
    label = clean(first(keyword.get("customer_label_cn"), keyword.get("intent_cn"), keyword.get("keyword_cn"), default=""))
    if not label:
        label = clean(keyword.get("keyword"))
    return re.sub(r"\s+", " ", label).casefold()


def keyword_customer_intent_count(keywords: list[dict[str, Any]]) -> int:
    return len({key for key in (keyword_customer_intent_key(keyword) for keyword in keywords) if key})


def public_delivery_result_summary(delivery_result: dict[str, Any]) -> dict[str, Any]:
    readiness = delivery_result.get("data_readiness") if isinstance(delivery_result.get("data_readiness"), dict) else {}
    return client_safe_view_payload(
        {
            "status": delivery_result.get("status"),
            "decision": delivery_result.get("decision"),
            "delivery_mode": delivery_result.get("delivery_mode") or readiness.get("delivery_mode"),
            "overall_pass": delivery_result.get("overall_pass"),
            "full_acceptance_pass": delivery_result.get("full_acceptance_pass"),
            "diagnostic_delivery_pass": delivery_result.get("diagnostic_delivery_pass"),
            "data_readiness": {
                "decision": readiness.get("decision"),
                "delivery_mode": readiness.get("delivery_mode"),
                "evidence_grade": readiness.get("evidence_grade"),
                "score": readiness.get("score"),
                "acceptance_ready": readiness.get("acceptance_ready"),
                "partial_report_ready": readiness.get("partial_report_ready"),
                "supply_conclusion_blocked": readiness.get("supply_conclusion_blocked"),
            },
        }
    )


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
    readiness_view = view_readiness_state(data_pack)
    if readiness_view.get("evidence_strength"):
        return readiness_view["evidence_strength"]
    score = as_float((data_pack.get("quality") or {}).get("overall_score"), 0)
    if score >= 0.82:
        return "高"
    if score >= 0.62:
        return "中高"
    return "中"


def view_readiness_state(data_pack: dict[str, Any], decision: str | None = None) -> dict[str, Any]:
    view = data_pack.get("report_readiness_view")
    if isinstance(view, dict) and view:
        return {
            "delivery_state": clean(first(view.get("delivery_state"), view.get("status"), default="完整可交付")),
            "decision": clean(first(view.get("decision"), decision, default="Watch")),
            "evidence_strength": clean(view.get("evidence_strength")),
            "blocking_gap_count": len(view.get("blocking_gaps") or []),
        }
    readiness = data_pack.get("report_readiness")
    if isinstance(readiness, dict) and readiness:
        acceptance_ready = readiness.get("acceptance_ready") is True
        partial_ready = readiness.get("partial_report_ready") is True
        if acceptance_ready:
            delivery_state = "完整可交付"
            evidence_strength = ""
        elif partial_ready:
            delivery_state = "诊断交付"
            evidence_strength = "中 / 诊断交付"
        else:
            delivery_state = "阻断交付"
            evidence_strength = "低 / 阻断交付"
        return {
            "delivery_state": delivery_state,
            "decision": clean(decision) or "Watch",
            "evidence_strength": evidence_strength,
            "blocking_gap_count": len(readiness.get("blocking_gaps") or []),
        }
    return {"delivery_state": "完整可交付", "decision": clean(decision) or "Watch", "evidence_strength": "", "blocking_gap_count": 0}


def lifecycle_skus(data_pack: dict[str, Any], lifecycle: dict[str, Any], fallback_source: str) -> list[dict[str, Any]]:
    lifecycle = lifecycle or data_pack.get("lifecycle_strategy") or {}
    candidate_pool = lifecycle.get("sku_candidate_pool")
    if isinstance(candidate_pool, list) and candidate_pool:
        return [item for item in candidate_pool if isinstance(item, dict)]
    recommended = lifecycle.get("recommended_skus")
    if isinstance(recommended, list) and recommended:
        return [item for item in recommended if isinstance(item, dict)]
    explicit = lifecycle.get("skus")
    if isinstance(explicit, list) and explicit:
        return [item for item in explicit if isinstance(item, dict)]
    products = relevant_products(data_pack.get("effective_products") or data_pack.get("products") or [], data_pack.get("research_object"))
    suppliers = data_pack.get("effective_suppliers") or data_pack.get("suppliers") or []
    rows: list[dict[str, Any]] = []
    type_labels = ["A", "B", "C", "D"]
    suffix_by_type = {"A": "基础验证款", "B": "场景升级款", "C": "配件补位款", "D": "维护复购款"}
    for idx, product in enumerate(products[:40]):
        sku_type = type_labels[idx % len(type_labels)]
        segment = infer_segment_cn(product) or customer_product_label(product)
        price = as_float(product_price(product), 0)
        rows.append(
            {
                "name": f"{segment} {suffix_by_type[sku_type]}",
                "stage": "竞品驱动候选",
                "type": sku_type,
                "type_label_cn": suffix_by_type[sku_type],
                "target_segment": segment,
                "reference_competitor": customer_product_label(product),
                "reference_asin": clean(product.get("asin")),
                "reference_price": money(price),
                "reference_rating": product.get("rating"),
                "reference_reviews": product.get("review_count"),
                "reference_sales": product_sales(product),
                "price": money(price or 19),
                "supply": "按竞品差异打样",
                "phase": "P1" if idx < 16 else "P2",
                "priority": max(45, min(96, int(60 + as_float(product_sales(product), 0) / 120 + as_float(product.get("rating"), 0) * 3))),
                "ecosystem_path": {"A": "关联度", "B": "场景", "C": "消耗", "D": "维护"}[sku_type],
                "ecosystem_segment": segment,
                "source_id": source_ids_for(product, fallback_source),
            }
        )
    for idx, supplier in enumerate(suppliers[:20]):
        title = clean(first(supplier.get("title"), supplier.get("Title"), supplier.get("name"), default="供应端相似成品"))
        if not title:
            continue
        sku_type = type_labels[(idx + len(rows)) % len(type_labels)]
        rows.append(
            {
                "name": f"{title[:28]} {suffix_by_type[sku_type]}",
                "stage": "供应链验证",
                "type": sku_type,
                "type_label_cn": suffix_by_type[sku_type],
                "target_segment": title[:18],
                "reference_competitor": "供应端相似成品",
                "price": money(first(supplier.get("price"), supplier.get("price_rmb"), supplier.get("Price"), default=12), "¥"),
                "supply": title,
                "phase": "P2",
                "priority": max(42, 68 - idx),
                "ecosystem_path": {"A": "关联度", "B": "场景", "C": "消耗", "D": "维护"}[sku_type],
                "ecosystem_segment": title[:18],
                "source_id": source_ids_for(supplier, fallback_source),
            }
        )
    return rows


def readiness_summary(readiness: dict[str, Any] | None) -> dict[str, Any]:
    readiness = readiness or {}
    supplier_quality = dict(readiness.get("supplier_quality_gate") or {})
    missing_fields = supplier_quality.pop("missing_documented_required_fields", [])
    supplier_quality.pop("observed_fields", None)
    if missing_fields:
        supplier_quality["field_diagnostic"] = "当前1688响应缺少商品标题和商品链接字段"
    return {
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


def customer_quality_label(quality: dict[str, Any]) -> dict[str, Any]:
    payload = dict(quality or {})
    grade = clean(payload.get("grade"))
    grade_map = {
        "ready_for_normalization": "可用于方向判断，需供应链复核",
        "low_confidence_watch": "证据不足，建议观察",
        "medium_confidence": "中等置信，可继续验证",
    }
    if grade:
        payload["grade"] = grade_map.get(grade, customer_safe_asset_text(grade))
    return client_safe_view_payload(payload)


GAP_MODULE_LABELS = {
    "competitor_pool_depth": "竞品池深度",
    "competitor_pool_relevance": "竞品相关性",
    "competitor_relevance_filter_final": "竞品相关性",
    "amazon_competitor_images": "竞品图片覆盖",
    "market_segment_depth": "细分赛道深度",
    "segment_gate": "细分赛道拆分",
    "keyword_sample_depth": "关键词数据记录深度",
    "keyword_customer_intent_duplicate_ratio": "关键词意图去重",
    "keyword_mapping_quality": "关键词中文映射",
    "supplier_quote_depth": "1688 报价深度",
    "supplier_quote_quality": "1688 报价质量",
    "supplier_relevance_filter": "1688 报价相关性",
    "tiktok_signal_depth": "TikTok 趋势信号",
    "web_evidence_depth": "公开网页交叉验证",
    "amazon_product_enrichment": "Amazon 产品详情补强",
}


def customer_gap_module_label(value: Any) -> str:
    raw = clean(value)
    if not raw:
        return "数据门禁"
    return GAP_MODULE_LABELS.get(raw, customer_safe_asset_text(raw))


def customer_safe_readiness_view(view: dict[str, Any]) -> dict[str, Any]:
    payload = dict(view or {})
    gaps: list[dict[str, Any]] = []
    for gap in payload.get("blocking_gaps") or []:
        if not isinstance(gap, dict):
            continue
        gaps.append(
            {
                "module": customer_gap_module_label(gap.get("module")),
                "reason": customer_safe_asset_text(first(gap.get("reason"), gap.get("gap"), default="当前门禁未通过")),
                "impact": customer_safe_asset_text(first(gap.get("impact"), default="不能输出对应模块的完整结论")),
                "next_step": customer_safe_asset_text(first(gap.get("next_step"), gap.get("next_action"), default="补齐数据后重新渲染")),
            }
        )
    payload["blocking_gaps"] = gaps
    return client_safe_view_payload(payload)


CUSTOMER_GAP_POLLUTION_TERMS = [
    "stanley cup",
    "owala",
    "water bottle",
    "户外感应灯",
    "氛围灯",
    "橱柜感应灯",
    "rgb 灯带",
    "智能灯泡",
    "狩猎",
    "地面盲棚",
    "快速搭建",
    "清晨/傍晚观察",
]


def customer_visible_data_gap(gap: Any) -> str:
    raw = gap.get("gap") if isinstance(gap, dict) else gap
    text = customer_safe_asset_text(raw)
    lowered = text.casefold()
    if not text:
        return ""
    if "filtered" in lowered and any(term in lowered for term in ["non-core", "incomplete", "low-price", "outlier", "1688 rows"]):
        return "采集数据已完成相关性清洗，低相关、字段不完整或价格异常记录已转入审计文件；客户侧仅使用通过门禁的数据。"
    if "未映射关键词" in text or any(term in lowered for term in ["stanley cup", "owala", "water bottle"]):
        return "关键词数据包含离题或未映射记录，已转入审计文件；客户侧不用于市场规模、赛道判断或推荐结论。"
    if any(term.casefold() in lowered for term in CUSTOMER_GAP_POLLUTION_TERMS):
        return "赛道拆分诊断发现跨类目污染，已转入审计文件；请按当前研究对象补采有效竞品并重新归一化。"
    return text


def is_valid_customer_image_url(value: Any) -> bool:
    text = clean(value)
    if not text or re.search(r"[\s\x00-\x1f\x7f]", text):
        return False
    try:
        parsed = urlparse(text)
    except ValueError:
        return False
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return False
    host = parsed.netloc.casefold()
    if any(domain in host for domain in ("alicdn.com", "1688.com", "taobao.com", "tmall.com")):
        return False
    return any(domain in host for domain in ("media-amazon.com", "ssl-images-amazon.com", "images-amazon.com", "amazon.com"))


def customer_product_image_url(product: dict[str, Any]) -> str:
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
        if is_valid_customer_image_url(candidate):
            return clean(candidate)
    return ""


def customer_visible_image_coverage_gap(data_pack: dict[str, Any]) -> str:
    products = relevant_products(effective_records(data_pack, "products"), data_pack.get("research_object"))
    total = len(products)
    with_image = sum(1 for product in products if customer_product_image_url(product))
    if not total:
        return "Amazon 竞品图片覆盖不足：当前客户可见有效竞品池为空，不能展示竞品全景和标杆竞品图片。"
    ratio = with_image / total
    return f"Amazon 竞品图片覆盖不足：当前有效竞品池 {total} 个，其中 {with_image} 个返回可展示主图 URL，图片覆盖率 {ratio:.0%}。"


def supplier_gap_resolved_by_readiness(gap: Any, readiness: dict[str, Any] | None) -> bool:
    if not isinstance(gap, dict) or not isinstance(readiness, dict):
        return False
    module = clean(first(gap.get("module"), gap.get("type"), default=""))
    if module not in {"supplier_quote_quality", "supplier_quote_depth"}:
        return False
    supplier_quote_gate = readiness.get("supplier_quote_gate") or {}
    supplier_quality_gate = readiness.get("supplier_quality_gate") or {}
    quality_passed = (
        supplier_quality_gate.get("customer_visible_passed")
        if "customer_visible_passed" in supplier_quality_gate
        else supplier_quality_gate.get("passed")
    )
    return bool(
        readiness.get("supply_conclusion_blocked") is not True
        and supplier_quote_gate.get("passed")
        and quality_passed
    )


def customer_visible_data_gaps(data_pack: dict[str, Any], readiness: dict[str, Any] | None = None) -> list[str]:
    messages: list[str] = []
    for gap in data_pack.get("data_gaps") or []:
        if supplier_gap_resolved_by_readiness(gap, readiness):
            continue
        if isinstance(gap, dict) and clean(first(gap.get("type"), gap.get("module"), default="")) == "competitor_image_coverage":
            messages.append(customer_visible_image_coverage_gap(data_pack))
            continue
        message = customer_visible_data_gap(gap)
        if message:
            messages.append(message)
    return unique_customer_messages(messages)


def unique_customer_messages(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = customer_safe_asset_text(item)
        if text and text not in seen:
            result.append(text)
            seen.add(text)
    return result


def decision_cockpit(data_pack: dict[str, Any], analysis_plan: dict[str, Any], decision: str, readiness: dict[str, Any] | None) -> dict[str, Any]:
    readiness = readiness or {}
    blocking = readiness.get("blocking_gaps") or []
    warnings = readiness.get("warnings") or []
    counts = readiness.get("counts") or {}
    supplier_quality = readiness.get("supplier_quality_gate") or {}
    competitor_gate = readiness.get("competitor_gate") or {}
    segment_gate = readiness.get("segment_gate") or {}
    if blocking:
        next_action = "先补齐阻断项，再生成完整客户报告。"
    elif warnings:
        next_action = "可用于方向判断，但关键风险需在打样和二次采集中复核。"
    else:
        next_action = "可进入客户版完整报告和小批量验证。"
    return {
        "核心结论": customer_safe_asset_text(decision),
        "当前阻断项": [customer_safe_asset_text(first(item.get("reason"), item.get("module"), default="需复核")) for item in blocking],
        "风险提醒": [customer_safe_asset_text(first(item.get("impact"), item.get("module"), default="需复核")) for item in warnings],
        "数据完整度": {
            "有效竞品": counts.get("valid_competitors", counts.get("products", 0)),
            "关键词": counts.get("keywords", len(data_pack.get("keywords") or [])),
            "评论": counts.get("reviews", len(data_pack.get("reviews") or [])),
            "1688有效报价": counts.get("valid_supplier_quotes", 0),
            "细分赛道": counts.get("market_segments", 0),
        },
        "门禁状态": {
            "竞品池": "通过" if competitor_gate.get("passed") else "需补采",
            "赛道拆分": "通过" if segment_gate.get("passed", True) else "需拆分",
            "1688质量": "通过" if supplier_quality.get("passed") else "需复核",
        },
        "下一步动作": next_action,
    }


def build_site_data(
    data_pack: dict[str, Any],
    analysis_plan: dict[str, Any],
    decision: str,
    child_skills: dict[str, str],
    readiness: dict[str, Any] | None = None,
    delivery_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalization = data_pack.get("normalization") or data_pack.get("cleaning_summary") or {}
    readiness_counts = (readiness or {}).get("counts") or {}
    research_object = data_pack.get("research_object")
    effective_counts = {
        "products": len(relevant_products(effective_records(data_pack, "products"), research_object)),
        "keywords": len(effective_records(data_pack, "keywords")),
        "reviews": len(effective_records(data_pack, "reviews")),
        "suppliers": len(effective_records(data_pack, "suppliers")),
    }
    payload = {
        "report_files": {key: filename for key, filename in HTML_REPORT_FILENAMES.items()},
        "child_skills": child_skills,
        "interactive_features": INTERACTIVE_FEATURES,
        "decision": decision,
        "report_readiness_view": customer_safe_readiness_view(data_pack.get("report_readiness_view") or {}),
        "readiness": readiness_summary(readiness),
        "quality": customer_quality_label(data_pack.get("quality") or {}),
        "decision_cockpit": decision_cockpit(data_pack, analysis_plan, decision, readiness),
        "cleaning_summary": {
            "deduped": normalization.get("deduped"),
            "before_counts": normalization.get("before_counts") or {},
            "after_counts": normalization.get("after_counts") or {},
            "removed_counts": normalization.get("removed_counts") or {},
            "cross_validated_counts": normalization.get("cross_validated_counts") or {},
            "effective_counts": effective_counts,
        },
        "coverage": {
            "products": readiness_counts.get("products", effective_counts["products"]),
            "keywords": readiness_counts.get("keywords", effective_counts["keywords"]),
            "reviews": readiness_counts.get("reviews", effective_counts["reviews"]),
            "tiktok_products": len(data_pack.get("tiktok_products") or []),
            "tiktok_videos": len(data_pack.get("tiktok_videos") or []),
            "tiktok_authors": len(data_pack.get("tiktok_authors") or []),
            "suppliers": readiness_counts.get("suppliers", effective_counts["suppliers"]),
            "web_documents": len(data_pack.get("web_documents") or []),
            "method_chain": len(analysis_plan.get("method_chain") or []),
        },
        "data_gaps": customer_visible_data_gaps(data_pack, readiness),
    }
    if delivery_result:
        payload["delivery_result"] = public_delivery_result_summary(delivery_result)
    return payload


def view_limitations(data_pack: dict[str, Any], analysis_plan: dict[str, Any]) -> list[str]:
    limitations: list[str] = []
    for gap in data_pack.get("data_gaps") or []:
        if isinstance(gap, dict):
            limitations.append(customer_visible_data_gap(first(gap.get("reason"), gap.get("impact"), gap.get("gap"), default="")))
        else:
            limitations.append(customer_visible_data_gap(gap))
    limitations.extend(customer_safe_asset_text(item) for item in (analysis_plan.get("limitations") or []))
    return unique_customer_messages([item for item in limitations if item])


def safe_kpis(data_pack: dict[str, Any], decision: str) -> list[dict[str, Any]]:
    category = (data_pack.get("categories") or [{}])[0]
    keywords = [kw for kw in customer_relevant_keywords(data_pack) if kw.get("monthly_search_volume")]
    keywords = sorted(keywords, key=lambda kw: as_float(kw.get("monthly_search_volume"), 0), reverse=True)
    effective_keywords = effective_records(data_pack, "keywords")
    keyword_intent_gate = (data_pack.get("report_readiness") or {}).get("keyword_customer_intent_gate") or {}
    keyword_intent_count = keyword_intent_gate.get("unique_customer_intents") or keyword_customer_intent_count(effective_keywords)
    keyword_subtext = f"{len(effective_keywords)} 条有效关键词聚合后的客户意图"
    if keyword_intent_gate and keyword_intent_gate.get("passed") is False:
        keyword_subtext += "；重复率过高已阻断完整结论"
    products = relevant_products(effective_records(data_pack, "products"), data_pack.get("research_object"))
    top100_units = category.get("top100_estimated_monthly_units")
    competitor_units = sum(as_float(product_sales(product), 0) for product in products)
    if top100_units and len(products) >= 100:
        volume_kpi = {"label": "Top100 估算月销量", "value": top100_units, "subtext": "第三方类目代理指标"}
    else:
        volume_kpi = {
            "label": "当前有效竞品池销量",
            "value": int(competitor_units) if competitor_units else None,
            "subtext": f"{len(products)} 个有效竞品汇总；不足大盘覆盖不冒充类目榜单",
        }
    return [
        {"label": "核心判断", "value": decision, "subtext": "Go / Watch / No-Go"},
        volume_kpi,
        {"label": "关键词意图数", "value": keyword_intent_count, "subtext": keyword_subtext},
        {"label": "评论记录", "value": len(effective_records(data_pack, "reviews")), "subtext": "客户版展示中文归纳和必要英文摘录"},
        {"label": "竞品", "value": len(products), "subtext": "过滤非目标噪声后"},
        {"label": "供应端记录", "value": len(effective_records(data_pack, "suppliers")), "subtext": "1688 参考"},
        {
            "label": "TikTok 信号",
            "value": len(data_pack.get("tiktok_products") or []) + len(data_pack.get("tiktok_videos") or []) + len(data_pack.get("tiktok_authors") or []),
            "subtext": "商品/视频/达人",
        },
        {"label": "最大关键词月搜索", "value": keywords[0].get("monthly_search_volume") if keywords else None, "subtext": keywords[0].get("keyword_cn") if keywords else "需增加关键词采集"},
    ]


def build_report_views(data_pack: dict[str, Any], analysis_plan: dict[str, Any], decision: str) -> dict[str, dict[str, Any]]:
    products = relevant_products(effective_records(data_pack, "products"), data_pack.get("research_object"))
    reviews = effective_records(data_pack, "reviews")
    suppliers = effective_records(data_pack, "suppliers")
    keywords = effective_records(data_pack, "keywords")
    theme_counts: Counter[str] = Counter()
    star_counts: Counter[str] = Counter()
    segment_counts: Counter[str] = Counter()
    for review in reviews:
        theme_counts.update(review_theme_labels(review))
        rating = int(as_float(review.get("rating"), 0))
        if rating:
            star_counts[f"{rating}星"] += 1
    for product in products:
        segment_counts[infer_segment_cn(product) or "目标类目竞品"] += 1

    limitations = view_limitations(data_pack, analysis_plan)
    readiness_state = view_readiness_state(data_pack, decision)
    common = {
        "evidence_strength": confidence_level(data_pack, analysis_plan),
        "readiness": readiness_state,
        "sample_coverage": {
            "products": len(products),
            "keywords": len(keywords),
            "reviews": len(reviews),
            "tiktok_products": len(data_pack.get("tiktok_products") or []),
            "tiktok_videos": len(data_pack.get("tiktok_videos") or []),
            "tiktok_authors": len(data_pack.get("tiktok_authors") or []),
            "suppliers": len(suppliers),
            "web_documents": len(data_pack.get("web_documents") or []),
        },
        "limitations": limitations,
        "client_safe_text": True,
    }
    market_rows = [
        {
            "reference_asin": clean(product.get("asin")),
            "segment": infer_segment_cn(product) or "目标类目竞品",
            "title_cn": customer_product_label(product),
            "brand": customer_safe_brand(product.get("brand")) or "参考竞品品牌",
            "price": product_price(product),
            "monthly_sales": product_sales(product),
            "rating": product.get("rating"),
            "review_count": product.get("review_count"),
            "positioning_cn": product.get("positioning_cn"),
            "image_url": clean(first(product.get("image_url"), product.get("image"), product.get("photo"), product.get("main_image"), default="")),
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
    lifecycle_analysis = data_pack.get("lifecycle_strategy") or {}
    lifecycle_sku_rows = lifecycle_skus(data_pack, lifecycle_analysis, primary_source_id(data_pack))
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
            "sku_candidate_pool": lifecycle_analysis.get("sku_candidate_pool") or lifecycle_sku_rows,
            "recommended_skus": lifecycle_analysis.get("recommended_skus") or lifecycle_sku_rows[:8],
            "ecosystem_nodes": lifecycle_analysis.get("ecosystem_nodes") or [],
            "filter_diagnostics": lifecycle_analysis.get("filter_diagnostics") or {},
        },
    }


def write_report_views(report_dir: Path, data_pack: dict[str, Any], analysis_plan: dict[str, Any], decision: str) -> None:
    views = build_report_views(data_pack, analysis_plan, decision)
    analysis_dir = report_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in views.items():
        (analysis_dir / f"{name}.json").write_text(json.dumps(client_safe_view_payload(payload), ensure_ascii=False, indent=2), encoding="utf-8")
