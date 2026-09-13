# Codex-first standalone workflow

1. Run `python codex_article.py new "TOPIC"`. Existing projects are never overwritten;
   use a distinct topic/slug for a new workspace.
2. Edit ARTICLE_BRIEF.md and place original local source files in sources/ (subfolders
   are supported). Keep private provenance. Do not upload private files through the
   legacy provider unless you intend to use that separate workflow.
3. Run `python codex_article.py status <slug>` for inventory and file readiness.
4. Run `python codex_article.py prompt <slug>` and give the resulting assignment to
   Codex. Refreshing the prompt inventories current sources without editing the brief.
5. Codex reads permanent authority, brief, private sources and relevant archive records;
   performs additional research; writes dossier, outline, SEO, article and source map;
   adds FAQ and related links; audits evidence, revises and validates.
6. Final output contains research_dossier.md, outline.md, seo.md, article.md,
   sources.csv and audit.md. Working notes belong in research/.
7. Run `python codex_article.py validate <slug>`. A nonzero exit code and useful errors
   mean mechanical failure. Warnings cover editorial review and unusual length.
8. Run `python codex_article.py export <slug>`. Export requires mechanical PASS and
   creates article_substack.docx and article_substack.html. Re-export updates these
   generated files, leaving article.md and source material intact.

audit.md must separately address MECHANICAL CITATION VALIDITY, EDITORIAL SOURCE ADEQUACY,
DOSSIER-TO-ARTICLE AUDIT, SECTION-BY-SECTION SOURCE COVERAGE, PRIMARY-SOURCE ESCALATION,
competing explanations, evidence-weighted conclusions and unresolved limitations.
The tool cannot judge factual truth, citation sufficiency or rhetorical quality.

## Local archive after moving the repository

Legacy registry entries may retain old absolute directories. Search resolves the
known research_library/previous_white_rabbit_articles suffix under the current root,
preferring that local copy when available and otherwise retaining usable original paths.
It rejects traversal during recovery and does not rewrite the database.
Index cache freshness incorporates resolved file location/availability and modification
state, so an empty index made before recovery is rebuilt automatically.
Run `python -m white_rabbit archive reindex --force` for an explicit local rebuild.
Search/reindex need installed local dependencies but no provider key; sync uses network.
The legacy run command remains a separate, optional Gemini pipeline.
