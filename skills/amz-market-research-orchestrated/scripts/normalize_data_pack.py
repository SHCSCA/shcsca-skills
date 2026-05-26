#!/usr/bin/env python3
"""Cross-validate, dedupe, and enrich a v1 market-research data_pack.json."""

from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


ENTITY_KEYS = [
    "products",
    "keywords",
    "reviews",
    "tiktok_products",
    "tiktok_videos",
    "suppliers",
    "web_documents",
]

TITLE_TERMS = [
    ("battery operated wall sconce", "电池供电壁灯"),
    ("rechargeable wall sconce", "充电式壁灯"),
    ("wall sconces", "壁灯"),
    ("wall sconce", "壁灯"),
    ("wall light", "墙面灯"),
    ("wall lamp", "壁灯"),
    ("picture light", "画作照明灯"),
    ("gallery light", "画廊照明灯"),
    ("art display light", "艺术展示灯"),
    ("outdoor wall light", "户外壁灯"),
    ("outdoor wall lantern", "户外墙灯"),
    ("porch light", "门廊灯"),
    ("vanity light", "浴室镜前灯"),
    ("bathroom light", "浴室灯"),
    ("set of 2", "两只装"),
    ("2 pack", "两只装"),
    ("remote", "遥控"),
    ("dimmable", "可调光"),
    ("cordless", "免布线"),
    ("wireless", "无线"),
    ("waterproof", "防水"),
    ("glass shade", "玻璃灯罩"),
    ("gold", "金色"),
    ("black", "黑色"),
    ("led", "LED"),
    ("led lights", "LED灯"),
    ("strip lights", "灯带"),
    ("under cabinet lighting", "橱柜灯"),
    ("closet lights", "衣柜灯"),
    ("night light", "夜灯"),
    ("motion sensor", "人体感应"),
    ("warm white", "暖白光"),
    ("color temperature", "色温"),
    ("front door", "前门"),
    ("hallway", "走廊"),
    ("bedroom", "卧室"),
    ("living room", "客厅"),
]

KEYWORD_MAP = {
    "wall sconce": "壁灯",
    "wall sconces": "壁灯",
    "wall scones": "壁灯",
    "sconce lights": "壁灯",
    "light sconces": "壁灯",
    "wall sconce set of two": "两只装壁灯",
    "wall sconces set of two": "两只装壁灯",
    "wall sconces set of 2": "两只装壁灯",
    "sconces set of 2": "两只装壁灯",
    "sconces wall decor set of 2": "两只装装饰壁灯",
    "battery operated wall sconce": "电池供电壁灯",
    "battery operated wall sconces": "电池供电壁灯",
    "wall sconces battery operated": "电池供电壁灯",
    "rechargeable wall sconce": "充电式壁灯",
    "outdoor wall light": "户外壁灯",
    "outdoor wall lantern": "户外墙灯",
    "picture light": "画作照明灯",
    "picture lights for wall": "画作照明灯",
    "gallery light": "画廊照明灯",
    "wall light": "墙面灯",
    "wall lights": "墙面灯",
    "wall sconce light": "壁灯",
    "wall lamp": "壁灯",
    "sconce": "壁灯",
    "sconces": "壁灯",
    "lampara de pared": "壁灯",
    "bathroom light fixtures": "浴室灯具",
    "bathroom lighting fixtures over mirror": "浴室镜前灯",
    "bathroom vanity light": "浴室镜前灯",
    "vanity lights for bathroom": "浴室镜前灯",
    "vanity lights": "镜前灯",
    "wall decor": "墙面装饰",
    "wall decor for bedroom": "卧室墙面装饰",
    "living room wall decor": "客厅墙面装饰",
    "bedroom wall sconces": "卧室壁灯",
    "wall sconces for bedroom": "卧室壁灯",
    "room decor": "房间装饰",
    "led lights": "LED灯",
    "led strip lights": "LED灯带",
    "strip lights": "灯带",
    "night light": "夜灯",
    "night lights": "夜灯",
    "under cabinet lighting": "橱柜灯",
    "closet lights": "衣柜灯",
    "motion sensor light": "人体感应灯",
}

SEGMENT_CN = {
    "picture/gallery light": "画作/画廊照明",
    "outdoor wall light": "户外壁灯",
    "vanity light": "浴室镜前灯",
    "rechargeable wall sconce": "充电式壁灯",
    "general wall sconce": "通用壁灯",
    "night light": "夜灯",
    "out-of-scope wall light": "非目标泛灯具",
}

