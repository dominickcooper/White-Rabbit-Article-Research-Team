# Codex-First Migration Report

## Migration summary

The application's normal article path is now Codex-first. Local Python tooling creates an article workspace, exposes sources and institutional memory, validates Codex's six publication artifacts, and exports the already-linked final Markdown. This path does not instantiate a model provider, require an API key, or require a local model server.

## Old default flow

The former `python -m white_rabbit run` path used Gemini to plan research, conduct grounded web research, extract evidence, create an outline, draft an evidence-marked article, audit sources, and complete provider-assisted archive relevance decisions. It then used deterministic source mapping, link insertion, DOCX conversion, and HTML conversion.

That flow remains available as optional legacy compatibility functionality. It is no longer documented or exposed as the normal article workflow.

## New default flow

1. Create `article_projects/<slug>/` with `ARTICLE_BRIEF.md`, `CODEX_PROMPT.md`, `sources/`, `research/`, and `output/`.
2. Put private/author material in `sources/` and optionally edit the brief.
3. Open the generated prompt in Codex. It directs Codex to the root `AGENTS.md`, which is the authority gateway to the research, evidence, style, sourcing, SEO, and workflow specifications.
4. Codex inspects local sources, searches the preserved archive, performs web research when available, and writes the six contracted output files.
5. Run deterministic validation and correct failures.
6. Optionally export the already-linked final Markdown directly to DOCX and HTML.

Standalone commands:

```powershell
python .\codex_article.py new "ARTICLE TOPIC"
python .\codex_article.py status project-slug
python .\codex_article.py prompt project-slug
python .\codex_article.py validate project-slug
python .\codex_article.py export project-slug
```

Equivalent package commands use `python -m white_rabbit article ...`.

## Implementation changes

- Strengthened `codex_article.py` with relative/absolute archive-path resolution and verified archive article counting.
- Kept project creation idempotent: existing briefs and prompts are preserved unless `--force` is explicit.
- Added strict project-slug validation.
- Strengthened validation for required outputs, exact five-question FAQ count, CTA markers, malformed links, tracking parameters, CSV exact-phrase integrity, and CSV-to-inline-link agreement.
- Added direct DOCX/HTML export from `output/article.md`, avoiding a second linking pass.
- Added `python -m white_rabbit article new|status|prompt|validate|export` while keeping provider imports off that command path.
- Made archive indexing portable across repository moves by recovering from stale absolute `local_dir` values in the SQLite registry.
- Added deterministic Codex workflow tests.
- Reoriented `README.md` and expanded `README_CODEX.md` around the Codex-first workflow.

## Preserved data and deterministic utilities

No archive or research files were moved, rewritten, or deleted.

- Archive: `research_library/previous_white_rabbit_articles/`
- Article bodies verified during migration: **145** `article.md` files
- Matching archive metadata records: **145** `metadata.json` files
- Archive registry: `knowledge/white_rabbit.db`
- Preserved archive sync/downloader: `white_rabbit/archive_sync.py`
- Preserved local archive retrieval/search/indexing: `white_rabbit/archive_retrieval.py` and related archive modules
- Preserved local/private source readers: `white_rabbit/local_sources.py`
- Preserved evidence database: `white_rabbit/evidence_db.py`
- Preserved source mapping and URL handling: `white_rabbit/source_mapper.py` and `white_rabbit/web_fetch.py`
- Preserved source linker and Markdown-to-DOCX/HTML conversion: `white_rabbit/publishing/substack_source_linker.py`

The Codex exporter calls the proven conversion functions directly on final, already-linked Markdown so the legacy linker cannot double-link it.

## Legacy/optional provider functionality

The following remain intentionally because removing them would add migration risk and discard working optional behavior:

- `white_rabbit/gemini_provider.py`
- `white_rabbit/pipeline.py`
- `white_rabbit/archive_reranker.py`
- `python -m white_rabbit doctor`
- `python -m white_rabbit run ...`
- `python -m white_rabbit archive rerank ...`

These commands require Gemini configuration. Codex-first article commands do not invoke them.

## Validation and tests

The initial baseline command could not start because the available Python interpreters did not yet have `pytest` installed. After installing the repository's declared `requirements.txt`, the full suite passed:

```text
46 passed in 5.18s
```

The new tests cover slug generation, scaffolding, prompt authority, existing-project preservation, validator success, exact phrase failure, tracking-parameter failure, absolute archive discovery, package CLI integration, and recovery from stale absolute archive paths. A forced local reindex also completed with 145 articles and 2,051 chunks, followed by a successful archive search smoke test.

## Unresolved technical debt

- Structural validation cannot prove factual accuracy, source quality, quote fidelity, or whether an inference is justified; the required Codex adversarial evidence audit remains authoritative.
- Legacy provider modules and their dependency footprint remain installed for compatibility.
- The old linker has its own `Originals/` and `Completed/` folder-oriented CLI. The Codex-first exporter bypasses that interface, but the older interface remains for existing users.
- Archive content is currently concentrated under a `2026` directory regardless of original publication chronology; metadata remains the safer source for dates.
- The SQLite registry still stores historical absolute `local_dir` values. Indexing now resolves these portably at runtime, but a future archive maintenance command could rewrite them to repository-relative paths.
- Online archive sync and live provider behavior were not exercised during this migration because they are network/API-dependent; their deterministic test coverage was preserved and passed.
