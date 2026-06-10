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
            "Price": "1450",
            "WholesalePriceRange": [{"Price": "14.5", "PurchaseQuantity": "≥2"}],
            "ProductId": "707",
            "SalesOf30d": "92113",
            "Url": "https://detail.1688.com/offer/707.html?spm=a",
            "SkuCount": 5,
            "RepurchaseRate": 15.5,
        }

        entity = collector.supplier_entity(row, "sf_1688_seed_p001", "橱柜灯")

        self.assertEqual(entity["title"], "LED人体感应橱柜灯")
        self.assertEqual(entity["supplier_name"], "中山照明厂")
        self.assertEqual(entity["price_rmb"], 14.5)
        self.assertEqual(entity["listed_price_raw"], 1450)
        self.assertEqual(entity["product_id"], "707")
        self.assertEqual(entity["sales_30d"], 92113)
        self.assertEqual(entity["url"], "https://detail.1688.com/offer/707.html?spm=a")
        self.assertEqual(entity["sku_count"], 5)
        self.assertEqual(entity["repurchase_rate"], 15.5)
        self.assertEqual(entity["seed_keyword"], "橱柜灯")

    def test_current_mcp_1688_shape_counts_product_id_store_and_price_as_valid_quote(self):
        row = {
            "ProductId": "678442451719",
            "Photo": "https://cbu01.alicdn.com/img/ibank/example.jpg",
            "StoreName": "中山市帝曼森灯饰有限公司",
            "Price": 500.0,
            "ReviewCount": 271,
            "Star": 0.0,
        }

        entity = collector.supplier_entity(row, "sf_1688_seed_p001", "智能照明")

        self.assertIsNone(entity["title"])
        self.assertEqual(entity["product_id"], "678442451719")
        self.assertEqual(entity["photo_url"], "https://cbu01.alicdn.com/img/ibank/example.jpg")
        self.assertEqual(entity["supplier_name"], "中山市帝曼森灯饰有限公司")
        self.assertEqual(entity["price_rmb"], 500.0)
        self.assertEqual(entity["review_count"], 271)
        self.assertTrue(collector.is_valid_quote(entity))

    def test_dedupe_supplier_records_merges_later_title_and_url_by_product_id(self):
        records = collector.dedupe_supplier_records(
            [
                {"product_id": "778", "supplier_name": "中山工厂", "price_rmb": 9.9, "source_id": "old"},
                {
                    "product_id": "778",
                    "supplier_name": "中山工厂",
                    "price_rmb": 9.9,
                    "title": "LED 橱柜感应灯",
                    "url": "https://detail.1688.com/offer/778.html",
                    "source_id": "new",
                },
            ]
        )

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["title"], "LED 橱柜感应灯")
        self.assertEqual(records[0]["url"], "https://detail.1688.com/offer/778.html")
        self.assertEqual(records[0]["source_id"], "old")
        self.assertIn("old", records[0]["source_ids"])
        self.assertIn("new", records[0]["source_ids"])

    def test_remove_legacy_incomplete_1688_quotes_drops_old_product_id_only_rows(self):
        kept, removed = collector.remove_legacy_incomplete_1688_quotes(
            [
                {"provider": "sorftime", "source_id": "sf_1688_old", "product_id": "1", "supplier_name": "旧店", "price_rmb": 500},
                {
                    "provider": "sorftime",
                    "source_id": "sf_1688_new",
                    "product_id": "1",
                    "title": "LED 橱柜灯",
                    "url": "https://detail.1688.com/offer/1.html",
                    "supplier_name": "新店",
                    "price_rmb": 5,
                },
            ]
        )

        self.assertEqual(removed, 1)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["title"], "LED 橱柜灯")

    def test_remove_legacy_unpriced_1688_quotes_drops_rows_without_wholesale_range(self):
        kept, removed = collector.remove_legacy_unpriced_1688_quotes(
            [
                {"provider": "sorftime", "source_id": "sf_1688_old", "product_id": "1", "title": "旧灯", "url": "https://detail.1688.com/offer/1.html", "price_rmb": 131},
                {
                    "provider": "sorftime",
                    "source_id": "sf_1688_new",
                    "product_id": "2",
                    "title": "新灯",
                    "url": "https://detail.1688.com/offer/2.html",
                    "price_rmb": 1.31,
                    "wholesale_price_range": [{"Price": "1.31"}],
                },
            ]
        )

        self.assertEqual(removed, 1)
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["price_rmb"], 1.31)

    def test_recompute_prices_from_wholesale_range_updates_old_scaled_price(self):
        suppliers = [{"price_rmb": 125600, "wholesale_price_range": [{"Price": "266", "PurchaseQuantity": "≥1"}]}]

        updated = collector.recompute_1688_prices_from_wholesale_range(suppliers)

        self.assertEqual(updated, 1)
        self.assertEqual(suppliers[0]["price_rmb"], 266.0)

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
                self.assertIn("page", args)
                offset = (args["page"] - 1) * 20
                rows = [
                    {
                        "Title": f"{keyword} 工厂款 {offset + idx}",
                        "StoreName": f"工厂 {keyword}-{offset + idx}",
                        "Price": str(8 + idx),
                        "SalesOf30d": str(100 + idx),
                        "URL": f"https://detail.1688.com/offer/{keyword}-{offset + idx}.html",
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
            self.assertEqual(summary["rounds"][0]["page"], 1)
            self.assertEqual(summary["rounds"][1]["page"], 2)
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

    def test_summary_records_missing_documented_title_and_url_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(report_dir / "data" / "data_pack.json", {"sources": [], "products": [], "keywords": [], "suppliers": [], "data_gaps": []})

            def fake_call_tool(_url, _name, args):
                self.assertEqual(args, {"searchName": "橱柜灯", "page": 1})
                rows = [
                    {
                        "ProductId": f"pid-{idx}",
                        "StoreName": f"工厂 {idx}",
                        "Price": str(8 + idx),
                        "Photo": "https://cbu01.alicdn.com/example.jpg",
                    }
                    for idx in range(50)
                ]
                return {"result": {"content": [{"type": "text", "text": json.dumps(rows, ensure_ascii=False)}]}}

            with patch.object(collector, "mcp_url", return_value="http://sorftime.test"), patch.object(collector, "call_tool", side_effect=fake_call_tool):
                summary = collector.collect(report_dir, min_valid_quotes=50, seeds=["橱柜灯"], max_rounds=1, max_pages=1, sleep_seconds=0)

            self.assertFalse(summary["collection_ready"])
            self.assertEqual(summary["valid_quotes_total"], 50)
            self.assertIn("Title", summary["missing_documented_required_fields"])
            self.assertIn("URL", summary["missing_documented_required_fields"])
            self.assertIn("MCP实际响应缺少官方文档关键字段", summary["failure_reason"])

    def test_missing_required_fields_accepts_url_alias(self):
        rows = [{"Title": "LED 橱柜灯", "Url": "https://detail.1688.com/offer/1.html"}]

        self.assertEqual(collector.missing_required_fields(rows), [])

    def test_documented_1688_field_coverage_includes_sku_count_and_url_alias(self):
        observed = {
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
        }

        coverage = collector.documented_field_coverage(observed)

        self.assertIn("SkuCount", collector.DOCUMENTED_RESPONSE_FIELDS)
        self.assertEqual(coverage["documented_field_count"], 16)
        self.assertIn("URL", coverage["present_fields"])
        self.assertIn("SkuCount", coverage["present_fields"])
        self.assertEqual(coverage["missing_fields"], [])

    def test_same_search_bucket_gate_allows_coherent_bucket_when_global_prices_are_mixed(self):
        stable_bucket = [
            {
                "title": f"无线磁吸感应灯 成品 {idx}",
                "supplier_name": f"中山供应商 {idx}",
                "url": f"https://detail.1688.com/offer/stable-{idx}.html",
                "price_rmb": 18 + idx % 6,
                "seed_keyword": "无线磁吸感应灯",
            }
            for idx in range(55)
        ]
        outlier_bucket = [
            {
                "title": f"大型工程灯 {idx}",
                "supplier_name": f"工程灯供应商 {idx}",
                "url": f"https://detail.1688.com/offer/outlier-{idx}.html",
                "price_rmb": 860 + idx,
                "seed_keyword": "工程灯",
            }
            for idx in range(4)
        ]

        global_quality = collector.quote_quality(stable_bucket + outlier_bucket, 70, 20, 5)
        same_bucket = collector.same_search_bucket_gate(stable_bucket + outlier_bucket, 50, 70, 20, 5)

        self.assertFalse(global_quality["price_spread_passed"])
        self.assertTrue(same_bucket["passed"])
        self.assertEqual(same_bucket["bucket"], "无线磁吸感应灯")
        self.assertGreaterEqual(same_bucket["valid_quotes"], 50)

    def test_existing_supplier_response_fields_backfill_observed_mcp_fields(self):
        suppliers = [
            {"response_fields": ["Title", "Url", "Price", "StoreName", "SkuCount"]},
            {"response_fields": ["WholesalePriceRange", "SalesOf30d"]},
        ]

        fields = collector.existing_supplier_response_fields(suppliers)
        coverage = collector.documented_field_coverage(fields)

        self.assertIn("Title", fields)
        self.assertIn("Url", fields)
        self.assertIn("URL", coverage["present_fields"])
        self.assertIn("SkuCount", coverage["present_fields"])

    def test_collect_removes_stale_supplier_gaps_when_collection_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            suppliers = [
                {
                    "title": f"无线磁吸感应灯 成品 {idx}",
                    "supplier_name": f"中山供应商 {idx}",
                    "url": f"https://detail.1688.com/offer/ready-{idx}.html",
                    "price_rmb": 18 + idx % 5,
                    "seed_keyword": "无线磁吸感应灯",
                }
                for idx in range(55)
            ]
            write_json(
                report_dir / "data" / "data_pack.json",
                {
                    "sources": [],
                    "products": [],
                    "keywords": [],
                    "suppliers": suppliers,
                    "data_gaps": [
                        {
                            "type": "supplier_quote_quality",
                            "module": "supplier_quote_quality",
                            "gap": "1688报价价格分布异常：旧结果。",
                        },
                        {"module": "review_sample_depth", "reason": "评论样本不足"},
                    ],
                },
            )

            summary = collector.collect(report_dir, min_valid_quotes=50, seeds=[], max_rounds=0, max_pages=1, sleep_seconds=0)

            self.assertTrue(summary["collection_ready"])
            self.assertEqual(summary["stale_supplier_gaps_removed"], 1)
            data_pack = json.loads((report_dir / "data" / "data_pack.json").read_text(encoding="utf-8"))
            modules = [gap.get("module") for gap in data_pack["data_gaps"] if isinstance(gap, dict)]
            self.assertNotIn("supplier_quote_quality", modules)
            self.assertIn("review_sample_depth", modules)

    def test_collect_replaces_stale_supplier_gaps_with_current_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(
                report_dir / "data" / "data_pack.json",
                {
                    "sources": [],
                    "products": [],
                    "keywords": [],
                    "suppliers": [],
                    "data_gaps": [
                        {"module": "supplier_quote_quality", "reason": "1688报价价格分布异常：旧结果。"},
                        {"type": "supplier_quote_depth", "gap": "1688有效报价不足50条：旧结果。"},
                        "1688报价价格分布异常：旧文本缺口。",
                        {"module": "keyword_sample_depth", "reason": "关键词样本不足"},
                    ],
                },
            )

            def fake_call_tool(_url, _name, _args):
                return {"result": {"content": [{"type": "text", "text": "[]"}]}}

            with patch.object(collector, "mcp_url", return_value="http://sorftime.test"), patch.object(collector, "call_tool", side_effect=fake_call_tool):
                summary = collector.collect(report_dir, min_valid_quotes=50, seeds=["不存在的灯"], max_rounds=1, max_pages=1, sleep_seconds=0)

            self.assertFalse(summary["collection_ready"])
            self.assertEqual(summary["stale_supplier_gaps_removed"], 3)
            data_pack = json.loads((report_dir / "data" / "data_pack.json").read_text(encoding="utf-8"))
            supplier_gaps = [
                gap
                for gap in data_pack["data_gaps"]
                if isinstance(gap, dict) and (gap.get("type") or gap.get("module") or "").startswith("supplier_quote")
            ]
            self.assertEqual(len(supplier_gaps), 1)
            self.assertEqual(supplier_gaps[0]["type"], "supplier_quote_depth")
            self.assertTrue(any(isinstance(gap, dict) and gap.get("module") == "keyword_sample_depth" for gap in data_pack["data_gaps"]))


if __name__ == "__main__":
    unittest.main()
