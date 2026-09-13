# Series implementation report

Implemented against baseline f094107 (79 tests), preserving standalone and legacy
workflows. No real series, article, private research or historical archive prose was
created or changed. Synthetic test workspaces were used for verification.

## 1. Files created or changed

Added:
- white_rabbit/codex_series.py
- templates/SERIES_BRIEF_TEMPLATE.md
- templates/SERIES_PLAN_TEMPLATE.md
- templates/SERIES_PART_PLAN_TEMPLATE.md
- templates/SERIES_TIMELINE_TEMPLATE.md
- templates/SERIES_ENTITIES_TEMPLATE.md
- templates/SERIES_CONTINUITY_TEMPLATE.md
- templates/SERIES_MASTER_DOSSIER_TEMPLATE.md
- tests/test_codex_series.py
- docs/SERIES_WORKFLOW.md
- docs/SERIES_IMPLEMENTATION_REPORT.md

Updated:
- white_rabbit/codex_articles.py: reusable project scaffold/path guard/renderer,
  configurable assignment command target, series link metrics and series CLI routing.
- white_rabbit_codex_config.json: series_dir, with fallback for older config files.
- AGENTS.md: conditional series authority/map.
- README.md, README_CODEX.md, docs/CODEX_WORKFLOW.md, docs/APP_ARCHITECTURE.md:
  additive workflow documentation.
- .gitignore: private/generated series projects excluded by default.

## 2. Commands

```powershell
python .\codex_article.py series new "SERIES TITLE" [--parts N]
python .\codex_article.py series add <series> "ARTICLE TITLE" [--finale]
python .\codex_article.py series status <series>
python .\codex_article.py series prompt <series> <part>
python .\codex_article.py series validate <series> <part>
python .\codex_article.py series export <series> <part>
python .\codex_article.py series set-url <series> <part> "https://..."
python .\codex_article.py series set-finale <series> <part> [--clear]
python .\codex_article.py series set-status <series> <part> planned|drafting|complete|published
```

Bracketed flags above are optional notation, not literal shell arguments.

## 3. Directory structure

```text
series_projects/<series>/
  SERIES_MANIFEST.json
  SERIES_BRIEF.md
  SERIES_PLAN.md
  SERIES_TIMELINE.md
  SERIES_ENTITIES.md
  SERIES_CONTINUITY.md
  shared_sources/
  shared_research/master_dossier.md
  articles/part-01-<slug>/
    ARTICLE_BRIEF.md
    CODEX_PROMPT.md
    sources/
    research/
    output/
      research_dossier.md
      outline.md
      seo.md
      article.md
      sources.csv
      audit.md
      article_substack.docx
      article_substack.html
```

New creates blank series templates with no part. Add creates only a blank part scaffold;
the six final deliverables are authored later by Codex, not fabricated by Python.

## 4. Manifest behavior

Schema version 1 records series title/slug/status/planned count, UTC creation/update
timestamps, and ordered part metadata. Parts have number/title/slug/status/finale,
previous/next and optional published URL. Numbers increment deterministically; titles
may repeat without colliding because the part number is included. Known planned counts
can grow. Invalid sequence, paths, relationships, dates, statuses and URLs are rejected.
Only the last part may be finale. Extending a finale requires explicitly clearing it.

Metadata mutations lock the series, replace individual files atomically and refresh
generated prompts. Existing brief/prose/source content is preserved. Series status is
derived from the part lifecycle on updates. Completion is explicit, never inferred from
the mere presence of article.md; set-status complete first requires validation.

## 5–8. Continuity, repetition and shared research

Prompts require current series memory, shared/part sources and prior completed articles,
plus their dossiers/audits where useful. They embed current plan/continuity and prior
publication metadata and instruct re-reading live files if the snapshot is stale.
Unfinished parts are not presumed established reader knowledge.

Every part must explain its new value and recommend merging if it adds too little.
Reader-state summaries preserve established findings, introductions, conclusions,
questions and deferred rabbit holes. Normal recaps are a sentence/short paragraph,
with enough context for midstream readers. Teaser-safe and withheld discoveries are
explicitly tracked in both the plan and continuity templates.

