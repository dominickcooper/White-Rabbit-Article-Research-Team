# Stage 2C — independent factual audit, adversarial review and source reconciliation

Date: 2026-10-05  
Role: Independent Factual Auditor and Senior Investigative Editor  
Status: **AUDIT COMPLETE — CORRECTED DRAFT REQUIRES AUTHOR REVIEW**

## Scope completed

The accepted Stage 2B.1 article was preserved before edits and audited against the full
research record rather than the Writer Packet alone. The audit included the locked Source
Thesis, approved Story Spine, supplied thirteen-file corpus, v1 extractions, evidence and
testimony ledger, connection chains, dependency trace, Extreme-Thesis reduction, Zebra
analysis, external research log, published White Rabbit canon and targeted re-opening of
official NARA/FRUS/committee records.

The article was not broadly rewritten. Corrections were limited to factual scope, source
dependency, adversarial evidence and reader-facing source links.

## Snapshot and integrity record

The accepted Stage 2B.1 article was preserved byte-for-byte at:

`research/revision_history/STAGE_2B1_ARTICLE.md`

Incoming article and snapshot SHA-256:

`8B1B78E3D92E4C33669DE552DB8CBA2AFC9EA58EFC27895D3A5591703D8A6D15`

Corrected article SHA-256:

`A552B779F756C73E2D1B4F84CD08DEE4B81ADD4CCB7F1DB24485D77CD9CC3584`

Hash comparison against the Stage 2C baseline found only two pre-existing files changed:

- `output/article.md`
- `output/editorial_audit.md`

New Stage 2C/final-deliverable files are:

- `output/audit.md`
- `output/outline.md`
- `output/seo.md`
- `output/sources.csv`
- this report

All 87 v1 files remain present and hash-unchanged. All thirteen v2 source files remain
present and hash-unchanged. No pre-existing research artifact, locked thesis, approved
spine, private source or completed article was changed. No file was removed.

## Audit coverage

- 228 sentence-level article units screened.
- 53 consequential claim clusters individually mapped in `output/audit.md`.
- Direct fact, attributed testimony, secondary interpretation, inference, contradiction,
  non-substantiation, denial, source dependency and missing evidence were reviewed as
  distinct categories.
- Every major section received a reader-facing source-adequacy review.
- Twelve unique source URLs were reconciled in `output/sources.csv`, each once, against
  the exact linked phrase and destination in the article.

## Findings by severity

### CRITICAL — 1 found and corrected

The Congo section said too little was known about QJWIN's original mission. FRUS document
46 contains a November 29, 1960 cable describing a plan to enter a redacted target's home
with UN-marked vehicles, remove him under escort and, after the target moved, consider
QJWIN's proposed direct action in Stanleyville. The correction adds this record while
preserving the target redaction, the ambiguity of “execute the plan,” and the Church
Committee's finding that no clear evidence established QJWIN's participation in an
assassination plan or attempt.

The result is more precise than either extreme: QJWIN's Congo activity was not a blank,
but the record still does not disclose the target, final task or outcome.

### IMPORTANT — 2 found and corrected

1. The WIROGUE execution-squad offer lacked the station's contrary account. The article
   now states that Leopoldville considered WIROGUE freewheeling and that the chief of
   station denied authorizing the approach or tasking an execution squad.
2. Major documentary claims lacked granular first-use links. NARA/FRUS links were added
   for the Helms authorization, Mankel identity, Congo cables, Task Force W, Harvey's
   August 1962 memorandum and the 2025 lifeline release.

### MINOR — 2 found and corrected

1. “Hunt's versions” was narrowed to “The book” because the Guatemala claim belongs to
   Hamburg's afterword narration rather than a second Hunt statement.
2. The duplicate Cargill destination at the lifeline was replaced by the fuller 2025
   NARA release.

No CRITICAL, IMPORTANT or MINOR correction identified by this audit remains unapplied.

## Adversarial review result

The strongest official or record-based alternatives were checked:

- Harvey's denial sits beside the committee's capability finding.
- The Leopoldville station's unauthorized/freewheeling account now sits beside the
  WIROGUE offer.
- Church non-substantiation and the later denial of a QJWIN/WIROGUE role in Lumumba's
  arrest or death remain distinct.
- Bissell's merger account and Helms's no-crossing account both remain.
- Hunt's later denial, Phillips/Veciana non-recognition and the Lorenz inconsistency
  finding remain in the article.
- Rockefeller's derelict-photo finding and the HSCA's group-level findings were audited.
  They were not inserted because the article does not make the propositions they directly
  reject and neither resolves the later person-specific account. Their scope is recorded
  in `output/audit.md`.
