# Previous White Rabbit Articles Archive

This upgrade adds a persistent corpus of previously published White Rabbit Report articles.

## What happens before every article run

1. The program checks the configured White Rabbit Substack publication.
2. It discovers post URLs from the publication sitemap, RSS feed, and archive page.
3. New/changed posts are downloaded as clean Markdown.
4. Hyperlinks and metadata are extracted and stored alongside each article.
5. A global SQLite registry is updated at `knowledge/white_rabbit.db`.
6. The most relevant prior White Rabbit articles are retrieved before Gemini creates its research plan.
7. Published prior articles are supplied as **Level 1 project canon and voice canon**.
8. Their established premises may be used without re-verification. Their source trails
   should be reopened when a canon exception applies or when they can expand the new
   investigation; genuine contradictions are preserved for author review.

## Folder layout

```text
research_library/
  previous_white_rabbit_articles/
    articles/
      YYYY/
        article-slug/
          article.md
          metadata.json
          links.json
    imports/
      substack_exports/
    sync/
      sync_report.json
  projects/
    <project_id>/
      sources/
knowledge/
  white_rabbit.db
  archive_search_index_v3.joblib   # local, rebuild with `archive reindex`
```

## Commands

```powershell
python -m white_rabbit archive sync
python -m white_rabbit archive sync --refresh   # re-fetch older posts to detect edits
python -m white_rabbit archive status
python -m white_rabbit archive reindex          # rebuild the local search index
python -m white_rabbit archive search "query"
python -m white_rabbit archive voice "investigative intelligence contractor"
python -m white_rabbit archive probe             # real-network discovery smoke test
python -m white_rabbit archive verify
python -m white_rabbit run "TOPIC" --project project_id
```

The `run` command performs an incremental archive sync automatically unless `--no-archive-sync` is supplied. Incremental sync discovers the publication but downloads only article URLs not already stored locally. Use `archive sync --refresh` when you want to re-fetch older posts and detect edits.

Search indexes are generated on the machine and should not be committed. After a fresh clone:

```powershell
python -m white_rabbit archive reindex
```

`archive search` is the published-factual-canon path. It returns ranked article passages,
canonical URLs, precise sections, access status, and source trails while preserving the
writer's original testimony/inference/question status. `archive voice` is a separate
full-body authored-prose path. It excludes Markdown blockquotes, copied quotations,
related-post cards, subscription/paywall UI, and every partial-preview article. Both
packets are generated and embedded in every Codex-first prompt; the legacy pipeline writes
`previous_white_rabbit_canon.md` and `previous_white_rabbit_voice.md` separately and sends
their combined, clearly labeled packet to planning, outlining, writing, audit, and revision.

`archive verify` writes these evidence artifacts in the archive root:

- `PUBLISHED_ARTICLE_INVENTORY.csv`
- `ARCHIVE_COVERAGE_REPORT.md`
- `CANON_RETRIEVAL_SMOKE_TEST.md`
- `VOICE_RETRIEVAL_SMOKE_TEST.md`
- `DRY_RUN_CODEX_ASSIGNMENT.md`

The inventory uses `FULL_PUBLIC`, `FULL_AUTHOR_EXPORT`, `PARTIAL_PREVIEW`, `TITLE_ONLY`,
and `FETCH_FAILED`. It includes publication/update timestamps, discovery provenance, HTTP
status, word and authored-paragraph counts, content hash, archive path, indexing state,
failure reason, duplicate hash, and missing-from-latest-discovery review state. Missing
URLs are never silently deleted.

## Paid/subscriber-only posts

Anonymous web retrieval can expose only a preview for some paid posts. The synchronizer detects common paywall signals and records `content_status: preview_only` instead of silently treating a preview as the full article. The `imports/substack_exports/` directory accepts an official owner export so full paid-post text can be seeded without storing browser session cookies.

To fill those gaps, request a Substack owner export and keep the ZIP outside the
repository (preferred), then run:

```powershell
python -m white_rabbit archive import-export "PATH_TO_EXPORT.zip"
python -m white_rabbit archive reindex --force
python -m white_rabbit archive verify
```

The importer reads `posts.csv` plus only the matching HTML for rows whose
`is_published` flag is true. It does not read or copy subscriber lists, email addresses,
payments, pledges, open/delivery analytics, or other account files. Drafts remain
excluded. Imported full bodies are labeled `FULL_AUTHOR_EXPORT` and retain their export
post ID, publication status, audience, subtitle, dates, links, images, headings, quotes,
captions, and source entry. The ZIP may remain outside the repository; extracted exports
under `imports/substack_exports/` are ignored as a privacy backstop.

Source precedence is `author export > verified local author copy > full public capture >
public preview > metadata shell`. Once a published body is labeled `FULL_AUTHOR_EXPORT`,
a later public refresh records its observation in metadata but cannot overwrite the
author-export body with a preview or divergent public rendering.
