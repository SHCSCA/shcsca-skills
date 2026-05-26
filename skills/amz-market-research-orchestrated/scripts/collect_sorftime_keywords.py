#!/usr/bin/env python3
"""Collect paginated Sorftime keyword evidence into a generic report Data Pack."""

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


ENTITY_KEY = "keywords"
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
    text = re.sub(r"[,，]", "", str(value))
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return value


def keyword_entity(row: dict[str, Any], source_id: str, source_type: str) -> dict[str, Any]:
    return {
        "keyword": first(row, "关键词", "keyword"),
        "weekly_search_rank": to_number(first(row, "周搜索排名")),
        "weekly_search_volume": to_number(first(row, "周搜索量")),
        "weekly_rank_change": to_number(first(row, "周搜索排名变化")),
        "monthly_search_volume": to_number(first(row, "月搜索量")),
        "recommended_cpc": first(row, "cpc精准竞价", "cpc推荐竞价", "推荐cpc竞价"),
        "competitor_count": to_number(first(row, "搜索结果数", "搜索结果竞品数量")),
        "season_peak": first(row, "搜索量旺季", "季节性", "词搜索量旺季"),
        "front_page_avg_monthly_sales": to_number(first(row, "搜索结果首页自然位产品平均月销量")),
        "top100_sales_sum": to_number(first(row, "搜索结果前3页销量Top100产品月销量之和")),
        "avg_price_top3_pages": to_number(first(row, "搜索结果前3页产品平均销售价")),
        "source_type": source_type,
        "source_id": source_id,
        "provider": "sorftime",
    }


def infer_node_id(data_pack: dict[str, Any], explicit: str | None) -> str | None:
    if explicit:
        return explicit
    for category in data_pack.get("categories") or []:
        for key in ("node_id", "nodeId", "category_id"):
            if category.get(key):
                return str(category[key])
    for source in data_pack.get("sources") or []:
        query = source.get("query") or source.get("args") or {}
        if isinstance(query, dict):
            for key in ("nodeId", "node_id"):
                if query.get(key):
                    return str(query[key])
    return None


def infer_seeds(data_pack: dict[str, Any], provided: list[str]) -> list[str]:
    seeds: list[str] = []
    for seed in provided or []:
        if seed and seed not in seeds:
            seeds.append(seed)

    research_object = data_pack.get("research_object") or {}
    value = research_object.get("value") if isinstance(research_object, dict) else research_object
    if value:
        for part in re.split(r"[/,，|]+", str(value)):
            clean = part.strip()
            if clean and re.search(r"[a-zA-Z]", clean) and clean not in seeds:
                seeds.append(clean)

    for keyword in data_pack.get("keywords") or []:
        text = keyword.get("keyword")
        if text and re.search(r"[a-zA-Z]", str(text)) and text not in seeds:
            seeds.append(str(text))
        if len(seeds) >= 12:
            break

    return seeds[:20]


def source_exists(data_pack: dict[str, Any], source_id: str) -> bool:
    return any(source.get("source_id") == source_id for source in data_pack.get("sources") or [])


def invalidate_normalization(report_dir: Path, data_pack: dict[str, Any]) -> None:
    data_pack.pop("normalization", None)
    for filename in ["normalization_baseline.json", "cross_validated_data_pack.json"]:
        path = report_dir / "data" / "normalized" / filename
        if path.exists():
            path.unlink()


def collect(report_dir: Path, min_keywords: int, node_id: str | None, seeds: list[str], max_pages: int, sleep_seconds: float) -> dict[str, Any]:
    data_path = report_dir / "data" / "data_pack.json"
    data_pack = load_json(data_path, {})
    url = mcp_url()
    raw_dir = report_dir / "data" / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    fetched_at = utc_now()
    inferred_node = infer_node_id(data_pack, node_id)
    seed_terms = infer_seeds(data_pack, seeds)
    added = 0
    calls = 0

    def add_rows(tool: str, args: dict[str, Any], rows: list[dict[str, Any]], raw_path: Path) -> None:
        nonlocal added
        source_id = f"sf_{tool}_{slug(args.get('nodeId') or args.get('keyword'))}_p{args.get('page', 1):03d}"
        if not source_exists(data_pack, source_id):
            data_pack.setdefault("sources", []).append(
                {
                    "source_id": source_id,
                    "provider": "sorftime",
                    "tool": tool,
                    "query": args,
                    "raw_path": str(raw_path),
                    "fetched_at": fetched_at,
                    "confidence": "high",
                    "limitation": "Sorftime paginated keyword sample; values are third-party estimates.",
                }
            )
        source_type = "category_keywords" if tool == "category_keywords" else "keyword_extends"
        for row in rows:
            entity = keyword_entity(row, source_id, source_type)
            if entity.get("keyword"):
                data_pack.setdefault(ENTITY_KEY, []).append(entity)
                added += 1

    tasks: list[tuple[str, dict[str, Any]]] = []
    if inferred_node:
        for page in range(1, max_pages + 1):
            tasks.append(("category_keywords", {"nodeId": inferred_node, "page": page, "amzSite": "US"}))
    for seed in seed_terms:
        for page in range(1, max_pages + 1):
            tasks.append(("keyword_extends", {"keyword": seed, "page": page, "keywordSupportSite": "US"}))

    for tool, args in tasks:
        if len(data_pack.get(ENTITY_KEY) or []) >= min_keywords:
            break
        raw_path = raw_dir / f"sorftime_{tool}_{slug(args.get('nodeId') or args.get('keyword'))}_p{args.get('page', 1):03d}_{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}.json"
        try:
            response = call_tool(url, tool, args)
            rows = content_rows(response)
        except Exception as exc:
            response = {"error": f"{type(exc).__name__}: {exc}", "tool": tool, "args": args}
            rows = []
        write_json(raw_path, {"tool": tool, "args": args, "result": response, "parsed": rows})
        calls += 1
        if rows:
            add_rows(tool, args, rows, raw_path)
        if sleep_seconds:
            time.sleep(sleep_seconds)

    invalidate_normalization(report_dir, data_pack)
    write_json(data_path, data_pack)
    summary = {
        "keywords_total": len(data_pack.get(ENTITY_KEY) or []),
        "keywords_added": added,
        "calls": calls,
        "min_keywords": min_keywords,
        "node_id": inferred_node,
        "seed_count": len(seed_terms),
    }
    write_json(report_dir / "data" / "normalized" / "keyword_collection_summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect paginated Sorftime keyword samples into data_pack.json.")
    parser.add_argument("--dir", required=True, help="Report directory containing data/data_pack.json.")
    parser.add_argument("--min-keywords", type=int, default=1000, help="Minimum keyword rows required in data_pack.json.")
    parser.add_argument("--node-id", default=None, help="Amazon category nodeId for category_keywords.")
    parser.add_argument("--seed", action="append", default=[], help="Seed keyword for keyword_extends. Can be repeated.")
    parser.add_argument("--max-pages", type=int, default=50, help="Max pages per source. Sorftime returns 20 rows per page.")
    parser.add_argument("--sleep", type=float, default=0.15, help="Seconds between MCP calls.")
    args = parser.parse_args(argv)
    summary = collect(Path(args.dir), args.min_keywords, args.node_id, args.seed, args.max_pages, args.sleep)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["keywords_total"] >= args.min_keywords else 2


if __name__ == "__main__":
    raise SystemExit(main())
