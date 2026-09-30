# Validation Report

## Pre-export checks

- Article word count: 4,269 words (PowerShell whitespace count; exporter count may differ slightly).
- Sources: 32 exact phrase/link entries; local precheck found zero missing or mismatched hyperlinks.
- Required article markers: present (3 image opportunities, `[[SUBSCRIBE]]`, `[[SHARE]]`).
- FAQs: exactly 5 under the FAQ section.
- Required research artifacts: present in staging.
- Required output artifacts: present except generated HTML/DOCX, pending repository export.
- Article, story decision and story spine were written only after the research matrices and connection analysis.

## Workflow validation

Repository command: `python codex_article.py series validate usaid-office-of-public-safety part-07-what-survived-inside-foreign-aid`

- Result: **PASS**
- Validator word count: 4,310
- Markdown links: 38
- External links: 35
- Verified White Rabbit archive links: 3
- Source CSV rows: 32
- Duplication matches: none
- Errors: none
- Non-blocking warnings: requested length exceeds the repository's ordinary 2,000–3,500-word range; repeated opening/emphasis diagnostics; reminder that mechanical validation does not prove factual truth. The assignment explicitly authorized 4,000–7,000 words, and the factual/editorial audits review the remaining warnings.

## Export validation

Repository export command completed successfully and generated:

- `output/article_substack.html`
- `output/article_substack.docx`

The DOCX opens through the bundled `python-docx` parser and contains 156 nonempty paragraphs, one section, no tables, and the correct article title. The prescribed PNG rendering tool could not perform visual QA because the workspace dependency bundle did not contain `soffice.exe`; no user-installed LibreOffice was substituted. This is a layout-verification limitation, not an export or content-validation failure.

## Final status

**PASS** for repository validation, factual/evidence audit, editorial audit, source-link integrity and export. Series status recorded as complete. No commit, push or remote action performed.
