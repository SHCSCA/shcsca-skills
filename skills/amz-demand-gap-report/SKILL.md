---
name: amz-demand-gap-report
description: "Amazon / 电商用户心智断层与需求机会子 Skill。由 amz-market-research-orchestrated 主控调用，基于只读 normalized_data_pack.json 生成 demand-gap-report.html。"
---

# amz-demand-gap-report

## 定位

本 Skill 只负责三报告中的“用户心智断层与需求机会报告”。它不采集数据，不改写主控数据口径，只读取主控生成的 `normalized_data_pack.json`、`analysis_plan.json` 和 `report_brief.json`。

允许做展示层二次聚合：`$APPEALS` 痛点图、满意度鸿沟、KANO × JTBD、用户原声分组、需求优先级。展示层聚合必须可回到主控数据，不得制造新事实。

## 输入

```text
reports/{task_id}/data/normalized/normalized_data_pack.json
reports/{task_id}/analysis/analysis_plan.json
reports/{task_id}/report_brief.json
```

## 输出

```text
reports/{task_id}/analysis/demand_gap.json
reports/{task_id}/output/html_reports/demand-gap-report.html
```

## 必备板块

1. 研究对象概述
2. 决策看板
3. `$APPEALS` 痛点图
4. 满意度鸿沟
5. `KANO × JTBD`
6. 用户原声
7. 需求优先级

## 质量门禁

- 用户原声只展示中文摘要、情绪、主题和动作含义；英文原评只留在审计文件。
- 子报告只读 `normalized_data_pack.json`，不得自行覆盖全局去重结果。
- 表格必须支持静态站点包的筛选、排序和证据抽屉交互。
- 输出文件固定为 `demand-gap-report.html`。
