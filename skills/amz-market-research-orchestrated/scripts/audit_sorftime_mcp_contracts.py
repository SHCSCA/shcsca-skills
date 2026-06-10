#!/usr/bin/env python3
"""Audit Sorftime MCP schemas and actual returned fields for a report run."""

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


AMAZON_TOOLS = [
    "keyword_detail",
    "keyword_extends",
    "keyword_search_results",
    "product_search",
    "product_detail",
    "product_trend",
    "product_reviews",
    "product_variations",
    "product_traffic_terms",
    "competitor_product_keywords",
    "category_name_search",
    "category_search_from_product_name",
]
TIKTOK_TOOLS = [
    "tiktok_similar_product",
    "tiktok_product_detail",
    "tiktok_product_trend",
    "tiktok_product_video",
    "tiktok_product_video_author",
    "tiktok_author",
    "tiktok_category_name_search",
]
SUPPLY_TOOLS = ["ali1688_similar_product"]
ALI1688_DOCUMENTED_FIELDS = {
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
URL_FIELD_ALIASES = {"URL", "Url", "url"}
NORMALIZATION_FIELD_REQUIREMENTS = {
    "keyword_detail": {
        "keyword": ["关键词", "keyword"],
        "monthly_search_volume": ["月搜索量", "monthly_search_volume"],
    },
    "keyword_extends": {
        "keyword": ["关键词", "keyword"],
        "monthly_search_volume": ["月搜索量", "monthly_search_volume"],
    },
    "keyword_search_results": {
        "asin": ["ASIN", "asin", "产品ASIN码"],
        "title": ["标题", "Title", "title"],
        "brand": ["品牌", "Brand", "brand"],
        "price": ["价格", "Price", "price"],
        "sales": ["本产品月销量", "月销量", "estimated_monthly_sales"],
    },
    "product_search": {
        "asin": ["产品ASIN码", "ASIN", "asin"],
        "title": ["标题", "Title", "title"],
        "brand": ["品牌", "Brand", "brand"],
        "price": ["价格", "Price", "price"],
        "rating": ["星级", "评分", "rating"],
        "review_count": ["评论数", "ReviewCount", "review_count"],
        "sales": ["月销量", "estimated_monthly_sales", "MonthlySales"],
    },
    "product_detail": {
        "title": ["标题", "Title", "title"],
        "brand": ["品牌", "Brand", "brand"],
        "price": ["价格", "Price", "price"],
    },
    "product_reviews": {
        "title": ["标题", "Title", "title"],
        "rating": ["评星", "rating", "Rating"],
        "review_text": ["评论", "review", "text"],
        "review_date": ["评论日期", "date", "review_date"],
    },
    "product_traffic_terms": {
        "keyword": ["关键词", "keyword"],
        "monthly_search_volume": ["月搜索量", "monthly_search_volume"],
        "exposure_position": ["曝光位置", "最近自然曝光位置", "最近广告曝光位置"],
    },
    "competitor_product_keywords": {
        "keyword": ["关键词", "keyword"],
        "monthly_search_volume": ["关键词月搜索量", "月搜索量", "monthly_search_volume"],
        "exposure_position": ["曝光位置", "exposure_position"],
    },
    "category_name_search": {
        "category_name": ["CategoryName", "类目名称"],
        "node_id": ["NodeId", "nodeid"],
    },
    "category_search_from_product_name": {
        "category_name": ["类目名称", "CategoryName"],
        "top100_units": ["Top100产品月销量"],
        "average_price": ["平均价格"],
    },
    "tiktok_similar_product": {
        "product_id": ["ProductId", "productId", "product_id"],
        "title": ["Title", "标题", "title"],
        "price": ["价格", "Price", "price"],
        "monthly_sales": ["月销量", "monthly_sales"],
    },
    "tiktok_product_detail": {
        "title": ["标题", "Title", "title"],
        "price": ["价格", "Price", "price"],
        "monthly_sales": ["月销量", "monthly_sales"],
        "category": ["所属类目", "category"],
    },
    "tiktok_product_trend": {
        "sales_trend": ["产品销量趋势", "sales_trend"],
        "price_trend": ["产品价格趋势", "price_trend"],
    },
    "tiktok_product_video": {
        "url": ["url", "URL"],
        "title": ["标题", "Title", "title"],
        "views": ["播放量", "views"],
        "author": ["达人", "author"],
    },
    "tiktok_product_video_author": {
        "author_count": ["带货达人数", "author_count"],
        "top_authors": ["达人清单", "top_authors"],
    },
    "tiktok_category_name_search": {
        "category_name": ["类目名称", "CategoryName"],
        "node_id": ["nodeid", "NodeId"],
    },
}


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


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


def mcp_request(url: str, method: str, params: dict[str, Any] | None = None, timeout: int = 90) -> dict[str, Any]:
    payload = {"jsonrpc": "2.0", "id": int(time.time() * 1000) % 1_000_000, "method": method, "params": params or {}}
    request = urllib.request.Request(url, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Accept", "application/json, text/event-stream")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return parse_sse_json(response.read().decode("utf-8", errors="replace"))


def call_tool(url: str, name: str, arguments: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    response = mcp_request(url, "tools/call", {"name": name, "arguments": arguments})
    result = response.get("result") or {}
    if result.get("isError"):
        return [], {"is_error": True, "content": result.get("content") or []}
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
    return rows, None


def tool_schemas(url: str) -> dict[str, dict[str, Any]]:
    response = mcp_request(url, "tools/list")
    tools = (response.get("result") or {}).get("tools") or []
    return {tool.get("name"): tool for tool in tools if isinstance(tool, dict)}


def first_value(rows: list[dict[str, Any]], *keys: str) -> str:
    for row in rows:
        for key in keys:
            value = row.get(key)
            if value not in (None, ""):
                return str(value)
    return ""


def sample_context(data_pack: dict[str, Any]) -> dict[str, str]:
    products = [item for item in data_pack.get("products") or [] if isinstance(item, dict)]
    keywords = [item for item in data_pack.get("keywords") or [] if isinstance(item, dict)]
    tiktok_products = [item for item in data_pack.get("tiktok_products") or [] if isinstance(item, dict)]
    keyword = first_value(keywords, "keyword") or "smart lighting"
    asin = first_value(products, "asin", "ASIN")
    title = first_value(products, "title", "title_cn") or keyword
    tiktok_product_id = first_value(tiktok_products, "product_id", "ProductId")
    return {
        "keyword": keyword,
        "asin": asin,
        "product_title": title,
        "tiktok_product_id": tiktok_product_id,
        "site": "US",
    }


def sample_args(tool: str, ctx: dict[str, str]) -> dict[str, Any] | None:
    keyword = ctx["keyword"]
    asin = ctx["asin"]
    title = ctx["product_title"]
    product_id = ctx["tiktok_product_id"]
    if tool == "keyword_detail":
        return {"keyword": keyword, "keywordSupportSite": "US"}
    if tool == "keyword_extends":
        return {"keyword": keyword, "page": 1, "keywordSupportSite": "US"}
    if tool == "keyword_search_results":
        return {"keyword": keyword, "positionType": 1, "page": 1, "keywordSupportSite": "US"}
    if tool == "product_search":
        return {"searchName": keyword, "page": 1, "amzSite": "US"}
    if tool == "product_detail" and asin:
        return {"asin": asin, "amzSite": "US"}
    if tool == "product_trend" and asin:
        return {"asin": asin, "productTrendType": "SalesVolume", "amzSite": "US"}
    if tool == "product_reviews" and asin:
        return {"asin": asin, "reviewType": "Both", "amzSite": "US"}
    if tool == "product_variations" and asin:
        return {"asin": asin, "amzSite": "US"}
    if tool == "product_traffic_terms" and asin:
        return {"asin": asin, "page": 1, "amzSite": "US"}
    if tool == "competitor_product_keywords" and asin:
        return {"asin": asin, "page": 1, "keywordSupportSite": "US"}
    if tool == "category_name_search":
        return {"categoryName": keyword, "amzSite": "US"}
    if tool == "category_search_from_product_name":
        return {"productName": title, "page": 1, "amzSite": "US"}
    if tool == "tiktok_similar_product":
        return {"searchName": keyword, "page": 1, "site": "US"}
    if tool == "tiktok_product_detail" and product_id:
        return {"productId": product_id, "site": "US"}
    if tool == "tiktok_product_trend" and product_id:
        return {"productId": product_id, "site": "US"}
    if tool == "tiktok_product_video" and product_id:
        return {"productId": product_id, "page": 1, "site": "US"}
    if tool == "tiktok_product_video_author" and product_id:
        return {"productId": product_id, "site": "US"}
    if tool == "tiktok_author":
        return {"searchName": keyword, "page": 1, "site": "US"}
    if tool == "tiktok_category_name_search":
        return {"searchName": keyword, "site": "US"}
    if tool == "ali1688_similar_product":
        return {"searchName": "橱柜灯", "page": 1}
    return None


def documented_field_coverage(tool: str, fields: list[str]) -> dict[str, Any] | None:
    if tool != "ali1688_similar_product":
        return None
    observed = set(fields)
    if observed & URL_FIELD_ALIASES:
        observed.add("URL")
    present = sorted(field for field in ALI1688_DOCUMENTED_FIELDS if field in observed)
    missing = sorted(field for field in ALI1688_DOCUMENTED_FIELDS if field not in observed)
    return {
        "documented_field_count": len(ALI1688_DOCUMENTED_FIELDS),
        "observed_documented_field_count": len(present),
        "coverage_pct": round(len(present) / len(ALI1688_DOCUMENTED_FIELDS) * 100, 1),
        "present_fields": present,
        "missing_fields": missing,
        "passed": not missing,
    }


def normalization_field_coverage(tool: str, fields: list[str]) -> dict[str, Any] | None:
    requirements = NORMALIZATION_FIELD_REQUIREMENTS.get(tool)
    if not requirements:
        return None
    field_set = set(fields)
    present: list[str] = []
    missing: list[str] = []
    for dimension, aliases in requirements.items():
        if field_set & set(aliases):
            present.append(dimension)
        else:
            missing.append(dimension)
    total = len(requirements)
    return {
        "required_dimension_count": total,
        "observed_dimension_count": len(present),
        "coverage_pct": round(len(present) / total * 100, 1) if total else 0,
        "present_dimensions": sorted(present),
        "missing_dimensions": sorted(missing),
        "passed": not missing,
    }


def audit_tool(url: str, schemas: dict[str, dict[str, Any]], tool: str, args: dict[str, Any] | None) -> dict[str, Any]:
    schema = (schemas.get(tool) or {}).get("inputSchema") or {}
    if not args:
        return {"tool": tool, "available": tool in schemas, "called": False, "reason": "missing sample arguments", "input_schema": schema}
    try:
        rows, error = call_tool(url, tool, args)
    except Exception as exc:
        return {"tool": tool, "available": tool in schemas, "called": True, "args": args, "error": f"{type(exc).__name__}: {exc}", "input_schema": schema}
    fields = sorted({str(key) for row in rows for key in row.keys()})
    coverage = documented_field_coverage(tool, fields)
    normalization_coverage = normalization_field_coverage(tool, fields)
    return {
        "tool": tool,
        "available": tool in schemas,
        "called": True,
        "args": args,
        "row_count": len(rows),
        "fields": fields,
        "documented_field_coverage": coverage,
        "normalization_field_coverage": normalization_coverage,
        "empty_result_note": (
            "Tool call succeeded but returned zero rows for this sample context; try another ASIN/productId/category node before treating the tool as unavailable."
            if not rows else ""
        ),
        "sample_keys": sorted(rows[0].keys()) if rows else [],
        "error": error,
        "input_schema": schema,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit Sorftime MCP actual fields against tool schemas.")
    parser.add_argument("--dir", required=True, type=Path, help="Report directory.")
    parser.add_argument("--platform", choices=["all", "amazon", "tiktok", "1688"], default="all")
    args = parser.parse_args(argv)

    report_dir = args.dir
    data_pack = load_json(report_dir / "data" / "normalized" / "normalized_data_pack.json", {})
    if not data_pack:
        data_pack = load_json(report_dir / "data" / "data_pack.json", {})
    ctx = sample_context(data_pack)
    url = mcp_url()
    schemas = tool_schemas(url)
    selected: list[tuple[str, list[str]]] = []
    if args.platform in {"all", "amazon"}:
        selected.append(("amazon", AMAZON_TOOLS))
    if args.platform in {"all", "tiktok"}:
        selected.append(("tiktok", TIKTOK_TOOLS))
    if args.platform in {"all", "1688"}:
        selected.append(("1688", SUPPLY_TOOLS))

    out = report_dir / "data" / "normalized" / "sorftime_mcp_contract_audit.json"
    previous = load_json(out, {})
    if args.platform != "all" and isinstance(previous, dict) and previous.get("platforms"):
        result = previous
        result["audited_at"] = utc_now()
        result["report_dir"] = str(report_dir.resolve())
        result["sample_context"] = ctx
    else:
        result = {"audited_at": utc_now(), "report_dir": str(report_dir.resolve()), "sample_context": ctx, "platforms": {}}
    for platform, tools in selected:
        result["platforms"][platform] = [audit_tool(url, schemas, tool, sample_args(tool, ctx)) for tool in tools]

    write_json(out, result)
    compact = {
        platform: [
            {
                "tool": item["tool"],
                "called": item.get("called"),
                "row_count": item.get("row_count"),
                "fields": item.get("fields"),
                "documented_field_coverage": item.get("documented_field_coverage"),
                "normalization_field_coverage": item.get("normalization_field_coverage"),
                "empty_result_note": item.get("empty_result_note"),
                "error": item.get("error"),
            }
            for item in items
        ]
        for platform, items in result["platforms"].items()
    }
    print(json.dumps({"audit": str(out), "summary": compact}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
