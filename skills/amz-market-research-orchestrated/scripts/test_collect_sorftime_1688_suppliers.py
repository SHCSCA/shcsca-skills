#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import collect_sorftime_1688_suppliers as collector


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class CollectSorftime1688SuppliersTest(unittest.TestCase):
    def test_infers_unique_1688_seed_terms_from_competitors_and_keywords(self):
        seeds = collector.infer_1688_seed_terms(
            {
                "research_object": {"value": "under cabinet lights"},
                "products": [
                    {"title": "Motion Sensor Under Cabinet Lights Rechargeable"},
                    {"title": "Wall Sconce Battery Operated Light"},
                ],
                "keywords": [{"keyword": "vanity light"}, {"keyword": "motion sensor light"}],
            },
            [],
            max_rounds=5,
        )

        self.assertIn("橱柜灯", seeds)
        self.assertIn("人体感应灯", seeds)
        self.assertIn("充电壁灯", seeds)
        self.assertIn("镜前灯", seeds)
        self.assertEqual(len(seeds), len(set(seeds)))
        self.assertLessEqual(len(seeds), 5)

    def test_supplier_entity_maps_1688_fields(self):
        row = {
            "Title": "LED人体感应橱柜灯",
            "StoreName": "中山照明厂",
            "Price": "14.5",
            "ProductId": "707",
            "SalesOf30d": "92113",
            "URL": "https://detail.1688.com/offer/707.html?spm=a",
        }

        entity = collector.supplier_entity(row, "sf_1688_seed_p001", "橱柜灯")

        self.assertEqual(entity["title"], "LED人体感应橱柜灯")
        self.assertEqual(entity["supplier_name"], "中山照明厂")
        self.assertEqual(entity["price_rmb"], 14.5)
        self.assertEqual(entity["product_id"], "707")
        self.assertEqual(entity["sales_30d"], 92113)
        self.assertEqual(entity["url"], "https://detail.1688.com/offer/707.html?spm=a")
        self.assertEqual(entity["seed_keyword"], "橱柜灯")

    def test_collect_retries_different_terms_until_50_valid_deduped_quotes(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(
                report_dir / "data" / "data_pack.json",
                {
                    "sources": [],
                    "products": [{"title": "Motion Sensor Under Cabinet Lights"}],
                    "keywords": [],
                    "suppliers": [],
                    "data_gaps": [],
                },
            )

            def fake_call_tool(_url, _name, args):
                keyword = args["searchName"]
                rows = [
                    {
                        "Title": f"{keyword} 工厂款 {idx}",
                        "StoreName": f"工厂 {keyword}-{idx}",
                        "Price": str(8 + idx),
                        "SalesOf30d": str(100 + idx),
                        "URL": f"https://detail.1688.com/offer/{keyword}-{idx}.html",
                    }
                    for idx in range(20)
                ]
                return {"result": {"content": [{"type": "text", "text": json.dumps(rows, ensure_ascii=False)}]}}

            with patch.object(collector, "mcp_url", return_value="http://sorftime.test"), patch.object(collector, "call_tool", side_effect=fake_call_tool):
                summary = collector.collect(report_dir, min_valid_quotes=50, seeds=[], max_rounds=5, max_pages=2, sleep_seconds=0)

            self.assertTrue(summary["collection_ready"])
            self.assertEqual(summary["valid_quotes_total"], 60)
            self.assertEqual(summary["calls"], 3)
            self.assertEqual(len(summary["rounds"]), 3)
            self.assertEqual(summary["rounds"][0]["seed"], "橱柜灯")
            self.assertGreater(summary["rounds"][0]["new_valid_quotes"], 0)
            data_pack = json.loads((report_dir / "data" / "data_pack.json").read_text(encoding="utf-8"))
            self.assertEqual(len(data_pack["suppliers"]), 60)

    def test_collect_records_blocking_diagnostic_after_all_rounds_under_50(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(report_dir / "data" / "data_pack.json", {"sources": [], "products": [], "keywords": [], "suppliers": [], "data_gaps": []})

            def fake_call_tool(_url, _name, _args):
                return {"result": {"content": [{"type": "text", "text": "[]"}]}}

            with patch.object(collector, "mcp_url", return_value="http://sorftime.test"), patch.object(collector, "call_tool", side_effect=fake_call_tool):
                summary = collector.collect(report_dir, min_valid_quotes=50, seeds=["不存在的灯"], max_rounds=5, max_pages=1, sleep_seconds=0)

            self.assertFalse(summary["collection_ready"])
            self.assertEqual(summary["valid_quotes_total"], 0)
            self.assertEqual(len(summary["rounds"]), 5)
            self.assertIn("不存在的灯", summary["attempted_seeds"])
            self.assertIn("1688有效报价不足50条", summary["failure_reason"])
            data_pack = json.loads((report_dir / "data" / "data_pack.json").read_text(encoding="utf-8"))
            self.assertEqual(data_pack["data_gaps"][0]["type"], "supplier_quote_depth")

    def test_collect_records_mcp_errors_instead_of_treating_them_as_empty_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(report_dir / "data" / "data_pack.json", {"sources": [], "products": [], "keywords": [], "suppliers": [], "data_gaps": []})

            def fake_call_tool(_url, _name, _args):
                return {"result": {"isError": True, "content": [{"type": "text", "text": "bad arguments"}]}}

            with patch.object(collector, "mcp_url", return_value="http://sorftime.test"), patch.object(collector, "call_tool", side_effect=fake_call_tool):
                summary = collector.collect(report_dir, min_valid_quotes=50, seeds=["橱柜灯"], max_rounds=1, max_pages=1, sleep_seconds=0)

            self.assertFalse(summary["collection_ready"])
            self.assertIn("bad arguments", summary["errors"][0]["error"])
            raw_files = list((report_dir / "data" / "raw").glob("sorftime_ali1688_similar_product_*.json"))
            self.assertEqual(len(raw_files), 1)


if __name__ == "__main__":
    unittest.main()
