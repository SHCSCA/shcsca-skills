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
    "tiktok_authors",
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

KEYWORD_CN_RULES = [
    ("under cabinet", "橱柜灯"),
    ("under counter", "柜底灯"),
    ("cabinet light", "橱柜灯"),
    ("cabinet lights", "橱柜灯"),
    ("lights for cabinets", "橱柜灯"),
    ("light for cabinets", "橱柜灯"),
    ("sensor lights for cabinets", "橱柜人体感应灯"),
    ("sensor light for cabinets", "橱柜人体感应灯"),
    ("closet light", "衣柜灯"),
    ("closet lights", "衣柜灯"),
    ("light for closet", "衣柜灯"),
    ("lights for closet", "衣柜灯"),
    ("lights for closets", "衣柜灯"),
    ("closet motion light", "衣柜人体感应灯"),
    ("closet sensor light", "衣柜人体感应灯"),
    ("motion light for closet", "衣柜人体感应灯"),
    ("sensor light for closet", "衣柜人体感应灯"),
    ("luces para closet", "衣柜灯"),
    ("luz para closet", "衣柜灯"),
    ("closet led lights", "衣柜LED灯"),
    ("wardrobe light", "衣柜灯"),
    ("wardrobe lights", "衣柜灯"),
    ("pantry light", "储物间灯"),
    ("puck light", "圆形橱柜灯"),
    ("stick on", "免打孔粘贴"),
    ("adhesive", "胶贴安装"),
    ("battery operated", "电池供电"),
    ("indoor motion sensor", "室内人体感应"),
    ("motion light indoor", "室内人体感应灯"),
    ("motion lights indoor", "室内人体感应灯"),
    ("indoor motion light", "室内人体感应灯"),
    ("indoor motion lights", "室内人体感应灯"),
    ("motion activated light", "人体感应灯"),
    ("motion activated lights", "人体感应灯"),
    ("motion detector light", "人体感应灯"),
    ("motion detector lights", "人体感应灯"),
    ("motion sensor led light", "人体感应LED灯"),
    ("motion sensor rechargeable light", "可充电人体感应灯"),
    ("rechargeable motion light", "可充电人体感应灯"),
    ("motion sensor", "人体感应"),
    ("wireless", "无线"),
    ("rechargeable", "可充电"),
    ("usb rechargeable", "USB充电"),
    ("magnetic", "磁吸"),
    ("rgbic", "RGBIC"),
    ("rgb", "RGB"),
    ("led strip", "灯带"),
    ("strip lights", "灯带"),
    ("smart bulb", "智能灯泡"),
    ("light bulb", "灯泡"),
    ("outdoor", "户外"),
    ("solar", "太阳能"),
    ("wall sconce", "壁灯"),
    ("vanity light", "镜前灯"),
    ("night light", "夜灯"),
    ("table lamp", "台灯"),
    ("floor lamp", "落地灯"),
    ("smart lighting", "智能照明"),
    ("led lights", "LED灯"),
    ("lighting", "照明"),
]

EFFECTIVE_ENTITY_KEYS = [
    "effective_products",
    "effective_keywords",
    "effective_reviews",
    "effective_suppliers",
]

TITLE_SEGMENT_RULES = [
    ("橱柜感应灯", ["under cabinet", "cabinet light", "motion sensor", "puck light"]),
    ("RGB 灯带", ["rgbic", "rgb led strip", "led strip", "strip lights", "light strip"]),
    ("智能灯泡", ["smart bulb", "a19", "light bulb"]),
    ("户外感应灯", ["outdoor", "solar", "security light", "flood light", "wall sconce"]),
    ("氛围灯", ["ambient", "night light", "table lamp", "sunset"]),
]

HUNTING_BLINDS_SEGMENT_RULES = [
    ("透视地面盲棚", ["see through", "see-through", "one-way", "one way", "270", "360"]),
    ("弹出式地面盲棚", ["pop up", "pop-up", "hub style", "hub blind", "ground blind"]),
    ("多人狩猎盲棚", ["2 person", "3 person", "4 person", "two person", "three person", "four person"]),
    ("椅式单人盲棚", ["chair blind", "blind chair", "one man", "1 man", "1/2 man"]),
    ("塔式/箱式盲棚", ["tower blind", "box blind", "elevated", "stand blind"]),
    ("水禽/布局盲棚", ["duck blind", "layout blind", "waterfowl"]),
]

LIGHTING_RESEARCH_TOKENS = {
    "smart lighting",
    "lighting",
    "led lighting",
    "智能照明",
    "灯具",
    "灯饰",
}

CABINET_CLOSET_RESEARCH_TOKENS = {
    "under cabinet",
    "under counter",
    "cabinet light",
    "cabinet lights",
    "closet light",
    "closet lights",
    "wardrobe light",
    "wardrobe lights",
    "motion sensor cabinet",
    "rechargeable closet",
    "magnetic under cabinet",
    "indoor motion sensor light",
    "indoor motion sensor lights",
    "motion light indoor",
    "motion lights indoor",
    "indoor motion light",
    "indoor motion lights",
    "motion activated light indoor",
    "motion detector lights for inside",
    "室内感应灯",
    "室内人体感应灯",
    "橱柜灯",
    "橱柜感应灯",
    "衣柜灯",
    "衣柜感应灯",
    "柜底灯",
}

UNDER_CABINET_CATEGORY_RESEARCH_TOKENS = {
    "under-cabinet lights",
    "under cabinet lights",
    "under-cabinet light",
    "under cabinet light",
    "under-counter light fixtures",
    "under counter light fixtures",
    "under-counter lights",
    "under counter lights",
}

