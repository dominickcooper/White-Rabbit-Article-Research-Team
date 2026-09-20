# Distribution Engine Sprint 1.5 → Sprint 1.6 comparison

Measured against regenerated USAID Part 1 manifests:

| Measure | Sprint 1.5 | Sprint 1.6 |
|---|---:|---:|
| Assets | 43 | 43 |
| Claim library | 24 | 24 |
| Assertion rows | 140 selected-claim rows | 244 sentence/clause rows |
| Synthetic inference rows | not detected | 123 |
| Partially supported rows | 0 | 3 |
| Unsupported rows | 0 reported | 0 after revision |
| Hook mismatches | not enforced | 0 after revision |
| Whole-asset duplicate rate | 0% | 16.3% |
| Repeated sentences detected | not measured | 36 patterns |
| Repeated closings detected | not measured | 6 patterns |
| Repeated eight-token phrases | not measured | 217 patterns |
| Copyedit warnings | not measured | 0 after revision |
| Platform-fit warnings | not measured | 0 |
| Facebook LONG words | below enforced threshold | 175 |
| CTA families | one default family | 6 |
| Source-excerpt coverage | 100% | 100% |
| Spoiler violations | 0 | 0 |

The higher whole-asset duplicate rate is not a regression hidden by the validator: v1.6
detects it after CTA changes and still remains below the 25% campaign failure threshold.
Unlike v1.5, phrase-level reuse is fully visible. Many warnings are repeated source-backed
claim sentences, not merely boilerplate; editors should use the report to remove needless
reuse without suppressing legitimate evidence.

Three uses of “Follow four decisions across 1962” are now `PARTIALLY_SUPPORTED` because
their selected packets do not establish four distinct decisions. They remain
`PASS_WITH_REVIEW`; an editor should revise the numeral or expand the packet before use.
