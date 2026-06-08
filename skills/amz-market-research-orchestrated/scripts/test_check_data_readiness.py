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


def base_pack(**overrides):
    data = {
        "sources": [{"source_id": "src_001", "provider": "sorftime", "fetched_at": "2026-05-26T10:00:00Z", "confidence": "high"}],
        "products": [{"asin": "B0TEST1234", "title": "neck massager", "source_id": "src_001", "provider": "sorftime"}],
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
            self.assertEqual(report["sample_class"], "non_acceptance_sample")
            supply_gap = next(item for item in report["blocking_gaps"] if item["module"] == "supplier_quote_depth")
            self.assertEqual(supply_gap["current"], 49)
            self.assertEqual(supply_gap["required"], 50)
            self.assertEqual(report["supplier_quote_gate"]["actual"], 49)
            self.assertFalse(report["supplier_quote_gate"]["passed"])

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
            readiness_path = root / "data" / "normalized" / "data_readiness_report.json"
            self.assertTrue(readiness_path.exists())
            written = json.loads(readiness_path.read_text(encoding="utf-8"))
            self.assertFalse(written["acceptance_ready"])


if __name__ == "__main__":
    unittest.main()
