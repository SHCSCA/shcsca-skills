#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import collect_sorftime_product_enrichment as collector


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def mcp_rows(rows):
    return {"result": {"content": [{"type": "text", "text": json.dumps(rows, ensure_ascii=False)}]}}


class CollectSorftimeProductEnrichmentTest(unittest.TestCase):
    def test_empty_dimensions_replace_stale_gap_and_record_retry_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(
                report_dir / "data" / "data_pack.json",
                {
                    "sources": [],
                    "products": [
                        {"asin": "B0AAA", "title": "Under Cabinet Light", "brand": "A"},
                        {"asin": "B0BBB", "title": "Motion Sensor Light", "brand": "B"},
                    ],
                    "keywords": [],
                    "data_gaps": [
                        {"type": "amazon_product_enrichment_empty_dimensions", "module": "amazon_product_enrichment", "gap": "old gap"},
                        {"module": "amazon_product_enrichment", "gap": "older gap"},
                        {"module": "review_sample_depth", "reason": "keep this"},
                    ],
                },
            )

            def fake_call_tool(_url, name, _args):
                if name in {"product_detail", "product_trend", "product_variations"}:
                    return mcp_rows([])
                if name == "product_traffic_terms":
                    return mcp_rows([{"关键词": "under cabinet lights", "月搜索量": 1000}])
                if name == "competitor_product_keywords":
                    return mcp_rows([{"关键词": "motion sensor light", "关键词月搜索量": 800}])
                raise AssertionError(name)

            with patch.object(collector, "mcp_url", return_value="http://sorftime.test"), patch.object(collector, "call_tool", side_effect=fake_call_tool):
                summary = collector.collect(report_dir, max_products=2, max_pages=1, site="US", sleep_seconds=0)

            self.assertTrue(summary["collection_ready"])
            self.assertEqual(summary["empty_tools"], ["product_detail", "product_trend", "product_variations"])
            self.assertEqual(summary["stale_product_enrichment_gaps_removed"], 2)
            data_pack = json.loads((report_dir / "data" / "data_pack.json").read_text(encoding="utf-8"))
            enrichment_gaps = [
                gap
                for gap in data_pack["data_gaps"]
                if isinstance(gap, dict) and gap.get("module") == "amazon_product_enrichment"
            ]
            self.assertEqual(len(enrichment_gaps), 1)
            self.assertEqual(enrichment_gaps[0]["retry_evidence"]["attempted_asin_count"], 2)
            self.assertEqual(enrichment_gaps[0]["retry_evidence"]["asins_attempted"], ["B0AAA", "B0BBB"])
            self.assertIn("product_traffic_terms", enrichment_gaps[0]["retry_evidence"]["successful_dimensions"])
            self.assertTrue(any(isinstance(gap, dict) and gap.get("module") == "review_sample_depth" for gap in data_pack["data_gaps"]))

    def test_successful_dimensions_remove_stale_product_enrichment_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(
                report_dir / "data" / "data_pack.json",
                {
                    "sources": [],
                    "products": [{"asin": "B0AAA", "title": "Under Cabinet Light", "brand": "A"}],
                    "keywords": [],
                    "data_gaps": [
                        {"type": "amazon_product_enrichment_empty_dimensions", "module": "amazon_product_enrichment", "gap": "old gap"},
                    ],
                },
            )

            def fake_call_tool(_url, name, _args):
                if name == "product_detail":
                    return mcp_rows([{"标题": "Under Cabinet Light", "品牌": "A", "价格": 19.99}])
                if name == "product_trend":
                    return mcp_rows([{"产品销量趋势": ["2026-06-01=100"]}])
                if name == "product_variations":
                    return mcp_rows([{"asin": "B0AAA-RED"}])
                if name == "product_traffic_terms":
                    return mcp_rows([{"关键词": "under cabinet lights", "月搜索量": 1000}])
                if name == "competitor_product_keywords":
                    return mcp_rows([{"关键词": "motion sensor light", "关键词月搜索量": 800}])
                raise AssertionError(name)

            with patch.object(collector, "mcp_url", return_value="http://sorftime.test"), patch.object(collector, "call_tool", side_effect=fake_call_tool):
                summary = collector.collect(report_dir, max_products=1, max_pages=1, site="US", sleep_seconds=0)

            self.assertEqual(summary["empty_tools"], [])
            self.assertEqual(summary["stale_product_enrichment_gaps_removed"], 1)
            data_pack = json.loads((report_dir / "data" / "data_pack.json").read_text(encoding="utf-8"))
            self.assertFalse(
                any(isinstance(gap, dict) and gap.get("module") == "amazon_product_enrichment" for gap in data_pack["data_gaps"])
            )
            self.assertGreater(summary["product_patches"], 0)


if __name__ == "__main__":
    unittest.main()
