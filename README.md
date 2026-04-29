# shcsca-skills

> 一个面向**跨境电商运营 / AI 工作流 / 软件工程**的 Skills 合集仓库

精选来自社区的优质 Skills，遵循 [Agent Skills](https://agentskills.io) 开放标准，支持 Claude Code、Codex、OpenClaw、Cursor 等主流 AI 开发工具直接安装使用。

---

## 快速开始

### 安装方式一：让 AI 自动安装（推荐）

在你使用的 AI 工具中直接发送：

```
帮我安装 <skill-name>，来源仓库 shcsca-skills，直接装到当前工作区
```

### 安装方式二：手动安装

```bash
# 1. clone 本仓库
git clone https://github.com/SHCSCA/shcsca-skills.git
cd shcsca-skills

# 2. 复制单个 skill 到你的 skills 目录
cp -r skills/<skill-name> ~/.openclaw/skills/
```

### 安装方式三：通过包管理器

```bash
# ClawHub
clawhub install <skill-name>

# Tessl
tessl install shcsca-skills/<skill-name>
```

---

## Skills 速查表

### 🛒 亚马逊运营

| Skill | 一句话说明 |
|-------|-----------|
| `zach-feature-demand-validator` | 用 Review / 关键词 / 社区三维证据验证功能点是不是真需求 |
| `neat-freak` | 任务完成后自动同步文档、CLAUDE.md、Agent 记忆，防止 AI 脑腐 |
| `hv-analysis` | 横纵分析法——输出万字级别竞品/公司/概念全景调研报告 |
| `khazix-writer` | 模拟作者口吻写长文，拒绝"赋能、抓手、闭环"等空洞词汇 |

### 💻 工程开发（mattpocock）

| Skill | 一句话说明 |
|-------|-----------|
| `grill-me` | 上线前灵魂拷问，彻底理清需求再开工 |
| `grill-with-docs` | 需求拷问 + 建立团队共享语言 + 更新 CONTEXT.md 和 ADR |
| `diagnose` | 系统性调试循环：复现→最小化→假设→验证→修复→回归 |
| `tdd` | 红绿重构测试驱动开发，垂直切片构建功能 |
| `improve-codebase-architecture` | 发现代码架构深化机会，防止代码腐烂 |
| `to-prd` | 将对话上下文合成 PRD 并提交为 GitHub Issue |
| `to-issues` | 将 PRD 分解为可独立领取的垂直切片 GitHub Issue |
| `triage` | Issue 分诊状态机 |
| `zoom-out` | 让 Agent 从系统整体视角解释代码 |
| `setup-matt-pocock-skills` | 每个项目初始化 Issue Tracker / 标签 / 文档结构 |

### ⚡ 生产力工具（mattpocock）

| Skill | 一句话说明 |
|-------|-----------|
| `caveman` | 压缩沟通语言，节省约 75% token |
| `write-a-skill` | 创建新 Skill 的模板与规范 |

### 🔧 工具类（mattpocock）

| Skill | 一句话说明 |
|-------|-----------|
| `git-guardrails-claude-code` | 拦截危险 git 命令（push / reset --hard / clean） |
| `setup-pre-commit` | 配置 Husky + lint-staged + Prettier + 类型检查 + 测试 |
| `scaffold-exercises` | 创建练习目录结构（题目/解答/解析） |
| `migrate-to-shoehorn` | 迁移类型断言到 @total-typescript/shoehorn |

### 🔖 其他

| Skill | 来源 | 一句话说明 |
|-------|------|-----------|
| `edit-article` | mattpocock/personal | 辅助文章编辑 |
| `obsidian-vault` | mattpocock/personal | Obsidian 知识库管理 |
| `design-an-interface` | mattpocock/deprecated | 界面设计（已废弃） |
| `qa` | mattpocock/deprecated | Q&A 流程（已废弃） |
| `request-refactor-plan` | mattpocock/deprecated | 重构计划（已废弃） |
| `ubiquitous-language` | mattpocock/deprecated | 共享语言（已废弃） |

---

## 核心 Skill 详解

### zach-feature-demand-validator

> 解决"这个功能点，到底是不是用户真的在意"

从三个维度交叉验证：
- **Review 信号**：用户有没有提到、抱怨缺失
- **关键词信号**：用户有没有主动搜索这个功能
- **社区信号**：Reddit / Quora 等社区是否反复讨论

```
/zach-feature-demand-validator 帮我验证一下 air fryer 的 steam 功能在美国站是不是真需求
```

### neat-freak（khazix）

每次任务完成后自动同步三层：

1. **项目文档**（CLAUDE.md / AGENTS.md / docs/）— 给 AI 和同事看
2. **Agent 记忆**（跨会话的自己）— 防止 AI 用过期信息
3. **项目 README** — 给团队其他成员看

触发方式：`/neat` 或 `整理一下` 或 `同步一下`

```
每次在 Agent 里干完一件事，跑一下 /neat，它会把你这次改的东西全部对齐。
```

### hv-analysis（khazix）

同时跑两条线：
- **纵向**：从诞生到当下，完整演变
- **横向**：同期所有主要竞品逐一对比

最后两条线交叉，输出 10,000–30,000 字的排版精美 PDF 研究报告。

适合：竞品调研、公司研究、概念入门、写作素材准备。

### khazix-writer（khazix）

有立场的写作 skill。拒绝空洞词汇（赋能、抓手、闭环、首先...其次...）。

四层自检体系：结构 / 节奏 / 内容 / 文字。

适合：写公众号长文、品牌内容、正式文档。

### mattpocock 工程系列

**grill-me / grill-with-docs**：最受欢迎的两个 skill。每次想做任何变更前，跑一遍灵魂拷问，Agent 会追问到每个决策分支都清晰为止。

**tdd**：红绿重构循环，测试先行。帮助 Agent 保持一致的反馈水平，产出质量更高的代码。

**improve-codebase-architecture**：建议每隔几天跑一次，防止 AI 加速开发导致的软件熵增。

**diagnose**：封装了最佳调试实践的循环：复现 → 最小化 → 假设 → 验证 → 修复 → 回归测试。

### caveman

压缩沟通模式，保留完整技术准确度的同时减少约 75% token 使用量。

适合高频对话、上下文紧张的场景。

---

## 仓库结构

```
shcsca-skills/
├── README.md
└── skills/
    ├── zach-feature-demand-validator/   # 需求验证
    ├── neat-freak/                      # 任务收尾同步
    ├── hv-analysis/                     # 横纵分析法
    ├── khazix-writer/                   # 写作风格
    ├── diagnose/                        # 调试循环
    ├── grill-with-docs/                 # 需求拷问 + 文档
    ├── triage/                          # Issue 分诊
    ├── improve-codebase-architecture/   # 架构改善
    ├── setup-matt-pocock-skills/        # 项目初始化
    ├── tdd/                             # 测试驱动开发
    ├── to-issues/                       # PRD → Issue
    ├── to-prd/                          # 对话 → PRD
    ├── zoom-out/                        # 系统视角
    ├── caveman/                         # 压缩沟通
    ├── grill-me/                        # 需求拷问
    ├── write-a-skill/                   # Skill 编写
    ├── git-guardrails-claude-code/     # git 保护
    ├── migrate-to-shoehorn/            # 类型迁移
    ├── scaffold-exercises/             # 练习脚手架
    ├── setup-pre-commit/               # pre-commit 配置
    ├── edit-article/                   # 文章编辑
    ├── obsidian-vault/                 # Obsidian 管理
    ├── design-an-interface/            # (deprecated)
    ├── qa/                              # (deprecated)
    ├── request-refactor-plan/          # (deprecated)
    └── ubiquitous-language/            # (deprecated)
```

---

## 适合谁用

- 🛒 **亚马逊卖家 & 跨境电商运营** — 用 AI 做市场研究和产品开发
- 📝 **内容创作者** — 公众号、品牌文案、内容生产
- 🔍 **市场调研人员** — 竞品分析、公司/概念全景调研
- 💻 **软件工程团队** — TDD、代码质量、需求对齐
- 🤖 **AI Agent 用户** — 把业务方法论沉淀成可复用 Skill

---

## 致谢

本仓库精选了以下优质开源 Skills：

- **khazix-skills** — [KKKKhazix/khazix-skills](https://github.com/KKKKhazix/khazix-skills)  
  作者：数字生命卡兹克，公众号「数字生命卡兹克」

- **mattpocock/skills** — [mattpocock/skills](https://github.com/mattpocock/skills)  
  作者：Matt Pocock，TypeScript 专家

---

*持续更新中。欢迎提交 Issue 或 PR 推荐新的优质 Skills。*
