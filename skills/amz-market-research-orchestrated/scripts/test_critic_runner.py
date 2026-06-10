#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path

import critic_runner


def thin_data_pack():
    return {
        "task_id": "thin_case",
        "reviews": [{"rating": 5, "text": "Works well"}],
        "data_gaps": [{"module": "review_sample_depth", "reason": "评论样本不足"}],
        "quality": {"overall_score": 0.74, "grade": "low_confidence_watch"},
        "normalization": {"cross_validated_counts": {"keywords": 1000, "products": 0, "reviews": 0}},
    }


class CriticRunnerTest(unittest.TestCase):
    def test_low_evidence_go_fails_then_refinement_downgrades_to_watch(self):
        data_pack = thin_data_pack()
        analysis_plan = {"limitations": []}
        delivery = {"status": "partial", "decision": "Go"}

        draft = critic_runner.build_critic_review(data_pack, analysis_plan, delivery, "Go", round_id=0)
        plan = critic_runner.build_refinement_plan(draft, "Go")
        final_decision = critic_runner.apply_refinement_plan(delivery, plan, "Go")
        final = critic_runner.build_critic_review(data_pack, analysis_plan, delivery, final_decision, round_id=1, previous_review=draft, applied_operations=plan["operations"])

        self.assertFalse(draft["pass"])
        self.assertIn("F-review-depth", draft["remaining_findings"])
        self.assertTrue(plan["operations"])
        self.assertEqual(final_decision, "Watch")
        self.assertEqual(delivery["decision_adjustment"]["to"], "Watch")
        self.assertIn("partial_delivery", delivery["decision_adjustment"]["reasons"])
        self.assertTrue(final["pass"])
        self.assertIn("F-review-depth", final["resolved_findings"])

    def test_write_critic_outputs_records_history_and_failed_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            data_pack = thin_data_pack()
            analysis_plan = {"limitations": []}
            delivery = {"status": "partial", "decision": "Go"}
            draft = critic_runner.build_critic_review(data_pack, analysis_plan, delivery, "Go", round_id=0)
            plan = critic_runner.build_refinement_plan(draft, "Go")
            final_decision = critic_runner.apply_refinement_plan(delivery, plan, "Go")

            final = critic_runner.write_critic_outputs(report_dir, data_pack, analysis_plan, delivery, final_decision, draft_review=draft, refinement_plan=plan)

            self.assertTrue(final["pass"])
            review = json.loads((report_dir / "analysis" / "critic_review.json").read_text(encoding="utf-8"))
            refinement = json.loads((report_dir / "analysis" / "refinement_plan.json").read_text(encoding="utf-8"))
            self.assertEqual(review["round_id"], 1)
            self.assertEqual(refinement["status"], "accepted")
            self.assertTrue(refinement["applied_operations"])
            self.assertTrue((report_dir / "analysis" / "refinement_history.jsonl").exists())
            self.assertTrue((report_dir / "training_data" / "failed_cases.jsonl").exists())
            summary = (report_dir / "analysis" / "critic_summary.md").read_text(encoding="utf-8")
            self.assertIn("# Critic Summary", summary)
            self.assertIn("final_pass: `true`", summary)
            self.assertIn("decision_adjusted: `true`", summary)
            self.assertIn("must not claim delivery completion", summary)

    def test_critic_reviews_rendered_html_and_view_models(self):
        data_pack = {
            "task_id": "html_case",
            "reviews": [{"rating": 5}],
            "data_gaps": [],
            "quality": {"overall_score": 0.72, "grade": "B"},
            "normalization": {"cross_validated_counts": {"keywords": 1000, "products": 3}},
        }
        rendered_docs = {
            "market_depth": "<html><body>证据强度 数据覆盖 数据缺口 置信等级 建议动作 source_id</body></html>",
            "lifecycle_strategy": "<html><body>证据强度 数据覆盖 数据缺口 置信等级 建议动作 成本</body></html>",
            "demand_gap": "<html><body>证据强度 数据覆盖 数据缺口 置信等级 建议动作</body></html>",
        }
        view_models = {
            "market_depth_view.json": {"client_safe_text": True},
            "lifecycle_strategy_view.json": {"client_safe_text": False},
            "demand_gap_view.json": {"client_safe_text": True},
        }

        review = critic_runner.build_critic_review(
            data_pack,
            {"limitations": []},
            {"status": "complete", "decision": "Watch"},
            "Watch",
            rendered_docs=rendered_docs,
            view_models=view_models,
        )

        self.assertFalse(review["pass"])
        self.assertIn("F-customer-html-leak", review["remaining_findings"])
        self.assertIn("F-view-client-safe-lifecycle_strategy_view.json", review["remaining_findings"])
        self.assertIn("F-finance-depth", [item["id"] for item in review["findings"]])

    def test_critic_allows_competitor_table_scoped_asin(self):
        data_pack = {
            "task_id": "html_case",
            "reviews": [{"rating": 5}],
            "data_gaps": [],
            "quality": {"overall_score": 0.72, "grade": "B"},
            "normalization": {"cross_validated_counts": {"keywords": 1000, "products": 3}},
        }
        required_terms = "证据强度 数据覆盖 数据缺口 置信等级 建议动作 成本 毛利 FBA"
        rendered_docs = {
            "market_depth": f'<html><body>{required_terms}<span class="asin-token" data-allow-asin="competitor-table">B0TEST1234</span></body></html>',
            "lifecycle_strategy": f"<html><body>{required_terms}</body></html>",
            "demand_gap": f"<html><body>{required_terms}</body></html>",
        }

        review = critic_runner.build_critic_review(
            data_pack,
            {"limitations": []},
            {"status": "complete", "decision": "Watch"},
            "Watch",
            rendered_docs=rendered_docs,
        )

        self.assertTrue(review["pass"])
        self.assertNotIn("F-customer-html-leak", review["remaining_findings"])


if __name__ == "__main__":
    unittest.main()
