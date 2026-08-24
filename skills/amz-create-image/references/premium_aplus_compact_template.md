# 高级 A+ 简版模板规则

本文件用于高级 A+ 阶段。执行前以当前站点 A+ Content Manager 显示的模块、字段和限制为最终准绳。

## 官方基础要求

- 单图格式：JPG、BMP 或 PNG
- 色彩空间：RGB
- 单图大小：不超过2MB
- 分辨率：至少72 dpi
- 高级 A+ 最多7个模块

## 推荐5模块结构

| 模块 | Amazon模块 | 用途 | 关键规格 |
|---|---|---|---|
| M1 | Premium Full Image | 品牌首屏与品类认知 | 桌面1464×600；手机600×450；Headline≤80；Body≤300 |
| M2 | Premium Navigation Carousel | 功能/购买理由轮播 | 2–5帧；每帧双端图 |
| M3 | Full Image / Hotspots / Regimen Carousel | 使用教育、结构或步骤 | 按内容选择，不机械固定 |
| M4 | Premium Simple Image Carousel | 人群、地点、部位或时机场景 | 2–6帧；每帧双端图 |
| M5 | Premium Comparison Table 2 | 同品牌变体/产品选择 | 2–3产品；2–5特征；图≥300×225 |

若不足2个真实可关联产品，M5改为：

- Premium Q&A
- Premium Full Video
- Premium Technical Specifications

## Excel 标准输出结构

A+需求 Sheet 不把所有内容混成一张长表。固定结构为：

1. 顶部标题与产品元信息区。
2. 蓝色六列表头。
3. M1–M5 主模块总览，每模块一行。
4. 黄色 `M2 功能轮播详细拆分` 分隔条。
5. 重复蓝色六列表头。
6. M2 每个 Panel 单独一行。
7. 黄色 `M4 场景轮播详细拆分` 分隔条。
8. 重复蓝色六列表头。
9. M4 每个 Panel 单独一行。

要求：

- M2/M4主模块总览行只说明轮播目的、帧数与整体节奏。
- 每个轮播帧在详细区单独写桌面/手机构图、原生字段、参考图、Alt Text与禁用。
- 不得只写 `4 Panels` 而没有帧级执行说明。
- 每个视觉执行行必须有真实A+参考图。
- Premium Q&A、技术规格等原生文本模块在参考图列写 `原生文本模块｜无需上传图片`。

## 功能轮播

使用 `Premium Navigation Carousel`：

- Panels：2–5
- Navigation text：≤25字符
- Subheadline：≤25字符
- Headline：≤25字符
- Body text：≤100字符
- 桌面图：1464×600
- 手机图：600×450
- 每个 Panel 各需要桌面图和手机图

执行规则：

- 每帧只讲一个功能、部件、动作或购买理由。
- 不将五个功能压进同一帧。
- 产品和关键动作避开导航标签、箭头和手机裁切区。
- 原生字段承载标题与正文，图片只保留必要短标签。
- 每帧在Excel详细区单独一行，并给独立参考图。

## 场景轮播

使用 `Premium Simple Image Carousel`：

- Panels：2–6
- Headline：≤50字符
- Body text：≤200字符
- 桌面图：1464×600
- 手机图：600×450
- 每个 Panel 各需要桌面图和手机图

执行规则：

- 每帧只讲一个人群、地点、部位或使用时机。
- 场景承担代入任务，不重复功能轮播的参数。
- 人物动作、部位和环境必须符合说明书。
- 桌面与手机分别构图，不把桌面横图机械裁成手机图。
- 模板默认预留5帧；需要第6帧时复制同结构新增。
- 每帧在Excel详细区单独一行，并给独立参考图。

## 对比表

`Premium Comparison Table 2`：

- Products：2–3
- Features：2–5
- Product image：至少300×225
- Module headline：≤80字符
- Image headline：≤30字符
- Feature：≤30字符
- Body text：≤80字符

只比较同品牌真实产品或变体。禁止：

- 与竞品或传统方案比较
- 价格、折扣或“better value”
- 虚构差异
- 为凑数关联不相关 ASIN

## 参考图交付

默认在Excel参考图列使用远程 `IMAGE()` 公式：

```excel
=IMAGE("https://...","APLUS_REF_01",0)
```

要求：

- 只使用直接HTTPS图片文件地址。
- 当前竞品缺少对应A+图时继续全网搜索同类型A+模块。
- 远程图片不显示时更换来源，不得留下空白图片框。
- 用户需允许Excel/WPS外部内容。
- 实体嵌图仅在用户明确要求离线可见时使用，并须在目标软件验证。

## 模块选择原则

- 有多个互不重复功能：优先功能轮播。
- 有多个真实使用情境：优先场景轮播。
- 只有1–2个核心功能：用 Full Image 或 Hotspots，不强制轮播。
- 使用顺序重要：考虑 Regimen Carousel 或步骤型 Full Image。
- 售后疑虑多：考虑 Premium Q&A。
- 操作动态强：考虑 Premium Video。

## 官方来源

- Premium A+ Module Guide
  https://m.media-amazon.com/images/G/01/BX_Marketing/2023/AMZ_Guide_Premium_A_Module_05b.pdf
- A+ Content Guide
  https://sellercentral.amazon.com/help/hub/reference/external/GLG4RQK2Y2RJADU4
- A+ Content Overview
  https://sellercentral.amazon.com/help/hub/reference/external/G202102930
