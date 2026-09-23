# Multi-part White Rabbit investigations

A series is one investigation unfolding across publication-ready articles. Permanent
research, responsibility, style, sourcing, SEO and audit standards apply without weakening.
The series brief sets scope beneath those authorities. The manifest governs machine
metadata; the editable plan, dossier, timeline, entities and continuity govern research
memory. Resolve conflicts explicitly rather than silently changing earlier conclusions.

## New value and cumulative memory

Before drafting each installment answer: “What will the reader know after this article
that they did not know before it?” Put that answer in research_dossier.md and audit.md.
Each part must justify publication for a reader who read everything before it. New value
can be documents, operations, people, responsibility, financial or intelligence links,
contractors, archival findings, foreign-government involvement, scientific/technical
findings, competing explanations, consequences, successor institutions, modern relevance,
clarified chronology or documented causal chains. Recommend merging a weak installment
instead of padding it with summary.

Every part reads SERIES_BRIEF.md, SERIES_PLAN.md, SERIES_TIMELINE.md, SERIES_ENTITIES.md,
SERIES_CONTINUITY.md and shared_research/master_dossier.md before drafting. Inspect
relevant shared_sources and current sources without copying shared files into each part.
Consult prior completed articles and relevant dossiers/audits. Planned/drafting parts
are not reader knowledge. If earlier work is unfinished, record that dependency.

After research update the master dossier, timeline, entities, continuity and plan where
appropriate. Findings retain source/page/archive ID, evidence level, confidence,
responsibility, competing explanation, unresolved question, significance, connection
and first part established. Preserve each changed judgment as earlier judgment -> new
evidence -> revised judgment -> reason for revision. Never destroy cumulative memory.
The canonical timeline prevents date drift and unsupported causal compression. Entity
records preserve roles, dates, documents, connections and where people were introduced.

## Continuity and repetition

For every completed part, add a compact ## PART N reader-state entry to continuity:
findings, people introduced, institutions explained, dates/events, understood claims,
evidence-weighted conclusions, open questions, deferred rabbit holes and final transition.
Both plan and continuity track NEXT ARTICLE QUESTION, NEXT ARTICLE CONNECTION,
REVEALS SAFE TO TEASE and REVEALS TO WITHHOLD.

Later installments must not re-teach established material merely because it recurs.
Six paragraphs reintroducing an already-explained agency usually waste the reader's time.
Prefer a natural callback such as “As we established in Part 1…” followed immediately
by what matters now. Use one sentence or a short paragraph, and several paragraphs only
when comprehension requires them. Preserve context for readers who enter midstream.
Do not copy earlier prose or force identical callback phrasing.

Before finalizing Part 2+, compare ALL prior finalized article.md files for repeated
background, people/agency explanations, quotations, anecdotes, conclusions, introductions,
document descriptions and rhetorical framing. Check contradictions, chronology,
evidence-rating and responsibility-rating conflicts. Summarize and link backward when
necessary instead of reproducing an earlier article.

The lightweight validator compares normalized exact paragraphs of at least 40 words
against earlier complete/published parts. It normalizes Unicode, case, whitespace and
simple emphasis/links. Headings, marker/table blocks and trailing FAQ/related sections
are excluded. Repeated paragraphs warn; 300 or more matching words against one earlier
part fail. It does not perform semantic similarity or judge necessary quotation/recap.
Review flagged material editorially and replace excessive verbatim blocks with a concise
sourced summary. Missing completed articles fail because comparison cannot be performed.

## Non-final endings

End the investigative narrative before FAQ/related sections with:
this article's mystery -> answer/partial answer -> new document or connection -> larger
unresolved question -> next article. The next investigation must emerge from evidence
developed here. Do not write “Stay tuned for Part 2.” Tease a person, institution,
document, country, operation, contradiction or connection; preserve the strongest reveals.
If no next title exists yet, record an evidence-led question without inventing findings.

## Finale

The finale must not tease another installment. Move from the last specific mystery to
what the series documented, the pattern across parts, what survived/changed, how it
relates to the present and a provocative evidence-based final implication. Avoid generic
“lessons of history” recaps. Examine surviving institutions, successor agencies/programs,
contractors, surveillance systems, doctrine, funding, intelligence relationships, legal
authorities, personnel networks, organizational culture and policy where evidence permits.

Distinguish DOCUMENTED CONTINUITY, INSTITUTIONAL DESCENT, PERSONNEL CONTINUITY,
POLICY / DOCTRINAL CONTINUITY, FUNCTIONAL SIMILARITY, HISTORICAL ANALOGY and SPECULATION.
Resemblance alone is not continuity. The final implication must follow the record, not
manufacture a historical link to the present. Rhetorical quality remains editorial.

## Part dossier and audit

