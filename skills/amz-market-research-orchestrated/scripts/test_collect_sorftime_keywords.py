#!/usr/bin/env python3
import json
import unittest

from collect_sorftime_keywords import content_rows, infer_seeds, keyword_entity, parse_sse_json


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


if __name__ == "__main__":
    unittest.main()
