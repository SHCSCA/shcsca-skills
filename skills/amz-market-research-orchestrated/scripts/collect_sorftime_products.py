#!/usr/bin/env python3
"""Collect Sorftime Amazon competitor products into a report Data Pack."""

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


ENTITY_KEY = "products"
PRIMARY_TOOL = "product_search"
FALLBACK_TOOL = "keyword_search_results"
IMAGE_COVERAGE_GAP_TYPE = "competitor_image_coverage"
IMAGE_COVERAGE_MINIMUM = 0.25
DEFAULT_SEGMENT_SEEDS = [
    ("橱柜感应灯", "under cabinet motion sensor light"),
    ("RGB 灯带", "rgbic led strip lights"),
    ("智能灯泡", "smart light bulb"),
    ("氛围灯", "ambient night light"),
    ("户外感应灯", "outdoor motion sensor light"),
]
SEGMENT_RULES = [
    ("橱柜感应灯", ["under cabinet", "cabinet light", "motion sensor", "puck light"]),
    ("RGB 灯带", ["rgbic", "rgb led strip", "led strip", "strip lights", "light strip"]),
    ("智能灯泡", ["smart bulb", "a19", "light bulb"]),
    ("户外感应灯", ["outdoor", "solar", "security light", "flood light", "wall sconce"]),
    ("氛围灯", ["ambient", "night light", "table lamp", "sunset"]),
]
GENERIC_SEED_TOKENS = {"smart", "light", "lights", "lighting", "led", "lamp", "lamps", "for", "with", "and"}


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


