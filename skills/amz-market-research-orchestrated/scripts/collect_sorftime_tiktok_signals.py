#!/usr/bin/env python3
"""Collect Sorftime TikTok Shop product, video, trend, and creator signals."""

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


SIMILAR_TOOL = "tiktok_similar_product"
DETAIL_TOOL = "tiktok_product_detail"
TREND_TOOL = "tiktok_product_trend"
VIDEO_TOOL = "tiktok_product_video"
AUTHOR_TOOL = "tiktok_product_video_author"


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
    content = result.get("content") or []
    for item in content:
        if item.get("type") != "text":
            continue
        text = item.get("text") or ""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            continue
    return []


def content_rows(response: dict[str, Any]) -> list[dict[str, Any]]:
    payload = content_payload(response)
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


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
            "limitation": "Sorftime TikTok Shop sample; use as content/channel signal, not Amazon demand proof.",
        }
    )


def infer_seed_terms(data_pack: dict[str, Any], provided: list[str], max_seeds: int = 6) -> list[str]:
    seeds: list[str] = []
    for seed in provided:
        clean = normalize_space(seed)
        if clean and clean not in seeds:
            seeds.append(clean)

    research_object = data_pack.get("research_object") or {}
    if isinstance(research_object, dict):
        value = normalize_space(research_object.get("value"))
        if value and value not in seeds:
            seeds.append(value)

    for product in data_pack.get("products") or []:
        if not isinstance(product, dict):
            continue
        title = normalize_space(product.get("title") or product.get("title_cn"))
        if title and title not in seeds:
            seeds.append(title)
        if len(seeds) >= max_seeds:
            break

    for keyword in data_pack.get("keywords") or []:
        if not isinstance(keyword, dict):
            continue
        text = normalize_space(keyword.get("keyword"))
        if text and re.search(r"[a-zA-Z]", text) and text not in seeds:
            seeds.append(text)
        if len(seeds) >= max_seeds:
            break
    return seeds[:max_seeds]


def product_entity(row: dict[str, Any], source_id: str, seed: str) -> dict[str, Any]:
    return {
        "product_id": str(first(row, "ProductId", "productId", "product_id") or "").strip(),
        "title": first(row, "Title", "标题", "title", "name"),
        "brand": first(row, "品牌", "brand", "Brand"),
        "seller": first(row, "卖家", "seller", "Seller"),
        "image_url": first(row, "主图", "image_url", "Photo"),
        "weekly_sales": to_number(first(row, "周销量", "weekly_sales", "WeeklySales")),
        "monthly_sales": to_number(first(row, "月销量", "monthly_sales", "MonthlySales")),
        "price": to_number(first(row, "价格", "price", "Price")),
        "rating": to_number(first(row, "星级", "rating", "Score")),
        "review_count": to_number(first(row, "评论数量", "评论数", "review_count", "ReviewCount")),
        "seed_keyword": seed,
        "source_id": source_id,
        "provider": "sorftime",
    }


def detail_patch(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "title": first(row, "标题", "Title", "title"),
        "brand": first(row, "品牌", "brand", "Brand"),
        "weekly_sales": to_number(first(row, "周销量", "weekly_sales")),
        "lifetime_sales": to_number(first(row, "累计销量", "lifetime_sales")),
        "price": to_number(first(row, "价格", "price", "Price")),
        "rating": to_number(first(row, "星级", "rating")),
        "review_count": to_number(first(row, "评论数", "评论数量", "review_count")),
        "category": first(row, "所属类目", "category"),
        "sales_trend": first(row, "产品销量趋势", "sales_trend"),
        "price_trend": first(row, "产品价格趋势", "price_trend"),
    }


def trend_patch(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "sales_trend": first(row, "产品销量趋势", "sales_trend"),
        "price_trend": first(row, "产品价格趋势", "price_trend"),
        "rating_trend": first(row, "星级趋势", "rating_trend"),
        "review_trend": first(row, "评论数量趋势", "review_trend"),
        "new_video_trend": first(row, "新增带货视频数趋势", "new_video_trend"),
        "new_author_trend": first(row, "新增带货达人数趋势", "new_author_trend"),
    }


def video_id_from_url(url: Any) -> str:
    text = str(url or "")
    match = re.search(r"/video/(\d+)", text)
    return match.group(1) if match else ""


