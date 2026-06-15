#!/usr/bin/env python3
import unittest

from customer_copy import customer_product_position, customer_review_summary, review_theme_labels
from customer_safety import client_safe_view_payload, customer_safe_asset_text


class CustomerCopyTest(unittest.TestCase):
    def test_maps_raw_review_to_customer_safe_chinese_summary(self):
        review = {
            "rating": 2,
            "title": "privacy issue",
            "text": "This toy stopped working after two days and the privacy policy is confusing.",
        }

        summary = customer_review_summary(review)

        self.assertIn("隐私政策和数据使用说明不够清晰", summary)
        self.assertIn("短期使用后出现失效", summary)
        self.assertNotIn("privacy issue", summary)

    def test_positive_review_does_not_reuse_negative_summary(self):
        review = {
            "rating": 5,
            "summary_cn": "续航或充电体验没有达到预期",
            "title": "Great lights",
            "text": "Bright, easy to install, the motion sensor works well and charging lasts a long time.",
        }

        summary = customer_review_summary(review)

        self.assertNotIn("没有达到预期", summary)
        self.assertIn("正向反馈", summary)

    def test_positive_hunting_review_does_not_treat_lightweight_as_lighting(self):
        review = {
            "rating": 5,
            "title": "Nice blind",
            "text": "Nice blind. Good quality, size is nice, light weight easy to set up and carry.",
        }

        summary = customer_review_summary(review)

        self.assertIn("轻便和携带体验获得正向反馈", summary)
        self.assertIn("安装和上手体验获得正向反馈", summary)
        self.assertNotIn("亮度", summary)
        self.assertNotIn("灯效", summary)

    def test_uses_customer_visible_product_positioning(self):
        product = {"segment": "premium", "price": 89, "rating": 4.5, "review_count": 500}

        position = customer_product_position(product)

        self.assertIn("premium", position)
        self.assertIn("$89.00", position)
        self.assertIn("评论 500", position)

    def test_hunting_blind_context_ignores_lighting_positioning_pollution(self):
        product = {
            "title": "FUNHORUN Hunting Blind 270/360 Degree See Through Ground Blind",
            "title_cn": "透视弹出式地面盲棚",
            "segment_cn": "透视弹出式地面盲棚",
            "positioning_cn": "户外感应灯",
        }

        position = customer_product_position(product)

        self.assertEqual(position, "透视弹出式地面盲棚")
        self.assertNotIn("户外感应灯", position)

    def test_maps_theme_labels_to_chinese_copy(self):
        self.assertEqual(review_theme_labels({"themes": ["privacy"]}), ["隐私与信任"])
        self.assertEqual(review_theme_labels({}), ["其他体验问题"])

    def test_drops_battery_theme_when_review_has_no_power_context(self):
        review = {
            "rating": 5,
            "title": "Roomy blind",
            "text": "Quick and easy setup. The hunting blind is roomy and has good visibility.",
            "summary_cn": "续航或充电体验没有达到预期；正向反馈集中在开箱、陪伴和礼品场景",
            "themes": ["battery_charging"],
        }

        labels = review_theme_labels(review)

        self.assertNotIn("电池与充电", labels)
        self.assertEqual(labels, ["其他体验问题"])

    def test_keeps_battery_theme_when_review_mentions_power_context(self):
        review = {
            "rating": 2,
            "title": "Battery issue",
            "text": "Battery stopped charging after one night and the USB cable did not work.",
            "themes": ["battery_charging"],
        }

        labels = review_theme_labels(review)

        self.assertIn("电池与充电", labels)

    def test_customer_assets_translate_technical_no_rows_errors(self):
        raw = "Sorftime Amazon ASIN enrichment tools returned no rows for: product_detail, product_trend, product_variations after retrying 12 ASINs."

        safe = customer_safe_asset_text(raw)
        view = client_safe_view_payload(raw)

        for text in [safe, view]:
            self.assertIn("产品详情维度", text)
            self.assertIn("未返回可验证结果", text)
            self.assertNotIn("returned no rows", text)
            self.assertNotIn("product_detail", text)
            self.assertNotIn("ASIN", text)

    def test_customer_assets_localize_review_collection_sentiment_types(self):
        raw = "对核心 ASIN 补采 Positive/Neutral/Negative 评论，优先达到 80 条。"

        safe = customer_safe_asset_text(raw)
        view = client_safe_view_payload(raw)

        for text in [safe, view]:
            self.assertIn("正向/中性/负向评论", text)
            self.assertNotIn("Positive", text)
            self.assertNotIn("Neutral", text)
            self.assertNotIn("Negative", text)
            self.assertNotIn("ASIN", text)


if __name__ == "__main__":
    unittest.main()