CABINET_CLOSET_PRODUCT_SIGNALS = [
    "under cabinet",
    "under counter",
    "cabinet light",
    "cabinet lights",
    "closet light",
    "closet lights",
    "wardrobe light",
    "wardrobe lights",
    "puck light",
    "puck lights",
    "stick on light",
    "stick on lights",
    "motion sensor light",
    "motion sensor lights",
    "indoor motion sensor light",
    "indoor motion sensor lights",
    "motion light indoor",
    "motion lights indoor",
    "indoor motion light",
    "indoor motion lights",
    "motion activated light",
    "motion activated lights",
    "motion detector light",
    "motion detector lights",
    "motion sensor led light",
    "motion sensor rechargeable light",
    "rechargeable motion light",
    "rechargeable motion lights",
    "automatic light",
    "automatic lights",
    "sensor light indoor",
    "sensor lights indoor",
    "battery operated light",
    "battery operated lights",
    "rechargeable light",
    "rechargeable lights",
    "magnetic light",
    "magnetic lights",
    "pantry light",
    "kitchen cabinet",
    "橱柜灯",
    "橱柜感应灯",
    "感应橱柜灯",
    "柜底灯",
    "衣柜灯",
    "衣柜感应灯",
    "人体感应灯",
    "充电感应灯",
    "磁吸感应灯",
]

CABINET_CLOSET_FUNCTION_SIGNALS = [
    "motion sensor",
    "sensor",
    "pir",
    "motion activated",
    "motion detector",
    "rechargeable",
    "battery",
    "wireless",
    "cordless",
    "usb",
    "magnetic",
    "adhesive",
    "stick on",
    "puck",
    "under cabinet",
    "under counter",
    "closet",
    "wardrobe",
    "pantry",
    "感应",
    "人体感应",
    "充电",
    "电池",
    "无线",
    "磁吸",
    "胶贴",
    "免打孔",
]

CABINET_CLOSET_MOTION_TERMS = [
    "motion sensor",
    "motion activated",
    "motion detector",
    "motion sensing",
    "motion sensored",
    "motion light",
    "motion lights",
    "auto lights motion",
    "pir",
    "human body sensing",
    "sensor de movimiento",
    "sensores de movimiento",
    "人体感应",
    "红外感应",
]

CABINET_CLOSET_LIGHT_TERMS = [
    "light",
    "lights",
    "lighting",
    "lamp",
    "lampara",
    "lamparas",
    "luz",
    "luces",
    "led",
    "灯",
    "照明",
]

CABINET_CLOSET_SCENE_TERMS = [
    "cabinet",
    "cabinets",
    "closet",
    "closets",
    "wardrobe",
    "wardrobes",
    "cupboard",
    "cupboards",
    "under counter",
    "undercounter",
    "counter lights",
    "under shelf",
    "under shelves",
    "shelf lighting",
    "shelf lights",
    "drawer light",
    "drawer lights",
    "stair light",
    "stair lights",
    "safe light",
    "safe lights",
    "push light",
    "push lights",
    "stick up light",
    "stick up lights",
    "peel and stick light",
    "peel and stick lights",
    "touch light",
    "touch lights",
    "wireless light",
    "wireless lights",
    "battery powered light",
    "battery powered lights",
    "battery operated light",
    "battery operated lights",
    "rechargeable light",
    "rechargeable lights",
    "lights without wiring",
    "light without wiring",
    "under kitchen cabinet",
    "under kitchen cabinets",
    "kitchen cabinet",
    "kitchen cabinets",
    "gabinete",
    "gabinetes",
    "debajo gabinete",
    "debajo de gabinetes",
    "橱柜",
    "衣柜",
    "柜底",
]

CABINET_CLOSET_LIGHT_SENSOR_ONLY_TERMS = [
    "dusk to dawn",
    "light sensor",
    "photocell",
    "光控",
]

CABINET_CLOSET_STRIP_TERMS = [
    "light strip",
    "light strips",
    "strip light",
    "strip lights",
    "led strip",
    "led strips",
]

CABINET_CLOSET_STRIP_ALLOWED_TERMS = [
    "under cabinet",
    "cabinet",
    "under counter",
    "counter",
    "under shelf",
    "shelf",
    "closet",
    "wardrobe",
    "motion",
    "sensor",
    "橱柜",
    "衣柜",
    "感应",
]

CABINET_CLOSET_HARD_NOISE = [
    "outdoor",
    "outdoor light",
    "solar",
    "security light",
    "flood light",
    "wall sconce",
    "porch",
    "patio",
    "garden",
    "landscape",
    "flashlight",
    "flashlights",
    "headlamp",
    "head lamp",
    "camping",
    "hiking",
    "fishing",
    "bedside",
    "bedroom decor",
    "table lamp",
    "floor lamp",
    "smart bulb",
    "light bulb",
    "a19",
    "string lights",
    "tv backlight",
    "grow light",
    "ceiling light",
    "ceiling lights",
    "techo",
    "overhead lighting",
    "garage light",
    "bathroom vanity",
    "rgb strip",
    "rgbic",
    "govee",
    "户外",
    "太阳能",
    "投光灯",
    "庭院",
    "景观",
    "床头灯",
    "装饰灯",
    "台灯",
    "落地灯",
    "灯泡",
    "电视背光",
    "植物灯",
    "吸顶灯",
]

