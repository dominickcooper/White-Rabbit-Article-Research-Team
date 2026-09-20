# White Rabbit Distribution Engine v1

The Distribution Engine converts a completed, evidence-backed series into structured,
human-reviewable campaign assets. It is additive and offline: it does not alter canonical
articles, source CSVs, research, or continuity files; call a model; use credentials; or
publish to any platform.

## Architecture and schemas

`white_rabbit/distribution.py` reads the existing series manifest, continuity record,
Part 1 article, and exact-anchor `sources.csv`. It writes only beneath the series
`distribution/` directory. Stable campaign/article/content IDs are independent of the
canonical folder names. Part 1 claims retain classification, exact source anchor, URL,
article section, and source-file provenance in `evidence_manifest.csv`.

The campaign manifest maps all seven ordered parts. `CURRENT_PART` and `PRIOR_PARTS` are
eligible; future-part facts are blocked unless explicitly `TEASER_SAFE`. V1's supplied
Part 2 teasers are deliberately limited to Part 1's documented transition question.

Content IDs use `WRR-USAIDCIA-P01-PLATFORM-FORMAT-NNN`. Experiments use stable IDs such
as `EXP-HOOK-001`; their scores and variants are editorial heuristics, not validated
scientific measures. UTMs are deterministic and use campaign `usaid_cia_2026`.

## Output layout

```text
distribution/
  campaign/ campaign_manifest.{json,md}, series_hooks.csv,
            experiment_manifest.csv, content_registry.csv,
            analytics_import_template.csv
  part-01/  hooks.csv, platform drafts, utm_links.csv,
            evidence_manifest.csv, approval_queue.csv,
            distribution_manifest.json
```

The analytics template contains no invented observations. Later importers can populate
reach, watch, engagement, click, signup, referral, and revenue fields while preserving
the content/experiment dimensions.

## Editorial and operational safety

Every factual asset beat must have an evidence row. Classifications are limited to
`DOCUMENTED_FACT`, `STRONG_INFERENCE`, `PLAUSIBLE_CONNECTION`, and `SPECULATION` and are
never promoted automatically. Quotations are not synthesized. Document visuals must be
authentic or clearly labeled; generated imagery must never impersonate an archive record.
All generated assets begin at `NEEDS_REVIEW`. No publishing API exists.

Known limitations: v1 is optimized for this seven-part campaign; generation is a
reproducible offline editorial template rather than model-based variation; unpublished
articles temporarily target the publication root; classifications still require human
editorial confirmation; approval decisions are recorded in CSV but no UI is provided.

## Source-aware creative generation (v1.5)

The creative layer now builds a rich claim library from the article and locally stored
source extracts, then groups compatible claims into named angles. Each request receives
a bounded evidence packet, hook-specific guidance, platform requirements, spoiler
prohibitions, exact excerpts, and CTA choices. A provider-neutral `CreativeProvider`
protocol permits an injected model adapter; the normal CLI uses the offline source-bounded
generator, requires no credential, and logs provider, model, prompt version, evidence
packets, and generation time.

After writing, the deterministic layer emits assertion records, maps them to approved
claim IDs, rejects unsupported assertions, surfaces partial support, estimates video
duration, checks near-duplicate copy, and creates `review_packet.md`. Missing local source
text is recorded as `UNAVAILABLE` and requires review; it is never reconstructed.

## Editorial hardening (v1.6)

Assertion validation now examines every generated sentence and splits adversative or
semicolon-linked composite clauses. It distinguishes direct facts, synthesis, inference,
chronology, causation, comparison, numbers, quotations, relationships, and genuinely
nonfactual framing. Synthetic language is recorded as `INFERENCE_SUPPORTED`, mapped to
its underlying claims, downgraded from documented fact, and routed to human review.

Hook families have deterministic semantic requirements. Sentence, closing, and rolling
eight-token repetition are reported separately from whole-asset similarity. Approved
brand phrases are exempt. Copyediting checks capitalization, repeated words, punctuation,
spacing, and quotation balance. Platform-fit checks enforce Facebook long-post depth,
Reddit standalone value, and X thread progression. Every asset now carries component
validation results and an overall `PASS`, `PASS_WITH_REVIEW`, or `FAIL` status.
