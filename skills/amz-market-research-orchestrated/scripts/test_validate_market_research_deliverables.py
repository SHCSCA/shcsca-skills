#!/usr/bin/env python3
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("validate_market_research_deliverables.py")


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_valid_report(root):
    write_json(
        root / "data" / "data_pack.json",
        {
            "task_id": "ai_plush_us_20260526",
            "created_at": "2026-05-26T10:00:00+08:00",
            "sources": [
                {
                    "source_id": "src_001",
                    "provider": "sorftime",
                    "tool": "product_search",
                    "fetched_at": "2026-05-26T10:00:00+08:00",
                    "confidence": "medium",
                },
                {
                    "source_id": "src_002",
                    "provider": "firecrawl",
                    "tool": "firecrawl_search",
                    "fetched_at": "2026-05-26T10:01:00+08:00",
                    "confidence": "medium",
                },
            ],
            "products": [{"asin": "B0TEST1234", "source_id": "src_001", "provider": "sorftime"}],
            "keywords": [
                {"keyword": f"ai plush keyword {idx}", "source_id": "src_001", "provider": "sorftime"}
                for idx in range(1000)
            ],
            "categories": [{"node_id": "123", "source_id": "src_001", "provider": "sorftime"}],
            "reviews": [{"asin": "B0TEST1234", "text": "good", "source_id": "src_001", "provider": "sorftime"}],
            "tiktok_products": [{"product_id": "tk_1", "source_id": "src_001", "provider": "sorftime"}],
            "tiktok_videos": [{"video_id": "v_1", "source_id": "src_001", "provider": "sorftime"}],
            "suppliers": [{"name": "supplier", "source_id": "src_001", "provider": "sorftime"}],
            "web_documents": [{"url": "https://example.com/report", "source_id": "src_002", "provider": "firecrawl"}],
            "data_gaps": ["Keepa not used in v1"],
            "quality": {"overall_score": 0.82, "grade": "decision_grade"},
            "normalization": {
                "deduped": True,
                "before_counts": {"products": 1, "keywords": 1000},
                "after_counts": {"products": 1, "keywords": 1000},
                "removed_counts": {"products": 0, "keywords": 0},
                "cross_validated_counts": {"products": 0, "keywords": 0},
            },
        },
    )
    write_json(
        root / "analysis" / "analysis_plan.json",
        {
            "task_id": "ai_plush_us_20260526",
            "method_chain": [
                {
                    "method_id": "market.top100_competitor_scan",
                    "name": "Top100 competitor scan",
                    "used_source_ids": ["src_001"],
                    "output": "competitor matrix",
                },
                {
                    "method_id": "decision.go_watch_nogo",
                    "name": "Go / Watch / No-Go",
                    "used_source_ids": ["src_001", "src_002"],
                    "output": "Watch",
                },
            ],
            "confidence": {"final_decision": "medium"},
            "limitations": ["Sorftime estimates are not official Amazon sales."],
        },
    )
    write_text(root / "data" / "lineage.md", "# Data Lineage\n\n- src_001: Sorftime product_search\n- src_002: Firecrawl search\n")
    write_text(root / "output" / "report.md", "# Report\n\n估算月销量（Sorftime）来自 src_001。\n\n## Go / Watch / No-Go\nWatch\n")
    write_text(
        root / "output" / "report.html",
        """<!doctype html>
<html lang="zh-CN" data-report-style="strategic-dashboard-v1">
<head><meta charset="utf-8"><style>.report-header{}.kpi-grid{}.section-number{}.evidence-table{}.chart-container{}.insight-box{}.conclusion{}.comp-deep-card{}</style></head>
<body>
<header class="report-header"><h1>Report</h1></header>
<main>
  <section id="executive-dashboard"><span class="section-number">00</span>Go / Watch / No-Go src_001</section>
  <section id="data-coverage"><span class="section-number">01</span>数据覆盖 交叉验证 去重 <div class="chart-container"><div class="mini-chart"></div></div></section>
  <section id="market-dashboard"><span class="section-number">02</span>市场大盘</section>
  <section id="keyword-demand"><span class="section-number">03</span>关键词需求</section>
  <section id="competitor-landscape"><span class="section-number">04</span>Top 竞品</section>
  <section id="competitor-deep-dive"><span class="section-number">05</span>竞品深挖 <div class="deep-dive-grid"><div class="comp-deep-card"></div></div></section>
  <section id="voc"><span class="section-number">06</span>Review / VOC</section>
  <section id="tiktok-validation"><span class="section-number">07</span>TikTok 验证</section>
  <section id="supply-chain"><span class="section-number">08</span>1688 供应链</section>
  <section id="web-risk"><span class="section-number">09</span>Web / 风险补充</section>
  <section id="opportunity-matrix"><span class="section-number">10</span>机会矩阵</section>
  <section id="decision-roadmap"><span class="section-number">11</span>Go / Watch / No-Go</section>
  <section id="data-gaps"><span class="section-number">12</span>数据缺口</section>
  <section id="full-data-appendix"><span class="section-number">13</span>完整数据附录 <table class="evidence-table appendix-table"><tr><td>src_001</td></tr></table></section>
  <section id="lineage"><span class="section-number">14</span>数据血缘</section>
  <div class="kpi-grid"><article>估算月销量（Sorftime）</article></div>
  <div class="conclusion"><div class="insight-box">结论</div></div>
  <table class="evidence-table"><tr><th>关键词中文</th><th>英文关键词</th><th>相关性</th><th>中文定位</th><th>英文标题</th></tr><tr><td>AI 毛绒</td><td>ai plush</td><td>高相关</td><td>智能玩具</td><td>AI Plush Toy</td></tr></table>
  <table class="evidence-table"><tr><td>src_001</td></tr></table>
  <table class="evidence-table"><tr><td>1</td></tr></table>
  <table class="evidence-table"><tr><td>2</td></tr></table>
  <table class="evidence-table"><tr><td>3</td></tr></table>
  <table class="evidence-table"><tr><td>4</td></tr></table>
  <table class="evidence-table"><tr><td>5</td></tr></table>
  <table class="evidence-table"><tr><td>6</td></tr></table>
  <table class="evidence-table"><tr><td>7</td></tr></table>
  <table class="evidence-table"><tr><td>8</td></tr></table>
  <table class="evidence-table"><tr><td>9</td></tr></table>
  <details><summary>关键词</summary>detail</details>
  <details><summary>评论</summary>detail</details>
  <details><summary>来源</summary>detail</details>
</main>
</body></html>""",
    )
    write_json(root / "output" / "delivery_result.json", {"status": "complete", "formats": ["html", "markdown", "json"]})