CABINET_CLOSET_KEYWORD_SIGNALS = [
    "under cabinet",
    "under counter",
    "cabinet light",
    "cabinet lights",
    "closet light",
    "closet lights",
    "wardrobe light",
    "wardrobe lights",
    "puck light",
    "puck lights",
    "stick on light",
    "stick on lights",
    "motion sensor light",
    "motion sensor lights",
    "battery operated closet",
    "battery operated under cabinet",
    "rechargeable closet",
    "rechargeable under cabinet",
    "wireless under cabinet",
    "magnetic closet",
    "magnetic under cabinet",
    "pantry light",
    "kitchen cabinet light",
    "indoor motion sensor light",
    "indoor motion sensor lights",
    "motion light indoor",
    "motion lights indoor",
    "indoor motion light",
    "indoor motion lights",
    "motion activated light",
    "motion activated lights",
    "motion detector light",
    "motion detector lights",
    "motion sensor led light",
    "motion sensor rechargeable light",
    "rechargeable motion light",
    "rechargeable motion lights",
    "automatic light",
    "automatic lights",
    "sensor lights indoor",
    "sensor light indoor",
    "closet motion light",
    "motion light for closet",
    "motion lights for closets",
    "closet sensor light",
    "sensor light for closet",
    "sensor lights for closet",
    "lights for closet",
    "lights for closets",
    "light for closet",
    "battery lights for closet",
    "battery light for closet",
    "rechargeable light for closet",
    "sensor lights for cabinets",
    "lights for cabinets",
    "luces para closet",
    "luz para closet",
    "橱柜灯",
    "橱柜感应灯",
    "衣柜灯",
    "衣柜感应灯",
    "柜底灯",
    "人体感应灯",
    "充电感应灯",
    "磁吸感应灯",
]

LIGHTING_PRODUCT_SIGNALS = [
    "light",
    "lighting",
    "lamp",
    "led",
    "bulb",
    "strip",
    "cabinet",
    "under cabinet",
    "motion sensor",
    "puck",
    "closet",
    "sconce",
    "vanity",
    "night light",
    "ambient",
    "rgb",
    "rgbic",
    "solar",
    "outdoor light",
    "security light",
    "flood light",
    "橱柜灯",
    "感应灯",
    "灯带",
    "灯泡",
    "壁灯",
    "镜前灯",
    "夜灯",
    "氛围灯",
    "户外灯",
    "太阳能灯",
    "智能照明",
]

LIGHTING_KEYWORD_SIGNALS = [
    "smart light",
    "smart lighting",
    "led light",
    "led lights",
    "under cabinet",
    "under cabinet light",
    "under cabinet lights",
    "under cabinet lighting",
    "under counter",
    "under counter light",
    "under counter lights",
    "under counter lighting",
    "under-counter light",
    "under-counter lights",
    "cabinet light",
    "cabinet lights",
    "cabinet lighting",
    "cupboard light",
    "cupboard lights",
    "cupboard lighting",
    "closet light",
    "closet lights",
    "closet lighting",
    "closet motion light",
    "closet motion sensor light",
    "motion sensor closet light",
    "motion sensor closet lights",
    "wardrobe light",
    "wardrobe lights",
    "puck light",
    "puck lights",
    "drawer light",
    "drawer lights",
    "shelf light",
    "shelf lights",
    "shelf lighting",
    "stick up light",
    "stick up lights",
    "peel and stick lights",
    "push light",
    "push lights",
    "wireless light",
    "wireless lights",
    "rechargeable light",
    "rechargeable lights",
    "battery operated light",
    "battery operated lights",
    "battery powered light",
    "battery powered lights",
    "motion sensor light",
    "motion sensor lights",
    "motion sensor light indoor",
    "motion sensor lights indoor",
    "indoor motion sensor light",
    "indoor motion sensor lights",
    "motion activated light",
    "motion activated lights",
    "motion detector light",
    "motion detector lights",
    "motion light indoor",
    "motion lights indoor",
    "night light",
    "rgb light",
    "rgb lights",
    "rgbic",
    "led strip",
    "strip lights",
    "light strip",
    "smart bulb",
    "light bulb",
    "outdoor light",
    "outdoor lights",
    "solar light",
    "solar lights",
    "wall sconce",
    "vanity light",
    "ambient light",
    "橱柜灯",
    "感应灯",
    "灯带",
    "灯泡",
    "夜灯",
    "氛围灯",
    "户外灯",
    "智能照明",
]

LIGHTING_NOISE_TOKENS = [
    "owala",
    "water bottle",
    "bpa-free sports water bottle",
    "sports water bottle",
    "bottle",
    "tumbler",
    "hydro flask",
    "hydroflask",
    "stanley cup",
    "protein",
    "shake",
    "beverage",
    "energy drink",
    "room decor",
    "bedroom decor",
    "bathroom decor",
    "floor lamp",
    "table lamp",
    "camera",
    "video doorbell",
    "doorbell",
    "shampoo",
    "ventilador",
    "worldcup",
    "world cup",
]

LIGHTING_HARD_PRODUCT_NOISE = [
    "owala",
    "water bottle",
    "bpa-free sports water bottle",
    "sports water bottle",
    "bottle",
    "tumbler",
    "hydro flask",
    "hydroflask",
    "stanley cup",
    "protein",
    "shake",
    "beverage",
    "energy drink",
    "camera",
    "video doorbell",
    "doorbell",
    "shampoo",
    "ventilador",
    "worldcup",
    "world cup",
]

HUNTING_BLINDS_RESEARCH_TOKENS = {
    "hunting blind",
    "hunting blinds",
    "ground blind",
    "ground blinds",
    "deer blind",
    "deer blinds",
    "turkey blind",
    "turkey blinds",
    "see through hunting blind",
    "pop up hunting blind",
    "狩猎帐篷",
    "狩猎隐蔽帐篷",
    "狩猎盲",
}

HUNTING_BLINDS_PRODUCT_SIGNALS = [
    "hunting blind",
    "hunting blinds",
    "ground blind",
    "ground blinds",
    "deer blind",
    "deer blinds",
    "turkey blind",
    "turkey blinds",
    "pop up blind",
    "pop-up blind",
    "see through blind",
    "see-through blind",
    "one-way see through",
    "concealed shelter",
    "camouflage tent",
    "camo tent",
    "hub blind",
    "chair blind",
    "tower blind",
    "box blind",
    "bale blind",
    "shooting blind",
    "blind tent",
    "狩猎帐篷",
    "狩猎隐蔽帐篷",
    "迷彩帐篷",
    "伪装帐篷",
    "伪装棚",
]

