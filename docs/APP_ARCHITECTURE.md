# Application architecture

## Additive editorial layer

`white_rabbit/editorial_memory.py` owns durable voice memory, Gold selection,
non-destructive artifact initialization, revision snapshots, diff packets and approved
promotion. `codex_articles.py` keeps standalone CLI/validation/export ownership;
`codex_series.py` composes it with factual series memory and conceptual SERIES_THEMES.
The legacy `python -m white_rabbit` Gemini/archive application is unchanged.

Editorial diagnostics are warnings. `white_rabbit/investigative_workflow.py` supplies
deterministic state checks for Thesis Lock, dependency-aware convergence, rabbit-hole
completion, writer/auditor context boundaries and independent quality gates. It does not
decide historical truth or literary merit. Publication files, links, CSV mappings and exports
retain mechanical behavior. Factual confidence belongs to evidence artifacts; narrative
quality belongs to the story/editorial layer; neither substitutes for the other.

The Python Codex layer is a workspace manager, archive/research memory interface,
mechanical validator, advisory editorial diagnostic layer and publisher. Codex performs
research, reasoning and writing outside the Python process. No Codex command loads .env, instantiates a provider,
uploads a source or calls an LLM API. Research performed by Codex may use its own tools.

The Source Thesis researcher, Rabbit-Hole Investigator, showrunner, writer, Narrative Structure Editor, Author Voice Editor,
Emphasis and Formatting Editor, Visual Story Editor, Evidence Integrity Editor and
Anti-AI Style Red Team are distinct prompt-governed passes, not provider-backed Python
agents. Keeping them as passes preserves the local Codex-first architecture and avoids
redundant orchestration. `white_rabbit/editorial_diagnostics.py` supplies non-blocking
signals and located multi-paragraph rhetorical patterns for final review; it does not
assign a style score or factual verdict. The semantic editorial artifact remains a
prompt-governed judgment because regexes cannot adjudicate rhetoric.
Extreme-Thesis evidence building, connection chains, disconfirmation, Zebra adjudication,
and thesis reduction are likewise prompt-governed research stages. Their permanent
authorities live under `research_library/methodologies/`; templates make their provenance
and ordering auditable without pretending Python can adjudicate historical truth.
`SOURCE_AUTHORITY_AND_CANON.md` is the single authority for the three-level source
hierarchy, accepted testimony, cumulative inference, canon conflicts, and the rule that
corroboration should open new branches. Python exposes this contract in generated prompts
and diagnostics; it does not decide whether testimony is true or a contradiction is real.

`INVESTIGATION_TO_STORY_HANDOFF.md` is the context-boundary authority. The writer does not
automatically ingest the complete adversarial bureaucracy; the auditor does. Quality
gates report Technical, Research, Thesis, Narrative, Voice, Evidence and Human Approval
separately. Existing export remains a technical operation and never writes software
publication approval.

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
