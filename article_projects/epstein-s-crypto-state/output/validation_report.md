# Validation report

Project: `epstein-s-crypto-state`  
Validated: **September 23, 2026**

## Result

**PASS**

Command:

```text
.\.venv\Scripts\python.exe codex_article.py validate epstein-s-crypto-state
```

## Mechanical metrics

| Metric | Result |
|---|---:|
| Article word count | 3,244 |
| Image markers | 8 |
| Subscribe markers | 1 |
| Share markers | 1 |
| Markdown links | 30 |
| External source links | 26 |
| Internal-link occurrences | 4 |
| Unique internal White Rabbit articles | 4 |
| FAQ questions | 5 |
| Source CSV rows | 26 |
| Validation errors | 0 |

## Link verification

- **22 of 26** source URLs returned HTTP 200 to a direct HEAD check.
- The remaining four—Washington Post, DOI/ACM, ADGM, and Justia—were independently retrieved by the browser/search verifier; their HEAD behavior reflected a timeout, access control, or DNS handling rather than a dead destination.
- All **4 of 4** internal White Rabbit links returned HTTP 200.
- All 26 source-map anchors match their exact article phrases and destinations.

## Editorial diagnostics

The validator reported two advisory warnings:

1. Two paragraphs are entirely bold. Both are intentional argumentative punch lines: the Satoshi-sidebar conclusion and the sovereign-pitch limit.
2. Mechanical validation does not establish factual truth or editorial source adequacy. Those issues are addressed separately in `audit.md`.

No length warning was produced. The article is within the repository’s usual 2,000–3,500-word band and the user’s requested 3,000–4,500-word band.

## Evidence QA

- Direct quotations verified: **24 / 24**
- Factual claims audited: **100 / 100**
- Source rows reconciled: **26 / 26**
- Primary or official/court sources: **24**
- Unique EFTA documents linked in final source map: **17**

## Live court-status check

As of September 23, 2026, the foreign-language-materials portion of Judge Emmet Sullivan’s September 16 order is temporarily stayed pending D.C. Circuit consideration of DOJ’s forthcoming stay request in *Phang v. Blanche*, No. 26-5299. The appellate court had not resolved that request, and the reviewed docket did not show that foreign-language review or production had begun.
