#!/usr/bin/env python3
import unittest

from html_components import (
    esc,
    first,
    has_cjk,
    kpi_card_html,
    mini_chart,
    money,
    num,
    price_band,
    table,
)


class HtmlComponentsTest(unittest.TestCase):
    def test_formats_and_escapes_values(self):
        self.assertEqual(num(1234.4), "1,234")
        self.assertEqual(money(12), "$12.00")
        self.assertEqual(esc("<b>bad</b>"), "&lt;b&gt;bad&lt;/b&gt;")
        self.assertEqual(first(0, "fallback"), 0)
        self.assertEqual(first(False, "fallback"), False)
        self.assertTrue(has_cjk("中文"))
        self.assertEqual(price_band(19.99), "<$20")
        self.assertEqual(price_band(60), "$60+")

    def test_table_and_chart_render_structured_html(self):
        table_html = table(["名称", "值"], [["A&B", 10]])
        filtered_table_html = table(
            ["相关性", "值"],
            [["高相关", 10], ["待判断", 1]],
            filter_options=[("全部", "all"), ("高相关", "高相关")],
            row_filters=["高相关", "待判断"],
        )
        chart_html = mini_chart([("A", 10, "10"), ("B", 5, "5")])

        self.assertIn("<table", table_html)
        self.assertIn("A&amp;B", table_html)
        self.assertIn("filter-bar", filtered_table_html)
        self.assertIn('data-filter="高相关"', filtered_table_html)
        self.assertIn("bar-row", chart_html)
        self.assertIn("--w:100.0%", chart_html)
        self.assertIn("<b>raw</b>", kpi_card_html("HTML", "<b>raw</b>"))


if __name__ == "__main__":
    unittest.main()