THEME_CN = {
    "installation_mounting": "安装/固定",
    "battery_charging": "电池/充电",
    "brightness_color": "亮度/色温",
    "remote_timer_controls": "遥控/定时",
    "quality_durability": "质量/耐用",
    "size_finish_design": "尺寸/外观",
    "outdoor_weather": "户外/耐候",
    "glass_damage": "玻璃/破损",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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


def keyword_cn(keyword: Any) -> str:
    text = normalized_key(keyword)
    if text in KEYWORD_MAP:
        return KEYWORD_MAP[text]
    translated = text
    for source, target in sorted(KEYWORD_MAP.items(), key=lambda item: len(item[0]), reverse=True):
        translated = translated.replace(source, target)
    if translated != text:
        return translated
    for source, target in TITLE_TERMS:
        translated = translated.replace(source, target)
    return translated if translated != text else "待人工翻译"


def keyword_intent_cn(keyword: Any) -> str:
    text = normalized_key(keyword)
    if any(term in text for term in ["battery", "rechargeable", "cordless", "wireless"]):
        return "免布线/充电需求"
    if any(term in text for term in ["outdoor", "porch", "lantern", "waterproof"]):
        return "户外照明/耐候需求"
    if any(term in text for term in ["picture", "gallery", "art"]):
        return "画作/装饰照明需求"
    if any(term in text for term in ["vanity", "bathroom"]):
        return "浴室镜前灯需求"
    if any(term in text for term in ["decor", "room"]):
        return "家居装饰泛需求"
    if any(term in text for term in ["led lights", "strip lights", "under cabinet", "night light", "closet"]):
        return "相邻照明泛流量"
    return "壁灯泛品类需求"


def keyword_relevance_cn(keyword: Any) -> str:
    text = normalized_key(keyword)
    high_terms = [
        "sconce",
        "sconces",
        "scones",
        "wall light",
        "wall lamp",
        "wall mounted light",
        "picture light",
        "gallery light",
        "art display light",
        "outdoor wall light",
        "outdoor wall lantern",
        "porch light",
        "vanity light",
        "bathroom light",
        "lampara de pared",
    ]
    adjacent_terms = [
        "wall decor",
        "room decor",
        "living room decor",
        "bedroom decor",
        "battery operated lamp",
        "cordless lamp",
        "rechargeable light",
    ]
    noise_terms = [
        "battery pack",
        "led lights",
        "strip lights",
        "under cabinet",
        "closet lights",
        "night light",
        "motion sensor light",
    ]
    if any(term in text for term in high_terms):
        return "高相关"
    if any(term in text for term in noise_terms):
        return "噪声/泛流量"
    if any(term in text for term in adjacent_terms):
        return "相邻相关"
    return "待判断"


def title_cn(title: Any, segment: Any = None) -> str:
    text = normalized_key(title)
    pieces: list[str] = []
    if segment and SEGMENT_CN.get(str(segment)):
        pieces.append(SEGMENT_CN[str(segment)])
    for source, target in TITLE_TERMS:
        if source in text and target not in pieces:
            pieces.append(target)
    if not pieces:
        return "英文标题待人工精翻"
    return " / ".join(pieces[:8])


def enrich_product(product: dict[str, Any]) -> dict[str, Any]:
    product["title_cn"] = title_cn(product.get("title"), product.get("segment"))
    product["segment_cn"] = SEGMENT_CN.get(str(product.get("segment")), "未分层")
    product["positioning_cn"] = product["title_cn"]
    return product


def enrich_keyword(keyword: dict[str, Any]) -> dict[str, Any]:
    keyword["keyword_cn"] = keyword_cn(keyword.get("keyword"))
    keyword["intent_cn"] = keyword_intent_cn(keyword.get("keyword"))
    keyword["relevance_cn"] = keyword_relevance_cn(keyword.get("keyword"))
    keyword["is_core_relevant"] = keyword["relevance_cn"] == "高相关"
    keyword["recommended_use_cn"] = "主词验证" if keyword.get("source_type") == "keyword_detail" else "长尾/内容/广告拓词"
    return keyword


def enrich_review(review: dict[str, Any]) -> dict[str, Any]:
    themes = review.get("themes") or []
    review["themes_cn"] = [THEME_CN.get(theme, theme) for theme in themes]
    return review


def normalize(report_dir: Path) -> dict[str, Any]:
    data_path = report_dir / "data" / "data_pack.json"
    data_pack = load_json(data_path)
    source_index = {source.get("source_id"): source for source in data_pack.get("sources", [])}
    current_counts = {key: len(data_pack.get(key) or []) for key in ENTITY_KEYS}
    before_counts = baseline_counts(report_dir, data_pack, current_counts)

    data_pack["products"] = [enrich_product(product) for product in dedupe(data_pack.get("products") or [], lambda item: normalized_key(item.get("asin")), source_index)]
    data_pack["keywords"] = [enrich_keyword(keyword) for keyword in dedupe(data_pack.get("keywords") or [], keyword_dedupe_key, source_index)]
    data_pack["reviews"] = [enrich_review(review) for review in dedupe(data_pack.get("reviews") or [], lambda item: "|".join([normalized_key(item.get("asin")), normalized_key(item.get("review_date")), normalized_key(item.get("title")), normalized_key(item.get("text"))[:90]]), source_index)]
    data_pack["tiktok_products"] = dedupe(data_pack.get("tiktok_products") or [], lambda item: normalized_key(item.get("product_id")), source_index)
    data_pack["tiktok_videos"] = dedupe(data_pack.get("tiktok_videos") or [], lambda item: normalized_key(item.get("url")) or "|".join([normalized_key(item.get("product_id")), normalized_key(item.get("title"))]), source_index)
    data_pack["suppliers"] = dedupe(data_pack.get("suppliers") or [], lambda item: normalized_key(item.get("product_id")) or normalized_key(item.get("url")) or "|".join([normalized_key(item.get("title")), normalized_key(item.get("store_name"))]), source_index)
    data_pack["web_documents"] = dedupe(data_pack.get("web_documents") or [], lambda item: normalized_key(item.get("url")), source_index)

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
            "market keywords deduped by normalized English keyword",
            "ASIN traffic keywords deduped by ASIN + normalized English keyword",
            "reviews deduped by ASIN/date/title/text fingerprint",
            "tiktok_products deduped by product_id",
            "tiktok_videos and web_documents deduped by URL",
            "suppliers deduped by product_id, URL, or title+store",
            "English keyword/title fields enriched with Chinese mapping fields",
        ],
    }

    write_json(data_path, data_pack)
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
