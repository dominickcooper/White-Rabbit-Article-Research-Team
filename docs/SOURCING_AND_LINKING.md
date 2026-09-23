# Sourcing and linking

The Codex workflow produces already-linked output/article.md. Unlike the legacy
evidence-marker pipeline, its exporter does not insert links. Use inline Markdown
`[exact phrase](https://canonical-url)`. Percent-encode parentheses in destinations
for DOCX compatibility; reference-style links and raw HTML anchors are not supported.

output/sources.csv must have exactly `source_number,phrase,link` as its header.
Use unique positive source numbers, nonempty fields and exact, case-sensitive phrases
that occur in article.md and are visibly linked to the identical destination. Include
important explicit and implicit factual claims. Use each URL normally once and link
the first useful occurrence. Do not duplicate CSV mappings; repeated contextual links
in article prose are allowed. Strip UTM and other tracking parameters with the existing
publisher's normalize_url rules. Preserve meaningful document identifiers in URLs.

## Mechanical citation validity

Validate exact anchors, correct Markdown destinations, malformed links, invalid or
duplicate CSV rows, HTTP(S) URL syntax and tracking parameters. Local files and private
provenance belong in the dossier, not fabricated public destinations. Validation is
offline: it does not check live URL availability or whether a source supports a claim.

## Editorial source adequacy

Review every major factual section for visible, reader-facing support. A valid CSV or
working URL does not establish source adequacy. Check whether each consequential claim
is sourced and whether the cited record actually substantiates it. Avoid arbitrary
citation quotas. During final audit seek reasonable upgrades to government documents,
archives, court filings, contracts, patents, academic papers, company filings, official
biographies and primary interviews/transcripts. If the claim is a scholar's interpretation,
cite the scholar; a primary document that does not make that interpretation is no substitute.

## Access versus publication

Mirrors, OCR copies, cached scans and StudyLib may help research access. Reader-facing
links should prefer original government/archive records, publisher DOI pages, university
repositories, official institutions, stable legitimate archives, and mirrors only when
necessary. Do not publish a weak mirror when an authoritative destination is available.

## White Rabbit archive

Search research_library/previous_white_rabbit_articles and inspect relevant article.md,
metadata.json and links.json files. Reverify underlying sources. About 3–6 internal links
are often useful, but relevance governs. Link useful callbacks without spamming.
Validation reports internal_link_occurrences separately from
unique_internal_white_rabbit_articles (fragment/query variants count as one article).
Known registry URLs identify archive articles; configure internal_hosts for missing
registry entries/custom publication hosts. Host matching is exact, never substring-based.
Unknown archive URLs are not assumed internal merely because they are on Substack.