Recommended ## sections in each part research_dossier.md are WHAT THIS PART ADDS, EARLIER
FINDINGS REQUIRED FOR CONTEXT, NEW FINDINGS, NEW SOURCES, NEW PEOPLE / ORGANIZATIONS,
EVIDENCE-WEIGHTED CONCLUSIONS, RESPONSIBILITY ASSESSMENT, CONTRARY EVIDENCE, COMPETING
EXPLANATIONS, CONNECTIONS TO MASTER DOSSIER, QUESTIONS RESOLVED, QUESTIONS CARRIED FORWARD,
and MATERIAL RESERVED FOR NEXT PART. Explain not-applicable fields instead of leaving blanks.
Formatting may vary if all concepts are covered. Missing standard dossier headings warn
for editorial review; the validator does not attempt to infer conceptual coverage.

In addition to the permanent standalone audits, include:

- ## SERIES CONTINUITY AUDIT: repetition, missing recap, contradictions, chronology,
  evidence/responsibility ratings, repeated quotes/anecdotes/document explanations,
  and dossier/timeline/entity/continuity updates.
- ## NEW VALUE AUDIT: what this reveals that prior parts did not; whether it still
  justifies publication for an informed reader; merge/restructure if it does not.
- ## TRANSITION AUDIT: for non-final parts, test the evidence-led next question and
  tease/spoiler boundary; for the finale, test synthesis, modern relevance, continuity
  versus analogy and whether the implication follows from evidence.

Audit understatement as well as overstatement. Preserve fact -> question -> judgment ->
implication, causal chains, competing explanations, foreign-government response,
primary-source escalation, dossier-to-article comparison, and visible section-by-section
source coverage. Mechanical validation never establishes editorial source adequacy.

## Commands and lifecycle

```powershell
python .\codex_article.py series new "SERIES TITLE"
# Optional: series new "SERIES TITLE" --parts 3
python .\codex_article.py series add series-title "FIRST ARTICLE"
python .\codex_article.py series add series-title "SECOND ARTICLE" --finale
python .\codex_article.py series status series-title
python .\codex_article.py series prompt series-title part-01-first-article
python .\codex_article.py series validate series-title part-01-first-article
python .\codex_article.py series export series-title part-01-first-article
python .\codex_article.py series set-status series-title part-01-first-article complete
python .\codex_article.py series set-url series-title part-01-first-article "https://publication.example/p/first"
python .\codex_article.py series set-finale series-title part-02-second-article
```

New creates only blank memory templates, no Part 1. Add numbers parts deterministically
and appends a blank plan entry; it does not renumber prior parts. Unknown planned count
is null. A known count grows when additional parts require it. Setting a finale sets
planned count to the current count. Only the last part can be the finale. To extend
an investigation, run set-finale <series> <last-part> --clear, then add another part.

Part statuses are planned, drafting, complete and published. set-status complete requires
mechanical validation; use it after editorial review and memory updates. set-url records
actual publication and marks published without requiring local publication files (it can
record a URL after external publication). Earlier finalized files must still be present
for later validation. No command publishes online. Series status is derived on updates:
planned with no parts, active with parts, complete once all parts are complete/published
and the last is a finale. Published parts retain publication status during revisions.

The manifest tracks titles, slugs, numbers, statuses, finale, previous/next, publication
URLs and UTC timestamps. Edit planned_parts or titles carefully if needed; malformed
metadata, duplicate URLs, broken relationships and invalid paths are rejected. Refresh
the selected prompt after manual edits. Metadata commands refresh all generated part
prompts so URLs and relationships are current; they never rewrite article prose/briefs.
Generated prompts embed current plan/continuity snapshots and instruct re-reading them.

Published URLs appear automatically in later assignments. Link the first useful callback
without spamming. Validation reports series_internal_links, unique_series_articles and
white_rabbit_archive_links separately; total internal metrics include both categories.
A series URL takes precedence over archive membership, preventing double-counting.

Series validation reuses standalone source/SEO/FAQ/marker checks, adding manifest/memory
consistency, series audit sections, dossier coverage warnings and duplication checks. Export runs this full
validation before using the same DOCX/HTML renderer. It creates the same two filenames
inside the selected part's output/. Image and CTA notes retain existing behavior.

## Files, safety and limitations

```text
series_projects/<series-slug>/
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
    output/  (six standard deliverables, then DOCX and HTML)
```

series_dir defaults to series_projects even in older configuration files. It must be
separate from standalone projects_dir. Series projects are ignored by Git by default.
Creation never overwrites an existing directory. Metadata updates use an exclusive
.series.lock and atomic per-file replacement. A process crash can leave a stale lock
or an incomplete multi-file update; inspect before removing the lock and reconcile the
manifest/plan/directory, then refresh prompts. This is not a database transaction.
No automatic semantic truth check, memory synthesis, OCR or LLM call is performed.
Codex must actually maintain the memory and editorial audits. Standalone projects,
legacy Gemini commands, archive retrieval and source content are not migrated.
