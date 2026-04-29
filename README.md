# shcsca-skills

> 一个面向**跨境电商运营 / AI 工作流**的 Skills 合集仓库

精选优质 Skills，遵循 [Agent Skills](https://agentskills.io) 开放标准，支持 Claude Code、OpenClaw 等主流 AI 开发工具直接安装使用。

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

---

## Skills 速查

| Skill | 来源 | 一句话说明 |
|-------|------|-----------|
| `zach-feature-demand-validator` | 自建 | 用 Review / 关键词 / 社区三维证据验证功能点是不是真需求 |
| `neat-freak` | khazix | 任务完成后自动同步文档、CLAUDE.md、Agent 记忆，防止 AI 脑腐 |
| `hv-analysis` | khazix | 横纵分析法——输出万字级别竞品/公司/概念全景调研报告 |
| `khazix-writer` | khazix | 模拟作者口吻写长文，拒绝"赋能、抓手、闭环"等空洞词汇 |
| `mattpocock/*` | mattpocock | 工程开发系列 Skill（TDD、调试、需求拷问等） |

---

## 自建 & khazix Skills

### zach-feature-demand-validator（自建）

> 解决"这个功能点，到底是不是用户真的在意"

从三个维度交叉验证：
- **Review 信号**：用户有没有提到、抱怨缺失
- **关键词信号**：用户有没有主动搜索这个功能
- **社区信号**：Reddit / Quora 等社区是否反复讨论

```
/zach-feature-demand-validator 帮我验证一下 air fryer 的 steam 功能在美国站是不是真需求
```

适合用来判断：
- 某个微创新要不要立项
- 某个功能是卖点还是伪需求
- 用户是真的在抱怨，还是卖家自己想象出来的需求

---

### neat-freak（khazix）

> "每次任务做完要退出窗口的时候，如果不跑一遍 /neat，我就浑身难受，如坐针毡如芒刺背如鲠在喉。"

每次任务完成后自动同步三层：

1. **项目文档**（CLAUDE.md / AGENTS.md / docs/）— 给 AI 和同事看
2. **Agent 记忆**（跨会话的自己）— 防止 AI 用过期信息
3. **项目 README** — 给团队其他成员看

触发方式：`/neat` 或 `整理一下` 或 `同步一下` 或 `sync up`

🌐 跨平台支持：Claude Code · Codex · OpenCode · OpenClaw

---

### hv-analysis（khazix）

> "纵向追时间深度，横向追同期广度，最终交汇出判断。"

同时跑两条线：
- **纵向**：从诞生到当下，完整演变，像讲故事一样
- **横向**：同期所有主要竞品逐一对比

最后两条线交叉，输出 10,000–30,000 字的排版精美 PDF 研究报告。

适合：
- 调研竞品 / 调研一个新概念 / 调研一个公司
- 写作前期需要系统性的素材准备
- 对一个领域想从零搞懂

---

### khazix-writer（khazix）

> "有见识的普通人在认真聊一件打动他的事。"

模拟作者口吻写长文。**有立场**——拒绝空洞词汇：
- ❌ "赋能、抓手、闭环"
- ❌ "首先...其次...最后"
- ❌ "在当今 AI 快速发展的时代"
- ❌ "说白了 / 本质上 / 换句话说"

四层自检体系：结构 / 节奏 / 内容 / 文字。

适合：你看过数字生命卡兹克的文章，觉得风格还行，想让你的 AI 照着这个调子写东西。

---

## mattpocock Skills（工程开发系列）

> "Skills I use every day to do real engineering — not vibe coding."

来源：[mattpocock/skills](https://github.com/mattpocock/skills)，作者 Matt Pocock

### 工程类

| Skill | 一句话说明 |
|-------|-----------|
| `diagnose` | 系统性调试循环：复现→最小化→假设→验证→修复→回归 |
| `grill-with-docs` | 需求拷问 + 建立团队共享语言 + 更新 CONTEXT.md 和 ADR |
| `triage` | Issue 分诊状态机 |
| `improve-codebase-architecture` | 发现代码架构深化机会，防止代码腐烂 |
| `setup-matt-pocock-skills` | 每个项目初始化 Issue Tracker / 标签 / 文档结构 |
| `tdd` | 红绿重构测试驱动开发，垂直切片构建功能 |
| `to-issues` | 将 PRD 分解为可独立领取的垂直切片 GitHub Issue |
| `to-prd` | 将对话上下文合成 PRD 并提交为 GitHub Issue |
| `zoom-out` | 让 Agent 从系统整体视角解释代码 |

### 生产力类

| Skill | 一句话说明 |
|-------|-----------|
| `caveman` | 压缩沟通语言，节省约 75% token |
| `grill-me` | 上线前灵魂拷问，彻底理清需求再开工 |
| `write-a-skill` | 创建新 Skill 的模板与规范 |

### 工具类

| Skill | 一句话说明 |
|-------|-----------|
| `git-guardrails-claude-code` | 拦截危险 git 命令（push / reset --hard / clean） |
| `setup-pre-commit` | 配置 Husky + lint-staged + Prettier + 类型检查 + 测试 |
| `scaffold-exercises` | 创建练习目录结构（题目/解答/解析） |
| `migrate-to-shoehorn` | 迁移类型断言到 @total-typescript/shoehorn |

### 个人 & 已废弃

| Skill | 说明 |
|-------|------|
| `edit-article` | 辅助文章编辑 |
| `obsidian-vault` | Obsidian 知识库管理 |
| `design-an-interface` | (deprecated) |
| `qa` | (deprecated) |
| `request-refactor-plan` | (deprecated) |
| `ubiquitous-language` | (deprecated) |

---

## 仓库结构

```
shcsca-skills/
├── README.md
└── skills/
    ├── zach-feature-demand-validator/      # 自建 · 需求验证
    ├── neat-freak/                         # khazix · 任务收尾同步
    ├── hv-analysis/                        # khazix · 横纵分析法
    ├── khazix-writer/                      # khazix · 写作风格
    └── mattpocock/                         # mattpocock · 工程开发系列
        ├── engineering/                    # 工程类（9个）
        ├── productivity/                  # 生产力类（3个）
        ├── misc/                          # 工具类（4个）
        ├── personal/                      # 个人用
        └── deprecated/                    # 已废弃
```

---

## 适合谁用

- 🛒 **亚马逊卖家 & 跨境电商运营** — 用 AI 做市场研究和产品开发
- 📝 **内容创作者** — 公众号、品牌文案、内容生产
- 🔍 **市场调研人员** — 竞品分析、公司/概念全景调研
- 💻 **软件工程团队** — TDD、代码质量、需求对齐（mattpocock 系列）
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
