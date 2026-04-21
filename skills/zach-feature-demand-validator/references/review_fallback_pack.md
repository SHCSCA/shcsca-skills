# review_fallback_pack 说明

当 Sorftime MCP 不可用时，可以提供一个本地评论证据包作为降级输入。

## 目录结构

```text
review_source_pack/
├── source_manifest.json
└── raw/
    ├── reviews.csv
    ├── reviews.txt
    └── reviews.html
```

## source_manifest.json 最少字段

- `asin`
- `site`
- `captured_at`
- `source_url`
- `export_method`

## 目标

这个证据包的作用不是替代完整 MCP 数据，而是让 review 维度至少可核查、可追溯、可复用。