class ValidateMarketResearchDeliverablesTest(unittest.TestCase):
    def run_validator(self, report_dir):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--dir", str(report_dir)],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_valid_report_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)

            result = self.run_validator(report_dir)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("validate_ok", result.stdout)

    def test_rejects_keyword_samples_below_1000(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            data_pack_path = report_dir / "data" / "data_pack.json"
            data_pack = json.loads(data_pack_path.read_text(encoding="utf-8"))
            data_pack["keywords"] = data_pack["keywords"][:999]
            data_pack["normalization"]["after_counts"]["keywords"] = 999
            write_json(data_pack_path, data_pack)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("at least 1000", result.stderr + result.stdout)

    def test_entity_without_source_id_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            data_pack_path = report_dir / "data" / "data_pack.json"
            data_pack = json.loads(data_pack_path.read_text(encoding="utf-8"))
            del data_pack["products"][0]["source_id"]
            write_json(data_pack_path, data_pack)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("source_id", result.stderr + result.stdout)

    def test_missing_delivery_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            (report_dir / "output" / "delivery_result.json").unlink()

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("delivery_result.json", result.stderr + result.stdout)

    def test_markdown_wrapped_html_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            write_text(
                report_dir / "output" / "report.html",
                """<!doctype html><html><body><pre># Report

| 关键词 | 月销量 |
|---|---:|
| test | 10 |

## Go / Watch / No-Go
估算月销量（Sorftime）来自 src_001。
</pre></body></html>""",
            )

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("strategic-dashboard-v1", result.stderr + result.stdout)

    def test_html_missing_required_dashboard_section_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            html_path = report_dir / "output" / "report.html"
            report_html = html_path.read_text(encoding="utf-8").replace("TikTok 验证", "TikTok")
            write_text(html_path, report_html)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("TikTok 验证", result.stderr + result.stdout)

    def test_html_missing_full_data_appendix_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            html_path = report_dir / "output" / "report.html"
            report_html = html_path.read_text(encoding="utf-8").replace("完整数据附录", "数据附录")
            write_text(html_path, report_html)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("完整数据附录", result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
