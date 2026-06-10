#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from check_data_readiness import assess


SCRIPT = Path(__file__).with_name("check_data_readiness.py")


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def supplier_rows(count=50):
    return [
        {
            "title": f"1688 supplier product {idx}",
            "supplier_name": f"Supplier {idx}",
            "url": f"https://detail.1688.com/offer/{idx}.html",
            "price_rmb": 10 + idx,
            "sales_30d": 1000 + idx,
            "source_id": "src_001",
            "provider": "sorftime",
        }
        for idx in range(count)
    ]


def competitor_rows(count=30, segment_count=3):
    segments = ["橱柜感应灯", "RGB 灯带", "智能灯泡", "氛围灯", "户外感应灯"]
    return [
        {
            "asin": f"B0TEST{idx:05d}",
            "title": f"Smart lighting competitor {idx}",
            "brand": f"Brand {idx % 7}",
            "price": 12.99 + idx,
            "rating": 4.0 + (idx % 8) / 10,
            "review_count": 100 + idx,
            "estimated_monthly_sales": 500 + idx,
            "segment_cn": segments[idx % segment_count],
            "source_id": "src_001",
            "provider": "sorftime",
        }
        for idx in range(count)
    ]


def base_pack(**overrides):
    data = {
        "sources": [{"source_id": "src_001", "provider": "sorftime", "fetched_at": "2026-05-26T10:00:00Z", "confidence": "high"}],
        "products": competitor_rows(30),
        "keywords": [{"keyword": f"neck massager keyword {idx}", "source_id": "src_001", "provider": "sorftime"} for idx in range(1000)],
        "categories": [],
        "reviews": [],
        "tiktok_products": [],
        "tiktok_videos": [],
        "suppliers": supplier_rows(50),
        "web_documents": [],
        "data_gaps": [],
        "quality": {"overall_score": 0.8, "grade": "watch"},
    }
    data.update(overrides)
    return data


