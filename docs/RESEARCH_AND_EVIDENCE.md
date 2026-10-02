# Research and evidence

## Author-approved source corpus

Anything the author deliberately places in an article `sources/` folder, a series
`shared_sources/` folder, or another explicitly author-provided source location is
admissible evidence. Codex does not need to independently re-verify the source before
using facts, quotations, statistics, dates, testimony, relationships, or claims from it.
The corpus is evidence, not a pile of leads awaiting permission.

Admissibility is not equal weight. Preserve whether the item is contemporaneous primary
documentation, an official retrospective, a court/congressional/oversight record, named
firsthand testimony, scholarly or investigative secondary work, memoir, or disputed/
partisan secondary work. Preserve page, chapter, document ID, witness, and author. Never
rewrite “McCoy's interview with X described...” as “CIA records prove...” unless those
records actually do.

Independent corroboration is strongly encouraged and should expand the investigation, but
it is not a permission gate. If an underlying archival citation cannot be recovered,
record: supplied source says X; underlying citation is Y; Y was or was not recovered; and
additional corroboration was or was not found. Do not omit X merely because Y is missing.

## Internal evidence hierarchy

Use A — contemporaneous primary documentation; B — official retrospective or
investigative record; C — named firsthand participant/witness account; D — investigative
secondary reconstruction; E — secondhand, anonymous or unclear source; F — contradicted
or disproven. Add modifiers such as independently corroborated, partially corroborated,
uncorroborated, materially disputed, contradicted and chronology unresolved. Keep these
labels mainly in research artifacts, not publication prose.

Interviews, memoirs and investigative reporting are evidence. A named account does not
become “no evidence” because a declassified memo has not surfaced. Attribute it and give
it the weight its provenance, specificity, corroboration and conflicts deserve.

Attribution often supplies sufficient qualification. Do not reflexively append a
no-primary-source disclaimer after “According to...,” “told,” “recalled” or “described.”
Add an explicit caveat when uncertainty or contrary evidence materially changes meaning.

The evidence engine establishes what is supportable. The connection engine builds the
entity network, connection report and rabbit-hole queue, including a two-hop personnel
pass when sources permit. The story engine uses STORY_DECISION.md and STORY_SPINE.md to
decide discovery order. Never draft in ledger order merely because it is convenient.

Follow documented rabbit holes involving intelligence agencies, military organizations,
defense contractors, politicians, billionaires, venture capital, banks, foundations,
NGOs, universities, surveillance companies, Big Tech, military science, patents,
subcontractors, family ties, investors, board memberships, lawyers, donors, personnel
overlap and successor institutions. Proximity is a lead, not proof.

Classify findings as DIRECTLY DOCUMENTED, CORROBORATED STRONG INFERENCE,
HIGH-DIAGNOSTIC PATTERN, PLAUSIBLE CONNECTION, LEAD, SPECULATION, or CONTRADICTED.
The older shorthand DOCUMENTED FACT / STRONG INFERENCE remains readable in existing
projects. Preserve uncertainty without flattening unequal evidence.
Distinguish what is directly proven, what the total evidence most likely means, and
what remains genuinely unknown. When independent facts converge, state the strongest
reasonable conclusion. Do not manufacture 50/50 ambiguity when evidence is asymmetric.

Useful language includes “From what we can verify, the evidence points toward…”,
“The most likely explanation is…”, and “Taken together, these records strongly suggest…”.
Explain the evidentiary bridge. The absence of a signed order is relevant but is not
automatically exculpatory; it also does not license inventing an order.
For covert, compartmented, distributed, outsourced, or deniable systems, ask what
documentary footprint should exist rather than demanding one memorandum describing the
entire operation. Look for role division, personnel overlap, common recipients, funding
sequences, statutory workarounds, contractors, intelligence access, concealed sponsorship,
synchronized timing, common objectives, interagency coordination, successors, information
sharing, offshore entities, and functional migration. Evaluate the combination.

## Evidence convergence and stepping stones

