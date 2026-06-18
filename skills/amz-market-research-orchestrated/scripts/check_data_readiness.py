#!/usr/bin/env python3
"""Preflight data-depth gate for amz-market-research-orchestrated runs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from html_components import relevant_products


MIN_STANDARD_KEYWORDS = 1000
MIN_STANDARD_PRODUCTS = 1
MIN_STANDARD_COMPETITORS = 30
MIN_DEEP_COMPETITORS = 60
MIN_BROAD_MARKET_SEGMENTS = 3
MIN_COMPETITORS_PER_PRIMARY_SEGMENT = 10
MIN_QUICK_KEYWORDS = 1
MIN_QUICK_PRODUCTS = 1
RECOMMENDED_STANDARD_REVIEW_SAMPLE = 80
RECOMMENDED_DEEP_REVIEW_SAMPLE = 200
RECOMMENDED_WEB_DOCUMENTS = 1
MIN_VALID_1688_QUOTES = 50
MIN_SUPPLIER_FIELD_COVERAGE_PCT = 70
MAX_SUPPLIER_MAX_TO_P50_RATIO = 20
MAX_SUPPLIER_P75_TO_P25_RATIO = 5
MIN_KEYWORD_CN_MAPPING_COVERAGE_PCT = 70
MAX_CUSTOMER_KEYWORD_INTENT_DUPLICATE_RATIO = 0.30
RECOMMENDED_TIKTOK_SIGNALS = 1
SUPPLY_BLOCKER_MODULES = {
    "supplier_quote_depth",
    "supplier_quote_relevance",
    "supplier_quote_quality",
    "supplier_quote_price_spread",
}
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
    "玻璃火罐",
    "抽气式",
    "抽气枪",
    "拔罐枪",
    "硅胶面部",
    "面部罐",
    "脸部",
    "眼部",
    "小儿",
    "单个真空",
    "散装",
    "手动拉杆",
    "延生罐体",
    "罐子配件",
]
SUPPLIER_STRONG_FINISHED_GOOD_TOKENS = [
    "电动",
    "智能",
    "充电",
    "热敷",
    "红光",
    "负压",
    "按摩器",
    "刮痧仪",
    "吸痧仪",
    "揉腹仪",
    "成品",
    "套装",
]
SUPPLIER_HARD_COMPONENT_TOKENS = [
    "玻璃火罐",
    "抽气枪",
    "拔罐枪",
    "硅胶面部",
    "面部罐",
    "脸部硅胶",
    "眼部",
    "小儿",
    "罐子配件",
    "手动拉杆",
    "单个真空",
    "散装",
]
SUPPLIER_CONTEXT_GENERIC_TERMS = {
    "产品",
    "商品",
    "供应",
    "厂家",
    "工厂",
    "批发",
    "现货",
    "跨境",
    "专供",
    "亚马逊",
    "外贸",
    "1688",
    "配件",
    "套装",
    "定制",
    "户外",
    "便携",
    "多功能",
}
SUPPLIER_CONTEXT_NOISE_TERMS = {
    "儿童",
    "玩具",
    "吊床",
    "急救",
    "医疗",
    "沙滩",
    "餐具",
    "背包",
    "广告",
    "婚礼",
    "蒙古包",
    "更衣",
    "淋浴",
}
BROAD_RESEARCH_TERMS = {
    "smart lighting",
    "智能照明",
    "lighting",
    "灯具",
    "led lighting",
}
MAX_EFFECTIVE_KEYWORD_DUPLICATE_RATIO = 0.02


class ReadinessError(Exception):
    pass


def load_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise ReadinessError(f"Missing JSON file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReadinessError(f"{path}: invalid JSON: {exc}") from exc


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def infer_depth(report_dir: Path, explicit_depth: str) -> str:
    if explicit_depth != "auto":
        return explicit_depth
    brief = load_json(report_dir / "report_brief.json", {})
    candidates = [
        brief.get("data_depth"),
        brief.get("depth"),
        (brief.get("data_scope") or {}).get("depth") if isinstance(brief.get("data_scope"), dict) else None,
        (brief.get("data_scope") or {}).get("level") if isinstance(brief.get("data_scope"), dict) else None,
    ]
    joined = " ".join(str(item or "").lower() for item in candidates)
    if any(token in joined for token in ("quick", "快速")):
        return "quick"
    if any(token in joined for token in ("deep", "深度")):
        return "deep"
    return "standard"


def authorized_keyword_minimum(report_dir: Path, default: int) -> tuple[int, dict[str, Any] | None]:
    """Allow a run-specific, user-authorized keyword floor without changing defaults."""
    brief = load_json(report_dir / "report_brief.json", {})
    if not isinstance(brief, dict):
        return default, None
    data_scope = brief.get("data_scope") if isinstance(brief.get("data_scope"), dict) else {}
    waiver = data_scope.get("keyword_sample_depth_waiver") if isinstance(data_scope, dict) else None
    if not isinstance(waiver, dict):
        waiver = brief.get("keyword_sample_depth_waiver")
    data_inputs = brief.get("data_inputs") if isinstance(brief.get("data_inputs"), dict) else {}
    if not isinstance(waiver, dict) and isinstance(data_inputs, dict):
        waiver = data_inputs.get("keyword_sample_depth_waiver")
    if not isinstance(waiver, dict):
        return default, None
    try:
        authorized_minimum = int(waiver.get("authorized_min_effective_keywords"))
    except (TypeError, ValueError):
        return default, None
    if authorized_minimum <= 0 or authorized_minimum >= default:
        return default, None
    if waiver.get("authorized_by_user") is not True:
        return default, None
    if not str(waiver.get("reason") or "").strip():
        return default, None
    return authorized_minimum, waiver


def load_data_pack(report_dir: Path) -> tuple[dict[str, Any], str]:
    normalized = report_dir / "data" / "normalized" / "normalized_data_pack.json"
    raw = report_dir / "data" / "data_pack.json"
    path = normalized if normalized.exists() else raw
    data_pack = load_json(path)
    if not isinstance(data_pack, dict):
        raise ReadinessError(f"{path}: data pack must be a JSON object")
    return data_pack, path.relative_to(report_dir).as_posix()


def count(data_pack: dict[str, Any], key: str) -> int:
    value = data_pack.get(key)
    return len(value) if isinstance(value, list) else 0


def effective_records(data_pack: dict[str, Any], key: str) -> list[dict[str, Any]]:
    effective_key = f"effective_{key}"
    value = data_pack.get(effective_key)
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    value = data_pack.get(key)
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def gap(module: str, current: int, required: int, reason: str, next_step: str) -> dict[str, Any]:
    return {
        "module": module,
        "current": current,
        "required": required,
        "reason": reason,
        "next_step": next_step,
    }


def warning(module: str, current: int, recommended: int, impact: str, next_step: str) -> dict[str, Any]:
    return {
        "module": module,
        "current": current,
        "recommended": recommended,
        "impact": impact,
        "next_step": next_step,
    }


def to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "").replace("，", ""))
    except (TypeError, ValueError):
        return None


def supplier_identity(supplier: dict[str, Any]) -> str:
    for key in ("canonical_url", "url", "product_url"):
        value = str(supplier.get(key) or "").strip().split("?", 1)[0].split("#", 1)[0].lower()
        if value:
            return f"url|{value.rstrip('/')}"
    product_id = str(supplier.get("product_id") or supplier.get("offer_id") or "").strip().lower()
    if product_id:
        return f"id|{product_id}"
    title = " ".join(str(supplier.get("title") or supplier.get("title_cn") or supplier.get("name") or "").casefold().split())
    shop = " ".join(str(supplier.get("supplier_name") or supplier.get("store_name") or supplier.get("shop") or "").casefold().split())
    return f"title_shop|{title}|{shop}" if title and shop else ""


def product_price(product: dict[str, Any]) -> Any:
    for key in ("price", "current_price", "buy_box_price"):
        if product.get(key) not in (None, ""):
            return product.get(key)
    return None


def product_sales(product: dict[str, Any]) -> Any:
    for key in ("estimated_monthly_sales", "monthly_sales", "sales", "sales_30d", "bsr_sales_estimate"):
        if product.get(key) not in (None, ""):
            return product.get(key)
    for key in ("bsr", "rank", "sales_rank", "best_seller_rank"):
        if product.get(key) not in (None, ""):
            return product.get(key)
    return None


def product_reviews(product: dict[str, Any]) -> Any:
    for key in ("review_count", "reviews", "rating_count", "ratings_count"):
        if product.get(key) not in (None, ""):
            return product.get(key)
    return None


def product_segment(product: dict[str, Any]) -> str:
    return str(product.get("segment_cn") or product.get("segment") or product.get("category_cn") or product.get("category") or "").strip()


def is_valid_segment(segment: str) -> bool:
    return bool(segment and segment not in {"未分层", "unclassified", "unknown", "n/a", "na"})


def valid_competitor_products(data_pack: dict[str, Any]) -> list[dict[str, Any]]:
    valid: list[dict[str, Any]] = []
    seen: set[str] = set()
    for product in relevant_products(effective_records(data_pack, "products"), data_pack.get("research_object")):
        if not isinstance(product, dict):
            continue
        asin = str(product.get("asin") or "").strip().upper()
        title = str(product.get("title") or product.get("title_cn") or "").strip()
        brand = str(product.get("brand") or "").strip()
        segment = product_segment(product)
        price = to_float(product_price(product))
        rating = to_float(product.get("rating") or product.get("星级"))
        reviews = to_float(product_reviews(product))
        sales = to_float(product_sales(product))
        key = asin or title.casefold()
        if (
            not key
            or key in seen
            or not asin
            or not title
            or not brand
            or not is_valid_segment(segment)
            or price is None
            or price <= 0
            or rating is None
            or rating <= 0
            or reviews is None
            or reviews <= 0
            or sales is None
            or sales <= 0
        ):
            continue
        seen.add(key)
        valid.append(product)
    return valid


def research_object_text(report_dir: Path, data_pack: dict[str, Any]) -> str:
    brief = load_json(report_dir / "report_brief.json", {})
    values: list[str] = []
    for source in (brief, data_pack.get("brief") or {}, data_pack):
        if not isinstance(source, dict):
            continue
        obj = source.get("research_object")
        if isinstance(obj, dict):
            values.append(str(obj.get("value") or ""))
        elif obj:
            values.append(str(obj))
        for key in ("task_id", "category", "keyword"):
            if source.get(key):
                values.append(str(source.get(key)))
    return " ".join(values).casefold()


def is_broad_research(report_dir: Path, data_pack: dict[str, Any]) -> bool:
    text = research_object_text(report_dir, data_pack)
    return any(term in text for term in BROAD_RESEARCH_TERMS)


def segment_counts(products: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for product in products:
        segment = product_segment(product) or "未分层"
        counts[segment] = counts.get(segment, 0) + 1
    return counts


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


def valid_supplier_quotes(data_pack: dict[str, Any]) -> list[dict[str, Any]]:
    valid: list[dict[str, Any]] = []
    seen: set[str] = set()
    for supplier in effective_records(data_pack, "suppliers"):
        if not isinstance(supplier, dict):
            continue
        price = to_float(
            supplier.get("price_rmb")
            if supplier.get("price_rmb") not in (None, "")
            else supplier.get("factory_price_rmb")
            if supplier.get("factory_price_rmb") not in (None, "")
            else supplier.get("price")
        )
        title = supplier.get("title") or supplier.get("title_cn") or supplier.get("name")
        product_id = supplier.get("product_id") or supplier.get("offer_id")
        shop = supplier.get("supplier_name") or supplier.get("store_name") or supplier.get("shop")
        identity = supplier_identity(supplier)
        if price is None or price <= 0 or not (title or product_id) or not shop or not identity or identity in seen:
            continue
        seen.add(identity)
        valid.append(supplier)
    return valid


def supplier_price(supplier: dict[str, Any]) -> Any:
    if supplier.get("price_rmb") not in (None, ""):
        return supplier.get("price_rmb")
    if supplier.get("factory_price_rmb") not in (None, ""):
        return supplier.get("factory_price_rmb")
    return supplier.get("price")


def supplier_title_text(supplier: dict[str, Any]) -> str:
    return " ".join(
        str(supplier.get(key) or "")
        for key in ["title", "title_cn", "name", "product_name", "supplier_name", "seed_keyword"]
    ).strip().casefold()


def supplier_product_text(supplier: dict[str, Any]) -> str:
    return " ".join(
        str(supplier.get(key) or "")
        for key in ["title", "title_cn", "name", "product_name"]
    ).strip().casefold()


def cjk_terms(value: Any) -> set[str]:
    terms: set[str] = set()
    for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", str(value or "")):
        if chunk not in SUPPLIER_CONTEXT_GENERIC_TERMS and len(chunk) <= 12:
            terms.add(chunk)
        max_len = min(5, len(chunk))
        for size in range(2, max_len + 1):
            for idx in range(0, len(chunk) - size + 1):
                term = chunk[idx : idx + size]
                if term not in SUPPLIER_CONTEXT_GENERIC_TERMS:
                    terms.add(term)
    return terms


def supplier_relevance_terms(data_pack: dict[str, Any]) -> set[str]:
    texts: list[str] = []
    research_object = data_pack.get("research_object")
    if isinstance(research_object, dict):
        texts.append(str(research_object.get("value") or ""))
    elif research_object:
        texts.append(str(research_object))
    for product in valid_competitor_products(data_pack)[:80]:
        texts.extend(
            str(product.get(key) or "")
            for key in (
                "customer_segment_cn",
                "segment_cn",
                "segment",
                "title_cn",
                "customer_label_cn",
                "category_cn",
            )
        )
    for keyword in effective_records(data_pack, "keywords")[:160]:
        keyword_cn = str(keyword.get("keyword_cn") or keyword.get("label_cn") or "")
        if keyword_cn and "未映射关键词" not in keyword_cn:
            texts.append(keyword_cn)
    terms: set[str] = set()
    for text in texts:
        terms.update(cjk_terms(text))
    return {term for term in terms if len(term) >= 2 and term not in SUPPLIER_CONTEXT_GENERIC_TERMS}


def supplier_matches_research_context(supplier: dict[str, Any], data_pack: dict[str, Any]) -> bool:
    product_text = supplier_product_text(supplier)
    if not product_text:
        return False
    context_terms = supplier_relevance_terms(data_pack)
    has_context_hit = any(term in product_text for term in context_terms)
    has_noise = any(term in product_text for term in SUPPLIER_CONTEXT_NOISE_TERMS)
    if context_terms:
        return has_context_hit and not (has_noise and not has_context_hit)
    return not has_noise


def is_finished_supplier_quote(supplier: dict[str, Any]) -> bool:
    price = to_float(supplier_price(supplier))
    if price is None or price <= 0:
        return False
    text = supplier_title_text(supplier)
    has_strong_finished_signal = any(token in text for token in SUPPLIER_STRONG_FINISHED_GOOD_TOKENS)
    if any(token in text for token in SUPPLIER_HARD_COMPONENT_TOKENS):
        return False
    if any(token in text for token in SUPPLIER_NON_FINISHED_TOKENS) and not has_strong_finished_signal:
        return False
    if price < 0.5:
        return False
    return True


def supplier_quality(valid_quotes: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(valid_quotes)
    prices = []
    title_count = 0
    identity_count = 0
    segment_hint_count = 0
    for supplier in valid_quotes:
        title = supplier.get("title") or supplier.get("title_cn") or supplier.get("name")
        url = supplier.get("canonical_url") or supplier.get("url") or supplier.get("product_url")
        product_id = supplier.get("product_id") or supplier.get("offer_id")
        segment_hint = supplier.get("segment_cn") or supplier.get("segment") or supplier.get("seed_keyword") or supplier.get("search_term")
        if title:
            title_count += 1
        if url or product_id:
            identity_count += 1
        if segment_hint:
            segment_hint_count += 1
        price = to_float(
            supplier.get("price_rmb")
            if supplier.get("price_rmb") not in (None, "")
            else supplier.get("factory_price_rmb")
            if supplier.get("factory_price_rmb") not in (None, "")
            else supplier.get("price")
        )
        if price is not None and price > 0:
            prices.append(price)
    title_pct = round((title_count / total) * 100, 1) if total else 0
    identity_pct = round((identity_count / total) * 100, 1) if total else 0
    segment_pct = round((segment_hint_count / total) * 100, 1) if total else 0
    p25 = percentile(prices, 0.25)
    p50 = percentile(prices, 0.50)
    p75 = percentile(prices, 0.75)
    max_price = max(prices) if prices else None
    max_to_p50 = round(max_price / p50, 2) if max_price and p50 else None
    p75_to_p25 = round(p75 / p25, 2) if p75 and p25 else None
    field_passed = title_pct >= MIN_SUPPLIER_FIELD_COVERAGE_PCT and identity_pct >= MIN_SUPPLIER_FIELD_COVERAGE_PCT
    price_spread_passed = (
        max_to_p50 is None
        or p75_to_p25 is None
        or (max_to_p50 <= MAX_SUPPLIER_MAX_TO_P50_RATIO and p75_to_p25 <= MAX_SUPPLIER_P75_TO_P25_RATIO)
    )
    return {
        "required_field_coverage_pct": MIN_SUPPLIER_FIELD_COVERAGE_PCT,
        "title_coverage_pct": title_pct,
        "identity_coverage_pct": identity_pct,
        "segment_hint_coverage_pct": segment_pct,
        "p25_rmb": p25,
        "p50_rmb": p50,
        "p75_rmb": p75,
        "max_rmb": max_price,
        "max_to_p50_ratio": max_to_p50,
        "p75_to_p25_ratio": p75_to_p25,
        "field_quality_passed": field_passed,
        "price_spread_passed": price_spread_passed,
        "passed": field_passed and price_spread_passed,
    }


def supplier_bucket_label(supplier: dict[str, Any]) -> str:
    for key in ("seed_keyword", "search_term", "query", "segment_cn", "segment"):
        value = supplier.get(key)
        if value not in (None, ""):
            return str(value).strip()
    return ""


def same_search_supplier_bucket_gate(valid_quotes: list[dict[str, Any]], minimum_quotes: int = MIN_VALID_1688_QUOTES) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for supplier in valid_quotes:
        label = supplier_bucket_label(supplier)
        if not label:
            continue
        buckets.setdefault(label, []).append(supplier)

    best: dict[str, Any] = {"passed": False, "bucket": None, "valid_quotes": 0, "quality": None}
    for label, quotes in buckets.items():
        if len(quotes) < minimum_quotes:
            continue
        quality = supplier_quality(quotes)
        candidate = {
            "passed": quality["passed"],
            "bucket": label,
            "valid_quotes": len(quotes),
            "quality": quality,
        }
        if candidate["passed"]:
            return candidate
        if len(quotes) > int(best.get("valid_quotes") or 0):
            best = candidate
    return best


def keyword_bucket_key(keyword: dict[str, Any]) -> str:
    explicit_bucket = " ".join(str(keyword.get("source_bucket") or keyword.get("bucket") or "").strip().casefold().split())
    if explicit_bucket:
        bucket = explicit_bucket
    else:
        source_type = str(keyword.get("source_type") or "").strip().casefold()
        asin = str(keyword.get("asin") or "").strip().casefold()
        bucket = f"traffic:{asin or 'unknown'}" if source_type == "product_traffic_terms" or asin else "market"
    text = " ".join(str(keyword.get("keyword") or "").strip().casefold().split())
    return f"{bucket}|{text}"


def keyword_duplicate_diagnostic(keywords: list[dict[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    duplicate_extra = 0
    for keyword in keywords:
        key = keyword_bucket_key(keyword)
        if not key or key.endswith("|"):
            continue
        if key in seen:
            duplicate_extra += 1
        seen.add(key)
    ratio = duplicate_extra / len(keywords) if keywords else 0.0
    return {
        "duplicate_extra": duplicate_extra,
        "duplicate_ratio": round(ratio, 4),
        "max_duplicate_ratio": MAX_EFFECTIVE_KEYWORD_DUPLICATE_RATIO,
        "passed": ratio <= MAX_EFFECTIVE_KEYWORD_DUPLICATE_RATIO,
    }


def keyword_customer_intent_diagnostic(keywords: list[dict[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    total = 0
    duplicate_extra = 0
    examples: list[str] = []
    for keyword in keywords:
        label = str(keyword.get("customer_label_cn") or keyword.get("keyword_cn") or "").strip()
        if not label or label.startswith("未映射关键词") or label.startswith("污染关键词"):
            continue
        key = re.sub(r"\s+", " ", label.casefold()).strip()
        if not key:
            continue
        total += 1
        if key in seen:
            duplicate_extra += 1
            if len(examples) < 8 and label not in examples:
                examples.append(label)
        seen.add(key)
    ratio = duplicate_extra / total if total else 0.0
    return {
        "total": total,
        "unique_customer_intents": len(seen),
        "duplicate_extra": duplicate_extra,
        "duplicate_ratio": round(ratio, 4),
        "max_duplicate_ratio": MAX_CUSTOMER_KEYWORD_INTENT_DUPLICATE_RATIO,
        "passed": ratio <= MAX_CUSTOMER_KEYWORD_INTENT_DUPLICATE_RATIO,
        "duplicate_examples": examples,
    }


def keyword_mapping_quality(keywords: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(keywords)
    mapped = 0
    unmapped_examples: list[str] = []
    for keyword in keywords:
        keyword_cn = str(keyword.get("keyword_cn") or keyword.get("customer_label_cn") or "").strip()
        raw_keyword = str(keyword.get("keyword") or "").strip()
        is_mapped = (
            bool(keyword_cn)
            and not keyword_cn.startswith("未映射关键词")
            and keyword_cn.casefold() != raw_keyword.casefold()
            and re.search(r"[\u4e00-\u9fff]", keyword_cn) is not None
        )
        if is_mapped:
            mapped += 1
        elif len(unmapped_examples) < 8 and raw_keyword:
            unmapped_examples.append(raw_keyword)
    coverage = round((mapped / total) * 100, 1) if total else 0.0
    return {
        "total": total,
        "mapped": mapped,
        "unmapped": max(0, total - mapped),
        "mapping_coverage_pct": coverage,
        "required_mapping_coverage_pct": MIN_KEYWORD_CN_MAPPING_COVERAGE_PCT,
        "passed": coverage >= MIN_KEYWORD_CN_MAPPING_COVERAGE_PCT,
        "unmapped_examples": unmapped_examples,
    }


def collector_commands(report_dir: Path) -> list[str]:
    report = str(report_dir)
    return [
        f"python skills/amz-market-research-orchestrated/scripts/collect_sorftime_keywords.py --dir {report} --min-keywords 1200",
        f"python skills/amz-market-research-orchestrated/scripts/collect_sorftime_products.py --dir {report} --min-products {MIN_STANDARD_COMPETITORS} --max-seeds 8 --max-pages 3 --site US --min-segments {MIN_BROAD_MARKET_SEGMENTS} --min-per-segment {MIN_COMPETITORS_PER_PRIMARY_SEGMENT}",
        f"python skills/amz-market-research-orchestrated/scripts/collect_sorftime_product_enrichment.py --dir {report} --max-products 10 --max-pages 1 --site US",
        f"python skills/amz-market-research-orchestrated/scripts/collect_sorftime_reviews.py --dir {report} --review-type Both",
        f"python skills/amz-market-research-orchestrated/scripts/collect_sorftime_tiktok_signals.py --dir {report} --site US --max-seeds 4 --max-pages 1 --max-products-detail 3 --video-pages 1",
        f"python skills/amz-market-research-orchestrated/scripts/collect_sorftime_1688_suppliers.py --dir {report} --min-valid-quotes {MIN_VALID_1688_QUOTES} --max-rounds 5 --max-pages 3 --force-rounds",
        f"python skills/amz-market-research-orchestrated/scripts/normalize_data_pack.py --dir {report}",
    ]


def assess(report_dir: Path, depth: str = "auto") -> dict[str, Any]:
    report_dir = report_dir.resolve()
    data_pack, data_pack_path = load_data_pack(report_dir)
    resolved_depth = infer_depth(report_dir, depth)
    standard_like = resolved_depth in {"standard", "deep"}
    required_keywords = MIN_STANDARD_KEYWORDS if standard_like else MIN_QUICK_KEYWORDS
    keyword_waiver: dict[str, Any] | None = None
    if standard_like:
        required_keywords, keyword_waiver = authorized_keyword_minimum(report_dir, required_keywords)
    required_products = MIN_STANDARD_PRODUCTS if standard_like else MIN_QUICK_PRODUCTS

    raw_supplier_quotes = valid_supplier_quotes(data_pack)
    supplier_quotes = [quote for quote in raw_supplier_quotes if is_finished_supplier_quote(quote)]
    relevant_supplier_quotes = [quote for quote in supplier_quotes if supplier_matches_research_context(quote, data_pack)]
    non_finished_filtered = len(raw_supplier_quotes) - len(supplier_quotes)
    context_products = relevant_products(effective_records(data_pack, "products"), data_pack.get("research_object"))
    competitor_products = valid_competitor_products(data_pack)
    competitor_segments = segment_counts(competitor_products)
    effective_keywords = effective_records(data_pack, "keywords")
    effective_reviews = effective_records(data_pack, "reviews")
    keyword_duplicate_gate = keyword_duplicate_diagnostic(effective_keywords)
    keyword_customer_intent_gate = keyword_customer_intent_diagnostic(effective_keywords)
    keyword_mapping_gate = keyword_mapping_quality(effective_keywords)
    raw_supplier_quality_gate = supplier_quality(supplier_quotes)
    supplier_quality_gate = supplier_quality(relevant_supplier_quotes)
    same_search_bucket_gate = same_search_supplier_bucket_gate(relevant_supplier_quotes)
    supplier_quality_gate["same_search_bucket_gate"] = same_search_bucket_gate
    supplier_quality_gate["global_passed"] = supplier_quality_gate["passed"]
    supplier_quality_gate["effective_passed"] = bool(supplier_quality_gate["passed"] or same_search_bucket_gate.get("passed"))
    supplier_quality_gate["customer_visible_passed"] = bool(
        len(relevant_supplier_quotes) >= (MIN_VALID_1688_QUOTES if standard_like else 1)
        and supplier_quality_gate["effective_passed"]
    )
    supplier_quality_gate["passed"] = supplier_quality_gate["customer_visible_passed"]
    supplier_quality_gate["raw_finished_valid_quotes"] = len(supplier_quotes)
    supplier_quality_gate["strict_relevant_valid_quotes"] = len(relevant_supplier_quotes)
    supplier_quality_gate["strict_relevance_filtered"] = len(supplier_quotes) - len(relevant_supplier_quotes)
    supplier_quality_gate["raw_quality_gate"] = raw_supplier_quality_gate
    supplier_collection_summary = load_json(report_dir / "data" / "normalized" / "supplier_1688_collection_summary.json", {})
    missing_1688_fields = supplier_collection_summary.get("missing_documented_required_fields") or []
    if missing_1688_fields:
        supplier_quality_gate["missing_documented_required_fields"] = missing_1688_fields
        supplier_quality_gate["observed_fields"] = supplier_collection_summary.get("observed_fields") or []
    competitor_minimum = MIN_DEEP_COMPETITORS if resolved_depth == "deep" else MIN_STANDARD_COMPETITORS if standard_like else MIN_QUICK_PRODUCTS
    broad_research = is_broad_research(report_dir, data_pack)
    top_segment_counts = sorted(competitor_segments.values(), reverse=True)
    underfilled_segments = {
        segment: count
        for segment, count in competitor_segments.items()
        if count < MIN_COMPETITORS_PER_PRIMARY_SEGMENT
    }
    segment_depth_gate_passed = not (standard_like and underfilled_segments)
    segment_gate_passed = (
        segment_depth_gate_passed
        and (
            not broad_research
            or (
            len(competitor_segments) >= MIN_BROAD_MARKET_SEGMENTS
            and len(top_segment_counts) >= MIN_BROAD_MARKET_SEGMENTS
            and not underfilled_segments
            )
        )
    )
    counts = {
        "sources": count(data_pack, "sources"),
        "raw_products": count(data_pack, "products"),
        "products": len(context_products),
        "valid_competitors": len(competitor_products),
        "market_segments": len(competitor_segments),
        "raw_keywords": count(data_pack, "keywords"),
        "keywords": len(effective_keywords),
        "categories": count(data_pack, "categories"),
        "raw_reviews": count(data_pack, "reviews"),
        "reviews": len(effective_reviews),
        "tiktok_products": count(data_pack, "tiktok_products"),
        "tiktok_videos": count(data_pack, "tiktok_videos"),
        "tiktok_authors": count(data_pack, "tiktok_authors"),
        "raw_suppliers": count(data_pack, "suppliers"),
        "suppliers": len(effective_records(data_pack, "suppliers")),
        "valid_supplier_quotes": len(relevant_supplier_quotes),
        "raw_valid_supplier_quotes": len(supplier_quotes),
        "web_documents": count(data_pack, "web_documents"),
        "data_gaps": count(data_pack, "data_gaps"),
    }

    blocking_gaps: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    applied_waivers: list[dict[str, Any]] = []
    if keyword_waiver:
        applied_waivers.append(
            {
                "module": "keyword_sample_depth",
                "default_required": MIN_STANDARD_KEYWORDS,
                "authorized_required": required_keywords,
                "authorized_by_user": True,
                "reason": keyword_waiver.get("reason"),
                "limitation": keyword_waiver.get("limitation", "低于默认关键词样本门槛，报告必须显式披露。"),
            }
        )
        warnings.append(
            warning(
                "keyword_sample_depth_waiver",
                counts["keywords"],
                MIN_STANDARD_KEYWORDS,
                "用户授权本次以低于默认 1000 条有效关键词门槛继续；报告结论需要保留样本限制说明。",
                "不要把本次授权改写为默认合同；后续同类项目仍按 1000 条有效关键词门槛执行。",
            )
        )

    if counts["sources"] < 1:
        blocking_gaps.append(
            gap(
                "source_lineage",
                counts["sources"],
                1,
                "Data Pack 没有任何可追溯 source，不能进入审计型报告生成。",
                "先采集 Sorftime/Firecrawl 原始证据并写入 data_pack.sources。",
            )
        )
    if counts["products"] < required_products:
        blocking_gaps.append(
            gap(
                "product_sample_depth",
                counts["products"],
                required_products,
                "缺少 Amazon 产品池/竞品样本，市场、生命周期和需求断层报告都会失真。",
                "先运行产品池/搜索结果/竞品详情采集，再归一化。",
            )
        )
    if standard_like and len(competitor_products) < competitor_minimum:
        blocking_gaps.append(
            gap(
                "competitor_pool_depth",
                len(competitor_products),
                competitor_minimum,
                "亚马逊竞品池不足，不能支撑标准版/深度版市场格局、价格带和标杆竞品拆解。",
                "补采 Amazon 竞品详情，确保每个竞品具备 ASIN、标题、品牌、价格、评分、评论数、销量或排名代理字段、细分赛道。",
            )
        )
    if standard_like and not segment_gate_passed:
        blocking_gaps.append(
            gap(
                "market_segment_split",
                len(competitor_segments),
                MIN_BROAD_MARKET_SEGMENTS,
                "研究对象属于大词，必须先拆分到可比较的细分赛道，不能把混合类目直接做成完整结论。",
                "按当前研究对象重新拆分核心使用场景、价格带和功能路线，并补齐每个主赛道至少 10 个有效竞品。",
            )
        )
    if standard_like and not segment_depth_gate_passed:
        blocking_gaps.append(
            gap(
                "market_segment_depth",
                min(underfilled_segments.values()) if underfilled_segments else 0,
                MIN_COMPETITORS_PER_PRIMARY_SEGMENT,
                "部分细分赛道有效竞品不足 10 个，不能进入推荐排名、生命周期 SKU 池或完整市场结论。",
                "按当前提示的低样本赛道补采 Amazon 竞品；补齐前这些赛道只能作为需验证方向展示。",
            )
        )
    if counts["keywords"] < required_keywords:
        keyword_next_step = (
            f"当前原始关键词 {counts['raw_keywords']} 条，但有效去重关键词只有 {counts['keywords']} 条；请扩展细分赛道种子词、降低重复分页损耗，并重新归一化，直到有效去重关键词至少 {required_keywords} 条。"
            if counts["raw_keywords"] >= required_keywords
            else f"运行 collect_sorftime_keywords.py 扩展细分赛道种子词，采集后重新归一化，直到有效去重关键词至少 {required_keywords} 条。"
        )
        blocking_gaps.append(
            gap(
                "keyword_sample_depth",
                counts["keywords"],
                required_keywords,
                "关键词样本不足，标准版/深度版不能支撑需求结构和机会判断。",
                keyword_next_step,
            )
        )
    if not keyword_duplicate_gate["passed"]:
        blocking_gaps.append(
            gap(
                "keyword_duplicate_ratio",
                int(keyword_duplicate_gate["duplicate_extra"]),
                0,
                "有效关键词池仍存在重复记录，不能把重复流量词计入需求规模或机会排序。",
                "重新运行 normalize_data_pack.py，按 normalized lowercase keyword + source bucket 去重；若重复来自采集层，需要修正采集分页合并逻辑。",
            )
        )
    if standard_like and not keyword_customer_intent_gate["passed"]:
        blocking_gaps.append(
            gap(
                "keyword_customer_intent_duplicate_ratio",
                int(keyword_customer_intent_gate["duplicate_extra"]),
                0,
                "客户侧关键词主题重复率过高，不能把大量同义词当作独立需求规模或机会排序。",
                "按中文意图聚合关键词，补采更多不同场景、功能、痛点和人群词；客户页主表必须按主题去重展示。",
            )
        )
    if standard_like and not keyword_mapping_gate["passed"]:
        blocking_gaps.append(
            gap(
                "keyword_chinese_mapping",
                int(keyword_mapping_gate["mapping_coverage_pct"]),
                MIN_KEYWORD_CN_MAPPING_COVERAGE_PCT,
                "有效关键词中文映射覆盖率不足，不能把英文原词或未映射词直接用于客户页、COSMO 标签、赛道判断和广告动作。",
                "补充关键词中文映射规则或 AI 标签画像后重新归一化；未映射关键词只能进入审计文件，不能参与客户结论。",
            )
        )

    recommended_reviews = RECOMMENDED_DEEP_REVIEW_SAMPLE if resolved_depth == "deep" else RECOMMENDED_STANDARD_REVIEW_SAMPLE
    if counts["reviews"] < recommended_reviews:
        warnings.append(
            warning(
                "review_sample_depth",
                counts["reviews"],
                recommended_reviews,
                "VOC 可以降级展示，但不能写精确比例或强结论。",
                "运行 collect_sorftime_reviews.py；标准版建议达到 80 条，深度版建议 200 条以上，或在 data_gaps 标注评论样本限制。",
            )
        )
    if counts["web_documents"] < RECOMMENDED_WEB_DOCUMENTS:
        warnings.append(
            warning(
                "web_evidence_depth",
                counts["web_documents"],
                RECOMMENDED_WEB_DOCUMENTS,
                "公开市场、法规或测评证据不足，外部交叉验证偏弱。",
                "用 Firecrawl 补行业/品牌/测评/合规网页；不可用时写 data_gaps。",
            )
        )
    supplier_gate = {
        "required": MIN_VALID_1688_QUOTES if standard_like else 1,
        "actual": counts["valid_supplier_quotes"],
        "raw_valid_quotes": len(raw_supplier_quotes),
        "raw_finished_valid_quotes": len(supplier_quotes),
        "non_finished_filtered": non_finished_filtered,
        "strict_relevance_filtered": len(supplier_quotes) - len(relevant_supplier_quotes),
        "passed": counts["valid_supplier_quotes"] >= (MIN_VALID_1688_QUOTES if standard_like else 1),
        "policy": "1688 去重有效报价必须同时满足数量、字段质量和研究对象相关性，不得用无关报价生成最终供应链毛利率结论。",
    }
    if not supplier_gate["passed"]:
        module = "supplier_quote_depth" if len(supplier_quotes) < supplier_gate["required"] else "supplier_quote_relevance"
        reason = (
            "1688 去重有效报价不足 50 条，不能支撑供应链成本和毛利率测算。"
            if module == "supplier_quote_depth"
            else "1688 成品报价数量足够，但与当前研究对象严格相关的报价不足 50 条，不能支撑供应链成本和毛利率测算。"
        )
        action = (
            "运行 collect_sorftime_1688_suppliers.py 多轮切换搜索词补采；5 轮仍不足时阻断供应链结论并输出诊断。"
            if module == "supplier_quote_depth"
            else "用当前产品标题、细分类目和核心功能词重新生成 1688 中文搜索词，剔除儿童帐篷、吊床、急救帐篷等无关结果后再测算。"
        )
        blocking_gaps.append(
            gap(
                module,
                counts["valid_supplier_quotes"],
                supplier_gate["required"],
                reason,
                action,
            )
        )
    raw_quality_failed = len(supplier_quotes) >= supplier_gate["required"] and not raw_supplier_quality_gate["field_quality_passed"]
    if (supplier_gate["passed"] and not supplier_quality_gate["field_quality_passed"] and not same_search_bucket_gate.get("passed")) or raw_quality_failed:
        missing_field_note = (
            f" 当前 Sorftime 1688 MCP 实际响应缺少官方文档关键字段：{', '.join(str(field) for field in missing_1688_fields)}。"
            if missing_1688_fields
            else ""
        )
        field_quality_current = int(
            min(
                supplier_quality_gate["title_coverage_pct"] or raw_supplier_quality_gate["title_coverage_pct"],
                supplier_quality_gate["identity_coverage_pct"] or raw_supplier_quality_gate["identity_coverage_pct"],
            )
        )
        blocking_gaps.append(
            gap(
                "supplier_quote_quality",
                field_quality_current,
                MIN_SUPPLIER_FIELD_COVERAGE_PCT,
                "1688 报价虽然达到数量门槛，但商品标题、链接或稳定商品指纹覆盖不足，不能证明报价与目标赛道匹配。" + missing_field_note,
                "用细分赛道中文词重新采集 1688，要求去重报价同时具备标题、供应商、价格和链接或稳定商品指纹；若 MCP 继续缺少 Title/URL，需要先修正 Sorftime 返回字段。",
            )
        )
    if supplier_gate["passed"] and not supplier_quality_gate["price_spread_passed"] and same_search_bucket_gate.get("passed"):
        warnings.append(
            warning(
                "supplier_quote_price_spread_global",
                int(supplier_quality_gate["max_to_p50_ratio"] or 0),
                MAX_SUPPLIER_MAX_TO_P50_RATIO,
                f"全局 1688 报价价差异常，已改用搜索词“{same_search_bucket_gate.get('bucket')}”下 {same_search_bucket_gate.get('valid_quotes')} 条同口径报价进入供应链测算。",
                "继续保留全局异常报价在审计文件；客户页只展示同搜索词报价桶的成本分位数和竞品参考毛利率。",
            )
        )
    if supplier_gate["passed"] and not supplier_quality_gate["price_spread_passed"] and not same_search_bucket_gate.get("passed"):
        blocking_gaps.append(
            gap(
                "supplier_quote_price_spread",
                int(supplier_quality_gate["max_to_p50_ratio"] or 0),
                MAX_SUPPLIER_MAX_TO_P50_RATIO,
                "1688 报价分布存在极端价差，说明混入非同类商品、套装、大宗设备或无关供应记录，不能直接进入毛利率测算。",
                "按赛道重新筛选报价，剔除非同类和极端报价后再计算 P25/P50/P75。",
            )
        )
    tiktok_signal_count = counts["tiktok_products"] + counts["tiktok_videos"] + counts.get("tiktok_authors", 0)
    if tiktok_signal_count < RECOMMENDED_TIKTOK_SIGNALS:
        warnings.append(
            warning(
                "tiktok_signal_depth",
                tiktok_signal_count,
                RECOMMENDED_TIKTOK_SIGNALS,
                "内容场景和渠道热度只能降级为未知。",
                "运行 collect_sorftime_tiktok_signals.py 补 TikTok 商品/视频/达人链路；不可用时保留 TikTok 缺口。",
            )
        )

    acceptance_ready = not blocking_gaps
    blocking_modules = {item.get("module") for item in blocking_gaps}
    partial_report_ready = bool(blocking_gaps) and blocking_modules <= SUPPLY_BLOCKER_MODULES
    quality = data_pack.get("quality") or {}
    try:
        score = float(quality.get("overall_score", quality.get("score", 0.0)) or 0.0)
    except (TypeError, ValueError):
        score = 0.0
    if not score:
        score = 0.85 if acceptance_ready else 0.45 if not partial_report_ready else 0.6
    delivery_mode = "full_delivery" if acceptance_ready else "diagnostic_delivery"
    decision = "Watch" if acceptance_ready else "No-Go"
    evidence_grade = "完整可交付" if acceptance_ready else ("供应链诊断交付" if partial_report_ready else "阻断交付")
    return {
        "report_dir": str(report_dir),
        "checked_at": utc_now(),
        "depth": resolved_depth,
        "data_pack": data_pack_path,
        "sample_class": "acceptance_sample" if acceptance_ready else "partial_acceptance_sample" if partial_report_ready else "non_acceptance_sample",
        "acceptance_ready": acceptance_ready,
        "partial_report_ready": partial_report_ready,
        "supply_conclusion_blocked": bool(blocking_modules & SUPPLY_BLOCKER_MODULES),
        "delivery_mode": delivery_mode,
        "decision": decision,
        "evidence_grade": evidence_grade,
        "score": round(score, 3),
        "data_gaps": blocking_gaps,
        "blocking_gaps": blocking_gaps,
        "warnings": warnings,
        "counts": counts,
        "supplier_quote_gate": supplier_gate,
        "supplier_quality_gate": supplier_quality_gate,
        "keyword_duplicate_gate": keyword_duplicate_gate,
        "keyword_customer_intent_gate": keyword_customer_intent_gate,
        "keyword_mapping_gate": keyword_mapping_gate,
        "applied_waivers": applied_waivers,
        "competitor_gate": {
            "minimum_total": competitor_minimum,
            "valid_total": len(competitor_products),
            "minimum_per_primary_segment": MIN_COMPETITORS_PER_PRIMARY_SEGMENT if standard_like else 0,
            "segments": competitor_segments,
            "underfilled_segments": underfilled_segments,
            "passed": len(competitor_products) >= competitor_minimum and segment_depth_gate_passed and (not broad_research or not underfilled_segments),
        },
        "segment_gate": {
            "broad_research": broad_research,
            "required_segments": MIN_BROAD_MARKET_SEGMENTS if broad_research else 0,
            "segments": competitor_segments,
            "underfilled_segments": underfilled_segments,
            "passed": segment_gate_passed,
            "depth_passed": segment_depth_gate_passed,
        },
        "collector_commands": collector_commands(report_dir),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check whether a report Data Pack is ready for standard/deep rendering.")
    parser.add_argument("--dir", required=True, type=Path, help="Report directory containing data/data_pack.json.")
    parser.add_argument("--depth", choices=["auto", "quick", "standard", "deep"], default="auto")
    parser.add_argument("--write", action="store_true", help="Write data/normalized/data_readiness_report.json.")
    args = parser.parse_args(argv)

    try:
        report = assess(args.dir, args.depth)
    except ReadinessError as exc:
        print(json.dumps({"acceptance_ready": False, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    if args.write:
        write_json(args.dir / "data" / "normalized" / "data_readiness_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["acceptance_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