class DataReadinessTest(unittest.TestCase):
    def test_standard_pack_with_required_depth_is_ready_with_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "data" / "data_pack.json", base_pack())

            report = assess(root, "standard")

            self.assertTrue(report["acceptance_ready"])
            self.assertEqual(report["sample_class"], "acceptance_sample")
            self.assertEqual(report["counts"]["keywords"], 1000)
            self.assertFalse(report["blocking_gaps"])
            self.assertTrue(any(item["module"] == "review_sample_depth" for item in report["warnings"]))
            review_warning = next(item for item in report["warnings"] if item["module"] == "review_sample_depth")
            self.assertEqual(review_warning["recommended"], 80)

    def test_zero_depth_pack_blocks_standard_rendering(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(
                root / "data" / "data_pack.json",
                base_pack(
                    sources=[],
                    products=[],
                    keywords=[],
                    data_gaps=[{"module": "keyword_sample_depth", "reason": "no Sorftime rows"}],
                ),
            )

            report = assess(root, "standard")

            self.assertFalse(report["acceptance_ready"])
            self.assertEqual(report["sample_class"], "non_acceptance_sample")
            self.assertFalse(report["partial_report_ready"])
            modules = {item["module"] for item in report["blocking_gaps"]}
            self.assertIn("source_lineage", modules)
            self.assertIn("product_sample_depth", modules)
            self.assertIn("keyword_sample_depth", modules)
            self.assertTrue(any("collect_sorftime_keywords.py" in command for command in report["collector_commands"]))
            self.assertTrue(any("collect_sorftime_1688_suppliers.py" in command for command in report["collector_commands"]))

    def test_standard_pack_blocks_when_valid_1688_quotes_under_50(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "data" / "data_pack.json", base_pack(suppliers=supplier_rows(49)))

            report = assess(root, "standard")

            self.assertFalse(report["acceptance_ready"])
            self.assertEqual(report["sample_class"], "partial_acceptance_sample")
            self.assertTrue(report["partial_report_ready"])
            self.assertTrue(report["supply_conclusion_blocked"])
            supply_gap = next(item for item in report["blocking_gaps"] if item["module"] == "supplier_quote_depth")
            self.assertEqual(supply_gap["current"], 49)
            self.assertEqual(supply_gap["required"], 50)
            self.assertEqual(report["supplier_quote_gate"]["actual"], 49)
            self.assertFalse(report["supplier_quote_gate"]["passed"])

    def test_supplier_gate_counts_only_finished_goods_for_1688_depth(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            finished = supplier_rows(45)
            components = [
                {
                    "title": f"LED灯珠 发光二极管 光源配件 {idx}",
                    "supplier_name": f"灯珠配件厂 {idx}",
                    "url": f"https://detail.1688.com/offer/bead-{idx}.html",
                    "price_rmb": 0.05,
                    "sales_30d": 5000 + idx,
                    "seed_keyword": "RGB灯带",
                    "source_id": "src_001",
                    "provider": "sorftime",
                }
                for idx in range(30)
            ]
            write_json(root / "data" / "data_pack.json", base_pack(suppliers=finished + components))

            report = assess(root, "standard")

            self.assertFalse(report["acceptance_ready"])
            self.assertEqual(report["supplier_quote_gate"]["actual"], 45)
            self.assertFalse(report["supplier_quote_gate"]["passed"])
            self.assertIn("non_finished_filtered", report["supplier_quote_gate"])
            self.assertEqual(report["supplier_quote_gate"]["non_finished_filtered"], 30)

    def test_deep_pack_uses_higher_review_recommendation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "data" / "data_pack.json", base_pack())

            report = assess(root, "deep")

            review_warning = next(item for item in report["warnings"] if item["module"] == "review_sample_depth")
            self.assertEqual(review_warning["recommended"], 200)

    def test_cli_writes_report_and_returns_two_when_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "data" / "data_pack.json", base_pack(products=[], keywords=[]))

            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--dir", str(root), "--depth", "standard", "--write"],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            stdout = json.loads(result.stdout)
            readiness_path = Path(stdout["report_dir"]) / "data" / "normalized" / "data_readiness_report.json"
            self.assertTrue(readiness_path.exists())
            written = json.loads(readiness_path.read_text(encoding="utf-8"))
            self.assertFalse(written["acceptance_ready"])

    def test_standard_pack_blocks_when_competitor_pool_under_30(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "data" / "data_pack.json", base_pack(products=competitor_rows(29)))

            report = assess(root, "standard")

            self.assertFalse(report["acceptance_ready"])
            modules = {item["module"] for item in report["blocking_gaps"]}
            self.assertIn("competitor_pool_depth", modules)
            self.assertEqual(report["competitor_gate"]["minimum_total"], 30)
            self.assertEqual(report["competitor_gate"]["valid_total"], 29)

    def test_unclassified_products_do_not_count_as_valid_competitors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            products = competitor_rows(30)
            for product in products:
                product["segment_cn"] = "未分层"
            write_json(root / "data" / "data_pack.json", base_pack(products=products))

            report = assess(root, "standard")

            self.assertFalse(report["acceptance_ready"])
            self.assertEqual(report["competitor_gate"]["valid_total"], 0)
            modules = {item["module"] for item in report["blocking_gaps"]}
            self.assertIn("competitor_pool_depth", modules)

    def test_off_target_products_do_not_count_as_valid_competitors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            products = competitor_rows(29)
            products.extend(
                {
                    "asin": f"B0NOISE{idx:04d}",
                    "title": f"Premier Protein Shake Chocolate Pack {idx}",
                    "brand": "Premier Protein",
                    "price": 31.98,
                    "rating": 4.6,
                    "review_count": 58142,
                    "estimated_monthly_sales": 705547,
                    "segment_cn": "饮料",
                    "source_id": "src_001",
                    "provider": "sorftime",
                }
                for idx in range(10)
            )
            write_json(root / "data" / "data_pack.json", base_pack(products=products))

            report = assess(root, "standard")

            self.assertFalse(report["acceptance_ready"])
            self.assertEqual(report["competitor_gate"]["valid_total"], 29)
            modules = {item["module"] for item in report["blocking_gaps"]}
            self.assertIn("competitor_pool_depth", modules)

    def test_deep_pack_requires_60_competitors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / "data" / "data_pack.json", base_pack(products=competitor_rows(59)))

            report = assess(root, "deep")

            self.assertFalse(report["acceptance_ready"])
            self.assertEqual(report["competitor_gate"]["minimum_total"], 60)

    def test_broad_smart_lighting_requires_segment_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            products = competitor_rows(30, segment_count=1)
            write_json(root / "report_brief.json", {"research_object": {"value": "smart lighting"}})
            write_json(root / "data" / "data_pack.json", base_pack(products=products))

            report = assess(root, "standard")

            self.assertFalse(report["acceptance_ready"])
            modules = {item["module"] for item in report["blocking_gaps"]}
            self.assertIn("market_segment_split", modules)
            self.assertFalse(report["segment_gate"]["passed"])

    def test_supplier_gate_blocks_when_title_and_link_quality_is_low(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            suppliers = [
                {"product_id": f"id_{idx}", "supplier_name": f"Supplier {idx}", "price_rmb": 10 + idx}
                for idx in range(91)
            ]
            write_json(root / "data" / "data_pack.json", base_pack(suppliers=suppliers))

            report = assess(root, "standard")

            self.assertFalse(report["acceptance_ready"])
            supply_gap = next(item for item in report["blocking_gaps"] if item["module"] == "supplier_quote_quality")
            self.assertEqual(supply_gap["required"], 70)
            self.assertLess(report["supplier_quality_gate"]["title_coverage_pct"], 70)
            self.assertFalse(report["supplier_quality_gate"]["passed"])

    def test_supplier_gate_blocks_extreme_price_spread(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            suppliers = supplier_rows(50)
            suppliers[-1]["price_rmb"] = 5000
            write_json(root / "data" / "data_pack.json", base_pack(suppliers=suppliers))

            report = assess(root, "standard")

            self.assertFalse(report["acceptance_ready"])
            modules = {item["module"] for item in report["blocking_gaps"]}
            self.assertIn("supplier_quote_price_spread", modules)
            self.assertFalse(report["supplier_quality_gate"]["price_spread_passed"])

    def test_supplier_gate_accepts_clean_same_search_bucket_when_global_spread_is_mixed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            suppliers = []
            for idx in range(55):
                suppliers.append(
                    {
                        "title": f"橱柜感应灯供应端 {idx}",
                        "supplier_name": f"橱柜灯工厂 {idx}",
                        "url": f"https://detail.1688.com/offer/cabinet-{idx}.html",
                        "price_rmb": 12 + (idx % 8),
                        "sales_30d": 1000 + idx,
                        "seed_keyword": "橱柜感应灯",
                        "source_id": "src_001",
                        "provider": "sorftime",
                    }
                )
            for idx in range(10):
                suppliers.append(
                    {
                        "title": f"大型户外太阳能壁灯套装 {idx}",
                        "supplier_name": f"户外灯厂 {idx}",
                        "url": f"https://detail.1688.com/offer/outdoor-{idx}.html",
                        "price_rmb": 3000 + idx * 100,
                        "sales_30d": 100 + idx,
                        "seed_keyword": "户外灯",
                        "source_id": "src_001",
                        "provider": "sorftime",
                    }
                )
            write_json(root / "data" / "data_pack.json", base_pack(suppliers=suppliers))

            report = assess(root, "standard")

            self.assertTrue(report["acceptance_ready"])
            self.assertFalse(any(item["module"] == "supplier_quote_price_spread" for item in report["blocking_gaps"]))
            self.assertFalse(report["supplier_quality_gate"]["price_spread_passed"])
            self.assertTrue(report["supplier_quality_gate"]["same_search_bucket_gate"]["passed"])
            self.assertEqual(report["supplier_quality_gate"]["same_search_bucket_gate"]["bucket"], "橱柜感应灯")
            self.assertTrue(any(item["module"] == "supplier_quote_price_spread_global" for item in report["warnings"]))


if __name__ == "__main__":
    unittest.main()