def video_entity(row: dict[str, Any], source_id: str, product_id: str) -> dict[str, Any]:
    url = first(row, "url", "URL")
    return {
        "video_id": first(row, "video_id", "VideoId") or video_id_from_url(url),
        "product_id": product_id,
        "title": first(row, "标题", "Title", "title"),
        "url": url,
        "published_at": first(row, "视频发布时间", "published_at"),
        "tags": first(row, "标签", "tags"),
        "views": to_number(first(row, "播放量", "views")),
        "likes": to_number(first(row, "获赞量", "likes")),
        "author": first(row, "达人", "author"),
        "author_followers": to_number(first(row, "达人粉丝量", "author_followers")),
        "source_id": source_id,
        "provider": "sorftime",
    }


def author_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "author_count": to_number(first(row, "带货达人数", "author_count")),
        "follower_buckets": first(row, "带货达人粉丝量", "follower_buckets"),
        "top_authors": first(row, "达人清单", "top_authors") or [],
    }


def product_identity(product: dict[str, Any]) -> str:
    return str(product.get("product_id") or "").strip()


def video_identity(video: dict[str, Any]) -> str:
    return str(video.get("url") or video.get("video_id") or "").strip().casefold()


def merge_product(data_pack: dict[str, Any], entity: dict[str, Any]) -> bool:
    product_id = product_identity(entity)
    if not product_id:
        return False
    for existing in data_pack.setdefault("tiktok_products", []):
        if product_identity(existing) == product_id:
            for key, value in entity.items():
                if value not in (None, "", []):
                    existing[key] = value
            return False
    data_pack["tiktok_products"].append(entity)
    return True


def merge_video(data_pack: dict[str, Any], entity: dict[str, Any]) -> bool:
    identity = video_identity(entity)
    if not identity:
        return False
    for existing in data_pack.setdefault("tiktok_videos", []):
        if video_identity(existing) == identity:
            for key, value in entity.items():
                if value not in (None, "", []):
                    existing[key] = value
            return False
    data_pack["tiktok_videos"].append(entity)
    return True


def invalidate_normalization(report_dir: Path, data_pack: dict[str, Any]) -> None:
    data_pack.pop("normalization", None)
    for filename in ["normalization_baseline.json", "cross_validated_data_pack.json", "normalized_data_pack.json"]:
        path = report_dir / "data" / "normalized" / filename
        if path.exists():
            path.unlink()


def run_call(url: str, raw_dir: Path, tool: str, args: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]], Path]:
    raw_path = raw_dir / f"sorftime_{tool}_{slug(args.get('searchName') or args.get('productId') or args.get('nodeId'))}_p{args.get('page', 1):03d}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.json"
    response = call_tool(url, tool, args)
    rows = content_rows(response)
    write_json(raw_path, {"tool": tool, "args": args, "result": response, "parsed": rows})
    return response, rows, raw_path