HUNTING_BLINDS_KEYWORD_SIGNALS = [
    "hunting blind",
    "hunting blinds",
    "ground blind",
    "ground blinds",
    "deer blind",
    "deer blinds",
    "turkey blind",
    "turkey blinds",
    "pop up blind",
    "pop-up blind",
    "see through blind",
    "see-through blind",
    "360 blind",
    "hub blind",
    "chair blind",
    "tower blind",
    "box blind",
    "bale blind",
    "blind tent",
    "狩猎帐篷",
    "狩猎隐蔽帐篷",
    "迷彩帐篷",
    "伪装帐篷",
]

HUNTING_BLINDS_HARD_PRODUCT_NOISE = [
    "aluminum boat paint",
    "boat paint",
    "marine paint",
    "painting supplies",
    "paint for",
    "paint |",
    "camo netting",
    "camouflage netting",
    "camouflage net",
    "camo net",
    "face paint",
    "makeup",
    "socks",
    "deer feeder",
    "trail camera",
    "cellular trail camera",
    "tripod chairs",
    "tripod stool",
    "bucket backpack",
    "bracket",
    "brackets",
    "angle bracket",
    "tree stand bracket",
    "car cover",
    "party decoration",
]

GENERIC_CUSTOMER_LABELS = {
    "未命名竞品",
    "竞品记录",
    "未知",
    "未分层",
    "核心竞品",
}

LIGHTING_CUSTOMER_LABELS = {label for label, _needles in TITLE_SEGMENT_RULES}

HUNTING_BLINDS_KEYWORD_NOISE = [
    "outdoor lighting",
    "outdoor light",
    "outdoor lights",
    "led light",
    "led lights",
    "lighting",
    "lamp",
    "solar light",
    "camo netting",
    "camouflage netting",
    "camouflage net",
    "face paint",
    "socks",
    "deer feeder",
    "trail camera",
    "cellular camera",
    "tripod chair",
    "bracket",
    "car cover",
    "party decoration",
]

LIGHTING_CATEGORY_NOISE = [
    "sports & outdoors",
    "grocery",
    "beauty",
    "health",
]


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


def tiktok_author_dedupe_key(item: dict[str, Any]) -> str:
    return canonical_url(item.get("profile_url")) or normalized_key(item.get("author") or item.get("name"))


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


def contains_any(text: str, needles: list[str] | set[str]) -> bool:
    return any(needle in text for needle in needles)


def is_lighting_research(seed_terms: list[str]) -> bool:
    joined = " ".join(seed_terms).casefold()
    return any(term in joined for term in LIGHTING_RESEARCH_TOKENS)


def is_cabinet_closet_light_research(seed_terms: list[str]) -> bool:
    joined = " ".join(seed_terms).casefold()
    return any(term in joined for term in CABINET_CLOSET_RESEARCH_TOKENS)


def is_under_cabinet_category_research(seed_terms: list[str]) -> bool:
    joined = " ".join(seed_terms).casefold()
    return any(term in joined for term in UNDER_CABINET_CATEGORY_RESEARCH_TOKENS)


def is_hunting_blinds_research(seed_terms: list[str]) -> bool:
    joined = " ".join(seed_terms).casefold()
    return any(term in joined for term in HUNTING_BLINDS_RESEARCH_TOKENS)


def hunting_blind_segment(entity: dict[str, Any]) -> str:
    text = entity_search_text(
        entity,
        ["title", "title_cn", "category", "category_cn", "segment", "segment_cn", "subcategory", "seed_keyword"],
    )
    labels: list[str] = []
    for label, needles in HUNTING_BLINDS_SEGMENT_RULES:
        if any(needle in text for needle in needles):
            labels.append(label)
    if not labels:
        return "通用狩猎地面盲棚"
    if "透视地面盲棚" in labels and "弹出式地面盲棚" in labels:
        return "透视弹出式地面盲棚"
    return labels[0]


def is_placeholder_customer_label(value: Any) -> bool:
    text = normalize_text(value)
    if not text:
        return True
    return text in GENERIC_CUSTOMER_LABELS or text.startswith("未映射关键词")


def is_cross_domain_or_placeholder_label(value: Any) -> bool:
    text = normalize_text(value)
    if is_placeholder_customer_label(text):
        return True
    return text in LIGHTING_CUSTOMER_LABELS


def clear_customer_label_pollution(product: dict[str, Any]) -> None:
    for key in ("title_cn", "segment_cn", "positioning_cn"):
        if is_cross_domain_or_placeholder_label(product.get(key)):
            product.pop(key, None)
    if is_cross_domain_or_placeholder_label(product.get("segment")):
        product.pop("segment", None)


def entity_search_text(entity: dict[str, Any], fields: list[str]) -> str:
    return " ".join(normalized_key(entity.get(field)) for field in fields)