An established fact or strong inference may become the premise for the next research
question. The investigation does not reset to zero after every connection. No single edge
must prove the entire chain, but every edge keeps its own classification and a weak or
broken edge must remain visible in `research/CONNECTION_CHAINS.md`.

Do not dismiss a theory by observing separately that A, B, and C each fail to prove X.
Ask what A + B + C show together. Independent streams increase evidentiary weight;
repetition derived from the same witness, document, dataset, or reporting chain must not
be double-counted. A strong inference is a valid article-level conclusion when the chain
and its meaningful boundary are shown.

## Books, bibliographies, and historical precedent

Author-supplied books, monographs, dissertations, memoirs, and investigative works are
usable evidence and major lead generators, not merely context. Preserve page/chapter and
attribution for consequential claims. Inspect footnotes and bibliographies, trace archival
references and document numbers where possible, add recovered records to the corpus, and
search them for people, programs, organizations, grants, contracts, and new connections.
Use `research/BOOK_LEADS.md` and `research/BIBLIOGRAPHY_TRACE.csv`. A controversial
interpretation is not grounds to reject an author-supplied work.

Ask whether the actor or system has used the alleged mechanism before. Document the prior
mechanism, identify its observable footprint, and search the present case for analogous
signatures. Historical precedent changes research strategy; it is not proof of recurrence
and must not be confused with direct continuity.

Before outlining, run a Rabbit-Hole Investigator pass: ask which documented connection
could materially change the reader's understanding, then check relevant biographies,
employment, intelligence or military service, funding, program ancestry, successor and
predecessor programs, testimony, oral histories, memoirs and declassified records. Do not
include a connection merely because it is colorful. Classify it before drafting.

Distinguish DIRECT RESPONSIBILITY (participation), COMMAND RESPONSIBILITY (supported
authority, knowledge and control), INSTITUTIONAL RESPONSIBILITY (organizational role),
PROBABLE RESPONSIBILITY (strongest supported attribution), and POSSIBLE RESPONSIBILITY
(credible but unresolved attribution). These analytical labels are not automatic legal
findings. Assign responsibility when supported; do not shield actors merely because
clandestine work leaves no explicit confession.

For consequential disputed questions: state the evidence, present the strongest
conventional/alternative explanation, test each against the total record, explain
what each accounts for and cannot account for, then make an evidence-weighted judgment.
Actively seek contrary evidence and distinguish independent sources from repetition
of a single source. Never treat an old White Rabbit article as independent proof.

If a foreign government knew about misconduct, investigate what it knew and when,
private beliefs, investigations, differences between public/private positions,
protests, minimization, compartmentalization and whether strategic priorities explain
inaction. Reserve “cover-up” for evidence of active concealment, while recognizing
that meaningful inaction can matter analytically.

## Research dossier

output/research_dossier.md preserves more detail than the article. For important
findings record finding, evidence, source, page/location/archive ID, evidence level,
confidence, responsibility where relevant, why it matters, natural question, strongest
competing explanation, unresolved gap and rabbit-hole connection. Keep precise local
file/book/scan/transcript provenance. Find stable public corroboration when possible;
do not replace a strong private source with a weak web page merely because it has a URL.
Report OCR/extraction gaps and missing records honestly.

## Adversarial and dossier-to-article audit

Compare the complete dossier against the draft before completion. Look for strong
findings lost in drafting, missing qualifications, unsupported prose claims, omitted
contrary evidence, over-compressed rabbit holes and causal chains collapsed from
A → B → C → D into unsupported A → D. Restore supported chains and revise judgments
when contrary evidence warrants it. Record resolved issues and remaining limitations
in audit.md. Mechanical PASS cannot substitute for this review.

After the main voice rewrite, independently compare prose and planned visuals against the
claims ledger, sources, quotations and chronology. Flag claim inflation, lost qualifiers,
altered quotations, institutional conflation, invented motive, chronology errors,
inaccurate captions and documentary crops whose visible language does not support their
placement. Do not flatten a documented fact while correcting an unsupported inference.
