#!/usr/bin/env python3
import unittest

from customer_copy import customer_product_position, customer_review_summary, review_theme_labels


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

    def test_uses_customer_visible_product_positioning(self):
        product = {"segment": "premium", "price": 89, "rating": 4.5, "review_count": 500}

        position = customer_product_position(product)

        self.assertIn("premium", position)
        self.assertIn("$89.00", position)
        self.assertIn("评论 500", position)

    def test_maps_theme_labels_to_chinese_copy(self):
        self.assertEqual(review_theme_labels({"themes": ["privacy"]}), ["隐私与信任"])
        self.assertEqual(review_theme_labels({}), ["其他体验问题"])


if __name__ == "__main__":
    unittest.main()
