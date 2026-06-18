#!/usr/bin/env python3
import json
import re
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import check_data_readiness
import report_renderers
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


def competitor_rows(count=30, include_images=False):
    segments = ["智能陪伴玩具", "语音互动玩具", "儿童礼品玩具"]
    rows = [
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
    if include_images:
        for idx, row in enumerate(rows):
            row["main_image_url"] = f"https://m.media-amazon.com/images/I/test-competitor-{idx}.jpg"
    return rows


def make_renderable_report(root):
    keywords = [
        {
            "keyword": f"ai plush toy {idx}" if idx >= 5 else f"robot companion {idx}",
            "keyword_cn": f"AI毛绒玩具 {idx}" if idx >= 5 else f"机器人陪伴玩具 {idx}",
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
            "products": competitor_rows(30, include_images=True),
            "keywords": keywords,
            "categories": [{"node_id": "123", "name": "Plush Toys", "top100_estimated_monthly_units": 10000, "source_id": "src_001", "provider": "sorftime"}],
            "reviews": [
                {
                    "asin": "B0P0000000",
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

    def test_market_template_keeps_cosmo_section_before_competitor_scan(self):
        template = (SCRIPT.parent.parent / "assets" / "market-depth-template.html").read_text(encoding="utf-8")
        market_pos = template.index('id="market-dashboard"')
        cosmo_pos = template.index('id="cosmo-alexa-tags"')
        competitor_pos = template.index('id="competitor-scan"')
        self.assertLess(market_pos, cosmo_pos)
        self.assertLess(cosmo_pos, competitor_pos)
        self.assertLess(template.index(">02<"), template.index(">03<"))

    def test_market_template_exposes_competitor_image_and_diagnostic_slot(self):
        template = (SCRIPT.parent.parent / "assets" / "market-depth-template.html").read_text(encoding="utf-8")
        competitor_pos = template.index('id="competitor-scan"')
        cards_pos = template.index("{{COMPETITOR_SEGMENT_CARDS}}")
        table_pos = template.index("{{COMPETITOR_TABLE}}")
        deep_dive_pos = template.index("{{COMPETITOR_DEEP_DIVES}}")

        self.assertLess(competitor_pos, cards_pos)
        self.assertLess(cards_pos, table_pos)
        self.assertLess(table_pos, deep_dive_pos)

    def test_competitor_renderer_shows_amazon_images_in_scan_and_deep_dive(self):
        data_pack = {
            "products": [
                {
                    "asin": "B0IMG00001",
                    "title": "Pop Up Hunting Blind See Through Ground Blind",
                    "title_cn": "透视弹出式地面盲棚",
                    "brand": "FUNHORUN",
                    "segment_cn": "透视地面盲棚",
                    "price": 87.98,
                    "rating": 4.5,
                    "review_count": 1087,
                    "estimated_monthly_sales": 349,
                    "main_image_url": "https://m.media-amazon.com/images/I/71example.jpg",
                }
            ]
        }

        table_html, cards_html, products = renderer.render_competitors(data_pack)
        deep_dive_html = renderer.render_product_deep_dives(products, [])

        self.assertIn('class="comp-image-thumb"', cards_html)
        self.assertIn('class="comp-product-thumb"', table_html)
        self.assertIn('class="comp-deep-image"', deep_dive_html)
        self.assertIn("https://m.media-amazon.com/images/I/71example.jpg", table_html + cards_html + deep_dive_html)
        self.assertNotIn("图片维度未返回可展示 URL", cards_html)

    def test_competitor_renderer_keeps_visible_image_diagnostic_when_images_missing(self):
        data_pack = {
            "products": [
                {
                    "asin": "B0NOIMAGE01",
                    "title": "Pop Up Hunting Blind",
                    "title_cn": "弹出式地面盲棚",
                    "brand": "FUNHORUN",
                    "segment_cn": "地面盲棚",
                    "price": 79.99,
                    "rating": 4.4,
                    "review_count": 900,
                    "estimated_monthly_sales": 320,
                }
            ]
        }

        _table_html, cards_html, _products = renderer.render_competitors(data_pack)

        self.assertIn("comp-image-diagnostic-card", cards_html)
        self.assertIn("图片维度未返回可展示 URL", cards_html)
        self.assertIn("采集层补齐商品主图链接", cards_html)

    def test_cosmo_renderer_exposes_all_relation_cards_with_tag_chips(self):
        data_pack = {
            "research_object": {"value": "hunting blinds"},
            "products": [
                {
                    "asin": "B0BR4QYGS7",
                    "title": "Pop Up Hunting Blind See Through Ground Blind",
                    "title_cn": "FUNHORUN 透视弹出式地面盲棚",
                    "brand": "FUNHORUN",
                    "segment_cn": "透视弹出式地面盲棚",
                    "price": 87.98,
                    "rating": 4.5,
                    "review_count": 1087,
                    "estimated_monthly_sales": 349,
                }
            ],
            "keywords": [
                {"keyword": "hunting blinds", "keyword_cn": "狩猎盲棚主词"},
                {"keyword": "deer blind", "keyword_cn": "鹿猎场景"},
                {"keyword": "turkey hunting blind", "keyword_cn": "火鸡狩猎场景"},
            ],
            "reviews": [
                {
                    "rating": 5,
                    "title": "easy to set up",
                    "text": "Easy to set up for deer hunting and keeps me concealed in the field.",
                    "theme_cn": "安装与隐蔽",
                }
            ],
            "suppliers": [
                {
                    "title": "跨境户外270度单向透视迷彩打猎狩猎帐篷",
                    "price_rmb": 168,
                    "seed_keyword": "狩猎盲棚",
                }
            ],
        }
        html = renderer.render_cosmo_alexa_tags(data_pack, {})
        self.assertEqual(html.count('data-cosmo-relation="'), 15)
        self.assertGreaterEqual(html.count('class="cosmo-tag-terms"'), 15)
        self.assertIn('data-cosmo-relation="P01"', html)
        self.assertIn('data-cosmo-relation="U09"', html)
        self.assertNotRegex(html, r"\b(?:USED_[A-Z_]+|CAPABLE_OF|IS_A|xWANT|xIs_A|xINTERSTED_IN)\b")
        self.assertNotIn(">USED_FOR_FUNC<", html)
        self.assertNotIn(">xWANT<", html)
        self.assertIn("功能·用途", html)
        self.assertIn("用户想要达成", html)
        self.assertIn("15 类意图关系", html)
        self.assertNotIn("relation types", html)

    def test_cosmo_renderer_uses_reference_style_four_zone_layout(self):
        data_pack = {
            "research_object": {"value": "hunting blinds"},
            "products": competitor_rows(30),
            "keywords": [
                {"keyword": "hunting blinds", "keyword_cn": "狩猎盲棚", "monthly_search_volume": 1200},
                {"keyword": "deer blind", "keyword_cn": "鹿猎隐蔽场景", "monthly_search_volume": 980},
            ],
            "reviews": [
                {
                    "rating": 5,
                    "text": "Easy to set up and keeps me concealed during deer hunting.",
                    "theme_cn": "安装与隐蔽",
                }
            ],
        }

        html = renderer.render_cosmo_alexa_tags(data_pack, {})

        self.assertEqual(html.count('data-cosmo-relation="'), 15)
        for required in [
            "cosmo-matrix",
            "cosmo-top-list",
            "cosmo-gap-panel",
            "cosmo-action-board",
            "cosmo-card-meta-grid",
            "cosmo-term-block",
            "cosmo-action-direction",
            "15 标签矩阵",
            "高置信标签排行",
            "产品标签 / 用户标签缺口",
            "Listing / QA / 广告动作",
            "标签对象",
            "证据强度",
            "动作方向",
        ]:
            self.assertIn(required, html)
        self.assertGreaterEqual(html.count('class="cosmo-card-meta-grid"'), 15)
        self.assertGreaterEqual(html.count('class="cosmo-term-block"'), 15)
        self.assertGreaterEqual(html.count('class="cosmo-action-direction"'), 15)
        self.assertNotIn(">USED_FOR_FUNC<", html)
        self.assertNotIn(">USED_IN_BODY<", html)
        self.assertIn('class="cosmo-relation-kind">产品意图</span>', html)
        self.assertIn('class="cosmo-relation-kind">用户意图</span>', html)
        self.assertIn('class="cosmo-relation-id">产品</b>', html)
        self.assertIn('class="cosmo-relation-id">用户</b>', html)
        self.assertIn('data-dimension="产品标签"', html)
        self.assertIn('data-dimension="用户标签"', html)
        self.assertNotIn('class="cosmo-relation-code">功能·用途</div>', html)

    def test_cosmo_renderer_adds_reference_style_summary_kpi_strip(self):
        data_pack = {
            "research_object": {"value": "hunting blinds"},
            "products": competitor_rows(30),
            "keywords": [
                {"keyword": "hunting blinds", "keyword_cn": "狩猎盲棚"},
                {"keyword": "deer blind", "keyword_cn": "鹿猎盲棚"},
                {"keyword": "ground blind", "keyword_cn": "地面盲棚"},
            ],
            "reviews": [
                {"rating": 5, "text": "Easy to set up and keeps me concealed.", "theme_cn": "安装与隐蔽"},
                {"rating": 2, "text": "The fabric is not durable enough.", "theme_cn": "质量与耐用"},
            ],
        }

        html = renderer.render_cosmo_alexa_tags(data_pack, {})

        self.assertIn('class="cosmo-summary-strip"', html)
        self.assertEqual(html.count('class="cosmo-summary-item'), 4)
        for label in ["产品标签覆盖", "用户标签覆盖", "高置信关系", "低覆盖关系"]:
            self.assertIn(label, html)
        self.assertRegex(html, r"<b>\d+/6</b>")
        self.assertRegex(html, r"<b>\d+/9</b>")
        self.assertLess(html.index('class="cosmo-summary-strip"'), html.index("cosmo-layout"))

    def test_cosmo_renderer_uses_stacked_three_column_matrix_layout(self):
        data_pack = {
            "research_object": {"value": "hunting blinds"},
            "products": competitor_rows(30),
            "keywords": [
                {"keyword": "hunting blinds", "keyword_cn": "狩猎盲棚"},
                {"keyword": "deer blind", "keyword_cn": "鹿猎盲棚"},
                {"keyword": "ground blind", "keyword_cn": "地面盲棚"},
            ],
            "reviews": [
                {"rating": 5, "text": "Easy to set up and keeps me concealed.", "theme_cn": "安装与隐蔽"},
                {"rating": 2, "text": "The fabric is not durable enough.", "theme_cn": "质量与耐用"},
            ],
        }

        html = renderer.render_cosmo_alexa_tags(data_pack, {})

        self.assertIn('class="cosmo-layout cosmo-layout-stacked"', html)
        self.assertIn('class="cosmo-submodule-grid"', html)
        self.assertIn('class="cosmo-panel cosmo-top-list cosmo-submodule"', html)
        self.assertIn('class="cosmo-panel cosmo-gap-panel cosmo-submodule"', html)
        self.assertEqual(html.count('data-cosmo-relation="'), 15)
        self.assertLess(html.index('class="cosmo-panel cosmo-matrix"'), html.index('class="cosmo-submodule-grid"'))
        self.assertLess(html.index('class="cosmo-submodule-grid"'), html.index('class="cosmo-panel cosmo-action-board"'))

    def test_cosmo_diagnostic_skeleton_keeps_standard_matrix_panel(self):
        html = renderer.render_cosmo_diagnostic_skeleton("关键词 916")

        self.assertIn('class="cosmo-panel cosmo-matrix"', html)
        self.assertEqual(html.count('class="cosmo-tag-card cosmo-matrix-cell"'), 15)
        self.assertLess(html.index('class="cosmo-panel cosmo-matrix"'), html.index('class="cosmo-submodule-grid"'))
        matrix_html = html[
            html.index('class="cosmo-panel cosmo-matrix"') : html.index('class="cosmo-submodule-grid"')
        ]
        self.assertEqual(matrix_html.count('class="cosmo-tag-card cosmo-matrix-cell"'), 15)
        self.assertIn("产品标签 · 产品被算法识别为什么", matrix_html)
        self.assertIn("用户标签 · 用户为什么搜索/购买", matrix_html)

    def test_cosmo_renderer_shows_customer_safe_evidence_sources_per_relation(self):
        data_pack = {
            "research_object": {"value": "hunting blinds"},
            "products": competitor_rows(30),
            "keywords": [
                {"keyword": "hunting blinds", "keyword_cn": "狩猎盲棚"},
                {"keyword": "ground blind", "keyword_cn": "地面隐蔽棚"},
            ],
            "reviews": [
                {
                    "rating": 5,
                    "text": "Easy to set up and keeps me concealed during deer hunting.",
                    "theme_cn": "安装与隐蔽",
                }
            ],
            "suppliers": [
                {
                    "title": "跨境户外270度单向透视迷彩打猎狩猎帐篷",
                    "price_rmb": 168,
                    "seed_keyword": "狩猎盲棚",
                }
            ],
        }

        html = renderer.render_cosmo_alexa_tags(data_pack, {})

        self.assertIn('class="cosmo-evidence-sources"', html)
        self.assertIn("证据来源", html)
        self.assertIn("竞品", html)
        self.assertIn("关键词", html)
        self.assertIn("评论", html)
        for forbidden in ["source_id", "provider", "raw_path", "effective_products", "effective_reviews"]:
            self.assertNotIn(forbidden, html)

    def test_cosmo_renderer_groups_product_and_user_labels_into_separate_lanes(self):
        data_pack = {
            "research_object": {"value": "hunting blinds"},
            "products": competitor_rows(30),
            "keywords": [
                {"keyword": "hunting blinds", "keyword_cn": "狩猎盲棚", "monthly_search_volume": 1200},
                {"keyword": "ground blind", "keyword_cn": "地面隐蔽棚", "monthly_search_volume": 900},
            ],
            "reviews": [
                {
                    "rating": 5,
                    "text": "Easy to set up for deer hunting and keeps hunters concealed in the field.",
                    "theme_cn": "安装与隐蔽",
                }
            ],
        }

        html = renderer.render_cosmo_alexa_tags(data_pack, {})

        self.assertIn('class="cosmo-matrix-lanes"', html)
        self.assertIn('class="cosmo-matrix-lane product-lane"', html)
        self.assertIn('class="cosmo-matrix-lane user-lane"', html)
        self.assertIn("产品标签 · 产品被算法识别为什么", html)
        self.assertIn("用户标签 · 用户为什么搜索/购买", html)
        self.assertEqual(html.count('data-cosmo-relation="'), 15)
        self.assertRegex(html, r'class="cosmo-matrix-lane product-lane".*data-dimension="产品标签"')
        self.assertRegex(html, r'class="cosmo-matrix-lane user-lane".*data-dimension="用户标签"')
        self.assertNotRegex(html, r">\s*(?:P0[1-8]|U0[1-9])\s*<")

    def test_keyword_customer_table_aggregates_duplicate_chinese_intents(self):
        html = renderer.render_keywords(
            {
                "effective_keywords": [
                    {
                        "keyword": "electric cupping massager",
                        "keyword_cn": "电动拔罐按摩器",
                        "relevance_cn": "高相关",
                        "monthly_search_volume": 3800,
                        "weekly_search_volume": 920,
                        "recommended_cpc": 1.22,
                        "competitor_count": 1200,
                        "intent_cn": "用户寻找电动拔罐理疗设备",
                    },
                    {
                        "keyword": "smart cupping therapy massager",
                        "keyword_cn": "电动拔罐按摩器",
                        "relevance_cn": "高相关",
                        "monthly_search_volume": 2600,
                        "weekly_search_volume": 610,
                        "recommended_cpc": 1.4,
                        "competitor_count": 980,
                        "intent_cn": "用户寻找智能拔罐按摩器",
                    },
                    {
                        "keyword": "red light therapy cupping",
                        "keyword_cn": "红光理疗拔罐",
                        "relevance_cn": "高相关",
                        "monthly_search_volume": 1800,
                        "weekly_search_volume": 420,
                        "recommended_cpc": 1.8,
                        "competitor_count": 740,
                        "intent_cn": "用户寻找红光热敷拔罐",
                    },
                ]
            }
        )

        self.assertEqual(html.count("<td>电动拔罐按摩器</td>"), 1)
        self.assertIn("electric cupping massager / smart cupping therapy massager", html)
        self.assertIn("<td>6,400</td>", html)

    def test_cosmo_renderer_outputs_analyzed_chinese_labels_not_raw_fragments(self):
        data_pack = {
            "research_object": {"value": "hunting blinds"},
            "products": [
                {
                    "asin": "B0BR4QYGS7",
                    "title": "Pop Up Hunting Blind See Through Ground Blind",
                    "title_cn": "FUNHORUN 透视弹出式地面盲棚",
                    "brand": "FUNHORUN",
                    "segment_cn": "透视弹出式地面盲棚",
                    "price": 87.98,
                    "rating": 4.5,
                    "review_count": 1087,
                    "estimated_monthly_sales": 349,
                }
            ],
            "keywords": [
                {"keyword": "hunting blinds", "keyword_cn": "狩猎盲棚"},
                {"keyword": "deer blind", "keyword_cn": "鹿猎场景"},
            ],
            "reviews": [
                {
                    "rating": 5,
                    "text": "Easy to set up and keeps me concealed during deer hunting.",
                    "theme_cn": "安装与隐蔽",
                },
                {
                    "rating": 2,
                    "text": "Material was not durable and the blind felt cramped.",
                    "theme_cn": "质量与空间",
                },
            ],
        }

        html = renderer.render_cosmo_alexa_tags(data_pack, {})

        self.assertIn("cosmo-business-meaning", html)
        self.assertIn("隐蔽观察", html)
        self.assertIn("更容易安装", html)
        self.assertIn("材质更耐用", html)
        self.assertNotIn(">USED_FOR_FUNC<", html)
        for bad_fragment in ["弹出式地</span>", "出式地面盲</span>", "视弹出式地</span>"]:
            self.assertNotIn(bad_fragment, html)
        self.assertRegex(html, r'data-cosmo-relation="U05" data-confidence="低"')

    def test_cosmo_renderer_does_not_show_relation_codes_as_customer_copy(self):
        data_pack = {
            "research_object": {"value": "hunting blinds"},
            "products": [
                {
                    "asin": "B0BR4QYGS7",
                    "title": "Pop Up Hunting Blind See Through Ground Blind",
                    "title_cn": "FUNHORUN 透视弹出式地面盲棚",
                    "brand": "FUNHORUN",
                    "segment_cn": "透视弹出式地面盲棚",
                }
            ],
            "keywords": [{"keyword": "hunting blinds", "keyword_cn": "狩猎盲棚"}],
        }

        html = renderer.render_cosmo_alexa_tags(data_pack, {})
        visible_text = re.sub(r"<[^>]+>", " ", html)

        self.assertNotRegex(visible_text, r"\b(?:USED|CAPABLE|IS_A)[A-Z_]*\b")
        self.assertNotRegex(visible_text, r"\bx(?:WANT|INTERSTED_IN|Is_A)\b")
        self.assertIn('data-cosmo-relation="P01"', html)
        self.assertNotRegex(html, r"\b(?:USED_[A-Z_]+|CAPABLE_OF|IS_A|xWANT|xIs_A|xINTERSTED_IN)\b")

    def test_cosmo_renderer_does_not_show_internal_slot_ids_as_customer_copy(self):
        data_pack = {
            "research_object": {"value": "hunting blinds"},
            "products": [
                {
                    "asin": "B0BR4QYGS7",
                    "title": "Pop Up Hunting Blind See Through Ground Blind",
                    "title_cn": "FUNHORUN 透视弹出式地面盲棚",
                    "brand": "FUNHORUN",
                    "segment_cn": "透视弹出式地面盲棚",
                }
            ],
            "keywords": [{"keyword": "hunting blinds", "keyword_cn": "狩猎盲棚"}],
        }

        html = renderer.render_cosmo_alexa_tags(data_pack, {})
        visible_text = re.sub(r"<[^>]+>", " ", html)

        self.assertIn('data-cosmo-relation="P01"', html)
        self.assertIn('data-cosmo-relation="U09"', html)
        self.assertNotRegex(visible_text, r"\b[PU]\d{2}\b")
        self.assertIn("产品标签", visible_text)
        self.assertIn("用户标签", visible_text)

    def test_cosmo_low_coverage_slots_use_relation_specific_chinese_diagnostics(self):
        data_pack = {
            "research_object": {"value": "hunting blinds"},
            "products": [
                {
                    "asin": "B0BR4QYGS7",
                    "title": "Pop Up Hunting Blind See Through Ground Blind",
                    "title_cn": "透视地面盲棚",
                    "brand": "FUNHORUN",
                    "segment_cn": "透视地面盲棚",
                }
            ],
            "keywords": [{"keyword": "hunting blinds", "keyword_cn": "狩猎盲棚"}],
        }

        html = renderer.render_cosmo_alexa_tags(data_pack, {})
        visible_text = re.sub(r"<[^>]+>", " ", html)

        self.assertNotIn("低覆盖诊断", visible_text)
        self.assertIn("需补强：功能与用途证据", visible_text)
        self.assertIn("需补强：身体部位证据", visible_text)
        self.assertIn("需补强：用户想要达成证据", visible_text)
        self.assertNotRegex(visible_text, r"\b(?:USED_[A-Z_]+|CAPABLE_OF|IS_A|xWANT|xIs_A|xINTERSTED_IN)\b")
        self.assertGreaterEqual(len(set(re.findall(r"需补强：[^\s<]+证据", visible_text))), 8)

    def test_cosmo_renderer_does_not_fill_action_relations_with_generic_product_names(self):
        data_pack = {
            "research_object": {"value": "hunting blinds"},
            "products": [
                {
                    "asin": "B0BR4QYGS7",
                    "title": "Hunting Blind",
                    "title_cn": "通用狩猎地面盲棚",
                    "brand": "FUNHORUN",
                    "segment_cn": "通用狩猎地面盲棚",
                }
            ],
            "keywords": [{"keyword": "hunting blinds", "keyword_cn": "狩猎盲棚"}],
        }

        payload = renderer.generate_cosmo_alexa_tags(data_pack, {})
        by_relation = {item["relation_type"]: item for item in payload["relations"]}

        self.assertIn("狩猎盲棚", by_relation["IS_A"]["terms"])
        for relation in ["CAPABLE_OF", "USED_TO", "USED_WITH"]:
            self.assertNotIn("通用狩猎地面盲棚", by_relation[relation]["terms"])

    def test_cosmo_renderer_generates_category_specific_tags_without_hunting_fallbacks(self):
        data_pack = {
            "research_object": {"value": "smart cat water fountain"},
            "products": [
                {
                    "asin": "B0PETWATER1",
                    "title": "Smart Cat Water Fountain Stainless Steel Pet Drinking Fountain Quiet Pump",
                    "title_cn": "不锈钢宠物饮水机 静音水泵 自动循环",
                    "brand": "PetFlow",
                    "segment_cn": "宠物饮水机",
                    "category": "Pet Supplies",
                    "price": 29.99,
                    "rating": 4.6,
                    "review_count": 2400,
                    "estimated_monthly_sales": 1800,
                }
            ],
            "keywords": [
                {"keyword": "cat water fountain", "keyword_cn": "猫咪饮水机", "intent_cn": "宠物补水"},
                {"keyword": "pet drinking fountain", "keyword_cn": "宠物自动饮水", "intent_cn": "自动循环饮水"},
                {"keyword": "quiet pump cat fountain", "keyword_cn": "静音水泵饮水机", "intent_cn": "低噪运行"},
            ],
            "reviews": [
                {
                    "rating": 5,
                    "text": "My cats drink more water now. The pump is quiet and the stainless bowl is easy to clean.",
                    "theme_cn": "饮水量与静音",
                    "summary_cn": "猫咪饮水量增加，水泵安静，不锈钢碗容易清洁。",
                },
                {
                    "rating": 2,
                    "text": "Filter replacement is confusing and the pump needs cleaning often.",
                    "theme_cn": "滤芯维护",
                    "summary_cn": "滤芯更换说明不清晰，水泵需要频繁清洁。",
                },
            ],
            "suppliers": [
                {
                    "title": "宠物饮水机静音循环水泵不锈钢猫咪自动饮水器",
                    "price_rmb": 38,
                    "supplier_name": "宠物用品工厂",
                    "url": "https://detail.1688.com/offer/123.html",
                }
            ],
        }

        payload = renderer.generate_cosmo_alexa_tags(data_pack, {})
        by_relation = {item["relation_type"]: item for item in payload["relations"]}
        all_terms = " ".join(term for item in payload["relations"] for term in item["terms"])

        for forbidden in ["狩猎", "盲棚", "猎人", "迷彩", "地面盲棚"]:
            self.assertNotIn(forbidden, all_terms)
        self.assertIn("宠物饮水机", by_relation["USED_AS"]["terms"])
        self.assertTrue({"静音水泵", "自动循环饮水"} & set(by_relation["USED_FOR_FUNC"]["terms"]))
        self.assertTrue({"猫咪饮水", "宠物补水"} & set(by_relation["USED_TO"]["terms"]))
        self.assertTrue({"宠物主人", "猫咪用户"} & set(by_relation["USED_BY"]["terms"]))
        self.assertTrue({"更容易清洁", "安静运行"} & set(by_relation["xWANT"]["terms"]))

    def test_cosmo_renderer_does_not_leak_hunting_labels_into_outdoor_non_hunting_categories(self):
        data_pack = {
            "research_object": {"value": "wireless bluetooth speaker"},
            "products": [
                {
                    "asin": "B0SPEAKER1",
                    "title": "Portable Bluetooth Speaker Waterproof Outdoor Wireless Speaker",
                    "title_cn": "便携蓝牙音箱 防水户外无线音箱",
                    "brand": "SoundBox",
                    "segment_cn": "蓝牙音箱",
                    "category": "Electronics",
                    "price": 39.99,
                    "rating": 4.6,
                    "review_count": 4200,
                    "estimated_monthly_sales": 2600,
                }
            ],
            "keywords": [
                {"keyword": "bluetooth speaker", "keyword_cn": "蓝牙音箱", "intent_cn": "户外音乐"},
                {"keyword": "waterproof speaker", "keyword_cn": "防水音箱", "intent_cn": "户外使用"},
            ],
            "reviews": [
                {
                    "rating": 5,
                    "text": "The speaker is easy to carry outside and the waterproof shell works well.",
                    "theme_cn": "便携与防水",
                    "summary_cn": "用户认可便携、防水和户外播放。",
                }
            ],
        }

        payload = renderer.generate_cosmo_alexa_tags(data_pack, {})
        all_terms = " ".join(term for item in payload["relations"] for term in item["terms"])
        by_relation = {item["relation_type"]: item for item in payload["relations"]}

        for forbidden in ["狩猎", "盲棚", "猎人", "迷彩", "隐蔽装备", "塔式/箱式盲棚", "地面盲棚"]:
            self.assertNotIn(forbidden, all_terms)
        self.assertIn("蓝牙音箱", by_relation["USED_AS"]["terms"])
        self.assertTrue({"户外使用", "户外播放", "户外音乐"} & set(by_relation["USED_TO"]["terms"]))

    def test_cosmo_renderer_uses_analysis_plan_relation_profile_for_generic_categories(self):
        data_pack = {
            "research_object": {"value": "ergonomic office chair"},
            "products": [
                {
                    "asin": "B0CHAIR0001",
                    "title": "Ergonomic Office Chair Adjustable Lumbar Support Mesh Seat",
                    "title_cn": "人体工学办公椅 可调节腰托 网布坐垫",
                    "brand": "WorkSeat",
                    "segment_cn": "人体工学办公椅",
                    "category": "Office Furniture",
                    "price": 129.99,
                    "rating": 4.4,
                    "review_count": 1800,
                    "estimated_monthly_sales": 900,
                }
            ],
            "keywords": [
                {"keyword": "ergonomic office chair", "keyword_cn": "人体工学办公椅", "intent_cn": "久坐支撑"},
                {"keyword": "office chair lumbar support", "keyword_cn": "腰托办公椅", "intent_cn": "腰背支撑"},
            ],
            "reviews": [
                {
                    "rating": 5,
                    "text": "The lumbar support helps during long work days and the armrests are easy to adjust.",
                    "theme_cn": "腰背支撑",
                    "summary_cn": "用户认可久坐支撑和扶手调节。",
                }
            ],
        }
        analysis_plan = {
            "report_label_profile": {
                "cosmo_relation_terms": {
                    "USED_FOR_FUNC": ["腰背支撑", "扶手调节", "网布透气"],
                    "USED_FOR_AUD": ["居家办公人群"],
                    "USED_TO": ["久坐办公", "姿势支撑"],
                    "USED_AS": ["人体工学办公椅"],
                    "USED_BY": ["办公室用户"],
                    "xWANT": ["久坐不累", "调节更顺手"],
                }
            }
        }

        payload = renderer.generate_cosmo_alexa_tags(data_pack, analysis_plan)
        by_relation = {item["relation_type"]: item for item in payload["relations"]}
        all_terms = " ".join(term for item in payload["relations"] for term in item["terms"])

        self.assertEqual(by_relation["USED_FOR_FUNC"]["terms"][:3], ["腰背支撑", "扶手调节", "网布透气"])
        self.assertIn("居家办公人群", by_relation["USED_FOR_AUD"]["terms"])
        self.assertIn("人体工学办公椅", by_relation["USED_AS"]["terms"])
        self.assertIn("久坐不累", by_relation["xWANT"]["terms"])
        for forbidden in ["狩猎", "盲棚", "宠物饮水机", "蓝牙音箱"]:
            self.assertNotIn(forbidden, all_terms)

    def test_cosmo_renderer_filters_unsupported_ai_profile_terms_per_term(self):
        data_pack = {
            "research_object": {"value": "ergonomic office chair"},
            "products": [
                {
                    "asin": "B0CHAIR0001",
                    "title": "Ergonomic Office Chair Adjustable Lumbar Support Mesh Seat",
                    "title_cn": "人体工学办公椅 可调节腰托 网布坐垫",
                    "brand": "WorkSeat",
                    "segment_cn": "人体工学办公椅",
                    "category": "Office Furniture",
                    "price": 129.99,
                    "rating": 4.4,
                    "review_count": 1800,
                    "estimated_monthly_sales": 900,
                }
            ],
            "keywords": [
                {"keyword": "ergonomic office chair", "keyword_cn": "人体工学办公椅", "intent_cn": "久坐支撑"},
                {"keyword": "office chair lumbar support", "keyword_cn": "腰托办公椅", "intent_cn": "腰背支撑"},
            ],
            "reviews": [
                {
                    "rating": 5,
                    "text": "The lumbar support helps during long work days and the mesh back is breathable.",
                    "theme_cn": "腰背支撑",
                    "summary_cn": "用户认可久坐支撑和网布透气。",
                }
            ],
        }
        analysis_plan = {
            "report_label_profile": {
                "cosmo_relation_terms": {
                    "USED_FOR_FUNC": ["腰背支撑", "宠物饮水机", "狩猎盲棚", "LED灯带"],
                    "USED_AS": ["人体工学办公椅", "蓝牙音箱", "塔式狩猎盲棚"],
                    "xWANT": ["久坐不累", "水杯保冷", "隐蔽观察"],
                }
            }
        }

        payload = renderer.generate_cosmo_alexa_tags(data_pack, analysis_plan)
        all_terms = " ".join(term for item in payload["relations"] for term in item["terms"])
        by_relation = {item["relation_type"]: item for item in payload["relations"]}

        self.assertIn("腰背支撑", by_relation["USED_FOR_FUNC"]["terms"])
        self.assertIn("人体工学办公椅", by_relation["USED_AS"]["terms"])
        for forbidden in ["宠物饮水机", "狩猎盲棚", "LED灯带", "蓝牙音箱", "塔式狩猎盲棚", "水杯保冷", "隐蔽观察"]:
            self.assertNotIn(forbidden, all_terms)

    def test_cosmo_renderer_blocks_cross_category_event_and_interest_pollution(self):
        data_pack = {
            "research_object": {"value": "under cabinet motion sensor light"},
            "products": [
                {
                    "asin": "B0LIGHT0001",
                    "title": "Rechargeable Under Cabinet Motion Sensor Light for Kitchen Closet",
                    "title_cn": "无线充电橱柜感应灯 厨房衣柜使用",
                    "brand": "LightBrand",
                    "segment_cn": "橱柜感应灯",
                    "category": "Under Cabinet Lights",
                    "price": 19.99,
                    "rating": 4.5,
                    "review_count": 1200,
                    "estimated_monthly_sales": 900,
                }
            ],
            "keywords": [
                {"keyword": "under cabinet motion sensor light", "keyword_cn": "橱柜感应灯", "intent_cn": "厨房照明"},
                {"keyword": "outdoor speaker turkey hunting noise", "keyword_cn": "污染关键词：户外音箱火鸡狩猎"},
            ],
            "reviews": [
                {
                    "rating": 5,
                    "text": "Easy to install under the cabinet and the motion sensor works well at night.",
                    "theme_cn": "安装与感应",
                    "summary_cn": "用户认可安装便利和夜间感应触发。",
                }
            ],
        }

        payload = renderer.generate_cosmo_alexa_tags(data_pack, {})
        all_terms = " ".join(term for item in payload["relations"] for term in item["terms"])

        self.assertIn("橱柜感应灯", all_terms)
        for forbidden in ["火鸡狩猎", "鹿猎场景", "户外狩猎活动", "狩猎体验", "户外音乐"]:
            self.assertNotIn(forbidden, all_terms)

    def test_cosmo_renderer_treats_kids_mentions_as_family_safety_for_non_toy_products(self):
        data_pack = {
            "research_object": {"value": "under cabinet motion sensor light"},
            "products": [
                {
                    "asin": "B0LIGHT0002",
                    "title": "Rechargeable Under Cabinet Motion Sensor Light for Kitchen Stairs",
                    "title_cn": "无线充电橱柜感应灯 楼梯厨房夜间照明",
                    "brand": "LightBrand",
                    "segment_cn": "橱柜感应灯",
                    "category": "Under Cabinet Lights",
                    "price": 19.99,
                    "rating": 4.5,
                    "review_count": 1200,
                    "estimated_monthly_sales": 900,
                }
            ],
            "keywords": [
                {"keyword": "under cabinet motion sensor light", "keyword_cn": "橱柜感应灯", "intent_cn": "厨房照明"}
            ],
            "reviews": [
                {
                    "rating": 5,
                    "text": "I use these lights on the stairs at night so kids and family can walk safely.",
                    "theme_cn": "夜间安全",
                    "summary_cn": "用户认可夜间照明和家庭安全感。",
                }
            ],
        }

        payload = renderer.generate_cosmo_alexa_tags(data_pack, {})
        all_terms = " ".join(term for item in payload["relations"] for term in item["terms"])

        self.assertIn("家庭使用场景", all_terms)
        for forbidden in ["儿童使用场景", "父母购买者", "儿童礼品决策者"]:
            self.assertNotIn(forbidden, all_terms)

    def test_cosmo_renderer_localizes_and_deduplicates_profile_terms_for_customer_html(self):
        data_pack = {
            "research_object": {"value": "hunting blinds"},
            "products": [
                {
                    "asin": "B0BR4QYGS7",
                    "title": "See Through Pop Up Ground Blind for Deer Hunting",
                    "title_cn": "透视弹出式地面盲棚 鹿猎使用",
                    "brand": "FUNHORUN",
                    "segment_cn": "透视弹出式地面盲棚",
                    "category": "Hunting Blinds",
                }
            ],
            "keywords": [
                {"keyword": "see through ground blind", "keyword_cn": "透视地面盲棚"},
                {"keyword": "deer hunting blind", "keyword_cn": "鹿猎盲棚"},
            ],
            "reviews": [
                {
                    "rating": 5,
                    "text": "The see through blind helps me stay concealed while watching deer.",
                    "theme_cn": "隐蔽观察",
                    "summary_cn": "用户认可透视观察和隐蔽效果。",
                }
            ],
        }
        analysis_plan = {
            "report_label_profile": {
                "cosmo_relation_terms": {
                    "USED_FOR_FUNC": [
                        "see through",
                        "see-through",
                        "ground blind",
                        "透视地面盲棚",
                        "隐蔽观察",
                    ],
                    "USED_AS": ["ground blind", "hunting blind", "透视地面盲棚", "弹出式地面盲棚"],
                }
            }
        }

        payload = renderer.generate_cosmo_alexa_tags(data_pack, analysis_plan)
        html = renderer.render_cosmo_alexa_tags(data_pack, analysis_plan)
        by_relation = {item["relation_type"]: item for item in payload["relations"]}

        self.assertIn("透视地面盲棚", by_relation["USED_FOR_FUNC"]["terms"])
        self.assertIn("隐蔽观察", by_relation["USED_FOR_FUNC"]["terms"])
        self.assertEqual(len(by_relation["USED_FOR_FUNC"]["terms"]), len(set(by_relation["USED_FOR_FUNC"]["terms"])))
        for forbidden in ["see through", "see-through", "ground blind", "hunting blind"]:
            self.assertNotIn(f">{forbidden}<", html)
            self.assertNotIn(forbidden, by_relation["USED_FOR_FUNC"]["terms"])
        self.assertNotRegex(html, r"<span>[^<]*[a-zA-Z]{3,}[^<]*</span>")

    def test_cosmo_action_cards_are_relation_specific_not_template_repeats(self):
        data_pack = {
            "research_object": {"value": "hunting blinds"},
            "products": competitor_rows(30),
            "keywords": [
                {"keyword": "hunting blinds", "keyword_cn": "狩猎盲棚"},
                {"keyword": "deer blind", "keyword_cn": "鹿猎场景"},
                {"keyword": "ground blind", "keyword_cn": "地面隐蔽棚"},
            ],
            "reviews": [
                {"rating": 5, "text": "Easy to set up and keeps me concealed.", "theme_cn": "安装与隐蔽"},
                {"rating": 2, "text": "Material was not durable.", "theme_cn": "质量与耐用"},
            ],
        }

        html = renderer.render_cosmo_alexa_tags(data_pack, {})

        self.assertLessEqual(html.count("自然覆盖"), 2)
        self.assertLessEqual(html.count("避免堆砌"), 2)
        for expected in ["首屏承诺", "证据问答", "精准投放"]:
            self.assertIn(expected, html)

    def test_cosmo_terms_are_not_over_reused_across_high_confidence_relations(self):
        data_pack = {
            "research_object": {"value": "hunting blinds"},
            "products": competitor_rows(30),
            "keywords": [
                {"keyword": "hunting blinds", "keyword_cn": "狩猎盲棚"},
                {"keyword": "deer blind", "keyword_cn": "鹿猎场景"},
                {"keyword": "ground blind", "keyword_cn": "地面隐蔽棚"},
            ],
            "reviews": [
                {"rating": 5, "text": "Easy to set up and keeps me concealed in the field.", "theme_cn": "安装与隐蔽"},
                {"rating": 2, "text": "The material is not durable and the space feels small.", "theme_cn": "质量与空间"},
            ],
        }

        payload = renderer.generate_cosmo_alexa_tags(data_pack, {})
        term_relation_counts = Counter()
        for item in payload["relations"]:
            if item["confidence"] == "低":
                continue
            for term in set(item["terms"]):
                term_relation_counts[term] += 1

        overused = {term: count for term, count in term_relation_counts.items() if count > 2}
        self.assertEqual(overused, {})

    def test_cosmo_relation_terms_collapse_near_duplicate_product_type_variants(self):
        data_pack = {
            "research_object": {"value": "hunting blinds"},
            "products": [
                {
                    "asin": "B0BLIND001",
                    "title": "See Through Pop Up Ground Blind for Deer Hunting",
                    "title_cn": "透视弹出式地面盲棚",
                    "brand": "FieldOne",
                    "segment_cn": "高价透视地面盲棚",
                    "category": "Hunting Blinds",
                    "price": 119.99,
                    "rating": 4.6,
                    "reviews_count": 300,
                    "monthly_sales": 900,
                },
                {
                    "asin": "B0BLIND002",
                    "title": "Universal Hunting Ground Blind with Carry Bag",
                    "title_cn": "通用狩猎地面盲棚",
                    "brand": "FieldTwo",
                    "segment_cn": "透视地面盲棚",
                    "category": "Hunting Blinds",
                    "price": 89.99,
                    "rating": 4.4,
                    "reviews_count": 180,
                    "monthly_sales": 650,
                },
            ],
            "keywords": [
                {"keyword": "see through ground blind", "keyword_cn": "透视地面盲棚"},
                {"keyword": "pop up hunting blind", "keyword_cn": "弹出式狩猎盲棚"},
            ],
            "reviews": [
                {"rating": 5, "text": "Easy to set up and keeps me concealed.", "theme_cn": "安装与隐蔽"},
                {"rating": 2, "text": "The material is not durable.", "theme_cn": "质量与耐用"},
            ],
        }

        payload = renderer.generate_cosmo_alexa_tags(data_pack, {})
        by_relation = {item["relation_type"]: item for item in payload["relations"]}

        for relation_type in ["USED_AS", "IS_A"]:
            terms = by_relation[relation_type]["terms"]
            normalized_roots = [
                term
                for term in terms
                if "地面盲棚" in term or "狩猎盲棚" in term
            ]
            self.assertLessEqual(len(normalized_roots), 2, terms)
            self.assertNotIn("高价透视地面盲棚", terms)
            self.assertNotIn("通用狩猎地面盲棚", terms)

    def test_cosmo_relation_terms_collapse_duplicate_action_intents(self):
        data_pack = {
            "research_object": {"value": "hunting blinds"},
            "products": competitor_rows(30),
            "keywords": [
                {"keyword": "easy setup hunting blind", "keyword_cn": "易安装狩猎盲棚"},
                {"keyword": "quick pop up ground blind", "keyword_cn": "快速搭建地面盲棚"},
            ],
            "reviews": [
                {"rating": 5, "text": "It is easy to set up and install.", "theme_cn": "安装更简单"},
                {"rating": 4, "text": "Setup was fast and the blind is durable.", "theme_cn": "搭建效率"},
                {"rating": 2, "text": "The fabric is not durable enough.", "theme_cn": "质量与耐用"},
            ],
        }

        payload = renderer.generate_cosmo_alexa_tags(data_pack, {})
        xwant = next(item for item in payload["relations"] if item["relation_type"] == "xWANT")
        install_terms = [term for term in xwant["terms"] if "安装" in term or "搭建" in term]

        self.assertEqual(len(install_terms), 1, xwant["terms"])

    def test_report_readiness_view_downgrades_partial_supply_claims(self):
        readiness = {
            "acceptance_ready": False,
            "partial_report_ready": True,
            "supply_conclusion_blocked": True,
            "blocking_gaps": [
                {
                    "module": "supplier_quote_relevance",
                    "reason": "严格相关 1688 成品报价不足 50 条",
                    "impact": "不能输出毛利率和供应链可控结论",
                    "next_step": "继续用相关中文词补采 1688",
                }
            ],
        }
        view = renderer.report_readiness_view(readiness, {"overall_score": 0.93, "grade": "A"}, "Go")

        self.assertEqual(view["delivery_state"], "诊断交付")
        self.assertEqual(view["decision"], "Watch")
        self.assertEqual(view["evidence_strength"], "中 / 诊断交付")
        self.assertTrue(view["supply_blocked"])
        forbidden = "证据充分 供应链可控度较高 50+ 可打样 毛利率可测算".split()
        self.assertFalse(any(term in json.dumps(view, ensure_ascii=False) for term in forbidden))

    def test_client_trust_copy_respects_blocked_readiness_without_supply_block(self):
        data_pack = {
            "report_readiness_view": renderer.report_readiness_view(
                {
                    "acceptance_ready": False,
                    "partial_report_ready": False,
                    "supply_conclusion_blocked": False,
                    "blocking_gaps": [
                        {
                            "module": "competitor_pool_depth",
                            "reason": "亚马逊竞品池不足",
                            "impact": "不能输出完整市场结论",
                            "next_step": "补采竞品",
                        }
                    ],
                    "counts": {"keywords": 518, "valid_competitors": 31, "reviews": 724, "valid_supplier_quotes": 88},
                },
                {"overall_score": 0.93, "grade": "A"},
                "Go",
            ),
            "products": competitor_rows(31),
            "keywords": [{"keyword": "smart lighting", "keyword_cn": "智能照明"} for _ in range(10)],
            "reviews": [{"summary_cn": "评论归纳"} for _ in range(8)],
            "suppliers": supplier_rows(55),
            "data_gaps": [],
        }
        analysis_plan = {}

        trust_html = renderer.client_trust_strip(data_pack, analysis_plan, "No-Go")
        coverage_html = renderer.render_client_data_coverage(data_pack, analysis_plan, "No-Go")

        self.assertIn("低 / 阻断交付", trust_html + coverage_html)
        self.assertNotIn("kpi-trend up\">通过", trust_html)
        self.assertNotIn("当前数据足以支持 Go / Watch / No-Go 方向判断", coverage_html)
        self.assertIn("核心门禁未通过", coverage_html)
        self.assertNotIn("<td>数据覆盖</td><td>中高</td>", coverage_html)

    def test_blocked_readiness_does_not_render_supply_gate_as_clean_pass(self):
        readiness = {
            "acceptance_ready": False,
            "partial_report_ready": False,
            "supply_conclusion_blocked": False,
            "blocking_gaps": [
                {
                    "module": "keyword_sample_depth",
                    "reason": "有效关键词样本不足",
                    "impact": "不能输出完整市场结构判断",
                    "next_step": "补充细分赛道关键词并重新去重",
                }
            ],
            "supplier_quote_gate": {"passed": True},
            "supplier_quality_gate": {"passed": True, "customer_visible_passed": True},
        }
        view = renderer.report_readiness_view(readiness, {"overall_score": 0.91, "grade": "A"}, "Watch")
        data_pack = {
            "report_readiness_view": view,
            "quality": {"overall_score": 0.91, "grade": "A"},
            "products": competitor_rows(30),
            "keywords": [{"keyword": "cupping massager", "keyword_cn": "拔罐按摩器"} for _ in range(20)],
            "reviews": [{"summary_cn": "评论归纳"} for _ in range(6)],
            "suppliers": supplier_rows(60),
        }

        cards_html = renderer.render_index_cards("电动拔罐器", "Watch", data_pack)

        self.assertEqual(view["delivery_state"], "阻断交付")
        self.assertIn("供应链数据通过；完整结论仍受其他门禁阻断", cards_html)
        self.assertNotIn("供应链测算门禁通过", cards_html)
        self.assertNotIn("kpi-trend up\">通过", cards_html)

    def test_blocked_trust_strip_uses_core_blocking_gap_count_not_raw_gap_total(self):
        readiness = {
            "acceptance_ready": False,
            "partial_report_ready": False,
            "blocking_gaps": [
                {"module": "market_segment_split", "reason": "赛道未拆分", "next_step": "补采赛道"},
                {"module": "market_segment_depth", "reason": "主赛道不足", "next_step": "补采竞品"},
                {"module": "keyword_sample_depth", "reason": "关键词不足", "next_step": "补采关键词"},
            ],
            "counts": {"keywords": 534, "valid_competitors": 30, "reviews": 320, "suppliers": 201},
        }
        view = renderer.report_readiness_view(readiness, {"overall_score": 0.7, "grade": "B"}, "No-Go")
        data_pack = {
            "report_readiness": readiness,
            "report_readiness_view": view,
            "quality": {"overall_score": 0.7, "grade": "B"},
            "products": competitor_rows(38),
            "keywords": [{"keyword": "cupping", "keyword_cn": "拔罐"} for _ in range(20)],
            "reviews": [{"summary_cn": "评论归纳"} for _ in range(6)],
            "suppliers": supplier_rows(60),
            "data_gaps": [f"raw gap {idx}" for idx in range(9)],
        }
        analysis_plan = {"limitations": [f"limitation {idx}" for idx in range(5)]}

        html = renderer.client_trust_strip(data_pack, analysis_plan, "No-Go")

        self.assertIn("3 项", html)
        self.assertNotIn("14 项", html)

    def test_sample_coverage_without_readiness_does_not_claim_qualified_competitors(self):
        data_pack = {
            "products": competitor_rows(12),
            "keywords": [{"keyword": "cupping", "keyword_cn": "拔罐"} for _ in range(3)],
            "reviews": [{"summary_cn": "评论归纳"}],
            "suppliers": supplier_rows(4),
        }

        coverage = renderer.sample_coverage(data_pack)

        self.assertIn("相关产品覆盖 12", coverage)
        self.assertNotIn("合格竞品 12", coverage)

    def test_diagnostic_child_reports_hide_internal_readiness_file_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_renderable_report(report_dir)
            data_path = report_dir / "data" / "data_pack.json"
            data_pack = json.loads(data_path.read_text(encoding="utf-8"))
            data_pack["keywords"] = data_pack["keywords"][:12]
            write_json(data_path, data_pack)
            result = self.run_renderer(report_dir, "--no-recover")

            self.assertNotEqual(result.returncode, 0)
            for filename in ["market-depth-report.html", "lifecycle-strategy-report.html", "demand-gap-report.html"]:
                html = (report_dir / "output" / "html_reports" / filename).read_text(encoding="utf-8")
                self.assertIn("门禁诊断记录", html)
                self.assertNotIn("data_readiness_report", html)

    def test_diagnostic_render_rewrites_stale_report_md_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_renderable_report(report_dir)
            stale_report = (
                "# 旧审计稿\n\n"
                "## 交付状态\n"
                "- readiness: acceptance_ready=true\n"
                "- decision: Watch\n\n"
                "## Go / Watch / No-Go\n"
                "- final_decision: Watch\n"
                "- rationale: 样本达到标准版门槛。\n"
            )
            write_text(report_dir / "output" / "report.md", stale_report)
            data_path = report_dir / "data" / "data_pack.json"
            data_pack = json.loads(data_path.read_text(encoding="utf-8"))
            data_pack["keywords"] = data_pack["keywords"][:12]
            write_json(data_path, data_pack)

            result = self.run_renderer(report_dir, "--no-recover")

            self.assertNotEqual(result.returncode, 0)
            report_md = (report_dir / "output" / "report.md").read_text(encoding="utf-8")
            self.assertIn("final_decision: No-Go", report_md)
            self.assertIn("diagnostic_delivery_pass: true", report_md)
            self.assertNotIn("acceptance_ready=true", report_md)
            self.assertNotIn("样本达到标准版门槛", report_md)

    def test_lifecycle_supplier_matching_rejects_generic_tent_noise(self):
        data_pack = {
            "research_object": {"value": "hunting blinds"},
            "products": [
                {
                    "asin": f"B0HUNT{idx:04d}",
                    "title": f"See Through Pop Up Hunting Blind {idx}",
                    "title_cn": f"FUNHORUN 透视弹出式地面盲棚 {idx}",
                    "brand": "FUNHORUN",
                    "segment_cn": "透视弹出式地面盲棚",
                    "price": 79.99 + idx,
                    "rating": 4.5,
                    "review_count": 1000 + idx,
                    "estimated_monthly_sales": 300 + idx,
                }
                for idx in range(12)
            ],
            "keywords": [
                {"keyword": "hunting blind", "keyword_cn": "狩猎盲棚"},
                {"keyword": "see through blind", "keyword_cn": "透视盲棚"},
            ],
            "suppliers": [
                {
                    "title": "跨境户外270度单向透视迷彩打猎狩猎帐篷",
                    "price_rmb": 168,
                    "seed_keyword": "狩猎盲棚",
                    "url": "https://detail.1688.com/offer/good.html",
                },
                {
                    "title": "儿童帐篷室内游戏屋亲子露营帐篷",
                    "price_rmb": 45,
                    "seed_keyword": "户外帐篷",
                    "url": "https://detail.1688.com/offer/bad-kids.html",
                },
                {
                    "title": "吊床吊篮降落伞布吊床带蚊帐户外帐篷",
                    "price_rmb": 32,
                    "seed_keyword": "户外帐篷",
                    "url": "https://detail.1688.com/offer/bad-hammock.html",
                },
                {
                    "title": "急救帐篷一次性帐篷野外自救保温",
                    "price_rmb": 12,
                    "seed_keyword": "户外帐篷",
                    "url": "https://detail.1688.com/offer/bad-emergency.html",
                },
            ],
        }
        lifecycle = renderer.build_lifecycle_strategy_analysis(data_pack, {}, "src_test")
        serialized = json.dumps(lifecycle, ensure_ascii=False)
        self.assertIn("透视迷彩打猎狩猎帐篷", serialized)
        self.assertNotIn("儿童帐篷", serialized)
        self.assertNotIn("吊床", serialized)
        self.assertNotIn("急救帐篷", serialized)
        self.assertNotIn("拓品路径C", serialized)

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
            self.assertIn('class="comp-product-thumb"', market_html)
            self.assertIn('class="comp-image-thumb"', market_html)
            self.assertIn('class="comp-deep-image"', market_html)
            self.assertIn("https://m.media-amazon.com/images/I/test-competitor-", market_html)
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
            self.assertIn('class="sku-reference-image"', lifecycle_html)
            self.assertIn('class="sku-reference-thumb table-thumb"', lifecycle_html)
            self.assertIn("https://m.media-amazon.com/images/I/test-competitor-", lifecycle_html)
            self.assertIn("lifecycle-kpi-secondary", lifecycle_html)
            self.assertIn("P1 首发 SKU", lifecycle_html)
            self.assertIn("高优先级 SKU", lifecycle_html)
            self.assertIn("套装/升级 SKU", lifecycle_html)
            self.assertIn("战略结论", lifecycle_html)
            for name in ["market-depth-report.html", "lifecycle-strategy-report.html", "demand-gap-report.html"]:
                child_html = (report_dir / "output" / "html_reports" / name).read_text(encoding="utf-8")
                self.assertIn("site-nav", child_html)
                self.assertIn('href="report.html"', child_html)
                self.assertIn('href="market-depth-report.html"', child_html)
                self.assertIn('href="lifecycle-strategy-report.html"', child_html)
                self.assertIn('href="demand-gap-report.html"', child_html)
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
            self.assertIn('class="metric-tag"><b>30</b><span>合格竞品</span></span>', rendered_text)
            self.assertNotIn('class="metric-tag"><b>30</b><span>竞品</span></span>', rendered_text)
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
            self.assertIn(delivery["decision"], {"Go", "Watch", "No-Go"})
            self.assertIsNotNone(delivery["decision"])
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
            cosmo_path = report_dir / "analysis" / "cosmo_alexa_tags.json"
            self.assertTrue(cosmo_path.exists(), "diagnostic bundle must keep COSMO artifact for validator parity")
            cosmo = json.loads(cosmo_path.read_text(encoding="utf-8"))
            self.assertEqual(len(cosmo["relations"]), 15)
            delivery_path = report_dir / "output" / "delivery_result.json"
            self.assertTrue(delivery_path.exists(), "diagnostic bundle must keep delivery metadata")
            delivery = json.loads(delivery_path.read_text(encoding="utf-8"))
            self.assertIn(delivery.get("decision"), {"Watch", "No-Go"})
            self.assertEqual(delivery.get("cosmo_alexa_tags", {}).get("path"), "analysis/cosmo_alexa_tags.json")
            self.assertEqual(delivery.get("cosmo_alexa_tags", {}).get("relation_total"), 15)
            self.assertEqual(delivery.get("status"), "blocked")
            self.assertIs(delivery.get("critic_review", {}).get("pass"), False)
            self.assertEqual(delivery.get("critic_review", {}).get("score"), 0)
            invocation_statuses = {
                entry.get("status")
                for entry in (delivery.get("child_skill_invocations") or {}).values()
            }
            self.assertEqual(invocation_statuses, {"diagnostic_template"})
            diagnostic_html = (report_dir / "output" / "html_reports" / "report.html").read_text(encoding="utf-8")
            compat_html = (report_dir / "output" / "report.html").read_text(encoding="utf-8")
            self.assertIn("三合一市场研究报告", diagnostic_html)
            for href in ["market-depth-report.html", "lifecycle-strategy-report.html", "demand-gap-report.html"]:
                self.assertIn(href, diagnostic_html)
                self.assertIn(f"html_reports/{href}", compat_html)
            for client_term in ["证据强度", "数据覆盖", "数据缺口", "建议动作", "置信等级"]:
                self.assertIn(client_term, diagnostic_html)
            self.assertIn("补齐门禁后重新分析", diagnostic_html)
            self.assertNotIn("collect_", diagnostic_html)
            self.assertNotIn("sorftime", diagnostic_html.casefold())
            child_expectations = {
                "market-depth-report.html": ["template-market", "市场深度调研报告", "补采诊断"],
                "lifecycle-strategy-report.html": ["template-lifecycle", "产品全生命周期拓品战略报告", "补采诊断"],
                "demand-gap-report.html": ["template-demand", "用户心智断层与需求机会报告", "补采诊断"],
            }
            forbidden_child_conclusions = [
                "毛利率测算 · 各定价方案对比",
                "竞品狙击结论",
                "SKU 优先级全量榜",
                "证据充分",
                "供应链可控度较高",
            ]
            for filename, expected_terms in child_expectations.items():
                child_html = (report_dir / "output" / "html_reports" / filename).read_text(encoding="utf-8")
                for expected_term in expected_terms:
                    self.assertIn(expected_term, child_html, f"{filename} must keep the standard diagnostic template slot {expected_term}")
                for forbidden in forbidden_child_conclusions:
                    self.assertNotIn(forbidden, child_html, f"{filename} must not keep stale full-report conclusion {forbidden}")

    def test_cosmo_tags_do_not_use_outdoor_fallbacks_for_cupping_reports(self):
        data_pack = {
            "research_object": {"value": "electric cupping massager"},
            "effective_products": [
                {
                    "asin": "B0CUPPING01",
                    "title": "Smart Electric Cupping Therapy Massager with Red Light Heat",
                    "title_cn": "智能电动拔罐理疗按摩器",
                    "segment_cn": "热敷红光电动拔罐器",
                    "brand": "TheraCup",
                    "price": 49.99,
                    "rating": 4.5,
                    "review_count": 320,
                    "estimated_monthly_sales": 1200,
                    "source_id": "src_product",
                }
            ],
            "effective_keywords": [
                {"keyword": "electric cupping massager", "keyword_cn": "电动拔罐按摩器", "source_id": "src_kw"},
                {"keyword": "red light therapy", "keyword_cn": "红光理疗", "source_id": "src_kw"},
                {"keyword": "back pain relief", "keyword_cn": "背部疼痛缓解", "source_id": "src_kw"},
            ],
            "effective_reviews": [
                {
                    "asin": "B0CUPPING01",
                    "rating": 5,
                    "title": "Works well on shoulder pain",
                    "text": "The suction and heat helped my shoulder and back after workouts.",
                    "themes": ["pain relief", "heat"],
                    "source_id": "src_review",
                }
            ],
            "effective_suppliers": [
                {
                    "title": "电动拔罐器红光热敷负压按摩仪",
                    "price": 35,
                    "seed_keyword": "电动拔罐器",
                    "source_id": "src_supplier",
                }
            ],
        }

        tags = renderer.generate_cosmo_alexa_tags(data_pack, {})
        tag_text = json.dumps(tags, ensure_ascii=False)

        for polluted in ["快速安装", "快速搭建", "清晨/傍晚观察", "户外活动日", "便携户外使用", "空间更充足"]:
            self.assertNotIn(polluted, tag_text)
        for expected in ["电动拔罐按摩器", "红光理疗", "背部疼痛"]:
            self.assertIn(expected, tag_text)

    def test_cosmo_cupping_context_blocks_setup_and_observation_terms_even_when_source_text_mentions_them(self):
        data_pack = {
            "research_object": {"value": "electric cupping massager"},
            "effective_products": [
                {
                    "title": "Electric cupping massager with heat suction, easy install charging base",
                    "title_cn": "电动拔罐按摩器",
                    "segment_cn": "电动拔罐按摩器",
                    "brand": "TheraCup",
                    "source_id": "src_product",
                }
            ],
            "effective_keywords": [
                {"keyword": "electric cupping massager morning routine", "keyword_cn": "电动拔罐按摩器", "source_id": "src_kw"}
            ],
            "effective_reviews": [
                {
                    "rating": 5,
                    "title": "I use it in the morning after workouts",
                    "text": "The suction and heat help my back and shoulders.",
                    "source_id": "src_review",
                }
            ],
            "effective_suppliers": [
                {"title": "电动拔罐器安装底座便携收纳套装", "seed_keyword": "电动拔罐器", "source_id": "src_supplier"}
            ],
        }

        tags = renderer.generate_cosmo_alexa_tags(data_pack, {})
        tag_text = json.dumps(tags, ensure_ascii=False)

        for polluted in ["快速搭建", "快速安装", "清晨/傍晚观察", "户外活动日", "隐蔽观察"]:
            self.assertNotIn(polluted, tag_text)

    def test_lifecycle_strategy_persists_priority_scores_for_audit(self):
        products = []
        for idx in range(12):
            products.append(
                {
                    "asin": f"B0CUP{idx:05d}",
                    "title": f"Electric Cupping Massager Red Light Therapy {idx}",
                    "title_cn": f"热敷红光电动拔罐器 {idx}",
                    "segment_cn": "热敷红光电动拔罐器",
                    "brand": "TheraCup",
                    "price": 39.99 + idx,
                    "rating": 4.4,
                    "review_count": 200 + idx,
                    "estimated_monthly_sales": 1000 - idx * 10,
                    "source_id": f"src_product_{idx}",
                }
            )
        data_pack = {
            "research_object": {"value": "electric cupping massager"},
            "effective_products": products,
            "effective_keywords": [{"keyword": "electric cupping massager", "keyword_cn": "电动拔罐按摩器"}],
            "effective_reviews": [{"rating": 5, "themes": ["pain relief"], "text": "Works for back pain."}],
            "effective_suppliers": [
                {"title": "电动拔罐器红光热敷负压按摩仪", "price": 35, "seed_keyword": "电动拔罐器"}
                for _ in range(60)
            ],
        }

        lifecycle = renderer.build_lifecycle_strategy_analysis(data_pack, {}, "src_fallback")
        pool = lifecycle["sku_candidate_pool"]

        self.assertGreaterEqual(len(pool), 12)
        self.assertTrue(all(isinstance(item.get("priority_score"), int) for item in pool))
        self.assertTrue(all(0 <= item["priority_score"] <= 100 for item in pool))
        self.assertTrue(all(item.get("priority_basis") for item in pool))

    def test_lifecycle_strategy_populates_decision_fields_for_recommended_skus(self):
        products = []
        for idx in range(12):
            products.append(
                {
                    "asin": f"B0CUP{idx:05d}",
                    "title": f"Smart Electric Cupping Therapy Massager with Heat Red Light {idx}",
                    "title_cn": f"热敷红光电动拔罐器 {idx}",
                    "brand": f"Brand{idx}",
                    "segment_cn": "热敷红光电动拔罐器",
                    "price": 29.99 + idx,
                    "rating": 4.4,
                    "review_count": 800 + idx,
                    "estimated_monthly_sales": 1200 - idx,
                    "source_id": f"src_product_{idx}",
                }
            )
        data_pack = {
            "research_object": {"value": "electric cupping massager"},
            "effective_products": products,
            "effective_suppliers": [
                {"title": f"电动拔罐器红光热敷负压按摩仪 {idx}", "price": 35 + idx, "price_rmb": 35 + idx, "seed_keyword": "电动拔罐器"}
                for idx in range(60)
            ],
        }

        lifecycle = renderer.build_lifecycle_strategy_analysis(data_pack, {}, "src_life")

        for sku in lifecycle["recommended_skus"]:
            self.assertIn(sku.get("strategy_type_key"), renderer.LIFECYCLE_TYPE_ORDER)
            self.assertTrue(sku.get("type_label_cn"))
            self.assertTrue(sku.get("price_band"))
            self.assertTrue(sku.get("supply_chain_status"))
            self.assertTrue(sku.get("supply_chain_anchor"))
            self.assertTrue(sku.get("reference_asin") or sku.get("supply_chain_status") == "仅供应端候选")

    def test_lifecycle_strategy_deduplicates_candidate_names_without_hiding_distinct_asins(self):
        products = []
        for idx in range(16):
            products.append(
                {
                    "asin": f"B0DUP{idx:05d}",
                    "title": f"Electric Cupping Massager Red Light Therapy Duplicate Naming Source {idx}",
                    "title_cn": "电动拔罐按摩器",
                    "brand": f"Brand{idx}",
                    "segment_cn": "热敷红光电动拔罐器",
                    "price": 39.99 + idx,
                    "rating": 4.4,
                    "review_count": 800 + idx,
                    "estimated_monthly_sales": 1200 - idx,
                    "source_id": f"src_product_{idx}",
                }
            )
        data_pack = {
            "research_object": {"value": "electric cupping massager"},
            "effective_products": products,
            "effective_suppliers": [
                {
                    "title": f"电动拔罐器红光热敷负压按摩仪 {idx}",
                    "price": 35 + idx,
                    "price_rmb": 35 + idx,
                    "seed_keyword": "电动拔罐器",
                    "url": f"https://detail.1688.com/offer/{idx}.html",
                }
                for idx in range(60)
            ],
        }

        lifecycle = renderer.build_lifecycle_strategy_analysis(data_pack, {}, "src_life")
        names = [sku.get("name") for sku in lifecycle["sku_candidate_pool"]]

        self.assertEqual(len(names), len(set(names)))
        self.assertGreaterEqual(len(lifecycle["sku_candidate_pool"]), 12)
        self.assertEqual(len({sku.get("reference_asin") for sku in lifecycle["sku_candidate_pool"] if sku.get("reference_asin")}), 16)

    def test_lifecycle_recommended_skus_exclude_underfilled_segments(self):
        products = []
        for idx in range(11):
            products.append(
                {
                    "asin": f"B0MAIN{idx:05d}",
                    "title": f"Main Segment Electric Cupping Massager {idx}",
                    "title_cn": f"主赛道电动拔罐器 {idx}",
                    "brand": "MainBrand",
                    "segment_cn": "主赛道拔罐器",
                    "price": 39.99,
                    "rating": 4.5,
                    "review_count": 900,
                    "estimated_monthly_sales": 1000 - idx,
                }
            )
        products.append(
            {
                "asin": "B0TINY00001",
                "title": "Tiny Segment Lymphatic Drainage Device",
                "title_cn": "小样本淋巴引流负压仪",
                "brand": "TinyBrand",
                "segment_cn": "小样本淋巴引流负压仪",
                "price": 89.99,
                "rating": 4.8,
                "review_count": 5000,
                "estimated_monthly_sales": 9999,
            }
        )
        data_pack = {
            "research_object": {"value": "electric cupping massager"},
            "effective_products": products,
            "effective_suppliers": supplier_rows(60),
        }

        lifecycle = renderer.build_lifecycle_strategy_analysis(data_pack, {}, "src_life")
        recommended_text = json.dumps(lifecycle["recommended_skus"], ensure_ascii=False)
        pool_tiny = [sku for sku in lifecycle["sku_candidate_pool"] if sku.get("target_segment") == "小样本淋巴引流负压仪"]

        self.assertNotIn("小样本淋巴引流负压仪", recommended_text)
        self.assertTrue(pool_tiny)
        self.assertTrue(all(sku.get("segment_status") == "需验证赛道" for sku in pool_tiny))

    def test_lifecycle_ecosystem_nodes_expand_from_candidate_pool(self):
        products = [
            {
                "asin": f"B0LIFE{idx:04d}",
                "title": f"Electric Cupping Massager Set {idx}",
                "title_cn": "热敷红光电动拔罐器",
                "brand": f"Brand {idx}",
                "segment_cn": "热敷红光电动拔罐器" if idx < 12 else "套装型电动拔罐器",
                "price": 39.99 + idx,
                "rating": 4.4,
                "review_count": 100 + idx,
                "estimated_monthly_sales": 900 - idx,
                "main_image_url": f"https://m.media-amazon.com/images/I/life{idx}.jpg",
            }
            for idx in range(24)
        ]
        suppliers = [
            {
                "title": f"电动拔罐器热敷红光成品 {idx}",
                "supplier_name": f"供应商 {idx}",
                "url": f"https://detail.1688.com/offer/{idx}.html",
                "price_rmb": 20 + idx,
                "seed_keyword": "电动拔罐器",
            }
            for idx in range(30)
        ]

        lifecycle = renderer.build_lifecycle_strategy_analysis(
            {"research_object": {"value": "electric cupping massager"}, "products": products, "suppliers": suppliers},
            {},
            "src_life",
        )

        ecosystem = lifecycle["ecosystem_nodes"]
        self.assertGreater(len(ecosystem.get("paths") or []), 1)
        self.assertGreater(len(ecosystem.get("segments") or []), 3)
        self.assertIn("children", ecosystem)
        first_path = ecosystem["children"][0]
        self.assertIn("children", first_path)
        self.assertTrue(any((segment.get("children") or []) for segment in first_path["children"]))

    def test_product_image_url_rejects_urls_with_embedded_whitespace_and_uses_valid_alternative(self):
        product = {
            "image_url": "https://m.media-amazon.com/images/I/71bad image.jpg",
            "images": [
                "https://detail.1688.com/offer/not-amazon.jpg",
                "https://m.media-amazon.com/images/I/71valid.jpg",
            ],
        }

        self.assertEqual(renderer.product_image_url(product), "https://m.media-amazon.com/images/I/71valid.jpg")

    def test_diagnostic_child_reports_keep_standard_slot_density(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(
                root / "data" / "data_pack.json",
                {
                    "research_object": {"value": "electric cupping massager"},
                    "sources": [{"source_id": "src_001", "provider": "sorftime"}],
                    "products": competitor_rows(30),
                    "keywords": [{"keyword": f"cupping {idx}", "keyword_cn": f"拔罐 {idx}"} for idx in range(200)],
                    "reviews": [],
                    "suppliers": supplier_rows(50),
                },
            )
            write_json(
                root / "data" / "normalized" / "data_readiness_report.json",
                {
                    "acceptance_ready": False,
                    "blocking_gaps": [
                        {
                            "module": "keyword_sample_depth",
                            "current": 200,
                            "required": 1000,
                            "reason": "关键词样本不足。",
                            "next_step": "补充有效去重关键词。",
                        }
                    ],
                    "counts": {"products": 30, "keywords": 200, "reviews": 0, "suppliers": 50, "valid_supplier_quotes": 50},
                },
            )
            result = self.run_renderer(root, "--no-recover")
            self.assertNotEqual(result.returncode, 0)

            for filename in ["market-depth-report.html", "lifecycle-strategy-report.html", "demand-gap-report.html"]:
                html = (root / "output" / "html_reports" / filename).read_text(encoding="utf-8")
                self.assertIn("diagnostic-slot-grid", html)
                self.assertGreaterEqual(html.count("diagnostic-slot-card"), 6)
                self.assertIn("diagnostic-slot-status", html)
                self.assertIn("标准报告结构", html)

    def test_diagnostic_child_reports_keep_full_template_section_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_pack = {
                "research_object": {"value": "ai plush toy"},
                "sources": [{"source_id": "src_001", "provider": "sorftime"}],
                "effective_products": competitor_rows(30, include_images=True),
                "effective_keywords": [{"keyword": f"cupping {idx}", "keyword_cn": f"拔罐 {idx}"} for idx in range(611)],
                "effective_reviews": [],
                "effective_suppliers": supplier_rows(50),
                "quality": {"overall_score": 0.4, "grade": "D"},
            }
            readiness = {
                "acceptance_ready": False,
                "partial_report_ready": False,
                "sample_class": "non_acceptance_sample",
                "blocking_gaps": [
                    {
                        "module": "market_segment_depth",
                        "reason": "部分细分赛道有效竞品不足 10 个。",
                        "next_step": "补采低样本赛道竞品。",
                    }
                ],
                "counts": {"valid_competitors": 30, "market_segments": 4, "keywords": 611, "reviews": 0, "suppliers": 50, "valid_supplier_quotes": 50},
                "competitor_gate": {"minimum_total": 30, "minimum_per_primary_segment": 10, "passed": False},
                "segment_gate": {"minimum_per_primary_segment": 10, "passed": False},
                "supplier_quote_gate": {"required": 50, "passed": True},
                "supplier_quality_gate": {"title_coverage_pct": 100, "field_quality_passed": True},
            }

            renderer.write_readiness_diagnostic_bundle(root, data_pack, {}, readiness)

            expectations = {
                "market-depth-report.html": ["大盘仪表盘", "COSMO + Alexa 标签识别", "Top 竞品全景扫描", "VOC 体验深潜", "TikTok 趋势信号", "供应链成本估算"],
                "lifecycle-strategy-report.html": ["战略仪表盘", "四维拓品生态", "拓品方案池", "Bundle 策略", "风险矩阵"],
                "demand-gap-report.html": ["目标ASIN锚点", "决策看板", "市场痛点全景图", "KANO × JTBD", "用户原声"],
            }
            for filename, labels in expectations.items():
                html = (root / "output" / "html_reports" / filename).read_text(encoding="utf-8")
                self.assertGreaterEqual(html.count("<section"), len(labels))
                for label in labels:
                    self.assertIn(label, html)
                self.assertIn('id="', html)
                self.assertGreaterEqual(html.count('class="nav-link"'), 3)

    def test_diagnostic_child_reports_keep_standard_section_anchors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_pack = {
                "research_object": {"value": "electric cupping massager"},
                "sources": [{"source_id": "src_001", "provider": "sorftime"}],
                "effective_products": competitor_rows(30, include_images=True),
                "effective_keywords": [{"keyword": f"cupping {idx}", "keyword_cn": f"拔罐 {idx}"} for idx in range(611)],
                "effective_reviews": [{"summary_cn": "评论归纳"} for _ in range(80)],
                "effective_suppliers": supplier_rows(55),
                "quality": {"overall_score": 0.4, "grade": "D"},
            }
            readiness = {
                "acceptance_ready": False,
                "partial_report_ready": False,
                "sample_class": "non_acceptance_sample",
                "blocking_gaps": [
                    {
                        "module": "market_segment_depth",
                        "reason": "部分细分赛道有效竞品不足 10 个。",
                        "next_step": "补采低样本赛道竞品。",
                    }
                ],
                "counts": {"valid_competitors": 30, "keywords": 611, "reviews": 80, "suppliers": 55, "valid_supplier_quotes": 55},
            }

            renderer.write_readiness_diagnostic_bundle(root, data_pack, {}, readiness)

            expected_anchors = {
                "market-depth-report.html": [
                    "market-dashboard",
                    "cosmo-alexa-tags",
                    "competitor-scan",
                    "voc-deep-dive",
                    "benchmark-sniper",
                    "product-definition",
                    "pricing",
                    "visual-direction",
                    "prompt",
                    "tiktok-trends",
                    "supply-chain",
                ],
                "lifecycle-strategy-report.html": [
                    "strategy-dashboard",
                    "lifecycle-personas",
                    "lifecycle-journey",
                    "lifecycle-ecosystem",
                    "sku-strategy-pool",
                    "bundle-strategy",
                    "risk-matrix",
                ],
                "demand-gap-report.html": [
                    "target-anchor",
                    "decision-board",
                    "appeals-map",
                    "gap-analysis",
                    "kano-jtbd",
                    "voice-theater",
                    "priority-table",
                ],
            }
            for filename, anchors in expected_anchors.items():
                html = (root / "output" / "html_reports" / filename).read_text(encoding="utf-8")
                for anchor in anchors:
                    self.assertIn(f'id="{anchor}"', html, f"{filename} should preserve standard anchor {anchor}")
                    self.assertIn(f'href="#{anchor}"', html, f"{filename} slot grid should link to standard anchor {anchor}")
                self.assertNotIn('id="diagnostic-slot-02-cosmo-alexa-标签识别"', html)

    def test_diagnostic_child_reports_keep_component_skeletons_not_only_slot_cards(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_pack = {
                "research_object": {"value": "ai plush toy"},
                "sources": [{"source_id": "src_001", "provider": "sorftime"}],
                "effective_products": competitor_rows(30, include_images=True),
                "effective_keywords": [{"keyword": f"cupping {idx}", "keyword_cn": f"拔罐 {idx}"} for idx in range(611)],
                "effective_reviews": [{"summary_cn": "评论归纳"} for _ in range(80)],
                "effective_suppliers": supplier_rows(55),
                "quality": {"overall_score": 0.4, "grade": "D"},
            }
            readiness = {
                "acceptance_ready": False,
                "partial_report_ready": False,
                "sample_class": "non_acceptance_sample",
                "blocking_gaps": [
                    {
                        "module": "market_segment_depth",
                        "reason": "部分细分赛道有效竞品不足 10 个。",
                        "next_step": "补采低样本赛道竞品。",
                    }
                ],
                "counts": {"valid_competitors": 30, "market_segments": 4, "keywords": 611, "reviews": 80, "suppliers": 55, "valid_supplier_quotes": 55},
                "competitor_gate": {"minimum_total": 30, "minimum_per_primary_segment": 10, "passed": False},
                "segment_gate": {"minimum_per_primary_segment": 10, "passed": False},
                "supplier_quote_gate": {"required": 50, "passed": True},
                "supplier_quality_gate": {"title_coverage_pct": 100, "field_quality_passed": True, "customer_visible_passed": True, "passed": True},
            }

            renderer.write_readiness_diagnostic_bundle(root, data_pack, {}, readiness)

            market_html = (root / "output" / "html_reports" / "market-depth-report.html").read_text(encoding="utf-8")
            lifecycle_html = (root / "output" / "html_reports" / "lifecycle-strategy-report.html").read_text(encoding="utf-8")
            demand_html = (root / "output" / "html_reports" / "demand-gap-report.html").read_text(encoding="utf-8")

            for token in [
                "cosmo-diagnostic-shell",
                "comp-image-strip-card",
                "market-voc-sentiment-columns",
                "tiktok-diagnostic-card",
                "supply-grid",
                "prompt-card",
            ]:
                self.assertIn(token, market_html)
            self.assertEqual(market_html.count("cosmo-matrix-cell"), 15)
            self.assertIn("产品标签 · 产品被算法识别为什么", market_html)
            self.assertIn("用户标签 · 用户为什么搜索/购买", market_html)
            for raw_relation in ["USED_FOR_FUNC", "CAPABLE_OF", "USED_IN_LOC", "xWANT", "xINTERSTED_IN"]:
                self.assertNotIn(raw_relation, market_html)
            self.assertIn("<img", market_html)
            self.assertIn("test-competitor-", market_html)
            for placeholder in ["待验证", "待补", "暂无"]:
                self.assertNotIn(placeholder, market_html)
            for token in ["lifecycle-ecosystem", "sku-priority", "sku-pool-table", "bundle-card"]:
                self.assertIn(token, lifecycle_html)
            self.assertIn('id="lifecycleSunburst"', lifecycle_html)
            self.assertIn('id="priorityChart"', lifecycle_html)
            self.assertIn('data-chart-disabled="true"', lifecycle_html)
            self.assertIn("补齐门禁后输出候选池评分", lifecycle_html)
            for token in ["demand-evidence", "voice-card", "kano-jtbd-grid", "demand-priority-grid"]:
                self.assertIn(token, demand_html)
            self.assertGreater(market_html.count("diagnostic-slot-card"), 0)
            self.assertNotIn("图片加载失败", market_html + lifecycle_html + demand_html)

    def test_diagnostic_pages_use_readiness_competitor_counts_without_ambiguous_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            products = competitor_rows(30)
            products.extend(
                {
                    "asin": f"B0PARTIAL{idx:02d}",
                    "title": f"Electric cupping partial competitor {idx}",
                    "title_cn": "电动拔罐器相关产品",
                    "brand": "PartialBrand",
                    "segment_cn": "热敷红光电动拔罐器",
                    "price": 29.99,
                    "rating": 0,
                    "review_count": 0,
                    "estimated_monthly_sales": 5,
                }
                for idx in range(8)
            )
            data_pack = {
                "research_object": {"value": "electric cupping massager"},
                "sources": [{"source_id": "src_001", "provider": "sorftime"}],
                "effective_products": products,
                "effective_keywords": [{"keyword": f"cupping {idx}", "keyword_cn": f"拔罐 {idx}"} for idx in range(534)],
                "effective_reviews": [{"summary_cn": "评论归纳"} for _ in range(320)],
                "effective_suppliers": supplier_rows(201),
                "quality": {"overall_score": 0.72, "grade": "B"},
            }
            readiness = {
                "acceptance_ready": False,
                "partial_report_ready": False,
                "sample_class": "non_acceptance_sample",
                "blocking_gaps": [
                    {
                        "module": "market_segment_depth",
                        "reason": "部分细分赛道有效竞品不足 10 个。",
                        "next_step": "补采低数据记录赛道竞品。",
                    }
                ],
                "counts": {
                    "keywords": 534,
                    "valid_competitors": 30,
                    "market_segments": 4,
                    "reviews": 320,
                    "suppliers": 201,
                    "valid_supplier_quotes": 199,
                },
                "competitor_gate": {"minimum_total": 30, "passed": False},
                "segment_gate": {"minimum_per_primary_segment": 10, "passed": False},
                "supplier_quote_gate": {"required": 50, "passed": True},
                "supplier_quality_gate": {"title_coverage_pct": 100, "field_quality_passed": True},
            }

            renderer.write_readiness_diagnostic_bundle(root, data_pack, {}, readiness)

            combined_html = "\n".join(
                (root / "output" / "html_reports" / filename).read_text(encoding="utf-8")
                for filename in ["report.html", "market-depth-report.html", "lifecycle-strategy-report.html", "demand-gap-report.html"]
            )
            self.assertIn("合格竞品 30", combined_html)
            self.assertIn("相关产品覆盖 8", combined_html)
            self.assertNotIn("相关产品覆盖 38", combined_html)
            self.assertNotIn("竞品 38", combined_html)
            self.assertIn("每个主赛道≥10", combined_html)
            self.assertNotIn("<td>细分赛道</td><td>4</td><td>0</td>", combined_html)
            self.assertIn("数量通过；完整结论受其他门禁阻断", combined_html)
            self.assertIn("字段通过；完整结论受其他门禁阻断", combined_html)
            self.assertNotIn("局部通过", combined_html)
            self.assertNotIn("<td>1688有效报价</td><td>199</td><td>50</td><td>通过</td>", combined_html)

    def test_diagnostic_slots_use_module_specific_metrics_and_copy(self):
        def section(html: str, title: str) -> str:
            marker = f'<h2 class="section-title">{title}</h2>'
            start = html.index(marker)
            next_start = html.find('<section id="diagnostic-slot-', start + len(marker))
            return html[start:] if next_start == -1 else html[start:next_start]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            readiness = {
                "acceptance_ready": False,
                "partial_report_ready": False,
                "sample_class": "non_acceptance_sample",
                "blocking_gaps": [
                    {
                        "module": "competitor_pool_depth",
                        "reason": "有效竞品池不足。",
                        "next_step": "补采同类竞品。",
                    }
                ],
                "counts": {
                    "valid_competitors": 32,
                    "keywords": 916,
                    "reviews": 214,
                    "valid_supplier_quotes": 9,
                    "tiktok_products": 7,
                    "sku_candidates": 18,
                },
            }
            data_pack = {
                "research_object": {"value": "generic product"},
                "effective_products": competitor_rows(32, include_images=True),
                "effective_keywords": [{"keyword": f"term {idx}", "keyword_cn": f"中文词 {idx}"} for idx in range(20)],
                "effective_reviews": [{"summary_cn": "评论归纳"} for _ in range(12)],
                "effective_suppliers": supplier_rows(9),
                "quality": {"overall_score": 0.55, "grade": "D"},
            }

            renderer.write_readiness_diagnostic_bundle(root, data_pack, {}, readiness)

            market_html = (root / "output" / "html_reports" / "market-depth-report.html").read_text(encoding="utf-8")
            lifecycle_html = (root / "output" / "html_reports" / "lifecycle-strategy-report.html").read_text(encoding="utf-8")
            demand_html = (root / "output" / "html_reports" / "demand-gap-report.html").read_text(encoding="utf-8")
            index_html = (root / "output" / "html_reports" / "report.html").read_text(encoding="utf-8")
            combined_html = index_html + market_html + lifecycle_html + demand_html

            self.assertIn('<div class="diagnostic-slot-metric">合格竞品 32</div>', section(market_html, "Top 竞品全景扫描"))
            self.assertIn('<div class="diagnostic-slot-metric">关键词 916</div>', section(market_html, "COSMO + Alexa 标签识别"))
            self.assertIn('<div class="diagnostic-slot-metric">评论 214</div>', section(market_html, "VOC 体验深潜"))
            self.assertIn('<div class="diagnostic-slot-metric">有效报价 9</div>', section(market_html, "供应链成本估算"))
            self.assertIn('<div class="diagnostic-slot-metric">TikTok信号 7</div>', section(market_html, "TikTok 趋势信号"))
            self.assertIn('<div class="diagnostic-slot-metric">SKU候选 18</div>', section(lifecycle_html, "拓品方案池"))
            self.assertIn('<div class="diagnostic-slot-metric">评论 214</div>', section(demand_html, "用户原声"))
            self.assertNotIn("当前只展示门禁状态、可用数据覆盖和补采动作，暂不输出结论。", combined_html)
            self.assertNotIn("补齐阻断项后重新分析，并在本模块输出图表、表格和结论", combined_html)
            self.assertNotIn("本节保留标准版结构，只展示当前门禁状态和下一步动作。", combined_html)
            self.assertNotIn("当前数据未达决策门槛，本模块只显示诊断和补采动作。", combined_html)
            self.assertNotIn("Pain 主要痛点", combined_html)
            self.assertNotIn("Joy 主要爽点", combined_html)
            self.assertNotIn("PROMPT 01", combined_html)
            self.assertNotIn("PROMPT 02", combined_html)
            self.assertNotIn("PROMPT 03", combined_html)
            self.assertNotIn("当前只展示", combined_html)
            self.assertNotIn("本节只展示", combined_html)

    def test_blocked_diagnostic_overwrites_stale_critic_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(
                root / "data" / "data_pack.json",
                {
                    "research_object": {"value": "electric cupping massager"},
                    "sources": [{"source_id": "src_001", "provider": "sorftime"}],
                    "products": competitor_rows(30),
                    "keywords": [{"keyword": f"cupping {idx}", "keyword_cn": f"拔罐 {idx}"} for idx in range(200)],
                    "reviews": [],
                    "suppliers": supplier_rows(50),
                },
            )
            write_json(root / "analysis" / "critic_decision.json", {"decision": "Watch", "pass": True, "score": 88})

            result = self.run_renderer(root, "--no-recover")

            self.assertNotEqual(result.returncode, 0)
            critic_decision = json.loads((root / "analysis" / "critic_decision.json").read_text(encoding="utf-8"))
            self.assertEqual(critic_decision["decision"], "No-Go")
            self.assertFalse(critic_decision["pass"])
            self.assertEqual(critic_decision["status"], "not_run_data_readiness_blocked")

    def test_demand_template_uses_shared_report_header_structure(self):
        template = (renderer.SKILL_DIR / "assets" / "demand-gap-template.html").read_text(encoding="utf-8")

        self.assertRegex(template, r'<header\b[^>]*class="[^"]*\breport-header\b')
        self.assertIn("{{DEMAND_REPORT_TITLE}}", template)
        self.assertNotIn('<section class="hero">', template)

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
            self.assertEqual(delivery["decision"], "Watch")
            self.assertTrue(delivery["data_readiness"]["partial_report_ready"])
            combined_html = "\n".join(
                (report_dir / "output" / "html_reports" / name).read_text(encoding="utf-8")
                for name in [
                    "report.html",
                    "market-depth-report.html",
                    "lifecycle-strategy-report.html",
                    "demand-gap-report.html",
                ]
            )
            self.assertIn("供应链测算未达门槛", combined_html)
            self.assertIn("诊断交付", combined_html)
            for forbidden in ["证据充分", "供应链可控度较高", "门禁通过", "可控供应链", "首发可控 SKU", "50+ 条成品报价可进入打样复核", "毛利率可测算"]:
                self.assertNotIn(forbidden, combined_html)

    def test_lifecycle_sku_table_defaults_to_top_window_and_folds_full_pool(self):
        skus = [
            {
                "id": f"SKU-{idx:03d}",
                "type": "A" if idx % 4 == 0 else "B" if idx % 4 == 1 else "C" if idx % 4 == 2 else "D",
                "phase": "P1",
                "name": f"候选方案 {idx}",
                "target_segment": "核心赛道",
                "reference_asin": f"B0SKU{idx:05d}",
                "reference_competitor": "标杆竞品",
                "price": "$39-$59",
                "supply": "仅竞品/VOC 候选，供应链待核实",
                "priority": 100 - idx,
                "source_id": "src_001",
            }
            for idx in range(1, 81)
        ]

        html = renderer.render_sku_execution_table(skus, "src_001")

        self.assertIn("默认展示 Top", html)
        self.assertIn("完整候选池", html)
        self.assertIn("<details", html)
        self.assertLessEqual(html.split('id="skuBody"', 1)[1].split("</tbody>", 1)[0].count("<tr"), 15)
        self.assertIn("仅竞品/VOC 候选", html)
        self.assertNotIn("Type A", html)

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
            {"asin": "B0LIGHT001", "keyword": "under cabinet lighting", "customer_label_cn": "橱柜灯", "monthly_search_volume": 1000},
            {"asin": "B0LIGHT001", "keyword": "kitchen cabinet lights", "customer_label_cn": "橱柜灯", "keyword_cn": "未映射关键词：kitchen cabinet lights", "monthly_search_volume": 900},
            {"asin": "B0LIGHT001", "keyword": "ring camera", "monthly_search_volume": 800},
            {"asin": "B0LIGHT001", "keyword": "motion sensor light", "customer_label_cn": "感应灯", "monthly_search_volume": 700},
            {"asin": "B0LIGHT001", "keyword": "flashlight", "customer_label_cn": "户外便携灯", "keyword_cn": "未映射关键词：flashlight", "monthly_search_volume": 600},
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
        products = [
            {**product, "segment_cn": "橱柜感应灯", "title_cn": "厨房橱柜感应灯"}
            for product in competitor_rows(30)
        ]
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
        data_pack = {
            "research_object": {"type": "keyword", "value": "橱柜感应灯"},
            "products": products,
            "keywords": [{"keyword_cn": "橱柜感应灯", "keyword": "under cabinet light"}],
            "suppliers": stable_suppliers + mixed_outliers,
        }

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

    def test_data_readiness_blocks_low_keyword_chinese_mapping_coverage(self):
        keywords = [
            {"keyword": f"electric cupping keyword {idx}", "keyword_cn": f"未映射关键词：electric cupping keyword {idx}"}
            for idx in range(100)
        ]

        gate = check_data_readiness.keyword_mapping_quality(keywords)

        self.assertFalse(gate["passed"])
        self.assertLess(gate["mapping_coverage_pct"], gate["required_mapping_coverage_pct"])

    def test_data_readiness_filters_cupping_accessories_from_finished_supplier_quotes(self):
        bad_rows = [
            {"title": "拔罐器抽气枪双色拔罐枪硅胶大号配件", "price_rmb": 10, "supplier_name": "配件厂"},
            {"title": "硅胶面部拔罐器小儿吸湿拨罐器", "price_rmb": 0.68, "supplier_name": "美容工具厂"},
            {"title": "玻璃火罐家用拔罐器散装", "price_rmb": 1.2, "supplier_name": "火罐厂"},
        ]
        good_row = {"title": "电动拔罐器红光热敷负压按摩器成品套装", "price_rmb": 32, "supplier_name": "成品厂"}

        self.assertTrue(check_data_readiness.is_finished_supplier_quote(good_row))
        for row in bad_rows:
            with self.subTest(row=row["title"]):
                self.assertFalse(check_data_readiness.is_finished_supplier_quote(row))

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
        prompt_texts = re.findall(r'<div class="prompt-text">(.*?)</div>', prompt_html)
        self.assertEqual(len(prompt_texts), 3)
        self.assertEqual(len(set(prompt_texts)), 3)
        self.assertRegex(prompt_texts[0], r"Photorealistic Amazon product photography")
        self.assertRegex(prompt_texts[1], r"realistic lifestyle scene|visible selling point")
        self.assertRegex(prompt_texts[2], r"premium bundle scene|organized unboxing")
        for text in prompt_texts:
            self.assertRegex(text, r"scene:|composition:|no text|no watermark|no distorted product")
            self.assertNotRegex(text, r"生成一张|商品方向：|把该机会写入")

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

    def test_market_prompt_body_carries_current_opportunity_context(self):
        html = renderer.render_visual_direction(
            {
                "opportunities": [
                    {"name": "透视地面盲棚 入门验证款"},
                    {"name": "透视地面盲棚 差异化主力款"},
                    {"name": "透视地面盲棚 高溢价套装款"},
                ]
            }
        )

        prompt_texts = re.findall(r'<div class="prompt-text">(.*?)</div>', html)

        self.assertEqual(len(prompt_texts), 3)
        self.assertIn("透视地面盲棚 入门验证款", prompt_texts[0])
        self.assertIn("透视地面盲棚 差异化主力款", prompt_texts[1])
        self.assertIn("透视地面盲棚 高溢价套装款", prompt_texts[2])

    def test_market_supply_uses_reference_order_and_no_free_floating_cost_metrics(self):
        products = [
            {**product, "segment_cn": "橱柜感应灯", "title_cn": "厨房橱柜感应灯"}
            for product in competitor_rows(30)
        ]
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

        html = renderer.render_supply(
            {
                "research_object": {"type": "keyword", "value": "橱柜感应灯"},
                "products": products,
                "keywords": [{"keyword_cn": "橱柜感应灯", "keyword": "under cabinet light"}],
                "suppliers": suppliers,
            },
            {},
        )

        self.assertEqual(html.count('class="supply-card'), 4)
        self.assertLess(html.find("supply-grid"), html.find('id="marginChart"'))
        self.assertLess(html.find('id="marginChart"'), html.find("profitability-table"))
        self.assertNotIn("metric-strip", html)
        self.assertNotIn("P25采购成本", html)
        self.assertIn("1688 成本分位数", html)
        self.assertIn("供应链核心结论", html)

    def test_market_supply_blocked_uses_diagnostic_chart_not_profit_series(self):
        suppliers = [
            {
                "title": f"狩猎盲棚供应记录 {idx}",
                "supplier_name": f"供应商 {idx}",
                "url": f"https://detail.1688.com/offer/{idx}.html",
                "price_rmb": 120 + idx,
                "seed_keyword": "狩猎盲棚",
            }
            for idx in range(9)
        ]

        html = renderer.render_supply(
            {
                "research_object": {"type": "asin", "value": "B0BR4QYGS7"},
                "products": competitor_rows(30),
                "suppliers": suppliers,
            },
            {},
        )

        self.assertIn('id="marginChart"', html)
        self.assertIn('data-chart-disabled="true"', html)
        self.assertIn("diagnostic-chart-item", html)
        self.assertIn("供应链测算未达门槛", html)
        self.assertNotIn('data-chart-source="marginChartRows"', html)
        self.assertNotIn("毛利率测算 · 各定价方案对比", html)

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

    def test_competitor_modules_render_product_images_when_available(self):
        products = competitor_rows(30)
        products[-1]["image_url"] = "https://images-na.ssl-images-amazon.com/images/I/example-a.jpg"
        products[-2]["main_image"] = "https://m.media-amazon.com/images/I/example-b.jpg"
        products[-3]["images"] = ["https://m.media-amazon.com/images/I/example-c.jpg"]

        table_html, cards_html, filtered = renderer.render_competitors({"products": products})
        deep_html = renderer.render_product_deep_dives(filtered, [])

        self.assertIn('class="comp-product-thumb"', table_html)
        self.assertIn('src="https://images-na.ssl-images-amazon.com/images/I/example-a.jpg"', table_html)
        self.assertIn('src="https://m.media-amazon.com/images/I/example-b.jpg"', table_html)
        self.assertIn('src="https://m.media-amazon.com/images/I/example-c.jpg"', deep_html)
        self.assertIn('class="comp-image-strip"', cards_html)
        self.assertNotIn("src=\"\"", table_html + cards_html + deep_html)

    def test_competitor_images_have_silent_load_failure_fallback(self):
        products = competitor_rows(30)
        products[-1]["image_url"] = "https://m.media-amazon.com/images/I/example-a.jpg"

        table_html, cards_html, filtered = renderer.render_competitors({"products": products})
        deep_html = renderer.render_product_deep_dives(filtered, [])
        combined = table_html + cards_html + deep_html

        self.assertIn("this.parentElement.classList.add('image-frame-missing')", combined)
        self.assertIn('role="img" aria-label="竞品图片槽位"', combined)
        self.assertIn('class="image-load-fallback"', combined)
        self.assertIn('class="image-load-fallback" hidden></span>', combined)
        self.assertNotIn("display:inline-flex", combined)
        self.assertNotIn("竞品图片未返回", combined)
        self.assertNotIn("参考竞品图片未返回", combined)
        self.assertNotIn("图片加载失败", combined)
        self.assertNotIn("broken image", combined.lower())

    def test_competitor_modules_do_not_render_broken_images_when_image_urls_missing(self):
        table_html, cards_html, filtered = renderer.render_competitors({"products": competitor_rows(30)})
        deep_html = renderer.render_product_deep_dives(filtered, [])

        self.assertNotIn("<img", table_html + cards_html + deep_html)
        self.assertNotIn("src=\"\"", table_html + cards_html + deep_html)
        self.assertIn("图片维度未返回可展示 URL", cards_html)
        self.assertIn("comp-product-thumb-empty", table_html)
        self.assertIn("comp-deep-image-empty", deep_html)
        self.assertNotIn("采集层未返回 Amazon 可展示主图", table_html + deep_html)
        self.assertNotIn("标杆竞品图片未返回", deep_html)
        self.assertNotIn("image_url", cards_html)
        self.assertNotIn("main_image", cards_html)
        self.assertNotIn("photo 字段", cards_html)
        self.assertIn("商品主图链接或可展示图片", cards_html)

    def test_competitor_modules_render_product_detail_enrichment_images(self):
        products = competitor_rows(30)
        products[-1]["sorftime_enrichment"] = {
            "detail_image_url": "https://m.media-amazon.com/images/I/detail-image.jpg"
        }

        table_html, cards_html, filtered = renderer.render_competitors({"products": products})
        deep_html = renderer.render_product_deep_dives(filtered, [])

        self.assertIn('src="https://m.media-amazon.com/images/I/detail-image.jpg"', table_html + cards_html + deep_html)
        self.assertIn('class="comp-product-thumb"', table_html)

    def test_competitor_modules_reject_whitespace_corrupted_amazon_image_urls(self):
        products = competitor_rows(30)
        products[-1]["image_url"] = "https://m.media-amazon.com/images/I/bad image.jpg"

        table_html, cards_html, filtered = renderer.render_competitors({"products": products})
        deep_html = renderer.render_product_deep_dives(filtered, [])

        combined = table_html + cards_html + deep_html
        self.assertNotIn("bad image.jpg", combined)
        self.assertNotIn("<img", combined)
        self.assertIn("图片维度未返回可展示 URL", cards_html)

    def test_lifecycle_reference_images_have_load_failure_fallback(self):
        html = renderer.sku_reference_image_html(
            {
                "reference_image_url": "https://m.media-amazon.com/images/I/lifecycle.jpg",
                "reference_competitor": "B0REF12345 · 标杆竞品",
                "name": "主品验证款",
            }
        )

        self.assertIn('class="sku-reference-thumb"', html)
        self.assertIn(
            "this.parentElement.classList.add('image-frame-missing')",
            html,
        )
        self.assertIn('class="image-load-fallback"', html)
        self.assertIn('class="image-load-fallback" hidden>', html)
        self.assertIn('aria-label="参考竞品图片槽位"', html)
        self.assertNotIn("display:inline-flex", html)
        self.assertNotIn("参考竞品图片未返回", html)
        self.assertNotIn("未返回</span>", html)
        self.assertNotIn("图片加载失败", html)

    def test_competitor_modules_reject_1688_supplier_images_as_amazon_competitor_images(self):
        products = competitor_rows(30)
        products[-1]["image_url"] = "https://cbu01.alicdn.com/img/ibank/example.jpg"
        products[-2]["main_image"] = "https://detail.1688.com/offer/123456.html"
        products[-3]["sorftime_enrichment"] = {
            "detail_image_url": "https://img.alicdn.com/imgextra/example.jpg"
        }

        table_html, cards_html, filtered = renderer.render_competitors({"products": products})
        deep_html = renderer.render_product_deep_dives(filtered, [])

        combined = table_html + cards_html + deep_html
        self.assertNotIn("alicdn.com", combined)
        self.assertNotIn("detail.1688.com", combined)
        self.assertNotIn("<img", combined)
        self.assertIn("图片维度未返回可展示 URL", cards_html)

    def test_competitor_modules_reject_non_amazon_external_images(self):
        products = competitor_rows(30)
        products[-1]["image_url"] = "https://cdn.example-shop.com/product/example.jpg"
        products[-2]["main_image"] = "https://images.example.com/competitor.jpg"

        table_html, cards_html, filtered = renderer.render_competitors({"products": products})
        deep_html = renderer.render_product_deep_dives(filtered, [])

        combined = table_html + cards_html + deep_html
        self.assertNotIn("cdn.example-shop.com", combined)
        self.assertNotIn("images.example.com", combined)
        self.assertNotIn("<img", combined)
        self.assertIn("图片维度未返回可展示 URL", cards_html)

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

    def test_lifecycle_skus_preserve_and_render_reference_competitor_images(self):
        products = [
            {
                "asin": "B0BLINDIMG1",
                "title": "Pop Up Hunting Blind See Through Ground Blind",
                "brand": "FUNHORUN",
                "segment_cn": "透视地面盲棚",
                "price": 87.98,
                "estimated_monthly_sales": 349,
                "rating": 4.5,
                "review_count": 1087,
                "image_url": "https://m.media-amazon.com/images/I/blind-main.jpg",
            },
            {
                "asin": "B0SUPPLYIMG",
                "title": "Portable Hunting Blind Ground Blind",
                "brand": "SupplierLeak",
                "segment_cn": "弹出式地面盲棚",
                "price": 76.49,
                "estimated_monthly_sales": 320,
                "rating": 4.4,
                "review_count": 900,
                "image_url": "https://cbu01.alicdn.com/img/ibank/supplier.jpg",
            },
        ]

        lifecycle = renderer.build_lifecycle_strategy_analysis({"products": products}, {}, "src_img")
        html = renderer.render_sku_execution_table(lifecycle["sku_candidate_pool"], "src_img")

        self.assertEqual(lifecycle["sku_candidate_pool"][0]["reference_image_url"], "https://m.media-amazon.com/images/I/blind-main.jpg")
        self.assertIn('class="sku-reference-thumb table-thumb"', html)
        self.assertIn('src="https://m.media-amazon.com/images/I/blind-main.jpg"', html)
        self.assertNotIn("cbu01.alicdn.com", html)
        self.assertNotIn('src=""', html)

    def test_lifecycle_supplier_matching_caches_effective_product_context(self):
        data_pack = {
            "research_object": {"value": "hunting blind"},
            "products": [
                {
                    "asin": "B0BLIND001",
                    "title_cn": "透视弹出式地面盲棚",
                    "segment_cn": "弹出式地面盲棚",
                    "relevance_status": "passed",
                }
            ],
            "keywords": [],
        }
        suppliers = [
            {"title": "透视弹出式地面盲棚 加厚防水款", "price_rmb": 88},
            {"title": "多人狩猎地面盲棚 迷彩款", "price_rmb": 128},
        ]
        calls = {"products": 0}

        def counted_effective_products(pack):
            calls["products"] += 1
            return pack["products"]

        with patch.object(renderer, "effective_products", side_effect=counted_effective_products):
            for _ in range(5):
                for supplier in suppliers:
                    self.assertTrue(renderer.supplier_matches_lifecycle_context(supplier, data_pack, "弹出式地面盲棚"))

        self.assertEqual(calls["products"], 1)

    def test_lifecycle_strategy_uses_analysis_plan_type_labels_for_generic_categories(self):
        data_pack = {
            "research_object": {"value": "smart cat water fountain"},
            "products": [
                {
                    "asin": f"B0PETWAT{i:02d}",
                    "title": f"Smart Cat Water Fountain Quiet Pump Stainless Steel {i}",
                    "title_cn": f"宠物饮水机 静音循环水泵 {i}",
                    "brand": "PetFlow",
                    "segment_cn": "宠物饮水机",
                    "price": 29.99 + i,
                    "rating": 4.3 + (i % 3) * 0.1,
                    "review_count": 800 + i * 120,
                    "estimated_monthly_sales": 2200 - i * 20,
                }
                for i in range(12)
            ],
            "suppliers": [
                {
                    "title": "宠物饮水机静音循环水泵不锈钢猫咪自动饮水器",
                    "price_rmb": 38,
                    "supplier_name": "宠物用品工厂",
                    "url": "https://detail.1688.com/offer/123.html",
                }
            ],
        }
        analysis_plan = {
            "report_label_profile": {
                "lifecycle_type_labels": {
                    "A": "主饮水验证",
                    "B": "静音升级",
                    "C": "滤芯配件",
                    "D": "维护复购",
                }
            }
        }

        lifecycle = renderer.build_lifecycle_strategy_analysis(data_pack, analysis_plan, "src_pet")
        skus = renderer.lifecycle_skus(data_pack, lifecycle, "src_pet")
        ecosystem_html = renderer.render_ecosystem(data_pack, skus, "src_pet")
        sku_names = " ".join(str(sku.get("name")) for sku in skus)

        for expected in ["主饮水验证", "静音升级", "滤芯配件", "维护复购"]:
            self.assertIn(expected, sku_names + ecosystem_html)
        for forbidden in ["橱柜感应灯", "RGB 灯带", "户外感应灯", "Type A", "Type B", "未命名竞品"]:
            self.assertNotIn(forbidden, sku_names + ecosystem_html)
        self.assertGreater(len(lifecycle["sku_candidate_pool"]), 5)
        strategy_keys = {sku.get("strategy_type_key") for sku in lifecycle["sku_candidate_pool"]}
        self.assertGreaterEqual(len(strategy_keys), 4)
        self.assertIn("core_validation", strategy_keys)
        self.assertNotIn("A", strategy_keys)

    def test_lifecycle_candidate_names_do_not_embed_analysis_sentences_or_unsegmented_labels(self):
        data_pack = {
            "research_object": {"value": "electric cupping massager"},
            "products": [
                {
                    "asin": "B0CUP001",
                    "title": "Electric Cupping Massager with Red Light and Heat",
                    "title_cn": "未分层",
                    "brand": "Dopsikn",
                    "segment_cn": "未分层",
                    "price": 28.49,
                    "rating": 4.3,
                    "review_count": 1221,
                    "estimated_monthly_sales": 5087,
                },
                {
                    "asin": "B0CUP002",
                    "title": "Smart Cupping Therapy Massager Vacuum Scraping Device",
                    "brand": "REVO",
                    "segment_cn": "未分层",
                    "price": 136.0,
                    "rating": 4.3,
                    "review_count": 4458,
                    "estimated_monthly_sales": 1966,
                },
            ],
            "suppliers": supplier_rows(2),
        }

        lifecycle = renderer.build_lifecycle_strategy_analysis(data_pack, {}, "src_life")
        payload = json.dumps(lifecycle["sku_candidate_pool"], ensure_ascii=False)

        self.assertNotIn("未分层", payload)
        self.assertNotIn("用于判断竞品定位", payload)
        self.assertNotIn("价格带 · 评分", payload)
        self.assertIn("电动拔罐", payload)

    def test_cosmo_evidence_excerpts_do_not_embed_internal_positioning_sentences(self):
        data_pack = {
            "research_object": {"value": "electric cupping massager"},
            "products": [
                {
                    "asin": "B0CUP001",
                    "title": "Lymphatic Drainage Massager Electric Cupping Massager with Heat Vibration",
                    "title_cn": "未分层",
                    "brand": "Goticc",
                    "segment_cn": "未分层",
                    "positioning_cn": "未分层 · $34.19 价格带 · 评分 4.5 · 评论 25，用于判断竞品定位和页面表达",
                    "price": 34.19,
                    "rating": 4.5,
                    "review_count": 25,
                    "estimated_monthly_sales": 860,
                }
            ],
            "keywords": [
                {
                    "keyword": "electric cupping massager",
                    "keyword_cn": "电动拔罐按摩器",
                    "intent_cn": "按摩放松",
                    "relevance_cn": "高相关",
                    "monthly_search_volume": 3800,
                }
            ],
        }

        tags = renderer.generate_cosmo_alexa_tags(data_pack, {})
        payload = json.dumps(tags, ensure_ascii=False)

        self.assertNotIn("未分层", payload)
        self.assertNotIn("用于判断竞品定位", payload)
        self.assertNotIn("价格带 · 评分", payload)
        self.assertIn("电动拔罐", payload)

    def test_report_object_prefers_research_object_over_first_effective_product_segment(self):
        data_pack = {
            "research_object": {"value": "Electric Cupping Massager"},
            "effective_products": [
                {
                    "asin": "B0SEGMENT01",
                    "title": "Double Cup Electric Cupping Massager",
                    "brand": "CupBrand",
                    "segment_cn": "双杯/多杯套装型拔罐器",
                }
            ],
        }
        fns = {
            "effective_products": lambda pack: pack.get("effective_products") or [],
            "customer_product_position": lambda product: product.get("segment_cn"),
        }

        label = report_renderers.customer_report_object(data_pack, {}, "Electric Cupping Massager", fns)

        self.assertEqual(label, "Electric Cupping Massager")
        self.assertNotEqual(label, "双杯/多杯套装型拔罐器")

    def test_lifecycle_candidate_priorities_are_spread_for_decision_ranking(self):
        data_pack = {
            "research_object": {"type": "keyword", "value": "wall lighting"},
            "products": [
                {
                    "asin": f"B0LIGHT{i:03d}",
                    "title": f"Wall lighting fixture {i}",
                    "brand": f"Brand {i}",
                    "segment_cn": "墙面灯具",
                    "price": 39.99 + i,
                    "rating": 4.5,
                    "review_count": 9800,
                    "estimated_monthly_sales": 26000,
                }
                for i in range(18)
            ],
            "suppliers": [
                {
                    "title": "室内墙面灯具成品供应",
                    "price_rmb": 36,
                    "supplier_name": "灯具工厂",
                    "url": "https://detail.1688.com/offer/light.html",
                }
            ],
        }

        lifecycle = renderer.build_lifecycle_strategy_analysis(data_pack, {}, "src_light")
        scores = [sku["priority"] for sku in lifecycle["sku_candidate_pool"][:15]]

        self.assertGreaterEqual(max(scores), 90)
        self.assertLessEqual(min(scores), 75)
        self.assertGreaterEqual(len(set(scores)), 8)

    def test_lifecycle_sku_table_uses_semantic_strategy_filters(self):
        skus = [
            {
                "name": "透视地面盲棚 主盲棚验证款",
                "stage": "首发验证",
                "type": "A",
                "strategy_type_key": "core_validation",
                "type_label_cn": "主盲棚验证款",
                "price": "$89.99",
                "supply": "1688 成品报价复核",
                "phase": "P1",
                "priority": 88,
                "pain": "验证视野和搭建稳定性",
                "target_segment": "透视地面盲棚",
                "reference_competitor": "TIDEWE 透视地面盲棚",
            }
        ]

        html = renderer.render_sku_execution_table(skus, "src_001")

        self.assertIn('data-filter="core_validation"', html)
        self.assertIn('data-type="core_validation"', html)
        self.assertIn('data-sku-label="透视地面盲棚 主盲棚验证款"', html)
        self.assertIn('data-filter="scenario_upgrade"', html)
        self.assertNotIn('data-filter="A"', html)
        self.assertNotIn('data-type="a"', html)

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
            {"name": "透视地面盲棚 基础款", "type": "A", "priority": 92, "ecosystem_path": "关联度", "ecosystem_segment": "地面盲棚"},
            {"name": "弹出式地面盲棚 升级款", "type": "B", "priority": 86, "ecosystem_path": "场景", "ecosystem_segment": "弹出式盲棚"},
            {"name": "塔式狩猎盲棚 配件款", "type": "C", "priority": 74, "ecosystem_path": "消耗", "ecosystem_segment": "塔式盲棚"},
            {"name": "透视盲棚 维护款", "type": "D", "priority": 68, "ecosystem_path": "维护", "ecosystem_segment": "维护复购"},
        ]

        html = renderer.render_ecosystem({}, skus, "src_001")
        sku_html = renderer.render_sku_execution_table(skus, "src_001")

        self.assertIn("四维拓品生态 · 4D Ecosystem", html)
        self.assertIn("SKU 候选池总数：4", html)
        self.assertIn('id="sunburst"', html)
        self.assertIn('id="priorityChart"', html)
        self.assertIn("研究对象 → 四维路径 → 赛道/场景 → SKU 候选", html)
        self.assertIn("Top SKU 优先级评分", html)
        for label in ["基础款", "升级款", "配件款", "维护款"]:
            self.assertIn(label, html)
            self.assertIn(label, sku_html)
        self.assertIn('data-ecosystem-path="关联度"', sku_html)
        self.assertIn('data-segment="地面盲棚"', sku_html)
        for label in ["Type A", "Type B", "Type C", "Type D"]:
            self.assertNotIn(label, html)
            self.assertNotIn(label, sku_html)
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

        self.assertIn("供应链复核状态", html)
        self.assertIn("供应链风险", html)
        self.assertNotIn("可自产 SKU", html)
        self.assertNotIn('<div class="kpi-value">0</div>', html)

    def test_lifecycle_strategy_dashboard_respects_blocked_supply_readiness(self):
        data_pack = {
            "report_readiness": {
                "acceptance_ready": False,
                "partial_report_ready": True,
                "supply_conclusion_blocked": True,
                "supplier_quote_gate": {"passed": False, "actual": 9, "required": 50},
            },
            "report_readiness_view": renderer.report_readiness_view(
                {
                    "acceptance_ready": False,
                    "partial_report_ready": True,
                    "supply_conclusion_blocked": True,
                    "supplier_quote_gate": {"passed": False, "actual": 9, "required": 50},
                },
                {},
                "Watch",
            ),
            "products": [
                {
                    "asin": "B0HUNT0001",
                    "title": "See Through Pop Up Hunting Blind",
                    "brand": "FUNHORUN",
                    "segment_cn": "透视弹出式地面盲棚",
                    "price": 87.98,
                    "estimated_monthly_sales": 349,
                    "rating": 4.5,
                    "review_count": 1087,
                }
            ],
            "suppliers": [],
        }

        html = renderer.render_strategy_dashboard(data_pack, {}, "src_blocked")

        self.assertIn("供应链测算状态", html)
        self.assertIn("供应链测算未达门槛", html)
        self.assertIn("P1 候选 SKU", html)
        self.assertNotIn("供应链可控度", html)
        self.assertNotIn("P1 首发 SKU", html)
        self.assertNotIn("门禁通过", html)
        self.assertNotIn("可控供应链", html)
        self.assertNotIn("首发可控 SKU", html)

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
        for text in ["入门验证套装", "高配场景套装", "场景补位包", "维护替换包"]:
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
        self.assertIn('data-filter="core_validation"', html)
        self.assertIn("基础款", html)
        self.assertNotIn("Type A", html)
        self.assertNotIn('data-filter="A"', html)
        self.assertIn("供应链验证", html)
        self.assertIn("P1 立即启动", html)

    def test_report_css_caps_prompt_card_height_for_pc_layout(self):
        from site_assets import REPORT_CSS

        self.assertIn(".prompt-card", REPORT_CSS)
        self.assertIn(".pricing-card.recommended::before", REPORT_CSS)
        self.assertIn(".visual-item:last-child", REPORT_CSS)
        self.assertIn(".prompt-card::before", REPORT_CSS)
        self.assertIn(".prompt-copy-label", REPORT_CSS)
        self.assertIn(".template-market .supply-grid", REPORT_CSS)
        self.assertNotRegex(REPORT_CSS, r"\.prompt-card\{[^}]*max-height:260px")
        self.assertIn(".template-market .prompt-text{font-size:11px", REPORT_CSS)
        self.assertIn("max-height:188px;overflow:auto", REPORT_CSS)
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

    def test_report_css_styles_cosmo_reference_template_slots(self):
        from site_assets import REPORT_CSS, REPORT_POST_REFERENCE_CSS

        for selector in [
            ".cosmo-summary-strip",
            ".cosmo-summary-item",
            ".cosmo-summary-item.product",
            ".cosmo-summary-item.user",
            ".cosmo-card-meta-grid",
            ".cosmo-term-block",
            ".cosmo-block-label",
            ".cosmo-action-direction",
            ".cosmo-evidence-strip em",
            ".cosmo-evidence-sources",
        ]:
            self.assertIn(selector, REPORT_CSS)
        self.assertRegex(REPORT_CSS, r"\.cosmo-summary-strip\{[^}]*grid-template-columns:repeat\(4")
        self.assertRegex(REPORT_CSS, r"\.cosmo-summary-item b\{[^}]*font-size:")
        self.assertRegex(REPORT_CSS, r"\.cosmo-card-meta-grid\{[^}]*grid-template-columns:repeat\(2")
        self.assertRegex(REPORT_CSS, r"\.cosmo-action-direction\{[^}]*border-top:")
        self.assertRegex(
            REPORT_POST_REFERENCE_CSS,
            r"body\.template-market #cosmo-alexa-tags \.cosmo-submodule-grid\{[^}]*grid-template-columns:repeat\(2",
        )
        self.assertNotRegex(
            REPORT_POST_REFERENCE_CSS,
            r"body\.template-market #cosmo-alexa-tags \.cosmo-submodule-grid\{[^}]*grid-template-columns:1fr",
        )

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
        self.assertIn("高星证据", html)
        self.assertIn("低星证据", html)
        self.assertNotIn("Positive Reviews", html)
        self.assertNotIn("Negative Reviews", html)
        self.assertLess(html.find("正面好评"), html.find("负面差评"))
        self.assertNotIn('class="quote-grid"', html)
        positive_section = html.split("负面差评", 1)[0]
        negative_section = html.split("负面差评", 1)[1].split("</section>", 1)[0]
        self.assertEqual(positive_section.count("market-voc-card joy"), 6)
        self.assertEqual(negative_section.count("market-voc-card pain"), 6)

    def test_market_voc_recomputes_known_stale_toy_summary_for_other_categories(self):
        html = renderer.render_voc(
            {
                "reviews": [
                    {
                        "rating": 5,
                        "title": "Great size for an adult plus two kids",
                        "text": "Awesome see-through blind for turkey hunting. Great size for an adult plus two kids. Lightweight and easy to set up.",
                        "summary_cn": "正向反馈集中在开箱、陪伴和礼品场景",
                        "themes": ["size_finish_design", "ease_of_use"],
                    }
                ]
            },
            {},
        )

        self.assertNotIn("开箱、陪伴和礼品场景", html)
        self.assertNotIn("儿童陪伴", html)
        self.assertTrue("轻便" in html or "安装" in html or "使用满意度" in html)

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
        self.assertIn("高星证据", html)
        self.assertIn("低星证据", html)
        self.assertNotIn(">Positive<", html)
        self.assertNotIn(">Negative<", html)
        self.assertIn("用户原声证据明细表", html)
        self.assertIn("evidence-drawer", html)
        self.assertNotIn("需补齐证据", html)
        self.assertLess(html.find("正面反馈"), html.find("负面反馈"))
        positive_section = html.split("负面反馈", 1)[0]
        negative_section = html.split("负面反馈", 1)[1].split("</div></div>", 1)[0]
        self.assertEqual(positive_section.count("demand-evidence-card joy"), 6)
        self.assertEqual(negative_section.count("demand-evidence-card pain"), 6)

    def test_demand_voice_theater_diagnostic_slots_use_customer_business_copy(self):
        html = renderer.render_voice_theater(
            {
                "reviews": [
                    {
                        "rating": 5,
                        "title": "Good blind",
                        "text": "Easy to set up and the see through hunting blind works well.",
                        "themes": ["setup", "visibility"],
                    },
                    {
                        "rating": 2,
                        "title": "Noisy zipper",
                        "text": "The zipper is noisy and the blind fabric needs stronger stitching.",
                        "themes": ["noise", "durability"],
                    },
                ]
            },
            "src_001",
        )

        self.assertEqual(html.count("demand-evidence-card joy"), 6)
        self.assertEqual(html.count("demand-evidence-card pain"), 6)
        self.assertNotIn("证据采集诊断", html)
        self.assertNotIn("审计文件未提供", html)
        self.assertNotIn("需要更多原声验证", html)
        self.assertIn("评论证据槽位", html)
        self.assertIn("继续采集同赛道评论原声", html)

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

    def test_market_voc_filters_reviews_outside_effective_product_pool(self):
        data_pack = {
            "products": [
                {
                    "asin": "B0BLIND001",
                    "title": "Hunting Blind 270 Degree See Through Ground Blind",
                    "title_cn": "透视地面盲棚",
                    "segment_cn": "透视地面盲棚",
                }
            ],
            "reviews": [
                {
                    "asin": "B0BLIND001",
                    "rating": 5,
                    "title": "Roomy blind",
                    "text": "Quick and easy setup. The hunting blind is roomy and has good visibility.",
                    "themes": ["battery_charging"],
                },
                {
                    "asin": "B0FEEDER001",
                    "rating": 1,
                    "title": "Feeder battery failed",
                    "text": "The deer feeder battery stopped charging and the timer failed.",
                    "themes": ["battery_charging"],
                },
                {
                    "asin": "B0CAMERA001",
                    "rating": 2,
                    "title": "Trail camera problem",
                    "text": "The trail camera app subscription and video recording did not work.",
                    "themes": ["battery_charging", "subscription"],
                },
            ],
        }

        html = renderer.render_voc(data_pack, {})

        self.assertIn("Quick and easy setup", html)
        self.assertNotIn("电池与充电", html)
        self.assertNotIn("deer feeder", html.casefold())
        self.assertNotIn("trail camera", html.casefold())
        self.assertNotIn("subscription", html.casefold())

    def test_demand_appeal_rows_filter_off_target_review_themes(self):
        data_pack = {
            "products": [
                {
                    "asin": "B0BLIND001",
                    "title": "Hunting Blind 270 Degree See Through Ground Blind",
                    "title_cn": "透视地面盲棚",
                    "segment_cn": "透视地面盲棚",
                }
            ],
            "reviews": [
                {
                    "asin": "B0BLIND001",
                    "rating": 4,
                    "title": "Good blind",
                    "text": "The blind is easy to set up and visibility is good.",
                    "themes": ["ease_of_use", "visibility"],
                },
                {
                    "asin": "B0FEEDER001",
                    "rating": 1,
                    "title": "Feeder battery failed",
                    "text": "The deer feeder battery stopped charging.",
                    "themes": ["battery_charging"],
                },
            ],
        }

        rows = renderer.appeal_rows(data_pack, "src_001")
        labels = [row[1] for row in rows]

        self.assertIn("易用性", labels)
        self.assertNotIn("电池与充电", labels)


if __name__ == "__main__":
    unittest.main()
