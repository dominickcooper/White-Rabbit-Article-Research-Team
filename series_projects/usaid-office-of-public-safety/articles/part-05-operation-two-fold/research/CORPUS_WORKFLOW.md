# Part 5 corpus workflow

## Controlling instruction

Reconstruct Operation TWO-FOLD from the records upward. Do not begin with Douglas
Valentine's or any other secondary author's conclusion. Secondary works may identify
names, citations, relationships and missing records; each consequential claim must be
reversed to an underlying primary record where possible.

The source corpus is read-only. Nothing in `../sources/` may be edited, renamed, moved
or deleted.

## Persistent method

1. Run `python research/index_corpus.py` from the Part 5 article directory, or invoke
   it by full path from the repository root.
2. Confirm every source file has a stable `P5-####` identifier in
   `generated/corpus_manifest.csv`.
3. Review exact and normalized duplicate groups. Duplicates remain in the ledger; one
   representative can carry the substantive reading only when identity is verified.
4. Work through every size-bounded file under `generated/review_packets/` in order.
   Long books are also reviewed by internal section/chapter and citation trail, not
   merely by keyword hits.
5. Update `CORPUS_REVIEW_LEDGER.csv` for every source ID. `REVIEWED` means the entire
   record was examined; `DUPLICATE_REVIEWED` means byte/text identity was verified and
   the canonical copy was fully examined; `OCR_BLOCKED` means the file was inspected
   but extraction defects prevent reliable substantive review.
6. Put document-level findings and limitations in `DOCUMENT_NOTES.md`, claim-level
   synthesis in `CLAIMS_LEDGER.md`, chronology in `TIMELINE.md`, people and institutional
   links in `ENTITY_NETWORK.md`, and unresolved searches in `OPEN_LEADS.md`.
7. Test each meaningful secondary claim against the primary corpus and log the result
   in `REVERSE_SOURCING_LEDGER.md`.
8. Chase external leads only after the local corpus has supplied a concrete name,
   document identifier, event or claim. Prefer official archives and primary records.
9. Reconcile Parts 1–4 and shared-series sources after independent Part 5 findings are
   recorded, so continuity does not substitute for reading the new corpus.
10. Do not outline or draft the article during this phase.

## Evidence and responsibility labels

- `DOCUMENTED FACT`
- `STRONG INFERENCE`
- `PLAUSIBLE CONNECTION`
- `SPECULATION / UNVERIFIED`

Where responsibility is material, distinguish direct, command, institutional, probable
and possible responsibility. Record the strongest competing explanation and the exact
gap that prevents a stronger classification.

## Completion gate

Research is not corpus-complete until every manifest row has a non-`UNREVIEWED` status,
every OCR-blocked record has an explicit limitation, duplicate treatment is documented,
the two book-length HTML sources have chapter/section coverage notes, and the claims,
timeline, entity, reverse-sourcing and open-lead ledgers have been reconciled.

## Completion status — 2026-09-26

- Manifest rows accounted for: **155 / 155**
- Fully reviewed: **134**
- Exact/normalized duplicates verified against reviewed canonical copies: **20**
- OCR-blocked after inspection: **1** (P5-0148; blank/unusable extraction)
- Remaining `UNREVIEWED` rows: **0**
- Source integrity check against the manifest: **155 matches; 0 missing or changed**
- Book-length sources received segmented/chapter and citation-trail review.
- Claims, chronology, entity, open-lead and reverse-sourcing ledgers reconciled.

The local-corpus completion gate is satisfied. External document recovery remains open and
is explicitly separated from corpus completeness.

## External recovery checkpoint — 2026-09-26

Four external records/maps have been incorporated without adding them to the 155-file local
corpus count:

- **E-001:** CIA Family Jewels memorandum/action notation establishing TWO-FOLD's selective
  May 1973 continuation and supplying the adjacent origin account.
- **E-002:** Library of Congress Rockefeller Commission finding aid supplying exact testimony
  and chapter-file retrieval coordinates.
- **E-003:** CIA damage assessment 104-10428-10019 identifying Byron Engle as a CIA employee
  who served as AID/OPS director under cover.
- **E-004:** CIA Office of Training FY1972 annual report documenting a separate BNDD foreign-
  clandestine training channel beginning in November 1969.

External records are logged in `DOCUMENT_NOTES.md` and their claims propagated to the claims,
timeline, entity, reverse-sourcing, synthesis and open-lead ledgers. They do not alter the
local-corpus accounting or authorize modification of `sources/`.
