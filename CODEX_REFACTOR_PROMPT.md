# CODEX TASK — CONVERT WHITE RABBIT APP TO CODEX-FIRST ARTICLE WORKFLOW

You are working in this repository:

`C:\Users\Cody\White-Rabbit-Article-Research-Team`

The user has decided that, for now, this application should use **Codex itself as the research, reasoning, and article-writing engine**, rather than orchestrating Ollama, Gemini, OpenAI API, Claude, or other LLM APIs.

## Authority
Before making changes, read:

1. `AGENTS.md`
2. `docs/APP_ARCHITECTURE.md`
3. `docs/CODEX_WORKFLOW.md`
4. `docs/RESEARCH_AND_EVIDENCE.md`
5. `docs/WHITE_RABBIT_STYLE.md`
6. `docs/SOURCING_AND_LINKING.md`
7. `docs/SEO_AND_PUBLISHING.md`
8. `README_CODEX.md`
9. `codex_article.py`
10. `white_rabbit_codex_config.json`

Treat these files as the target product specification unless the current repository contains a conflict that requires a safer implementation. If so, preserve data and document the deviation.

## Objective
Refactor the existing application so the **normal article workflow is Codex-first**:

1. create an article project;
2. user drops relevant source files into the project's `sources/` folder;
3. project-specific Codex prompt is generated;
4. Codex researches local sources;
5. Codex searches previous White Rabbit articles for institutional memory and internal links;
6. Codex conducts additional online research when network access is available;
7. Codex creates the research dossier;
8. Codex creates the outline and SEO package;
9. Codex writes the sourced publication-ready article;
10. Codex inserts image, subscribe, and share markers;
11. Codex audits and corrects the article;
12. deterministic local tooling validates and optionally exports the finished work.

## First: audit the current repository
Do not blindly replace the existing app.

Inspect the entire repository and identify:
- current CLI entry points;
- current Gemini/Ollama/OpenAI/provider abstractions;
- previous White Rabbit archive and its exact location;
- archive sync/downloader logic;
- archive search/retrieval logic;
- local/private source handling;
- evidence/database code;
- source-linking/hyperlinking logic;
- Markdown → DOCX/HTML export code;
- existing tests;
- generated/output directories;
- configuration/environment assumptions.

Run the existing tests before major changes if feasible and record the baseline.

## Preserve useful deterministic features
Preserve working capabilities that remain useful in a Codex-first system, especially:
- the previous White Rabbit article archive;
- Substack archive/sync utilities;
- local archive search;
- local source organization;
- URL cleanup/normalization;
- source CSV/link audits;
- Markdown hyperlink helpers;
- DOCX/HTML publishing/export tooling;
- relevant deterministic tests.

Do not delete or overwrite existing research/archive data.

If the archive does not currently live at the configured path in `white_rabbit_codex_config.json`, locate it and either safely configure the new workflow to use the existing location or migrate/copy it without data loss. Verify the article count before and after any migration.

## Deprioritize provider orchestration
The default article path must not require API keys or local model servers.

Do not require Gemini, OpenAI API, Ollama, Claude, or another provider to:
- judge archive relevance;
- research sources;
- extract evidence;
- create outlines;
- draft articles;
- produce SEO metadata.

If existing provider-specific modules are risky to remove, retain them as clearly labeled legacy/experimental functionality, but ensure they are not invoked by the normal Codex workflow.

Do not spend time perfecting legacy provider orchestration.

## Integrate the supplied Codex project helper
Treat `codex_article.py` as the minimum working specification for project scaffolding and validation.

You may improve it, but preserve these user-facing capabilities:

```powershell
python .\codex_article.py new "ARTICLE TOPIC"
python .\codex_article.py new "ARTICLE TOPIC" --slug project-slug
python .\codex_article.py status project-slug
python .\codex_article.py prompt project-slug
python .\codex_article.py validate project-slug
```

The `new` command must create:

```text
article_projects/<slug>/
├── ARTICLE_BRIEF.md
├── CODEX_PROMPT.md
├── sources/
├── research/
└── output/
```

The generated prompt must direct Codex to the repository authority files rather than duplicating all standards into every project.

If appropriate, add equivalent commands to the existing `python -m white_rabbit` CLI, but do not break the standalone helper.

## Ensure the article output contract
A completed project must contain:

```text
output/research_dossier.md
output/outline.md
output/seo.md
output/article.md
output/sources.csv
output/audit.md
```

The validator should check as much as can be checked deterministically, including:
- required outputs;
- article length;
- `[IMAGE: description | ALT: alt text]` markers;
- `[[SUBSCRIBE]]` markers;
- `[[SHARE]]` markers;
- five FAQs;
- `## YOU MAY BE INTERESTED IN THESE ARTICLES`;
- source CSV schema;
- exact CSV phrase presence in `article.md`;
- internal White Rabbit links;
- obvious tracking parameters and malformed links.

Do not pretend deterministic validation proves factual correctness. Codex's separate evidence audit remains required.

## Publishing/export integration
Inspect the existing publishing/linker code before changing it.

The target behavior is:

- `article.md` contains correct inline Markdown links already;
- `sources.csv` mirrors/audits the source relationships;
- existing DOCX/HTML conversion can consume the final Markdown where practical;
- existing linker logic must not double-link or corrupt already-linked Markdown;
- if necessary, adapt the exporter rather than forcing Codex to produce an inferior intermediate format.

## Tests
Add/update tests for the Codex-first deterministic workflow.

At minimum test:
- project scaffolding;
- slug generation;
- prompt generation;
- existing project preservation;
- validator success/failure cases;
- exact CSV phrase checking;
- tracking-parameter detection;
- archive path discovery/config behavior if modified;
- any integration added to the existing CLI.

Run the full relevant test suite before finishing.

## Documentation
Create/update:

`docs/CODEX_MIGRATION_REPORT.md`

Document:
- what the old default pipeline did;
- what the new default pipeline does;
- archive/data locations;
- which old modules remain but are legacy/optional;
- preserved publishing utilities;
- exact commands for starting and validating an article;
- test results;
- unresolved technical debt.

Update `README_CODEX.md` if implementation details change.

## Completion criteria
Do not stop at an architecture proposal. Modify the repository and leave the Codex-first workflow operational.

Before finishing:
1. run tests;
2. create a temporary sample article project using the helper/CLI;
3. verify its folders, brief, and generated Codex prompt;
4. run the validator against controlled fixture data or tests;
5. verify existing White Rabbit archive data was not lost;
6. inspect git diff/status;
7. summarize exactly what changed.

Do not begin writing a real White Rabbit article as part of this task. This task is to **convert and validate the application architecture** so the next task can be a real article investigation.

When complete, report:
- files changed/added;
- new normal workflow;
- exact command to create the first real article project;
- archive location and article count if determinable;
- tests run and results;
- any legacy provider code still present;
- unresolved issues or recommended next steps.