def product_relevance(product: dict[str, Any], seed_terms: list[str]) -> tuple[bool, str]:
    text = entity_search_text(
        product,
        ["title", "title_cn", "brand", "category", "category_cn", "segment", "segment_cn", "subcategory", "positioning_cn"],
    )
    cabinet_closet_mode = is_cabinet_closet_light_research(seed_terms)
    lighting_mode = is_lighting_research(seed_terms)
    hunting_blinds_mode = is_hunting_blinds_research(seed_terms)
    if cabinet_closet_mode:
        if contains_any(text, CABINET_CLOSET_HARD_NOISE):
            return False, "non_cabinet_closet_lighting_noise"
        if contains_any(text, CABINET_CLOSET_LIGHT_SENSOR_ONLY_TERMS) and not contains_any(text, CABINET_CLOSET_MOTION_TERMS):
            return False, "non_motion_light_sensor_only"
        if contains_any(text, CABINET_CLOSET_STRIP_TERMS) and not contains_any(text, CABINET_CLOSET_STRIP_ALLOWED_TERMS):
            return False, "non_motion_or_cabinet_light_strip"
        if contains_any(text, CABINET_CLOSET_MOTION_TERMS) and contains_any(text, CABINET_CLOSET_LIGHT_TERMS):
            return True, "indoor_motion_lighting_signal"
        if contains_any(text, CABINET_CLOSET_SCENE_TERMS) and contains_any(text, CABINET_CLOSET_LIGHT_TERMS):
            return True, "cabinet_closet_adjacent_light_signal"
        has_product_signal = contains_any(text, CABINET_CLOSET_PRODUCT_SIGNALS)
        has_function_signal = contains_any(text, CABINET_CLOSET_FUNCTION_SIGNALS)
        if has_product_signal and has_function_signal:
            return True, "cabinet_closet_lighting_signal"
        return False, "missing_cabinet_closet_lighting_signal"
    if lighting_mode:
        has_signal = contains_any(text, LIGHTING_PRODUCT_SIGNALS)
        if contains_any(text, LIGHTING_HARD_PRODUCT_NOISE):
            return False, "non_lighting_noise_token"
        if contains_any(text, LIGHTING_NOISE_TOKENS) and not has_signal:
            return False, "non_lighting_noise_token"
        category_noise = contains_any(text, LIGHTING_CATEGORY_NOISE)
        if category_noise and not has_signal:
            return False, "non_lighting_category"
        if not has_signal:
            return False, "missing_lighting_signal"
        return True, "lighting_signal"
    if hunting_blinds_mode:
        if contains_any(text, HUNTING_BLINDS_HARD_PRODUCT_NOISE):
            return False, "non_hunting_blind_accessory_or_noise"
        if contains_any(text, HUNTING_BLINDS_PRODUCT_SIGNALS):
            return True, "hunting_blind_signal"
        return False, "missing_hunting_blind_signal"

    seed_tokens = set().union(*(tokens(seed) for seed in seed_terms)) if seed_terms else set()
    product_tokens = tokens(text)
    if not seed_tokens:
        return True, "no_seed_keep_for_audit"
    if seed_tokens & product_tokens:
        return True, "seed_overlap"
    return False, "missing_seed_overlap"


def keyword_source_bucket(keyword: dict[str, Any]) -> str:
    source_type = normalized_key(keyword.get("source_type"))
    asin = normalized_key(keyword.get("asin"))
    if source_type == "product_traffic_terms" or asin:
        return f"traffic:{asin or 'unknown'}"
    return "market"


def keyword_relevance(
    keyword: dict[str, Any],
    seed_terms: list[str],
    valid_asins: set[str],
    product_context_tokens: set[str] | None = None,
) -> tuple[bool, str]:
    text = normalized_key(keyword.get("keyword"))
    if not text:
        return False, "missing_keyword"
    source_type = normalized_key(keyword.get("source_type"))
    asin = normalized_key(keyword.get("asin")).upper()
    if source_type == "product_traffic_terms" and asin and asin not in valid_asins:
        return False, "traffic_asin_not_effective"
    under_cabinet_category_mode = is_under_cabinet_category_research(seed_terms)
    cabinet_closet_mode = is_cabinet_closet_light_research(seed_terms)
    lighting_mode = is_lighting_research(seed_terms)
    hunting_blinds_mode = is_hunting_blinds_research(seed_terms)
    if under_cabinet_category_mode and source_type == "category_keywords":
        if contains_any(text, CABINET_CLOSET_HARD_NOISE):
            return False, "non_under_cabinet_category_keyword_noise"
        if contains_any(text, CABINET_CLOSET_LIGHT_SENSOR_ONLY_TERMS) and not (
            contains_any(text, CABINET_CLOSET_SCENE_TERMS) or contains_any(text, CABINET_CLOSET_MOTION_TERMS)
        ):
            return False, "non_motion_or_under_cabinet_light_sensor_only"
        if contains_any(text, CABINET_CLOSET_LIGHT_TERMS) or contains_any(text, CABINET_CLOSET_SCENE_TERMS):
            return True, "under_cabinet_category_keyword"
        return False, "missing_under_cabinet_category_signal"
    if cabinet_closet_mode:
        if contains_any(text, CABINET_CLOSET_HARD_NOISE):
            return False, "non_cabinet_closet_keyword_noise"
        if contains_any(text, CABINET_CLOSET_LIGHT_SENSOR_ONLY_TERMS) and not contains_any(text, CABINET_CLOSET_MOTION_TERMS):
            return False, "non_motion_light_sensor_only"
        if contains_any(text, CABINET_CLOSET_STRIP_TERMS) and not contains_any(text, CABINET_CLOSET_STRIP_ALLOWED_TERMS):
            return False, "non_motion_or_cabinet_light_strip"
        if contains_any(text, CABINET_CLOSET_MOTION_TERMS) and contains_any(text, CABINET_CLOSET_LIGHT_TERMS):
            return True, "indoor_motion_lighting_keyword"
        if contains_any(text, CABINET_CLOSET_SCENE_TERMS) and contains_any(text, CABINET_CLOSET_LIGHT_TERMS):
            return True, "cabinet_closet_adjacent_light_keyword"
        if contains_any(text, CABINET_CLOSET_KEYWORD_SIGNALS):
            return True, "cabinet_closet_keyword_signal"
        if source_type in {"competitor_product_keywords", "product_traffic_terms"} and (product_context_tokens or set()) & tokens(text):
            return True, "product_context_token_overlap"
        return False, "missing_cabinet_closet_keyword_signal"
    if lighting_mode and contains_any(text, LIGHTING_NOISE_TOKENS):
        return False, "non_lighting_noise_token"
    if lighting_mode:
        if not contains_any(text, LIGHTING_KEYWORD_SIGNALS):
            return False, "missing_lighting_keyword_signal"
        if str(keyword.get("keyword_cn") or "").startswith("未映射关键词"):
            return False, "keyword_cn_unmapped"
        return True, "lighting_keyword_signal"
    if hunting_blinds_mode:
        if contains_any(text, HUNTING_BLINDS_KEYWORD_NOISE):
            return False, "non_hunting_blind_keyword_noise"
        if contains_any(text, HUNTING_BLINDS_KEYWORD_SIGNALS):
            return True, "hunting_blind_keyword_signal"
        if source_type in {"keyword_extends", "category_keywords"}:
            return True, "hunting_blind_market_keyword_sample"
        seed_tokens = set().union(*(tokens(seed) for seed in seed_terms)) if seed_terms else set()
        if source_type in {"competitor_product_keywords", "product_traffic_terms"} and seed_tokens & tokens(text):
            return True, "hunting_blind_adjacent_seed_overlap"
        if source_type in {"competitor_product_keywords", "product_traffic_terms"} and (product_context_tokens or set()) & tokens(text):
            return True, "product_context_token_overlap"
        return False, "missing_hunting_blind_keyword_signal"
    if not seed_terms:
        return True, "no_seed_keep_for_audit"
    if keyword.get("is_core_relevant") or keyword.get("relevance_cn") in {"高相关", "相邻相关"}:
        return True, "relevance_bucket"
    if keyword.get("relevance_cn") == "低相关":
        return False, "low_relevance"
    seed_tokens = set().union(*(tokens(seed) for seed in seed_terms)) if seed_terms else set()
    if seed_tokens and seed_tokens & tokens(text):
        return True, "seed_overlap"
    return True, "generic_unlabeled_keep"


