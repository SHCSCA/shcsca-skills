#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import collect_sorftime_products as collector


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class CollectSorftimeProductsTest(unittest.TestCase):
    def test_product_entity_maps_amazon_fields_and_segment(self):
        row = {
            "ASIN": "B0TEST1234",
            "Title": "Rechargeable Motion Sensor Under Cabinet Lights",
            "Brand": "MCGOR",
            "Price": "$17.97",
            "Rating": "4.5",
            "ReviewCount": "56202",
            "MonthlySales": "64553",
        }

        entity = collector.product_entity(row, "sf_product_search_under_cabinet_p001", "under cabinet lights", "橱柜感应灯")

        self.assertEqual(entity["asin"], "B0TEST1234")
        self.assertEqual(entity["brand"], "MCGOR")
        self.assertEqual(entity["price"], 17.97)
        self.assertEqual(entity["rating"], 4.5)
        self.assertEqual(entity["review_count"], 56202)
        self.assertEqual(entity["estimated_monthly_sales"], 64553)
        self.assertEqual(entity["segment_cn"], "橱柜感应灯")
        self.assertTrue(collector.is_valid_competitor(entity))

    def test_collect_uses_fallback_schema_when_first_product_search_shape_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(
                report_dir / "data" / "data_pack.json",
                {"sources": [], "products": [], "keywords": [], "data_gaps": [], "research_object": {"value": "smart lighting"}},
            )

            def fake_call_tool(_url, tool, args):
                if tool == "product_search" and "keyword" in args:
                    return {"result": {"isError": True, "content": [{"type": "text", "text": "bad keyword schema"}]}}
                rows = [
                    {
                        "ASIN": f"B0SMART{int(args.get('page', 1)):02d}{idx:04d}",
                        "Title": f"{args.get('searchName') or args.get('keyword')} under cabinet motion sensor light competitor {idx}",
                        "Brand": f"Brand {idx}",
                        "Price": str(10 + idx),
                        "Rating": "4.4",
                        "ReviewCount": str(500 + idx),
                        "MonthlySales": str(1000 + idx),
                    }
                    for idx in range(10)
                ]
                return {"result": {"content": [{"type": "text", "text": json.dumps(rows, ensure_ascii=False)}]}}

            with patch.object(collector, "mcp_url", return_value="http://sorftime.test"), patch.object(collector, "call_tool", side_effect=fake_call_tool):
                summary = collector.collect(report_dir, min_products=30, seeds=[], max_seeds=4, max_pages=3, site="US", sleep_seconds=0)

            self.assertTrue(summary["collection_ready"])
            self.assertGreaterEqual(summary["valid_competitors_total"], 30)
            self.assertTrue(any(error["tool"] == "product_search" and "keyword" in error["args"] for error in summary["errors"]))
            data_pack = json.loads((report_dir / "data" / "data_pack.json").read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(data_pack["products"]), 30)
            self.assertTrue(all(product.get("asin") for product in data_pack["products"]))

    def test_collect_records_gap_when_competitors_remain_under_minimum(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(report_dir / "data" / "data_pack.json", {"sources": [], "products": [], "keywords": [], "data_gaps": [], "research_object": {"value": "desk lamp"}})

            def fake_call_tool(_url, _tool, _args):
                return {"result": {"content": [{"type": "text", "text": "[]"}]}}

            with patch.object(collector, "mcp_url", return_value="http://sorftime.test"), patch.object(collector, "call_tool", side_effect=fake_call_tool):
                summary = collector.collect(report_dir, min_products=30, seeds=[], max_seeds=1, max_pages=1, site="US", sleep_seconds=0)

            self.assertFalse(summary["collection_ready"])
            self.assertIn("Amazon有效竞品不足", summary["failure_reason"])
            data_pack = json.loads((report_dir / "data" / "data_pack.json").read_text(encoding="utf-8"))
            self.assertEqual(data_pack["data_gaps"][0]["type"], "competitor_pool_depth")


if __name__ == "__main__":
    unittest.main()
