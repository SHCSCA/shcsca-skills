#!/usr/bin/env python3
import unittest

from customer_safety import client_safe_view_payload, customer_safe_asset_text, redact_customer_html


class CustomerSafetyTest(unittest.TestCase):
    def test_redact_customer_html_removes_technical_values_and_raw_review(self):
        data_pack = {
            "sources": [
                {
                    "source_id": "src_001",
                    "provider": "sorftime",
                    "tool": "product_search",
                    "raw_path": "data/raw/sorftime.json",
                }
            ],
            "products": [{"asin": "B0TEST1234", "product_id": "internal_product_1", "source_id": "src_001"}],
            "reviews": [
                {
                    "title": "privacy issue",
                    "text": "This toy stopped working after two days and the privacy policy is confusing.",
                    "source_id": "src_001",
                }
            ],
        }
        html = """
        <p>source_id src_001 provider sorftime tool product_search raw_path data/raw/sorftime.json</p>
        <p>ASIN B0TEST1234 product_id internal_product_1</p>
        <p>This toy stopped working after two days and the privacy policy is confusing.</p>
        <p>sf_分析方法_under_cabinet_lighting_p002</p>
        """

        redacted = redact_customer_html(html, data_pack)

        for leaked in ["source_id", "src_001", "provider", "sorftime", "raw_path", "data/raw", "B0TEST1234", "internal_product_1", "sf_分析方法"]:
            self.assertNotIn(leaked, redacted)
        self.assertIn("中文化评论摘要", redacted)
        self.assertIn("竞品记录", redacted)

    def test_customer_safe_asset_text_redacts_internal_ids_without_destroying_normal_strength_words(self):
        text = "ASIN B0TEST1234 来源 src_评论_under 证据强度 高，data/raw/file.json"

        safe = customer_safe_asset_text(text)

        self.assertNotIn("ASIN", safe)
        self.assertNotIn("B0TEST1234", safe)
        self.assertNotIn("src_评论_under", safe)
        self.assertNotIn("data/raw", safe)
        self.assertIn("证据强度 高", safe)

    def test_redact_customer_html_preserves_benchmark_scoped_asin(self):
        data_pack = {"products": [{"asin": "B0TEST1234", "source_id": "src_001"}], "reviews": []}
        html = """
        <section id="benchmark-sniper">
          <span class="asin-token" data-allow-asin="benchmark-sniper">B0TEST1234</span>
        </section>
        <p>其他区域 B0TEST1234 仍要脱敏。</p>
        """

        redacted = redact_customer_html(html, data_pack)

        self.assertIn('data-allow-asin="benchmark-sniper">B0TEST1234</span>', redacted)
        self.assertIn("其他区域 竞品记录 仍要脱敏", redacted)

    def test_redact_customer_html_preserves_scoped_english_review_excerpt(self):
        data_pack = {
            "reviews": [
                {
                    "text": "This toy stopped working after two days and the privacy policy is confusing.",
                    "source_id": "src_001",
                }
            ]
        }
        html = """
        <p><span class="review-excerpt-en" data-allow-english-review="short">This toy stopped working after two days.</span></p>
        <p>This toy stopped working after two days and the privacy policy is confusing.</p>
        """

        redacted = redact_customer_html(html, data_pack)

        self.assertIn('data-allow-english-review="short">This toy stopped working after two days.</span>', redacted)
        self.assertIn("中文化评论摘要", redacted)

    def test_client_safe_view_payload_drops_blocked_keys_recursively(self):
        payload = {
            "source_id": "src_001",
            "evidence_strength": "高",
            "nested": [
                {
                    "asin": "B0TEST1234",
                    "summary": "来自 sf_评论_under 的高相关评论",
                    "raw_path": "data/raw/a.json",
                }
            ],
        }

        safe = client_safe_view_payload(payload)

        self.assertNotIn("source_id", safe)
        self.assertEqual(safe["evidence_strength"], "高")
        self.assertNotIn("asin", safe["nested"][0])
        self.assertNotIn("raw_path", safe["nested"][0])
        self.assertNotIn("sf_评论_under", safe["nested"][0]["summary"])
        self.assertIn("高相关评论", safe["nested"][0]["summary"])


if __name__ == "__main__":
    unittest.main()
