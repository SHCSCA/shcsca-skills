#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import collect_sorftime_reviews as collector


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class CollectSorftimeReviewsTest(unittest.TestCase):
    def test_parse_sse_json_and_content_rows(self):
        body = 'event: message\n' + 'data: {"result":{"content":[{"type":"text","text":"[{\\"评论\\":\\"Works well\\",\\"评星\\":\\"5\\"}]"}]},"id":1,"jsonrpc":"2.0"}\n'

        parsed = collector.parse_sse_json(body)
        rows = collector.content_rows(parsed)

        self.assertEqual(rows, [{"评论": "Works well", "评星": "5"}])

    def test_review_entity_maps_sorftime_fields(self):
        row = {
            "评星": "4",
            "评论日期": "2026-05-01",
            "标题": "Good",
            "评论": "Works well",
            "评论产品的属性": "White",
            "有用数": "12",
        }

        entity = collector.review_entity(row, "B0TEST1234", "sf_product_reviews_b0test1234_both", "Both")

        self.assertEqual(entity["asin"], "B0TEST1234")
        self.assertEqual(entity["rating"], 4)
        self.assertEqual(entity["review_date"], "2026-05-01")
        self.assertEqual(entity["text"], "Works well")
        self.assertEqual(entity["helpful_votes"], 12)
        self.assertEqual(entity["provider"], "sorftime")

    def test_collect_continues_after_one_failed_asin_and_records_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(
                report_dir / "data" / "data_pack.json",
                {
                    "research_object": {"seed_asins": ["B0FAIL0001", "B0OK000002"]},
                    "sources": [],
                    "products": [],
                    "reviews": [],
                    "data_gaps": [],
                },
            )

            def fake_call_tool(_url, _name, args):
                if args["asin"] == "B0FAIL0001":
                    raise RuntimeError("network timeout")
                return {
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps([{"评论": "Works well", "评星": "5"}], ensure_ascii=False),
                            }
                        ]
                    }
                }

            with patch.object(collector, "mcp_url", return_value="http://sorftime.test"), patch.object(collector, "call_tool", side_effect=fake_call_tool):
                summary = collector.collect(report_dir, [], "Both", "US", 0)

            data_pack = json.loads((report_dir / "data" / "data_pack.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["calls"], 2)
            self.assertEqual(summary["reviews_added"], 1)
            self.assertEqual(len(summary["failures"]), 1)
            self.assertEqual(data_pack["reviews"][0]["asin"], "B0OK000002")
            self.assertEqual(data_pack["data_gaps"][0]["type"], "review_collection_failure")
            self.assertFalse((report_dir / "data" / "normalized" / "normalized_data_pack.json").exists())


if __name__ == "__main__":
    unittest.main()
