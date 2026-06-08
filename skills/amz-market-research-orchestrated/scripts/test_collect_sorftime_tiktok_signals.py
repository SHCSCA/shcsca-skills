#!/usr/bin/env python3
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import collect_sorftime_tiktok_signals as collector


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class CollectSorftimeTikTokSignalsTest(unittest.TestCase):
    def test_product_and_video_field_mapping(self):
        product = collector.product_entity(
            {
                "ProductId": "1730154626423755709",
                "Title": "Under Cabinet Light",
                "品牌": "SHINE PAL",
                "卖家": "Tuffenough",
                "月销量": 7522,
                "周销量": 1083,
                "价格": 18.99,
                "星级": 4.6,
                "评论数量": 16813,
            },
            "src",
            "under cabinet lights",
        )
        self.assertEqual(product["product_id"], "1730154626423755709")
        self.assertEqual(product["monthly_sales"], 7522)
        self.assertEqual(product["review_count"], 16813)

        video = collector.video_entity(
            {
                "url": "https://www.tiktok.com/@maggy/video/7646541144737729805",
                "标题": "LED demo",
                "播放量": "126",
                "获赞量": "2",
                "达人": "MAGGYS",
            },
            "src_video",
            "1730154626423755709",
        )
        self.assertEqual(video["video_id"], "7646541144737729805")
        self.assertEqual(video["views"], 126)
        self.assertEqual(video["author"], "MAGGYS")

    def test_collect_uses_documented_tiktok_schema_and_enriches_products(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(
                report_dir / "data" / "data_pack.json",
                {
                    "sources": [],
                    "research_object": {"value": "under cabinet lights"},
                    "products": [],
                    "keywords": [],
                    "tiktok_products": [],
                    "tiktok_videos": [],
                    "data_gaps": [],
                },
            )
            seen_calls = []

            def fake_call_tool(_url, name, args):
                seen_calls.append((name, dict(args)))
                if name == collector.SIMILAR_TOOL:
                    self.assertEqual(args, {"searchName": "under cabinet lights", "page": 1, "site": "US"})
                    rows = [
                        {
                            "ProductId": "p1",
                            "Title": "Under Cabinet Light",
                            "品牌": "Brand A",
                            "月销量": 500,
                            "价格": 19.99,
                            "星级": 4.6,
                            "评论数量": 120,
                        }
                    ]
                    return {"result": {"content": [{"type": "text", "text": json.dumps(rows, ensure_ascii=False)}]}}
                if name == collector.DETAIL_TOOL:
                    self.assertEqual(args, {"productId": "p1", "site": "US"})
                    return {"result": {"content": [{"type": "text", "text": json.dumps({"累计销量": 9000, "所属类目": "Lighting"}, ensure_ascii=False)}]}}
                if name == collector.TREND_TOOL:
                    self.assertEqual(args, {"productId": "p1", "site": "US"})
                    return {"result": {"content": [{"type": "text", "text": json.dumps({"产品销量趋势": ["2026-05-31=500"]}, ensure_ascii=False)}]}}
                if name == collector.AUTHOR_TOOL:
                    self.assertEqual(args, {"productId": "p1", "site": "US"})
                    return {"result": {"content": [{"type": "text", "text": json.dumps({"带货达人数": 12, "达人清单": [{"达人名称": "A"}]}, ensure_ascii=False)}]}}
                if name == collector.VIDEO_TOOL:
                    self.assertEqual(args, {"productId": "p1", "page": 1, "site": "US"})
                    rows = [{"url": "https://www.tiktok.com/@a/video/123", "标题": "Demo", "播放量": 1000, "获赞量": 50, "达人": "A"}]
                    return {"result": {"content": [{"type": "text", "text": json.dumps(rows, ensure_ascii=False)}]}}
                raise AssertionError(name)

            with patch.object(collector, "mcp_url", return_value="http://sorftime.test"), patch.object(collector, "call_tool", side_effect=fake_call_tool):
                summary = collector.collect(report_dir, "US", [], 1, 1, 1, 1, 1, 0)

            self.assertTrue(summary["collection_ready"])
            self.assertEqual(summary["products_added"], 1)
            self.assertEqual(summary["videos_added"], 1)
            self.assertEqual(len(seen_calls), 5)
            data_pack = json.loads((report_dir / "data" / "data_pack.json").read_text(encoding="utf-8"))
            self.assertEqual(data_pack["tiktok_products"][0]["lifetime_sales"], 9000)
            self.assertEqual(data_pack["tiktok_products"][0]["author_count"], 12)
            self.assertEqual(data_pack["tiktok_videos"][0]["video_id"], "123")

    def test_collect_records_tiktok_mcp_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(report_dir / "data" / "data_pack.json", {"sources": [], "research_object": {"value": "light"}, "tiktok_products": [], "tiktok_videos": [], "data_gaps": []})

            def fake_call_tool(_url, _name, _args):
                return {"result": {"isError": True, "content": [{"type": "text", "text": "bad tk args"}]}}

            with patch.object(collector, "mcp_url", return_value="http://sorftime.test"), patch.object(collector, "call_tool", side_effect=fake_call_tool):
                summary = collector.collect(report_dir, "US", [], 1, 1, 1, 1, 1, 0)

            self.assertFalse(summary["collection_ready"])
            self.assertIn("bad tk args", summary["errors"][0]["error"])
            data_pack = json.loads((report_dir / "data" / "data_pack.json").read_text(encoding="utf-8"))
            self.assertEqual(data_pack["data_gaps"][0]["type"], "tiktok_signal_depth")

    def test_cli_accepts_full_tiktok_site_enum(self):
        with tempfile.TemporaryDirectory() as tmp:
            report_dir = Path(tmp)
            write_json(report_dir / "data" / "data_pack.json", {"sources": [], "research_object": {"value": "light"}, "tiktok_products": [], "tiktok_videos": [], "data_gaps": []})

            def fake_call_tool(_url, name, args):
                self.assertEqual(name, collector.SIMILAR_TOOL)
                self.assertEqual(args, {"searchName": "light", "page": 1, "site": "JP"})
                rows = [{"ProductId": "jp1", "Title": "Light", "月销量": 10}]
                return {"result": {"content": [{"type": "text", "text": json.dumps(rows, ensure_ascii=False)}]}}

            with patch.object(collector, "mcp_url", return_value="http://sorftime.test"), patch.object(collector, "call_tool", side_effect=fake_call_tool):
                code = collector.main(["--dir", str(report_dir), "--site", "JP", "--max-seeds", "1", "--max-pages", "1", "--max-products-detail", "0", "--min-signals", "1", "--sleep", "0"])

            self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