def collect(
    report_dir: Path,
    site: str,
    seeds: list[str],
    max_seeds: int,
    max_pages: int,
    max_products_detail: int,
    video_pages: int,
    min_signals: int,
    sleep_seconds: float,
) -> dict[str, Any]:
    data_path = report_dir / "data" / "data_pack.json"
    data_pack = load_json(data_path, {})
    data_pack.setdefault("sources", [])
    data_pack.setdefault("tiktok_products", [])
    data_pack.setdefault("tiktok_videos", [])
    data_pack.setdefault("data_gaps", [])
    raw_dir = report_dir / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    fetched_at = utc_now()
    seed_terms = infer_seed_terms(data_pack, seeds, max_seeds)
    url = mcp_url() if seed_terms else ""
    calls = 0
    products_added = 0
    videos_added = 0
    errors: list[dict[str, Any]] = []

    for seed in seed_terms:
        for page in range(1, max_pages + 1):
            args = {"searchName": seed, "page": page, "site": site}
            try:
                _, rows, raw_path = run_call(url, raw_dir, SIMILAR_TOOL, args)
                source_id = f"sf_tiktok_similar_{slug(seed)}_p{page:03d}"
                add_source(data_pack, source_id, SIMILAR_TOOL, args, raw_path, fetched_at)
                for row in rows:
                    if merge_product(data_pack, product_entity(row, source_id, seed)):
                        products_added += 1
            except Exception as exc:
                errors.append({"tool": SIMILAR_TOOL, "args": args, "error": f"{type(exc).__name__}: {exc}"})
            calls += 1
            if sleep_seconds:
                time.sleep(sleep_seconds)

    detail_targets = sorted(
        [item for item in data_pack.get("tiktok_products") or [] if item.get("product_id")],
        key=lambda item: to_number(item.get("monthly_sales")) or 0,
        reverse=True,
    )[:max_products_detail]
    for product in detail_targets:
        product_id = str(product.get("product_id"))
        for tool, args, patcher in [
            (DETAIL_TOOL, {"productId": product_id, "site": site}, detail_patch),
            (TREND_TOOL, {"productId": product_id, "site": site}, trend_patch),
            (AUTHOR_TOOL, {"productId": product_id, "site": site}, author_summary),
        ]:
            try:
                _, rows, raw_path = run_call(url, raw_dir, tool, args)
                source_id = f"sf_{tool}_{slug(product_id)}"
                add_source(data_pack, source_id, tool, args, raw_path, fetched_at)
                if rows:
                    product.update({key: value for key, value in patcher(rows[0]).items() if value not in (None, "", [])})
                    product.setdefault("source_ids", [])
                    if source_id not in product["source_ids"]:
                        product["source_ids"].append(source_id)
            except Exception as exc:
                errors.append({"tool": tool, "args": args, "error": f"{type(exc).__name__}: {exc}"})
            calls += 1
            if sleep_seconds:
                time.sleep(sleep_seconds)

        for page in range(1, video_pages + 1):
            args = {"productId": product_id, "page": page, "site": site}
            try:
                _, rows, raw_path = run_call(url, raw_dir, VIDEO_TOOL, args)
                source_id = f"sf_tiktok_video_{slug(product_id)}_p{page:03d}"
                add_source(data_pack, source_id, VIDEO_TOOL, args, raw_path, fetched_at)
                for row in rows:
                    if merge_video(data_pack, video_entity(row, source_id, product_id)):
                        videos_added += 1
            except Exception as exc:
                errors.append({"tool": VIDEO_TOOL, "args": args, "error": f"{type(exc).__name__}: {exc}"})
            calls += 1
            if sleep_seconds:
                time.sleep(sleep_seconds)

    signal_total = len(data_pack.get("tiktok_products") or []) + len(data_pack.get("tiktok_videos") or [])
    collection_ready = signal_total >= min_signals
    if not collection_ready:
        data_pack["data_gaps"].append(
            {
                "type": "tiktok_signal_depth",
                "module": "tiktok_signal_depth",
                "gap": f"TikTok 商品/视频信号不足：当前 {signal_total}/{min_signals}。",
                "impact": "内容场景和渠道热度只能标记为未知，不能作为 Amazon 需求证明。",
                "next_action": "确认 Sorftime TikTok 站点、搜索词和产品 ID 后重新采集。",
                "fetched_at": fetched_at,
            }
        )

    invalidate_normalization(report_dir, data_pack)
    write_json(data_path, data_pack)
    summary = {
        "collection_ready": collection_ready,
        "site": site,
        "seed_terms": seed_terms,
        "calls": calls,
        "products_total": len(data_pack.get("tiktok_products") or []),
        "videos_total": len(data_pack.get("tiktok_videos") or []),
        "products_added": products_added,
        "videos_added": videos_added,
        "errors": errors,
    }
    write_json(report_dir / "data" / "normalized" / "tiktok_collection_summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect Sorftime TikTok Shop signals into data_pack.json.")
    parser.add_argument("--dir", required=True, type=Path, help="Report directory containing data/data_pack.json.")
    parser.add_argument("--site", default="US", choices=["Unknow", "US", "MY", "PH", "VN", "TH", "ID", "GB", "JP"])
    parser.add_argument("--seed", action="append", default=[], help="TikTok product search seed. Repeatable.")
    parser.add_argument("--max-seeds", type=int, default=4)
    parser.add_argument("--max-pages", type=int, default=1)
    parser.add_argument("--max-products-detail", type=int, default=3)
    parser.add_argument("--video-pages", type=int, default=1)
    parser.add_argument("--min-signals", type=int, default=1)
    parser.add_argument("--sleep", type=float, default=0.15)
    args = parser.parse_args(argv)
    summary = collect(
        args.dir,
        args.site,
        args.seed,
        args.max_seeds,
        args.max_pages,
        args.max_products_detail,
        args.video_pages,
        args.min_signals,
        args.sleep,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["collection_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
