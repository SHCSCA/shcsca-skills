#!/usr/bin/env python3
"""Collect Sorftime Amazon ASIN enrichment dimensions into a report Data Pack."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


TOOLS = [
    "product_detail",
    "product_trend",
    "product_variations",
    "product_traffic_terms",
    "competitor_product_keywords",
]
PRODUCT_ENRICHMENT_GAP_TYPES = {"amazon_product_enrichment_empty_dimensions"}
PRODUCT_ENRICHMENT_GAP_MODULE = "amazon_product_enrichment"


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
    raise RuntimeError("Sorftime MCP URL not found.")


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
    rows: list[dict[str, Any]] = []
    for item in result.get("content") or []:
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
    text = re.sub(r"[,，¥￥$%]", "", str(value)).strip()
    try:
        return float(text) if "." in text else int(text)
    except ValueError:
        return value


def asin_value(product: dict[str, Any]) -> str:
    return str(product.get("asin") or product.get("ASIN") or product.get("产品ASIN码") or "").strip()


def select_asins(data_pack: dict[str, Any], max_products: int) -> list[str]:
    seen: set[str] = set()
    asins: list[str] = []
    for product in data_pack.get("products") or []:
        if not isinstance(product, dict):
            continue
        asin = asin_value(product)
        if asin and asin not in seen:
            seen.add(asin)
            asins.append(asin)
        if len(asins) >= max_products:
            break
    return asins


def source_exists(data_pack: dict[str, Any], source_id: str) -> bool:
    return any(source.get("source_id") == source_id for source in data_pack.get("sources") or [])


def add_source(data_pack: dict[str, Any], source_id: str, tool: str, args: dict[str, Any], raw_path: Path, fetched_at: str) -> None:
    if source_exists(data_pack, source_id):
        return
    data_pack.setdefault("sources", []).append(
        {
            "source_id": source_id,
            "provider": "sorftime",
            "tool": tool,
            "query": args,
            "raw_path": str(raw_path),
            "fetched_at": fetched_at,
            "confidence": "high",
            "limitation": "Sorftime Amazon ASIN enrichment; empty rows are preserved in collection summary.",
        }
    )


def merge_product_patch(data_pack: dict[str, Any], asin: str, patch: dict[str, Any]) -> bool:
    for product in data_pack.get("products") or []:
        if isinstance(product, dict) and asin_value(product) == asin:
            enrichment = product.setdefault("sorftime_enrichment", {})
            for key, value in patch.items():
                if value not in (None, "", []):
                    enrichment[key] = value
                    if key == "detail_image_url" and not product.get("image_url"):
                        product["image_url"] = value
            return True
    return False


def detail_patch(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "detail_title": first(row, "标题", "Title", "title"),
        "detail_brand": first(row, "品牌", "Brand", "brand"),
        "detail_price": to_number(first(row, "价格", "Price", "price")),
        "detail_rating": to_number(first(row, "星级", "评分", "rating")),
        "detail_review_count": to_number(first(row, "评论数", "评论数量", "ReviewCount")),
        "detail_monthly_sales": to_number(first(row, "月销量", "MonthlySales", "monthly_sales")),
        "detail_category": first(row, "所属类目", "所属细分类目", "category"),
        "detail_image_url": first(
            row,
            "图片",
            "image",
            "Image",
            "image_url",
            "ImageUrl",
            "imageUrl",
            "main_image",
            "mainImage",
            "main_image_url",
            "MainImage",
            "thumbnail",
            "thumbnail_url",
            "Thumbnail",
            "Photo",
            "photo",
        ),
    }


def trend_patch(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "sales_trend": first(row, "销量趋势", "产品销量趋势", "SalesVolumeTrend", "trend"),
        "sales_amount_trend": first(row, "销售额趋势", "SalesAmountTrend"),
        "price_trend": first(row, "价格趋势", "产品价格趋势", "PriceTrend"),
        "rank_trend": first(row, "排名趋势", "RankTrend"),
    }


def variation_patch(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    return {
        "variation_count_observed": len(rows),
        "variation_fields": sorted({str(key) for row in rows for key in row.keys()}),
        "variations": rows[:30],
    }


def keyword_entity(row: dict[str, Any], asin: str, source_id: str, source_type: str) -> dict[str, Any]:
    return {
        "keyword": first(row, "关键词", "keyword", "Keyword"),
        "asin": asin,
        "monthly_search_volume": to_number(first(row, "月搜索量", "关键词月搜索量", "monthly_search_volume")),
        "recommended_cpc": first(row, "推荐竞价", "推荐竞价范围", "cpc推荐竞价", "recommended_cpc"),
        "exposure_position": first(row, "曝光位置", "最近自然曝光位置", "最近广告曝光位置"),
        "source_type": source_type,
        "source_id": source_id,
        "provider": "sorftime",
    }


def keyword_identity(keyword: dict[str, Any]) -> str:
    return "|".join(
        [
            str(keyword.get("source_type") or ""),
            str(keyword.get("asin") or ""),
            str(keyword.get("keyword") or "").strip().casefold(),
        ]
    )


def add_keyword(data_pack: dict[str, Any], entity: dict[str, Any]) -> bool:
    if not entity.get("keyword"):
        return False
    identity = keyword_identity(entity)
    for existing in data_pack.setdefault("keywords", []):
        if isinstance(existing, dict) and keyword_identity(existing) == identity:
            for key, value in entity.items():
                if value not in (None, "", []) and existing.get(key) in (None, "", []):
                    existing[key] = value
            return False
    data_pack["keywords"].append(entity)
    return True


def is_product_enrichment_gap(gap: Any) -> bool:
    if not isinstance(gap, dict):
        return False
    marker = str(gap.get("type") or gap.get("module") or "")
    return marker in PRODUCT_ENRICHMENT_GAP_TYPES or marker == PRODUCT_ENRICHMENT_GAP_MODULE


def remove_product_enrichment_gaps(data_pack: dict[str, Any]) -> int:
    gaps = data_pack.setdefault("data_gaps", [])
    kept: list[Any] = []
    removed = 0
    for gap in gaps:
        if is_product_enrichment_gap(gap):
            removed += 1
        else:
            kept.append(gap)
    data_pack["data_gaps"] = kept
    return removed


def invalidate_normalization(report_dir: Path, data_pack: dict[str, Any]) -> None:
    data_pack.pop("normalization", None)
    for filename in ["normalization_baseline.json", "cross_validated_data_pack.json", "normalized_data_pack.json"]:
        path = report_dir / "data" / "normalized" / filename
        if path.exists():
            path.unlink()


def collect(report_dir: Path, max_products: int, max_pages: int, site: str, sleep_seconds: float) -> dict[str, Any]:
    data_path = report_dir / "data" / "data_pack.json"
    data_pack = load_json(data_path, {})
    data_pack.setdefault("sources", [])
    data_pack.setdefault("products", [])
    data_pack.setdefault("keywords", [])
    data_pack.setdefault("data_gaps", [])
    raw_dir = report_dir / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    fetched_at = utc_now()
    url = mcp_url()
    asins = select_asins(data_pack, max_products)
    calls = 0
    keyword_rows_added = 0
    product_patches = 0
    tool_stats: dict[str, dict[str, Any]] = {tool: {"calls": 0, "rows": 0, "empty_calls": 0, "fields": []} for tool in TOOLS}
    errors: list[dict[str, Any]] = []

    for asin in asins:
        tool_args: list[tuple[str, dict[str, Any]]] = [
            ("product_detail", {"asin": asin, "amzSite": site}),
            ("product_trend", {"asin": asin, "productTrendType": "SalesVolume", "amzSite": site}),
            ("product_variations", {"asin": asin, "amzSite": site}),
        ]
        for page in range(1, max_pages + 1):
            tool_args.append(("product_traffic_terms", {"asin": asin, "page": page, "amzSite": site}))
            tool_args.append(("competitor_product_keywords", {"asin": asin, "page": page, "keywordSupportSite": site}))

        for tool, args in tool_args:
            raw_path = raw_dir / f"sorftime_{tool}_{slug(asin)}_p{args.get('page', 1):03d}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.json"
            try:
                response = call_tool(url, tool, args)
                rows = content_rows(response)
            except Exception as exc:
                response = {"error": f"{type(exc).__name__}: {exc}", "tool": tool, "args": args}
                rows = []
                errors.append({"tool": tool, "asin": asin, "args": args, "error": response["error"]})
            calls += 1
            stats = tool_stats[tool]
            stats["calls"] += 1
            stats["rows"] += len(rows)
            if not rows:
                stats["empty_calls"] += 1
            stats["fields"] = sorted(set(stats["fields"]) | {str(key) for row in rows for key in row.keys()})
            source_id = f"sf_{tool}_{slug(asin)}_p{args.get('page', 1):03d}"
            write_json(raw_path, {"tool": tool, "args": args, "result": response, "parsed": rows})
            if rows:
                add_source(data_pack, source_id, tool, args, raw_path, fetched_at)
            if tool == "product_detail" and rows:
                product_patches += int(merge_product_patch(data_pack, asin, detail_patch(rows[0])))
            elif tool == "product_trend" and rows:
                product_patches += int(merge_product_patch(data_pack, asin, trend_patch(rows[0])))
            elif tool == "product_variations" and rows:
                product_patches += int(merge_product_patch(data_pack, asin, variation_patch(rows)))
            elif tool in {"product_traffic_terms", "competitor_product_keywords"}:
                source_type = "product_traffic_terms" if tool == "product_traffic_terms" else "competitor_product_keywords"
                for row in rows:
                    if add_keyword(data_pack, keyword_entity(row, asin, source_id, source_type)):
                        keyword_rows_added += 1
            if sleep_seconds:
                time.sleep(sleep_seconds)

    empty_tools = [tool for tool, stats in tool_stats.items() if stats["calls"] and stats["rows"] == 0]
    successful_dimensions = [tool for tool, stats in tool_stats.items() if stats["rows"] > 0]
    stale_product_enrichment_gaps_removed = remove_product_enrichment_gaps(data_pack)
    if empty_tools:
        data_pack["data_gaps"].append(
            {
                "type": "amazon_product_enrichment_empty_dimensions",
                "module": "amazon_product_enrichment",
                "gap": (
                    f"Sorftime Amazon ASIN enrichment tools returned no rows for: {', '.join(empty_tools)} "
                    f"after retrying {len(asins)} ASINs."
                ),
                "impact": "产品详情、趋势或变体维度只能降级，不能在报告中写成已验证事实。",
                "next_action": "优先更换 ASIN 或确认 Sorftime 当前站点是否开放这些维度；已返回的流量词/竞品关键词可继续用于需求和广告信号。",
                "retry_evidence": {
                    "asins_attempted": asins,
                    "attempted_asin_count": len(asins),
                    "empty_dimensions": empty_tools,
                    "successful_dimensions": successful_dimensions,
                    "tool_stats": tool_stats,
                },
                "fetched_at": fetched_at,
            }
        )

    invalidate_normalization(report_dir, data_pack)
    write_json(data_path, data_pack)
    summary = {
        "collection_ready": bool(asins) and (keyword_rows_added > 0 or product_patches > 0),
        "asins_attempted": asins,
        "calls": calls,
        "product_patches": product_patches,
        "keyword_rows_added": keyword_rows_added,
        "tool_stats": tool_stats,
        "empty_tools": empty_tools,
        "successful_dimensions": successful_dimensions,
        "stale_product_enrichment_gaps_removed": stale_product_enrichment_gaps_removed,
        "errors": errors,
    }
    write_json(report_dir / "data" / "normalized" / "product_enrichment_collection_summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect Sorftime Amazon product enrichment dimensions.")
    parser.add_argument("--dir", required=True, type=Path)
    parser.add_argument("--max-products", type=int, default=10)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--site", default="US")
    parser.add_argument("--sleep", type=float, default=0.1)
    args = parser.parse_args(argv)
    summary = collect(args.dir, args.max_products, args.max_pages, args.site, args.sleep)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["collection_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
