# Four-Plane Market Research Architecture

This framework has four peer planes. They are not a strict hierarchy; each plane has its own contract and can evolve independently.

## 1. Data Source Plane

Skill: `data-source-orchestrator`

Responsibility:

- Convert data needs into provider calls.
- Select Sorftime, Apify, Keepa, Jimu, Reddit, YouTube, TikTok, web, user files.
- Run probes before full collection.
- Normalize data into Data Pack.
- Record lineage, quality, failures, and fallbacks.

Does not:

- Decide business strategy.
- Choose analysis methodology beyond data requirements.
- Format final reports.

## 2. Methodology Plane

Skill: `market-method-orchestrator`

Responsibility:

- Select methods based on purpose and available data.
- Compose atomic methods into analysis chains.
- Produce Analysis Plan and structured method outputs.
- Track method-level confidence and data gaps.

Examples:

- Review data -> topic clustering -> aspect sentiment -> JTBD -> Kano -> RICE.
- Category data -> TAM/SAM/SOM -> trend -> concentration -> Porter Five Forces.
- Competitor data -> 4P -> feature benchmark -> review gap -> ERRC.

Does not:

- Fetch raw platform data.
- Decide output destination.

## 3. Task Purpose Plane

Owner: `amz-market-research-orchestrated` plus `market-method-orchestrator` playbooks.

Responsibility:

- Clarify the user's real decision.
- Distinguish new category entry from product iteration, segment discovery, competitor differentiation, VOC, supply/profit validation, and executive reporting.
- Decide primary and secondary purpose.
- Translate purpose into data scope and method chain requirements.

Why it matters:

The same data sources can support very different decisions. Amazon + Reddit + YouTube for a new market entry needs market structure and wedge selection; the same data for product iteration needs complaint severity, Kano, and roadmap prioritization.

## 4. Output Plane

Skill: `research-output-orchestrator`

Responsibility:

- Confirm output format and target.
- Generate HTML, Markdown, JSON, PDF, or platform documents.
- Write to Feishu/Lark, Obsidian, Notion, or other knowledge platforms when configured.
- Preserve data lineage, quality score, and method chain appendix.
- Save output preferences when user confirms.

Does not:

- Change business conclusions.
- Hide limitations for nicer presentation.

## Orchestration Flow

```text
User request
  -> Purpose clarification
  -> Data scope confirmation
  -> Output confirmation
  -> OrchestrationBrief
  -> DataSource Plane returns Data Pack
  -> Methodology Plane returns Analysis Plan
  -> Research Skill synthesizes decision
  -> Output Plane delivers artifacts
```

## Expansion Rules

- Add a new platform by updating only the data source plane registry and field mapping.
- Add a new analysis method by updating only the methodology library and purpose playbooks.
- Add a new task purpose by adding a playbook and confirmation language.
- Add a new output platform by updating only the output registry and delivery contract.
