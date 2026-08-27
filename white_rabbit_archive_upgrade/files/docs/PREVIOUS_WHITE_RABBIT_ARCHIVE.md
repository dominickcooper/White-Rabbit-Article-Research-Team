# Previous White Rabbit Articles Archive

This upgrade adds a persistent corpus of previously published White Rabbit Report articles.

## What happens before every article run

1. The program checks the configured White Rabbit Substack publication.
2. It discovers post URLs from the publication sitemap, RSS feed, and archive page.
3. New/changed posts are downloaded as clean Markdown.
4. Hyperlinks and metadata are extracted and stored alongside each article.
5. A global SQLite registry is updated at `knowledge/white_rabbit.db`.
6. The most relevant prior White Rabbit articles are retrieved before Gemini creates its research plan.
7. Prior articles are supplied as **institutional memory / research leads**, not as proof.
8. Their published URLs may be used for internal links. Their prior external source links may be re-opened and independently verified.

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
```

## Commands

```powershell
python -m white_rabbit archive sync
python -m white_rabbit archive sync --refresh   # re-fetch older posts to detect edits
python -m white_rabbit archive status
python -m white_rabbit run "TOPIC" --project project_id
```

The `run` command performs an incremental archive sync automatically unless `--no-archive-sync` is supplied. Incremental sync discovers the publication but downloads only article URLs not already stored locally. Use `archive sync --refresh` when you want to re-fetch older posts and detect edits.

## Paid/subscriber-only posts

Anonymous web retrieval can expose only a preview for some paid posts. The synchronizer detects common paywall signals and records `content_status: preview_only` instead of silently treating a preview as the full article. The `imports/substack_exports/` directory is reserved for a later owner-export importer so full paid-post text can be seeded from an official Substack export without storing browser session cookies.