def supplier_relevance(supplier: dict[str, Any], seed_terms: list[str]) -> tuple[bool, str]:
    text = entity_search_text(supplier, ["title", "title_cn", "name", "product_name", "supplier_name", "seed_keyword", "search_term", "segment", "segment_cn"])
    cabinet_closet_mode = is_cabinet_closet_light_research(seed_terms)
    lighting_mode = is_lighting_research(seed_terms)
    hunting_blinds_mode = is_hunting_blinds_research(seed_terms)
    if cabinet_closet_mode:
        if contains_any(text, CABINET_CLOSET_HARD_NOISE):
            return False, "non_cabinet_closet_supplier_noise"
        if contains_any(text, CABINET_CLOSET_PRODUCT_SIGNALS):
            return True, "cabinet_closet_supplier_signal"
        return False, "missing_cabinet_closet_supplier_signal"
    if lighting_mode and contains_any(text, LIGHTING_NOISE_TOKENS):
        return False, "non_lighting_noise_token"
    if lighting_mode:
        if not contains_any(text, LIGHTING_PRODUCT_SIGNALS):
            return False, "missing_lighting_supplier_signal"
        return True, "lighting_supplier_signal"
    if hunting_blinds_mode:
        if contains_any(text, HUNTING_BLINDS_PRODUCT_SIGNALS):
            return True, "hunting_blind_supplier_signal"
        return False, "missing_hunting_blind_supplier_signal"
    return True, "generic_supplier"


