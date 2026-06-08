#!/usr/bin/env python3
"""Collect multi-round Sorftime 1688 supplier quotes into a report Data Pack."""

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


ENTITY_KEY = "suppliers"
TOOL_NAME = "ali1688_similar_product"


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
        "price_rmb": to_number(first(row, "价格", "price", "Price", "price_rmb", "起批价", "采购价")),
        "product_id": first(row, "ProductId", "product_id", "offer_id"),
        "photo_url": first(row, "Photo", "photo", "image", "image_url"),
        "sales_30d": to_number(first(row, "30天销量", "近30天销量", "sales_30d", "SalesOf30d", "月销量")),
        "cumulative_sales": to_number(first(row, "CumulativeSaleCount", "累计销量", "cumulative_sales")),
        "monthly_sales": to_number(first(row, "MonthlySaleCount", "月销量", "monthly_sales")),
        "monthly_sales_amount": to_number(first(row, "MonthlySaleAmount", "月销额", "monthly_sales_amount")),
        "review_count": to_number(first(row, "ReviewCount", "评论数", "review_count")),
        "star": to_number(first(row, "Star", "星级", "star")),
        "moq": to_number(first(row, "起批量", "moq", "MOQ")),
        "shipping_origin": first(row, "发货地", "shipping_origin", "ShippingOrigin", "产地"),
        "url": first(row, "商品链接", "url", "URL", "link", "product_url"),
        "seed_keyword": seed_keyword,
        "schema_limitation": "Current ali1688_similar_product response may omit product title and URL; ProductId + StoreName + Price are used as quote identity when title/URL are unavailable.",
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


def collect(report_dir: Path, min_valid_quotes: int, seeds: list[str], max_rounds: int, max_pages: int, sleep_seconds: float) -> dict[str, Any]:
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
    url = mcp_url() if seed_terms else ""

    for round_idx, seed in enumerate(seed_terms, 1):
        before = valid_quote_count(data_pack.get(ENTITY_KEY) or [])
        returned = 0
        if valid_quote_count(data_pack.get(ENTITY_KEY) or []) >= min_valid_quotes:
            break
        args = {"searchName": seed}
        raw_path = raw_dir / f"sorftime_{TOOL_NAME}_{slug(seed)}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.json"
        try:
            response = call_tool(url, TOOL_NAME, args)
            rows = content_rows(response)
        except Exception as exc:
            response = {"error": f"{type(exc).__name__}: {exc}", "tool": TOOL_NAME, "args": args}
            rows = []
            errors.append({"seed": seed, "error": response["error"]})
        calls += 1
        returned += len(rows)
        source_id = f"sf_1688_{slug(seed)}"
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
                    "limitation": "Sorftime 1688 similar product quote sample; values are third-party estimates.",
                }
            )
        for row in rows:
            entity = supplier_entity(row, source_id, seed)
            if is_valid_quote(entity):
                data_pack[ENTITY_KEY].append(entity)
                added += 1
        write_json(raw_path, {"tool": TOOL_NAME, "args": args, "result": response, "parsed": rows})
        if sleep_seconds:
            time.sleep(sleep_seconds)
        after = valid_quote_count(data_pack.get(ENTITY_KEY) or [])
        rounds.append(
            {
                "round": round_idx,
                "seed": seed,
                "returned_rows": returned,
                "valid_quotes_before": before,
                "valid_quotes_after": after,
                "new_valid_quotes": max(0, after - before),
                "dedupe_loss": max(0, added - after),
            }
        )
        if after >= min_valid_quotes:
            break

    total_valid = valid_quote_count(data_pack.get(ENTITY_KEY) or [])
    collection_ready = total_valid >= min_valid_quotes
    failure_reason = "" if collection_ready else f"1688有效报价不足50条：当前 {total_valid}/{min_valid_quotes}，已尝试搜索词 {', '.join(seed_terms) or '-'}。"
    if not collection_ready:
        data_pack["data_gaps"].append(
            {
                "type": "supplier_quote_depth",
                "module": "supplier_quote_depth",
                "gap": failure_reason,
                "impact": "供应链成本和毛利率测算必须阻断，不能生成最终客户结论。",
                "next_action": "继续提供或授权 Sorftime 1688 数据，或扩大中文搜索词后重新采集。",
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
        "suppliers_added": added,
        "calls": calls,
        "rounds": rounds,
        "attempted_seeds": seed_terms,
        "errors": errors,
        "failure_reason": failure_reason,
    }
    write_json(report_dir / "data" / "normalized" / "supplier_1688_collection_summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect Sorftime 1688 supplier quotes with multi-round seed retries.")
    parser.add_argument("--dir", required=True, type=Path, help="Report directory containing data/data_pack.json.")
    parser.add_argument("--min-valid-quotes", type=int, default=50)
    parser.add_argument("--seed", action="append", default=[], help="Chinese 1688 search seed. Repeatable.")
    parser.add_argument("--max-rounds", type=int, default=5)
    parser.add_argument("--max-pages", type=int, default=3, help="Deprecated for ali1688_similar_product; kept for CLI compatibility.")
    parser.add_argument("--sleep", type=float, default=0.15)
    args = parser.parse_args(argv)
    summary = collect(args.dir, args.min_valid_quotes, args.seed, args.max_rounds, args.max_pages, args.sleep)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["collection_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
