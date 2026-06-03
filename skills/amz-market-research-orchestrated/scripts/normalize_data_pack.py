#!/usr/bin/env python3
"""Cross-validate, dedupe, and enrich a generic market-research data_pack.json."""

from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlsplit, urlunsplit


ENTITY_KEYS = [
    "products",
    "keywords",
    "categories",
    "reviews",
    "tiktok_products",
    "tiktok_videos",
    "suppliers",
    "web_documents",
]

THEME_CN = {
    "performance": "性能与效果",
    "privacy": "隐私与信任",
    "quality": "质量与耐用",
    "durability": "质量与耐用",
    "usability": "易用性",
    "price": "价格与订阅",
    "shipping": "物流与包装",
    "support": "售后与客服",
    "safety": "安全与合规",
    "installation_mounting": "安装与固定",
    "battery_charging": "电池与充电",
    "quality_durability": "质量与耐用",
    "size_finish_design": "尺寸与外观",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_data_pack_defaults(data_pack: dict[str, Any]) -> None:
    for key in ENTITY_KEYS + ["categories", "data_gaps"]:
        if not isinstance(data_pack.get(key), list):
            data_pack[key] = []
    quality = data_pack.get("quality")
    if not isinstance(quality, dict):
        data_pack["quality"] = {"overall_score": 0.68, "grade": "low_confidence_watch"}


def normalization_baseline_path(report_dir: Path) -> Path:
    return report_dir / "data" / "normalized" / "normalization_baseline.json"


def baseline_counts(report_dir: Path, data_pack: dict[str, Any], current_counts: dict[str, int]) -> dict[str, int]:
    """Keep dedupe counts stable when the normalizer is run multiple times."""
    path = normalization_baseline_path(report_dir)
    if path.exists():
        baseline = load_json(path)
        counts = baseline.get("before_counts") or {}
        if counts:
            return {key: int(counts.get(key, current_counts[key])) for key in ENTITY_KEYS}

    previous = data_pack.get("normalization") or {}
    previous_counts = previous.get("before_counts") or {}
    if previous_counts and any(int(previous_counts.get(key, 0)) > current_counts[key] for key in ENTITY_KEYS):
        counts = {key: int(previous_counts.get(key, current_counts[key])) for key in ENTITY_KEYS}
    else:
        counts = current_counts

    write_json(path, {"before_counts": counts})
    return counts


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def normalized_key(value: Any) -> str:
    return normalize_text(value).casefold()


def fingerprint(value: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", normalized_key(value)))


def canonical_url(value: Any) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    try:
        parts = urlsplit(text)
    except ValueError:
        return normalized_key(text)
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    path = re.sub(r"/+$", "", parts.path or "")
    if not netloc:
        return re.sub(r"/+$", "", text.split("#", 1)[0].split("?", 1)[0]).casefold()
    return urlunsplit((scheme, netloc, path, "", ""))


def product_dedupe_key(item: dict[str, Any]) -> str:
    asin = normalized_key(item.get("asin"))
    if asin:
        return f"asin|{asin}"
    title = fingerprint(item.get("title") or item.get("title_cn"))
    brand = fingerprint(item.get("brand"))
    return f"title|{brand}|{title}" if title else ""


def has_cjk(value: Any) -> bool:
    return re.search(r"[\u4e00-\u9fff]", normalize_text(value)) is not None


def source_ids(entity: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for value in entity.get("source_ids") or []:
        if value and value not in ids:
            ids.append(str(value))
    if entity.get("source_id") and entity["source_id"] not in ids:
        ids.append(str(entity["source_id"]))
    return ids


def confidence_label(source_count: int) -> str:
    if source_count >= 3:
        return "high"
    if source_count == 2:
        return "medium"
    return "single_source"


def normalize_sources(data_pack: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Backfill legacy source metadata so every downstream lineage check has an audit handle."""
    sources = data_pack.get("sources") or []
    if not isinstance(sources, list):
        sources = []
    fetched_at = normalize_text(
        first_existing(data_pack.get("created_at"), data_pack.get("generated_at"), data_pack.get("updated_at"))
    ) or "unknown"

    normalized_sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx, source in enumerate(sources, 1):
        if not isinstance(source, dict):
            source = {"name": normalize_text(source)}
        source_id = normalize_text(source.get("source_id")) or f"src_legacy_{idx:03d}"
        if source_id in seen:
            suffix = 2
            candidate = f"{source_id}_{suffix}"
            while candidate in seen:
                suffix += 1
                candidate = f"{source_id}_{suffix}"
            source_id = candidate
        seen.add(source_id)
        source["source_id"] = source_id
        source["provider"] = normalize_text(first_existing(source.get("provider"), source.get("type"))) or "legacy_manual"
        source["tool"] = normalize_text(first_existing(source.get("tool"), source.get("method"), source.get("type"))) or "legacy_fixture"
        source["fetched_at"] = normalize_text(source.get("fetched_at")) or fetched_at
        source["confidence"] = first_existing(source.get("confidence"), "low")
        normalized_sources.append(source)

    data_pack["sources"] = normalized_sources
    return {source["source_id"]: source for source in normalized_sources}


def attach_entity_provider(data_pack: dict[str, Any], source_index: dict[str, dict[str, Any]]) -> None:
    for key in ENTITY_KEYS + ["categories"]:
        for entity in data_pack.get(key) or []:
            if not isinstance(entity, dict):
                continue
            source_id = normalize_text(entity.get("source_id"))
            source = source_index.get(source_id) if source_id else None
            if source and not entity.get("provider"):
                entity["provider"] = source.get("provider")


def prefer_value(current: Any, incoming: Any, field: str) -> Any:
    if incoming in (None, "", [], {}):
        return current
    if current in (None, "", [], {}):
        return incoming
    if field in {"title", "description", "attributes"}:
        return incoming if len(str(incoming)) > len(str(current)) else current
    if field in {"estimated_monthly_sales", "estimated_monthly_revenue", "review_count", "weekly_search_volume", "monthly_search_volume", "competitor_count", "sales_30d", "views", "likes"}:
        try:
            return incoming if float(incoming) > float(current) else current
        except (TypeError, ValueError):
            return current
    return current


def merge_group(records: list[dict[str, Any]], key: str, source_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    merged = deepcopy(records[0])
    ids: list[str] = []
    providers: list[str] = []
    tools: list[str] = []
    conflicts: list[dict[str, Any]] = []

    for record in records:
        for source_id in source_ids(record):
            if source_id not in ids:
                ids.append(source_id)
                source = source_index.get(source_id, {})
                if source.get("provider") and source["provider"] not in providers:
                    providers.append(source["provider"])
                if source.get("tool") and source["tool"] not in tools:
                    tools.append(source["tool"])

        for field, value in record.items():
            if field in {"source_id", "source_ids", "validation"}:
                continue
            old = merged.get(field)
            new_value = prefer_value(old, value, field)
            if old not in (None, "", [], {}) and value not in (None, "", [], {}) and old != value and field in {"price", "estimated_monthly_sales", "review_count", "monthly_search_volume"}:
                conflicts.append({"field": field, "values": [old, value]})
            merged[field] = new_value

    merged["source_id"] = ids[0] if ids else merged.get("source_id")
    merged["source_ids"] = ids
    merged["validation"] = {
        "dedupe_key": key,
        "evidence_source_count": len(ids),
        "cross_validated": len(ids) >= 2,
        "providers": providers or sorted(set(record.get("provider") for record in records if record.get("provider"))),
        "tools": tools,
        "confidence": confidence_label(len(ids)),
        "conflicts": conflicts[:12],
    }
    return merged


def dedupe(records: list[dict[str, Any]], key_func: Callable[[dict[str, Any]], str], source_index: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    passthrough: list[dict[str, Any]] = []
    for idx, record in enumerate(records):
        key = key_func(record)
        if not key:
            passthrough.append(record)
            continue
        groups.setdefault(key, []).append(record)
    merged = [merge_group(records, key, source_index) for key, records in groups.items()]
    merged.extend(passthrough)
    return merged


def keyword_dedupe_key(item: dict[str, Any]) -> str:
    keyword = normalized_key(item.get("keyword"))
    if not keyword:
        return ""
    source_type = normalized_key(item.get("source_type"))
    asin = normalized_key(item.get("asin"))
    if source_type == "product_traffic_terms" or asin:
        return f"traffic|{asin}|{keyword}" if asin else f"traffic|{keyword}"
    return f"market|{keyword}"


def review_dedupe_key(item: dict[str, Any]) -> str:
    text = first_existing(item.get("text"), item.get("content"), item.get("body"), item.get("comment"))
    return "|".join(
        [
            normalized_key(item.get("asin")),
            normalized_key(item.get("review_date") or item.get("date")),
            fingerprint(item.get("title")),
            fingerprint(text)[:120],
        ]
    )


def supplier_dedupe_key(item: dict[str, Any]) -> str:
    url = canonical_url(item.get("url"))
    if url:
        return f"url|{url}"
    product_id = normalized_key(item.get("product_id"))
    if product_id:
        return f"id|{product_id}"
    return "|".join(["title_store", fingerprint(item.get("title") or item.get("name")), fingerprint(item.get("store_name") or item.get("supplier_name"))])


def web_document_dedupe_key(item: dict[str, Any]) -> str:
    url = canonical_url(item.get("url"))
    if url:
        item["canonical_url"] = url
        return f"url|{url}"
    return f"title|{fingerprint(item.get('title'))}"


def tiktok_product_dedupe_key(item: dict[str, Any]) -> str:
    return normalized_key(item.get("product_id"))


def tiktok_video_dedupe_key(item: dict[str, Any]) -> str:
    return canonical_url(item.get("url")) or "|".join([normalized_key(item.get("product_id")), fingerprint(item.get("title")) or normalized_key(item.get("video_id"))])


def category_dedupe_key(item: dict[str, Any]) -> str:
    node_id = normalized_key(item.get("node_id") or item.get("category_id"))
    if node_id:
        return f"node|{node_id}"
    name = fingerprint(item.get("name") or item.get("category") or item.get("title"))
    return f"name|{name}" if name else ""


STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "by",
    "for",
    "from",
    "in",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "set",
    "pack",
    "pcs",
    "piece",
    "pieces",
}


def tokens(value: Any) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", normalized_key(value))
        if len(token) > 1 and token not in STOP_WORDS
    }


def infer_seed_terms(data_pack: dict[str, Any]) -> list[str]:
    seeds: list[str] = []

    def add(value: Any) -> None:
        text = normalized_key(value)
        if text and text not in seeds:
            seeds.append(text)

    research_object = data_pack.get("research_object") or {}
    if isinstance(research_object, dict):
        add(research_object.get("value"))
        for key in ("seed_keywords", "seed_asins"):
            for value in research_object.get(key) or []:
                add(value)
    else:
        add(research_object)

    brief = data_pack.get("brief") or {}
    brief_object = brief.get("research_object") if isinstance(brief, dict) else {}
    if isinstance(brief_object, dict):
        add(brief_object.get("value"))
        for value in brief_object.get("seed_keywords") or []:
            add(value)

    for keyword in data_pack.get("keywords") or []:
        if keyword.get("source_type") == "keyword_detail":
            add(keyword.get("keyword"))
    return seeds


def keyword_cn(keyword: Any) -> str:
    text = normalize_text(keyword)
    return text or "待补充关键词"


def keyword_intent_cn(keyword: Any) -> str:
    text = normalized_key(keyword)
    if any(term in text for term in ["gift", "bundle", "set", "kit", "starter"]):
        return "礼品与组合购买需求"
    if any(term in text for term in ["kids", "children", "baby", "pet", "adult", "women", "men"]):
        return "人群与使用者需求"
    if any(term in text for term in ["replacement", "refill", "accessory", "parts", "cover", "case"]):
        return "配件、替换与复购需求"
    if any(term in text for term in ["outdoor", "waterproof", "portable", "travel"]):
        return "场景与耐用性需求"
    if any(term in text for term in ["battery", "rechargeable", "cordless", "wireless", "usb"]):
        return "供电、续航与便携需求"
    if any(term in text for term in ["smart", "ai", "app", "bluetooth", "voice", "interactive"]):
        return "智能与交互功能需求"
    return "核心品类与功能需求"


def keyword_relevance_cn(keyword: Any, seed_terms: list[str]) -> str:
    text = normalized_key(keyword)
    if not text:
        return "待判断"
    for seed in seed_terms:
        if seed and (seed in text or text in seed):
            return "高相关"
    seed_tokens = set().union(*(tokens(seed) for seed in seed_terms)) if seed_terms else set()
    keyword_tokens = tokens(text)
    if not seed_tokens or not keyword_tokens:
        return "待判断"
    overlap = len(seed_tokens & keyword_tokens)
    if overlap >= max(1, min(len(seed_tokens), len(keyword_tokens)) // 2):
        return "相邻相关"
    return "待判断"


def title_cn(title: Any, segment: Any = None) -> str:
    text = normalize_text(title)
    if has_cjk(text):
        return text
    segment_text = normalize_text(segment)
    if has_cjk(segment_text):
        return f"{segment_text}样本"
    return "竞品样本"


def infer_review_theme_keys(review: dict[str, Any]) -> list[str]:
    raw_text = " ".join(
        str(review.get(key) or "")
        for key in ("title", "title_cn", "summary_cn", "text", "content", "body", "comment", "quote_cn")
    )
    text = normalized_key(raw_text)
    rules = [
        ("privacy", ["privacy", "policy", "data", "record", "recording", "permission", "personal information"]),
        ("performance", ["not work", "doesn't work", "stopped working", "stop working", "broken", "defective", "fail", "failed", "不亮", "亮度", "不够亮", "失效", "不工作", "故障", "闪烁", "照射"]),
        ("battery_charging", ["battery", "charge", "charging", "recharge", "usb", "电池", "续航", "充电", "掉电", "不耐用", "容量"]),
        ("usability", ["confusing", "hard to use", "setup", "connect", "bluetooth", "wifi", "app", "遥控", "触控", "配对", "串扰", "操作", "开关"]),
        ("quality_durability", ["quality", "durable", "durability", "cheap", "material", "fall apart", "做工", "破损", "缺件", "材质", "粗糙", "断裂", "进水"]),
        ("price", ["subscription", "fee", "expensive", "price", "refund", "return"]),
        ("shipping", ["shipping", "package", "packaging", "box", "arrived"]),
        ("support", ["support", "service", "customer service", "warranty"]),
        ("safety", ["safe", "safety", "hazard", "warning", "certification", "安全", "过热", "烧焦", "起火", "短路", "温升"]),
        ("installation_mounting", ["install", "mount", "adhesive", "magnet", "screw", "安装", "打孔", "胶贴", "磁吸", "孔位", "固定", "支架"]),
        ("size_finish_design", ["size", "finish", "design", "color", "glass", "shade", "尺寸", "外观", "玻璃", "灯罩", "色差", "造型"]),
    ]
    themes: list[str] = []
    for key, needles in rules:
        if any(needle in text for needle in needles):
            themes.append(key)
    return themes


def review_summary_cn(review: dict[str, Any]) -> str:
    explicit = normalize_text(review.get("summary_cn") or review.get("text_cn") or review.get("quote_cn"))
    if explicit:
        return explicit

    raw_title = normalize_text(review.get("title"))
    raw_text = normalize_text(first_existing(review.get("text"), review.get("content"), review.get("body"), review.get("comment")))
    if has_cjk(raw_text):
        return raw_text
    if has_cjk(raw_title):
        return raw_title

    text = normalized_key(f"{raw_title} {raw_text}")
    phrases: list[str] = []
    if any(term in text for term in ["stopped working", "stop working", "not work", "doesn't work", "broken", "defective", "failed"]):
        phrases.append("短期使用后出现失效")
    if any(term in text for term in ["two days", "2 days", "after a day", "after one day", "within days"]):
        phrases.append("用户对耐用性和稳定性信任下降")
    if any(term in text for term in ["privacy", "policy", "data", "record", "recording", "permission"]):
        phrases.append("隐私政策和数据使用说明不够清晰")
    if any(term in text for term in ["confusing", "hard to use", "setup", "connect", "bluetooth", "wifi", "app"]):
        phrases.append("上手配置和使用路径需要更清楚")
    if any(term in text for term in ["battery", "charge", "charging", "recharge", "usb"]):
        phrases.append("续航或充电体验没有达到预期")
    if any(term in text for term in ["cheap", "quality", "material", "durable", "fall apart"]):
        phrases.append("材质做工和耐用性需要加强")
    if any(term in text for term in ["refund", "return", "warranty", "support", "service"]):
        phrases.append("售后承诺需要前置说明")
    if any(term in text for term in ["love", "cute", "fun", "gift", "kids", "daughter", "son"]):
        phrases.append("正向反馈集中在开箱、陪伴和礼品场景")

    if not phrases:
        rating = as_number(review.get("rating"))
        if rating and rating <= 3:
            phrases.append("负面反馈集中在体验未达预期")
        elif rating and rating >= 4:
            phrases.append("正向反馈集中在使用满意度和场景匹配")
        else:
            phrases.append("用户反馈需要继续归类后再转成需求动作")

    unique: list[str] = []
    for phrase in phrases:
        if phrase not in unique:
            unique.append(phrase)
    return "；".join(unique[:3])


def review_title_cn(review: dict[str, Any]) -> str:
    explicit = normalize_text(review.get("title_cn"))
    if explicit:
        return explicit
    themes = review.get("themes_cn") or []
    if isinstance(themes, str):
        themes = [themes]
    if themes:
        return "、".join(themes[:2])
    rating = as_number(review.get("rating"))
    return "负面体验反馈" if rating and rating <= 3 else "正向体验反馈"


def first_existing(*values: Any) -> Any:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return ""


def as_number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def enrich_product(product: dict[str, Any]) -> dict[str, Any]:
    product["title_cn"] = product.get("title_cn") or title_cn(product.get("title"), first_existing(product.get("segment_cn"), product.get("segment")))
    product["segment_cn"] = product.get("segment_cn") or normalize_text(product.get("segment")) or "未分层"
    product["segment"] = product.get("segment") or product["segment_cn"]
    product["positioning_cn"] = product.get("positioning_cn") or product["title_cn"]
    return product


def enrich_keyword(keyword: dict[str, Any], seed_terms: list[str]) -> dict[str, Any]:
    keyword["keyword_cn"] = keyword_cn(keyword.get("keyword"))
    keyword["intent_cn"] = keyword_intent_cn(keyword.get("keyword"))
    keyword["relevance_cn"] = keyword.get("relevance_cn") or keyword_relevance_cn(keyword.get("keyword"), seed_terms)
    keyword["is_core_relevant"] = keyword["relevance_cn"] == "高相关"
    keyword["recommended_use_cn"] = "主词验证" if keyword.get("source_type") == "keyword_detail" else "长尾、内容与广告拓词"
    return keyword


def enrich_review(review: dict[str, Any]) -> dict[str, Any]:
    explicit_themes = review.get("themes") or []
    explicit_themes_cn = review.get("themes_cn") or []
    if isinstance(explicit_themes, str):
        explicit_themes = [explicit_themes]
    if isinstance(explicit_themes_cn, str):
        explicit_themes_cn = [explicit_themes_cn]
    themes = list(explicit_themes) if explicit_themes else list(explicit_themes_cn)
    if not themes:
        themes = infer_review_theme_keys(review)
    review["themes"] = themes
    review["themes_cn"] = [THEME_CN.get(str(theme).casefold(), str(theme)) for theme in themes]
    review["summary_cn"] = review_summary_cn(review)
    review["title_cn"] = review_title_cn(review)
    return review


def upsert_gap(data_pack: dict[str, Any], module: str, reason: str, impact: str, next_step: str) -> None:
    gaps = data_pack.setdefault("data_gaps", [])
    for gap in gaps:
        if not isinstance(gap, dict):
            continue
        if gap.get("module") == module and gap.get("reason") == reason:
            gap.update({"impact": impact, "next_step": next_step})
            return
    gaps.append({"module": module, "reason": reason, "impact": impact, "next_step": next_step})


def apply_quality_caps(data_pack: dict[str, Any], after_counts: dict[str, int], cross_validated: dict[str, int]) -> None:
    quality = data_pack.setdefault("quality", {})
    raw_score = quality.get("overall_score")
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        score = 0.68
    caps: list[dict[str, Any]] = []
    if after_counts.get("reviews", 0) < 80:
        caps.append({"module": "review_sample_depth", "max_score": 0.74})
    non_keyword_cross = sum(value for key, value in cross_validated.items() if key != "keywords")
    if non_keyword_cross <= 0:
        caps.append({"module": "cross_validation_depth", "max_score": 0.74})
    if data_pack.get("data_gaps") and score > 0.84:
        caps.append({"module": "data_gap_visibility", "max_score": 0.84})
    if caps:
        capped = min([score, *[float(item["max_score"]) for item in caps]])
        quality["overall_score"] = round(capped, 2)
        if capped < score:
            quality["original_overall_score"] = score
            quality["score_adjustments"] = caps
        if capped < 0.75:
            quality["grade"] = "low_confidence_watch"
        elif capped < 0.85:
            quality["grade"] = quality.get("grade") or "medium_confidence"
    else:
        quality["overall_score"] = round(score, 2)


def normalize(report_dir: Path) -> dict[str, Any]:
    data_path = report_dir / "data" / "data_pack.json"
    data_pack = load_json(data_path)
    ensure_data_pack_defaults(data_pack)
    source_index = normalize_sources(data_pack)
    attach_entity_provider(data_pack, source_index)
    current_counts = {key: len(data_pack.get(key) or []) for key in ENTITY_KEYS}
    before_counts = baseline_counts(report_dir, data_pack, current_counts)
    seed_terms = infer_seed_terms(data_pack)

    for item in data_pack.get("web_documents") or []:
        if item.get("url"):
            item["canonical_url"] = canonical_url(item.get("url"))
    for item in data_pack.get("suppliers") or []:
        if item.get("url"):
            item["canonical_url"] = canonical_url(item.get("url"))

    data_pack["products"] = [enrich_product(product) for product in dedupe(data_pack.get("products") or [], product_dedupe_key, source_index)]
    data_pack["keywords"] = [enrich_keyword(keyword, seed_terms) for keyword in dedupe(data_pack.get("keywords") or [], keyword_dedupe_key, source_index)]
    data_pack["reviews"] = [enrich_review(review) for review in dedupe(data_pack.get("reviews") or [], review_dedupe_key, source_index)]
    data_pack["categories"] = dedupe(data_pack.get("categories") or [], category_dedupe_key, source_index)
    data_pack["tiktok_products"] = dedupe(data_pack.get("tiktok_products") or [], tiktok_product_dedupe_key, source_index)
    data_pack["tiktok_videos"] = dedupe(data_pack.get("tiktok_videos") or [], tiktok_video_dedupe_key, source_index)
    data_pack["suppliers"] = dedupe(data_pack.get("suppliers") or [], supplier_dedupe_key, source_index)
    data_pack["web_documents"] = dedupe(data_pack.get("web_documents") or [], web_document_dedupe_key, source_index)

    after_counts = {key: len(data_pack.get(key) or []) for key in ENTITY_KEYS}
    cross_validated = {
        key: sum(1 for item in data_pack.get(key, []) if (item.get("validation") or {}).get("cross_validated"))
        for key in ENTITY_KEYS
    }
    data_pack["normalization"] = {
        "deduped": True,
        "normalized_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "before_counts": before_counts,
        "after_counts": after_counts,
        "removed_counts": {key: before_counts[key] - after_counts[key] for key in ENTITY_KEYS},
        "cross_validated_counts": cross_validated,
        "rules": [
            "products deduped by ASIN",
            "products without ASIN deduped by normalized title fingerprint",
            "market keywords deduped by normalized English keyword",
            "ASIN traffic keywords deduped by ASIN + normalized English keyword",
            "reviews deduped by ASIN/date/title/text fingerprint",
            "tiktok_products deduped by product_id",
            "tiktok_videos deduped by canonical URL or product_id+title",
            "web_documents deduped by canonical URL with query and fragment removed",
            "suppliers deduped by canonical URL, product_id, or title+store",
            "English keyword/title fields copied into audit-friendly display fields; relevance is inferred from research_object/seed keyword overlap",
        ],
    }
    if after_counts.get("keywords", 0) < 1000:
        upsert_gap(
            data_pack,
            "keyword_sample_depth",
            f"标准/深度版关键词样本不足 1000，当前 {after_counts.get('keywords', 0)}。",
            "需求结构、关键词机会和内容选题只能做方向判断，不能做完整优先级排序。",
            "继续分页采集 category_keywords 与 keyword_extends，直到归一化后关键词样本 >=1000。",
        )
    if after_counts.get("reviews", 0) < 80:
        upsert_gap(
            data_pack,
            "review_sample_depth",
            f"评论样本不足建议门槛 80，当前 {after_counts.get('reviews', 0)}。",
            "VOC、APPEALS、KANO/JTBD 和用户原声只能作为初步线索，不能写成精确市场占比。",
            "对核心 ASIN 补采 Positive/Neutral/Negative 评论，优先达到 80 条，深度版建议 200 条以上。",
        )
    apply_quality_caps(data_pack, after_counts, cross_validated)
    data_pack["cleaning_summary"] = data_pack["normalization"]

    write_json(data_path, data_pack)
    write_json(report_dir / "data" / "normalized" / "normalized_data_pack.json", data_pack)
    write_json(report_dir / "data" / "normalized" / "cross_validated_data_pack.json", data_pack)
    return data_pack


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cross-validate, dedupe, and enrich a market research data_pack.json.")
    parser.add_argument("--dir", required=True, help="Report directory containing data/data_pack.json.")
    args = parser.parse_args(argv)
    data_pack = normalize(Path(args.dir))
    print(json.dumps(data_pack["normalization"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
