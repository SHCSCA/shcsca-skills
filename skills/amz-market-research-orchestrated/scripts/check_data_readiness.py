#!/usr/bin/env python3
"""Preflight data-depth gate for amz-market-research-orchestrated runs."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


MIN_STANDARD_KEYWORDS = 1000
MIN_STANDARD_PRODUCTS = 1
MIN_QUICK_KEYWORDS = 1
MIN_QUICK_PRODUCTS = 1
RECOMMENDED_STANDARD_REVIEW_SAMPLE = 80
RECOMMENDED_DEEP_REVIEW_SAMPLE = 200
RECOMMENDED_WEB_DOCUMENTS = 1
RECOMMENDED_SUPPLIERS = 1
RECOMMENDED_TIKTOK_SIGNALS = 1


class ReadinessError(Exception):
    pass


def load_json(path: Path, default: Any | None = None) -> Any:
    if not path.exists():
        if default is not None:
            return default
        raise ReadinessError(f"Missing JSON file: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReadinessError(f"{path}: invalid JSON: {exc}") from exc


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def infer_depth(report_dir: Path, explicit_depth: str) -> str:
    if explicit_depth != "auto":
        return explicit_depth
    brief = load_json(report_dir / "report_brief.json", {})
    candidates = [
        brief.get("data_depth"),
        brief.get("depth"),
        (brief.get("data_scope") or {}).get("depth") if isinstance(brief.get("data_scope"), dict) else None,
        (brief.get("data_scope") or {}).get("level") if isinstance(brief.get("data_scope"), dict) else None,
    ]
    joined = " ".join(str(item or "").lower() for item in candidates)
    if any(token in joined for token in ("quick", "快速")):
        return "quick"
    if any(token in joined for token in ("deep", "深度")):
        return "deep"
    return "standard"


def load_data_pack(report_dir: Path) -> tuple[dict[str, Any], str]:
    normalized = report_dir / "data" / "normalized" / "normalized_data_pack.json"
    raw = report_dir / "data" / "data_pack.json"
    path = normalized if normalized.exists() else raw
    data_pack = load_json(path)
    if not isinstance(data_pack, dict):
        raise ReadinessError(f"{path}: data pack must be a JSON object")
    return data_pack, path.relative_to(report_dir).as_posix()


def count(data_pack: dict[str, Any], key: str) -> int:
    value = data_pack.get(key)
    return len(value) if isinstance(value, list) else 0


def gap(module: str, current: int, required: int, reason: str, next_step: str) -> dict[str, Any]:
    return {
        "module": module,
        "current": current,
        "required": required,
        "reason": reason,
        "next_step": next_step,
    }


def warning(module: str, current: int, recommended: int, impact: str, next_step: str) -> dict[str, Any]:
    return {
        "module": module,
        "current": current,
        "recommended": recommended,
        "impact": impact,
        "next_step": next_step,
    }


def collector_commands(report_dir: Path) -> list[str]:
    report = str(report_dir)
    return [
        f"python skills/amz-market-research-orchestrated/scripts/collect_sorftime_keywords.py --dir {report} --min-keywords 1200",
        f"python skills/amz-market-research-orchestrated/scripts/collect_sorftime_reviews.py --dir {report} --review-type Both",
        f"python skills/amz-market-research-orchestrated/scripts/normalize_data_pack.py --dir {report}",
    ]


def assess(report_dir: Path, depth: str = "auto") -> dict[str, Any]:
    report_dir = report_dir.resolve()
    data_pack, data_pack_path = load_data_pack(report_dir)
    resolved_depth = infer_depth(report_dir, depth)
    standard_like = resolved_depth in {"standard", "deep"}
    required_keywords = MIN_STANDARD_KEYWORDS if standard_like else MIN_QUICK_KEYWORDS
    required_products = MIN_STANDARD_PRODUCTS if standard_like else MIN_QUICK_PRODUCTS

    counts = {
        "sources": count(data_pack, "sources"),
        "products": count(data_pack, "products"),
        "keywords": count(data_pack, "keywords"),
        "categories": count(data_pack, "categories"),
        "reviews": count(data_pack, "reviews"),
        "tiktok_products": count(data_pack, "tiktok_products"),
        "tiktok_videos": count(data_pack, "tiktok_videos"),
        "suppliers": count(data_pack, "suppliers"),
        "web_documents": count(data_pack, "web_documents"),
        "data_gaps": count(data_pack, "data_gaps"),
    }

    blocking_gaps: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    if counts["sources"] < 1:
        blocking_gaps.append(
            gap(
                "source_lineage",
                counts["sources"],
                1,
                "Data Pack 没有任何可追溯 source，不能进入审计型报告生成。",
                "先采集 Sorftime/Firecrawl 原始证据并写入 data_pack.sources。",
            )
        )
    if counts["products"] < required_products:
        blocking_gaps.append(
            gap(
                "product_sample_depth",
                counts["products"],
                required_products,
                "缺少 Amazon 产品池/竞品样本，市场、生命周期和需求断层报告都会失真。",
                "先运行产品池/搜索结果/竞品详情采集，再归一化。",
            )
        )
    if counts["keywords"] < required_keywords:
        blocking_gaps.append(
            gap(
                "keyword_sample_depth",
                counts["keywords"],
                required_keywords,
                "关键词样本不足，标准版/深度版不能支撑需求结构和机会判断。",
                "运行 collect_sorftime_keywords.py 补到 1200 条采集目标，归一化后至少保留 1000 条。",
            )
        )

    recommended_reviews = RECOMMENDED_DEEP_REVIEW_SAMPLE if resolved_depth == "deep" else RECOMMENDED_STANDARD_REVIEW_SAMPLE
    if counts["reviews"] < recommended_reviews:
        warnings.append(
            warning(
                "review_sample_depth",
                counts["reviews"],
                recommended_reviews,
                "VOC 可以降级展示，但不能写精确比例或强结论。",
                "运行 collect_sorftime_reviews.py；标准版建议达到 80 条，深度版建议 200 条以上，或在 data_gaps 标注评论样本限制。",
            )
        )
    if counts["web_documents"] < RECOMMENDED_WEB_DOCUMENTS:
        warnings.append(
            warning(
                "web_evidence_depth",
                counts["web_documents"],
                RECOMMENDED_WEB_DOCUMENTS,
                "公开市场、法规或测评证据不足，外部交叉验证偏弱。",
                "用 Firecrawl 补行业/品牌/测评/合规网页；不可用时写 data_gaps。",
            )
        )
    if counts["suppliers"] < RECOMMENDED_SUPPLIERS:
        warnings.append(
            warning(
                "supplier_evidence_depth",
                counts["suppliers"],
                RECOMMENDED_SUPPLIERS,
                "供应链和成本红线只能做方向判断。",
                "补 1688/Alibaba 相似货源；不可用时保留供应链缺口。",
            )
        )
    if counts["tiktok_products"] + counts["tiktok_videos"] < RECOMMENDED_TIKTOK_SIGNALS:
        warnings.append(
            warning(
                "tiktok_signal_depth",
                counts["tiktok_products"] + counts["tiktok_videos"],
                RECOMMENDED_TIKTOK_SIGNALS,
                "内容场景和渠道热度只能降级为未知。",
                "补 TikTok 商品/视频/达人链路；不可用时保留 TikTok 缺口。",
            )
        )

    return {
        "report_dir": str(report_dir),
        "checked_at": utc_now(),
        "depth": resolved_depth,
        "data_pack": data_pack_path,
        "sample_class": "acceptance_sample" if not blocking_gaps else "non_acceptance_sample",
        "acceptance_ready": not blocking_gaps,
        "blocking_gaps": blocking_gaps,
        "warnings": warnings,
        "counts": counts,
        "collector_commands": collector_commands(report_dir),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check whether a report Data Pack is ready for standard/deep rendering.")
    parser.add_argument("--dir", required=True, type=Path, help="Report directory containing data/data_pack.json.")
    parser.add_argument("--depth", choices=["auto", "quick", "standard", "deep"], default="auto")
    parser.add_argument("--write", action="store_true", help="Write data/normalized/data_readiness_report.json.")
    args = parser.parse_args(argv)

    try:
        report = assess(args.dir, args.depth)
    except ReadinessError as exc:
        print(json.dumps({"acceptance_ready": False, "error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1

    if args.write:
        write_json(args.dir / "data" / "normalized" / "data_readiness_report.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["acceptance_ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
