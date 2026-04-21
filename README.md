# amazon-skills

一个面向 **亚马逊卖家 / 跨境电商团队 / AI 工作流** 的 Skills 合集仓库。

这个仓库的目标，不是放零散提示词，而是沉淀一套可以持续复用的 **Amazon 运营、选品、需求验证、竞品分析、内容生成** 能力模块。

## 作者

**SHCSCA**

## 项目定位

`amazon-skills` 主要服务以下场景：

- 亚马逊新品开发前的市场验证
- 功能点 / 微创新需求判断
- 竞品研究与评论痛点归因
- 关键词与用户需求信号交叉验证
- 后续可扩展到 listing、A+、广告、内容生成、运营 SOP 等方向

也就是说，这个仓库会逐步沉淀成一个 **亚马逊 skills 合集**，让 AI 在具体业务任务里不只是“会聊天”，而是真的能按方法做事。

## 当前收录的 Skills

| Skill | 作用 | 适用场景 |
|---|---|---|
| `zach-feature-demand-validator` | 用 Review / 关键词 / 社区三维证据验证一个功能点是不是真需求 | 选品后判断某个功能值不值得做、要不要跟进、是否是真需求 |

## Skill 详细说明

### 1. zach-feature-demand-validator

这是当前仓库里第一批收录的核心 skill。

它解决的不是“这个品类值不值得做”，而是更关键也更常见的问题：

**某个功能点，到底是不是用户真的在意。**

它会从三个维度交叉验证：

- **Review 信号**：用户有没有提到、抱怨缺失、吐槽现有实现
- **关键词信号**：用户有没有主动搜索这个功能
- **社区信号**：用户在 Reddit / Quora 等社区是否反复讨论这个问题

适合用来判断：

- 某个微创新要不要立项
- 某个功能是卖点还是伪需求
- 用户是真的在抱怨，还是卖家自己想象出来的需求

## 仓库结构

```text
amazon-skills/
├── README.md
└── skills/
    └── zach-feature-demand-validator/
        ├── SKILL.md
        ├── README.md
        ├── references/
        ├── examples/
        └── scripts/
```

## 如何安装

### 方式 1：让 AI 直接安装

适用于 Claude Code、Codex、Cursor、OpenClaw 等可直接操作工作区的 AI 环境。

你可以把下面这句话直接发给 AI：

```text
帮我安装 `zach-feature-demand-validator` 这个 skill，来源仓库是 `amazon-skills`。直接装到当前工作区，并把依赖一起检查好。
```

### 方式 2：手动安装单个 skill

1. clone 本仓库
2. 进入 `skills/`
3. 把目标 skill 目录复制到你的本地 skills 目录

例如：

```bash
git clone https://github.com/SHCSCA/amazon-skills.git
cd amazon-skills
```

然后把：

```text
skills/zach-feature-demand-validator/
```

复制到你的实际 skills 目录中。

### 方式 3：把整个仓库作为 skills 来源库

如果你的 AI / Agent 支持从 GitHub 仓库直接读取 skills，也可以直接把这个仓库作为统一来源仓库使用，后续新增 skill 时就不用反复单独分发。

## 如何使用

安装完成后，直接在你的 AI 环境中调用对应 skill 即可。

例如当前仓库内的：

- `/zach-feature-demand-validator`

典型使用方式：

```text
/zach-feature-demand-validator 帮我验证一下 air fryer 的 steam 功能在美国站是不是真需求
```

## 适合谁用

这个仓库适合：

- 亚马逊卖家
- 跨境电商运营
- 独立站 / 电商选品团队
- 用 AI 做市场研究和产品开发的人
- 想把业务方法论沉淀成 skill 的团队

## 后续规划

后续会继续往这个仓库里补充更多 Amazon 方向 skills，例如：

- 选品研究
- 竞品深挖
- Listing 生成
- A+ / Q&A 内容生产
- 评论分析
- 广告与关键词运营辅助

## 当前状态

这是第一版公开仓库，已完成基础结构搭建，并收录了第一个可用 skill。后续会持续扩展。
