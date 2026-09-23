# TARGET APP ARCHITECTURE — CODEX-FIRST WHITE RABBIT WORKFLOW

## Goal
For now, the White Rabbit application should **not** depend on Ollama, Gemini, OpenAI API, Claude, or another external model API to research or write articles.

The primary reasoning/research/writing engine is **Codex operating inside this repository**.

The application should prepare a disciplined workspace, preserve institutional memory, expose relevant source material, and validate/publish Codex's outputs.

## Core architecture

```text
TOPIC
  ↓
ARTICLE PROJECT SCAFFOLD
  ↓
AUTHOR DROPS SOURCES INTO sources/
  ↓
CODEX READS REPO AUTHORITY + SOURCE FILES
  ↓
CODEX SEARCHES PRIOR WHITE RABBIT ARCHIVE
  ↓
CODEX CONDUCTS ADDITIONAL ONLINE RESEARCH
  ↓
RESEARCH DOSSIER
  ↓
OUTLINE + SEO PACKAGE
  ↓
SOURCED ARTICLE + IMAGE/CTA MARKERS
  ↓
ADVERSARIAL AUDIT + CORRECTIONS
  ↓
LOCAL VALIDATION
  ↓
OPTIONAL DOCX/HTML/PUBLISHING EXPORT
```

## The Python application's responsibilities
The Python app should focus on deterministic/local tasks:

### 1. Project creation
Create predictable article workspaces:

`article_projects/<project_slug>/`

with:
- `ARTICLE_BRIEF.md`
- `CODEX_PROMPT.md`
- `sources/`
- `research/`
- `output/`

### 2. Archive management
Preserve and expose the existing local archive of previous White Rabbit articles.

Do not delete, overwrite, or discard the existing archive during migration.

If the repository already contains Substack sync/download logic that reliably maintains the archive, preserve it as a utility. It may remain callable independently from article generation.

The archive should be discoverable by Codex under a stable configured path, preferably:

`research_library/previous_white_rabbit_articles/`

If existing data lives elsewhere, either:
- update configuration to reference it; or
- migrate/copy it safely after verifying counts/hashes.

Never silently destroy the old archive.

### 3. Source organization
Provide stable locations for:
- project-specific author sources;
- shared reusable research sources;
- previous White Rabbit articles.

Do not require API ingestion merely to make local files usable by Codex.

### 4. Prompt generation
Generate a project-specific `CODEX_PROMPT.md` containing:
- topic
- project slug
- source path
- output path
- required workflow
- required final deliverables
- validation command

Permanent house rules should live in repository documentation, not be duplicated in full inside every project prompt.

### 5. Structural validation
Provide deterministic validation for:
- required output files
- article word count
- image marker syntax/count
- subscribe/share markers
- FAQ presence/count
- related-reading section
- source CSV header
- exact CSV phrase occurrence in article Markdown
- internal White Rabbit link count
- tracking parameters
- malformed obvious link patterns

Validation is not a substitute for Codex's evidence/fact audit.

### 6. Publishing/export helpers
Preserve useful deterministic publishing functionality already present in the repository, especially any proven Markdown → DOCX/HTML and source-linking utilities.

If an existing source-linker/hyperlinker is retained, it must not overwrite already-correct inline Markdown links produced by Codex.

Prefer using Codex's already-linked `article.md` as the source of truth, with CSV/linker tooling acting as audit/export support.

## What should NOT be on the default article path
The default article workflow should not require:
- `GEMINI_API_KEY`
- OpenAI API keys
- Ollama running locally
- provider selection
- LLM API orchestration
- Gemini archive reranking
- API-based evidence extraction
- API-based article drafting

Existing provider-specific code may remain under a clearly labeled `legacy`, `experimental`, or optional path if removing it would be risky. It should not execute during the normal Codex article workflow.

## Existing capabilities to preserve where useful
During migration, audit the repository before deleting or replacing anything.

Likely useful existing capabilities include:
- previous White Rabbit article archive
- Substack archive/sync utilities
- local archive search/retrieval
- project/private source folder conventions
- source/link normalization
- Markdown hyperlink tooling
- Markdown → DOCX/HTML conversion
- publishing/link reports
- tests covering deterministic utilities

Preserve working components rather than rewriting them without reason.

## Desired CLI/user experience
Codex should make the repository's normal workflow simple.

At minimum, support the root helper:

```powershell
python .\codex_article.py new "COINTELPRO"
python .\codex_article.py status cointelpro
python .\codex_article.py prompt cointelpro
python .\codex_article.py validate cointelpro
```

If the existing `python -m white_rabbit` CLI is healthy, Codex may also integrate equivalent commands, for example:

```powershell
python -m white_rabbit article new "COINTELPRO" --project cointelpro
python -m white_rabbit article status cointelpro
python -m white_rabbit article validate cointelpro
```

Do not break the root helper merely to add CLI integration.

## Project brief behavior
`ARTICLE_BRIEF.md` is author-editable.

Codex should treat it as project-specific direction subordinate only to the user's current prompt and higher-priority repository/system instructions.

It may contain:
- desired angle
- claims/leads to investigate
- people/agencies/companies to inspect
- must-use source files
- series context
- free/paid status
- author notes

A blank optional field should not cause Codex to stop.

## Final article contract
Codex must create:

`output/research_dossier.md`

`output/outline.md`

`output/seo.md`

`output/article.md`

`output/sources.csv`

`output/audit.md`

`article.md` is the publication source of truth.

## Final Markdown requirements
The finished article should include:
- reader-facing H1 title
- reader-facing description/deck
- White Rabbit H2/H3 structure
- inline source hyperlinks
- relevant internal White Rabbit hyperlinks
- `[IMAGE: description | ALT: alt text]`
- `[[SUBSCRIBE]]`
- `[[SHARE]]`
- exactly five FAQs unless explicitly overridden
- `## YOU MAY BE INTERESTED IN THESE ARTICLES`

## Migration safety
Before changing the existing app:
1. inventory current files/modules/features;
2. identify archive/data directories;
3. identify current tests;
4. identify publishing/linker utilities worth preserving;
5. run baseline tests if possible;
6. make incremental changes;
7. run tests after changes;
8. verify archive/data counts were not reduced;
9. leave a migration report explaining what changed and what remains legacy/optional.

## Required migration report
For the initial Codex-first refactor, create:

`docs/CODEX_MIGRATION_REPORT.md`

It should document:
- old default flow
- new default flow
- files/modules added
- modules preserved
- provider-specific paths disabled/deprioritized
- archive location and verified article count if determinable
- how to create an article project
- how to validate a completed article
- any unresolved technical debt
