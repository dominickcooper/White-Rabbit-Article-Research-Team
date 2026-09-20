# Distribution workflow

Build and validate from the repository root:

```powershell
python -m white_rabbit.distribution build-campaign usaid-office-of-public-safety
python -m white_rabbit.distribution build-part usaid-office-of-public-safety --part 1
python -m white_rabbit.distribution validate usaid-office-of-public-safety --part 1
```

Add `--dry-run` to either build command to inspect its destination and counts without
writing. Review `evidence_manifest.csv` beside each draft, confirm the source wording and
spoiler boundary, then record reviewer, decision, notes, timestamp, and revision history
in `approval_queue.csv`. Allowed progression is `GENERATED → NEEDS_REVIEW → APPROVED →
READY_TO_PUBLISH → PUBLISHED`, with rejection/revision branches. Generation itself can
never set `PUBLISHED`.

To add a future campaign, create it through the existing series workflow, preserve its
ordered manifest and continuity tease/withhold fields, then add an explicit campaign
profile and evidence-backed claim extraction rules. Do not infer a new campaign ID from
unstable display titles. Future analytics imports must retain the template header, use
nonnegative numeric metrics, and never fill missing measurements with invented zeroes.

Sprint 1.5 adds `campaign/claim_library.csv`, `campaign/angles.json`,
`part-01/assertion_manifest.csv`, `part-01/similarity_report.json`, and
`part-01/review_packet.md`. Review assertion status and the exact source excerpt before
approving an asset. `UNAVAILABLE` is an explicit missing-excerpt marker, not evidence.
A package fails when an assertion is unsupported, a future-part claim crosses the spoiler
boundary, a video plainly misses its duration bucket, or excessive unapproved duplication
is detected.

Sprint 1.6 requires reviewers to inspect inference-supported and partially supported
assertions even when the package passes. `HOOK_MISMATCH`, unsupported language, spoiler
violations, missing evidence, invalid approval state, or failed duration checks block an
asset. Repeated phrases, minor copyediting issues, and platform-fit concerns produce
review warnings. The review packet exposes every sentence-level assertion, mapped claim,
source excerpt, and component validator so clever opening language cannot bypass review.

## Targeted production correction: X length and factual framing

Use the existing builder's refresh option to revalidate saved copy without requesting
creative variants:

```powershell
python -m white_rabbit.distribution build-part usaid-office-of-public-safety --part 1 --refresh-existing
python -m white_rabbit.distribution validate usaid-office-of-public-safety --part 1
```

The refresh preserves canonical files, claim library, evidence packets, publication
URLs, UTMs, approval records, generation provenance and unchanged assertion IDs. Only X
body shortening changes publishable wording. Other platform files may be re-rendered
to reflect corrected assertion and evidence results.

X uses a local 280-character budget, conservatively counting non-ASCII characters as
two. It reserves 24 characters for a separately stored outbound link and its separator,
plus the intact CTA and two separating newlines. It removes complete trailing sentences;
an incomplete legacy tail is discarded. If no complete sentence fits, generation fails
for revision. Thread posts are checked individually, including their numeric prefixes;
the last post reserves the CTA and link. Quotes, decimals and initials remain intact.

Assets store `body_copy`, `cta_text`, and the final `copy`. Assertion extraction processes
body and CTA separately and records `text_section` on each assertion. `validated_copy`
must equal the rendered copy; validation repeats extraction and checks the review and X
renderings. A shortened body cannot borrow punctuation or wording from its CTA.

The rhetoric classifier gives actor/action propositions priority over invitation words.
In particular, an embedded `support` or `review` no longer turns an action by Kennedy or
an agency into an instruction to the reader. Substantive conclusions and questions with
factual premises require evidence; short invitations remain nonfactual. Inference
matching remains a heuristic requiring editorial review, not a factual-truth guarantee.

### Verified USAID Part 1 result

- 43 assets retained; seven X bodies shortened; all other 36 copies unchanged, including
  the X thread. All nine X assets inspected; standalone reserved lengths are 214–273
  against the 280 budget.
- Three occurrences of the Kennedy review request changed from nonfactual to
  `DIRECT_FACT / SUPPORTED`, mapped to `CLM-USAIDCIA-P01-005` in TT-MEDIUM-002,
  IG-REEL-003 and X-THREAD-001.
- Fourteen previously nonfactual assertions now require synthesis/inference review,
  including all three substantive conclusions identified in the brief. Counts compare
  unchanged assertion text against the saved pre-fix baseline.
- 232 unchanged assertion identities retained; deleted fragment rows removed and new
  rows assigned unused IDs. Body/CTA segmentation does not merge factual copy with CTA.
- Distribution validation PASS: 243 assertion rows, zero unsupported, three partially
  supported, 98 inference-supported, zero hook mismatches and zero spoiler violations.
- The three `four decisions` warnings remain visible without adding evidence. Repetition
  checks remain active: 239 warnings (39 sentence, 8 closing and 192 phrase patterns).
  The changed counts reflect final text and corrected sentence boundaries; no repeated
  copy was rewritten or warnings waived.
- Focused tests: 48 passed (25 new cases plus 23 existing). At the time of this sprint's
  production correction, the full suite contained 177 passing tests,
  with 74 existing NumPy/joblib deprecation warnings. Existing Part 1 series validation
  and `git diff --check` passed.
- The aggregate checksum of every canonical file in this series is unchanged. No model
  call, external publishing or approval decision occurred.

Technical recommendation: ready for human editorial launch preparation for these two
corrections. The partial-support, inference and repetition review items still apply.
