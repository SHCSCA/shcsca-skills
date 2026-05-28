---
name: amz-lifecycle-strategy-report
description: "Amazon / 电商产品全生命周期拓品战略子 Skill。由 amz-market-research-orchestrated 主控调用，基于只读 normalized_data_pack.json 生成 lifecycle-strategy-report.html。"
---

# amz-lifecycle-strategy-report

## 定位

本 Skill 只负责三报告中的“产品全生命周期拓品战略报告”。它不采集数据，不改写主控数据口径，只读取主控生成的 `normalized_data_pack.json`、`analysis_plan.json` 和 `report_brief.json`。

允许做展示层二次聚合：用户画像、生命周期阶段、SKU 优先级、Bundle 组合、30/60/90 天路线图、供应链风险矩阵。展示层聚合必须可回到主控数据，不得制造新事实。

## 输入

```text
reports/{task_id}/data/normalized/normalized_data_pack.json
reports/{task_id}/analysis/analysis_plan.json
reports/{task_id}/report_brief.json
```

## 输出

```text
reports/{task_id}/analysis/lifecycle_strategy.json
reports/{task_id}/output/html_reports/lifecycle-strategy-report.html
```

## 必备板块

1. 战略仪表盘
2. 用户画像
3. 生命周期旅程
4. 四维拓品生态
5. 拓品方案池
6. Bundle 策略
7. 30/60/90 天路线图
8. 风险矩阵
9. 市场验证摘要

## 质量门禁

- SKU、Bundle、AOV、LTV、复购判断必须来自主控数据或明确标注为 AI 推理。
- 子报告只读 `normalized_data_pack.json`，不得自行覆盖全局去重结果。
- 表格必须支持静态站点包的筛选、排序和证据抽屉交互。
- 输出文件固定为 `lifecycle-strategy-report.html`。
