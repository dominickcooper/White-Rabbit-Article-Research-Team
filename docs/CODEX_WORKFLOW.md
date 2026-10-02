# Codex-first standalone workflow

## Connection-first editorial workflow

The ordinary sequence is SOURCES → EVIDENCE ENGINE → CONNECTION ENGINE → STORY ENGINE →
ARTICLE → FACTUAL AUDIT → EDITORIAL/VOICE AUDIT → REVISION → VALIDATION →
POST-PUBLICATION LEARNING.

For covert, deniable, compartmented, conspiratorial, outsourced, or comparably
circumstantial theories, activate the permanent Extreme-Thesis Protocol. Its research
order is EXTREME THESIS → EVIDENCE BUILD → CONNECTION CHAINS → DISCONFIRMATION → ZEBRA
ADJUDICATION → THESIS REDUCTION → STORY DECISION. Zebra is an adjudication stage, not a
preemptive moderation stage. Ordinary projects remain valid and need not manufacture an
extreme thesis or Zebra analysis.

New projects receive STYLE_PROFILE.md, ENTITY_NETWORK.md, RABBIT_HOLE_QUEUE.md,
CONNECTION_REPORT.md, CONNECTION_CHAINS.md, BOOK_LEADS.md, BIBLIOGRAPHY_TRACE.csv,
STORY_DECISION.md, STORY_SPINE.md and editorial_audit.md. The claims
ledger establishes support; STORY_SPINE controls reader-facing reveal order. Do not draft
directly from the dossier or ledger. The connection pass follows significant people two
career/network hops when sources permit. STORY_DECISION lets the thesis mutate when the
research earns it. Editorial audit remains separate from factual audit and drives revision
before mechanical validation.

## Extreme-Thesis activation and artifacts

Read `research_library/methodologies/EXTREME_THESIS_PROTOCOL.md` and
`research_library/methodologies/ZEBRA_PROTOCOL.md`. Activate the protocol when the brief
requests it or the central theory materially depends on covert, deniable, compartmented,
conspiratorial, outsourced, or cumulative circumstantial conduct. State the strongest
logically coherent thesis before research and break it into testable propositions with
predicted observables. Do not soften it in anticipation of later review.

When active, create `research/EXTREME_THESIS_LEDGER.md`,
`research/ZEBRA_ANALYSIS.md`, and `research/THESIS_REDUCTION.md` from the repository
templates. Build the strongest case first, track evidence dependencies, seek contrary
evidence, adjudicate Horse/Zebra/Black Zebra/Hybrid/Unresolved, then reduce the thesis.
Horse can win; a theory can be contradicted; or the strongest surviving result can be a
corroborated strong inference. Story Decision uses the reduced thesis, not the safest
available wording.

CONNECTION_CHAINS.md permits a documented fact or strong inference to become the premise
for the next research question without promoting it into proof of the entire chain. Every
edge retains its classification and source dependency. Analyze what independent A + B + C
show together; do not double-count derivative repetition of one witness, record, dataset,
or reporting chain.

## Editorial memory and learning

`init-editorial-memory` creates only missing permanent memory. Approved Gold entries must
point to real files. Export preserves the first pre-human draft; `snapshot` can do so
explicitly. After human edits, `learn <slug> --review` performs Stage 1 only: it preserves
the final, creates a structured `editorial_diff.md`, generates `LEARNING_PROMPT.md`, and
marks the postmortem `AWAITING CODEX ANALYSIS`. It does not perform semantic analysis.

Before preparing ordinary editorial learning, the system runs a multi-signal article-
identity check using title, major headings, principal entities, topic keywords, source
families and substantial text overlap. It allows heavy revision and thesis mutation, but
blocks a pair that appears to contain different stories. A deliberately preserved scope
or story-replacement comparison must be explicitly marked `story_replacement`; its prompt
forbids treating whole-story deletions as rejected claims or reusable editorial preferences.
The identity result and comparison mode are recorded in metadata and the generated diff.

In Stage 2, give LEARNING_PROMPT.md to Codex. Codex reads the pair, diff, standards and
series memory where applicable, then replaces the placeholder with a substantive
editorial_postmortem.md and semantic candidate_learnings.json. Use `learning-status` to
distinguish preparation, analysis, human review, readiness and promotion. A human must
mark each reusable candidate `status: approved`; strings and merely present candidates
cannot be promoted. Article-specific candidates stay out of permanent global memory.
Only `promote-learnings <slug>` appends approved non-article-specific lessons to
EDITORIAL_LESSONS.md. VOICE_CANON.md and ANTI_PATTERNS.md remain deliberate manual edits.

Old projects remain usable. Prompt refresh adds absent new artifacts without overwrite;
validation warns rather than hard-fails on missing editorial artifacts. Mechanical rules
remain a separate gate and never pretend to numerically score good writing.

1. Run `python codex_article.py new "TOPIC"`. Existing projects are never overwritten;
   use a distinct topic/slug for a new workspace.
2. Edit ARTICLE_BRIEF.md and place original local source files in sources/ (subfolders
   are supported). Keep private provenance. Do not upload private files through the
   legacy provider unless you intend to use that separate workflow.
3. Run `python codex_article.py status <slug>` for inventory and file readiness.
4. Run `python codex_article.py prompt <slug>` and give the resulting assignment to
   Codex. Refreshing the prompt inventories current sources without editing the brief.
5. Codex reads permanent authority, brief, private sources and relevant archive records;
   treats author-approved source folders as admissible evidence while preserving weight;
   performs additional and rabbit-hole research; traces book footnotes and bibliographies;
   builds claims and connection-chain ledgers plus a visual plan;
   drafts; runs separate structure, voice, emphasis, visual, evidence-integrity and
   anti-AI review passes; reconciles source anchors after prose is stable; writes SEO,
   FAQ and related links; then audits, revises and validates.
6. Final output contains research_dossier.md, outline.md, seo.md, article.md,
   sources.csv and audit.md. Working notes belong in research/.
7. Run `python codex_article.py validate <slug>`. A nonzero exit code and useful errors
   mean mechanical failure. Warnings cover editorial review and unusual length.
8. Run `python codex_article.py export <slug>`. Export requires mechanical PASS and
   creates article_substack.docx and article_substack.html. Re-export updates these
   generated files, leaving article.md and source material intact.

audit.md must separately address DIRECT FACTUAL CLAIMS, ATTRIBUTED SOURCE CLAIMS,
INFERENTIAL CLAIMS, CONNECTION CHAINS, HISTORICAL ANALOGY, MECHANICAL CITATION VALIDITY,
EDITORIAL SOURCE ADEQUACY, DOSSIER-TO-ARTICLE AUDIT, SECTION-BY-SECTION SOURCE COVERAGE,
PRIMARY-SOURCE ESCALATION, competing explanations, evidence-weighted conclusions and
unresolved limitations. Do not downgrade a supported strong inference merely because a
single smoking-gun memorandum does not exist.
The tool cannot judge factual truth, citation sufficiency or rhetorical quality. Its
editorial diagnostics are advisory warnings and must not be optimized as numeric targets.

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

## Series investigations

For a master investigation split into installments, use the parallel `series` commands.
Read [SERIES_WORKFLOW.md](SERIES_WORKFLOW.md) for shared sources, cumulative memory,
published callbacks, incremental part management and finale rules. The standalone
commands above retain their syntax and behavior.
