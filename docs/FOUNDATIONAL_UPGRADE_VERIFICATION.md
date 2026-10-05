# Foundational investigative-workflow upgrade: verification report

Date: 2026-10-04  
Scope: Codex-first standalone and series workflow, plus compatible legacy-pipeline
handoffs.  
Frozen control: `article_projects/zrrifle/` was inspected read-only. No article,
research, source, export, or audit file in that project was revised.

## Executive result

The failed ZR/RIFLE v1 run exposed an architectural failure, not merely a bad paragraph:
the system let the Story Decision replace the source-selected investigation, handed the
writer the adjudication machinery, treated unpursued rabbit holes as sufficient, and
collapsed technical validity into a single PASS. The upgraded workflow now makes those
states explicit and independently reviewable.

The new controls are:

1. a locked Source Thesis created from the brief and supplied corpus before external
   research;
2. an author checkpoint for any fundamental change of investigation;
3. separate factual-canon and filtered voice retrieval;
4. dependency-aware network convergence and evidence-linked rabbit-hole dispositions;
5. a controlled Writer Packet, with the full research record reserved for independent
   audit and specific factual lookup;
6. targeted audit findings and surgical correction rather than auditor-led redrafting;
7. semantic rhetorical diagnostics with exact locations and local repairs;
8. separate A–G quality gates, where technical PASS never becomes publication approval;
9. explicit, manual role/model handoffs rather than claimed automatic routing.

## Root causes confirmed

### 1. No durable thesis lock

The old project had a Story Decision that said the original JFK-deployment thesis no
longer deserved control and selected the adjacent withholding story. There was no
pre-research `SOURCE_THESIS.md`, no explicit ALIGNED / REFINED / FUNDAMENTAL CHANGE
PROPOSED result, and no author-decision state. The move could therefore be described as
ordinary adjudication even though it changed the article.

### 2. Research completion was confused with issue enumeration

The v1 Rabbit-Hole Queue left the most consequential branches as `FOLLOW`, `INCLUDED as
unresolved`, or dependent on future recovery. QJWIN's Congo task, WIROGUE's tasking, the
Islamorada expenses, Roselli contact logs, and the “precautionary lifeline” were named,
but the workflow did not require searches, records read, discoveries, stopping reasons,
and a valid terminal disposition before drafting.

### 3. The writer inherited the auditor's frame

The draft's source discussion became a sequence of allegation, repeated proof-status
limits, explicit thesis failure, and redirection to “the cover-up we can actually prove.”
That is the shape of an audit memo, not a reader-led investigation. The old system did
not distinguish the writer's primary packet from the full ledger, Zebra analysis,
adversarial notes, and failed-claim bookkeeping.

### 4. Canon retrieval did not reliably create a new research edge

The v1 canon report accurately labeled its closest matches “structural,” but the article
used one callback defensively: it immediately said the earlier program was not a
continuation before extracting the new question. Canon was available, but the workflow
did not force premise → next-hop use or keep factual-canon and voice retrieval as
separate downstream products.

### 5. Lexical style checks could not see multi-paragraph drift

The v1 article had zero legacy AI-tic hits. The failure lived across several paragraphs:
the supplied thesis was introduced, qualified repeatedly, adjudicated as failed, and
replaced with a safer story. Phrase counting could not identify that structure.

### 6. One PASS concealed multiple unrun reviews

The old validator could truthfully report technical PASS while research completeness,
thesis fidelity, narrative quality, Gold-voice comparison, evidence integrity, and human
approval were not independently represented.

## Implemented architecture

### Thesis and authority

- `SOURCE_THESIS.md` records corpus coverage, principal thesis, competing subtheories,
  accepted testimony, entities, chains, predicted footprints, contradictions, external
  research objectives, version, and lock state.
- `STORY_DECISION.md` now records the Source Thesis version, thesis-fidelity outcome, and
  author-decision state.
- A fundamental change remains blocked until `Author thesis decision: APPROVED`; lexical
  comparison is only a review backstop and can never auto-approve a change.
- Editorial priority is distinct from evidence authority: explicit author objective →
  supplied-corpus thesis → published canon → new external research, while every claim
  retains its provenance and evidentiary weight.

### Research depth and network convergence

- Connection chains carry chronology and dependency groups.
- Shared nodes reached by multiple paths are surfaced for further investigation.
  Derivative reports sharing one source dependency are not counted as independent
  streams, and convergence never automatically establishes unified command.
- High-value rabbit holes require the searches made, identifiers, records actually read,
  discoveries/connections, stopping reason, and one of DEVELOPED, CONTRADICTED,
  EXHAUSTED, DEFERRED, or BLOCKED. One failed search cannot be EXHAUSTED.

### Story handoff

- The showrunner works from the full research and produces the Story Spine and Writer
  Packet.
- The writer's primary context is Source Thesis, Writer Packet, Story Spine, Style
  Profile, selected documentary excerpts/locators, Gold behavior, the brief, and
  publication constraints.
- The dossier, claims ledger, Extreme-Thesis ledger, Zebra adjudication, thesis reduction,
  adversarial audit, and exploratory notes are lookup-only for the writer. The independent
  auditor receives the complete record.
- Audit findings specify exact passage, problem, evidence, required constraint, and
  minimum correction. Revision is surgical and is rechecked.

### Voice and semantic review

- Style profiles require full-body comparison against at least three relevant approved
  Gold articles and an actual final-draft comparison.
- Semantic review covers defensive sequence, contrived dialectic, auditor voice,
  premature adjudication, narrative stagnation, narrator absence, mechanical reveal
  writing, canon defensiveness, and thesis substitution.
- Deterministic diagnostics provide locator, excerpt, reason, and local repair. They are
  review leads, not automatic literary verdicts.

