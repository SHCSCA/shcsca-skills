#!/usr/bin/env python3
"""Collect multi-round Sorftime 1688 supplier quotes into a report Data Pack."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ENTITY_KEY = "suppliers"
TOOL_NAME = "ali1688_similar_product"
DOCUMENTED_RESPONSE_FIELDS = {
    "Title",
    "Photo",
    "URL",
    "Price",
    "ProductId",
    "StoreName",
    "ServiceScore",
    "ServiceScoreDetail",
    "OnlineDate",
    "SalesOf30d",
    "WholesalePriceRange",
    "RepurchaseRate",
    "ShippingOrigin",
    "ReviewCount",
    "Score",
    "SkuCount",
}
REQUIRED_ANALYSIS_FIELDS = {"Title", "URL"}
URL_FIELD_ALIASES = {"URL", "Url", "url"}
SUPPLIER_GAP_MODULE_PREFIX = "supplier_quote"


EN_TO_CN_SEEDS = [
    (("under cabinet", "cabinet light", "cupboard"), "橱柜灯"),
    (("motion sensor", "sensor light", "human body"), "人体感应灯"),
    (("magnetic", "rechargeable", "wireless"), "无线磁吸感应灯"),
    (("wall sconce", "wall light", "battery operated"), "充电壁灯"),
    (("vanity", "mirror"), "镜前灯"),
    (("solar", "outdoor"), "户外太阳能灯"),
    (("bedside", "night light"), "床头小夜灯"),
    (("strip", "rgb"), "RGB灯带"),
]
DEFAULT_SEEDS = ["橱柜灯", "人体感应灯", "无线磁吸感应灯", "充电壁灯", "镜前灯"]


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def slug(value: Any) -> str:
    text = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "_", str(value or "").strip().lower()).strip("_")
    return text[:72] or "query"


def mcp_url() -> str:
    if os.environ.get("SORFTIME_MCP_URL"):
        return os.environ["SORFTIME_MCP_URL"]
    config_path = Path.home() / ".codex" / "config.toml"
    if config_path.exists():
        text = config_path.read_text(encoding="utf-8")
        match = re.search(r"\[mcp_servers\.sorftime\]\s*\nurl\s*=\s*\"([^\"]+)\"", text)
        if match:
            return match.group(1)
    raise RuntimeError("Sorftime MCP URL not found. Set SORFTIME_MCP_URL or configure mcp_servers.sorftime.")


def parse_sse_json(body: str) -> dict[str, Any]:
    data_lines = [line[5:].strip() for line in body.splitlines() if line.startswith("data:")]
    if not data_lines:
        raise RuntimeError("MCP response did not contain SSE data lines.")
    return json.loads("\n".join(data_lines))


def call_tool(url: str, name: str, arguments: dict[str, Any], timeout: int = 90) -> dict[str, Any]:
    payload = {
        "jsonrpc": "2.0",
        "id": int(time.time() * 1000) % 1_000_000,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    request = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Accept", "application/json, text/event-stream")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return parse_sse_json(response.read().decode("utf-8", errors="replace"))


def content_rows(response: dict[str, Any]) -> list[dict[str, Any]]:
    result = response.get("result") or {}
    if result.get("isError"):
        content = result.get("content") or []
        message = "; ".join(str(item.get("text") or "") for item in content if isinstance(item, dict))
        raise RuntimeError(message or "MCP tool returned isError=true.")
    content = result.get("content") or []
    rows: list[dict[str, Any]] = []
    for item in content:
        if item.get("type") != "text":
            continue
        try:
            parsed = json.loads(item.get("text") or "")
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list):
            rows.extend(row for row in parsed if isinstance(row, dict))
        elif isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def first(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if row.get(key) not in (None, ""):
            return row.get(key)
    return None


def to_number(value: Any) -> Any:
    if value in (None, ""):
        return None
    text = re.sub(r"[,，¥￥$]", "", str(value)).strip()
    try:
        return float(text) if "." in text else int(text)
    except ValueError:
        return value


def wholesale_prices(row: dict[str, Any]) -> list[float]:
    values = row.get("WholesalePriceRange") or row.get("wholesalePriceRange") or row.get("wholesale_price_range") or row.get("批发价格区间")
    prices: list[float] = []
    if isinstance(values, list):
        for item in values:
            raw = item.get("Price") if isinstance(item, dict) else item
            number = to_number(raw)
            if isinstance(number, (int, float)) and number > 0:
                prices.append(float(number))
    return prices


def supplier_price(row: dict[str, Any]) -> Any:
    prices = wholesale_prices(row)
    if prices:
        return min(prices)
    return to_number(first(row, "价格", "price", "Price", "price_rmb", "起批价", "采购价"))


def normalize_space(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def supplier_identity(supplier: dict[str, Any]) -> str:
    url = normalize_space(supplier.get("canonical_url") or supplier.get("url") or supplier.get("product_url"))
    if url:
        return "url|" + url.split("?", 1)[0].split("#", 1)[0].rstrip("/").casefold()
    product_id = normalize_space(supplier.get("product_id") or supplier.get("offer_id") or supplier.get("ProductId"))
    if product_id:
        return "id|" + product_id.casefold()
    title = normalize_space(supplier.get("title") or supplier.get("title_cn") or supplier.get("name")).casefold()
    shop = normalize_space(supplier.get("supplier_name") or supplier.get("store_name") or supplier.get("shop")).casefold()
    return f"title_shop|{title}|{shop}" if title and shop else ""


def supplier_identity_candidates(supplier: dict[str, Any]) -> list[str]:
    candidates: list[str] = []
    product_id = normalize_space(supplier.get("product_id") or supplier.get("offer_id") or supplier.get("ProductId"))
    if product_id:
        candidates.append("id|" + product_id.casefold())
    url = normalize_space(supplier.get("canonical_url") or supplier.get("url") or supplier.get("product_url"))
    if url:
        candidates.append("url|" + url.split("?", 1)[0].split("#", 1)[0].rstrip("/").casefold())
    title = normalize_space(supplier.get("title") or supplier.get("title_cn") or supplier.get("name")).casefold()
    shop = normalize_space(supplier.get("supplier_name") or supplier.get("store_name") or supplier.get("shop")).casefold()
    if title and shop:
        candidates.append(f"title_shop|{title}|{shop}")
    return candidates


def is_valid_quote(supplier: dict[str, Any]) -> bool:
    price = to_number(supplier.get("price_rmb") if supplier.get("price_rmb") not in (None, "") else supplier.get("price"))
    title = supplier.get("title") or supplier.get("title_cn") or supplier.get("name")
    product_id = supplier.get("product_id") or supplier.get("offer_id") or supplier.get("ProductId")
    shop = supplier.get("supplier_name") or supplier.get("store_name") or supplier.get("shop")
    return isinstance(price, (int, float)) and price > 0 and bool(title or product_id) and bool(shop) and bool(supplier_identity(supplier))


def supplier_entity(row: dict[str, Any], source_id: str, seed_keyword: str) -> dict[str, Any]:
    return {
        "title": first(row, "标题", "title", "Title", "商品标题", "name"),
        "supplier_name": first(row, "供应商", "supplier", "supplier_name", "店铺", "store_name", "StoreName", "shop"),
        "price_rmb": supplier_price(row),
        "listed_price_raw": to_number(first(row, "价格", "price", "Price", "price_rmb", "起批价", "采购价")),
        "wholesale_price_range": first(row, "WholesalePriceRange", "wholesalePriceRange", "批发价格区间"),
        "product_id": first(row, "ProductId", "product_id", "offer_id"),
        "photo_url": first(row, "Photo", "photo", "image", "image_url"),
        "sales_30d": to_number(first(row, "30天销量", "近30天销量", "sales_30d", "SalesOf30d", "月销量")),
        "cumulative_sales": to_number(first(row, "CumulativeSaleCount", "累计销量", "cumulative_sales")),
        "monthly_sales": to_number(first(row, "MonthlySaleCount", "月销量", "monthly_sales")),
        "monthly_sales_amount": to_number(first(row, "MonthlySaleAmount", "月销额", "monthly_sales_amount")),
        "review_count": to_number(first(row, "ReviewCount", "评论数", "review_count")),
        "star": to_number(first(row, "Star", "星级", "star")),
        "service_score": to_number(first(row, "ServiceScore", "服务评分", "service_score")),
        "score": to_number(first(row, "Score", "综合评分", "score")),
        "repurchase_rate": to_number(first(row, "RepurchaseRate", "复购率", "repurchase_rate")),
        "sku_count": to_number(first(row, "SkuCount", "SKU数量", "sku_count")),
        "online_date": first(row, "OnlineDate", "上架日期", "online_date"),
        "moq": to_number(first(row, "起批量", "moq", "MOQ")),
        "shipping_origin": first(row, "发货地", "shipping_origin", "ShippingOrigin", "产地"),
        "url": first(row, "商品链接", "url", "URL", "Url", "link", "product_url"),
        "seed_keyword": seed_keyword,
        "response_fields": sorted(str(key) for key in row.keys()),
        "schema_note": "ali1688_similar_product(searchName,page) normalized from Sorftime MCP response.",
        "source_id": source_id,
        "provider": "sorftime",
    }


def add_unique(seeds: list[str], seed: str) -> None:
    seed = normalize_space(seed)
    if seed and seed not in seeds:
        seeds.append(seed)


def infer_1688_seed_terms(data_pack: dict[str, Any], provided: list[str], max_rounds: int = 5) -> list[str]:
    seeds: list[str] = []
    for seed in provided:
        add_unique(seeds, seed)

    text_parts: list[str] = []
    research_object = data_pack.get("research_object") or {}
    if isinstance(research_object, dict):
        text_parts.append(str(research_object.get("value") or ""))
    for product in data_pack.get("products") or []:
        if isinstance(product, dict):
            text_parts.append(str(product.get("title") or product.get("title_cn") or product.get("segment") or ""))
    for keyword in data_pack.get("keywords") or []:
        if isinstance(keyword, dict):
            text_parts.append(str(keyword.get("keyword") or ""))
        if len(text_parts) >= 80:
            break
    folded = " ".join(text_parts).casefold()
    for needles, seed in EN_TO_CN_SEEDS:
        if any(needle in folded for needle in needles):
            add_unique(seeds, seed)
    for seed in DEFAULT_SEEDS:
        add_unique(seeds, seed)
    return seeds[:max_rounds]


def source_exists(data_pack: dict[str, Any], source_id: str) -> bool:
    return any(source.get("source_id") == source_id for source in data_pack.get("sources") or [])


def invalidate_normalization(report_dir: Path, data_pack: dict[str, Any]) -> None:
    data_pack.pop("normalization", None)
    for filename in ["normalization_baseline.json", "cross_validated_data_pack.json", "normalized_data_pack.json"]:
        path = report_dir / "data" / "normalized" / filename
        if path.exists():
            path.unlink()


def valid_quote_count(suppliers: list[dict[str, Any]]) -> int:
    seen: set[str] = set()
    count = 0
    for supplier in suppliers:
        identity = supplier_identity(supplier)
        if is_valid_quote(supplier) and identity not in seen:
            seen.add(identity)
            count += 1
    return count


def dedupe_supplier_records(suppliers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def normalize_sources(record: dict[str, Any]) -> dict[str, Any]:
        source_values: list[str] = []
        for key in ("source_id", "source_ids"):
            value = record.get(key)
            if isinstance(value, list):
                source_values.extend(str(item) for item in value if item)
            elif value:
                source_values.extend(part.strip() for part in str(value).split(";") if part.strip())
        unique_sources: list[str] = []
        for source in source_values:
            if source not in unique_sources:
                unique_sources.append(source)
        if unique_sources:
            record["source_id"] = unique_sources[0]
            if len(unique_sources) > 1:
                record["source_ids"] = unique_sources
            else:
                record.pop("source_ids", None)
        return record

    merged: list[dict[str, Any]] = []
    identity_to_index: dict[str, int] = {}
    passthrough: list[dict[str, Any]] = []
    for supplier in suppliers:
        supplier = normalize_sources(dict(supplier))
        identities = supplier_identity_candidates(supplier)
        if not identities:
            passthrough.append(supplier)
            continue
        match_index = next((identity_to_index[identity] for identity in identities if identity in identity_to_index), None)
        if match_index is None:
            match_index = len(merged)
            merged.append(dict(supplier))
            for identity in identities:
                identity_to_index[identity] = match_index
            continue
        target = merged[match_index]
        for key, value in supplier.items():
            if value not in (None, "", []):
                if target.get(key) in (None, "", []):
                    target[key] = value
                elif key in {"source_id", "source_ids"}:
                    existing_sources = target.get("source_ids") or [target.get("source_id")]
                    incoming_sources = supplier.get("source_ids") or [supplier.get("source_id")]
                    combined = [str(item) for item in existing_sources + incoming_sources if item]
                    target["source_ids"] = []
                    for source in combined:
                        if source not in target["source_ids"]:
                            target["source_ids"].append(source)
                    target["source_id"] = target["source_ids"][0]
        for identity in supplier_identity_candidates(target):
            identity_to_index[identity] = match_index
    return [normalize_sources(record) for record in merged + passthrough]


def is_legacy_incomplete_1688_quote(supplier: dict[str, Any]) -> bool:
    provider = str(supplier.get("provider") or "").casefold()
    source = str(supplier.get("source_id") or "")
    source_ids = supplier.get("source_ids") or []
    sources = [source] + [str(item) for item in source_ids if item]
    is_sorftime_1688 = provider == "sorftime" and any(item.startswith("sf_1688_") for item in sources)
    has_title = bool(supplier.get("title") or supplier.get("title_cn") or supplier.get("name"))
    has_url = bool(supplier.get("canonical_url") or supplier.get("url") or supplier.get("product_url"))
    has_product_id = bool(supplier.get("product_id") or supplier.get("offer_id") or supplier.get("ProductId"))
    return is_sorftime_1688 and has_product_id and not has_title and not has_url


def is_legacy_unpriced_1688_quote(supplier: dict[str, Any]) -> bool:
    provider = str(supplier.get("provider") or "").casefold()
    source = str(supplier.get("source_id") or "")
    source_ids = supplier.get("source_ids") or []
    sources = [source] + [str(item) for item in source_ids if item]
    is_sorftime_1688 = provider == "sorftime" and any(item.startswith("sf_1688_") for item in sources)
    return is_sorftime_1688 and not supplier.get("wholesale_price_range")


def remove_legacy_incomplete_1688_quotes(suppliers: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    kept: list[dict[str, Any]] = []
    removed = 0
    for supplier in suppliers:
        if is_legacy_incomplete_1688_quote(supplier):
            removed += 1
        else:
            kept.append(supplier)
    return kept, removed


def remove_legacy_unpriced_1688_quotes(suppliers: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    kept: list[dict[str, Any]] = []
    removed = 0
    for supplier in suppliers:
        if is_legacy_unpriced_1688_quote(supplier):
            removed += 1
        else:
            kept.append(supplier)
    return kept, removed


def recompute_1688_prices_from_wholesale_range(suppliers: list[dict[str, Any]]) -> int:
    updated = 0
    for supplier in suppliers:
        prices = wholesale_prices(supplier)
        if not prices:
            continue
        corrected = min(prices)
        if supplier.get("price_rmb") != corrected:
            supplier["price_rmb"] = corrected
            updated += 1
    return updated


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


def quote_quality(suppliers: list[dict[str, Any]], min_title_coverage: float, max_max_to_p50: float, max_p75_to_p25: float) -> dict[str, Any]:
    seen: set[str] = set()
    valid: list[dict[str, Any]] = []
    for supplier in suppliers:
        identity = supplier_identity(supplier)
        if is_valid_quote(supplier) and identity not in seen:
            seen.add(identity)
            valid.append(supplier)
    total = len(valid)
    title_count = 0
    identity_count = 0
    prices: list[float] = []
    for supplier in valid:
        if supplier.get("title") or supplier.get("title_cn") or supplier.get("name"):
            title_count += 1
        if supplier.get("canonical_url") or supplier.get("url") or supplier.get("product_url") or supplier.get("product_id") or supplier.get("offer_id"):
            identity_count += 1
        price = to_number(supplier.get("price_rmb") if supplier.get("price_rmb") not in (None, "") else supplier.get("price"))
        if isinstance(price, (int, float)) and price > 0:
            prices.append(float(price))
    title_pct = round((title_count / total) * 100, 1) if total else 0
    identity_pct = round((identity_count / total) * 100, 1) if total else 0
    p25 = percentile(prices, 0.25)
    p50 = percentile(prices, 0.50)
    p75 = percentile(prices, 0.75)
    max_price = max(prices) if prices else None
    max_to_p50 = round(max_price / p50, 2) if max_price and p50 else None
    p75_to_p25 = round(p75 / p25, 2) if p75 and p25 else None
    field_quality_passed = title_pct >= min_title_coverage and identity_pct >= min_title_coverage
    price_spread_passed = (
        max_to_p50 is None
        or p75_to_p25 is None
        or (max_to_p50 <= max_max_to_p50 and p75_to_p25 <= max_p75_to_p25)
    )
    return {
        "valid_quotes": total,
        "title_coverage_pct": title_pct,
        "identity_coverage_pct": identity_pct,
        "p25_rmb": p25,
        "p50_rmb": p50,
        "p75_rmb": p75,
        "max_rmb": max_price,
        "max_to_p50_ratio": max_to_p50,
        "p75_to_p25_ratio": p75_to_p25,
        "field_quality_passed": field_quality_passed,
        "price_spread_passed": price_spread_passed,
        "passed": field_quality_passed and price_spread_passed,
    }


def same_search_bucket_gate(
    suppliers: list[dict[str, Any]],
    min_valid_quotes: int,
    min_title_coverage: float,
    max_max_to_p50: float,
    max_p75_to_p25: float,
) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for supplier in suppliers:
        seed = normalize_space(supplier.get("seed_keyword") or supplier.get("search_term") or supplier.get("query"))
        if seed:
            buckets[seed].append(supplier)
    passing: list[dict[str, Any]] = []
    for seed, rows in buckets.items():
        quality = quote_quality(rows, min_title_coverage, max_max_to_p50, max_p75_to_p25)
        if quality["valid_quotes"] >= min_valid_quotes and quality["passed"]:
            passing.append({"bucket": seed, "valid_quotes": quality["valid_quotes"], "quality": quality})
    if not passing:
        return {"passed": False, "bucket": None, "valid_quotes": 0, "quality": None}
    return sorted(
        passing,
        key=lambda item: (
            item["valid_quotes"],
            -float((item["quality"] or {}).get("max_to_p50_ratio") or 0),
            -float((item["quality"] or {}).get("p75_to_p25_ratio") or 0),
        ),
        reverse=True,
    )[0] | {"passed": True}


def collection_passed(data_pack: dict[str, Any], min_valid_quotes: int, min_title_coverage: float, max_max_to_p50: float, max_p75_to_p25: float) -> bool:
    quality = quote_quality(data_pack.get(ENTITY_KEY) or [], min_title_coverage, max_max_to_p50, max_p75_to_p25)
    same_bucket = same_search_bucket_gate(data_pack.get(ENTITY_KEY) or [], min_valid_quotes, min_title_coverage, max_max_to_p50, max_p75_to_p25)
    return quality["valid_quotes"] >= min_valid_quotes and (quality["passed"] or bool(same_bucket.get("passed")))


def field_signature(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    return "|".join(sorted(str(key) for key in rows[0].keys()))


def missing_required_fields(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return sorted(REQUIRED_ANALYSIS_FIELDS)
    fields = {str(key) for row in rows for key in row.keys()}
    missing: list[str] = []
    if "Title" not in fields:
        missing.append("Title")
    if not (fields & URL_FIELD_ALIASES):
        missing.append("URL")
    return missing


def documented_field_coverage(observed_fields: set[str]) -> dict[str, Any]:
    canonical_observed = set(observed_fields)
    if canonical_observed & URL_FIELD_ALIASES:
        canonical_observed.add("URL")
    present = sorted(field for field in DOCUMENTED_RESPONSE_FIELDS if field in canonical_observed)
    missing = sorted(field for field in DOCUMENTED_RESPONSE_FIELDS if field not in canonical_observed)
    total = len(DOCUMENTED_RESPONSE_FIELDS)
    return {
        "documented_field_count": total,
        "observed_documented_field_count": len(present),
        "coverage_pct": round(len(present) / total * 100, 1) if total else 0,
        "present_fields": present,
        "missing_fields": missing,
    }


def existing_supplier_response_fields(suppliers: list[dict[str, Any]]) -> set[str]:
    fields: set[str] = set()
    for supplier in suppliers:
        response_fields = supplier.get("response_fields")
        if isinstance(response_fields, list):
            fields.update(str(field) for field in response_fields if field)
    return fields


def is_supplier_quote_gap(gap: Any) -> bool:
    if isinstance(gap, dict):
        marker = str(gap.get("type") or gap.get("module") or "")
        if marker.startswith(SUPPLIER_GAP_MODULE_PREFIX):
            return True
        text = " ".join(
            str(gap.get(key) or "")
            for key in ("gap", "reason", "impact", "next_action", "next_step")
        )
    else:
        text = str(gap or "")
    normalized = normalize_space(text)
    return normalized.startswith("1688报价") or normalized.startswith("1688有效报价")


def remove_stale_supplier_quote_gaps(data_pack: dict[str, Any]) -> int:
    gaps = data_pack.setdefault("data_gaps", [])
    kept: list[Any] = []
    removed = 0
    for gap in gaps:
        if is_supplier_quote_gap(gap):
            removed += 1
        else:
            kept.append(gap)
    data_pack["data_gaps"] = kept
    return removed


def collect(
    report_dir: Path,
    min_valid_quotes: int,
    seeds: list[str],
    max_rounds: int,
    max_pages: int,
    sleep_seconds: float,
    min_title_coverage: float = 70,
    max_max_to_p50: float = 20,
    max_p75_to_p25: float = 5,
    force_rounds: bool = False,
) -> dict[str, Any]:
    data_path = report_dir / "data" / "data_pack.json"
    data_pack = load_json(data_path, {})
    data_pack.setdefault("sources", [])
    data_pack.setdefault(ENTITY_KEY, [])
    data_pack.setdefault("data_gaps", [])
    raw_dir = report_dir / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    fetched_at = utc_now()
    seed_terms = infer_1688_seed_terms(data_pack, seeds, max_rounds)
    rounds: list[dict[str, Any]] = []
    calls = 0
    added = 0
    errors: list[dict[str, Any]] = []
    observed_fields: set[str] = existing_supplier_response_fields(data_pack.get(ENTITY_KEY) or [])
    field_sets: Counter[str] = Counter()
    url = mcp_url() if seed_terms else ""

    for round_idx, seed in enumerate(seed_terms, 1):
        if not force_rounds and collection_passed(data_pack, min_valid_quotes, min_title_coverage, max_max_to_p50, max_p75_to_p25):
            break
        for page in range(1, max(1, max_pages) + 1):
            before = valid_quote_count(data_pack.get(ENTITY_KEY) or [])
            if not force_rounds and collection_passed(data_pack, min_valid_quotes, min_title_coverage, max_max_to_p50, max_p75_to_p25):
                break
            args = {"searchName": seed, "page": page}
            raw_path = raw_dir / f"sorftime_{TOOL_NAME}_{slug(seed)}_p{page:03d}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.json"
            try:
                response = call_tool(url, TOOL_NAME, args)
                rows = content_rows(response)
            except Exception as exc:
                response = {"error": f"{type(exc).__name__}: {exc}", "tool": TOOL_NAME, "args": args}
                rows = []
                errors.append({"seed": seed, "page": page, "error": response["error"]})
            calls += 1
            returned = len(rows)
            if rows:
                observed_fields.update(str(key) for row in rows for key in row.keys())
                field_sets[field_signature(rows)] += 1
            source_id = f"sf_1688_{slug(seed)}_p{page:03d}"
            if rows and not source_exists(data_pack, source_id):
                data_pack["sources"].append(
                    {
                        "source_id": source_id,
                        "provider": "sorftime",
                        "tool": TOOL_NAME,
                        "query": args,
                        "raw_path": str(raw_path),
                        "fetched_at": fetched_at,
                        "confidence": "high",
                        "limitation": "Sorftime 1688 similar product quote sample; values are third-party estimates and require field-quality gates before profitability conclusions.",
                    }
                )
            added_before_page = added
            for row in rows:
                entity = supplier_entity(row, source_id, seed)
                if is_valid_quote(entity):
                    data_pack[ENTITY_KEY].append(entity)
                    added += 1
            write_json(raw_path, {"tool": TOOL_NAME, "args": args, "result": response, "parsed": rows})
            if sleep_seconds:
                time.sleep(sleep_seconds)
            after = valid_quote_count(data_pack.get(ENTITY_KEY) or [])
            quality_after = quote_quality(data_pack.get(ENTITY_KEY) or [], min_title_coverage, max_max_to_p50, max_p75_to_p25)
            page_added = added - added_before_page
            rounds.append(
                {
                    "round": round_idx,
                    "seed": seed,
                    "page": page,
                    "returned_rows": returned,
                    "valid_quotes_before": before,
                    "valid_quotes_after": after,
                    "new_valid_quotes": max(0, after - before),
                    "dedupe_loss": max(0, page_added - max(0, after - before)),
                    "observed_fields": sorted({str(key) for row in rows for key in row.keys()}),
                    "missing_documented_required_fields": missing_required_fields(rows),
                    "quality_after": quality_after,
                }
            )
            if collection_passed(data_pack, min_valid_quotes, min_title_coverage, max_max_to_p50, max_p75_to_p25):
                break

    legacy_incomplete_removed = 0
    legacy_unpriced_removed = 0
    if "Title" in observed_fields and (observed_fields & URL_FIELD_ALIASES):
        data_pack[ENTITY_KEY], legacy_incomplete_removed = remove_legacy_incomplete_1688_quotes(data_pack.get(ENTITY_KEY) or [])
    if "WholesalePriceRange" in observed_fields:
        data_pack[ENTITY_KEY], legacy_unpriced_removed = remove_legacy_unpriced_1688_quotes(data_pack.get(ENTITY_KEY) or [])
    prices_recomputed = recompute_1688_prices_from_wholesale_range(data_pack.get(ENTITY_KEY) or [])
    before_dedupe_rows = len(data_pack.get(ENTITY_KEY) or [])
    data_pack[ENTITY_KEY] = dedupe_supplier_records(data_pack.get(ENTITY_KEY) or [])
    deduped_supplier_rows_removed = max(0, before_dedupe_rows - len(data_pack.get(ENTITY_KEY) or []))
    total_valid = valid_quote_count(data_pack.get(ENTITY_KEY) or [])
    quality = quote_quality(data_pack.get(ENTITY_KEY) or [], min_title_coverage, max_max_to_p50, max_p75_to_p25)
    same_bucket = same_search_bucket_gate(data_pack.get(ENTITY_KEY) or [], min_valid_quotes, min_title_coverage, max_max_to_p50, max_p75_to_p25)
    collection_ready = total_valid >= min_valid_quotes and (quality["passed"] or bool(same_bucket.get("passed")))
    missing_documented_required = []
    if "Title" not in observed_fields:
        missing_documented_required.append("Title")
    if not (observed_fields & URL_FIELD_ALIASES):
        missing_documented_required.append("URL")
    field_coverage = documented_field_coverage(observed_fields)
    if collection_ready:
        failure_reason = ""
    elif total_valid < min_valid_quotes:
        failure_reason = f"1688有效报价不足50条：当前 {total_valid}/{min_valid_quotes}，已尝试搜索词 {', '.join(seed_terms) or '-'}。"
    elif not quality["field_quality_passed"]:
        field_note = f"；MCP实际响应缺少官方文档关键字段：{', '.join(missing_documented_required)}" if missing_documented_required else ""
        failure_reason = f"1688报价字段质量不足：标题覆盖 {quality['title_coverage_pct']}%，身份覆盖 {quality['identity_coverage_pct']}%，要求至少 {min_title_coverage}%{field_note}。"
    else:
        failure_reason = f"1688报价价格分布异常：max/P50={quality['max_to_p50_ratio']}，P75/P25={quality['p75_to_p25_ratio']}。"
    warning_reason = ""
    if collection_ready and not quality["passed"] and same_bucket.get("passed"):
        warning_reason = (
            f"全局1688报价价差异常，已改用搜索词“{same_bucket.get('bucket')}”下 "
            f"{same_bucket.get('valid_quotes')} 条同口径报价进入供应链测算。"
        )
    stale_supplier_gaps_removed = remove_stale_supplier_quote_gaps(data_pack)
    if not collection_ready:
        data_pack["data_gaps"].append(
            {
                "type": "supplier_quote_quality" if total_valid >= min_valid_quotes else "supplier_quote_depth",
                "module": "supplier_quote_quality" if total_valid >= min_valid_quotes else "supplier_quote_depth",
                "gap": failure_reason,
                "impact": "供应链成本和毛利率测算必须阻断，不能生成最终客户结论。",
                "next_action": "继续提供或授权 Sorftime 1688 数据；若官方文档字段与 MCP 实际响应不一致，需要先让 Sorftime 返回 Title/URL 后再生成毛利率测算。",
                "fetched_at": fetched_at,
            }
        )

    invalidate_normalization(report_dir, data_pack)
    write_json(data_path, data_pack)
    summary = {
        "tool": TOOL_NAME,
        "collection_ready": collection_ready,
        "min_valid_quotes": min_valid_quotes,
        "valid_quotes_total": total_valid,
        "quality": quality,
        "same_search_bucket_gate": same_bucket,
        "global_quality_passed": quality["passed"],
        "effective_quality_passed": collection_ready,
        "suppliers_added": added,
        "legacy_incomplete_quotes_removed": legacy_incomplete_removed,
        "legacy_unpriced_quotes_removed": legacy_unpriced_removed,
        "prices_recomputed_from_wholesale_range": prices_recomputed,
        "deduped_supplier_rows_removed": deduped_supplier_rows_removed,
        "stale_supplier_gaps_removed": stale_supplier_gaps_removed,
        "calls": calls,
        "rounds": rounds,
        "attempted_seeds": seed_terms,
        "documented_response_fields": sorted(DOCUMENTED_RESPONSE_FIELDS),
        "required_analysis_fields": sorted(REQUIRED_ANALYSIS_FIELDS),
        "observed_fields": sorted(observed_fields),
        "documented_field_coverage": field_coverage,
        "missing_documented_required_fields": missing_documented_required,
        "response_field_sets": [{"fields": fields.split("|") if fields else [], "calls": count} for fields, count in field_sets.most_common()],
        "errors": errors,
        "failure_reason": failure_reason,
        "warning_reason": warning_reason,
    }
    write_json(report_dir / "data" / "normalized" / "supplier_1688_collection_summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect Sorftime 1688 supplier quotes with multi-round seed retries.")
    parser.add_argument("--dir", required=True, type=Path, help="Report directory containing data/data_pack.json.")
    parser.add_argument("--min-valid-quotes", type=int, default=50)
    parser.add_argument("--seed", action="append", default=[], help="Chinese 1688 search seed. Repeatable.")
    parser.add_argument("--max-rounds", type=int, default=5)
    parser.add_argument("--max-pages", type=int, default=3, help="Max pages per 1688 search seed. Official Sorftime docs require searchName + page.")
    parser.add_argument("--sleep", type=float, default=0.15)
    parser.add_argument("--min-title-coverage", type=float, default=70)
    parser.add_argument("--max-max-to-p50", type=float, default=20)
    parser.add_argument("--max-p75-to-p25", type=float, default=5)
    parser.add_argument("--force-rounds", action="store_true", help="Continue trying seeds when count is met but quality/spread gates fail.")
    args = parser.parse_args(argv)
    summary = collect(
        args.dir,
        args.min_valid_quotes,
        args.seed,
        args.max_rounds,
        args.max_pages,
        args.sleep,
        args.min_title_coverage,
        args.max_max_to_p50,
        args.max_p75_to_p25,
        args.force_rounds,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["collection_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
