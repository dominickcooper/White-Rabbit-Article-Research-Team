# Integrity verification

Run: 2026-10-04, after research artifacts were completed.

## Frozen project

- Baseline manifest: `%TEMP%\zrrifle-before.sha256`
- Baseline entries: 87
- Current `article_projects/zrrifle/` files: 87
- SHA-256 differences: 0

## V2 source transfer

- Original source files: 13
- V2 source files: 13
- Missing or hash-different copies: 0

## Stage boundary

- V2 research artifacts: 23 after this report
- `article_projects/zrrifle-v2/article.md`: absent
- `article_projects/zrrifle-v2/output/article.html`: absent
- Export/publish actions: not run
- Commit/push actions: not run

## Test decision

The full software regression suite was not rerun for this content-only research package.
It had passed 263 tests immediately before this Stage 1 continuation, and no code or
methodology files were changed here. The article validator was intentionally not run
because the user prohibited creating the article and export artifacts it expects.

## Result

PASS for frozen-project and source-copy integrity. Research completeness and evidence
limits are separately recorded in `V2_RESEARCH_ACCEPTANCE.md`.
