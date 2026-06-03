#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import collect_sorftime_keywords as collector
from collect_sorftime_keywords import content_rows, infer_seeds, keyword_entity, parse_sse_json


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class CollectSorftimeKeywordsTest(unittest.TestCase):
    def test_parse_sse_json_and_content_rows(self):
        body = 'event: message\n' + 'data: {"result":{"content":[{"type":"text","text":"[{\\"关键词\\":\\"ai plush toy\\",\\"月搜索量\\":\\"1000\\"}]"}]},"id":1,"jsonrpc":"2.0"}\n'

        parsed = parse_sse_json(body)
        rows = content_rows(parsed)

        self.assertEqual(rows, [{"关键词": "ai plush toy", "月搜索量": "1000"}])

    def test_keyword_entity_maps_category_fields(self):
        row = {
            "关键词": "interactive ai plush toy",
            "周搜索量": "23652",
            "月搜索量": "112639",
            "cpc精准竞价": "0.60",
            "搜索结果数": "105992",
            "搜索量旺季": "1月",
        }

        entity = keyword_entity(row, "src_001", "category_keywords")

        self.assertEqual(entity["keyword"], "interactive ai plush toy")
        self.assertEqual(entity["weekly_search_volume"], 23652)
        self.assertEqual(entity["monthly_search_volume"], 112639)
        self.assertEqual(entity["recommended_cpc"], "0.60")
        self.assertEqual(entity["competitor_count"], 105992)
        self.assertEqual(entity["provider"], "sorftime")

    def test_infer_seeds_uses_research_object_without_category_defaults(self):
        seeds = infer_seeds({"research_object": {"value": "ai plush toy"}, "keywords": []}, [])

        self.assertEqual(seeds, ["ai plush toy"])
        self.assertNotIn("wall sconce", seeds)

    def test_collect_without_seed_records_gap_without_mcp(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(report_dir / "data" / "data_pack.json", {"sources": [], "keywords": [], "categories": [], "data_gaps": []})

            with patch.object(collector, "mcp_url", side_effect=AssertionError("mcp should not be needed without keyword tasks")):
                summary = collector.collect(report_dir, 1000, None, [], 75, 0)

            data_pack = json.loads((report_dir / "data" / "data_pack.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["calls"], 0)
            self.assertEqual(summary["planned_calls"], 0)
            self.assertFalse(summary["collection_ready"])
            self.assertEqual(summary["warnings"], ["No keyword collection tasks were available."])
            self.assertEqual(data_pack["data_gaps"][0]["type"], "keyword_collection_no_seed")

    def test_collect_reports_theoretical_capacity_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(report_dir / "data" / "data_pack.json", {"sources": [], "keywords": [], "categories": [], "data_gaps": []})

            def fake_call_tool(_url, _name, _args):
                return {"result": {"content": [{"type": "text", "text": "[]"}]}}

            with patch.object(collector, "mcp_url", return_value="http://sorftime.test"), patch.object(collector, "call_tool", side_effect=fake_call_tool):
                summary = collector.collect(report_dir, 1000, None, ["neck massager"], 10, 0)

            self.assertEqual(summary["planned_calls"], 10)
            self.assertEqual(summary["theoretical_row_capacity"], 200)
            self.assertFalse(summary["collection_ready"])
            self.assertIn("Theoretical row capacity is below min_keywords", summary["warnings"][0])

    def test_collect_pages_until_keyword_target_and_writes_raw_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(report_dir / "data" / "data_pack.json", {"sources": [], "keywords": [], "categories": [], "data_gaps": []})

            def fake_call_tool(_url, _name, args):
                page = int(args["page"])
                rows = [{"关键词": f"neck massager keyword {page}-{idx}", "月搜索量": str(1000 + idx)} for idx in range(20)]
                return {"result": {"content": [{"type": "text", "text": json.dumps(rows, ensure_ascii=False)}]}}

            with patch.object(collector, "mcp_url", return_value="http://sorftime.test"), patch.object(collector, "call_tool", side_effect=fake_call_tool):
                summary = collector.collect(report_dir, 45, None, ["neck massager"], 75, 0)

            data_pack = json.loads((report_dir / "data" / "data_pack.json").read_text(encoding="utf-8"))
            written_summary = json.loads((report_dir / "data" / "normalized" / "keyword_collection_summary.json").read_text(encoding="utf-8"))
            raw_files = list((report_dir / "data" / "raw").glob("sorftime_keyword_extends_*.json"))

            self.assertTrue(summary["collection_ready"])
            self.assertEqual(summary["calls"], 3)
            self.assertEqual(summary["planned_calls"], 75)
            self.assertEqual(summary["theoretical_row_capacity"], 1500)
            self.assertEqual(summary["min_keywords"], 45)
            self.assertEqual(summary["seed_count"], 1)
            self.assertEqual(summary["warnings"], [])
            self.assertEqual(summary["keywords_added"], 60)
            self.assertEqual(summary["keywords_total"], 60)
            self.assertEqual(summary, written_summary)
            self.assertEqual(len(raw_files), 3)
            self.assertEqual(len(data_pack["sources"]), 3)
            self.assertEqual(data_pack["keywords"][0]["source_type"], "keyword_extends")
            self.assertFalse((report_dir / "data" / "normalized" / "normalized_data_pack.json").exists())


if __name__ == "__main__":
    unittest.main()
