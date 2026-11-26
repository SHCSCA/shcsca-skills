---
name: cyber-motuo-aihot-intake
description: >
  AIHOT 多路径资讯采集 Skill。用户要求获取 AIHOT 最新资讯、日报、热点、最近24小时/7天动态，或公众号流水线启动时触发。
---

# AIHOT 多路径资讯采集

## 目标
取得 AIHOT 实际资讯条目，而不是只读到接入说明。输出可追溯的条目、时间、来源和 URL。

## 必须执行的多路径尝试

### 路径 A：外部 AIHOT Skill
1. 检查 Agent 是否发现 `aihot` Skill。
2. 若存在，激活它，分别请求过去24小时、最近7天、当前热点榜和当日日报。
3. 要求返回标题、AIHOT 条目链接、原始发布时间、来源和摘要。
4. 若未发现或失败，记录错误并继续。

### 路径 B：AIHOT REST API
1. 先读取 `https://aihot.news/api/v1/agent`。
2. 按官方说明确认当前端点和参数。
3. 官方接入页列出的最新资讯验证地址为 `https://aihot.news/api/v1/agent/latest`。
4. 如失败，重试一次并检查是否误用旧接口。
5. 不得使用已停用的 `/api/public/*`，不得猜测路由、参数、游标或鉴权字段。

### 路径 C：AIHOT 官网
分别尝试：
- `https://aihot.news/`
- `https://aihot.news/all`
- `https://aihot.news/hot`
- `https://aihot.news/daily`
- `https://aihot.news/topics`

若首页动态加载失败，继续尝试全部动态、热点榜、日报或主题页。记录实际读取成功的页面。

### 路径 D：RSS
1. 打开 `https://aihot.news/agent?tab=rss`。
2. 从官方页面复制当前 RSS 地址。
3. 使用 RSS 阅读器、HTTP 获取或可用连接器读取。
4. 不得凭经验猜 RSS URL。

### 路径 E：MCP
1. 打开 `https://aihot.news/agent?tab=mcp`。
2. 读取官方 MCP 地址和工具清单。
3. 只有运行环境支持远程 MCP 且实际连接成功时才使用。
4. 不得声称 MCP 已连接，除非实际调用成功。

## 重试策略
- 至少执行三条独立路径。
- 第一条路径成功后，仍至少再尝试一条独立路径核对新鲜度或完整性。
- 单条路径失败后切换路径，不要连续重复同一个失败请求冒充多路径尝试。
- 每次记录时间、端点/页面、结果和错误摘要。
- 至少一条路径必须返回真实资讯条目，才算采集成功。

## 成功判定
每条资讯尽量取得：AIHOT item ID、AIHOT URL、标题、AIHOT收录时间、原始发布时间、原始来源、原始来源 URL、摘要/推荐理由、事件主题。
读取到接入说明、OpenAPI 文档或 Skill README，不算资讯数据成功。

## 时间与去重
- 默认时区 `Asia/Shanghai`。
- 同一事件不同媒体报道合并成事件簇。
- 区分首次发布、AIHOT收录、后续更新。
- 不把日报、热点榜、全部动态的重复条目相加。
- 优先24小时，不足时扩展到最近7天。
- 不得把旧新闻包装成当天刚发生。

## 失败时
若所有路径均失败，停止选题和写作，输出逐条失败记录；不得用普通 Web 搜索的新闻冒充 AIHOT 数据。
