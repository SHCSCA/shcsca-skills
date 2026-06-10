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


def supplier_rows(count=50):
    return [
        {
            "title": f"智能玩具外壳工厂款 {idx}",
            "supplier_name": f"供应商 {idx}",
            "url": f"https://detail.1688.com/offer/{idx}.html",
            "price_rmb": 20 + idx,
            "sales_30d": 500 + idx,
            "shipping_origin": "广东",
            "seed_keyword": "智能玩具",
            "source_id": "src_001",
            "provider": "sorftime",
        }
        for idx in range(count)
    ]


def competitor_rows(count=30):
    segments = ["智能陪伴玩具", "语音互动玩具", "儿童礼品玩具"]
    return [
        {
            "asin": f"B0P{idx:07d}",
            "product_id": f"internal_product_{idx}",
            "title": f"Interactive AI Plush Toy Competitor {idx}",
            "brand": f"ToyBrand {idx % 8}",
            "segment_cn": segments[idx % len(segments)],
            "price": 39 + idx,
            "rating": 4.1 + (idx % 6) / 10,
            "review_count": 500 + idx,
            "estimated_monthly_sales": 1200 + idx,
            "source_id": "src_001",
            "provider": "sorftime",
        }
        for idx in range(count)
    ]


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
            "products": competitor_rows(30),
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
            "suppliers": supplier_rows(50),
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
    def run_renderer(self, report_dir, *extra_args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--dir", str(report_dir), *extra_args],
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
            self.assertIn("三合一市场研究报告", index)
            self.assertNotIn("three-report-index-v2", index)
            self.assertIn('href="assets/report.css"', index)
            self.assertIn('src="assets/report.js"', index)
            self.assertNotIn("<style", index)
            self.assertEqual(index.count("client-trust-grid"), 1)
            self.assertEqual(index.count("trust-tabs"), 1)
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
            market_html = (report_dir / "output" / "html_reports" / "market-depth-report.html").read_text(encoding="utf-8")
            self.assertIn("市场深度调研报告", market_html)
            self.assertNotIn("market-depth-report-v2", market_html)
            self.assertIn('body class="template-market"', market_html)
            self.assertNotIn("<style", market_html)
            for section_id in [
                "market-dashboard",
                "competitor-scan",
                "voc-deep-dive",
                "benchmark-sniper",
                "product-definition",
                "visual-direction",
                "supply-chain",
            ]:
                self.assertIn(f'id="{section_id}"', market_html)
            self.assertIn('class="chart-body chart-h-300"', market_html)
            self.assertIn('class="chart-body chart-h-260"', market_html)
            self.assertIn('class="comp-col-product"', market_html)
            self.assertIn('class="section-header section-header-spaced"', market_html)
            self.assertIn('data-chart-source="marketRows"', market_html)
            self.assertNotIn("<col style=", market_html)
            self.assertNotIn('style="height:', market_html)
            self.assertNotIn("style=\"--w:", market_html)
            self.assertNotIn('class="section-header" style=', market_html)
            demand_html = (report_dir / "output" / "html_reports" / "demand-gap-report.html").read_text(encoding="utf-8")
            self.assertIn('data-chart-source="appealsRows"', demand_html)
            self.assertIn('data-chart-source="gapRows"', demand_html)
            self.assertIn('id="appealsRose" class="chart demand-chart"', demand_html)
            self.assertIn('id="gapRadar" class="chart demand-chart"', demand_html)
            self.assertEqual(demand_html.count('class="chart demand-chart"'), 2)
            self.assertNotIn('id="appealsRose" class="chart"><div class="mini-chart"', demand_html)
            self.assertNotIn('id="gapRadar" class="chart"><div class="mini-chart"', demand_html)
            self.assertIn("目标ASIN锚点", demand_html)
            self.assertNotIn("demand-anchor-grid", demand_html)
            self.assertNotIn("研究对象锚点证据", demand_html)
            target_section = demand_html.split('id="target-anchor"', 1)[1].split('id="decision-board"', 1)[0]
            self.assertNotIn('<div class="card"><div class="card-title">研究对象锚点</div>', target_section)
            self.assertIn('body class="template-lifecycle"', rendered_text)
            self.assertIn('body class="template-demand mode-r3"', rendered_text)
            lifecycle_html = (report_dir / "output" / "html_reports" / "lifecycle-strategy-report.html").read_text(encoding="utf-8")
            self.assertIn("lifecycle-kpi-secondary", lifecycle_html)
            self.assertIn("P1 首发 SKU", lifecycle_html)
            self.assertIn("高优先级 SKU", lifecycle_html)
            self.assertIn("套装/升级 SKU", lifecycle_html)
            self.assertIn("战略结论", lifecycle_html)
            for name in ["market-depth-report.html", "lifecycle-strategy-report.html", "demand-gap-report.html"]:
                child_html = (report_dir / "output" / "html_reports" / name).read_text(encoding="utf-8")
                self.assertNotIn("site-nav", child_html)
                self.assertNotIn("<style", child_html)
                self.assertIn('href="assets/report.css"', child_html)
                self.assertIn('src="assets/report.js"', child_html)
            self.assertNotIn("壁灯", rendered_text)
            self.assertNotIn("灯具", rendered_text)
            self.assertNotIn("毛绒", rendered_text)
            for leaked in [
                "source_id",
                "src_001",
                "src_002",
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
            for client_term in ["证据强度", "数据覆盖", "数据缺口", "建议动作", "置信等级"]:
                self.assertIn(client_term, rendered_text)
            self.assertNotIn("1000 关键词 / 1 竞品 / 1 评论 / 1 供应样本", rendered_text)
            self.assertNotIn("1 个竞品 / 1 条评论 / 1000 个关键词", rendered_text)
            self.assertNotIn("隐私/信任", rendered_text)
            self.assertNotIn("性能/效果", rendered_text)
            self.assertIn('class="metric-tags"', rendered_text)
            self.assertIn('class="metric-tag"><b>1000</b><span>关键词</span></span>', rendered_text)
            self.assertIn('class="metric-tag"><b>30</b><span>竞品</span></span>', rendered_text)
            self.assertIn('data-allow-english-review="short"', rendered_text)
            self.assertIn("This toy stopped working after two days", rendered_text)
            self.assertNotIn("privacy issue", rendered_text)
            self.assertNotIn("Interactive AI Plush Toy", rendered_text)
            self.assertIn("短期使用后出现失效", rendered_text)
            self.assertIn("隐私政策和数据使用说明不够清晰", rendered_text)
            self.assertNotIn("{{", rendered_text)
            self.assertIn("竞品参考毛利率测算", rendered_text)
            self.assertIn("参考竞品 ASIN", rendered_text)
            self.assertIn("1688 成本分位数", rendered_text)
            self.assertIn("B0P0000000", market_html)
            self.assertIn('data-allow-asin="benchmark-sniper"', market_html)

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
                    "echarts": "output/html_reports/assets/echarts.min.js",
                },
            )
            for feature in ["table_filter", "table_sort", "tabs", "chart_linking", "pc_anchor_nav", "evidence_drawer"]:
                self.assertIn(feature, delivery["interactive_features"])
            self.assertNotIn("mobile_nav", delivery["interactive_features"])
            self.assertIn("removed_counts", delivery["cleaning_summary"])
            site_data = json.loads((report_dir / "output" / "html_reports" / "assets" / "report-data.json").read_text(encoding="utf-8"))
            self.assertEqual(site_data["report_files"]["market_depth"], "market-depth-report.html")
            self.assertTrue(site_data["readiness"]["acceptance_ready"])
            self.assertEqual(site_data["readiness"]["sample_class"], "acceptance_sample")
            self.assertEqual(site_data["readiness"]["counts"]["products"], 30)
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

            result = self.run_renderer(report_dir, "--no-recover")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("data readiness failed before final rendering after recovery", result.stderr + result.stdout)
            self.assertIn("diagnostic written", result.stderr + result.stdout)
            readiness_path = report_dir / "data" / "normalized" / "data_readiness_report.json"
            self.assertTrue(readiness_path.exists())
            readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
            self.assertFalse(readiness["acceptance_ready"])
            self.assertEqual(readiness["sample_class"], "non_acceptance_sample")

    def test_renderer_writes_partial_report_when_only_1688_quotes_are_under_50(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_renderable_report(report_dir)
            data_pack_path = report_dir / "data" / "data_pack.json"
            data_pack = json.loads(data_pack_path.read_text(encoding="utf-8"))
            data_pack["suppliers"] = supplier_rows(9)
            write_json(data_pack_path, data_pack)

            result = self.run_renderer(report_dir, "--no-recover")

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            readiness = json.loads((report_dir / "data" / "normalized" / "data_readiness_report.json").read_text(encoding="utf-8"))
            self.assertFalse(readiness["acceptance_ready"])
            self.assertTrue(readiness["partial_report_ready"])
            self.assertTrue(readiness["supply_conclusion_blocked"])
            self.assertEqual(readiness["supplier_quote_gate"]["actual"], 9)
            self.assertEqual(readiness["supplier_quote_gate"]["required"], 50)
            delivery = json.loads((report_dir / "output" / "delivery_result.json").read_text(encoding="utf-8"))
            self.assertEqual(delivery["status"], "partial")
            self.assertTrue(delivery["data_readiness"]["partial_report_ready"])

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

    def test_competitor_renderer_filters_off_target_noise(self):
        data_pack = {
            "products": [
                {
                    "asin": "B0LIGHT001",
                    "title": "Under Cabinet Motion Sensor Light Rechargeable LED",
                    "brand": "MCGOR",
                    "segment_cn": "橱柜感应灯",
                    "price": 17.97,
                    "rating": 4.5,
                    "review_count": 1200,
                    "estimated_monthly_sales": 64553,
                },
                {
                    "asin": "B0CAMERA01",
                    "title": "Ring Video Doorbell Security Camera with Motion Recording",
                    "brand": "Ring",
                    "segment_cn": "未分层",
                    "price": 99.99,
                    "rating": 4.5,
                    "review_count": 7041,
                    "estimated_monthly_sales": 30780,
                },
                {
                    "asin": "B0PROTEIN1",
                    "title": "Premier Protein Shake Chocolate 12 Pack",
                    "brand": "Premier Protein",
                    "segment_cn": "未分层",
                    "price": 31.98,
                    "rating": 4.6,
                    "review_count": 58142,
                    "estimated_monthly_sales": 705547,
                },
                {
                    "asin": "B0DRINK001",
                    "title": "CELSIUS Energy Drink Variety Pack",
                    "brand": "CELSIUS",
                    "segment_cn": "未分层",
                    "price": 21.48,
                    "rating": 4.6,
                    "review_count": 27362,
                    "estimated_monthly_sales": 442854,
                },
            ]
        }

        table_html, cards_html, filtered = renderer.render_competitors(data_pack)
        deep_html = renderer.render_product_deep_dives(filtered, [])

        combined = table_html + cards_html + deep_html
        self.assertEqual([product["asin"] for product in filtered], ["B0LIGHT001"])
        self.assertIn("MCGOR", combined)
        self.assertIn("橱柜感应灯", combined)
        self.assertNotIn("Premier Protein", combined)
        self.assertNotIn("CELSIUS", combined)
        self.assertNotIn("B0CAMERA01", combined)
        self.assertNotIn("Security Camera", combined)
        self.assertNotIn("未分层", combined)

    def test_deep_dive_traffic_tags_are_customer_mapped_and_deduped(self):
        products = [
            {
                "asin": "B0LIGHT001",
                "title": "Under Cabinet Motion Sensor Light Rechargeable LED",
                "brand": "MCGOR",
                "segment_cn": "橱柜感应灯",
                "price": 17.97,
                "rating": 4.5,
                "review_count": 1200,
                "estimated_monthly_sales": 64553,
            }
        ]
        keywords = [
            {"asin": "B0LIGHT001", "keyword": "under cabinet lighting", "monthly_search_volume": 1000},
            {"asin": "B0LIGHT001", "keyword": "kitchen cabinet lights", "keyword_cn": "未映射关键词：kitchen cabinet lights", "monthly_search_volume": 900},
            {"asin": "B0LIGHT001", "keyword": "ring camera", "monthly_search_volume": 800},
            {"asin": "B0LIGHT001", "keyword": "motion sensor light", "monthly_search_volume": 700},
            {"asin": "B0LIGHT001", "keyword": "flashlight", "keyword_cn": "未映射关键词：flashlight", "monthly_search_volume": 600},
        ]

        html = renderer.render_product_deep_dives(products, keywords)

        self.assertIn("橱柜灯", html)
        self.assertIn("感应灯", html)
        self.assertIn("户外便携灯", html)
        self.assertNotIn("under cabinet lighting", html)
        self.assertNotIn("kitchen cabinet lights", html)
        self.assertNotIn("ring camera", html)
        self.assertNotIn("未映射关键词", html)
        self.assertNotIn("定位标签：<span", html)

    def test_supply_uses_passing_segment_bucket_when_global_prices_are_mixed(self):
        products = competitor_rows(30)
        stable_suppliers = [
            {
                "title": f"厨房橱柜感应灯工厂款 {idx}",
                "supplier_name": f"中山供应商 {idx}",
                "url": f"https://detail.1688.com/offer/light-{idx}.html",
                "price_rmb": 10 + (idx % 5),
                "sales_30d": 300 + idx,
                "shipping_origin": "广东中山",
                "seed_keyword": "橱柜灯",
            }
            for idx in range(55)
        ]
        mixed_outliers = [
            {
                "title": f"大型户外工程灯具 {idx}",
                "supplier_name": f"工程灯供应商 {idx}",
                "url": f"https://detail.1688.com/offer/outdoor-{idx}.html",
                "price_rmb": 1200 + idx * 100,
                "sales_30d": 20 + idx,
                "shipping_origin": "广东",
                "seed_keyword": "工程灯",
            }
            for idx in range(8)
        ]
        data_pack = {"products": products, "suppliers": stable_suppliers + mixed_outliers}

        html = renderer.render_supply(data_pack, {})

        self.assertIn("参考竞品 ASIN", html)
        self.assertIn("1688 成本分位数", html)
        self.assertIn("测算口径", html)
        self.assertIn("橱柜灯", html)
        self.assertNotIn("需补采", html)
        self.assertNotIn("当前数据不能进入毛利率测算", html)

    def test_index_and_market_kpis_are_customer_ready_without_internal_status_or_empty_values(self):
        products = [
            {
                "asin": "B0LIGHT0001",
                "title": "Under Cabinet Motion Sensor Light Rechargeable",
                "brand": "MCGOR",
                "segment_cn": "橱柜感应灯",
                "price": 10,
                "estimated_monthly_sales": 12000,
                "rating": 4.5,
                "review_count": 1000,
            },
            {
                "asin": "B0LIGHT0002",
                "title": "RGBIC LED Strip Lights Smart App Control",
                "brand": "Govee",
                "segment_cn": "RGB 灯带",
                "price": 20,
                "estimated_monthly_sales": 24000,
                "rating": 4.6,
                "review_count": 3000,
            },
        ]
        data_pack = {
            "quality": {"grade": "collection_in_progress", "overall_score": 0.62},
            "products": products,
            "categories": [{}],
            "sources": [{"source_id": "src_001"}],
        }

        index_html = renderer.render_index_cards("smart lighting", "Watch", data_pack)
        market_html = renderer.render_market(data_pack, {})
        combined = index_html + market_html

        self.assertNotIn("collection_in_progress", combined)
        self.assertNotIn("score 0.62", combined)
        self.assertNotIn('<div class="kpi-value">-</div>', combined)
        self.assertIn("36,000", market_html)
        self.assertIn("$600,000", market_html)

    def test_supply_filters_non_finished_goods_before_margin_and_supplier_table(self):
        products = [
            {
                "asin": f"B0RGB{idx:05d}",
                "title": f"RGBIC LED Strip Lights Smart App Control {idx}",
                "brand": "Govee",
                "segment_cn": "RGB 灯带",
                "price": 19 + idx,
                "estimated_monthly_sales": 3000 + idx,
                "rating": 4.4,
                "review_count": 500 + idx,
            }
            for idx in range(30)
        ]
        finished_suppliers = [
            {
                "title": f"智能RGB灯带套装 成品带遥控器 {idx}",
                "supplier_name": f"中山成品灯带厂 {idx}",
                "url": f"https://detail.1688.com/offer/strip-{idx}.html",
                "price_rmb": 12 + idx % 4,
                "sales_30d": 200 + idx,
                "shipping_origin": "广东中山",
                "seed_keyword": "RGB灯带",
            }
            for idx in range(55)
        ]
        component_suppliers = [
            {
                "title": f"LED灯珠 发光二极管 光源配件 {idx}",
                "supplier_name": f"灯珠配件厂 {idx}",
                "url": f"https://detail.1688.com/offer/bead-{idx}.html",
                "price_rmb": 0.05,
                "sales_30d": 5000 + idx,
                "shipping_origin": "广东深圳",
                "seed_keyword": "RGB灯带",
            }
            for idx in range(20)
        ]

        html = renderer.render_supply({"products": products, "suppliers": finished_suppliers + component_suppliers}, {})

        self.assertIn("竞品参考毛利率测算", html)
        self.assertNotIn("LED灯珠", html)
        self.assertNotIn("发光二极管", html)
        self.assertNotIn("¥0.05", html)

    def test_market_pricing_and_prompt_sections_always_render_three_cards(self):
        opportunity = {
            "opportunities": [
                {
                    "name": "橱柜感应灯 高溢价主力款",
                    "price_band": "$39-$59",
                    "decision": "Watch",
                    "entry_shape": "围绕安装、续航和感应稳定性做主力款验证。",
                }
            ]
        }

        pricing_html = renderer.render_opportunities(opportunity)
        prompt_html = renderer.render_visual_direction(opportunity)

        self.assertEqual(pricing_html.count('class="pricing-card'), 3)
        self.assertEqual(prompt_html.count('class="prompt-card'), 3)
        self.assertIn("Starter", pricing_html)
        self.assertIn("Core", pricing_html)
        self.assertIn("Premium", pricing_html)
        self.assertIn('id="pricing"', pricing_html)
        self.assertIn("Prompt 01", prompt_html)
        self.assertIn("Prompt 02", prompt_html)
        self.assertIn("Prompt 03", prompt_html)
        self.assertIn('id="prompt"', prompt_html)
        self.assertNotIn("清洗数据", pricing_html + prompt_html)
        self.assertNotIn("清洗后", pricing_html + prompt_html)

    def test_market_visual_and_prompt_template_slots_match_reference_structure(self):
        html = renderer.render_visual_direction({"opportunities": [{"name": "橱柜感应灯 场景化主图"}]})

        self.assertEqual(html.count('class="visual-card"'), 2)
        self.assertEqual(html.count('class="prompt-card"'), 3)
        self.assertLess(html.find("visual-grid"), html.find("prompt-grid"))
        self.assertIn("📸 主图风格差异化建议", html)
        self.assertIn("📦 开箱体验差异化设计", html)
        self.assertIn("AI生图 Prompt · 可直接使用", html)
        for text in ["Prompt 01", "Prompt 02", "Prompt 03"]:
            self.assertIn(text, html)

    def test_market_supply_uses_reference_order_and_no_free_floating_cost_metrics(self):
        products = competitor_rows(30)
        suppliers = [
            {
                "title": f"成品橱柜感应灯套装 {idx}",
                "supplier_name": f"成品供应商 {idx}",
                "url": f"https://detail.1688.com/offer/finished-{idx}.html",
                "price_rmb": 18 + idx,
                "sales_30d": 1000 + idx,
                "shipping_origin": "广东中山",
                "seed_keyword": "橱柜感应灯",
            }
            for idx in range(60)
        ]

        html = renderer.render_supply({"products": products, "suppliers": suppliers}, {})

        self.assertEqual(html.count('class="supply-card'), 4)
        self.assertLess(html.find("supply-grid"), html.find('id="marginChart"'))
        self.assertLess(html.find('id="marginChart"'), html.find("profitability-table"))
        self.assertNotIn("metric-strip", html)
        self.assertNotIn("P25采购成本", html)
        self.assertIn("1688 成本分位数", html)
        self.assertIn("供应链核心结论", html)

    def test_market_dashboard_copy_uses_customer_ready_data_terms(self):
        html = renderer.render_market({"products": competitor_rows(30), "categories": [{}]}, {})

        self.assertNotIn("清洗数据", html)
        self.assertNotIn("清洗后", html)
        self.assertIn("已验证数据", html)

    def test_competitor_table_exposes_asin_for_customer_benchmarking(self):
        table_html, _cards_html, _filtered = renderer.render_competitors({"products": competitor_rows(30)})

        self.assertIn("<th>ASIN</th>", table_html)
        self.assertIn('data-allow-asin="competitor-table"', table_html)
        self.assertRegex(table_html, r"B0P\d{7}")

    def test_lifecycle_default_skus_are_segment_bound_real_sku_strategy(self):
        products = [
            {
                "asin": "B0CABINET01",
                "title": "Under Cabinet Motion Sensor Light Rechargeable LED",
                "brand": "MCGOR",
                "segment_cn": "橱柜感应灯",
                "price": 17.97,
                "estimated_monthly_sales": 64553,
                "rating": 4.5,
                "review_count": 56202,
            },
            {
                "asin": "B0RGB00001",
                "title": "RGBIC LED Strip Lights Smart App Control",
                "brand": "Govee",
                "segment_cn": "RGB 灯带",
                "price": 24.99,
                "estimated_monthly_sales": 20108,
                "rating": 4.4,
                "review_count": 24974,
            },
            {
                "asin": "B0OUTDOOR1",
                "title": "Outdoor Solar Motion Sensor Wall Lights",
                "brand": "HMCITY",
                "segment_cn": "户外感应灯",
                "price": 29.99,
                "estimated_monthly_sales": 18013,
                "rating": 4.4,
                "review_count": 13820,
            },
        ]
        suppliers = [
            {
                "title": "无线磁吸感应灯 成品套装",
                "supplier_name": "中山灯具厂",
                "price_rmb": 18.5,
                "seed_keyword": "无线磁吸感应灯",
            }
        ]

        skus = renderer.lifecycle_skus({"products": products, "suppliers": suppliers}, {}, "src_001")
        html = renderer.render_sku_execution_table(skus, "src_001")
        names = " ".join(str(sku.get("name")) for sku in skus)

        self.assertIn("橱柜感应灯", names)
        self.assertIn("RGB 灯带", names)
        self.assertIn("户外感应灯", names)
        self.assertIn("MCGOR 橱柜感应灯", html)
        self.assertIn("Govee RGB 灯带", html)
        self.assertIn('data-allow-asin="sku-reference">B0CABINET01</span>', html)
        self.assertNotIn("参考竞品 MCGOR 参考竞品", html)
        self.assertNotIn("备用与替换核心配件", names)
        self.assertNotIn("信任说明卡", names)
        self.assertNotIn("1688 相似供应端机会", names)

    def test_lifecycle_sku_section_renders_strategy_cards_before_table(self):
        skus = [
            {
                "name": "橱柜感应灯 基础款",
                "stage": "首发验证",
                "type": "A",
                "price": "$17.99",
                "supply": "1688 成品报价复核",
                "phase": "P1",
                "priority": 88,
                "pain": "解决安装固定和夜间感应痛点",
                "target_segment": "橱柜感应灯",
                "reference_competitor": "MCGOR B0CABINET01",
            }
        ]

        html = renderer.render_sku_execution_table(skus, "src_001")

        self.assertIn("sku-strategy-grid", html)
        self.assertIn("sku-strategy-card", html)
        self.assertEqual(html.count('class="sku-strategy-card'), 5)
        self.assertIn("目标赛道", html)
        self.assertIn("参考竞品", html)
        self.assertIn("MCGOR 橱柜感应灯", html)
        self.assertNotIn("B0CABINET01", html)
        for slot_name in ["橱柜感应灯 基础款", "升级款", "套装款", "配件款", "复购耗材"]:
            self.assertIn(slot_name, html)
        self.assertLess(html.find("sku-strategy-grid"), html.find("sku-table-wrap"))

    def test_lifecycle_ecosystem_uses_two_chart_reference_layout(self):
        skus = [
            {"name": "橱柜感应灯 基础款", "type": "A", "priority": 92},
            {"name": "RGB 灯带 升级款", "type": "B", "priority": 86},
            {"name": "户外感应灯 配件款", "type": "C", "priority": 74},
            {"name": "智能灯泡 维护款", "type": "D", "priority": 68},
        ]

        html = renderer.render_ecosystem({}, skus, "src_001")
        sku_html = renderer.render_sku_execution_table(skus, "src_001")

        self.assertIn("四维拓品生态 · 4D Ecosystem", html)
        self.assertIn('id="sunburst"', html)
        self.assertIn('id="priorityChart"', html)
        self.assertEqual(html.count("chart-container"), 2)
        self.assertNotIn('id="priorityChart"', sku_html)

    def test_lifecycle_strategy_dashboard_uses_customer_supply_risk_metric(self):
        data_pack = {
            "products": [
                {
                    "asin": "B0CABINET01",
                    "title": "Under Cabinet Motion Sensor Light Rechargeable LED",
                    "brand": "MCGOR",
                    "segment_cn": "橱柜感应灯",
                    "price": 17.97,
                    "estimated_monthly_sales": 64553,
                    "rating": 4.5,
                    "review_count": 56202,
                }
            ],
            "suppliers": [
                {
                    "title": "无线磁吸感应灯 成品套装",
                    "supplier_name": "中山灯具厂",
                    "price_rmb": 18.5,
                    "seed_keyword": "无线磁吸感应灯",
                }
            ],
        }

        html = renderer.render_strategy_dashboard(data_pack, {}, "src_001")

        self.assertIn("供应链可控度", html)
        self.assertIn("供应链风险", html)
        self.assertNotIn("可自产 SKU", html)
        self.assertNotIn('<div class="kpi-value">0</div>', html)

    def test_lifecycle_evidence_tables_are_collapsed_drawers(self):
        html = renderer.render_lifecycle_journey({}, "src_001")

        self.assertIn("lifecycle-evidence-drawer", html)
        self.assertIn("<summary>生命周期旅程证据表</summary>", html)
        self.assertLess(html.find("timeline-grid"), html.find("lifecycle-evidence-drawer"))

    def test_lifecycle_roadmap_uses_six_reference_phase_slots(self):
        html = renderer.render_lifecycle_roadmap([], "src_001")

        self.assertIn("roadmap-phase-grid", html)
        self.assertIn("roadmap-action-grid", html)
        self.assertEqual(html.count('class="phase-card'), 6)
        self.assertIn("30 天行动清单", html)
        self.assertIn("60 天行动清单", html)
        self.assertIn("90 天行动清单", html)

    def test_lifecycle_bundle_strategy_matches_reference_order(self):
        html = renderer.render_bundle_strategy([], "src_001")

        self.assertEqual(html.count('class="bundle-card'), 4)
        self.assertLess(html.find("bundle-grid"), html.find('id="aovChart"'))
        self.assertLess(html.find('id="aovChart"'), html.find("Bundle 策略核心"))
        for text in ["新手启航套装", "豪华礼品套装", "STEM 探索套装", "续航补给包"]:
            self.assertIn(text, html)
        for cls in ["bundle-header", "bundle-target", "bundle-items", "bundle-pricing", "orig", "final", "save"]:
            self.assertIn(cls, html)
        self.assertIn("insight-box", html)
        self.assertNotIn("source_id:", html)

    def test_lifecycle_sku_table_uses_seven_reference_filters(self):
        html = renderer.render_sku_execution_table([], "src_001")

        self.assertEqual(html.count('class="filter-btn'), 7)
        self.assertIn('data-filter="ext"', html)
        self.assertIn('data-filter="P1"', html)
        self.assertIn("供应链验证", html)
        self.assertIn("P1 立即启动", html)

    def test_report_css_caps_prompt_card_height_for_pc_layout(self):
        from site_assets import REPORT_CSS

        self.assertIn(".prompt-card", REPORT_CSS)
        self.assertIn(".pricing-card.recommended::before", REPORT_CSS)
        self.assertIn(".visual-item:last-child", REPORT_CSS)
        self.assertIn(".prompt-card::before", REPORT_CSS)
        self.assertIn(".template-market .supply-grid", REPORT_CSS)
        self.assertRegex(REPORT_CSS, r"\.prompt-card\{[^}]*max-height:")
        self.assertRegex(REPORT_CSS, r"\.prompt-text\{[^}]*line-clamp:")
        self.assertRegex(REPORT_CSS, r"\.demand-evidence-grid\{[^}]*repeat\(2")
        self.assertIn(".template-demand .demand-evidence-card .quote-cn", REPORT_CSS)
        self.assertIn(".template-index .kpi-card .kpi-value", REPORT_CSS)
        self.assertIn(".template-index .metric-tag b", REPORT_CSS)
        self.assertIn(".sku-strategy-grid", REPORT_CSS)
        self.assertIn(".lifecycle-evidence-drawer", REPORT_CSS)
        self.assertIn(".template-demand.mode-r3 .section-number{display:none}", REPORT_CSS)
        self.assertIn(".demand-brief-stack{display:grid", REPORT_CSS)
        self.assertNotIn(".demand-anchor-grid", REPORT_CSS)
        self.assertIn("table.sku th:nth-child(5),table.sku td:nth-child(5)", REPORT_CSS)
        self.assertIn(".market-voc-sentiment-columns", REPORT_CSS)
        self.assertIn(".market-voc-column{display:grid", REPORT_CSS)
        self.assertIn(".market-voc-card.joy", REPORT_CSS)
        self.assertIn(".market-voc-card.pain", REPORT_CSS)

    def test_market_voc_splits_positive_left_and_negative_right(self):
        reviews = []
        for idx in range(8):
            reviews.append(
                {
                    "rating": 5,
                    "title": f"Great lighting {idx}",
                    "text": "Great under cabinet light, easy to install, bright and motion sensor works well.",
                    "themes": ["installation", "brightness"],
                }
            )
            reviews.append(
                {
                    "rating": 2,
                    "title": f"Poor battery {idx}",
                    "text": "Battery stopped charging and adhesive fell off after a few days.",
                    "themes": ["battery", "adhesive"],
                }
            )

        html = renderer.render_voc({"reviews": reviews}, {})

        self.assertIn("market-voc-sentiment-columns", html)
        self.assertIn("正面好评", html)
        self.assertIn("负面差评", html)
        self.assertLess(html.find("正面好评"), html.find("负面差评"))
        self.assertNotIn('class="quote-grid"', html)
        positive_section = html.split("负面差评", 1)[0]
        negative_section = html.split("负面差评", 1)[1].split("</section>", 1)[0]
        self.assertEqual(positive_section.count("market-voc-card joy"), 6)
        self.assertEqual(negative_section.count("market-voc-card pain"), 6)

    def test_demand_target_anchor_keeps_reference_section_clean(self):
        data_pack = {
            "products": [
                {
                    "asin": "B0CABINET01",
                    "title": "Under Cabinet Motion Sensor Light",
                    "title_cn": "MCGOR 橱柜感应灯",
                    "brand": "MCGOR",
                    "price": 21.99,
                    "rating": 4.5,
                    "review_count": 56829,
                    "estimated_monthly_sales": 53146,
                    "source_id": "src_001",
                }
            ],
            "reviews": [{"rating": 5}],
            "keywords": [{"keyword": "under cabinet lights"}],
        }

        html = renderer.render_target_anchor(data_pack, "smart lighting", "src_001")

        self.assertIn("当前研究对象", html)
        self.assertIn("分析口径", html)
        self.assertIn("参考竞品ASIN", html)
        self.assertIn('data-allow-asin="demand-target-anchor">B0CABINET01</span>', html)
        self.assertIn("MCGOR 橱柜感应灯", html)
        self.assertIn("53,146/月", html)
        self.assertNotIn("demand-anchor-grid", html)
        self.assertNotIn("kpi-card", html)
        self.assertNotIn("<details", html)

    def test_demand_decision_board_owns_kpis_and_collapses_evidence(self):
        data_pack = {
            "products": [{"asin": "B0CABINET01"}],
            "reviews": [{"rating": 2}, {"rating": 5}],
            "sources": [{"source_id": "src_001"}],
        }
        demand_gap = {"opportunities": [{"pain": "续航与充电"}]}

        html = renderer.render_decision_board(data_pack, demand_gap, "Watch", "src_001")

        self.assertEqual(html.count('class="kpi"'), 4)
        self.assertIn("<summary>决策看板证据表</summary>", html)
        self.assertIn("evidence-drawer", html)
        self.assertNotIn("<h3>决策看板证据表</h3>", html)

    def test_demand_voice_theater_renders_evidence_opportunity_cards(self):
        data_pack = {
            "reviews": [
                {
                    "rating": 2,
                    "title": "Adhesive failed",
                    "text": "The adhesive fell off after two days and motion sensor misses at night.",
                    "themes": ["installation", "motion sensor"],
                },
                {
                    "rating": 5,
                    "title": "Easy install",
                    "text": "Easy to install and bright under cabinet light.",
                    "themes": ["installation", "brightness"],
                },
            ]
        }

        html = renderer.render_voice_theater(data_pack, "src_001")

        self.assertIn("demand-evidence-grid", html)
        self.assertIn("demand-evidence-card", html)
        self.assertIn("英文评论短摘", html)
        self.assertIn("中文洞察", html)
        self.assertIn("需求强度", html)
        self.assertIn("竞品未满足点", html)
        self.assertIn("可落地产品机会", html)
        self.assertIn('data-allow-english-review="short"', html)
        self.assertIn("adhesive fell off", html)
        self.assertIn("安装", html)
        self.assertNotIn('style="margin:0"', html)

    def test_demand_voice_theater_splits_positive_left_and_negative_right(self):
        reviews = []
        for idx in range(8):
            reviews.append(
                {
                    "rating": 5,
                    "title": f"Great install {idx}",
                    "text": "Great lights, easy to install, motion sensor works well under cabinet.",
                    "themes": ["installation", "motion sensor"],
                }
            )
            reviews.append(
                {
                    "rating": 2,
                    "title": f"Poor battery {idx}",
                    "text": "Battery stopped charging and adhesive fell off after a few days.",
                    "themes": ["battery", "adhesive"],
                }
            )

        html = renderer.render_voice_theater({"reviews": reviews}, "src_001")

        self.assertIn("demand-sentiment-columns", html)
        self.assertIn("正面反馈", html)
        self.assertIn("负面反馈", html)
        self.assertIn("用户原声证据明细表", html)
        self.assertIn("evidence-drawer", html)
        self.assertNotIn("需补齐证据", html)
        self.assertLess(html.find("正面反馈"), html.find("负面反馈"))
        positive_section = html.split("负面反馈", 1)[0]
        negative_section = html.split("负面反馈", 1)[1].split("</div></div>", 1)[0]
        self.assertEqual(positive_section.count("demand-evidence-card joy"), 6)
        self.assertEqual(negative_section.count("demand-evidence-card pain"), 6)

    def test_demand_voice_theater_prioritizes_product_relevant_reviews(self):
        data_pack = {
            "products": [
                {
                    "asin": "B0CABINET01",
                    "title": "Under Cabinet Motion Sensor Light Rechargeable",
                    "title_cn": "橱柜感应灯",
                    "segment_cn": "橱柜感应灯",
                },
                {
                    "asin": "B0CAMERA001",
                    "title": "Ring Outdoor Cam Plus security camera video service",
                    "title_cn": "户外安防摄像头",
                    "segment_cn": "户外安防摄像头",
                },
            ],
            "reviews": [
                {
                    "asin": "B0CAMERA001",
                    "rating": 1,
                    "title": "Ring service failed",
                    "text": "This Ring camera service and video recording subscription stopped working.",
                    "themes": ["service"],
                },
                {
                    "asin": "B0CABINET01",
                    "rating": 2,
                    "title": "Motion light adhesive failed",
                    "text": "The under cabinet light adhesive fell off and motion sensor misses at night.",
                    "themes": ["installation_mounting", "performance"],
                },
            ],
        }

        html = renderer.render_voice_theater(data_pack, "src_001")
        first_card = html.split("demand-evidence-card", 1)[1]

        self.assertIn("under cabinet light adhesive", first_card)
        self.assertNotIn("Ring camera service", first_card[:700])


if __name__ == "__main__":
    unittest.main()