def normalize_space(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


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


def content_payload(response: dict[str, Any]) -> Any:
    result = response.get("result") or {}
    if result.get("isError"):
        content = result.get("content") or []
        message = "; ".join(str(item.get("text") or "") for item in content if isinstance(item, dict))
        raise RuntimeError(message or "MCP tool returned isError=true.")
    for item in result.get("content") or []:
        if item.get("type") != "text":
            continue
        try:
            return json.loads(item.get("text") or "")
        except json.JSONDecodeError:
            continue
    return []


def flatten_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("rows", "data", "items", "list", "records", "products", "result"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
        return [payload]
    return []


def content_rows(response: dict[str, Any]) -> list[dict[str, Any]]:
    return flatten_rows(content_payload(response))


def first(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if row.get(key) not in (None, ""):
            return row.get(key)
    return None


def to_number(value: Any) -> Any:
    if value in (None, ""):
        return None
    text = re.sub(r"[,，$¥￥]", "", str(value)).strip()
    try:
        return float(text) if "." in text else int(text)
    except ValueError:
        return value


def infer_segment(text: Any, fallback: str = "") -> str:
    combined = normalize_space(text).casefold()
    for segment, needles in SEGMENT_RULES:
        if any(needle in combined for needle in needles):
            return segment
    return fallback or "未分层"


def token_set(value: Any) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", normalize_space(value).casefold()) if token and token not in GENERIC_SEED_TOKENS}


def directly_inferred_segment(text: Any) -> str:
    combined = normalize_space(text).casefold()
    for segment, needles in SEGMENT_RULES:
        if any(needle in combined for needle in needles):
            return segment
    return ""


def is_relevant_product(product: dict[str, Any]) -> bool:
    combined = " ".join(
        normalize_space(product.get(key))
        for key in ("title", "category", "subcategory", "seed_keyword")
        if product.get(key)
    )
    title_category = " ".join(normalize_space(product.get(key)) for key in ("title", "category", "subcategory") if product.get(key))
    if directly_inferred_segment(title_category):
        return True
    seed_tokens = token_set(product.get("seed_keyword"))
    product_tokens = token_set(title_category)
    if not seed_tokens:
        return False
    return len(seed_tokens & product_tokens) >= min(2, len(seed_tokens))


def product_identity(product: dict[str, Any]) -> str:
    asin = normalize_space(product.get("asin")).upper()
    if asin:
        return f"asin|{asin}"
    title = normalize_space(product.get("title") or product.get("title_cn")).casefold()
    brand = normalize_space(product.get("brand")).casefold()
    return f"title|{brand}|{title}" if title else ""


def is_valid_competitor(product: dict[str, Any]) -> bool:
    sales_or_rank = product.get("estimated_monthly_sales") if product.get("estimated_monthly_sales") not in (None, "") else product.get("bsr")
    return bool(
        product_identity(product)
        and product.get("asin")
        and product.get("title")
        and product.get("brand")
        and product.get("segment_cn")
        and isinstance(to_number(product.get("price")), (int, float))
        and isinstance(to_number(product.get("rating")), (int, float))
        and isinstance(to_number(product.get("review_count")), (int, float))
        and isinstance(to_number(sales_or_rank), (int, float))
    )


def product_entity(row: dict[str, Any], source_id: str, seed: str, segment: str) -> dict[str, Any]:
    title = first(row, "标题", "title", "Title", "商品标题", "ProductTitle", "product_title", "name", "Name")
    return {
        "asin": first(row, "ASIN", "asin", "Asin", "商品ASIN", "产品ASIN码", "asinCode"),
        "title": title,
        "brand": first(row, "品牌", "brand", "Brand", "店铺品牌", "seller_brand"),
        "price": to_number(first(row, "价格", "price", "Price", "售价", "current_price", "BuyBoxPrice", "buy_box_price")),
        "rating": to_number(first(row, "评分", "rating", "Rating", "Star", "星级", "star")),
        "review_count": to_number(first(row, "评论数", "review_count", "ReviewCount", "reviews", "ratings_count", "评价数")),
        "estimated_monthly_sales": to_number(
            first(row, "月销量", "estimated_monthly_sales", "MonthlySales", "monthly_sales", "sales_30d", "近30天销量", "销量")
        ),
        "bsr": to_number(first(row, "BSR", "bsr", "大类排名", "排名", "rank")),
        "image_url": first(
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
        "url": first(row, "url", "URL", "link", "商品链接", "product_url"),
        "category": first(row, "所属大类", "category", "Category", "大类"),
        "subcategory": first(row, "所属细分类目", "subcategory", "Subcategory", "细分类目"),
        "segment_cn": infer_segment(f"{title} {first(row, '所属大类', 'category', 'Category', '大类')} {first(row, '所属细分类目', 'subcategory', 'Subcategory', '细分类目')}", segment),
        "segment": infer_segment(f"{title} {first(row, '所属大类', 'category', 'Category', '大类')} {first(row, '所属细分类目', 'subcategory', 'Subcategory', '细分类目')}", segment),
        "seed_keyword": seed,
        "source_id": source_id,
        "provider": "sorftime",
    }


def add_unique(values: list[str], value: Any) -> None:
    clean = normalize_space(value)
    if clean and clean not in values:
        values.append(clean)


def infer_seed_terms(data_pack: dict[str, Any], provided: list[str], max_seeds: int) -> list[tuple[str, str]]:
    broad_terms: list[str] = []
    for seed in provided:
        add_unique(broad_terms, seed)
    research_object = data_pack.get("research_object") or {}
    if isinstance(research_object, dict):
        add_unique(broad_terms, research_object.get("value"))
        for seed in research_object.get("seed_keywords") or []:
            add_unique(broad_terms, seed)
    elif research_object:
        add_unique(broad_terms, research_object)
    folded = " ".join(broad_terms).casefold()

    seeds: list[str] = []
    if any(token in folded for token in ("smart lighting", "lighting", "智能照明", "灯具")):
        for _segment, seed in DEFAULT_SEGMENT_SEEDS:
            add_unique(seeds, seed)

    for seed in provided:
        add_unique(seeds, seed)
    if isinstance(research_object, dict):
        add_unique(seeds, research_object.get("value"))
        for seed in research_object.get("seed_keywords") or []:
            add_unique(seeds, seed)
    elif research_object:
        add_unique(seeds, research_object)
    for keyword in data_pack.get("keywords") or []:
        if isinstance(keyword, dict):
            add_unique(seeds, keyword.get("keyword"))
        if len(seeds) >= max_seeds:
            break

    planned: list[tuple[str, str]] = []
    for seed in seeds:
        segment = infer_segment(seed)
        if (seed, segment) not in planned:
            planned.append((seed, segment))
        if len(planned) >= max_seeds:
            break
    return planned


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
            "limitation": "Sorftime Amazon product search sample; values are third-party estimates.",
        }
    )


def invalidate_normalization(report_dir: Path, data_pack: dict[str, Any]) -> None:
    data_pack.pop("normalization", None)
    for filename in ["normalization_baseline.json", "cross_validated_data_pack.json", "normalized_data_pack.json"]:
        path = report_dir / "data" / "normalized" / filename
        if path.exists():
            path.unlink()


def valid_competitor_count(products: list[dict[str, Any]]) -> int:
    seen: set[str] = set()
    count = 0
    for product in products:
        identity = product_identity(product)
        if is_valid_competitor(product) and is_relevant_product(product) and identity not in seen:
            seen.add(identity)
            count += 1
    return count


def segment_counts(products: list[dict[str, Any]]) -> dict[str, int]:
    seen: set[str] = set()
    counts: dict[str, int] = {}
    for product in products:
        identity = product_identity(product)
        if not identity or identity in seen or not is_valid_competitor(product) or not is_relevant_product(product):
            continue
        seen.add(identity)
        segment = normalize_space(product.get("segment_cn") or product.get("segment"))
        if segment and segment != "未分层":
            counts[segment] = counts.get(segment, 0) + 1
    return counts


def image_url_coverage(products: list[dict[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    total = 0
    with_image = 0
    for product in products:
        identity = product_identity(product)
        if not identity or identity in seen or not is_valid_competitor(product) or not is_relevant_product(product):
            continue
        seen.add(identity)
        total += 1
        if normalize_space(product.get("image_url")):
            with_image += 1
    return {
        "valid_competitors_total": total,
        "with_image_url": with_image,
        "coverage": round(with_image / total, 4) if total else 0,
    }


def sync_image_coverage_gap(data_pack: dict[str, Any], coverage: dict[str, Any], fetched_at: str) -> bool:
    existing = data_pack.setdefault("data_gaps", [])
    data_pack["data_gaps"] = [gap for gap in existing if gap.get("type") != IMAGE_COVERAGE_GAP_TYPE]
    total = int(coverage.get("valid_competitors_total") or 0)
    with_image = int(coverage.get("with_image_url") or 0)
    ratio = float(coverage.get("coverage") or 0)
    if total <= 0 or ratio >= IMAGE_COVERAGE_MINIMUM:
        return False
    if with_image == 0:
        gap_text = f"Amazon 竞品池当前 {total} 个有效竞品未返回可展示主图 URL。"
    else:
        gap_text = f"Amazon 竞品池当前 {total} 个有效竞品中仅 {with_image} 个返回可展示主图 URL，图片覆盖率 {ratio:.0%}。"
    data_pack["data_gaps"].append(
        {
            "type": IMAGE_COVERAGE_GAP_TYPE,
            "module": "amazon_competitor_images",
            "gap": gap_text,
            "impact": "竞品全景扫描和标杆竞品狙击拆解只能保留图片槽位与中文诊断，不能使用 1688 货源图冒充 Amazon 竞品图。",
            "next_action": "运行 collect_sorftime_product_enrichment.py 对核心 ASIN 调用 product_detail 补采图片字段；若多 ASIN 仍为空，保留诊断并记录 Sorftime 图片维度缺口。",
            "coverage": coverage,
            "fetched_at": fetched_at,
        }
    )
    return True


def collection_ready(products: list[dict[str, Any]], min_products: int, min_segments: int, min_per_segment: int) -> bool:
    if valid_competitor_count(products) < min_products:
        return False
    if min_segments <= 0 or min_per_segment <= 0:
        return True
    top_counts = sorted(segment_counts(products).values(), reverse=True)
    return len(top_counts) >= min_segments and all(count >= min_per_segment for count in top_counts[:min_segments])


def tool_call_variants(seed: str, page: int, site: str) -> list[tuple[str, dict[str, Any]]]:
    return [
        (PRIMARY_TOOL, {"keyword": seed, "page": page, "amzSite": site}),
        (PRIMARY_TOOL, {"searchName": seed, "page": page, "amzSite": site}),
        (FALLBACK_TOOL, {"keyword": seed, "page": page, "amzSite": site}),
    ]


def collect(
    report_dir: Path,
    min_products: int,
    seeds: list[str],
    max_seeds: int,
    max_pages: int,
    site: str,
    sleep_seconds: float,
    min_segments: int = 0,
    min_per_segment: int = 0,
) -> dict[str, Any]:
    data_path = report_dir / "data" / "data_pack.json"
    data_pack = load_json(data_path, {})
    data_pack.setdefault("sources", [])
    data_pack.setdefault(ENTITY_KEY, [])
    data_pack.setdefault("data_gaps", [])
    raw_dir = report_dir / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    fetched_at = utc_now()
    seed_terms = infer_seed_terms(data_pack, seeds, max_seeds)
    calls = 0
    added = 0
    rounds: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    rejected_rows = 0

    if not seed_terms:
        data_pack["data_gaps"].append(
            {
                "type": "product_collection_no_seed",
                "module": "competitor_pool_depth",
                "gap": "No Amazon product-search seed was available.",
                "impact": "Competitor pool cannot be expanded from Sorftime.",
                "next_action": "Provide a research_object.value or product-search seed keyword.",
                "fetched_at": fetched_at,
            }
        )
        invalidate_normalization(report_dir, data_pack)
        write_json(data_path, data_pack)
        summary = {
            "tool": PRIMARY_TOOL,
            "collection_ready": collection_ready(data_pack.get(ENTITY_KEY) or [], min_products, min_segments, min_per_segment),
            "min_products": min_products,
            "valid_competitors_total": valid_competitor_count(data_pack.get(ENTITY_KEY) or []),
            "image_url_coverage": image_url_coverage(data_pack.get(ENTITY_KEY) or []),
            "segment_counts": segment_counts(data_pack.get(ENTITY_KEY) or []),
            "products_added": 0,
            "calls": 0,
            "rounds": [],
            "attempted_seeds": [],
            "errors": [],
            "failure_reason": "No Amazon product-search seed was available.",
        }
        write_json(report_dir / "data" / "normalized" / "product_collection_summary.json", summary)
        return summary

    url = mcp_url()
    for seed, segment in seed_terms:
        for page in range(1, max_pages + 1):
            before = valid_competitor_count(data_pack.get(ENTITY_KEY) or [])
            if collection_ready(data_pack.get(ENTITY_KEY) or [], min_products, min_segments, min_per_segment):
                break
            rows: list[dict[str, Any]] = []
            entities: list[dict[str, Any]] = []
            used_tool = ""
            used_args: dict[str, Any] = {}
            response: dict[str, Any] = {}
            for tool, args in tool_call_variants(seed, page, site):
                raw_path = raw_dir / f"sorftime_{tool}_{slug(seed)}_p{page:03d}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.json"
                try:
                    response = call_tool(url, tool, args)
                    rows = content_rows(response)
                    candidate_entities = [
                        product_entity(row, f"sf_{tool}_{slug(seed)}_p{page:03d}", seed, segment)
                        for row in rows
                    ]
                    entities = [entity for entity in candidate_entities if is_valid_competitor(entity) and is_relevant_product(entity)]
                    write_json(raw_path, {"tool": tool, "args": args, "result": response, "parsed": rows})
                    calls += 1
                    if entities or tool == tool_call_variants(seed, page, site)[-1][0]:
                        used_tool = tool
                        used_args = args
                        break
                    rejected_rows += len(rows)
                except Exception as exc:
                    response = {"error": f"{type(exc).__name__}: {exc}", "tool": tool, "args": args}
                    errors.append({"seed": seed, "page": page, "tool": tool, "args": args, "error": response["error"]})
                    write_json(raw_path, {"tool": tool, "args": args, "result": response, "parsed": []})
                    calls += 1
            if rows and used_tool:
                source_id = f"sf_{used_tool}_{slug(seed)}_p{page:03d}"
                add_source(data_pack, source_id, used_tool, used_args, raw_path, fetched_at)
                for entity in entities:
                    entity["source_id"] = source_id
                    data_pack[ENTITY_KEY].append(entity)
                    added += 1
                rejected_rows += max(0, len(rows) - len(entities))
            after = valid_competitor_count(data_pack.get(ENTITY_KEY) or [])
            rounds.append(
                {
                    "seed": seed,
                    "segment": segment,
                    "page": page,
                    "returned_rows": len(rows),
                    "valid_competitors_before": before,
                    "valid_competitors_after": after,
                    "new_valid_competitors": max(0, after - before),
                }
            )
            if sleep_seconds:
                time.sleep(sleep_seconds)
        if collection_ready(data_pack.get(ENTITY_KEY) or [], min_products, min_segments, min_per_segment):
            break

    total_valid = valid_competitor_count(data_pack.get(ENTITY_KEY) or [])
    segment_summary = segment_counts(data_pack.get(ENTITY_KEY) or [])
    image_coverage = image_url_coverage(data_pack.get(ENTITY_KEY) or [])
    ready = collection_ready(data_pack.get(ENTITY_KEY) or [], min_products, min_segments, min_per_segment)
    if ready:
        failure_reason = ""
    elif total_valid < min_products:
        failure_reason = f"Amazon有效竞品不足：当前 {total_valid}/{min_products}，已尝试搜索词 {', '.join(seed for seed, _ in seed_terms) or '-'}。"
    else:
        failure_reason = f"Amazon赛道拆分不足：当前赛道分布 {segment_summary}，要求至少 {min_segments} 个赛道且每个不少于 {min_per_segment} 个有效竞品。"
    if not ready:
        data_pack["data_gaps"].append(
            {
                "type": "market_segment_split" if total_valid >= min_products else "competitor_pool_depth",
                "module": "market_segment_split" if total_valid >= min_products else "competitor_pool_depth",
                "gap": failure_reason,
                "impact": "市场深度、竞品狙击和毛利率参考价不能形成完整客户结论。",
                "next_action": "继续授权或调整 Sorftime Amazon product_search / keyword_search_results 数据源后补采。",
                "fetched_at": fetched_at,
            }
        )
    image_gap_recorded = sync_image_coverage_gap(data_pack, image_coverage, fetched_at)

    invalidate_normalization(report_dir, data_pack)
    write_json(data_path, data_pack)
    summary = {
        "tool": PRIMARY_TOOL,
        "fallback_tool": FALLBACK_TOOL,
        "collection_ready": ready,
        "min_products": min_products,
        "min_segments": min_segments,
        "min_per_segment": min_per_segment,
        "valid_competitors_total": total_valid,
        "image_url_coverage": image_coverage,
        "image_gap_recorded": image_gap_recorded,
        "segment_counts": segment_summary,
        "products_added": added,
        "rejected_irrelevant_or_incomplete_rows": rejected_rows,
        "calls": calls,
        "rounds": rounds,
        "attempted_seeds": [seed for seed, _ in seed_terms],
        "errors": errors,
        "failure_reason": failure_reason,
    }
    write_json(report_dir / "data" / "normalized" / "product_collection_summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect Sorftime Amazon product competitors into data_pack.json.")
    parser.add_argument("--dir", required=True, type=Path, help="Report directory containing data/data_pack.json.")
    parser.add_argument("--min-products", type=int, default=30)
    parser.add_argument("--seed", action="append", default=[], help="Amazon product search seed. Repeatable.")
    parser.add_argument("--max-seeds", type=int, default=8)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--site", default="US")
    parser.add_argument("--sleep", type=float, default=0.15)
    parser.add_argument("--min-segments", type=int, default=0)
    parser.add_argument("--min-per-segment", type=int, default=0)
    args = parser.parse_args(argv)
    summary = collect(args.dir, args.min_products, args.seed, args.max_seeds, args.max_pages, args.site, args.sleep, args.min_segments, args.min_per_segment)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["collection_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
