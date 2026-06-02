#!/usr/bin/env python3
"""Collect Sorftime product review evidence into a report Data Pack."""

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


ENTITY_KEY = "reviews"


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
    text = re.sub(r"[^a-zA-Z0-9]+", "_", str(value or "").strip().lower()).strip("_")
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
    content = result.get("content") or []
    rows: list[dict[str, Any]] = []
    for item in content:
        if item.get("type") != "text":
            continue
        text = item.get("text") or ""
        try:
            parsed = json.loads(text)
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
    text = re.sub(r"[,，★星]", "", str(value)).strip()
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return value


def source_exists(data_pack: dict[str, Any], source_id: str) -> bool:
    return any(source.get("source_id") == source_id for source in data_pack.get("sources") or [])


def infer_asins(data_pack: dict[str, Any], provided: list[str]) -> list[str]:
    asins: list[str] = []
    for asin in provided:
        clean = str(asin or "").strip().upper()
        if clean and clean not in asins:
            asins.append(clean)
    research_object = data_pack.get("research_object") or {}
    if isinstance(research_object, dict):
        for asin in research_object.get("seed_asins") or []:
            clean = str(asin or "").strip().upper()
            if clean and clean not in asins:
                asins.append(clean)
    for product in sorted(data_pack.get("products") or [], key=lambda item: float(item.get("estimated_monthly_sales") or 0), reverse=True):
        clean = str(product.get("asin") or "").strip().upper()
        if clean and clean not in asins:
            asins.append(clean)
        if len(asins) >= 12:
            break
    return asins


def review_entity(row: dict[str, Any], asin: str, source_id: str, review_type: str) -> dict[str, Any]:
    return {
        "asin": asin,
        "rating": to_number(first(row, "评星", "星级", "rating", "star", "stars")),
        "review_date": first(row, "评论日期", "日期", "date", "review_date"),
        "title": first(row, "标题", "评论标题", "title", "review_title"),
        "text": first(row, "评论", "评论内容", "content", "text", "body", "comment"),
        "variant": first(row, "评论产品的属性", "属性", "variant"),
        "helpful_votes": to_number(first(row, "有用数", "helpful", "helpful_votes")),
        "sample_type": f"sorftime_{review_type.lower()}_review",
        "source_id": source_id,
        "provider": "sorftime",
    }


def invalidate_normalization(report_dir: Path, data_pack: dict[str, Any]) -> None:
    data_pack.pop("normalization", None)
    for filename in ["normalization_baseline.json", "cross_validated_data_pack.json", "normalized_data_pack.json"]:
        path = report_dir / "data" / "normalized" / filename
        if path.exists():
            path.unlink()


def add_data_gap(data_pack: dict[str, Any], gap: dict[str, Any]) -> None:
    gaps = data_pack.setdefault("data_gaps", [])
    fingerprint = (gap.get("type"), gap.get("asin"), gap.get("review_type"))
    for existing in gaps:
        if not isinstance(existing, dict):
            continue
        if (existing.get("type"), existing.get("asin"), existing.get("review_type")) == fingerprint:
            existing.update(gap)
            return
    gaps.append(gap)


def collect(report_dir: Path, asins: list[str], review_type: str, amz_site: str, sleep_seconds: float) -> dict[str, Any]:
    data_path = report_dir / "data" / "data_pack.json"
    data_pack = load_json(data_path, {})
    url = mcp_url()
    raw_dir = report_dir / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    fetched_at = utc_now()
    asin_list = infer_asins(data_pack, asins)
    added = 0
    calls = 0
    failures: list[dict[str, Any]] = []

    for asin in asin_list:
        args = {"asin": asin, "reviewType": review_type, "amzSite": amz_site}
        try:
            response = call_tool(url, "product_reviews", args)
            rows = content_rows(response)
        except Exception as exc:
            failures.append({"asin": asin, "review_type": review_type, "error": str(exc)})
            add_data_gap(
                data_pack,
                {
                    "type": "review_collection_failure",
                    "asin": asin,
                    "review_type": review_type,
                    "gap": "Sorftime review collection failed for one ASIN.",
                    "impact": "VOC coverage is thinner for this ASIN; critic and validator must reflect lower confidence.",
                    "error": str(exc),
                    "fetched_at": fetched_at,
                },
            )
            calls += 1
            if sleep_seconds:
                time.sleep(sleep_seconds)
            continue
        calls += 1
        raw_path = raw_dir / f"sorftime_product_reviews_{slug(asin)}_{slug(review_type)}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.json"
        write_json(raw_path, {"tool": "product_reviews", "args": args, "response": response, "rows": rows})
        source_id = f"sf_product_reviews_{slug(asin)}_{slug(review_type)}"
        if not source_exists(data_pack, source_id):
            data_pack.setdefault("sources", []).append(
                {
                    "source_id": source_id,
                    "provider": "sorftime",
                    "tool": "product_reviews",
                    "query": args,
                    "raw_path": str(raw_path),
                    "fetched_at": fetched_at,
                    "confidence": "high",
                    "limitation": "Sorftime product review sample; review availability depends on ASIN and review type.",
                }
            )
        for row in rows:
            entity = review_entity(row, asin, source_id, review_type)
            if entity.get("text") or entity.get("title"):
                data_pack.setdefault(ENTITY_KEY, []).append(entity)
                added += 1
        if sleep_seconds:
            time.sleep(sleep_seconds)

    invalidate_normalization(report_dir, data_pack)
    write_json(data_path, data_pack)
    summary = {
        "reviews_added": added,
        "calls": calls,
        "review_type": review_type,
        "asin_count": len(asin_list),
        "failures": failures,
    }
    write_json(report_dir / "data" / "normalized" / "review_collection_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", required=True, type=Path, help="Report directory, e.g. reports/foo")
    parser.add_argument("--asin", action="append", default=[], help="ASIN to collect. Repeatable.")
    parser.add_argument("--review-type", default="Both", choices=["Positive", "Neutral", "Negative", "Both"])
    parser.add_argument("--amz-site", default="US")
    parser.add_argument("--sleep", type=float, default=0.05)
    args = parser.parse_args()
    print(json.dumps(collect(args.dir, args.asin, args.review_type, args.amz_site, args.sleep), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