Normalized exact paragraphs of at least 40 words are compared against earlier
complete/published articles. Duplication warns; 300 matching words against a single prior
part fail. Repeated copies count toward that total. Routine publishing boilerplate is
excluded. This is a small fingerprint check, not semantic plagiarism detection.

Codex is instructed to update master_dossier.md with verified findings, provenance,
evidence/responsibility classifications, competing explanations and first part established.
Judgment changes preserve the old assessment, new evidence, revised judgment and reason.
The timeline is canonical chronology; entity records retain relationships/documents and
introduction/discussion history. Python never invents or automatically synthesizes memory.

## 9–10. Endings

Non-final prompts require mystery -> partial answer -> new connection -> larger question
-> next investigation, without a generic “stay tuned” or premature strongest reveal.
An unknown next title does not prevent an evidence-led next question.

Finale prompts explicitly prohibit another-installment teaser. They require series
synthesis, what survived/changed, supported modern relevance and an earned provocative
implication. They distinguish documented continuity/descent/personnel/policy from
functional similarity, historical analogy and speculation. These instructions govern
the narrative ending before FAQ and related-article publishing sections.

## 11. Published links

set-url stores a clean HTTP(S) destination and marks actual publication, without requiring
local deliverables to record an external publication. Later prompts receive it immediately.
Known series destinations count as internal even before archive sync. Reporting separates
series_internal_links, unique_series_articles and white_rabbit_archive_links; series
membership wins over archive membership so links are not double-counted.

## 12–14. Validation, export and compatibility

The existing validator still handles required deliverables, metadata/SEO, five FAQs,
image/CTA markers, CSV integrity, exact anchors, URLs and tracking. Series wrappers add
manifest/memory/directory checks, required series audit sections, dossier-coverage warnings
and duplicate paragraphs. Dossier formatting may vary; conceptual completeness remains
editorial. Missing completed articles fail rather than silently skipping comparison.

Series export validates the entire series part first, then calls the same renderer as
standalone export. Output stays within the selected part. Already-linked article.md is
not relinked or rewritten. All five standalone commands retain their syntax and behavior.
Legacy provider, archive/retrieval, source readers and publisher implementation remain
unchanged; no new provider dependencies, API keys or calls are required.

## 15. Verification

The full regression suite uses the repository virtual environment and a fresh ignored
workspace-local pytest base directory because the sandbox cannot use the default Windows
temporary directory. Final result: **129 passed** (79 unchanged baseline cases and
50 new series cases), with 74 existing upstream joblib/NumPy deprecation warnings.

```powershell
$testRun = Join-Path (Get-Location) ('article_projects/.series-tests-' + [guid]::NewGuid().ToString('N'))
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider --basetemp $testRun
```

Tests cover creation/non-overwrite, numbering, relationships, metadata corruption,
finale extension, statuses, URL refresh, source/research discovery, context/ending prompts,
link metrics, export paths, validation failures, missing memory, duplication thresholds,
config containment, locking and preservation of user prose/briefs. Original tests were
not removed or changed. Series help also runs with site packages disabled from another
working directory. Git whitespace checks pass, with Windows line-ending notices only.

## 16. Technical debt

- Multi-file metadata/scaffold changes are not a database transaction. A crash may leave
  a stale lock or partial operation. Inspect/reconcile the manifest, plan and directories
  before clearing a stale lock, then regenerate prompts.
- Memory updates, necessary recap, novel value, citation adequacy, responsibility and
  provocative implications need editorial review. Mechanical PASS cannot establish truth.
- Paragraph fingerprints do not detect paraphrase or reliably match a paragraph split
  into multiple blocks. Thresholds are conservative editorial signals, not legal judgments.
- Generated prompts include full plan/continuity snapshots; keep those memory files compact.
- The existing exporter supports a practical Markdown subset and two generated exports
  are not a transactional pair. Existing joblib/NumPy deprecation warnings remain upstream.

## 17. First series

With the repository virtual environment activated:

```powershell
python .\codex_article.py series new "YOUR SERIES TITLE"
```

Or without activation:

```powershell
.\.venv\Scripts\python.exe .\codex_article.py series new "YOUR SERIES TITLE"
```
