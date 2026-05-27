#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("render_dashboard_html.py")
VALIDATOR = Path(__file__).with_name("validate_market_research_deliverables.py")


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_renderable_report(root):
    keywords = [
        {
            "keyword": f"ai plush toy {idx}",
            "monthly_search_volume": 1200 - idx,
            "source_id": "src_001",
            "provider": "sorftime",
        }
        for idx in range(1000)
    ]
    write_json(
        root / "data" / "data_pack.json",
        {
            "task_id": "ai_plush_us_20260526",
            "created_at": "2026-05-26T10:00:00+08:00",
            "research_object": {"type": "keyword", "value": "ai plush toy"},
            "sources": [
                {
                    "source_id": "src_001",
                    "provider": "sorftime",
                    "tool": "product_search",
                    "fetched_at": "2026-05-26T10:00:00+08:00",
                    "confidence": "medium",
                    "raw_path": "data/raw/sorftime_product_search.json",
                },
                {
                    "source_id": "src_002",
                    "provider": "firecrawl",
                    "tool": "firecrawl_search",
                    "fetched_at": "2026-05-26T10:01:00+08:00",
                    "confidence": "medium",
                    "raw_path": "data/raw/firecrawl_search.json",
                },
            ],
            "products": [
                {
                    "asin": "B0TEST1234",
                    "title": "Interactive AI Plush Toy",
                    "price": 89,
                    "rating": 4.5,
                    "review_count": 500,
                    "estimated_monthly_sales": 1200,
                    "source_id": "src_001",
                    "provider": "sorftime",
                }
            ],
            "keywords": keywords,
            "categories": [{"node_id": "123", "name": "Plush Toys", "top100_estimated_monthly_units": 10000, "source_id": "src_001", "provider": "sorftime"}],
            "reviews": [{"asin": "B0TEST1234", "rating": 2, "title": "privacy issue", "text": "privacy concern", "source_id": "src_001", "provider": "sorftime"}],
            "tiktok_products": [{"product_id": "tk_1", "title": "AI plush", "sold_count": 100, "source_id": "src_001", "provider": "sorftime"}],
            "tiktok_videos": [{"video_id": "v_1", "title": "AI plush demo", "views": 10000, "source_id": "src_001", "provider": "sorftime"}],
            "suppliers": [{"supplier_name": "1688 supplier", "price": 18, "moq": 100, "source_id": "src_001", "provider": "sorftime"}],
            "web_documents": [{"url": "https://example.com/report", "title": "AI toy safety", "source_id": "src_002", "provider": "firecrawl"}],
            "data_gaps": ["No internal landed cost sheet."],
            "quality": {"overall_score": 0.82, "grade": "decision_grade"},
        },
    )
    write_json(
        root / "analysis" / "analysis_plan.json",
        {
            "task_id": "ai_plush_us_20260526",
            "method_chain": [
                {"method_id": "market.top100_competitor_scan", "used_source_ids": ["src_001"], "output": "competitor matrix"},
                {"method_id": "demand.kano_jtbd_gap", "used_source_ids": ["src_001"], "output": "需求断层"},
            ],
            "confidence": {"final_decision": "medium"},
            "limitations": ["Sorftime estimates are not official Amazon sales."],
        },
    )
    write_json(root / "analysis" / "lifecycle_strategy.json", {"skus": [{"name": "替换核心配件", "phase": "P1", "source_id": "src_001"}]})
    write_json(root / "analysis" / "demand_gap.json", {"opportunities": [{"pain": "隐私担忧", "kano": "must-be", "source_id": "src_001"}]})
    write_json(root / "output" / "delivery_result.json", {"status": "complete", "decision": "Watch"})
    write_text(root / "output" / "report.md", "# Report\n\n估算月销量（Sorftime）来自 src_001。\n\n## Go / Watch / No-Go\nWatch\n")


class RenderDashboardHtmlTest(unittest.TestCase):
    def run_renderer(self, report_dir):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--dir", str(report_dir)],
            text=True,
            capture_output=True,
            check=False,
        )

    def run_validator(self, report_dir):
        return subprocess.run(
            [sys.executable, str(VALIDATOR), "--dir", str(report_dir)],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_renderer_writes_index_and_three_child_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_renderable_report(report_dir)

            result = self.run_renderer(report_dir)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            for name in [
                "report.html",
                "market-depth-report.html",
                "lifecycle-strategy-report.html",
                "demand-gap-report.html",
            ]:
                self.assertTrue((report_dir / "output" / "html_reports" / name).exists(), name)
            self.assertTrue((report_dir / "output" / "report.html").exists(), "compat report.html")

            index = (report_dir / "output" / "html_reports" / "report.html").read_text(encoding="utf-8")
            compat_index = (report_dir / "output" / "report.html").read_text(encoding="utf-8")
            self.assertIn('data-report-style="three-report-index-v2"', index)
            self.assertIn('href="market-depth-report.html"', index)
            self.assertIn('href="lifecycle-strategy-report.html"', index)
            self.assertIn('href="demand-gap-report.html"', index)
            self.assertNotIn('href="output/', index)
            self.assertNotIn('href="html_reports/', index)
            self.assertIn('href="html_reports/market-depth-report.html"', compat_index)
            self.assertIn('href="html_reports/lifecycle-strategy-report.html"', compat_index)
            self.assertIn('href="html_reports/demand-gap-report.html"', compat_index)
            rendered_text = "\n".join(
                (report_dir / "output" / "html_reports" / name).read_text(encoding="utf-8")
                for name in [
                    "report.html",
                    "market-depth-report.html",
                    "lifecycle-strategy-report.html",
                    "demand-gap-report.html",
                ]
            )
            self.assertNotIn("壁灯", rendered_text)
            self.assertNotIn("灯具", rendered_text)
            self.assertNotIn("毛绒", rendered_text)
            self.assertNotIn("{{", rendered_text)

            delivery = json.loads((report_dir / "output" / "delivery_result.json").read_text(encoding="utf-8"))
            self.assertEqual(delivery["html_bundle_dir"], "output/html_reports")
            self.assertEqual(delivery["html_reports"]["index"], "output/html_reports/report.html")
            self.assertEqual(delivery["html_reports"]["compat_index"], "output/report.html")
            self.assertEqual(delivery["html_reports"]["market_depth"], "output/html_reports/market-depth-report.html")
            self.assertEqual(delivery["html_reports"]["lifecycle_strategy"], "output/html_reports/lifecycle-strategy-report.html")
            self.assertEqual(delivery["html_reports"]["demand_gap"], "output/html_reports/demand-gap-report.html")

            validation = self.run_validator(report_dir)
            self.assertEqual(validation.returncode, 0, validation.stderr + validation.stdout)


if __name__ == "__main__":
    unittest.main()
