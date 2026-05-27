# amz-create-image v7

Amazon 主图 / 副图 / A+ 美工需求稿 Skill。

## v7 关键更新

- 分阶段交付：先主图/副图，验收通过后再 A+
- 增加 Amazon 运营能力定义：选品定位、关键词意图、转化、广告协同、Review/VOC、竞品拆解、供应链、合规
- 增加 A9/COSMO/Rufus 相关能力定义：把搜索排序、用户意图和对话式购物问题转化为图片策略
- 主图/副图阶段必须先要求用户上传主图/副图参考图
- A+阶段必须等主图/副图验收通过后，再要求用户上传 A+参考图
- 主图/副图只能参考主图/副图参考图，A+只能参考 A+参考图，禁止跨阶段借图
- A+阶段必须在已验收的主图/副图 Excel 内继续补充，并另存新版本，不得用空模板单独做 A+
- Excel 中参考图片必须直接嵌入图片，不得只写文字描述
- 参考图编号、参考图片和参考点必须来自同一索引行，避免图片和描述错配
- 不生成本地路径/图片路径列
- 主图/副图阶段正常 7张、最多9张，按需求拓展，并标明是否轮播
- A+需求一般 5张/5个模块，按需求拓展；除 1464×600 外必须考虑手机端 600×450
- 尺寸/重量若给到 `cm/kg`，必须换算成美国站常用 `in/lb`：`cm × 0.3937 = in`，`kg × 2.20462 = lb`
- 文案必须提供断行版，主标题/副标题/子项分层
- 模板样式修复：去掉异常顶部色条和大面积空白区，统一表格样式

## 文件结构

```text
amz-create-image/
├── SKILL.md
├── README.md
├── templates/
│   └── amz-create-image_workbook.xlsx
└── references/
    ├── phased_workflow.md
    ├── reference_image_rules.md
    ├── copy_line_break_rules.md
    ├── amazon_operation_capabilities.md
    ├── excel_style_spec.md
    ├── output_spec.md      # 输出物类型、Excel必备Sheet/列、最终回复和质量门禁
    └── checklist.md
```

## 使用方式

1. 先收集产品资料。
2. 完成运营判断：关键词意图、Review/VOC、竞品差异、A9/COSMO/Rufus 承接。
3. 要求用户上传主图/副图参考图。
4. 生成主图/副图需求稿并等待验收。
5. 验收通过后要求用户上传 A+参考图。
6. 在原主图/副图需求稿工作簿内补充 A+需求稿，并另存新版本。
