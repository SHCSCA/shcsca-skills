#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

from view_model_builder import build_report_views, build_site_data, customer_product_label, customer_review_summary, safe_kpis, write_report_views


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

    def test_lifecycle_view_keeps_generated_candidate_pool(self):
        data_pack = sample_data_pack()
        data_pack["lifecycle_strategy"] = {
            "sku_candidate_pool": [
                {"name": "热敷红光电动拔罐基础验证款", "type": "主品验证", "priority": 92},
                {"name": "淋巴引流负压按摩升级款", "type": "场景升级", "priority": 86},
            ],
            "recommended_skus": [
                {"name": "热敷红光电动拔罐基础验证款", "type": "主品验证", "priority": 92}
            ],
            "ecosystem_nodes": [{"name": "主品验证", "value": 1}],
            "filter_diagnostics": {"input_products": 39, "candidate_pool": 2},
        }

        views = build_report_views(data_pack, {"method_chain": []}, "Watch")
        lifecycle_view = views["lifecycle_strategy_view"]

        self.assertEqual(len(lifecycle_view["sku_candidate_pool"]), 2)
        self.assertEqual(len(lifecycle_view["recommended_skus"]), 1)
        self.assertEqual(lifecycle_view["filter_diagnostics"]["candidate_pool"], 2)

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
            market_payload = json.loads((report_dir / "analysis" / "market_depth_view.json").read_text(encoding="utf-8"))
            payload = json.loads((report_dir / "analysis" / "demand_gap_view.json").read_text(encoding="utf-8"))
            self.assertIn("隐私政策和数据使用说明不够清晰", combined)
            self.assertEqual(market_payload["tables"]["competitors"][0]["reference_asin"], "B0TEST1234")
            for leaked in ["source_id", "src_001", '"asin"', "provider", "sorftime", "Interactive AI Plush Toy"]:
                self.assertNotIn(leaked, combined)
            self.assertTrue(payload["client_safe_text"])

    def test_customer_product_label_uses_brand_and_chinese_segment_not_generic_record(self):
        product = {
            "asin": "B0ABC12345",
            "brand": "Govee",
            "title": "Govee RGBIC LED Strip Lights, Smart LED Lights for Bedroom",
            "segment_cn": "RGB 灯带",
        }

        label = customer_product_label(product)

        self.assertEqual(label, "Govee RGB 灯带")
        self.assertNotIn("竞品记录", label)

    def test_customer_product_label_infers_current_product_family_from_title(self):
        product = {
            "asin": "B0CUPPING1",
            "brand": "Dopsikn",
            "title": "Dopsikn Red Light Electric Cupping Massager with Heat and Suction",
            "title_cn": "未分层",
            "segment_cn": "未分层",
            "category": "Electric Back Massagers",
        }

        label = customer_product_label(product)

        self.assertIn("Dopsikn", label)
        self.assertIn("拔罐", label)
        self.assertNotIn("未分层", label)

    def test_report_views_infer_segments_instead_of_showing_unsegmented_labels(self):
        data_pack = sample_data_pack()
        data_pack["research_object"] = {"value": "Electric Cupping Massager"}
        data_pack["products"] = [
            {
                "asin": "B0CUPPING1",
                "brand": "Dopsikn",
                "title": "Dopsikn Red Light Electric Cupping Massager with Heat and Suction",
                "title_cn": "未分层",
                "segment_cn": "未分层",
                "price": 28.49,
                "rating": 4.3,
                "review_count": 1221,
                "estimated_monthly_sales": 1200,
            }
        ]

        views = build_report_views(data_pack, {"method_chain": []}, "Watch")
        payload = json.dumps(views["market_depth_view"], ensure_ascii=False)

        self.assertIn("热敷红光电动拔罐器", payload)
        self.assertNotIn("未分层", payload)

    def test_site_data_exposes_pc_decision_cockpit_without_internal_status(self):
        data_pack = sample_data_pack()
        data_pack["quality"]["grade"] = "ready_for_normalization"
        data_pack["report_readiness_view"] = {
            "status": "诊断交付",
            "decision": "Watch",
            "supply_blocked": True,
            "blocking_gaps": [
                {
                    "module": "keyword_sample_depth",
                    "next_step": "运行 collect_sorftime_keywords.py 补到 1200 条采集目标。",
                }
            ],
        }
        analysis_plan = {"method_chain": [{"method_id": "market.scan"}], "limitations": []}
        readiness = {
            "acceptance_ready": False,
            "blocking_gaps": [{"module": "competitor_pool_depth"}],
            "warnings": [{"module": "review_sample_depth"}],
            "counts": {"products": 5},
            "supplier_quote_gate": {"passed": False},
            "competitor_gate": {"passed": False},
            "segment_gate": {"passed": False},
            "supplier_quality_gate": {"passed": False},
        }

        site_data = build_site_data(data_pack, analysis_plan, "Watch", CHILD_SKILLS, readiness)
        payload = json.dumps(site_data, ensure_ascii=False)

        self.assertIn("decision_cockpit", site_data)
        self.assertEqual(site_data["report_readiness_view"]["status"], "诊断交付")
        self.assertIn("当前阻断项", payload)
        self.assertNotIn("ready_for_normalization", payload)
        self.assertNotIn("sorftime", payload.casefold())
        self.assertNotIn("collect_", payload)
        self.assertIn("数据采集流程", payload)

    def test_site_data_preserves_all_readiness_blocking_gaps_with_customer_labels(self):
        data_pack = sample_data_pack()
        data_pack["report_readiness_view"] = {
            "delivery_state": "阻断交付",
            "decision": "No-Go",
            "blocking_gaps": [
                {
                    "module": "competitor_pool_depth",
                    "reason": "亚马逊竞品池不足。",
                    "impact": "不能支撑市场格局。",
                    "next_step": "补采 Amazon 竞品详情。",
                },
                {
                    "module": "keyword_sample_depth",
                    "reason": "关键词样本不足。",
                    "impact": "不能支撑需求结构。",
                    "next_step": "补采关键词。",
                },
                {
                    "module": "keyword_customer_intent_duplicate_ratio",
                    "reason": "客户侧关键词主题重复率过高。",
                    "impact": "不能把重复词当作需求规模。",
                    "next_step": "按中文意图聚合关键词。",
                },
            ],
        }
        readiness = {
            "acceptance_ready": False,
            "blocking_gaps": data_pack["report_readiness_view"]["blocking_gaps"],
            "warnings": [],
            "counts": {},
            "supplier_quote_gate": {"passed": True},
            "supplier_quality_gate": {"passed": True, "customer_visible_passed": True},
            "competitor_gate": {"passed": False},
            "segment_gate": {"passed": True},
        }

        site_data = build_site_data(data_pack, {"method_chain": []}, "No-Go", CHILD_SKILLS, readiness)
        gaps = site_data["report_readiness_view"]["blocking_gaps"]
        payload = json.dumps(site_data, ensure_ascii=False)

        self.assertEqual(len(gaps), 3)
        self.assertIn("竞品池深度", payload)
        self.assertIn("关键词数据记录深度", payload)
        self.assertNotIn("关键词样本深度", payload)
        self.assertIn("关键词意图去重", payload)
        self.assertNotIn("competitor_pool_depth", payload)

    def test_site_data_does_not_surface_resolved_supplier_quality_gap(self):
        data_pack = sample_data_pack()
        data_pack["data_gaps"] = [
            {
                "module": "supplier_quote_quality",
                "gap": "1688报价价格分布异常：max/P50=23.28。",
                "impact": "供应链成本和毛利率测算必须阻断。",
            },
            {
                "module": "tiktok_signal_depth",
                "gap": "TikTok 商品/视频信号不足：当前 0/1。",
            },
        ]
        readiness = {
            "acceptance_ready": False,
            "blocking_gaps": [{"module": "keyword_sample_depth", "reason": "关键词样本不足。"}],
            "warnings": [{"module": "tiktok_signal_depth"}],
            "counts": {},
            "supply_conclusion_blocked": False,
            "supplier_quote_gate": {"passed": True},
            "supplier_quality_gate": {"passed": True, "customer_visible_passed": True},
            "competitor_gate": {"passed": True},
            "segment_gate": {"passed": True},
        }

        site_data = build_site_data(data_pack, {"method_chain": []}, "No-Go", CHILD_SKILLS, readiness)
        payload = json.dumps(site_data["data_gaps"], ensure_ascii=False)

        self.assertNotIn("1688报价价格分布异常", payload)
        self.assertNotIn("毛利率测算必须阻断", payload)
        self.assertIn("TikTok", payload)

    def test_site_data_recomputes_competitor_image_gap_from_effective_products(self):
        data_pack = sample_data_pack()
        data_pack["research_object"] = {"value": "ai plush toy"}
        data_pack["effective_products"] = [
            {
                "asin": "B000000001",
                "title": "AI plush toy with voice",
                "brand": "Brand A",
                "segment_cn": "AI 毛绒玩具",
                "image_url": "https://m.media-amazon.com/images/I/71valid-one.jpg",
            },
            {
                "asin": "B000000002",
                "title": "AI plush toy companion",
                "brand": "Brand B",
                "segment_cn": "AI 毛绒玩具",
                "image_url": "",
            },
        ]
        data_pack["data_gaps"] = [
            {
                "type": "competitor_image_coverage",
                "module": "amazon_competitor_images",
                "gap": "Amazon 竞品池当前 96 个有效竞品中仅 15 个返回可展示主图 URL，图片覆盖率 16%。",
            }
        ]
        readiness = {
            "acceptance_ready": False,
            "blocking_gaps": [{"module": "keyword_sample_depth", "reason": "关键词数据不足"}],
            "warnings": [],
            "counts": {},
        }

        site_data = build_site_data(data_pack, {"method_chain": []}, "No-Go", CHILD_SKILLS, readiness)
        payload = json.dumps(site_data["data_gaps"], ensure_ascii=False)

        self.assertIn("当前有效竞品池 2 个", payload)
        self.assertIn("其中 1 个返回可展示主图 URL", payload)
        self.assertNotIn("96 个有效竞品", payload)

    def test_views_filter_off_target_competitor_noise(self):
        data_pack = sample_data_pack()
        data_pack["products"] = [
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
                "asin": "B0PROTEIN1",
                "title": "Premier Protein Shake Chocolate 12 Pack",
                "brand": "Premier Protein",
                "segment_cn": "未分层",
                "price": 31.98,
                "rating": 4.6,
                "review_count": 58142,
                "estimated_monthly_sales": 705547,
            },
        ]

        views = build_report_views(data_pack, {"method_chain": []}, "Watch")
        payload = json.dumps(views, ensure_ascii=False)

        self.assertIn("MCGOR 橱柜感应灯", payload)
        self.assertNotIn("Premier Protein", payload)
        self.assertNotIn("未分层", payload)

    def test_kpis_do_not_use_unmapped_or_off_topic_top_keywords(self):
        data_pack = sample_data_pack()
        data_pack["research_object"] = {"value": "Electric Cupping Massager"}
        data_pack["keywords"] = [
            {
                "keyword": "stanley cup",
                "keyword_cn": "未映射关键词：stanley cup",
                "monthly_search_volume": 1083728,
            },
            {
                "keyword": "electric cupping massager",
                "keyword_cn": "电动拔罐按摩器",
                "monthly_search_volume": 8200,
                "is_core_relevant": True,
                "relevance_cn": "高相关",
            },
        ]

        kpis = safe_kpis(data_pack, "No-Go")
        top_keyword = next(item for item in kpis if item["label"] == "最大关键词月搜索")

        self.assertEqual(top_keyword["value"], 8200)
        self.assertEqual(top_keyword["subtext"], "电动拔罐按摩器")
        self.assertNotIn("stanley", json.dumps(kpis, ensure_ascii=False).casefold())

    def test_kpis_use_effective_competitor_pool_when_top100_is_not_supported(self):
        data_pack = sample_data_pack()
        data_pack["categories"] = [{"top100_estimated_monthly_units": None}]
        data_pack["effective_products"] = [
            {
                "asin": "B0A0000001",
                "title": "Electric cupping massager with heat",
                "brand": "A",
                "estimated_monthly_sales": 120,
            },
            {
                "asin": "B0A0000002",
                "title": "Red light electric cupping massager",
                "brand": "B",
                "estimated_monthly_sales": 80,
            },
        ]
        data_pack["effective_keywords"] = [{"keyword": "electric cupping massager", "keyword_cn": "电动拔罐按摩器"}]

        kpis = safe_kpis(data_pack, "No-Go")
        volume = next(item for item in kpis if item["label"] == "当前有效竞品池销量")
        keyword_count = next(item for item in kpis if item["label"] == "关键词意图数")

        self.assertEqual(volume["value"], 200)
        self.assertIn("2 个有效竞品", volume["subtext"])
        self.assertEqual(keyword_count["value"], 1)
        self.assertIn("1 条有效关键词", keyword_count["subtext"])
        self.assertNotIn("Top100", json.dumps(kpis, ensure_ascii=False))

    def test_report_views_competitor_rows_expose_allowed_asin_and_image(self):
        data_pack = sample_data_pack()
        data_pack["effective_products"] = [
            {
                "asin": "B0IMG12345",
                "title": "Electric cupping massager with heat and red light",
                "brand": "CupPro",
                "segment_cn": "热敷红光电动拔罐器",
                "image_url": "https://example.com/main.jpg",
                "estimated_monthly_sales": 100,
            }
        ]

        views = build_report_views(data_pack, {"method_chain": []}, "Watch")
        row = views["market_depth_view"]["tables"]["competitors"][0]

        self.assertEqual(row["reference_asin"], "B0IMG12345")
        self.assertEqual(row["image_url"], "https://example.com/main.jpg")

    def test_site_data_gaps_do_not_expose_cross_category_pollution(self):
        data_pack = sample_data_pack()
        data_pack["research_object"] = {"value": "Electric Cupping Massager"}
        data_pack["data_gaps"] = [
            "Amazon赛道拆分不足：当前赛道分布 {'套装型电动拔罐器': 3, '户外感应灯': 6, '氛围灯': 1}，要求至少 3 个赛道。",
            "最大关键词月搜索来自未映射关键词：stanley cup，已进入审计。",
            "TikTok 商品/视频信号不足：当前 0/1。",
        ]

        site_data = build_site_data(data_pack, {"method_chain": []}, "No-Go", CHILD_SKILLS)
        payload = json.dumps(site_data["data_gaps"], ensure_ascii=False)

        self.assertIn("TikTok 商品/视频信号不足", payload)
        self.assertNotIn("户外感应灯", payload)
        self.assertNotIn("氛围灯", payload)
        self.assertNotIn("stanley", payload.casefold())

    def test_site_data_gaps_translate_internal_filtered_logs(self):
        data_pack = sample_data_pack()
        data_pack["data_gaps"] = [
            "Filtered 29 non-core or incomplete rows after 市场数据 collection.",
            "Filtered 30 1688 rows that were tabletop beauty machines, breast/body-shaping machines, red-light masks, or high-price outliers.",
            "Filtered 2 low-price/manual/non-electric cupping rows before final rendering.",
        ]

        site_data = build_site_data(data_pack, {"method_chain": []}, "No-Go", CHILD_SKILLS)
        payload = json.dumps(site_data["data_gaps"], ensure_ascii=False)

        self.assertIn("相关性清洗", payload)
        self.assertNotIn("Filtered", payload)
        self.assertNotIn("non-core", payload)
        self.assertNotIn("low-price", payload)
        self.assertEqual(len(site_data["data_gaps"]), 1)

    def test_report_views_limitations_do_not_expose_cross_category_pollution(self):
        data_pack = sample_data_pack()
        data_pack["research_object"] = {"value": "Electric Cupping Massager"}
        data_pack["data_gaps"] = [
            "Amazon赛道拆分不足：当前赛道分布 {'套装型电动拔罐器': 3, '户外感应灯': 6, '氛围灯': 1}，要求至少 3 个赛道。",
            "最大关键词月搜索来自未映射关键词：stanley cup，已进入审计。",
        ]

        views = build_report_views(data_pack, {"method_chain": [], "limitations": []}, "No-Go")
        payload = json.dumps({name: view["limitations"] for name, view in views.items()}, ensure_ascii=False)

        self.assertIn("跨类目污染", payload)
        self.assertNotIn("户外感应灯", payload)
        self.assertNotIn("氛围灯", payload)
        self.assertNotIn("stanley", payload.casefold())

    def test_views_downgrade_evidence_strength_when_readiness_is_blocked(self):
        data_pack = sample_data_pack()
        data_pack["quality"] = {"overall_score": 0.94, "grade": "A"}
        data_pack["report_readiness"] = {
            "acceptance_ready": False,
            "partial_report_ready": False,
            "supply_conclusion_blocked": False,
            "blocking_gaps": [
                {
                    "module": "keyword_sample_depth",
                    "reason": "有效关键词不足",
                    "impact": "不能输出完整市场结构判断",
                    "next_step": "补采有效关键词",
                }
            ],
        }

        views = build_report_views(data_pack, {"method_chain": []}, "No-Go")

        for payload in views.values():
            self.assertEqual(payload["evidence_strength"], "低 / 阻断交付")
            self.assertIn("readiness", payload)
            self.assertEqual(payload["readiness"]["delivery_state"], "阻断交付")

    def test_customer_review_summary_does_not_use_lighting_copy_for_cupping_reviews(self):
        review = {
            "rating": 5,
            "title": "Great red light heat cupping massager",
            "text": "The red light and heat work well. Strong suction helped my back pain and it is easy to use.",
        }

        summary = customer_review_summary(review)

        self.assertIn("热敷", summary)
        self.assertIn("吸力", summary)
        self.assertNotIn("亮度", summary)
        self.assertNotIn("灯效", summary)

    def test_site_data_includes_public_delivery_result_summary(self):
        data_pack = sample_data_pack()
        delivery = {
            "status": "blocked",
            "decision": "No-Go",
            "delivery_mode": "diagnostic_delivery",
            "overall_pass": False,
            "acceptance_proof": "output/acceptance_proof.json",
            "critic_review": {"path": "analysis/critic_review.json"},
            "data_readiness": {
                "decision": "No-Go",
                "delivery_mode": "diagnostic_delivery",
                "evidence_grade": "D",
                "score": 42,
                "acceptance_ready": False,
                "supply_conclusion_blocked": True,
                "path": "data/normalized/data_readiness_report.json",
            },
        }

        site_data = build_site_data(data_pack, {"method_chain": []}, "No-Go", CHILD_SKILLS, delivery_result=delivery)
        public = site_data["delivery_result"]
        payload = json.dumps(public, ensure_ascii=False)

        self.assertEqual(public["decision"], "No-Go")
        self.assertEqual(public["data_readiness"]["delivery_mode"], "diagnostic_delivery")
        self.assertNotIn("acceptance_proof", payload)
        self.assertNotIn("critic_review", payload)
        self.assertNotIn("path", payload)


if __name__ == "__main__":
    unittest.main()
