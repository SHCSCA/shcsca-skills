#!/usr/bin/env python3
import unittest
from pathlib import Path
import tempfile

import audit_sorftime_mcp_contracts as audit


class AuditSorftimeMcpContractsTest(unittest.TestCase):
    def test_1688_documented_field_coverage_accepts_url_alias_and_sku_count(self):
        fields = [
            "Title",
            "Photo",
            "Url",
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
        ]

        coverage = audit.documented_field_coverage("ali1688_similar_product", fields)

        self.assertTrue(coverage["passed"])
        self.assertEqual(coverage["documented_field_count"], 16)
        self.assertEqual(coverage["coverage_pct"], 100.0)
        self.assertIn("URL", coverage["present_fields"])
        self.assertIn("SkuCount", coverage["present_fields"])
        self.assertEqual(coverage["missing_fields"], [])

    def test_amazon_product_search_normalization_coverage_uses_chinese_fields(self):
        fields = ["产品ASIN码", "标题", "品牌", "价格", "星级", "评论数", "月销量"]

        coverage = audit.normalization_field_coverage("product_search", fields)

        self.assertTrue(coverage["passed"])
        self.assertEqual(coverage["coverage_pct"], 100.0)
        self.assertIn("asin", coverage["present_dimensions"])

    def test_tiktok_video_normalization_coverage_detects_missing_author(self):
        fields = ["url", "标题", "播放量"]

        coverage = audit.normalization_field_coverage("tiktok_product_video", fields)

        self.assertFalse(coverage["passed"])
        self.assertIn("author", coverage["missing_dimensions"])

    def test_platform_audit_updates_existing_platforms_instead_of_overwriting(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "data" / "normalized" / "sorftime_mcp_contract_audit.json"
            audit.write_json(out, {"platforms": {"amazon": [{"tool": "product_search"}]}})

            previous = audit.load_json(out, {})
            previous["platforms"]["tiktok"] = [{"tool": "tiktok_similar_product"}]
            audit.write_json(out, previous)

            merged = audit.load_json(out, {})
            self.assertIn("amazon", merged["platforms"])
            self.assertIn("tiktok", merged["platforms"])


if __name__ == "__main__":
    unittest.main()
