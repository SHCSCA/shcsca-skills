# Research Scope Menu

Use this menu when asking the user to confirm data scope. Purpose and output should be confirmed separately unless the user already specified them.

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

## Quick Prompt

```text
我可以按三个数据深度做：

1. Amazon-only 快速版：Amazon 市场/竞品/评论/关键词，适合先判断类目是否值得看。
2. 电商 + 社媒标准版：Amazon + Reddit + YouTube，可同时看竞品表现和用户真实讨论。（推荐）
3. 全域深度版：Amazon + Reddit + YouTube + TikTok/TikTok Shop + Keepa 历史 + 1688/供应链 + 公开报告，适合立项或老板汇报。

你希望用哪一档？目标站点默认 Amazon US，是否要改？
```

## Output Prompt

```text
报告完成后你希望怎么交付？
1. 默认本地 HTML 报告
2. HTML + Markdown + 数据包
3. 写入飞书/Lark 文档或知识库
4. 写入 Obsidian/Notion/其他知识库连接器

默认风格：全中文本土化、老练犀利、讲人话；网页报告采用理性美学直角卡片和交互图表，文档报告采用结构化表格/列表。
是否把这个选择保存为以后市场调研的默认输出方式？
```

## Scope to DataNeed Mapping

| Scope | Required Data | Optional Data | Default Depth |
|---|---|---|---|
| Amazon-only | Amazon market snapshot, competitor pool, listing details, reviews, keywords | Keepa history | quick |
| Ecommerce + social | Amazon-only data, Reddit discussions, YouTube videos/comments, web reports | YouTube transcripts, Keepa | standard |
| Full domain | Standard data, TikTok/TikTok Shop, Keepa, 1688, supplier files, brand/web reports | Jimu connector | deep |

## User Confirmation Summary

```text
本次调研范围确认：

- 研究对象：
- 目标市场：
- 深度：
- 数据源：
- 方法链：
- 预计输出：
- 输出风格：
- 先小样本验证：

确认后我会生成 OrchestrationBrief，再分别调度数据源、方法论和输出三个编排器。
```
