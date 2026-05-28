---
name: amz-market-depth-report
description: "Amazon / 电商市场深度调研子 Skill。由 amz-market-research-orchestrated 主控调用，基于只读 normalized_data_pack.json 生成 market-depth-report.html。"
---

# amz-market-depth-report

## 定位

本 Skill 只负责三报告中的“市场深度调研报告”。它不采集数据，不改写主控数据口径，只读取主控生成的 `normalized_data_pack.json`、`analysis_plan.json` 和 `report_brief.json`。

允许做展示层二次聚合：价格带分桶、竞品分层、VOC 主题排序、TikTok 内容信号摘要、1688 成本带汇总、风险行动表。展示层聚合必须可回到主控数据，不得制造新事实。

## 输入

```text
reports/{task_id}/data/normalized/normalized_data_pack.json
reports/{task_id}/analysis/analysis_plan.json
reports/{task_id}/report_brief.json
```

## 输出

```text
reports/{task_id}/analysis/market_depth.json
reports/{task_id}/output/html_reports/market-depth-report.html
```

## 必备板块

1. 大盘结论
2. 需求结构
3. 竞品格局
4. VOC 洞察
5. 标杆打法
6. 机会定义
7. TikTok 内容信号
8. 1688 供应链判断
9. 风险与行动摘要

## 质量门禁

- 客户版 HTML 不展示 `source_id`、ASIN、provider、raw path 或英文原始评论。
- 表格必须支持静态站点包的筛选、排序和证据抽屉交互。
- 结论必须先写商业含义，再写建议动作。
- 输出文件固定为 `market-depth-report.html`。
