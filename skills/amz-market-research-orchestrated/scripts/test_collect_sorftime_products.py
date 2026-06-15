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

    def test_product_entity_preserves_documented_and_common_image_aliases(self):
        alias_rows = [
            ("ImageUrl", "https://m.media-amazon.com/images/I/image-url.jpg"),
            ("mainImage", "https://m.media-amazon.com/images/I/main-image.jpg"),
            ("thumbnail_url", "https://m.media-amazon.com/images/I/thumb.jpg"),
        ]

        for field, expected_url in alias_rows:
            with self.subTest(field=field):
                row = {
                    "ASIN": f"B0IMG{field.upper()[:5]}",
                    "Title": "Rechargeable Motion Sensor Under Cabinet Lights",
                    "Brand": "MCGOR",
                    "Price": "$17.97",
                    "Rating": "4.5",
                    "ReviewCount": "56202",
                    "MonthlySales": "64553",
                    field: expected_url,
                }

                entity = collector.product_entity(row, "sf_product_search_under_cabinet_p001", "under cabinet lights", "橱柜感应灯")

                self.assertEqual(entity["image_url"], expected_url)
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
                        "ImageUrl": f"https://m.media-amazon.com/images/I/{idx}.jpg" if idx % 2 == 0 else "",
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
            self.assertEqual(summary["image_url_coverage"]["with_image_url"], 15)
            self.assertEqual(summary["image_url_coverage"]["valid_competitors_total"], summary["valid_competitors_total"])
            self.assertAlmostEqual(summary["image_url_coverage"]["coverage"], 0.5)

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

    def test_collect_records_image_gap_when_valid_competitors_have_no_amazon_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(
                report_dir / "data" / "data_pack.json",
                {"sources": [], "products": [], "keywords": [], "data_gaps": [], "research_object": {"value": "hunting blind"}},
            )

            def fake_call_tool(_url, _tool, args):
                rows = [
                    {
                        "ASIN": f"B0BLIND{idx:04d}",
                        "Title": f"Pop Up Hunting Blind Ground Blind competitor {idx}",
                        "Brand": f"BlindBrand {idx}",
                        "Price": str(45 + idx),
                        "Rating": "4.5",
                        "ReviewCount": str(800 + idx),
                        "MonthlySales": str(300 + idx),
                    }
                    for idx in range(30)
                ]
                return {"result": {"content": [{"type": "text", "text": json.dumps(rows, ensure_ascii=False)}]}}

            with patch.object(collector, "mcp_url", return_value="http://sorftime.test"), patch.object(collector, "call_tool", side_effect=fake_call_tool):
                summary = collector.collect(report_dir, min_products=30, seeds=["hunting blind"], max_seeds=1, max_pages=1, site="US", sleep_seconds=0)

            self.assertTrue(summary["collection_ready"])
            self.assertEqual(summary["image_url_coverage"]["valid_competitors_total"], 30)
            self.assertEqual(summary["image_url_coverage"]["with_image_url"], 0)
            data_pack = json.loads((report_dir / "data" / "data_pack.json").read_text(encoding="utf-8"))
            image_gaps = [gap for gap in data_pack["data_gaps"] if gap.get("type") == "competitor_image_coverage"]
            self.assertEqual(len(image_gaps), 1)
            self.assertEqual(image_gaps[0]["module"], "amazon_competitor_images")
            self.assertIn("Amazon 竞品池当前 30 个有效竞品未返回可展示主图 URL", image_gaps[0]["gap"])
            self.assertIn("collect_sorftime_product_enrichment.py", image_gaps[0]["next_action"])
            self.assertIn("不能使用 1688 货源图冒充 Amazon 竞品图", image_gaps[0]["impact"])


if __name__ == "__main__":
    unittest.main()
