# Codex continuation prompt

You are working on the White Rabbit Researcher Python project. Read README.md, config/white_rabbit_style.md, all source files, and tests before editing anything.

Goal: make the single-article MVP production-reliable before adding series support.

Requirements:
1. Preserve the user's existing `white_rabbit/publishing/substack_source_linker.py` behavior unless a test proves a bug.
2. Use the current `google-genai` Interactions API, not deprecated Gemini SDK patterns.
3. Keep model names configurable by environment variables.
4. Research must remain evidence-first: sources/evidence are stored before writing.
5. Never let the writer invent evidence IDs.
6. Validate exact quotations/excerpts against retrieved source text; unverified excerpts must not be treated as direct quotations.
7. Every hyperlink CSV phrase must appear exactly in final Markdown.
8. Use each public URL once by default; prefer primary sources over secondary reporting when both support the same fact.
9. Private/local sources with no public URL remain in the evidence database but do not enter the public hyperlink CSV.
10. Preserve intermediate artifacts so the user can audit how the article was produced.
11. Do not begin series planning, a GUI, or the cross-project knowledge graph until the current test suite passes and a live single-article run succeeds.

First task:
- audit the current implementation for Gemini Interactions API compatibility,
- fix any API-shape issues,
- strengthen exception handling/retries/rate-limit handling,
- run pytest,
- add tests for source citation extraction, exact anchor verification, duplicate URLs, missing public URLs, and unsupported evidence markers,
- update README only when behavior actually changes.

Return a concise build report with files changed, tests run, unresolved risks, and the exact PowerShell command for the first live single-article test.
