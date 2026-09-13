# Application architecture

The Python Codex layer is a workspace manager, archive/research memory interface,
mechanical validator and publisher. Codex performs research, reasoning and writing
outside the Python process. No Codex command loads .env, instantiates a provider,
uploads a source or calls an LLM API. Research performed by Codex may use its own tools.

`codex_article.py` delegates to `white_rabbit/codex_articles.py`. Repository paths
resolve from the installed script, not the shell's current directory. Relative paths
in `white_rabbit_codex_config.json` must stay within the repository. Project slugs
cannot traverse directories. Creation fails if the destination already exists.

`article_projects/<slug>/` contains ARTICLE_BRIEF.md, CODEX_PROMPT.md, sources/,
research/ and output/. Sources remain original inputs; research holds working notes;
output holds the six final deliverables and two exports. New does not invent research
or prefill final deliverables. Prompt refresh overwrites only generated CODEX_PROMPT.md.

The existing local source readers support PDF, DOCX, Markdown, text, CSV, JSON and
HTML. Existing evidence handling, archive sync, BM25/semantic search, reranking,
URL normalization and provider functionality remain available. Archive registry
reads for validation are read-only. The existing publishing converter exports
already-linked Markdown directly; it does not insert a second set of source links.

Legacy `python -m white_rabbit run` still uses Gemini and its existing configuration.
Legacy archive commands remain unchanged. `white_rabbit/codex_series.py` adds parallel
series metadata, shared memory and context through `codex_article.py series ...`.
It reuses create_project, check_project, generate_prompt, validate, status and the
shared export_validated renderer. See [Series workflow](SERIES_WORKFLOW.md).
