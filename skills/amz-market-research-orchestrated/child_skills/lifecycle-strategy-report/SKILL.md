---
name: amz-lifecycle-strategy-report
description: "Amazon / 电商产品全生命周期拓品战略子 Skill。由 amz-market-research-orchestrated 主控调用，基于只读 normalized_data_pack.json 生成 lifecycle-strategy-report.html。"
---

# amz-lifecycle-strategy-report

## 定位

本 Skill 是 `amz-market-research-orchestrated` 的内部 child module，不作为顶层入口单独触发。它只负责三报告中的“产品全生命周期拓品战略报告”，不采集数据，不改写主控数据口径，只读取主控生成的 `normalized_data_pack.json`、`analysis_plan.json`、`report_brief.json` 和 `lifecycle_strategy_view.json`。

允许做展示层二次聚合：用户画像、生命周期阶段、SKU 优先级、Bundle 组合、30/60/90 天路线图、供应链风险矩阵。展示层聚合必须可回到主控数据，不得制造新事实。

## 输入

```text
reports/{task_id}/data/normalized/normalized_data_pack.json
reports/{task_id}/analysis/analysis_plan.json
reports/{task_id}/report_brief.json
reports/{task_id}/analysis/lifecycle_strategy_view.json
```

## 输出

```text
reports/{task_id}/analysis/lifecycle_strategy.json
reports/{task_id}/output/html_reports/lifecycle-strategy-report.html
```

## 内部执行入口

```text
python skills/amz-market-research-orchestrated/child_skills/lifecycle-strategy-report/scripts/render_lifecycle_strategy_report.py --dir reports/{task_id}
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
- 优先消费 `lifecycle_strategy_view.json` 的 `kpis`、`charts`、`tables`、`cards`、`evidence_strength`、`sample_coverage`、`limitations`、`client_safe_text`。
- 子报告只读 `normalized_data_pack.json`，不得自行覆盖全局去重结果。
- 表格必须支持静态站点包的筛选、排序和证据抽屉交互。
- 输出文件固定为 `lifecycle-strategy-report.html`。
