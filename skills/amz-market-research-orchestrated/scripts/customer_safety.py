#!/usr/bin/env python3
"""Customer-facing redaction and view-model safety helpers."""

from __future__ import annotations

import html
import re
from typing import Any


TECHNICAL_DISPLAY_KEYS = {"source_id", "source_ids", "provider", "tool", "raw_path", "path", "asin", "product_id", "video_id"}
CLIENT_VIEW_BLOCKED_KEYS = {"source_id", "source_ids", "used_source_ids", "provider", "tool", "raw_path", "path", "asin", "product_id", "video_id", "method_id"}
REVIEW_TEXT_KEYS = {"title", "text", "content", "body", "comment"}

CUSTOMER_LABEL_REPLACEMENTS = [
    ("used_source_ids", "证据强度"),
    ("source_ids", "证据强度"),
    ("source_id", "证据强度"),
    ("Product ID", "产品角色"),
    ("product_id", "产品角色"),
    ("raw_path", "内部审计记录"),
    ("provider", "证据覆盖"),
    ("tool", "分析方法"),
    ("method_id", "分析方法"),
    ("ASIN", "竞品样本"),
    ("asin", "竞品样本"),
    ("Sorftime", "市场样本"),
    ("Firecrawl", "公开网页补充"),
    ("sorftime", "市场样本"),
    ("firecrawl", "公开网页补充"),
    ("Data Pack", "分析底稿"),
    ("data/raw", "内部审计记录"),
    ("数据血缘", "证据说明"),
    ("来源", "证据覆盖"),
    ("Provider Coverage", "证据覆盖"),
    ("lineage", "审计链路"),
    ("英文标题", "页面表达归纳"),
    ("Review", "评论"),
    ("reviews", "评论"),
    ("products", "竞品"),
    ("sources", "样本记录"),
]


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", "" if value is None else str(value)).strip()


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def truncate(value: Any, limit: int = 120) -> str:
    text = clean(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def has_cjk(value: Any) -> bool:
    return re.search(r"[\u4e00-\u9fff]", str(value or "")) is not None


def collect_technical_values(value: Any, key: str | None = None) -> set[str]:
    values: set[str] = set()
    if isinstance(value, dict):
        for child_key, child_value in value.items():
            values.update(collect_technical_values(child_value, str(child_key)))
    elif isinstance(value, list):
        for item in value:
            values.update(collect_technical_values(item, key))
    elif key in TECHNICAL_DISPLAY_KEYS and value not in (None, ""):
        text = str(value).strip()
        if len(text) >= 3:
            values.add(text)
    return values


def raw_english_review_values(data_pack: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for review in data_pack.get("reviews") or []:
        if not isinstance(review, dict):
            continue
        for key in REVIEW_TEXT_KEYS:
            text = clean(review.get(key))
            if len(text) < 8 or has_cjk(text):
                continue
            words = re.findall(r"[A-Za-z][A-Za-z']+", text)
            if len(words) >= 2:
                values.add(text)
    return values


def review_redaction_needles(text: str) -> set[str]:
    needles = {text, esc(text)}
    for limit in (60, 70, 72, 80, 90, 100, 120, 180, 220):
        if len(text) > limit:
            shortened = truncate(text, limit)
            needles.add(shortened)
            needles.add(esc(shortened))
    return {needle for needle in needles if len(needle) >= 8}


def redact_customer_html(html_doc: str, data_pack: dict[str, Any]) -> str:
    for old, new in CUSTOMER_LABEL_REPLACEMENTS:
        html_doc = html_doc.replace(old, new)

    replacement_by_key = {
        "source_id": "高",
        "source_ids": "高",
        "provider": "样本覆盖",
        "tool": "分析方法",
        "raw_path": "内部审计记录",
        "path": "内部审计记录",
        "asin": "竞品样本",
        "product_id": "内容商品样本",
        "video_id": "内容样本",
    }

    def replace_value(value: Any, key: str | None = None) -> None:
        nonlocal html_doc
        if isinstance(value, dict):
            for child_key, child_value in value.items():
                replace_value(child_value, str(child_key))
        elif isinstance(value, list):
            for item in value:
                replace_value(item, key)
        elif key in TECHNICAL_DISPLAY_KEYS and value not in (None, ""):
            text = str(value).strip()
            if len(text) < 3:
                return
            replacement = replacement_by_key.get(key or "", "样本证据")
            for needle in {text, esc(text)}:
                html_doc = html_doc.replace(needle, replacement)

    replace_value(data_pack)
    for review_text in raw_english_review_values(data_pack):
        for needle in review_redaction_needles(review_text):
            html_doc = html_doc.replace(needle, "中文化评论摘要")
    html_doc = re.sub(r"\bB0[A-Z0-9]{8}\b", "竞品样本", html_doc)
    html_doc = re.sub(r"\bsrc[_-][\w\u4e00-\u9fff-]+\b", "高", html_doc, flags=re.IGNORECASE)
    html_doc = re.sub(r"\bsf[_-][\w\u4e00-\u9fff-]+\b", "高", html_doc, flags=re.IGNORECASE)
    html_doc = re.sub(r"\bdata/raw/[^\s<>'\"]+", "内部审计记录", html_doc, flags=re.IGNORECASE)
    html_doc = re.sub(r"[A-Za-z]:\\[^\s<>'\"]+", "内部审计记录", html_doc)
    html_doc = html_doc.replace("证据强度: 高", "证据强度：高")
    html_doc = html_doc.replace("证据强度： 高", "证据强度：高")
    return html_doc


def customer_safe_asset_text(value: Any) -> str:
    text = clean(value)
    for old, new in CUSTOMER_LABEL_REPLACEMENTS:
        text = text.replace(old, new)
    text = re.sub(r"\bB0[A-Z0-9]{8}\b", "竞品样本", text)
    text = re.sub(r"\bsrc[_-][\w\u4e00-\u9fff-]+\b", "高", text, flags=re.IGNORECASE)
    text = re.sub(r"\bsf[_-][\w\u4e00-\u9fff-]+\b", "高", text, flags=re.IGNORECASE)
    text = re.sub(r"\bdata/raw/[^\s<>'\"]+", "内部审计记录", text, flags=re.IGNORECASE)
    text = re.sub(r"[A-Za-z]:\\[^\s<>'\"]+", "内部审计记录", text)
    return text


def client_safe_view_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): client_safe_view_payload(child)
            for key, child in value.items()
            if str(key) not in CLIENT_VIEW_BLOCKED_KEYS
        }
    if isinstance(value, list):
        return [client_safe_view_payload(item) for item in value]
    if isinstance(value, str):
        text = clean(value)
        for old, new in CUSTOMER_LABEL_REPLACEMENTS:
            text = text.replace(old, new)
        text = re.sub(r"\bB0[A-Z0-9]{8}\b", "竞品样本", text)
        text = re.sub(r"\b(?:src|sf)[_-][\w\u4e00-\u9fff-]+\b", "内部证据", text, flags=re.IGNORECASE)
        text = re.sub(r"\bdata/raw/[^\s<>'\"]+", "内部审计记录", text, flags=re.IGNORECASE)
        text = re.sub(r"[A-Za-z]:\\[^\s<>'\"]+", "内部审计记录", text)
        return text
    return value
