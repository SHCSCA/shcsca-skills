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
            self.assertNotIn("title_cn", product)
            self.assertNotIn("positioning_cn", product)

    def test_relevance_gate_clears_stale_customer_labels_without_generating_category_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(
                report_dir / "data" / "data_pack.json",
                {
                    "sources": [],
                    "research_object": {
                        "type": "asin",
                        "value": "B0BR4QYGS7",
                        "category": "Hunting Blinds",
                        "seed_keywords": ["hunting blinds", "ground blind", "see through hunting blind"],
                    },
                    "products": [
                        {
                            "asin": "B0BR4QYGS7",
                            "title": "FUNHORUN Hunting Blind 270/360 Degree See Through Ground Blind with Carrying Bag",
                            "brand": "FUNHORUN",
                            "category": "Sports & Outdoors",
                            "subcategory": "Blinds",
                            "positioning_cn": "户外感应灯",
                        },
                        {
                            "asin": "B076VQ91JJ",
                            "title": "TotalBoat Aluminum Boat Paint for Canoes, Hunting Blinds, and Trailers",
                            "brand": "TotalBoat",
                            "category": "Sports & Outdoors",
                            "subcategory": "Painting Supplies",
                            "positioning_cn": "户外感应灯",
                        },
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
            effective_asins = {product.get("asin") for product in data_pack["effective_products"]}
            self.assertIn("B0BR4QYGS7", effective_asins)
            self.assertNotIn("B076VQ91JJ", effective_asins)
            product = next(item for item in data_pack["products"] if item.get("asin") == "B0BR4QYGS7")
            self.assertNotEqual(product.get("title_cn"), "户外感应灯")
            self.assertNotEqual(product.get("segment_cn"), "户外感应灯")
            self.assertNotEqual(product.get("positioning_cn"), "户外感应灯")
            self.assertNotIn("customer_title_cn", product)

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
            self.assertEqual(keyword["keyword_cn"], "未映射关键词：ai plush toy")
            self.assertNotEqual(keyword["keyword_cn"], keyword["keyword"])
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

    def test_smart_lighting_relevance_gate_removes_owala_and_generates_categories(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(report_dir / "report_brief.json", {"research_object": {"value": "smart lighting"}})
            write_json(
                report_dir / "data" / "data_pack.json",
                {
                    "sources": [{"source_id": "src_a", "provider": "sorftime", "tool": "product_search", "fetched_at": "now", "confidence": 0.8}],
                    "research_object": {"type": "keyword", "value": "smart lighting"},
                    "products": [
                        {
                            "asin": "B0LIGHT001",
                            "title": "Rechargeable Under Cabinet Lights Motion Sensor LED Light",
                            "brand": "MCGOR",
                            "category": "Tools & Home Improvement > Lighting",
                            "segment_cn": "橱柜感应灯",
                            "source_id": "src_a",
                            "provider": "sorftime",
                        },
                        {
                            "asin": "B0OWALA001",
                            "title": "Owala FreeSip Insulated Stainless Steel Water Bottle",
                            "brand": "Owala",
                            "category": "Sports & Outdoors",
                            "segment_cn": "户外感应灯",
                            "source_id": "src_a",
                            "provider": "sorftime",
                        },
                    ],
                    "keywords": [
                        {"keyword": "under cabinet lighting", "monthly_search_volume": 1000, "source_id": "src_a", "provider": "sorftime"},
                        {"keyword": "Under Cabinet Lighting", "monthly_search_volume": 900, "source_id": "src_a", "provider": "sorftime"},
                        {"keyword": "water bottle", "monthly_search_volume": 50000, "keyword_cn": "水瓶", "source_id": "src_a", "provider": "sorftime"},
                    ],
                    "categories": [],
                    "reviews": [
                        {"asin": "B0LIGHT001", "rating": 5, "text": "Great under cabinet light", "source_id": "src_a", "provider": "sorftime"},
                        {"asin": "B0OWALA001", "rating": 5, "text": "Great water bottle", "source_id": "src_a", "provider": "sorftime"},
                    ],
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
            self.assertEqual([product["asin"] for product in data_pack["effective_products"]], ["B0LIGHT001"])
            self.assertEqual([review["asin"] for review in data_pack["effective_reviews"]], ["B0LIGHT001"])
            self.assertEqual([kw["keyword"].casefold() for kw in data_pack["effective_keywords"]], ["under cabinet lighting"])
            self.assertEqual(data_pack["research_relevance"]["removed_counts"]["products"], 1)
            self.assertEqual(data_pack["research_relevance"]["removed_counts"]["keywords"], 1)
            self.assertTrue(data_pack["categories"])
            self.assertEqual(data_pack["categories"][0]["product_count"], 1)

    def test_dedupes_repeated_data_gaps_by_module_and_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            repeated_gap = {
                "type": "amazon_product_enrichment_empty_dimensions",
                "module": "amazon_product_enrichment",
                "gap": "Sorftime Amazon ASIN enrichment tools returned no rows for: product_detail.",
                "fetched_at": "old",
            }
            write_json(
                report_dir / "data" / "data_pack.json",
                {
                    "sources": [],
                    "products": [],
                    "keywords": [{"keyword": f"smart light {idx}"} for idx in range(1000)],
                    "categories": [],
                    "reviews": [{"asin": "B0ABC", "rating": 5, "text": f"review {idx}"} for idx in range(80)],
                    "tiktok_products": [],
                    "tiktok_videos": [],
                    "suppliers": [],
                    "web_documents": [],
                    "data_gaps": [
                        repeated_gap,
                        repeated_gap | {"fetched_at": "new"},
                        "同一文本缺口",
                        "同一文本缺口",
                    ],
                    "quality": {"overall_score": 0.8, "grade": "B"},
                },
            )

            result = self.run_normalizer(report_dir)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            data_pack = json.loads((report_dir / "data" / "data_pack.json").read_text(encoding="utf-8"))
            enrichment_gaps = [
                gap
                for gap in data_pack["data_gaps"]
                if isinstance(gap, dict) and gap.get("module") == "amazon_product_enrichment"
            ]
            self.assertEqual(len(enrichment_gaps), 1)
            self.assertEqual(sum(1 for gap in data_pack["data_gaps"] if gap == "同一文本缺口"), 1)

    def test_removes_stale_keyword_and_review_gaps_when_counts_recover(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(
                report_dir / "data" / "data_pack.json",
                {
                    "sources": [],
                    "products": [],
                    "keywords": [{"keyword": f"smart light {idx}"} for idx in range(1000)],
                    "categories": [],
                    "reviews": [{"asin": "B0ABC", "rating": 5, "text": f"review {idx}"} for idx in range(80)],
                    "tiktok_products": [],
                    "tiktok_videos": [],
                    "suppliers": [],
                    "web_documents": [],
                    "data_gaps": [
                        {"module": "keyword_sample_depth", "reason": "标准/深度版关键词样本不足 1000，当前 12。"},
                        {"type": "keyword_collection_no_seed", "gap": "No keyword seed was available."},
                        {"type": "review_collection_no_asin", "gap": "No ASIN was available for Sorftime review collection."},
                        {"module": "review_sample_depth", "reason": "评论样本不足建议门槛 80，当前 0。"},
                        {"module": "amazon_product_enrichment", "gap": "产品增强维度仍需复测。"},
                    ],
                    "quality": {"overall_score": 0.8, "grade": "B"},
                },
            )

            result = self.run_normalizer(report_dir)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            data_pack = json.loads((report_dir / "data" / "data_pack.json").read_text(encoding="utf-8"))
            markers = [
                (gap.get("type") or gap.get("module"))
                for gap in data_pack["data_gaps"]
                if isinstance(gap, dict)
            ]
            self.assertNotIn("keyword_sample_depth", markers)
            self.assertNotIn("keyword_collection_no_seed", markers)
            self.assertNotIn("review_collection_no_asin", markers)
            self.assertNotIn("review_sample_depth", markers)
            self.assertIn("amazon_product_enrichment", markers)
            self.assertEqual(data_pack["normalization"]["data_gaps_recovered_removed"], 4)

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
