# CODEX WORKFLOW — WHITE RABBIT INVESTIGATIONS

This is the required production workflow for a full White Rabbit article.

## 0. Resolve the assignment
Read the user's prompt and the project's `ARTICLE_BRIEF.md`. Establish:
- topic / central mystery
- project slug
- any user-supplied thesis or angle
- explicit inclusions/exclusions
- whether the article is standalone or part of a series
- any known source folders or prior White Rabbit articles the user wants emphasized

If the brief is incomplete, do not stall unless the missing information makes the task impossible. Make a reasonable working interpretation and record it in `research/research_log.md`.

## 1. Inventory author-provided sources
Inspect every relevant file under `sources/` before broad web research.

Create or update `research/source_inventory.md` with:
- filename
- type
- date if known
- author/agency/company if known
- what it appears to contain
- usefulness to the investigation
- any access/extraction problem

Do not treat the filename as evidence of the document's contents.

## 2. Extract the evidence already in hand
Create structured notes in `research/evidence_notes.md`.

Capture:
- documented facts
- dates and timelines
- people and organizations
- agencies/programs/operations
- contracts, patents, grants, FOIA identifiers, case numbers
- money flows and ownership/investor relationships
- quotations worth preserving
- technical claims and specifications
- contradictions
- unresolved questions
- leads to verify online

For technical material, always record:
1. what the source literally says;
2. plain-English meaning;
3. why it matters.

## 3. Search institutional memory
Search `research_library/previous_white_rabbit_articles/` for relevant prior reporting.

Look beyond title overlap. Search for:
- people
- companies
- agencies
- intelligence relationships
- investors/VC firms
- banks/foundations/NGOs
- defense contractors/subcontractors
- technologies/patents
- universities/research programs
- covert programs and historical precedents
- shared lawyers/directors/donors/personnel

For each useful prior article, record in `research/prior_white_rabbit.md`:
- actual title and canonical URL
- why it is relevant
- useful claims/leads
- original external sources worth reopening
- whether it is a good internal-link candidate

Previous White Rabbit prose is not automatic evidence. Re-verify important claims at the underlying source.

## 4. Build a research plan
Before browsing widely, create `research/research_plan.md` with focused research lanes.

Typical lanes include:
- origin/history
- official documents
- key people
- corporate ownership/funding
- patents/contracts/grants
- intelligence/defense ties
- scientific/technical evidence
- legal/court/FOIA record
- critics/whistleblowers
- conventional explanation
- contrary evidence
- unresolved anomalies
- responsibility and command hierarchy
- foreign-government knowledge, private assessment, and response

Prefer targeted queries over vague topic searches.

## 5. Conduct new online research
When web/network access is available, search broadly but source selectively.

Priority order:
1. primary government/legal/corporate/scientific source
2. archival/original reporting
3. reputable secondary reporting
4. discovery sources such as Wikipedia

Wikipedia is useful for orientation, names, dates, bibliographies, and discovering primary sources. It should rarely be the final source for a consequential claim when a stronger source is available.

Follow meaningful rabbit holes. Do not force them.

Examples:
- inventor → military program
- company → defense contract
- startup → intelligence-linked investor
- patent → surveillance application
- contractor → subcontractor
- executive → prior government/intelligence role
- university lab → agency grant
- foundation → donor/personnel network
- local deployment → federal database access

Log significant searches, useful sources, dead ends, and inaccessible sources in `research/research_log.md`.

## 6. Create the research dossier
Create `output/research_dossier.md` before drafting the article.

Organize by investigative theme, not by source order.

For major findings include:
- FINDING
- EVIDENCE
- SOURCE(S)
- EVIDENCE TYPE
- CONFIDENCE
- WHY IT MATTERS
- NATURAL QUESTION
- IMPLICATION
- CONTRARY/CONVENTIONAL EXPLANATION
- UNRESOLVED GAP

For consequential inferences also record the competing explanation, the evidence-weighted judgment, why that judgment is more likely than alternatives, and the applicable responsibility level.

Use the White Rabbit pattern:

**FACT → QUESTION → JUDGMENT → IMPLICATION**

The judgment states what the evidence most likely means after testing alternatives. Neither the judgment nor implication may be written as proven fact unless the evidence actually proves it.

## 7. Design the article
Create `output/outline.md`.

Default to approximately 12–20 headings/subheadings when the material supports it. The flow should usually resemble:
- strange hook / mystery
- background
- key players
- documentary trail
- technical or financial evidence
- unexpected connections
- historical precedent
- conventional explanation
- what that explanation accounts for
- what remains unresolved
- larger pattern / implication
- conclusion
- FAQ
- related White Rabbit articles

Do not use generic section names like "Introduction" or "Body."

## 8. Build SEO/publishing metadata
Create `output/seo.md` using `docs/SEO_AND_PUBLISHING.md`.

## 9. Draft the article
Create `output/article.md` using `docs/WHITE_RABBIT_STYLE.md`.

The article must be a complete reader-facing artifact, not research notes disguised as prose.

## 10. Add image, subscribe, and share placements
Add image instructions and publishing markers directly in `article.md` according to `docs/SEO_AND_PUBLISHING.md`.

## 11. Source and hyperlink the article
Apply the rules in `docs/SOURCING_AND_LINKING.md`.

The final article should contain inline Markdown links at the first useful occurrence of the supported phrase.

Create `output/sources.csv` as an audit/reference artifact.

## 12. Add FAQ and related-reading section
The finished article must end with five useful FAQs followed by:

`## YOU MAY BE INTERESTED IN THESE ARTICLES`

Select genuinely relevant archived White Rabbit articles.

## 13. Perform adversarial audit
Create `output/audit.md`.

Audit for:
- factual errors
- unsupported claims
- weak sourcing
- stronger primary sources that should replace secondary sources
- inference inflation
- quote accuracy
- timeline problems
- title/SEO mismatches
- broken or mismatched links
- tracking parameters
- excessive generic AI prose
- repetitive rhetoric
- weak conventional explanation
- weak conclusion
- overstatement
- understatement or unwarranted neutrality
- failure to assign supported direct, command, institutional, probable, or possible responsibility
- failure to investigate meaningful foreign-government action or inaction

Also perform two explicit editorial passes:

1. Build a section-by-section source-coverage matrix. For every major section, record its consequential claims, current visible sources, locally supported but unlinked claims, and the action taken or remaining gap. Incorporate the final assessment into `output/audit.md`; the working matrix may remain in `research/` or be removed after the audit is complete.
2. Compare the dossier against the article for underused research. Preserve well-supported multi-step rabbit-hole chains rather than compressing them into a single causal sentence. Label chronological facts, the source author's causal interpretation, reasonable inference, and unproved links distinctly.

The final editorial pass should also vary formulaic evidence disclaimers while preserving their caution. Mechanical validation and editorial evidence adequacy are separate gates; both must pass.

Add an evidence-weighted conclusions audit covering each major inference. For each, record the conclusion, evidence level, strongest support, strongest alternative, confidence, and whether the article wording matches the evidence. An article can fail this audit by being too timid as well as by being too certain.

Then fix `article.md`, `seo.md`, and `sources.csv` as needed. Do not merely list defects.

## 14. Validate and finish
Run:

`python codex_article.py validate <project_slug>`

Fix all meaningful failures before completion.

In the final Codex response report:
- final title
- word count
- external source count
- primary-source count if determinable
- internal White Rabbit link occurrences and unique-article count
- image placement count
- subscribe-marker count
- share-marker count
- unresolved research gaps
- paths to every deliverable