def dedupe_effective_keywords(keywords: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    seen: set[str] = set()
    effective: list[dict[str, Any]] = []
    duplicate_extra = 0
    for keyword in keywords:
        key = f"{keyword_source_bucket(keyword)}|{normalized_key(keyword.get('keyword'))}"
        if key in seen:
            duplicate_extra += 1
            continue
        seen.add(key)
        effective.append(keyword)
    return effective, duplicate_extra


def build_categories_from_products(products: list[dict[str, Any]], existing: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if existing:
        return existing
    counts: dict[str, dict[str, Any]] = {}
    for product in products:
        category = normalize_text(product.get("category") or product.get("category_cn"))
        if not category:
            continue
        item = counts.setdefault(category, {"name": category, "category": category, "product_count": 0, "source_ids": []})
        item["product_count"] += 1
        for source_id in source_ids(product):
            if source_id not in item["source_ids"]:
                item["source_ids"].append(source_id)
    return sorted(counts.values(), key=lambda item: item["product_count"], reverse=True)


def apply_research_relevance_gate(data_pack: dict[str, Any], seed_terms: list[str]) -> None:
    effective_products: list[dict[str, Any]] = []
    removed_products: list[dict[str, Any]] = []
    for product in data_pack.get("products") or []:
        passed, reason = product_relevance(product, seed_terms)
        product["research_relevance"] = {"passed": passed, "reason": reason}
        if passed:
            if is_hunting_blinds_research(seed_terms):
                clear_customer_label_pollution(product)
            effective_products.append(product)
        else:
            removed_products.append(
                {
                    "asin": product.get("asin"),
                    "brand": product.get("brand"),
                    "title": normalize_text(product.get("title") or product.get("title_cn"))[:160],
                    "reason": reason,
                }
            )

    valid_asins = {normalized_key(product.get("asin")).upper() for product in effective_products if product.get("asin")}
    product_context_tokens: set[str] = set()
    for product in effective_products:
        product_context_tokens.update(
            tokens(
                entity_search_text(
                    product,
                    ["title", "title_cn", "brand", "category", "category_cn", "segment", "segment_cn", "subcategory"],
                )
            )
        )
    candidate_keywords: list[dict[str, Any]] = []
    removed_keywords: list[dict[str, Any]] = []
    for keyword in data_pack.get("keywords") or []:
        passed, reason = keyword_relevance(keyword, seed_terms, valid_asins, product_context_tokens)
        keyword["research_relevance"] = {"passed": passed, "reason": reason}
        if passed:
            candidate_keywords.append(keyword)
        else:
            removed_keywords.append(
                {
                    "keyword": keyword.get("keyword"),
                    "keyword_cn": keyword.get("keyword_cn"),
                    "source_type": keyword.get("source_type"),
                    "reason": reason,
                }
            )
    effective_keywords, keyword_duplicate_extra = dedupe_effective_keywords(candidate_keywords)

    cabinet_closet_mode = is_cabinet_closet_light_research(seed_terms)
    lighting_mode = is_lighting_research(seed_terms)
    hunting_blinds_mode = is_hunting_blinds_research(seed_terms)
    effective_reviews = [
        review
        for review in data_pack.get("reviews") or []
        if not (cabinet_closet_mode or lighting_mode or hunting_blinds_mode)
        or not valid_asins
        or not review.get("asin")
        or normalized_key(review.get("asin")).upper() in valid_asins
    ]

    effective_suppliers: list[dict[str, Any]] = []
    removed_suppliers: list[dict[str, Any]] = []
    for supplier in data_pack.get("suppliers") or []:
        passed, reason = supplier_relevance(supplier, seed_terms)
        supplier["research_relevance"] = {"passed": passed, "reason": reason}
        if passed:
            effective_suppliers.append(supplier)
        else:
            removed_suppliers.append(
                {
                    "title": normalize_text(supplier.get("title") or supplier.get("title_cn") or supplier.get("name"))[:160],
                    "supplier_name": supplier.get("supplier_name") or supplier.get("store_name"),
                    "reason": reason,
                }
            )

    data_pack["effective_products"] = effective_products
    data_pack["effective_keywords"] = effective_keywords
    data_pack["effective_reviews"] = effective_reviews
    data_pack["effective_suppliers"] = effective_suppliers
    data_pack["categories"] = build_categories_from_products(effective_products, data_pack.get("categories") or [])
    mode = (
        "cabinet_closet_lighting"
        if cabinet_closet_mode
        else ("lighting" if lighting_mode else ("hunting_blinds" if hunting_blinds_mode else "generic"))
    )
    data_pack["research_relevance"] = {
        "mode": mode,
        "seed_terms": seed_terms,
        "effective_counts": {
            "products": len(effective_products),
            "keywords": len(effective_keywords),
            "reviews": len(effective_reviews),
            "suppliers": len(effective_suppliers),
        },
        "removed_counts": {
            "products": len(removed_products),
            "keywords": len(removed_keywords) + keyword_duplicate_extra,
            "reviews": max(0, len(data_pack.get("reviews") or []) - len(effective_reviews)),
            "suppliers": len(removed_suppliers),
        },
        "keyword_duplicate_extra": keyword_duplicate_extra,
        "removed_examples": {
            "products": removed_products[:20],
            "keywords": removed_keywords[:30],
            "suppliers": removed_suppliers[:20],
        },
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
    if not text:
        return "未映射关键词"
    if has_cjk(text):
        return text
    lowered = text.casefold()
    labels: list[str] = []
    for needle, label in KEYWORD_CN_RULES:
        if needle in lowered and label not in labels:
            labels.append(label)
    if labels:
        return " ".join(labels)
    return f"未映射关键词：{text}"


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
        return segment_text
    return ""


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
    inferred_title_cn = title_cn(product.get("title"), first_existing(product.get("segment_cn"), product.get("segment")))
    if inferred_title_cn:
        product["title_cn"] = product.get("title_cn") or inferred_title_cn
    segment_cn = normalize_text(product.get("segment_cn") or product.get("segment"))
    if segment_cn and not is_placeholder_customer_label(segment_cn):
        product["segment_cn"] = product.get("segment_cn") or segment_cn
        product["segment"] = product.get("segment") or segment_cn
    if is_placeholder_customer_label(product.get("positioning_cn")):
        product.pop("positioning_cn", None)
    else:
        product["positioning_cn"] = product.get("positioning_cn")
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


def data_gap_identity(gap: Any) -> tuple[str, str, str]:
    if isinstance(gap, dict):
        marker = normalize_text(gap.get("module") or gap.get("type") or "")
        message = normalize_text(gap.get("gap") or gap.get("reason") or "")
        if not message:
            stable = {key: value for key, value in gap.items() if key != "fetched_at"}
            message = normalize_text(json.dumps(stable, ensure_ascii=False, sort_keys=True))
        return ("dict", marker, message)
    return ("text", "", normalize_text(gap))


def dedupe_data_gaps(data_pack: dict[str, Any]) -> int:
    gaps = data_pack.setdefault("data_gaps", [])
    deduped: list[Any] = []
    index_by_key: dict[tuple[str, str, str], int] = {}
    removed = 0
    for gap in gaps:
        key = data_gap_identity(gap)
        if key in index_by_key:
            removed += 1
            existing = deduped[index_by_key[key]]
            if isinstance(existing, dict) and isinstance(gap, dict):
                for field, value in gap.items():
                    if value not in (None, "", []) and existing.get(field) in (None, "", []):
                        existing[field] = value
            continue
        index_by_key[key] = len(deduped)
        deduped.append(gap)
    data_pack["data_gaps"] = deduped
    return removed


def data_gap_marker(gap: Any) -> str:
    if not isinstance(gap, dict):
        return ""
    return normalize_text(gap.get("module") or gap.get("type") or "")


def remove_recovered_data_gaps(data_pack: dict[str, Any], after_counts: dict[str, int]) -> int:
    recovered_markers: set[str] = set()
    if after_counts.get("keywords", 0) >= 1000:
        recovered_markers.update({"keyword_sample_depth", "keyword_collection_no_seed", "keyword_collection_failure"})
    if after_counts.get("reviews", 0) >= 80:
        recovered_markers.update({"review_sample_depth", "review_collection_no_asin", "review_collection_failure"})
    if not recovered_markers:
        return 0
    gaps = data_pack.setdefault("data_gaps", [])
    kept: list[Any] = []
    removed = 0
    for gap in gaps:
        if data_gap_marker(gap) in recovered_markers:
            removed += 1
        else:
            kept.append(gap)
    data_pack["data_gaps"] = kept
    return removed


def apply_quality_caps(data_pack: dict[str, Any], after_counts: dict[str, int], cross_validated: dict[str, int]) -> None:
    quality = data_pack.setdefault("quality", {})
    raw_score = quality.get("overall_score")
    try:
        score = float(raw_score)
    except (TypeError, ValueError):
        score = 0.68
    if score <= 0 or quality.get("grade") == "collection_started":
        score = 0.55
        if after_counts.get("products", 0) >= 60:
            score += 0.10
        if after_counts.get("keywords", 0) >= 900:
            score += 0.08
        elif after_counts.get("keywords", 0) >= 500:
            score += 0.04
        if after_counts.get("reviews", 0) >= 80:
            score += 0.08
        if after_counts.get("suppliers", 0) >= 50:
            score += 0.07
        if after_counts.get("tiktok_products", 0) or after_counts.get("tiktok_videos", 0):
            score += 0.05
        if after_counts.get("web_documents", 0):
            score += 0.04
        if sum(cross_validated.values()) > 0:
            score += 0.03
        quality["score_basis"] = "computed_from_normalized_evidence_coverage"
    caps: list[dict[str, Any]] = []
    if after_counts.get("keywords", 0) < 1000:
        caps.append({"module": "keyword_sample_depth_waiver", "max_score": 0.82})
    if after_counts.get("reviews", 0) < 80:
        caps.append({"module": "review_sample_depth", "max_score": 0.74})
    elif after_counts.get("reviews", 0) < 200:
        caps.append({"module": "review_sample_depth_deep_warning", "max_score": 0.82})
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
            quality["grade"] = "medium_confidence"
        else:
            quality["grade"] = "high_confidence"
    else:
        quality["overall_score"] = round(score, 2)
        quality["grade"] = "high_confidence" if score >= 0.85 else "medium_confidence" if score >= 0.75 else "low_confidence_watch"


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
    data_pack["tiktok_authors"] = dedupe(data_pack.get("tiktok_authors") or [], tiktok_author_dedupe_key, source_index)
    data_pack["suppliers"] = dedupe(data_pack.get("suppliers") or [], supplier_dedupe_key, source_index)
    data_pack["web_documents"] = dedupe(data_pack.get("web_documents") or [], web_document_dedupe_key, source_index)
    apply_research_relevance_gate(data_pack, seed_terms)

    after_counts = {key: len(data_pack.get(key) or []) for key in ENTITY_KEYS}
    effective_counts = (data_pack.get("research_relevance") or {}).get("effective_counts") or {}
    decision_counts = {
        "keywords": int(effective_counts.get("keywords", after_counts.get("keywords", 0))),
        "reviews": int(effective_counts.get("reviews", after_counts.get("reviews", 0))),
    }
    data_gaps_recovered_removed = remove_recovered_data_gaps(data_pack, after_counts)
    cross_validated = {
        key: sum(1 for item in data_pack.get(key, []) if (item.get("validation") or {}).get("cross_validated"))
        for key in ENTITY_KEYS
    }
    data_pack["normalization"] = {
        "deduped": True,
        "normalized_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "before_counts": before_counts,
        "after_counts": after_counts,
        "effective_counts": effective_counts,
        "research_relevance": data_pack.get("research_relevance") or {},
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
            "tiktok_authors deduped by canonical profile URL or author name",
            "web_documents deduped by canonical URL with query and fragment removed",
            "suppliers deduped by canonical URL, product_id, or title+store",
            "English keyword/title fields copied into audit-friendly display fields; relevance is inferred from research_object/seed keyword overlap",
            "customer reports use effective_* records that pass research_relevance_gate; raw records remain only for audit lineage",
        ],
    }
    if decision_counts.get("keywords", 0) < 1000:
        upsert_gap(
            data_pack,
            "keyword_sample_depth",
            f"标准/深度版有效关键词样本不足 1000，当前 {decision_counts.get('keywords', 0)}。",
            "需求结构、关键词机会和内容选题只能做方向判断，不能做完整优先级排序。",
            "继续分页采集 category_keywords 与 keyword_extends，直到归一化后关键词样本 >=1000。",
        )
    if decision_counts.get("reviews", 0) < 80:
        upsert_gap(
            data_pack,
            "review_sample_depth",
            f"有效评论样本不足建议门槛 80，当前 {decision_counts.get('reviews', 0)}。",
            "VOC、APPEALS、KANO/JTBD 和用户原声只能作为初步线索，不能写成精确市场占比。",
            "对核心 ASIN 补采 Positive/Neutral/Negative 评论，优先达到 80 条，深度版建议 200 条以上。",
        )
    data_gap_duplicates_removed = dedupe_data_gaps(data_pack)
    data_pack["normalization"]["data_gaps_recovered_removed"] = data_gaps_recovered_removed
    data_pack["normalization"]["data_gaps_duplicates_removed"] = data_gap_duplicates_removed
    apply_quality_caps(data_pack, {**after_counts, **decision_counts}, cross_validated)
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
