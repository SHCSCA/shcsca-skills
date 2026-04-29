# shcsca-skills

一个面向 **亚马逊卖家 / 跨境电商团队 / AI 工作流** 的 Skills 合集仓库。

这个仓库的目标，不是放零散提示词，而是沉淀一套可以持续复用的 **Amazon 运营、选品、需求验证、竞品分析、内容生成** 能力模块。

## 作者

**SHCSCA**

## 当前收录的 Skills

| Skill | 来源 | 作用 | 适用场景 |
|-------|------|------|---------|
| `zach-feature-demand-validator` | 自建 | 用 Review / 关键词 / 社区三维证据验证功能点是不是真需求 | 选品功能立项判断 |
| `neat-freak` | khazix | 任务完成后自动同步文档/CLAUDE.md/记忆，防止 Agent 脑腐 | 所有 AI 任务收尾 |
| `hv-analysis` | khazix | 横纵分析法——万字 PDF 研究报告，竞品/公司/概念全景调研 | 市场调研、竞品分析 |
| `khazix-writer` | khazix | 模拟作者口吻写长文，拒绝空洞词汇 | 公众号 / 品牌内容 |
| **mattpocock 工程系列** | mattpocock | TDD、调试、架构改善、PRD 产出 | 软件开发流程 |
| **mattpocock 生产力系列** | mattpocock | 需求拷问、沟通压缩、Skill 编写 | 团队协作与沟通 |

---

## Skill 详细说明

### 1. zach-feature-demand-validator（自建）

解决"某个功能点，到底是不是用户真的在意"。

从三个维度交叉验证：
- **Review 信号**：用户有没有提到、抱怨缺失
- **关键词信号**：用户有没有主动搜索这个功能
- **社区信号**：Reddit / Quora 等社区是否反复讨论

```
/zach-feature-demand-validator 帮我验证一下 air fryer 的 steam 功能在美国站是不是真需求
```

### 2. neat-freak（khazix）

每次任务完成后自动同步三层：
- 项目根的 CLAUDE.md / AGENTS.md（给 AI 看的）
- 项目的 docs/ 和 README（给同事看的）
- Agent 自己的记忆系统（给跨会话的自己看的）

触发方式：`/neat` 或 `整理一下` 或 `同步一下`

### 3. hv-analysis（khazix）

横纵分析法——同时跑两条线：
- **纵向**：从诞生到当下，完整演变
- **横向**：同期所有主要竞品逐一对比

输出排版精美的 PDF 研究报告，10,000–30,000 字，适合竞品调研、公司研究、概念入门。

### 4. khazix-writer（khazix）

模拟作者口吻写长文，拒绝"赋能、抓手、闭环"等空洞词汇。

四层自检体系：结构、节奏、内容、文字。

### 5. mattpocock 工程系列

| Skill | 作用 |
|-------|------|
| `diagnose` | 系统性调试循环：复现→最小化→假设→验证→修复→回归 |
| `grill-with-docs` | 上线前灵魂拷问，建立团队共享语言，更新 CONTEXT.md 和 ADR |
| `triage` | Issue 分诊状态机 |
| `improve-codebase-architecture` | 发现代码架构深化机会，防止代码腐烂 |
| `setup-matt-pocock-skills` | 每个项目跑一次，初始化 Issue Tracker / 标签 / 文档结构 |
| `tdd` | 红绿重构测试驱动开发 |
| `to-issues` | 将 PRD 分解为垂直切片的 GitHub Issue |
| `to-prd` | 将对话上下文合成 PRD 并提交为 GitHub Issue |
| `zoom-out` | 让 Agent 从系统整体视角解释代码 |

### 6. mattpocock 生产力系列

| Skill | 作用 |
|-------|------|
| `caveman` | 压缩沟通语言，节省约 75% token |
| `grill-me` | 需求拷问——彻底理清再开工 |
| `write-a-skill` | 创建新 skill 的模板 |

### 7. mattpocock 工具系列

| Skill | 作用 |
|-------|------|
| `git-guardrails-claude-code` | 拦截危险 git 命令（push/reset --hard/clean） |
| `migrate-to-shoehorn` | 迁移类型断言到 @total-typescript/shoehorn |
| `scaffold-exercises` | 创建练习目录结构 |
| `setup-pre-commit` | 配置 Husky + lint-staged + Prettier + 类型检查 + 测试 |

---

## 仓库结构

```text
shcsca-skills/
├── README.md
└── skills/
    ├── zach-feature-demand-validator/    # 自建 · 需求验证
    ├── neat-freak/                       # khazix · 任务收尾同步
    ├── hv-analysis/                      # khazix · 横纵分析法调研
    ├── khazix-writer/                    # khazix · 写作风格
    ├── engineering/                      # mattpocock · 工程系列
    ├── productivity/                     # mattpocock · 生产力系列
    └── misc/                             # mattpocock · 工具系列
```

## 如何安装

### 方式 1：让 AI 直接安装

适用于 Claude Code、Codex、Cursor、OpenClaw 等可直接操作工作区的 AI 环境。

```text
帮我安装 `hv-analysis` 这个 skill，来源仓库是 `shcsca-skills`。直接装到当前工作区。
```

### 方式 2：手动安装

```bash
# clone 本仓库
git clone https://github.com/SHCSCA/shcsca-skills.git
cd shcsca-skills

# 复制单个 skill 到你的 skills 目录
cp -r skills/<skill-name> ~/.openclaw/skills/
```

### 方式 3：通过包管理器

```bash
# ClawHub
clawhub install <skill-name>

# Tessl
tessl install shcsca-skills/<skill-name>
```

## 适合谁用

- 亚马逊卖家 & 跨境电商运营
- 用 AI 做市场研究和产品开发的人
- 独立站 / 电商选品团队
- 想把业务方法论沉淀成 skill 的团队
- 软件工程团队（mattpocock 工程系列）

## 后续规划

- 选品研究 skill
- 竞品深挖 skill
- Listing 生成 skill
- A+ / Q&A 内容生产 skill
- 广告与关键词运营辅助 skill