### Independent gates

| Gate | Meaning | Software behavior |
| --- | --- | --- |
| A | Technical validity | Computed by validator |
| B | Research completeness | Must be separately recorded |
| C | Thesis fidelity | Recomputed against Source Thesis; drift overrides a claimed PASS |
| D | Narrative quality | Must be separately recorded |
| E | Author voice / Gold comparison | Must be separately recorded |
| F | Evidence integrity | Must be separately recorded |
| G | Human editorial approval | Always `AUTHOR APPROVAL REQUIRED` in software |

Missing reviews are `NOT RUN`, not PASS. The legacy `result` field remains the technical
result for compatibility; `technical_result`, `quality_gates`, `thesis_fidelity`, and
`publication_status` expose the distinction.

## Frozen ZR/RIFLE v1 dry run

This is a representative handoff proof built by reading the frozen project. It is not a
replacement draft and was not written back into that project.

### Representative locked Source Thesis

The author-supplied books and testimony select an investigation into whether the
documented ZR/RIFLE capability, personnel, criminal recruitment, Castro operational
channel, Congo activity, and named anti-Castro network connect to a Dallas deployment.
The article may test and narrow individual links, but it may not substitute the adjacent
Warren Commission withholding story without preserving the original investigation and
obtaining an author decision on a fundamental change.

Initial high-value branches:

- QJWIN's one-shot Congo mission and its exact task;
- WIROGUE's action profile and any lethal tasking;
- the April 1963 Miami/Islamorada expenses and boat;
- Harvey/Roselli contact and accounting records;
- the June 1963 “precautionary lifeline” and any successor personnel or function;
- the Hunt/Furiati-named Dallas and anti-Castro people, travel, money, communications,
  and institutional links.

### Canon premise → next-hop proof

Published TWO-FOLD canon establishes that real visible work can coexist with a concealed
personnel system using spotting, assessment, proprietary cover, and obscured sponsorship.
The new edge is not “ZR/RIFLE was TWO-FOLD.” It is: identify who performed ZR/RIFLE's
spotting and assessment, which commercial/criminal covers were productive, whether those
people or procedures moved into Task Force W or another compartment, and what records
that migration should leave.

### Network convergence proof

The frozen chains converge on Harvey through executive-action assignment, Helms
authorization, QJWIN recruitment, Roselli/Castro operations, Task Force W, and later
withholding. They also converge on the Congo question through QJWIN and WIROGUE. The
upgraded workflow records whether those paths rely on independent documents or the same
CIA file family before assigning corroborative weight. Convergence opens coordination,
access, chronology, infrastructure, and coincidence tests; it does not itself prove one
command structure.

### Representative Writer Packet boundary

The writer would receive the locked investigation, the above developed chains, a
chronology, selected quotations and locators, authenticated facts, accepted testimony,
contradictions, unresolved edges, one material boundary per claim, Gold-derived narrative
behavior, and a reveal sequence. The writer would not receive the thesis-rejection prose
as the article's controlling structure. Full failed-claim and proof-status bookkeeping
would remain with the independent auditor.

### Semantic diagnostic result

Read-only analysis of `output/article.md` found:

- `DEFENSIVE SEQUENCE`, `CONTRIVED DIALECTIC`, and `PREMATURE ADJUDICATION` at lines
  176–192;
- `NARRATIVE STAGNATION` at lines 176–186;
- `THESIS SUBSTITUTION` at line 190, where “maximum thesis fails” is followed by the
  safer-story redirect;
- article-wide `AUDITOR VOICE` concentrated in that sequence;
- `CANON DEFENSIVENESS` at line 87;
- article-wide narrator-absence and mechanical-reveal signals for human review.

A regression control containing one compact material qualifier does not trigger either
DEFENSIVE SEQUENCE or THESIS SUBSTITUTION.

### Quality-gate result on frozen v1

| Gate | Result | Reason |
| --- | --- | --- |
| A Technical | PASS | Existing Markdown, source map, FAQ, markers, and link checks pass |
| B Research completeness | NOT RUN | No upgraded completeness decision; active rabbit holes remain |
| C Thesis fidelity | NOT RUN | No locked Source Thesis or explicit fidelity/author-decision fields exist in v1 |
| D Narrative | NOT RUN | No upgraded narrative-gate decision exists |
| E Author voice | NOT RUN | No full-body Gold comparison or semantic-review artifact exists |
| F Evidence integrity | NOT RUN | No upgraded independent gate decision exists |
| G Human approval | AUTHOR APPROVAL REQUIRED | Software cannot approve publication |

This is the intended behavior: the same frozen article may retain a technical PASS while
the system refuses to imply editorial readiness.

## Role/model execution contract

When available in the client, the documented preference is GPT-5.6 Sol High for research,
connections, extraction, and independent evidence audit; GPT-6 Astra for showrunning,
drafting, voice work, and final surgical correction. The repository does not invoke or
switch these models automatically. The stages must be run as separate manual Codex
tasks/turns with the defined context boundary, or performed with the available model while
recording the limitation.

## Verification

- Modified Python modules compile successfully.
- Focused workflow, article, series, editorial-memory, and legacy-pipeline regression set:
  **121 passed**.
- Dedicated foundational-upgrade tests cover artifact creation, thesis order and lock,
  approved/unapproved fundamental change, canon/voice separation, convergence and source
  dependency, rabbit-hole dispositions, writer/auditor context separation, independent
  gates, frozen-v1 semantic detection, compact-qualifier control, series inheritance, and
  manual model-role handoff.
- Full regression suite: **263 passed** (82 third-party NumPy/joblib deprecation
  warnings; no failures).
- Frozen-project integrity: **87 files before, 87 files after, zero SHA-256
  differences**.
