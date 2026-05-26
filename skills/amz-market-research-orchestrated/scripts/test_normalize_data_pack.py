#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("normalize_data_pack.py")


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class NormalizeDataPackTest(unittest.TestCase):
    def run_normalizer(self, report_dir):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--dir", str(report_dir)],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_dedupes_products_and_merges_source_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(
                report_dir / "data" / "data_pack.json",
                {
                    "sources": [
                        {"source_id": "src_search", "provider": "sorftime", "tool": "product_search", "fetched_at": "now", "confidence": 0.8},
                        {"source_id": "src_detail", "provider": "sorftime", "tool": "product_detail", "fetched_at": "now", "confidence": 0.9},
                    ],
                    "products": [
                        {"asin": "B0ABC", "title": "Rechargeable Wall Sconce Set of 2", "price": 39.99, "source_id": "src_search", "provider": "sorftime"},
                        {"asin": "B0ABC", "title": "Rechargeable Wall Sconce Set of 2 with Remote", "review_count": 120, "source_id": "src_detail", "provider": "sorftime"},
                    ],
                    "keywords": [],
                    "categories": [],
                    "reviews": [],
                    "tiktok_products": [],
                    "tiktok_videos": [],
                    "suppliers": [],
                    "web_documents": [],
                    "data_gaps": [],
                    "quality": {"overall_score": 0.8, "grade": "B"},
                },
            )

            result = self.run_normalizer(report_dir)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            data_pack = json.loads((report_dir / "data" / "data_pack.json").read_text(encoding="utf-8"))
            self.assertEqual(len(data_pack["products"]), 1)
            product = data_pack["products"][0]
            self.assertEqual(product["source_ids"], ["src_search", "src_detail"])
            self.assertEqual(product["validation"]["evidence_source_count"], 2)
            self.assertIn("充电式", product["title_cn"])

    def test_dedupes_keywords_and_adds_chinese_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(
                report_dir / "data" / "data_pack.json",
                {
                    "sources": [
                        {"source_id": "src_kw_1", "provider": "sorftime", "tool": "keyword_detail", "fetched_at": "now", "confidence": 0.8},
                        {"source_id": "src_kw_2", "provider": "sorftime", "tool": "category_keywords", "fetched_at": "now", "confidence": 0.8},
                    ],
                    "products": [],
                    "keywords": [
                        {"keyword": "battery operated wall sconce", "monthly_search_volume": 1000, "source_id": "src_kw_1", "provider": "sorftime"},
                        {"keyword": "Battery Operated Wall Sconce", "weekly_search_volume": 200, "recommended_cpc": 0.7, "source_id": "src_kw_2", "provider": "sorftime"},
                    ],
                    "categories": [],
                    "reviews": [],
                    "tiktok_products": [],
                    "tiktok_videos": [],
                    "suppliers": [],
                    "web_documents": [],
                    "data_gaps": [],
                    "quality": {"overall_score": 0.8, "grade": "B"},
                },
            )

            result = self.run_normalizer(report_dir)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            data_pack = json.loads((report_dir / "data" / "data_pack.json").read_text(encoding="utf-8"))
            self.assertEqual(len(data_pack["keywords"]), 1)
            keyword = data_pack["keywords"][0]
            self.assertEqual(keyword["keyword_cn"], "电池供电壁灯")
            self.assertEqual(keyword["relevance_cn"], "高相关")
            self.assertTrue(keyword["is_core_relevant"])
            self.assertEqual(keyword["source_ids"], ["src_kw_1", "src_kw_2"])
            self.assertTrue(data_pack["normalization"]["deduped"])

    def test_preserves_baseline_counts_across_multiple_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(
                report_dir / "data" / "data_pack.json",
                {
                    "sources": [
                        {"source_id": "src_kw_1", "provider": "sorftime", "tool": "keyword_detail", "fetched_at": "now", "confidence": 0.8},
                        {"source_id": "src_kw_2", "provider": "sorftime", "tool": "category_keywords", "fetched_at": "now", "confidence": 0.8},
                    ],
                    "products": [],
                    "keywords": [
                        {"keyword": "wall sconce", "monthly_search_volume": 100, "source_id": "src_kw_1", "provider": "sorftime"},
                        {"keyword": "Wall Sconce", "weekly_search_volume": 20, "source_id": "src_kw_2", "provider": "sorftime"},
                    ],
                    "categories": [],
                    "reviews": [],
                    "tiktok_products": [],
                    "tiktok_videos": [],
                    "suppliers": [],
                    "web_documents": [],
                    "data_gaps": [],
                    "quality": {"overall_score": 0.8, "grade": "B"},
                },
            )

            first_result = self.run_normalizer(report_dir)
            second_result = self.run_normalizer(report_dir)

            self.assertEqual(first_result.returncode, 0, first_result.stderr + first_result.stdout)
            self.assertEqual(second_result.returncode, 0, second_result.stderr + second_result.stdout)
            data_pack = json.loads((report_dir / "data" / "data_pack.json").read_text(encoding="utf-8"))
            self.assertEqual(data_pack["normalization"]["before_counts"]["keywords"], 2)
            self.assertEqual(data_pack["normalization"]["after_counts"]["keywords"], 1)
            self.assertEqual(data_pack["normalization"]["removed_counts"]["keywords"], 1)

    def test_keeps_market_keywords_separate_from_asin_traffic_terms(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(
                report_dir / "data" / "data_pack.json",
                {
                    "sources": [
                        {"source_id": "src_kw", "provider": "sorftime", "tool": "keyword_detail", "fetched_at": "now", "confidence": 0.8},
                        {"source_id": "src_traffic", "provider": "sorftime", "tool": "product_traffic_terms", "fetched_at": "now", "confidence": 0.8},
                    ],
                    "products": [],
                    "keywords": [
                        {"keyword": "wall sconce", "source_type": "keyword_detail", "monthly_search_volume": 59322, "source_id": "src_kw", "provider": "sorftime"},
                        {"keyword": "wall sconce", "source_type": "product_traffic_terms", "asin": "B0ABC", "traffic_position": "自然位", "source_id": "src_traffic", "provider": "sorftime"},
                    ],
                    "categories": [],
                    "reviews": [],
                    "tiktok_products": [],
                    "tiktok_videos": [],
                    "suppliers": [],
                    "web_documents": [],
                    "data_gaps": [],
                    "quality": {"overall_score": 0.8, "grade": "B"},
                },
            )

            result = self.run_normalizer(report_dir)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            data_pack = json.loads((report_dir / "data" / "data_pack.json").read_text(encoding="utf-8"))
            self.assertEqual(len(data_pack["keywords"]), 2)
            market_keyword = next(item for item in data_pack["keywords"] if item["source_type"] == "keyword_detail")
            traffic_keyword = next(item for item in data_pack["keywords"] if item["source_type"] == "product_traffic_terms")
            self.assertNotIn("asin", market_keyword)
            self.assertEqual(traffic_keyword["asin"], "B0ABC")


if __name__ == "__main__":
    unittest.main()
