# Part 3 Final Source Audit

Date: 2026-09-20  
CSV: `article_workspace/PART_03_PUBLICATION_SOURCES.csv`  
Linked candidate: `article_workspace/PART_03_REWRITE_V3_LINKED.md`

## Reader-facing source links

Every CSV anchor was found exactly once by the repository linker. “Primary” below includes statutes, contemporaneous government records, official investigations and firsthand testimony. “Secondary” includes histories, published scholarship and curated briefing portals.

| # | Anchor / destination | Class | Live check | Factual-support check |
|---:|---|---|---|---|
| 1 | CIA inspector-general inquiry — Senate-hosted official report | Primary | PASS | Supports Air America inquiry findings and control limitations |
| 2 | Agency's later official history of Laos — CIA CSI | Secondary | PASS | Supports wartime-priority context; not used as proof of trafficking |
| 3 | McCoy's interviews describe — Internet Archive bibliographic record | Secondary | PASS / borrow required | Exact 1972 Harper & Row edition matches the locally fact-checked book |
| 4 | around Mae Salong — FRUS document 173 | Primary | PASS | Supports Mae Salong resettlement, roads/economic program and anti-opium commitment context |
| 5 | August 1974 Embassy program record — State FOIA | Primary | PASS | Supports Laos military-police narcotics program and its stated objective |
| 6 | Police Academy Review — OJP scan | Primary | PASS | Supports PMNO No. 8, class composition and academy totals |
| 7 | FY1966 — Treasury annual report at FRASER | Primary | PASS | Supports FBN course and 19-officer figure |
| 8 | FY1967 — Treasury annual report at FRASER | Primary | PASS | Supports recurring FBN course / lectures |
| 9 | FY1968 — Treasury annual report at FRASER | Primary | PASS | Supports recurring bilingual FBN instruction |
| 10 | 1972 Justice Department report — OJP record | Primary | PASS | Supports IPA scale, alumni commands, narcotics training and contact value |
| 11 | Bill Lair's retrospective account — CIA CSI memoir | Primary | PASS | Supports PARU role and the USAID/CIA organizational distinction; memoir disclaimer noted |
| 12 | Public Law 93-559 — GovInfo | Primary | PASS | Supports Section 660 text, effective date and original exceptions |
| 13 | Public Law 99-83 — GovInfo | Primary | PASS | Supports later Administration of Justice amendments |
| 14 | 1986 Congressional Record — GovInfo | Primary | PASS | Supports contemporaneous Hasenfus account |
| 15 | archival oral history — Texas Tech Vietnam Archive | Primary | PASS | Supports McRainey's firsthand Cooper recollections |
| 16 | Compiled airframe histories — Texas Tech archive | Secondary | PASS | Supports the qualified serial/registration chain only; not treated as certified FAA proof |
| 17 | *Drugs, Law Enforcement and Foreign Policy* — NSA-hosted committee report | Primary | PASS | Supports Senate findings and named company/payment material |
| 18 | 1982 CIA–Justice Department agreement — DOJ OIG | Primary | PASS | Supports employee/nonemployee reporting-rule distinction |
| 19 | CIA's inspector general — stable FAS archive of official CIA OIG report | Primary | PASS | Supports Morales-related contacts and case-specific referral/retention findings |
| 20 | U.S. records document CIA political action — National Security Archive Brazil collection | Secondary | PASS | Curates primary records supporting pre-coup action and contingency planning |
| 21 | Brazilian Truth Commission — official Brazilian government portal | Primary | PASS | Supports the commission and its final-report record of repressive institutions |
| 22 | U.S. reporting addressed police-linked killings — National Security Archive briefing book | Secondary | PASS | Curates declassified State records on killings, arrests and interrogation |

Classification totals: **17 primary-source links** and **5 secondary-source links**.

## Book fallback detail

| Source title | Author | Local canonical source | Local edition | Public link type | Public URL | Edition match | Fact-checked against local source? | Notes |
|---|---|---|---|---|---|---|---|---|
| *The Politics of Heroin in Southeast Asia* | Alfred W. McCoy | `sources/52_Alfred_McCoy___The_politics_of_heroin_in_Southeast_Asia.pdf` | Harper & Row, 1972 | INTERNET_ARCHIVE_BIBLIOGRAPHIC_LINK | https://archive.org/details/politicsofheroin0000mcco | EXACT | YES | Borrow/login may be required; the public link is bibliographic access, while quotations and claims were checked against the local canonical scan |

No public Schanche link was published: the local canonical source remains `sources/Mister_Pop_Don_A_Schanche.pdf`, and no verified exact-edition Internet Archive, Google Books or clean Amazon destination was available.

## Internal links

| Link | Status | Placement reason |
|---|---|---|
| *The Blueprint Pt. 1: The CIA’s Global Coup Machine* | VERIFIED | Gives the broader covert-action architecture behind Laos and Brazil |
| *The Phoenix Program: The Template for Endless Wars* | VERIFIED | Connects police files, liaison and counterinsurgency in Vietnam |
| *From Gladio to Guyana: Jonestown and the CIA* | VERIFIED | Supplies related context for Brazil, Mitrione and later allegations |

All three URLs resolve to the intended White Rabbit articles. Phase 4 added a brief reader-facing reason to each related-reading entry.

## Link-policy findings

- Source CSV rows: **22**
- Reader-facing links audited: **25** (22 sources + 3 internal links)
- Book links: **1**
- Internet Archive bibliographic fallbacks: **1**
- Google Books fallbacks: **0**
- Amazon fallbacks: **0**
- Broken legacy URLs found: **3**
- Broken legacy URLs replaced: **2** (two obsolete CIA OIG direct-download destinations consolidated into the stable FAS archive of the official report)
- Broken destination omitted: **1** (the CIA Southeast Asia heroin-study direct URL now redirects to the generic reading-room homepage)
- Mirror/discovery destinations upgraded to stronger authoritative destinations: **4** (State FOIA, OJP, GovInfo and the official Brazilian-government portal)
- Tracking parameters removed: **all reader-facing URLs are clean**

## Deliberately unlinked claim groups

Five claim groups remain without a dedicated public hyperlink even though they are supported by the locked local evidence package:

1. Schanche's Buell narrative: no exact-edition Internet Archive, Google Books or verified Amazon destination was available.
2. The specific CIA Southeast Asia heroin-study passage: its old CIA direct URL redirects to a generic page, so a misleading link was not published.
3. XKAT ownership and cargo allegations: the draft itself identifies the documentary gap; no weak discovery link was added.
4. Later McCoy case details: the single exact-edition McCoy link is placed at the first substantive use rather than repeated.
5. The Mitrione transition: Part 4 is unpublished and the bridge rests on locked local continuity controls.

## Result

All 22 CSV links were inserted by `white_rabbit.publishing.substack_source_linker`, all anchor matches succeeded, and stripping link markup from both Markdown files produces identical narrative text. The linked source layer is ready for validation.
