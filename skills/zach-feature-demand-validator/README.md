# zach-feature-demand-validator

> **作者**：SHCSCA
>
> 用真实用户证据验证一个功能点是不是值得做。

功能需求真伪验证器。

这个 Skill 不解决“我要不要做这个品类”，而是解决另一个更常见的问题：

**这个微创新功能，到底是不是用户真的在意。**

对亚马逊卖家来说，大多数产品开发都不是颠覆式创新，而是在现有市场供给上做微创新。问题也往往出在这里：功能看起来合理，不代表需求真实存在。

这个 Skill 用三维数据交叉验证：

| 维度 | 数据源 | 作用 |
|------|--------|------|
| Review 信号 | Sorftime `product_reviews` 或本地 `review_source_pack` | 看用户评论里有没有直接提到、抱怨缺失、或者对现有实现不满意 |
| 关键词信号 | Sorftime `keyword_detail` / `keyword_trend` / `keyword_extends` | 看用户有没有主动搜索这个功能 |
| 社区信号 | WebSearch（Reddit + Quora） | 看用户在购买前有没有讨论这个功能 |

## 它具体能帮你解决什么问题

这个 Skill 解决的不是“大盘值不值得做”，而是更具体的一层：

1. **某个功能是不是用户真正在意**
   比如 self-cleaning、steam、foldable、anti-drip 这种功能，看起来都有道理，但不一定有人愿意为它买单。
2. **用户是真的在抱怨这个缺失，还是只是你主观觉得应该有**
   它会把评论、关键词和社区讨论放在一起看，避免只凭感觉做产品决策。
3. **这个功能是加分项，还是能影响转化的核心卖点**
   最终你拿到的不是一句“我觉得值得做”，而是证据链完整的判断。

## 详细功能介绍

- **评论证据验证**
  从评论里找用户是否直接提到这个功能、抱怨缺失、吐槽现有实现，判断需求是真存在还是伪命题。
- **关键词证据验证**
  看用户是否会主动搜索这个功能点，避免做一个“用户不会搜、不会买、不会感知”的伪创新。
- **社区讨论验证**
  看用户在 Reddit、Quora 这类社区里，是否在购买前就会反复提这个问题。
- **降级证据链支持**
  即使你没有 Sorftime，也能先用本地 review 证据包跑通第一层验证。
- **结构化交付**
  最后会输出 Markdown 结论、标准 CSV 和可回查证据，让你后续继续做产品立项或内部讨论。

## 安装方式

### 方式 1：让 AI 直接安装

适用于 Claude Code、Codex、Cursor、OpenClaw 等 AI 编程 / Agent 环境。

把下面这句话直接发给 AI：

```text
帮我安装 `zach-feature-demand-validator` 这个 skill，来源仓库是 `amazon-skills`。直接装到当前工作区，并把依赖一起检查好。
```

### 方式 2：手动安装

1. clone 仓库
2. 找到 `skills/zach-feature-demand-validator/`
3. 把整个目录复制到你的本地 skills 目录

示例：

```bash
git clone https://github.com/SHCSCA/amazon-skills.git
cd amazon-skills
```

然后复制：

```text
skills/zach-feature-demand-validator/
```

到你的目标 skills 目录。

## 这个 skill 能做什么

这个 skill 主要适合以下任务：

- 判断某个功能是不是用户真需求
- 识别用户是否真的在抱怨某个缺失点
- 判断某个功能是“加分项”还是“会影响转化的核心卖点”
- 在开发前减少拍脑袋立项
- 给选品、产品定义、竞品分析提供证据链

## 两种使用模式

### 1. Sorftime 完整版

适合已经配置 Sorftime MCP 的环境。

- Review 维度：Sorftime
- 关键词维度：Sorftime
- 社区维度：WebSearch

### 2. 无 Sorftime 降级版

适合暂时没有 Sorftime MCP，但手里已经有 Amazon 评论证据的人。

- Review 维度：`review_source_pack`
- 关键词维度：明确写“未验证 / 待补充”
- 社区维度：WebSearch

这不是完整版，但至少能把“评论里到底有没有人在乎这个功能”这条证据链先跑通。

## 输出结果

正常使用后，这个 skill 会产出：

- Markdown 验证报告
- 标准 CSV 数据文件
- 需要时附带 review fallback 证据包
- 支撑内部判断的结构化证据链

## 快速使用

### 业务输入

```text
帮我验证一下 air fryer 加 steam 功能在美国站是不是真需求
帮我验证一下 B0XXXX 的 self-cleaning 功能在 US 站值不值得做
```

### Review fallback 输入

```text
review_source_pack/
├── source_manifest.json
└── raw/
    ├── reviews.csv
    ├── reviews.txt
    └── reviews.html
```

详细格式见 [`references/review_fallback_pack.md`](./references/review_fallback_pack.md)。

## 关于脚本

当前这个公开仓库版本，先开放：

- `SKILL.md`
- `references/`
- `examples/`

便于直接给 AI 使用，或者作为你自己的 skill 模板继续改。

如果你后续想把它做成“可命令行批处理”的完整版本，可以在 `scripts/` 目录继续补上解析与校验脚本。

## 交付物

- 一份 Markdown 验证报告
- 五个标准 CSV
- 若走 fallback，再附一份可核查的 `review_source_pack`

所有 CSV 都会统一输出以下核查字段：

- `数据来源`
- `来源类型`
- `来源链接/查询词`
- `原始文件名`
- `采集时间`

## 上下游

- **上游**：`zach-product-research`、`zach-competitor-deep-dive`
- **下游**：`zach-new-product-listing-writer`

## 如果安装或运行出错，直接让 AI 帮你排查

把下面这段直接发给你的 AI，并把报错信息、截图或终端输出一起贴上：

```text
我已经安装了 `zach-feature-demand-validator`，但现在遇到了问题。请你直接帮我排查并尽量修复：

1. 先判断是 skill 文件缺失、依赖缺失、Sorftime MCP 未连接、Web 搜索链路异常，还是当前 IDE 没有正确加载
2. 自动检查当前工作区里和 `zach-feature-demand-validator` 相关的文件、脚本、references 和依赖
3. 如果可以自动修复，就直接修复
4. 修复后告诉我还需要重启 IDE、重新加载工作区，还是重新运行哪个命令
5. 最后给我一个最短的验证步骤，确认这个 skill 已经能用了
```

## 适合谁用

这个 skill 适合：

- 亚马逊卖家
- 跨境电商运营
- 产品开发 / 选品人员
- 用 AI 做市场研究的人
- 想把验证过程标准化的团队

## 关于作者

作者：**SHCSCA**  
定位：亚马逊与跨境电商场景下的 AI skills 沉淀与实践
