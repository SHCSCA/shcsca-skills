# AGENTS.md

## Project Scope

This repository is a skills collection. Keep user-facing documentation aligned with the actual `skills/` directory and each skill's `SKILL.md`.

## Key Rules

- Use `rg` / `rg --files` for repository search.
- Do not treat `amz-market-depth-report`, `amz-lifecycle-strategy-report`, or `amz-demand-gap-report` as top-level skills. They are internal modules under `skills/amz-market-research-orchestrated/child_skills/`.
- `amz-market-research-orchestrated` is the only external trigger for the Amazon market research workflow.
- `amz-ad-architecture` is a top-level installable skill for Chinese Amazon advertising structures, cost-profit and CPC linkage, metric definitions, negative targeting, and seven-day optimization rules.
- `amz-create-image` is a top-level installable skill whose default designer handoff is a compact two-sheet workbook (`主图副图` and `A+需求`), including Premium A+ function and scene carousel planning when appropriate.
- The root README is for human users. Keep it concise and aligned with the actual installable skill directories.
- There is no root `docs/` directory currently. Sync project knowledge through `README.md`, this file, and skill-local `SKILL.md` / `references/`.
- Ignore untracked scratch or generated output directories unless the user explicitly asks to publish them.

- `cyber-motuo-content-pipeline` is a top-level installable orchestrator; its nine modules under `child_skills/` are internal workflow modules, not sibling top-level Skills.

## Validation

For `amz-market-research-orchestrated`, common checks are:

```bash
python -m unittest discover -s skills/amz-market-research-orchestrated/scripts -p "test_*.py" -v
npm run test:amz-browser
python skills/amz-market-research-orchestrated/scripts/validate_market_research_deliverables.py --dir reports/<report_dir>
python skills/amz-market-research-orchestrated/scripts/run_visual_parity_audit.py --dir reports/<report_dir>
python skills/amz-market-research-orchestrated/scripts/run_acceptance_proof.py --dir reports/<report_dir> --depth standard
python skills/amz-market-research-orchestrated/scripts/run_acceptance_proof.py --dir reports/<report_dir> --depth deep --reference-visual --download-root C:\Users\wz\Downloads\downloadpage
```

Acceptance semantics:

- Full acceptance requires `overall_pass=true`, `delivery_mode=full_acceptance`, and `full_acceptance_pass=true`.
- Real reports with insufficient data gates may be valid diagnostic deliveries only when `overall_pass=false`, `delivery_mode=diagnostic_delivery`, and `diagnostic_delivery_pass=true`; do not describe these as complete market conclusions.
- Visual audits may ignore remote image 400/403/404 resource failures, but JavaScript errors, page errors, missing required components, and layout overflow are still failures.

<!-- CODEX-OBSIDIAN-PROTOCOL:START -->
## Obsidian 项目记忆

- `project_id`: `shcsca-skills`
- 项目知识库入口：`C:\Users\wz\Documents\Obsidian Vault\20_Projects\shcsca-skills\项目主页.md`
- 默认不自动检索 Vault。只有用户明确要求查知识库、历史记录或过往决策时，才运行 `powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\Users\wz\Documents\Codex\obsidian-memory-system\scripts\get-context.ps1" -Project shcsca-skills`；普通任务不得自动运行。
- Vault 默认只读；只有用户明确要求整理或更新笔记时才允许写入。
- 本文件的 full acceptance / diagnostic delivery 边界优先；事实状态以当前 Git、代码、运行、测试和交付证据为准。Vault 是历史上下文和可重建投影，冲突时标记旧笔记可能过期。
- 自动更新只能替换一对 `CODEX-KB-CURATOR` marker 之间的内容；marker 缺失、重复、嵌套或失衡时停止并报告。
- 不得修改 marker 外的人工内容，不得写入密钥、令牌、Cookie、完整原始对话或未筛选工具输出。
- 项目链接必须使用包含 `project_id` 的限定路径，禁止生成跨项目歧义裸链接。
<!-- CODEX-OBSIDIAN-PROTOCOL:END -->
