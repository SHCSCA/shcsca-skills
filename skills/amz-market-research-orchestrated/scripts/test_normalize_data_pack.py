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
                        {"asin": "B0ABC", "title": "Interactive AI Plush Toy with Voice Module", "price": 39.99, "source_id": "src_search", "provider": "sorftime"},
                        {"asin": "B0ABC", "title": "Interactive AI Plush Toy with Voice Module and Parent App", "review_count": 120, "source_id": "src_detail", "provider": "sorftime"},
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
            self.assertEqual(product["title_cn"], "竞品样本")
            self.assertNotIn("壁灯", product["title_cn"])

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
                    "research_object": {"type": "keyword", "value": "ai plush toy"},
                    "products": [],
                    "keywords": [
                        {"keyword": "ai plush toy", "monthly_search_volume": 1000, "source_id": "src_kw_1", "provider": "sorftime"},
                        {"keyword": "AI Plush Toy", "weekly_search_volume": 200, "recommended_cpc": 0.7, "source_id": "src_kw_2", "provider": "sorftime"},
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
            self.assertEqual(keyword["keyword_cn"], "ai plush toy")
            self.assertEqual(keyword["relevance_cn"], "高相关")
            self.assertTrue(keyword["is_core_relevant"])
            self.assertNotIn("壁灯", keyword["keyword_cn"])
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
                        {"keyword": "ai plush toy", "monthly_search_volume": 100, "source_id": "src_kw_1", "provider": "sorftime"},
                        {"keyword": "AI Plush Toy", "weekly_search_volume": 20, "source_id": "src_kw_2", "provider": "sorftime"},
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
                        {"keyword": "ai plush toy", "source_type": "keyword_detail", "monthly_search_volume": 59322, "source_id": "src_kw", "provider": "sorftime"},
                        {"keyword": "ai plush toy", "source_type": "product_traffic_terms", "asin": "B0ABC", "traffic_position": "自然位", "source_id": "src_traffic", "provider": "sorftime"},
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

    def test_strengthens_global_cleaning_for_titles_suppliers_and_canonical_urls(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(
                report_dir / "data" / "data_pack.json",
                {
                    "sources": [
                        {"source_id": "src_a", "provider": "sorftime", "tool": "product_search", "fetched_at": "now", "confidence": 0.8},
                        {"source_id": "src_b", "provider": "firecrawl", "tool": "scrape", "fetched_at": "now", "confidence": 0.8},
                    ],
                    "products": [
                        {"title": "AI Plush Toy - Parent App", "price": 89, "source_id": "src_a", "provider": "sorftime"},
                        {"title": " ai plush toy parent app ", "review_count": 22, "source_id": "src_b", "provider": "firecrawl"},
                    ],
                    "keywords": [],
                    "categories": [],
                    "reviews": [],
                    "tiktok_products": [],
                    "tiktok_videos": [],
                    "suppliers": [
                        {"title": "AI Plush Shell", "store_name": "Shenzhen Toy Co.", "url": "https://detail.1688.com/offer/1.html?spm=a", "source_id": "src_a", "provider": "sorftime"},
                        {"title": "ai plush shell", "store_name": "shenzhen toy co.", "url": "https://detail.1688.com/offer/1.html?foo=bar", "source_id": "src_b", "provider": "firecrawl"},
                    ],
                    "web_documents": [
                        {"url": "https://example.com/report?utm_source=ad#section", "title": "Report A", "source_id": "src_a", "provider": "sorftime"},
                        {"url": "https://example.com/report/", "title": "Report B", "source_id": "src_b", "provider": "firecrawl"},
                    ],
                    "data_gaps": [],
                    "quality": {"overall_score": 0.8, "grade": "B"},
                },
            )

            result = self.run_normalizer(report_dir)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            data_pack = json.loads((report_dir / "data" / "data_pack.json").read_text(encoding="utf-8"))
            normalized = json.loads((report_dir / "data" / "normalized" / "normalized_data_pack.json").read_text(encoding="utf-8"))
            self.assertEqual(len(data_pack["products"]), 1)
            self.assertEqual(len(data_pack["suppliers"]), 1)
            self.assertEqual(len(data_pack["web_documents"]), 1)
            self.assertEqual(normalized["normalization"]["removed_counts"]["products"], 1)
            self.assertEqual(normalized["normalization"]["removed_counts"]["suppliers"], 1)
            self.assertEqual(normalized["normalization"]["removed_counts"]["web_documents"], 1)
            self.assertEqual(data_pack["web_documents"][0]["canonical_url"], "https://example.com/report")
            self.assertEqual(data_pack["cleaning_summary"], data_pack["normalization"])

    def test_caps_quality_when_review_and_cross_validation_are_thin(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(
                report_dir / "data" / "data_pack.json",
                {
                    "sources": [{"source_id": "src_a", "provider": "sorftime", "tool": "product_search", "fetched_at": "now", "confidence": 0.8}],
                    "products": [{"asin": "B0ABC", "title": "AI Plush Toy", "source_id": "src_a", "provider": "sorftime"}],
                    "keywords": [{"keyword": f"ai plush toy {idx}", "source_id": "src_a", "provider": "sorftime"} for idx in range(1000)],
                    "categories": [],
                    "reviews": [{"asin": "B0ABC", "rating": 5, "text": "Works well", "source_id": "src_a", "provider": "sorftime"}],
                    "tiktok_products": [],
                    "tiktok_videos": [],
                    "suppliers": [],
                    "web_documents": [],
                    "data_gaps": [],
                    "quality": {"overall_score": 0.92, "grade": "A"},
                },
            )

            result = self.run_normalizer(report_dir)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            data_pack = json.loads((report_dir / "data" / "data_pack.json").read_text(encoding="utf-8"))
            self.assertLessEqual(data_pack["quality"]["overall_score"], 0.74)
            self.assertEqual(data_pack["quality"]["grade"], "low_confidence_watch")
            self.assertEqual(data_pack["quality"]["original_overall_score"], 0.92)
            self.assertTrue(any(gap.get("module") == "review_sample_depth" for gap in data_pack["data_gaps"] if isinstance(gap, dict)))

    def test_backfills_legacy_source_metadata_and_entity_provider(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(
                report_dir / "data" / "data_pack.json",
                {
                    "created_at": "2026-05-25T10:00:00+08:00",
                    "sources": [{"source_id": "src_legacy", "type": "market_report", "name": "Legacy market page"}],
                    "products": [{"title": "Legacy Product", "source_id": "src_legacy"}],
                    "quality": {"overall_score": 0.8, "grade": "B"},
                },
            )

            result = self.run_normalizer(report_dir)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            data_pack = json.loads((report_dir / "data" / "data_pack.json").read_text(encoding="utf-8"))
            source = data_pack["sources"][0]
            self.assertEqual(source["provider"], "market_report")
            self.assertEqual(source["tool"], "market_report")
            self.assertEqual(source["fetched_at"], "2026-05-25T10:00:00+08:00")
            self.assertEqual(source["confidence"], "low")
            self.assertEqual(data_pack["products"][0]["provider"], "market_report")
            for key in ["keywords", "categories", "reviews", "tiktok_products", "tiktok_videos", "suppliers", "web_documents", "data_gaps"]:
                self.assertIsInstance(data_pack[key], list)


if __name__ == "__main__":
    unittest.main()