- Cuba work remains the substantial ordinary explanation for the Florida expenses;
  cover/termination costs remain an alternative explanation for post-termination money.

No omitted contrary evidence was found that requires abandoning or fundamentally
changing the locked thesis. `AUTHOR THESIS DECISION REQUIRED` is not triggered.

## Source and link reconciliation

The corrected article has:

- 15 Markdown link occurrences;
- 9 external official/archive links;
- 6 internal White Rabbit link occurrences;
- 3 unique internal White Rabbit articles;
- 12 unique `sources.csv` mappings.

Hunt and Furiati remain supported by the deliberately supplied private corpus with
chapter/page provenance in the article and audit. No public link was invented for them.
Repeated Cargill/NARA releases, Hunt/Hamburg retellings, Furiati/Escalante interviews and
*Double Cross* dependencies were not double-counted as independent evidence.

## SEO and final deliverable completion

`output/seo.md` now contains every required SEO heading and content. `output/outline.md`
was added from the approved final reveal order because the six-deliverable validator
requires it. The title remains the author's preferred title:

**Project ZR/RIFLE: The CIA's Assassination Network**

No new factual assertion was introduced merely for SEO.

## Editorial and semantic diagnostics

The separate editorial audit passes the corrected article after surgical repair while
reserving author voice approval. The mechanical semantic diagnostic reported:

- 66 prose paragraphs;
- no abstract blocks;
- no symmetric-contrast signal;
- no caution-density passage;
- no semantic-rhetoric flag;
- two “however” pivots, both retained because they introduce material contrary evidence;
- a paragraph-uniformity warning (`CV 0.218`), recorded without an unauthorized broad
  rhythm rewrite.

The article's 4,299 words exceed the repository's generic 2,000–3,500 advisory range but
fall inside the user-authorized 3,500–4,500 target. Six image markers, one subscribe
marker, one share marker, exactly five FAQ questions and the related-reading section are
present.

## Validation and tests actually run

### Article validator

Command:

`.venv/Scripts/python.exe codex_article.py validate zrrifle-v2`

Result: **PASS**; zero errors. Warnings were the generic length advisory, the two
reviewed “however” pivots, paragraph uniformity and the standard notice that mechanical
validation does not establish factual truth.

The validator's embedded D/E/F statuses still echo the preserved pre-draft
`research/QUALITY_GATES.md`. That existing research artifact was not rewritten because
Stage 2C prohibited altering preserved research. Current Stage 2C evidence is instead:

- Narrative/editorial review: PASS AFTER SURGICAL REPAIR; author voice review required.
- Independent factual/evidence review: PASS AFTER SURGICAL CORRECTION.
- Human publication gate: **AUTHOR APPROVAL REQUIRED**.

### Regression suite

The first full run reached 108 passing tests but produced 155 setup errors because pytest
could not access its default Windows temp root. This was an environment failure, not a
test assertion failure.

The same suite was rerun with a fresh repository-local `--basetemp` and the cache provider
disabled. Final result:

`263 passed, 82 warnings in 30.90s`

The warnings are existing NumPy/joblib deprecations. The temporary test directory was
removed after the passing run.

## Deliverable hashes

| File | SHA-256 |
| --- | --- |
| `output/article.md` | `A552B779F756C73E2D1B4F84CD08DEE4B81ADD4CCB7F1DB24485D77CD9CC3584` |
| `output/sources.csv` | `D04A7A0EC24FC198C5160B2C8ACFF794479BD26D286C5563AC417282232B8583` |
| `output/audit.md` | `A251EB89B993A65EB2B7EC1D959FF3465AAAFD4A68C6C8E8C05DB9EA8E3065A1` |
| `output/editorial_audit.md` | `D647F2F50D796583A4E5CAE2AE6B50E6103C904554EDFA1B935A515941BAE0ED` |
| `output/outline.md` | `6B5DB523E7D5ED3F348F9F19DB989AC2BDC307AD3BCF42F418AFBF3376ED4E3A` |
| `output/seo.md` | `5FC9D18CDEEBE3C4580E333BE04FB3374E8CE650F79FD6EBC65E8D5F765074E4` |

## Model/runtime note

GPT-5.6 Sol High was preferred by the brief. This repository session provided no
attestable in-place model switch or reliable runtime identity check, so no claim is made
that the preferred model executed the audit. The available runtime performed the work
under the requested independent-auditor role.

## Prohibited actions check

No commit, push, export, DOCX/HTML generation, publication or external message was made.
The 87-file v1 project, supplied sources, locked thesis, approved spine and existing
research artifacts remain intact.

Final author decisions remain voice acceptance, editorial approval and publication.

**STAGE 2C COMPLETE — AUDITED DRAFT READY FOR AUTHOR REVIEW**
