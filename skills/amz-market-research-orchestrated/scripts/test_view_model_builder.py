#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from view_model_builder import build_report_views, build_site_data, write_report_views


CHILD_SKILLS = {
    "market_depth": "child_skills/market-depth-report",
    "lifecycle_strategy": "child_skills/lifecycle-strategy-report",
    "demand_gap": "child_skills/demand-gap-report",
    "critic": "child_skills/market-research-critic",
}


def sample_data_pack():
    return {
        "sources": [{"source_id": "src_001", "provider": "sorftime"}],
        "products": [
            {
                "asin": "B0TEST1234",
                "title": "Interactive AI Plush Toy",
                "segment": "premium",
                "price": "$89",
                "estimated_monthly_sales": 1200,
                "rating": 4.5,
                "review_count": 500,
                "source_id": "src_001",
                "provider": "sorftime",
            }
        ],
        "keywords": [{"keyword": "ai plush toy", "monthly_search_volume": 1200}],
        "categories": [{"top100_estimated_monthly_units": 10000}],
        "reviews": [
            {
                "asin": "B0TEST1234",
                "rating": 2,
                "title": "privacy issue",
                "text": "This toy stopped working after two days and the privacy policy is confusing.",
                "source_id": "src_001",
                "provider": "sorftime",
            }
        ],
        "suppliers": [{"supplier_name": "1688 supplier", "price": 18, "source_id": "src_001"}],
        "tiktok_products": [{}],
        "tiktok_videos": [{}],
        "web_documents": [{}],
        "data_gaps": [{"gap": "Need Keepa history", "reason": "No internal landed cost sheet."}],
        "quality": {"overall_score": 0.84, "grade": "A"},
        "normalization": {
            "deduped": True,
            "before_counts": {"products": 2},
            "after_counts": {"products": 1},
            "removed_counts": {"products": 1},
            "cross_validated_counts": {"products": 1},
        },
    }


class ViewModelBuilderTest(unittest.TestCase):
    def test_builds_three_views_and_site_data(self):
        data_pack = sample_data_pack()
        analysis_plan = {"method_chain": [{"method_id": "market.scan"}], "limitations": ["Review sample is thin."]}

        views = build_report_views(data_pack, analysis_plan, "Watch")
        site_data = build_site_data(data_pack, analysis_plan, "Watch", CHILD_SKILLS)

        self.assertEqual(sorted(views.keys()), ["demand_gap_view", "lifecycle_strategy_view", "market_depth_view"])
        for payload in views.values():
            self.assertIn("kpis", payload)
            self.assertIn("tables", payload)
            self.assertEqual(payload["evidence_strength"], "高")
            self.assertTrue(payload["client_safe_text"])
        self.assertEqual(site_data["child_skills"]["critic"], "child_skills/market-research-critic")
        self.assertEqual(site_data["cleaning_summary"]["removed_counts"]["products"], 1)
        self.assertIn("table_filter", site_data["interactive_features"])

    def test_write_report_views_redacts_customer_visible_payloads(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            data_pack = sample_data_pack()
            analysis_plan = {"method_chain": [], "limitations": ["Sorftime estimates are not official Amazon sales."]}

            write_report_views(report_dir, data_pack, analysis_plan, "Watch")

            combined = "\n".join(
                (report_dir / "analysis" / name).read_text(encoding="utf-8")
                for name in ["market_depth_view.json", "lifecycle_strategy_view.json", "demand_gap_view.json"]
            )
            payload = json.loads((report_dir / "analysis" / "demand_gap_view.json").read_text(encoding="utf-8"))
            self.assertIn("隐私政策和数据使用说明不够清晰", combined)
            for leaked in ["source_id", "src_001", "B0TEST1234", "provider", "sorftime", "Interactive AI Plush Toy"]:
                self.assertNotIn(leaked, combined)
            self.assertTrue(payload["client_safe_text"])


if __name__ == "__main__":
    unittest.main()
