# Distribution Engine Sprint 1 → Sprint 1.5 comparison

This report compares the generated USAID Part 1 manifests. Sprint 1's baseline is
recoverable from its implementation and completed run: 43 assets rotated four claims
through one invariant body template. Sprint 1.5 measurements come from the regenerated
v2 manifest and validators; no favorable values are inferred.

| Measure | Sprint 1 | Sprint 1.5 |
|---|---:|---:|
| Claim library | 4 | 24 |
| Assets | 43 | 43 |
| Exact local-source excerpt coverage | 0% (anchors only) | 100% |
| Assets involved in high-similarity pairs | effectively 100% | 0% |
| Unsupported assertions | not measured | 0 |
| Partially supported assertions | not measured | 0 |
| Spoiler violations | 0 | 0 |

Sprint 1 video bodies were the same short claim-summary construction regardless of
bucket. Sprint 1.5 video measurements are 36–47 words for SHORT, 85–89 words for MEDIUM,
and 150 words for LONG_SHORT; estimated durations are 15.0–19.6, 35.4–37.1, and 62.5
seconds respectively. Every video passes the approximate bucket validator.

Sprint 1 used identical platform framing and four repeating bodies. Sprint 1.5 uses
platform branches, 13 rotating hook approaches, ten evidence angles, and a deterministic
near-duplicate check at 0.82 similarity. The final v2 run found no high-similarity pair.
