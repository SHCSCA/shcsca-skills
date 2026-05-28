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


def child_html(style, title, sections, extra_terms=""):
    section_html = "\n".join(
        f'<section id="{slug}"><span class="section-number">{idx:02d}</span><h2>{name}</h2>'
        f'<div class="chart-container"><div class="mini-chart"></div></div>'
        f'<table class="evidence-table insight-table"><tr><th>结论</th><th>证据强度</th><th>商业含义</th><th>建议动作</th></tr>'
        f'<tr><td>{name}</td><td>高</td><td>样本覆盖足以支撑方向判断</td><td>优先转成页面卖点和打样清单</td></tr></table></section>'
        for idx, (slug, name) in enumerate(sections, 1)
    )
    return f"""<!doctype html>
<html lang="zh-CN" data-report-style="{style}">
<head><meta charset="utf-8"><style>.report-header{{}}.kpi-grid{{}}.section-number{{}}.evidence-table{{}}.insight-table{{}}.chart-container{{}}.mini-chart{{}}.insight-box{{}}.conclusion{{}}.deep-dive-grid{{}}.comp-deep-card{{}}.opportunity-matrix{{}}</style></head>
<body>
<header class="report-header"><h1>{title}</h1><div class="kpi-grid"><article>Go / Watch / No-Go</article><article>证据强度：高</article><article>样本覆盖：充分</article><article>数据缺口：已标注</article></div></header>
<main>
<div class="insight-box">客户版 AI 深度分析报告：先给判断，再给原因，最后给建议动作。</div>
{section_html}
<section><div class="deep-dive-grid"><div class="comp-deep-card">标杆样本 · 溢价逻辑 · 未满足需求</div></div></section>
<section><div class="insight-box">置信等级：中高；样本覆盖与数据缺口已进入判断。</div><div class="conclusion">结论：优先执行高确定性动作。</div></section>
{extra_terms}
</main>
</body></html>"""


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
            "products": [{"asin": "B0TEST1234", "title": "AI Plush Toy", "source_id": "src_001", "provider": "sorftime"}],
            "keywords": [
                {"keyword": f"ai plush keyword {idx}", "source_id": "src_001", "provider": "sorftime"}
                for idx in range(1000)
            ],
            "categories": [{"node_id": "123", "source_id": "src_001", "provider": "sorftime"}],
            "reviews": [
                {
                    "asin": "B0TEST1234",
                    "title": "privacy issue",
                    "text": "This toy stopped working after two days and the privacy policy is confusing.",
                    "source_id": "src_001",
                    "provider": "sorftime",
                }
            ],
            "tiktok_products": [{"product_id": "tk_1", "source_id": "src_001", "provider": "sorftime"}],
            "tiktok_videos": [{"video_id": "v_1", "source_id": "src_001", "provider": "sorftime"}],
            "suppliers": [{"name": "supplier", "source_id": "src_001", "provider": "sorftime"}],
            "web_documents": [{"url": "https://example.com/report", "source_id": "src_002", "provider": "firecrawl"}],
            "data_gaps": ["Keepa not used in this run"],
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
<html lang="zh-CN" data-report-style="three-report-index-v2">
<head><meta charset="utf-8"><style>.report-index{}.report-card{}</style></head>
<body><main class="report-index">
<h1>三合一市场研究报告</h1>
<a href="html_reports/market-depth-report.html">市场深度调研报告</a>
<a href="html_reports/lifecycle-strategy-report.html">产品全生命周期拓品战略报告</a>
<a href="html_reports/demand-gap-report.html">用户心智断层与需求机会报告</a>
<p>Go / Watch / No-Go · 证据强度 · 样本覆盖 · 数据缺口 · 建议动作</p>
</main></body></html>""",
    )
    write_text(
        root / "output" / "html_reports" / "report.html",
        """<!doctype html>
