#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import render_dashboard_html as renderer


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
            "keyword": f"ai plush toy {idx}" if idx >= 5 else f"robot companion {idx}",
            "monthly_search_volume": 1200 - idx if idx >= 5 else 1500 - idx,
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
                    "product_id": "internal_product_1",
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
            "tiktok_products": [{"product_id": "tk_1", "title": "AI plush", "sold_count": 100, "source_id": "src_001", "provider": "sorftime"}],
            "tiktok_videos": [{"video_id": "v_1", "title": "AI plush demo", "views": 10000, "source_id": "src_001", "provider": "sorftime"}],
            "suppliers": [{"supplier_name": "1688 supplier", "price": 18, "moq": 100, "source_id": "src_001", "provider": "sorftime"}],
            "web_documents": [{"url": "https://example.com/report", "title": "AI toy safety", "source_id": "src_002", "provider": "firecrawl"}],
            "data_gaps": ["No internal landed cost sheet."],
            "quality": {"overall_score": 0.7, "grade": "B"},
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
            for asset_name in ["report.css", "report.js", "report-data.json"]:
                self.assertTrue((report_dir / "output" / "html_reports" / "assets" / asset_name).exists(), asset_name)
            self.assertTrue((report_dir / "report_brief.json").exists(), "report_brief.json")
            self.assertTrue((report_dir / "output" / "report.html").exists(), "compat report.html")
            for view_name in [
                "market_depth_view.json",
                "lifecycle_strategy_view.json",
                "demand_gap_view.json",
            ]:
                view_path = report_dir / "analysis" / view_name
                self.assertTrue(view_path.exists(), view_name)
                view = json.loads(view_path.read_text(encoding="utf-8"))
                for key in [
                    "kpis",
                    "charts",
                    "tables",
                    "cards",
                    "evidence_strength",
                    "sample_coverage",
                    "limitations",
                    "client_safe_text",
                ]:
                    self.assertIn(key, view, f"{view_name}:{key}")
                self.assertTrue(view["client_safe_text"], view_name)

            index = (report_dir / "output" / "html_reports" / "report.html").read_text(encoding="utf-8")
            compat_index = (report_dir / "output" / "report.html").read_text(encoding="utf-8")
            self.assertIn('data-report-style="three-report-index-v2"', index)
            self.assertIn('href="assets/report.css"', index)
            self.assertIn('src="assets/report.js"', index)
            self.assertIn('href="market-depth-report.html"', index)
            self.assertIn('href="lifecycle-strategy-report.html"', index)
            self.assertIn('href="demand-gap-report.html"', index)
            self.assertNotIn('href="output/', index)
            self.assertNotIn('href="html_reports/', index)
            self.assertIn('href="html_reports/market-depth-report.html"', compat_index)
            self.assertIn('href="html_reports/lifecycle-strategy-report.html"', compat_index)
            self.assertIn('href="html_reports/demand-gap-report.html"', compat_index)
            for leaked in [
                "source_id",
                "src_001",
                "src_002",
                "B0TEST1234",
                "Product ID",
                "product_id",
                "raw_path",
                "data/raw",
                "provider",
                "tool",
                "Sorftime",
                "Firecrawl",
                "sorftime",
                "firecrawl",
                "tk_1",
                "来源",
            ]:
                self.assertNotIn(leaked, compat_index)
            rendered_text = "\n".join(
                (report_dir / "output" / "html_reports" / name).read_text(encoding="utf-8")
                for name in [
                    "report.html",
                    "market-depth-report.html",
                    "lifecycle-strategy-report.html",
                    "demand-gap-report.html",
                ]
            )
            self.assertIn('body class="template-market"', rendered_text)
            self.assertIn('body class="template-lifecycle"', rendered_text)
            self.assertIn('body class="template-demand mode-r3"', rendered_text)
            for name in ["market-depth-report.html", "lifecycle-strategy-report.html", "demand-gap-report.html"]:
                child_html = (report_dir / "output" / "html_reports" / name).read_text(encoding="utf-8")
                self.assertIn("site-nav", child_html)
                self.assertIn('href="assets/report.css"', child_html)
                self.assertIn('src="assets/report.js"', child_html)
            self.assertNotIn("壁灯", rendered_text)
            self.assertNotIn("灯具", rendered_text)
            self.assertNotIn("毛绒", rendered_text)
            for leaked in [
                "source_id",
                "src_001",
                "src_002",
                "B0TEST1234",
                "Product ID",
                "product_id",
                "internal_product_1",
                "raw_path",
                "data/raw",
                "provider",
                "tool",
                "Sorftime",
                "Firecrawl",
                "sorftime",
                "firecrawl",
                "tk_1",
                "来源",
            ]:
                self.assertNotIn(leaked, rendered_text)
            for client_term in ["证据强度", "样本覆盖", "数据缺口", "建议动作", "置信等级"]:
                self.assertIn(client_term, rendered_text)
            self.assertNotIn("1000 关键词 / 1 竞品 / 1 评论 / 1 供应样本", rendered_text)
            self.assertNotIn("1 个竞品 / 1 条评论 / 1000 个关键词", rendered_text)
            self.assertNotIn("隐私/信任", rendered_text)
            self.assertNotIn("性能/效果", rendered_text)
            self.assertIn('class="metric-tags"', rendered_text)
            self.assertIn('class="metric-tag"><b>1000</b><span>关键词</span></span>', rendered_text)
            self.assertIn('class="metric-tag"><b>1</b><span>竞品</span></span>', rendered_text)
            self.assertNotIn("This toy stopped working after two days", rendered_text)
            self.assertNotIn("privacy policy is confusing", rendered_text)
            self.assertNotIn("privacy issue", rendered_text)
            self.assertNotIn("Interactive AI Plush Toy", rendered_text)
            self.assertIn("短期使用后出现失效", rendered_text)
            self.assertIn("隐私政策和数据使用说明不够清晰", rendered_text)
            self.assertNotIn("{{", rendered_text)

            lineage = (report_dir / "data" / "lineage.md").read_text(encoding="utf-8")
            report_md = (report_dir / "output" / "report.md").read_text(encoding="utf-8")
            self.assertIn("src_001", lineage)
            self.assertIn("src_001", report_md)

            delivery = json.loads((report_dir / "output" / "delivery_result.json").read_text(encoding="utf-8"))
            self.assertEqual(delivery["html_bundle_dir"], "output/html_reports")
            self.assertEqual(delivery["html_reports"]["index"], "output/html_reports/report.html")
            self.assertEqual(delivery["html_reports"]["compat_index"], "output/report.html")
            self.assertEqual(delivery["html_reports"]["market_depth"], "output/html_reports/market-depth-report.html")
            self.assertEqual(delivery["html_reports"]["lifecycle_strategy"], "output/html_reports/lifecycle-strategy-report.html")
            self.assertEqual(delivery["html_reports"]["demand_gap"], "output/html_reports/demand-gap-report.html")
            self.assertEqual(delivery["data_readiness"]["path"], "data/normalized/data_readiness_report.json")
            self.assertTrue(delivery["data_readiness"]["acceptance_ready"])
            self.assertEqual(delivery["data_readiness"]["sample_class"], "acceptance_sample")
            self.assertEqual(delivery["data_readiness"]["counts"]["keywords"], 1000)
            self.assertEqual(
                delivery["child_skills"],
                {
                    "market_depth": "child_skills/market-depth-report",
                    "lifecycle_strategy": "child_skills/lifecycle-strategy-report",
                    "demand_gap": "child_skills/demand-gap-report",
                    "critic": "child_skills/market-research-critic",
                },
            )
            self.assertEqual(delivery["critic_review"]["path"], "analysis/critic_review.json")
            self.assertEqual(delivery["critic_review"]["refinement_plan"], "analysis/refinement_plan.json")
            self.assertEqual(delivery["critic_review"]["max_refinement_rounds"], 2)
            self.assertEqual(delivery["child_skill_invocations"]["market_depth"]["module"], "child_skills/market-depth-report")
            self.assertEqual(delivery["child_skill_invocations"]["market_depth"]["status"], "rendered")
            self.assertEqual(delivery["child_skill_invocations"]["market_depth"]["dispatch_mode"], "subprocess_child_renderer")
            self.assertEqual(delivery["child_skill_invocations"]["market_depth"]["invocation_log"], "analysis/child_skill_invocation_log.json")
            self.assertIn("analysis/market_depth_view.json", delivery["child_skill_invocations"]["market_depth"]["outputs"])
            self.assertEqual(delivery["child_skill_invocations"]["critic"]["dispatch_mode"], "subprocess_critic_child")
            self.assertEqual(delivery["child_skill_invocations"]["critic"]["invocation_log"], "analysis/child_skill_invocation_log.json")
            self.assertEqual(
                delivery["site_assets"],
                {
                    "css": "output/html_reports/assets/report.css",
                    "js": "output/html_reports/assets/report.js",
                    "data": "output/html_reports/assets/report-data.json",
                },
            )
            for feature in ["table_filter", "table_sort", "tabs", "evidence_drawer", "chart_linking", "mobile_nav"]:
                self.assertIn(feature, delivery["interactive_features"])
            self.assertIn("removed_counts", delivery["cleaning_summary"])
            site_data = json.loads((report_dir / "output" / "html_reports" / "assets" / "report-data.json").read_text(encoding="utf-8"))
            self.assertEqual(site_data["report_files"]["market_depth"], "market-depth-report.html")
            self.assertTrue(site_data["readiness"]["acceptance_ready"])
            self.assertEqual(site_data["readiness"]["sample_class"], "acceptance_sample")
            self.assertEqual(site_data["readiness"]["counts"]["products"], 1)
            self.assertEqual(site_data["cleaning_summary"]["after_counts"]["keywords"], 1000)
            self.assertIn("child_skills/demand-gap-report", site_data["child_skills"].values())
            self.assertIn("child_skills/market-research-critic", site_data["child_skills"].values())
            report_brief = json.loads((report_dir / "report_brief.json").read_text(encoding="utf-8"))
            self.assertEqual(report_brief["task_id"], "ai_plush_us_20260526")
            self.assertEqual(report_brief["child_skills"], delivery["child_skills"])
            self.assertEqual(report_brief["child_skill_invocations"], delivery["child_skill_invocations"])
            self.assertEqual(report_brief["static_site"]["bundle_dir"], "output/html_reports")
            self.assertTrue((report_dir / "analysis" / "critic_review.json").exists())
            self.assertTrue((report_dir / "analysis" / "refinement_plan.json").exists())
            invocation_log = json.loads((report_dir / "analysis" / "child_skill_invocation_log.json").read_text(encoding="utf-8"))
            self.assertEqual(len(invocation_log), 4)
            self.assertEqual(
                {entry["dispatch_mode"] for entry in invocation_log},
                {"subprocess_child_renderer", "subprocess_critic_child"},
            )
            self.assertEqual({entry["returncode"] for entry in invocation_log}, {0})
            self.assertTrue(all(entry.get("renderer_sha256") for entry in invocation_log))

            validation = self.run_validator(report_dir)
            self.assertEqual(validation.returncode, 0, validation.stderr + validation.stdout)

    def test_renderer_stops_when_data_readiness_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_renderable_report(report_dir)
            data_pack_path = report_dir / "data" / "data_pack.json"
            data_pack = json.loads(data_pack_path.read_text(encoding="utf-8"))
            data_pack["products"] = []
            data_pack["keywords"] = []
            write_json(data_pack_path, data_pack)

            result = self.run_renderer(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("data readiness failed before rendering", result.stderr + result.stdout)
            readiness_path = report_dir / "data" / "normalized" / "data_readiness_report.json"
            self.assertTrue(readiness_path.exists())
            readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
            self.assertFalse(readiness["acceptance_ready"])
            self.assertEqual(readiness["sample_class"], "non_acceptance_sample")

    def test_renderer_stops_when_critic_still_fails_after_refinement(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_renderable_report(report_dir)

            def failing_critic(*_args, **_kwargs):
                write_json(
                    report_dir / "analysis" / "critic_review.json",
                    {
                        "pass": False,
                        "round_id": 0,
                        "score": 61,
                        "grade": "C",
                        "findings": [],
                        "blocking_issues": ["证据不足"],
                        "resolved_findings": [],
                        "remaining_findings": ["证据不足"],
                        "report_issues": {},
                        "data_confidence": {},
                        "suggestions": [],
                        "refinement_targets": [],
                        "max_refinement_rounds": 2,
                    },
                )
                write_json(report_dir / "analysis" / "refinement_plan.json", {"status": "needs_revision", "max_refinement_rounds": 2, "operations": []})
                write_json(report_dir / "analysis" / "critic_decision.json", {"decision": "Watch", "pass": False, "score": 61})
                return {"decision": "Watch", "pass": False, "score": 61}

            with patch.object(renderer, "run_critic_child", side_effect=failing_critic):
                with self.assertRaises(RuntimeError) as ctx:
                    renderer.render(report_dir)

            self.assertIn("critic did not pass after refinement", str(ctx.exception))

    def test_renderer_downgrades_partial_go_to_watch(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_renderable_report(report_dir)
            delivery_path = report_dir / "output" / "delivery_result.json"
            delivery = json.loads(delivery_path.read_text(encoding="utf-8"))
            delivery["status"] = "partial"
            delivery["decision"] = "Go"
            write_json(delivery_path, delivery)

            result = self.run_renderer(report_dir)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            delivery = json.loads(delivery_path.read_text(encoding="utf-8"))
            self.assertEqual(delivery["decision"], "Watch")
            self.assertEqual(delivery["decision_adjustment"]["from"], "Go")
            self.assertIn("partial_delivery", delivery["decision_adjustment"]["reasons"])
            validation = self.run_validator(report_dir)
            self.assertEqual(validation.returncode, 0, validation.stderr + validation.stdout)


if __name__ == "__main__":
    unittest.main()
