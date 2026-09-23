# SOURCING AND LINKING RULES

## Core rule
Every important factual claim should be traceable to a source that actually supports it.

The final `article.md` should contain inline Markdown hyperlinks, not placeholder citation numbers.

## Preferred linking behavior
Hyperlink the **first useful occurrence** of the exact phrase supported by the source.

Example:

`The [Church Committee's final report](https://...) documented ...`

Do not link every later occurrence of the same phrase unless a different source supports a different claim.

## Source selection
Prefer:
1. stable primary source
2. contemporaneous original reporting
3. reputable secondary source
4. discovery/reference source only when stronger material is unavailable

Do not use a source merely because it mentions the same subject. The page must substantiate the linked claim in context.

## Canonical URLs
- Strip UTM and tracking parameters when a clean canonical URL exists.
- Prefer stable agency, court, patent, university, archive, or publisher URLs.
- Avoid temporary redirect/grounding URLs.
- Do not invent a URL.

## Research-access links versus publication-facing links

Mirrors, OCR repositories, cached copies, StudyLib, and similar services may be used to inspect difficult material during research. In the final article, preferentially link readers to:

1. the original government or archive source;
2. the publisher DOI or official publication page;
3. a university repository;
4. an official institutional page;
5. a stable legitimate archive;
6. only then a mirror or secondary copy.

Do not use a research mirror as the reader-facing citation when an authoritative publication page for the same work exists. A mirror may remain in research notes with its limited purpose identified.

## White Rabbit internal links
Search the local archive first.

Use the actual published article title and canonical White Rabbit URL.

Prior White Rabbit articles can be used as:
- related-reading/internal links
- investigative memory
- a lead to original sources

Do not use prior White Rabbit prose as the only support for an important factual assertion when the original external source can be reopened.

## Links to people and organizations
On first meaningful mention, link important people/companies/agencies when a source materially improves the reader's understanding or verifies a consequential fact.

Do not turn every proper noun into a link.

## Source CSV
Create `output/sources.csv` with exactly:

`source_number,phrase,link`

Rules:
- `phrase` must EXACTLY appear in the final `article.md`.
- The link must support the sentence/context containing that phrase.
- Each URL should normally appear once in the CSV at its first useful occurrence.
- Remove tracking parameters.
- Prefer primary sources.
- Number sequentially from 1.
- Escape CSV fields correctly when they contain commas or quotes.

The CSV is an audit artifact even though `article.md` already contains hyperlinks.

## Verification audit
Before finishing:
- confirm every CSV phrase exists exactly in `article.md`;
- confirm the Markdown hyperlink destination agrees with the CSV where applicable;
- flag inaccessible sources in `audit.md`;
- remove links that do not substantiate their surrounding claim;
- replace weaker sources with stronger primary ones when reasonably available;
- verify quotations against their source;
- verify dates, amounts, and identifiers.

### Editorial coverage is separate from mechanical validity
Passing CSV and hyperlink checks proves that declared source relationships are well formed; it does not prove that the article is adequately sourced. Before publication, build a section-by-section coverage matrix and identify consequential factual claims whose support exists only in the dossier or supplied files. Add a strong inline source at the first useful occurrence when one is reasonably available. Do not add weak links merely to increase a count.

For a local or private source with no public copy, make its evidentiary role visible in the prose by naming the author, title, document, interview, or relevant page/location when useful. Never invent a public URL. If a legitimate publisher, library-catalog, repository, or authorized full-text page exists, it may provide bibliographic visibility, but it must not be described as supporting text the page does not expose.

### Internal-link metrics
Report these separately:

- **internal link occurrences:** every White Rabbit Markdown link in the article, including repeated destinations;
- **unique White Rabbit articles:** distinct canonical article URLs after normalizing a trailing slash.

Use the unique-article count when evaluating whether the related-reading requirement has been met. Repeating one URL does not create additional coverage.

## Source quality labels in research notes
During research, it is useful to mark sources as:
- PRIMARY
- CONTEMPORANEOUS REPORTING
- SECONDARY ANALYSIS
- DISCOVERY ONLY
- UNVERIFIED / LEAD

These labels do not need to appear in reader-facing prose unless useful.
