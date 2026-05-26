# Research Scope Menu v2

Use this menu only when the user has not already specified purpose, market, depth, or output.

## Purpose Prompt

```text
这次调研主要服务哪个决策？
1. 是否进入一个新品类/新市场
2. 现有产品迭代优化
3. 发现新的细分人群/场景/价格带
4. 竞品拆解和差异化定位
5. 社媒/VOC 用户洞察
6. 供应链、利润和可行性验证
7. 老板/客户汇报
```

Choose one primary purpose and at most two secondary purposes.

## Depth Prompt

```text
我可以按三档数据深度做：

1. 快速版：Amazon 关键词 + 产品池 20-50 + 核心竞品评论 + 3-5 个公开来源。
2. 标准版：Amazon Top100/近似 Top100 + 关键词趋势 + 竞品详情/趋势/评论/变体 + TikTok 相似产品 + 1688 相似货源 + 公开报告。（推荐）
3. 深度版：标准版基础上做多关键词去重、竞品分层、TikTok 视频/达人链路、1688 成本带和完整数据缺口说明，适合立项或老板汇报。

目标默认 Amazon US + TikTok Shop US + 1688 中国供应端。是否调整？
```

## Output Prompt

```text
报告完成后默认交付 HTML + Markdown + Data Pack。
如果你有特殊偏好，可以改成：
1. 默认本地 HTML + Markdown + Data Pack
2. 只要 Markdown + Data Pack
3. 增加可复核原始数据目录
4. 为老板/客户汇报强化视觉和摘要
```

v2 does not write to Feishu, Notion, or Obsidian. Keep those as future delivery targets.

## Scope to DataNeed Mapping

| Scope | Required Data | Optional Data | Default Depth |
|---|---|---|---|
| Quick | Amazon keyword detail, search results/product pool 20-50, core product detail, core product reviews, Firecrawl 3-5 sources | TikTok similar product, 1688 similar product | quick |
| Standard | Amazon near-Top100, keyword trend/extensions/search results, at least 1000 deduped keyword samples, product detail/trend/variations/reviews/traffic terms, TikTok similar products/trends, 1688 similar products, Firecrawl reports/brand/review/policy sources | Walmart retail comparison | standard |
| Deep | Standard data, at least 1000 deduped keyword samples, multi-keyword product pool dedupe, competitor tiers, TikTok videos/creators, broader 1688 supplier/cost proxy, stronger source coverage and data gaps | User files, supplier quotes, internal ads data | deep |

## User Confirmation Summary

```text
本次调研范围确认：

- 研究对象：
- 任务目的：
- 目标市场：
- 数据深度：
- Sorftime 模块：
- Firecrawl 补充：
- 预计输出：
- 输出风格：
- 约束条件：
```
