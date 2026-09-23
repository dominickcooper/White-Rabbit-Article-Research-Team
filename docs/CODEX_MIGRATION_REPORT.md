# Codex-first reconstruction report

## Scope

Reconstructed the standalone Codex layer from the supplied requirements on the current
Gemini-era checkout. This is a new implementation of those requirements, not recovery
of the uncommitted implementation from another computer. No real article, old private
research or multi-part series workflow was created.

## Files added

- AGENTS.md: short repository map and authority hierarchy.
- codex_article.py: required compatibility entry point.
- white_rabbit_codex_config.json: portable local paths, FAQ count and internal hosts.
- white_rabbit/codex_articles.py: new/status/prompt/validate/export implementation.
- templates/ARTICLE_BRIEF_TEMPLATE.md: article scope and research prompts.
- README_CODEX.md: setup, commands and source-folder workflow.
- docs/APP_ARCHITECTURE.md, docs/CODEX_WORKFLOW.md, docs/WHITE_RABBIT_STYLE.md,
  docs/RESEARCH_AND_EVIDENCE.md, docs/SOURCING_AND_LINKING.md,
  docs/SEO_AND_PUBLISHING.md: permanent Codex authorities.
- tests/test_codex_articles.py: 40 new test cases including parametrized cases.
- docs/CODEX_MIGRATION_REPORT.md: this report.

## Existing files changed

- README.md: additive link to the Codex workflow; legacy instructions retained.
- .gitignore: exclude private/generated article_projects contents by default.
- white_rabbit/archive_db.py: recover moved archive paths when reading records;
  preserve stored provenance and do not rewrite historical directory values.
- white_rabbit/archive_retrieval.py: include local file availability, resolved location,
  size and modification time in index freshness checks.

## Components reused and legacy functionality

The existing substack_source_linker publisher supplies normalize_url, markdown_to_docx,
markdown_to_html and wrap_html. It already handles styled text, quotes, lists, tables,
hyperlinks and image notes. Export receives already-linked Markdown without invoking
first-use link insertion. python-docx and markdown were already in requirements.txt.

Local readers remain available for PDF/DOCX/text/CSV/JSON/HTML and are referenced by
the assignment. The existing archive registry, sync, hybrid retrieval and reranking,
source/evidence pipeline, Gemini provider and CLI remain intact. No provider is loaded
by the new entry point. Legacy Gemini generation and provider reranking remain optional
separate functionality. No new command automatically syncs or uploads private sources.
docs/PREVIOUS_WHITE_RABBIT_ARCHIVE.md and config/white_rabbit_style.md were preserved.

## Archive compatibility and live verification

The actual registry contains 145 articles. Before recovery, 0 stored directories resolved;
all 145 resolve under the current repository with the new suffix-based recovery.
The recovery accepts the known research_library/previous_white_rabbit_articles suffix,
rejects traversal during rebasing, and prefers the present repository copy. It falls
back to existing original locations for custom layouts. No basename-only guessing.

`python -m white_rabbit archive search "Flock Safety" --limit 1 --links 1 --json`
completed successfully against the actual archive after rebuilding the local index.
The ignored index is rebuildable; no source prose or stored path values were migrated.

## Validation and publishing

Validation reports word count, image/subscribe/share markers, Markdown link count,
internal occurrences, unique internal articles, external links, FAQs and CSV rows.
It enforces six nonempty deliverables, article title, required sections/markers, five
FAQ headings, SEO field content, source CSV integrity and exact linked destinations.
Invalid/tracking URLs fail. Out-of-range article length and absent related archive
links warn for editorial review. Registry inspection for these metrics is read-only.

Export is blocked on mechanical failure. Synthetic fixtures verify DOCX relationships,
tables, markers and UTF-8 content, and HTML tables/quotes/emphasis/lists/hyperlinks.
The source article remains byte-for-byte unchanged. Image/CTA markers are retained
for placement in Substack; no publishing or actual image generation is performed.

## Regression results

79 tests passed: 39 existing and 40 added. No existing tests were removed or edited.
The full suite used the repository virtual environment. The sandbox's default Windows
temporary directory was inaccessible, so tests used a fresh workspace-local base:

```powershell
New-Item -ItemType Directory -Path article_projects -Force | Out-Null
$testRun = Join-Path (Get-Location) ('article_projects/.tests-' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp $testRun
```

The run emitted 74 upstream joblib/NumPy deprecation warnings about array shape
assignment. No test failed. Entry-point help also works from another working directory
with site packages disabled, verifying the basic manager imports no optional provider.
Git whitespace checks passed (Windows line-ending notices only).

## Technical debt and boundaries

- Mechanical PASS does not establish factual truth, URL availability, source adequacy,
  interesting prose, a strong conclusion or sufficient FAQ answers; these remain Codex
  and human editorial audit responsibilities.
- The existing DOCX renderer supports a practical Markdown subset. Reference links,
  raw HTML anchors and raw URL parentheses are rejected; use inline links and
  percent-encoded parentheses. Deeply nested layouts require manual review.
- Exports overwrite the two generated files and are not a transactional two-file bundle;
  a filesystem error during export may require rerunning it.
- Archive recovery handles the standard archive layout; arbitrary custom archive moves
  require configuration/data repair rather than guessing. Search still uses the existing
  domain-specific relevance gates. Dependency deprecation warnings remain upstream debt.
- Source discovery inventories files and tells Codex to inspect them; Python does not
  automatically OCR scans or perform research. No restoration of absent past projects
  or original uncommitted implementation is claimed.

## First article command

With the repository virtual environment activated:

```powershell
python .\codex_article.py new "YOUR ARTICLE TOPIC"
```
