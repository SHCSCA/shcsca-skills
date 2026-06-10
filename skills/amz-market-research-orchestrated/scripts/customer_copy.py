#!/usr/bin/env python3
"""Customer-facing copy helpers for report section rendering."""

from __future__ import annotations

from typing import Any

from html_components import as_float, clean, first, has_cjk, money, num, product_price, product_reviews, product_sales, truncate
from normalize_data_pack import THEME_CN


def review_theme_labels(review: dict[str, Any]) -> list[str]:
    themes = review.get("themes_cn") or review.get("themes") or []
    if isinstance(themes, str):
        themes = [themes]
    labels = []
    for theme in themes:
        text = str(theme)
        labels.append(THEME_CN.get(text.casefold(), text).replace("/", "与"))
    return labels or ["其他体验问题"]


def customer_review_summary(review: dict[str, Any], limit: int = 180) -> str:
    rating = as_float(review.get("rating"), 0)
    raw_text = clean(" ".join(str(review.get(key) or "") for key in ("title", "text", "content", "body", "comment"))).casefold()
    negative_summary_phrases = ["没有达到预期", "需要加强", "出现失效", "信任下降", "不够清晰", "难以使用"]
    for key in ("summary_cn", "text_cn", "quote_cn", "review_cn"):
        value = clean(review.get(key))
        if value:
            if rating >= 4 and any(phrase in value for phrase in negative_summary_phrases):
                break
            return truncate(value, limit)

    raw = clean(first(review.get("text"), review.get("content"), review.get("body"), review.get("comment"), default=""))
    if has_cjk(raw):
        return truncate(raw, limit)

    text = raw_text
    phrases: list[str] = []
    if rating >= 4:
        if any(term in text for term in ["bright", "brightness", "light", "color", "rgb"]):
            phrases.append("亮度和灯效获得正向反馈")
        if any(term in text for term in ["easy", "install", "setup", "stick", "adhesive"]):
            phrases.append("安装和上手体验获得正向反馈")
        if any(term in text for term in ["motion", "sensor", "detect"]):
            phrases.append("感应触发体验获得正向反馈")
        if any(term in text for term in ["battery", "charge", "charging", "last", "long time"]):
            phrases.append("续航和充电便利性获得正向反馈")
        if any(term in text for term in ["love", "great", "works well", "perfect", "recommend"]):
            phrases.append("整体使用满意度形成正向反馈")
        return "；".join(dict.fromkeys(phrases or ["用户正向反馈集中在功能效果、安装便利和场景适配"]))[:limit]

    if any(term in text for term in ["stopped working", "stop working", "not work", "doesn't work", "broken", "defective", "failed"]):
        phrases.append("短期使用后出现失效")
    if any(term in text for term in ["two days", "2 days", "after a day", "after one day", "within days"]):
        phrases.append("用户对耐用性和稳定性信任下降")
    if any(term in text for term in ["privacy", "policy", "data", "record", "recording", "permission"]):
        phrases.append("隐私政策和数据使用说明不够清晰")
    if any(term in text for term in ["confusing", "hard to use", "setup", "connect", "bluetooth", "wifi", "app"]):
        phrases.append("上手配置和使用路径需要更清楚")
    if any(term in text for term in ["battery", "charge", "charging", "recharge", "usb"]):
        phrases.append("续航或充电体验没有达到预期")
    if any(term in text for term in ["cheap", "quality", "material", "durable", "fall apart"]):
        phrases.append("材质做工和耐用性需要加强")
    if any(term in text for term in ["refund", "return", "warranty", "support", "service"]):
        phrases.append("售后承诺需要前置说明")

    if not phrases:
        phrases.append("负面反馈集中在体验未达预期" if rating and rating <= 3 else "用户反馈需要继续归类后再转成需求动作")
    unique = []
    for phrase in phrases:
        if phrase not in unique:
            unique.append(phrase)
    return "；".join(unique[:3])


def customer_review_title(review: dict[str, Any]) -> str:
    title_cn = clean(review.get("title_cn"))
    if title_cn:
        return truncate(title_cn, 60)
    return "、".join(review_theme_labels(review)[:2])


def review_sentiment_label(review: dict[str, Any]) -> str:
    rating = as_float(review.get("rating"), 0)
    if rating and rating <= 3:
        return "负面触发"
    if rating and rating >= 4:
        return "正向动机"
    return "待判定"


def customer_product_position(product: dict[str, Any]) -> str:
    for key in ("positioning_cn", "title_cn"):
        value = clean(product.get(key))
        if value and has_cjk(value):
            return truncate(value, 90)
    segment = first(product.get("segment_cn"), product.get("segment"), default="核心竞品")
    price = money(product_price(product))
    rating = first(product.get("rating"), default="-")
    reviews = num(product_reviews(product))
    return f"{segment} · {price} 价格带 · 评分 {rating} · 评论 {reviews}，用于判断竞品定位和页面表达"


def customer_product_message(product: dict[str, Any]) -> str:
    position = customer_product_position(product)
    sales = num(product_sales(product))
    return f"{position}；估算月销量 {sales}，重点观察其价格锚点、评价门槛和差异化承诺。"