<html lang="zh-CN" data-report-style="three-report-index-v2">
<head><meta charset="utf-8"><style>.report-index{}.report-card{}</style></head>
<body><main class="report-index">
<h1>三合一市场研究报告</h1>
<a href="market-depth-report.html">市场深度调研报告</a>
<a href="lifecycle-strategy-report.html">产品全生命周期拓品战略报告</a>
<a href="demand-gap-report.html">用户心智断层与需求机会报告</a>
<p>Go / Watch / No-Go · 证据强度 · 样本覆盖 · 数据缺口 · 建议动作</p>
</main></body></html>""",
    )
    write_text(
        root / "output" / "html_reports" / "market-depth-report.html",
        child_html(
            "market-depth-report-v2",
            "市场深度调研报告",
            [
                ("market-dashboard", "大盘结论"),
                ("keyword-demand", "需求结构"),
                ("competitor-landscape", "竞品格局"),
                ("voc", "VOC 洞察"),
                ("competitor-deep-dive", "标杆打法"),
                ("opportunity", "机会定义"),
                ("tiktok-validation", "TikTok 内容信号"),
                ("supply-chain", "1688 供应链判断"),
                ("web-risk", "风险与行动摘要"),
            ],
            "可进入性评分 价格带机会 竞争强度 关键切入口 商业含义",
        ),
    )
    write_text(
        root / "output" / "html_reports" / "lifecycle-strategy-report.html",
        child_html(
            "lifecycle-strategy-report-v2",
            "产品全生命周期拓品战略报告",
            [
                ("strategy-dashboard", "战略仪表盘"),
                ("personas", "用户画像"),
                ("lifecycle-journey", "生命周期旅程"),
                ("ecosystem", "四维拓品生态"),
                ("sku-table", "拓品方案池"),
                ("bundle-strategy", "Bundle 策略"),
                ("roadmap", "30/60/90 天路线图"),
                ("risk-matrix", "风险矩阵"),
                ("market-intelligence", "市场验证摘要"),
            ],
            "SKU Bundle 供应链 复购 AOV LTV",
        ),
    )
    write_text(
        root / "output" / "html_reports" / "demand-gap-report.html",
        child_html(
            "demand-gap-report-v2",
            "用户心智断层与需求机会报告",
            [
                ("target-anchor", "研究对象概述"),
                ("decision-board", "决策看板"),
                ("appeals-map", "$APPEALS 痛点图"),
                ("gap-analysis", "满意度鸿沟"),
                ("kano-jtbd", "KANO × JTBD"),
                ("voice-theater", "用户原声"),
                ("priority-table", "需求优先级"),
            ],
            "KANO JTBD 心智断层 负面触发点 转化机会",
        ),
    )
    write_json(
        root / "output" / "delivery_result.json",
        {
            "status": "complete",
            "formats": ["html", "markdown", "json"],
            "html_reports": {
                "index": "output/html_reports/report.html",
                "compat_index": "output/report.html",
                "market_depth": "output/html_reports/market-depth-report.html",
                "lifecycle_strategy": "output/html_reports/lifecycle-strategy-report.html",
                "demand_gap": "output/html_reports/demand-gap-report.html",
            },
            "html_bundle_dir": "output/html_reports",
        },
    )


class ValidateMarketResearchDeliverablesTest(unittest.TestCase):
    def run_validator(self, report_dir):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--dir", str(report_dir)],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_valid_three_report_bundle_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)

            result = self.run_validator(report_dir)

            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("validate_ok", result.stdout)

    def test_rejects_missing_child_html_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            (report_dir / "output" / "html_reports" / "demand-gap-report.html").unlink()

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("demand-gap-report.html", result.stderr + result.stdout)

    def test_rejects_index_without_child_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            html_path = report_dir / "output" / "html_reports" / "report.html"
            write_text(html_path, html_path.read_text(encoding="utf-8").replace("lifecycle-strategy-report.html", "lifecycle.html"))

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("lifecycle-strategy-report.html", result.stderr + result.stdout)

    def test_rejects_bundle_index_with_output_prefixed_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            html_path = report_dir / "output" / "html_reports" / "report.html"
            html_doc = html_path.read_text(encoding="utf-8").replace('href="market-depth-report.html"', 'href="output/market-depth-report.html"')
            write_text(html_path, html_doc)

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("same-folder relative links", result.stderr + result.stdout)

    def test_rejects_child_report_missing_required_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            html_path = report_dir / "output" / "html_reports" / "market-depth-report.html"
            write_text(html_path, html_path.read_text(encoding="utf-8").replace("TikTok 内容信号", "TikTok"))

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("TikTok 内容信号", result.stderr + result.stdout)

    def test_rejects_customer_html_leaking_technical_identifiers(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            html_path = report_dir / "output" / "html_reports" / "demand-gap-report.html"
            write_text(
                html_path,
                html_path.read_text(encoding="utf-8")
                + "<p>source_id src_001 Product ID product_id raw_path provider tool B0TEST1234 data/raw/file.json 来源</p>",
            )

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("customer HTML leaks technical identifier", result.stderr + result.stdout)

    def test_rejects_customer_html_without_analysis_terms(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            html_path = report_dir / "output" / "html_reports" / "market-depth-report.html"
            write_text(html_path, html_path.read_text(encoding="utf-8").replace("证据强度", "证据"))

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("证据强度", result.stderr + result.stdout)

    def test_rejects_raw_english_review_copied_into_customer_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            html_path = report_dir / "output" / "html_reports" / "demand-gap-report.html"
            write_text(
                html_path,
                html_path.read_text(encoding="utf-8")
                + "<p>This toy stopped working after two days and the privacy policy is confusing.</p>",
            )

            result = self.run_validator(report_dir)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("raw English review", result.stderr + result.stdout)

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

    def test_markdown_wrapped_child_html_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_valid_report(report_dir)
            write_text(
                report_dir / "output" / "html_reports" / "market-depth-report.html",
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
            self.assertIn("market-depth-report.html", result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
