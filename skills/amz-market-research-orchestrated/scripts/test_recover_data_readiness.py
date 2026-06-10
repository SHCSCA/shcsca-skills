#!/usr/bin/env python3
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import recover_data_readiness as recovery


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def competitor_rows():
    segments = ["橱柜感应灯", "RGB 灯带", "智能灯泡"]
    rows = []
    for idx in range(30):
        rows.append(
            {
                "asin": f"B0REC{idx:07d}",
                "title": f"Smart Lighting Competitor {idx}",
                "brand": f"Brand {idx % 5}",
                "segment_cn": segments[idx % 3],
                "price": 12 + idx,
                "rating": 4.2,
                "review_count": 500 + idx,
                "estimated_monthly_sales": 1000 + idx,
                "source_id": "src_001",
                "provider": "sorftime",
            }
        )
    return rows


def supplier_rows():
    return [
        {
            "title": f"智能照明工厂报价 {idx}",
            "supplier_name": f"供应商 {idx}",
            "url": f"https://detail.1688.com/offer/{idx}.html",
            "price_rmb": 10 + (idx % 12),
            "seed_keyword": "橱柜灯",
            "source_id": "src_002",
            "provider": "sorftime",
        }
        for idx in range(50)
    ]


def make_report(root: Path):
    write_json(
        root / "data" / "data_pack.json",
        {
            "research_object": {"value": "smart lighting"},
            "sources": [
                {"source_id": "src_001", "provider": "sorftime", "tool": "product_search"},
                {"source_id": "src_002", "provider": "sorftime", "tool": "ali1688_similar_product"},
            ],
            "products": [],
            "keywords": [{"keyword": f"smart lighting keyword {idx}", "source_id": "src_001", "provider": "sorftime"} for idx in range(1000)],
            "suppliers": supplier_rows(),
            "reviews": [],
            "tiktok_products": [],
            "tiktok_videos": [],
            "web_documents": [{"title": "market note", "url": "https://example.com/market"}],
            "data_gaps": [],
        },
    )
    write_json(root / "report_brief.json", {"research_object": {"value": "smart lighting"}, "data_depth": "standard"})


class RecoverDataReadinessTest(unittest.TestCase):
    def test_recovery_runs_product_collector_before_final_diagnostic(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            make_report(report_dir)
            calls = []

            def fake_runner(command):
                calls.append(command)
                if "collect_sorftime_products.py" in str(command[1]):
                    data_path = report_dir / "data" / "data_pack.json"
                    data_pack = json.loads(data_path.read_text(encoding="utf-8"))
                    data_pack["products"] = competitor_rows()
                    write_json(data_path, data_pack)
                return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

            report = recovery.recover_readiness(report_dir, "auto", max_rounds=2, runner=fake_runner)

            self.assertTrue(report["recovery_ready"])
            self.assertEqual(report["unresolved_modules"], [])
            self.assertTrue(any("collect_sorftime_products.py" in str(command[1]) for command in calls))
            written = json.loads((report_dir / "data" / "normalized" / "readiness_recovery_report.json").read_text(encoding="utf-8"))
            self.assertTrue(written["recovery_ready"])

    def test_target_commands_use_force_rounds_for_1688_quality_failures(self):
        readiness = {
            "depth": "standard",
            "blocking_gaps": [{"module": "supplier_quote_quality"}],
            "warnings": [],
        }

        commands = recovery.target_commands(Path("reports/example"), readiness)

        supplier_command = next(command for name, command in commands if name == "suppliers_1688")
        self.assertIn("--force-rounds", supplier_command)
        self.assertIn("--min-valid-quotes", supplier_command)


if __name__ == "__main__":
    unittest.main()
