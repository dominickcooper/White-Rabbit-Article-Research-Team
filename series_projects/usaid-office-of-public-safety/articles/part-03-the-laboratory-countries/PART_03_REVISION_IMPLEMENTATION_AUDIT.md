# PART 3 REVISION IMPLEMENTATION AUDIT

Phase 1 only. This document audits the current repository, Part 3 evidence, adjacent-part continuity, and the implementation path for a later rewrite. It does not rewrite the article, acquire sources, or alter Parts 2 or 4.

Audit date: 2026-09-20  
Repository baseline: `master`; clean working tree before this audit; reconciliation baseline of 192 passing tests.  
Part 3 workspace: `series_projects/usaid-office-of-public-safety/articles/part-03-the-laboratory-countries/`

## 1. EXECUTIVE SUMMARY

The proposed revision is viable, but not every requested section is ready to draft.

The local record is strongest where the future article needs its physical and institutional spine: Buell and Schanche; village collection around Long Pot; Ouane and Thao Ma interview testimony; Air America’s mixed AID/covert-war infrastructure; official concessions about occasional opium carriage and wartime non-suppression; Xieng Khouang Air Transport’s creation and route, though not its alleged narcotics cargo; the Mae Salong road’s construction and commercial effect; several Golden Triangle-to-U.S. endpoints as published attributed accounts; the Contra contractor/enforcement pattern; the 1982 CIA–DOJ reporting gap; and Brazil as a security, access, and political-action comparison where the drug chain breaks.

The record is weakest in the new middle of the article: the FY1974–75 Laos narcotics program, IPA Narcotics Orientation Course No. 8, the recurring Federal Bureau of Narcotics teaching relationship, the exact IPA alumni statistics and “valuable contacts” language, Trần Minh Công, Hang Doua, a named IPA-to-PARU link, Miguel Nazar Haro’s distinct evidence buckets, former Air America personnel in Contra logistics, the Seal/Contra C-123 identity, the scoped CIA Seal/Mena denial, and Héctor Romero Moran. Those are not small decorative gaps. Several are the documents that would make “the academy reappears” more than an analogy.

For planning purposes this audit treats the 24 A–X topic packages as the unit of measurement. Fourteen packages already have enough local support for at least one major planned proposition: A–H, O, Q, S, U, V, and W, although O and S do not yet support their proposed person-level and same-airframe hooks. Ten packages are absent or too incomplete for their proposed narrative function: I–N, P, R, T, and X. “Supported” never means every subclaim in a package is proved.

The same-airframe claim is not verified. The current collection establishes Barry Seal’s 1984 DEA operation and the later Contra shootdown as separate events, but supplies no registration/serial/ownership chain proving that the shot-down aircraft was Seal’s aircraft. The proposed heading “The Same Aircraft Goes to War” is unusable unless Phase 2 closes that chain.

No named IPA graduate-to-BPP/PARU-to-Laos/Long Tieng connection is presently verified. PARU’s CIA role and Laos insertion are supported at a general level; the requested person-level cross-match remains a documentary gap.

The Laos-to-U.S. endpoint is supportable at two levels. Official material supports a regional Golden Triangle/GI/U.S.-market connection. McCoy supplies named 1971 seizure accounts—the Fort Monmouth postal seizure and the Vientiane-to-New York arrest—and an attributed Sopsaisana chain. Until underlying Customs, BNDD/DEA, French, diplomatic, or court records are acquired, those three named cases should remain **PUBLISHED ATTRIBUTED ACCOUNT**, not be promoted to independent official findings.

The evidence can sustain this thesis:

> U.S. aid and covert programs built access, transport, security relationships, and allied institutions that repeatedly intersected with narcotics economies. In Laos and selected Contra cases, officials preserved operationally useful relationships after narcotics risks were known, and enforcement sometimes yielded to strategic priorities. The record is strongest for infrastructure, knowledge, tolerance, and selective non-enforcement—not for a centrally directed CIA drug pipeline into the United States.

The rewrite should not begin until the Tier 1 document package is acquired or the unsupported sections are explicitly cut. Phase 2 should begin with source acquisition and a structured, article-local source-guidance file; only then should the article architecture be locked.

## 2. WRR EDITOR ARCHITECTURE

### 2.1 Two additive workflows

The repository contains two different systems and the distinction matters:

1. The Codex-first workflow, entered through `codex_article.py` and implemented by `white_rabbit/codex_articles.py` and `white_rabbit/codex_series.py`, creates workspaces, generates instructions, inventories filenames, validates publication mechanics, and exports artifacts. It does not call an LLM provider, extract evidence automatically, or fact-check claims. Codex performs the research and writing outside the Python workflow.
2. The legacy `python -m white_rabbit` pipeline uses provider-driven research planning/extraction, `white_rabbit/local_sources.py`, Pydantic schemas, and `white_rabbit/evidence_db.py`. Its richer evidence database is not automatically populated or consulted by the Codex-first series workflow.

This audit concerns the Codex-first series path. Legacy capabilities cannot be treated as safeguards unless they are explicitly connected.

### 2.2 Workspace and source discovery

| Concern | Actual implementation | Result for Part 3 |
| --- | --- | --- |
| Standalone workspace | `white_rabbit.codex_articles.project_path()`, `new_project()`, `create_project()`, `require_project()`, `check_project()`; root configured by `white_rabbit_codex_config.json` | Standalone projects live in `article_projects/<slug>/` with `sources/`, `research/`, and `output/`. |
| Series workspace | `white_rabbit.codex_series.series_path()`, `new_series()`, `add_part()`, `load()`, `find_part()` | Series lives in `series_projects/<series>/`; parts in `articles/<slug>/`; manifest controls order/status/previous/next. |
| File discovery | `white_rabbit.codex_articles.files_under()` recursively lists every file; `generate_prompt()` embeds the inventory | Discovery is path-based. It records filenames, not bibliographic meaning, authority, or allowed uses. |
| Shared sources | `white_rabbit.codex_series.generate_prompt()` separately embeds recursive inventories of `shared_sources/`, part `sources/`, and `shared_research/` | A Part 3 writer is told to inspect both local and shared collections. Sources are associated by directory placement, not a source registry. |
| Configuration | `white_rabbit_codex_config.json` | Defines `projects_dir`, `series_dir`, archive directory/database, internal hosts, and FAQ count. No evidence taxonomy or source metadata configuration exists. |

### 2.3 Parsing and indexing

`white_rabbit.local_sources.SUPPORTED` covers PDF, DOCX, Markdown, TXT, CSV, JSON, HTML, and HTM. `read_local_document()` uses PyMuPDF for PDFs, `python-docx` for DOCX, BeautifulSoup for HTML, the CSV reader for CSV, JSON parsing for JSON, and normal text reads otherwise. `discover_local_documents()` recursively reads supported files. `chunk_document()` makes overlapping character chunks; `rank_chunks()` applies simple term-overlap scoring.

Important limits:

- The Codex prompt says to use `read_local_document()` “when helpful”; it does not call it automatically.
- There is no persistent Codex-first full-text index, OCR pipeline, page-image inspection service, or automatic parent/derivative relationship.
- PDF extraction concatenates pages without durable page identifiers. Page fidelity must therefore be preserved by the researcher or by sidecars such as this project’s page-marked derivatives.
- Scanned/low-text PDFs can appear discovered even when unreadable. The prompt correctly instructs visual inspection and disclosure, but validation cannot detect a false claim of having read them.
- The six utilities under `white_rabbit/research_tools/` are reusable research aids, not part of automatic project validation.

### 2.4 Research planning, evidence atlases, and article planning

The Codex-first prompt in `codex_articles.generate_prompt()` requires stages: source inspection, additional research, claims/evidence ledger, rabbit-hole investigation, dossier, architecture/draft, narrative/voice/visual/evidence/anti-AI passes, source reconciliation, SEO, FAQ, related links, adversarial audit, validation, and export. It creates no atlas itself. Part 3’s ledgers, atlases, timelines, and targeted reports are human/Codex-produced working artifacts.

The legacy path contains reusable structured models:

- `schemas.ResearchPlan` / `ResearchQuestion`
- `schemas.ExtractedEvidence` / `EvidenceExtraction`
- `schemas.ArticleOutline` / `OutlineSection(evidence_ids=...)`
- `schemas.AuditReport` / `AuditFinding`
- `evidence_db.EvidenceDB`, `SourceRecord`, and `EvidenceRecord`

Those models store claims, excerpts, excerpt verification, support type, reliability, people/entities, author/date, and source URL/path. They do not store most of the requested source-use contract, and the Codex-first series writer never receives a database packet unless a human creates one.

### 2.5 Source authority and evidentiary distinctions

Permanent Markdown authorities—especially `docs/RESEARCH_AND_EVIDENCE.md`, `docs/SOURCING_AND_LINKING.md`, and `docs/SERIES_WORKFLOW.md`—require provenance, evidence levels, contrary evidence, limitations, responsibility, primary-source escalation, and continuity. The prompt repeats those duties. Part 3’s own materials go further with claim ledgers and evidence atlases.

Enforcement is editorial, not computational. The legacy `SupportType` enum has only `documented_fact`, `strong_inference`, `plausible_connection`, and `speculation`; `Reliability` has `primary`, `high_quality_secondary`, `secondary`, and `unknown`. It does not represent the 13-category taxonomy required for this revision, nor CIA-hosted-document subtypes, attribution rules, contradictions, forbidden inferences, or section permissions.

### 2.6 Quotations, conflicts, limitations, and inferred claims

The prompt requires an Evidence Integrity Editor to compare quotations, chronology, and the claims ledger, and it requires competing explanations and contrary evidence in the audit. Nothing parses quotations back to source pages, verifies exact wording, enforces attribution, or stops a writer from flattening named interview testimony into fact. Conflicts and limitations survive only if the writer preserves them in the dossier, ledger, and prose.

Part 3’s current evidence atlases are a good local discipline: many entries contain exact claim, short quotation, evidence level, contradiction, source dependency, and “what this does not establish.” They are not a standardized input, have no schema, and are not referenced by the validator.

### 2.7 Citations, hyperlinks, and source CSVs

`codex_articles.validate()` checks article structure, URLs, one FAQ section with exactly five H3 questions, image/CTA markers, required related-article section, SEO fields, and `sources.csv`. The CSV must use `source_number,phrase,link`; each phrase must occur in the article and already be linked to the exact clean destination. The validator counts links and catches malformed, tracking, duplicate, absent, or mismatched anchors.

`white_rabbit.publishing.substack_source_linker` is the older publication helper. `read_sources()`, `replace_first_unlinked()`, and `insert_links()` can insert a source map’s first eligible exact phrase, while Markdown-to-DOCX/HTML routines preserve links and formatting. In the current Codex workflow, prose is expected to be linked before validation/export; export preserves linked input.

Neither system answers whether the linked source supports the sentence. Mechanical citation validity is explicitly separated from editorial source adequacy.

### 2.8 Series continuity

`codex_series.generate_prompt()` injects manifest state, earlier completed article/dossier/audit paths, `SERIES_PLAN.md`, `SERIES_CONTINUITY.md`, shared and part source inventories, required reader-state instructions, and a specific non-final ending pattern. It requires reading `SERIES_TIMELINE.md`, `SERIES_ENTITIES.md`, and `shared_research/master_dossier.md`.

`codex_series.validate()` reuses standalone validation, verifies series memory files/audit sections and prior completed articles, counts series/archive links separately, and detects duplicated paragraphs against earlier parts. It does not verify that a Part 2 proposition is accurately carried into Part 3 or that the Part 4 teaser is source-supported. Continuity is instruction plus memory, not claim-level dependency enforcement.

### 2.9 Editorial, voice, anti-AI, and visual controls

The prompt directly names Narrative Structure, Author Voice, Emphasis/Formatting, Visual Story, Evidence Integrity, and Anti-AI review passes. Permanent control files are:

- `docs/WHITE_RABBIT_STYLE.md`
- `docs/WHITE_RABBIT_AUTHOR_VOICE.md`
- `docs/WHITE_RABBIT_ANTI_AI_STYLE.md`
- `docs/WHITE_RABBIT_FORMAT_AND_VISUAL_STYLE.md`
- `docs/SEO_AND_PUBLISHING.md`

`white_rabbit.editorial_diagnostics.analyze_editorial_style()` provides non-blocking metrics and warnings for repetitive paragraph openings, explanatory scaffolds, performative caution, symmetric contrasts, uniform rhythm, emphasis density, repeated bolding, isolated fragments, list density, duplicated visuals, argumentative alt text, and generated-art substitution. These warnings are style heuristics, not evidence checks.

### 2.10 CLI, templates, and tests

Principal commands:

- `python codex_article.py new "TOPIC"`
- `python codex_article.py status|prompt|validate|export <slug>`
- `python codex_article.py series new|add|status|prompt|validate|export|set-url|set-finale|set-status ...`
- `python -m white_rabbit archive search "QUERY"`

Templates include `templates/ARTICLE_BRIEF_TEMPLATE.md` and the series templates/constants generated by `white_rabbit.codex_series`. The Part 3 `ARTICLE_BRIEF.md` still describes the original Vietnam/Brazil article and is now stale relative to the approved revision architecture; it must be updated in Phase 2 before prompt regeneration.

Relevant tests are `tests/test_codex_articles.py`, `tests/test_codex_series.py`, `tests/test_evidence_db.py`, `tests/test_linker.py`, and `tests/test_editorial_diagnostics.py`. They cover path safety, discovery/prompt refresh, mechanical validation, source reconciliation after prose edits, export preservation, series manifests/memory/links/duplication, evidence IDs/packets, link insertion, and advisory style diagnostics. There is no test for source permissions, claim-to-source sufficiency, quote-page verification, or evidence-category preservation.

## 3. CURRENT PART 3 INVENTORY

### 3.1 Article and control material

The root contains a stale `ARTICLE_BRIEF.md` and a generated `CODEX_PROMPT.md`. `article_workspace/` contains the current draft/final Markdown and DOCX; two claim-ledger CSVs; source links; article architecture; timeline, entity, personnel, logistics, pipeline, and dependency maps; thesis/intent/pattern/rebuttal tests; Southeast Asia, Contra, finance, Brazil, and enforcement reports; a master dossier; final targeted report; visual plan; 17 final source checks; and 17 source-specific evidence atlases in `article_workspace/evidence_atlas/`.

The current final article has 22 narrative/utility H2s. Its center of gravity is Laos, official Air America concessions, Contra investigations, the 1982 MOU, and Brazil. It does not contain the planned academy reappearance, IPA alumni network, Section 660 bridge, detailed Seal airframe story, or Moran transition.

`article_workspace/tools/build_part03_docx.py` is an article-specific document builder. It is presentation tooling, not a source or evidence validator.

### 3.2 Canonical source count

The Part 3 `sources/` tree contains 78 files:

- 58 PDF artifacts treated as the current canonical evidence documents;
- 6 HTML and 6 paired Markdown archive/finding-aid representations (discovery aids or alternate renderings, not 12 independent sources);
- 1 `NOT_DIGITIZED_LEADS.md` lead file;
- 7 acquisition metadata/manifests.

Accordingly, this audit reports **58 current Part 3 canonical source artifacts**. The source tree also contains 12 useful index/finding-aid representations and 8 metadata/lead files. This count excludes `shared_sources/`, derivatives, and duplicate representations from the canonical total.

### 3.3 Derivatives and parent mapping

`research/TMP_PROMOTION_MANIFEST.md` records the reconciliation promotion. It identifies 65 text derivatives and three JSON extraction indexes copied from `tmp/`; no non-reproducible research artifacts were found. The canonical originals remained under `sources/`.

`research/source_derivatives/part03_corpus/EXTRACTION_INDEX.json` maps corpus sidecars to source-relative paths, SHA-256 hashes, page counts, metadata, text counts, and low-text pages. `part03_targeted/SELECTED_EXTRACTION_INDEX.json` and its OCR copy map selected reports to their original PDFs and record extraction/OCR details. Most parent relationships are recoverable directly from the sidecar name. The notable normalization exceptions are documented in the indexes—for example the Agee derivative’s lower-case/hyphenated source name versus `Inside_the_Company_CIA_Diary_Philip_Agee.pdf`, and normalized filenames for Motta and Huggins.

The duplicate page-marked/OCR files in `part03_targeted/` are multiple derivatives of the same parents, not independent sources: Kerry’s report, the CIA OIG volumes, Huggins, the CIA–DOJ MOU, and Marchetti/Marks. Any future claim ledger must identify the parent PDF and treat sidecars only as locators.

### 3.4 Present research quality

The strongest existing controls are:

- `PART_03_CLAIM_LEDGER_V2.csv`: 60 claim rows with source/page, independent-source counts, official position, contrary evidence, documentary breaks, and strongest inference.
- `PART_03_SOURCE_DEPENDENCY_MAP.md`: explicitly prevents double-counting later books that reuse McCoy, Kerry, Blandón, or CIA denials.
- `FINAL_LAOS_IG_AUDIT.md`: correctly distinguishes the missing full IG attachment from the public Church Committee summary and its concessions.
- `FINAL_BUELL_SCHANCHE_VERDICT.md`, `FINAL_XIENG_KHOUANG_CHAIN.md`, and `FINAL_THAI_ROAD_CHAIN.md`: demonstrate appropriately narrow source adjudication.
- `FINAL_ALAN_HYDE_CHAIN.md`, `FINAL_JOHN_HULL_CHAIN.md`, and `FINAL_CONTRA_PATTERN_UPGRADES.md`: distinguish allegations, operational value, continued support, and enforcement anomalies.

The main weakness is not a lack of research effort. It is that the approved revision introduces a new document-dependent academy/alumni spine that the existing corpus was not designed to support.

## 4. EXISTING SOURCE INVENTORY

The table groups source families where individual records have the same provenance and evidentiary function. The count above remains artifact-level.

| Source | Filename | Type | Primary/Secondary | What It Proves | What It Does Not Prove | Current Use | Future Use | Quality Concerns |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| McCoy, *The Politics of Heroin in Southeast Asia* | `52_Alfred_McCoy___The_politics_of_heroin_in_Southeast_Asia.pdf` | Book / interviews / field investigation | Original published investigation; mixed firsthand and synthesis | Laos opium political economy; Ouane, Thao Ma, Ger Su Yang and village testimony; Air America/XKAT allegations; Mae Salong; 1971 endpoints | Institutional CIA authorization; continuous village-to-U.S. shipment; independent confirmation of every witness | Core Laos spine | Sections 4–8; endpoints; strongest-case/limitations | Many later authors depend on it; classify each underlying interview separately. |
| Don Schanche, *Mister Pop* | `Mister_Pop_Don_A_Schanche.pdf` | Book / firsthand-access biography | Original published book | Sweet-potato substitution failure; Buell cultivation advice/quote; medicine/use/surplus account; Buell refusal to fly opium | CIA admission; transcript of quote; institutional Air America drug policy | Final Buell verdict | Section 4 H3s | Schanche’s transport explanation is explicitly speculative. |
| Church Committee, Air America chapter | `FOREIGN AND MILITARY INTELLIGENCE - BOOK 1.pdf` | Congressional investigative material | Primary official investigation summary | 1972 inquiry scope; occasional carriage; incomplete loading control; suspected employees/allies; war priority/non-suppression | Full IG file; no carriage; no allied trafficking; every load knowingly piloted | Official denial/concessions | Sections 5–6 and rebuttal | Summarizes missing IG attachment; quotation scope must remain exact. |
| CIA IG transmittal/ROI | `REPORT OF INVESTIGATION - Vol 1.pdf`; `Vol 2.pdf` | Official CIA OIG reports (Contra) | Primary official investigation | Contractor relationships, traces, knowledge dates, referrals, Hyde/SETCO/Vortex/Hull/Morales case details; reporting framework | Truth of every allegation; universal protection policy | Contra and enforcement analysis | Sections 13–14 and rebuttal | Official self-investigation; allegations and findings must remain distinct. |
| Kerry Committee report | `Drugs Law Enforcement and Foreign Policy.pdf` | Senate subcommittee report | Primary official investigation | Contra-drug findings; contractors; Morales; Hull; Bueso; Seal political interference; BCCI inquiry limits | CIA-directed drug cartel; truth of every witness; complete exhibit archive | Core Contra findings | Sections 12–14 | Published report is local; underlying exhibits/depositions are incomplete. |
| CIA–DOJ MOU | `DOJ-CIA Memorandum of Understanding Relating.pdf` | Government agreement | Primary government record | Reporting procedures and the later-documented nonemployee/Title 21 gap | Intent to protect trafficking; non-reporting in every case | MOU blind-spot section | Sections 10 and 14 | OCR quality; legal history requires OIG context. |
| Leeker C-123 study/records | `Air_America_Fairchild_C-123_Providers_Leeker_TTU.pdf` | Archival aircraft history using company records | High-quality documentary synthesis | AID-439-342 assignments; mixed missions; Long Tieng/Vientiane/Udorn operations | Seal airframe identity; narcotics cargo | Air America operational map | Section 6; infrastructure | Useful record roadmap, not a full contract/invoice archive. |
| Marchetti and Marks | `The-CIA-and-the-Cult-of-Intelligence.pdf` | Former-insider published account | Firsthand/secondary mixed | AID/Air America financial relationship; insider account of occasional carriage; CIA publication dispute | Original contract total; policy/order; universal practice | Corroborates McCoy/official record | Sections 5–6, source controversy | Attribute; CIA review correspondence does not convert book claims into findings. |
| Scott, *American War Machine* | `American_War_Machine_-_Peter_Dale_Scott.pdf` | Scholarly synthesis | Secondary | System comparison, PARU/Bill Lair context, Shackley/XKAT lead, finance/network synthesis | Independent confirmation where he relies on McCoy; person-level IPA link | Cross-source map | Select context only | High dependency risk; reopen underlying sources. |
| Scott/Marshall, *Cocaine Politics* | long `cocaine-politics...pdf` | Scholarly synthesis | Secondary | Contra, Noriega, BCCI, Central American cases and leads | Independent proof where based on Kerry/OIG/press; CIA-controlled drug funds | Contra/finance atlas | Limited context | Prefer government/court records; avoid multiplying a shared source chain. |
| Gary Webb, *Dark Alliance* | `Dark_Alliance.pdf` | Investigative book | Published attributed investigation | Blandón/Meneses/Ross narrative, witnesses, leads | National crack causation; CIA protection finding | Adversarial comparison | Narrowly used with OIG | Official reviews confirm some facts and reject broader framing. |
| Agee, *Inside the Company* | `Inside_the_Company_CIA_Diary_Philip_Agee.pdf` | Former-officer retrospective | Named firsthand account reconstructed later | AID Public Safety cover, police liaison, spotting/recruitment practice; named cases | Every personnel identification; narcotics pipeline | Cover/access thesis | Brief Part 2 callback or network context | Reconstructed diary; requires corroboration for individuals. |
| Huggins, *Political Policing* | two `Political Policing...pdf` variants | Scholarly monograph | Secondary | OPS/access/repression synthesis | Direct proof of all named cover/recruitment claims | Background | Limited; stronger sources exist | One extraction incomplete; duplicate editions must not be double-counted. |
| Schrader, *Badges Without Borders* | `badges-without-borders...pdf` | Scholarly monograph | Secondary | Global police-assistance architecture, counterinsurgency, IPA/OPS context | New narcotics facts; specific alumni chain without cited primary record | Institutional context | Sections 8–10 if underlying record reopened | Canonical edition quality acceptable; use footnotes to escalate. |
| Motta, “Modernizing Repression” | `modernizing repression.pdf` | Scholarly article | Secondary synthesis with archival research | Brazil OPS equipment/access, Lingo/Mitrione/Brown, repression context | Direct CIA recruitment order; completed drug chain; U.S. command of torture | Brazil spine | Condensed Section 15 | Some important CIA-recruitment language is unfootnoted synthesis. |
| Brazilian political-policing books | `Book_Political_Policing_the_US_and_Latin.pdf`; `Political...pdf` | Scholarship | Secondary | OPS and Latin American policing context | Named drug route; CIA command/control | Brazil/OPS context | Condense | Editions/duplicate lineage require care. |
| MSU Vietnam project reports (12) | `msu_vietnam_project/documents/*.pdf` | Contractor/program reports | Primary program records | VBI reorganization; identification/fingerprints; communications; Civil Guard; participant program; transition to USOM | CIA access to databases; narcotics link; later political use in every case | Original Part 3 prototype | Minimal Part 2/early-file callback only | Strong primary evidence, but revision should avoid reopening a long Vietnam detour. |
| MSU finding aids/research guide | `msu_vietnam_project/finding_aids/*` | Archive aids | Primary archive metadata | Collection topology and not-digitized leads | Substantive claim itself | Source escalation | Phase 2 lead only | HTML/MD/PDF variants are not independent evidence. |
| Brazil policy/coup records, 1962–64 (18) | `national_security_archive_brazil/documents/1962*` through `1964*`; PFIAB release | White House/NSC/State/CIA records | Primary government records | Aid leverage; covert political action; coup contingency; Gordon arms/POL request; U.S. objectives | OPS under CIA command; completed narcotics pipeline | Brazil political-action chain | Condensed Section 15 | NSA index pages are curatorial aids; classify each originating agency correctly. |
| Brazil abuse records, 1970–73 (5) | `1970-10-07...` through `1973-05-08...` | State/embassy records | Primary government records | U.S. knowledge of DEOPS/OBAN abuse, death squads, torture and executions | U.S. authorship of abuse; narcotics protection chain | Brazil repression context | One compact comparison paragraph or cut | Contemporary reporting, not adjudication of every allegation. |
| Brazilian Truth Commission, vols. 1–3 | `volume_1_digital.pdf` etc. | Official national commission | Official investigative synthesis | SNI/DOPS/OBAN/DOI-CODI and dictatorship abuse | Direct U.S. operational command; drug pipeline | Brazil institutional history | Background, not center | Portuguese; page-level claim control required. |
| CIA/AID Brazil telegram | `Telegram From the Department of State to the Embassy in Brazil.pdf` | State record | Primary | Specific diplomatic/program context | Wider CIA/OPS command claim | Targeted support | Use only if it serves retained Brazil paragraph | Exact scope must be restated from document. |
| NSA Brazil index pages | `national_security_archive_brazil/indexes/*.{html,md}` | Curatorial pages | Secondary discovery aids | Provenance, titles, release context | Underlying claims by themselves | Acquisition metadata | Phase 2 navigation | Paired HTML/MD files are duplicates. |

## 5. NEW EVIDENCE COVERAGE MATRIX

Evidence labels below use the required expanded taxonomy. A row marked “partial” means at least one major proposition is usable, not that the whole requested package is complete.

| Claim / Connection | Already Supported? | Existing Source | Additional Source Needed? | Preferred Source | Evidence Level | Planned Section | Critical Caveat |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A. Buell’s sweet-potato substitution failed | Yes | Schanche PDF 142 / printed 131 | No for fact; useful archival corroboration optional | Buell/USAID field report | PUBLISHED ATTRIBUTED ACCOUNT / CORROBORATED ACCOUNT | 4 | A biographer with field access, not a program evaluation. |
| A. Buell cultivation advice and quote | Yes | Schanche PDF 267 / printed 242; McCoy PDF 216 | Interview notes desirable | Schanche notes/Buell papers | PUBLISHED ATTRIBUTED ACCOUNT | 4 | McCoy repeats Schanche; not independent and not a transcript. |
| A. Medicine reduced local use and left greater surplus | Partial | Schanche PDF 267; McCoy PDF 216 | Yes for measured effect | Village/USAID health and crop records | STRONG INFERENCE | 4 | “More marketable surplus” is inference, not quantified causation. |
| A. Phou Vieng/Blea Vu/ponies/counterfeit kip/buyer replacement | Partial/unverified at subclaim level | Schanche/McCoy chain; not fully controlled in present final report | Yes | Full page-specific Schanche/Buell source memo and underlying notes | PUBLISHED ATTRIBUTED ACCOUNT | 4 | Schanche’s CIA replacement-buyer theory must remain his inference. |
| B. Officers bought village opium at ~$60 vs $40–50, used bamboo/ponies, repeated trips | Yes | McCoy PDF 233–235; Ger Su Yang and village accounts | Underlying interview notes desirable | McCoy papers/audio/notes | NAMED FIRSTHAND INTERVIEW | 5 | Named interview testimony, not official finding. |
| B. 1969–70 helicopter insertion/radio pickup/Long Tieng | Yes | McCoy PDF 233–235; exact Ger Su Yang quotations verified in local text | Underlying notes desirable | McCoy field notes | NAMED FIRSTHAND INTERVIEW / CORROBORATED ACCOUNT | 5 | “American helicopters/pilots” does not by itself establish owner, order, or knowing pilot participation. |
| C. Ouane: Dakotas, floats, Gulf of Siam, $35,000/month to Phoumi | Yes as testimony | McCoy PDF 210–211; interview note citations PDF 343–344 | Yes for independent corroboration | McCoy notes; Lao records; Harper & Row/CIA correspondence | NAMED FIRSTHAND INTERVIEW | 6 | Separate rank/role, claimed method, and claimed revenue; no manifest or audit. |
| D. Thao Ma bribe offer, two C-47s, refusal/warning | Yes as testimony | McCoy PDF 236–238; interview citations PDF 351 | Yes for independent corroboration | Thao Ma interview notes; Lao Air Force/embassy records | NAMED FIRSTHAND INTERVIEW | 6 | Do not convert interview narrative into investigative finding. |
| E. XKAT creation, two C-47s, Long Tieng–Vientiane, U.S. assistance | Yes, bounded | McCoy PDF 225; Shackley lead via Scott; CIA-held congressional/press item | Yes for documentary proof | Corporate registry; AID grant/loan; aircraft-transfer records; Shackley original | CORROBORATED ACCOUNT | 6 | Lo Kham Thy was president; distinguish Vang Pao benefit/control. |
| E. XKAT carried opium/heroin; USAID expected opium commerce | Weak | Anonymous former USAID official and Hmong sources in McCoy PDF 225 | Yes | Named interviews, manifests, contemporaneous AID/CIA records | PLAUSIBLE CONNECTION | 6 | Creation/support is not cargo proof; CIA-hosted repeats are not CIA findings. |
| F. AID materially sustained Air America aviation | Yes | Leeker pp. 9, 15, 21–33; Marchetti/Marks; McCoy | Original contract/payment chain needed for exact total | AID-439-342/-713 contracts, modifications, invoices | DOCUMENTED FACT for contract operations; CORROBORATED ACCOUNT for >$83m | 6 | Never say AID purchased drug flights. |
| F. Occasional opium carriage and loading-control limits | Yes | Church Committee PDF 14–15; official IG summary | Full IG attachment desirable | CIA-RDP74B00415R000400020027-3 attachment/working papers | OFFICIAL INVESTIGATIVE FINDING | 6 / 17 | No policy or knowing U.S.-pilot finding. |
| G. Mae Salong Seabee/ARD road, market/truck expansion | Yes | McCoy PDF 282; FRUS leads; 1975 field study summarized in `FINAL_THAI_ROAD_CHAIN.md` | Exact project file preferred | USAID ARD project authorization/completion report | CORROBORATED ACCOUNT / STRONG INFERENCE | 6 | Commercial effect is documented; drug cargo on road remains attributed. |
| G. KMT/opium tonnage, caravans, labs | Partial | McCoy regional chapters; contemporary congressional/intelligence leads | Yes for exact numbers and CIA lab assessment | Original CIA/BNDD/State assessment and Thai records | SECONDARY SCHOLARLY SYNTHESIS / PUBLISHED ATTRIBUTED ACCOUNT | 6 | Never map regional annual tonnage onto one road or caravan. |
| H. 1971 Vientiane–New York, Fort Monmouth, Sopsaisana cases | Partial | McCoy PDF 197, 276–280; named quantities and Double U-O Globe | Yes | Customs/BNDD case files; French customs/diplomatic record; court/docket records | PUBLISHED ATTRIBUTED ACCOUNT | 7 | Seizures can be stated as McCoy’s sourced report; origin/brand/network needs primary confirmation. |
| H. Regional Laos/Golden Triangle to U.S. endpoint | Yes | FRUS docs 220/225 summarized in `FINAL_US_ENDPOINT_CHAIN.md`; McCoy | No for broad connection | Official fact sheets/CIA study already identified | PRIMARY GOVERNMENT RECORD / DOCUMENTED FACT | 7 | Does not trace one Hmong sack or quantify CIA-allied share. |
| I. FY1974–75 Laos narcotics program and 163 military police | No | No matching canonical/shared extraction found | Yes—high priority | Embassy/State/AID country narcotics-control program record | DOCUMENTARY GAP | 8 | This document is the intended academy re-entry hinge. |
| J. IPA Narcotics Orientation Course No. 8, 27 students | No | No original IPA publication in local set | Yes—high priority | Original IPA/USAID bulletin or graduation program dated 1974-12-20 | DOCUMENTARY GAP | 8 | Do not build roster/curriculum from a secondary summary. |
| K. FBN recurring teaching relationship, FY1966–68 | No | Only incidental shared reference | Yes | Treasury/FBN annual reports FY1966, FY1967, FY1968 | DOCUMENTARY GAP | 9 | Separate primary annual-report facts from historian interpretation. |
| L. 3,932 graduates, 73 countries, 13 chiefs, “valuable contacts” | No | No located issuing report | Yes | Exact DOJ/Justice/government report with title/date/pages | DOCUMENTARY GAP | 9 | “Contact” is not “asset.” |
| M. Trần Minh Công career and IPA attendance | No | Not located | Yes | RVN/IPA roster, academy record, oral history, scholarly biography | DOCUMENTARY GAP | 9 | Institutional/geographic significance only; no narcotics complicity claim. |
| N. Hang Doua academy/data training and Long Tieng role | No | Not located | Yes | Lao Police Academy/USAID files, oral history, official biography | DOCUMENTARY GAP | 9 | Do not call him a Washington IPA graduate without proof. |
| O. CIA–Thai police/BPP/PARU and Laos role | Partial at institutional level | Scott/McCoy synthesis; existing atlas; shared CIA histories may provide leads | Yes for primary upgrade | Bill Lair oral history; CIA Laos/Thailand histories; Thai/BPP records | SECONDARY SCHOLARLY SYNTHESIS / CORROBORATED ACCOUNT | 9 | General PARU role does not prove an academy link. |
| O. Named IPA graduate → BPP/PARU → Long Tieng | No | No roster match | Yes | IPA rosters cross-matched to BPP/PARU personnel records | DOCUMENTARY GAP | 9 | Explicitly not established. |
| P. Miguel Nazar Haro nine-bucket chain | No | Not located in current Part 3 corpus | Yes | IPA attendance file; DFS career records; CIA/DOJ/DEA/court/testimony records | DOCUMENTARY GAP | 9 | Attendance, liaison, prosecution sensitivity, allegation, and adjudication must remain separate. |
| Q. Section 660 prohibition and narcotics exception | Yes in shared collection, not yet Part 3-controlled | `STATUTE-88-Pg1795 (1).pdf`; congressional records; GAO `id-76-5`/`nsiad-92-118` | Targeted page memo needed, no bulk acquisition necessarily | Statute, 1973–74 debate, GAO interpretation | PRIMARY GOVERNMENT RECORD | 10 | Concise bridge only; never “DEA replaced OPS.” |
| R. Former Air America personnel in Contra logistics | Partial/insufficient | General Contra/aviation sources; no completed person-employment chain | Yes | Employment files, OIG/committee records, Air America roster | DOCUMENTARY GAP / PLAUSIBLE CONNECTION | 11 | Individual continuity is not corporate continuity. |
| S. Barry Seal DEA sting and political compromise | Yes | Kerry PDF 26, 66–67; current ledger | Full DEA/NSC file desirable for granular flight/camera/cargo details | DEA operation file, congressional exhibits | OFFICIAL INVESTIGATIVE FINDING | 12 | Does not require or prove that Seal worked for CIA. |
| S. Seal C-123 equals October 1986 Contra C-123 | No | No tail/serial/ownership chain in current corpus | Yes—mandatory | FAA registration history; USAF/manufacturer serial; sale/lease/insurance/maintenance records; shootdown report | DOCUMENTARY GAP | 12 | Heading “same aircraft” is prohibited unless every identity field reconciles. |
| T. CIA denial/file search concerning Seal/Mena | No scoped record | Current sources mention denials but no controlled briefing/search document | Yes | CIA briefing memorandum/file-search response with scope and date | DOCUMENTARY GAP | 17 | “No file,” “no relationship,” and “no Mena operation” are different propositions. |
| U. Morales, SETCO, Hull, Vortex, Hyde, MOU, Zavala, Meneses/Blandón, Fiers/Southern Front, Bueso | Yes, uneven by actor | Kerry; CIA OIG I–II; MOU; Webb; current final source checks | Some underlying case files/exhibits desirable | Customs/DEA/FBI/court/contracts and payment records | OFFICIAL INVESTIGATIVE FINDING / CORROBORATED ACCOUNT | 13–14 | Do not merge actors or convert enforcement conflict into deliberate trafficking. |
| U. Exact $806,452.32 contractor total | Not independently reconstructed | Secondary/current report assertions only | Yes | NHAO/State/CIA contractor vouchers and government payment schedules | DOCUMENTARY GAP | 13 | Use “more than $800,000” only if official component totals reconcile; otherwise omit amount. |
| V. BCCI covert/narcotics/intelligence overlap | Partial | Kerry PDF 12, 46–47, 64; *Cocaine Politics*; BCCI leads | Yes for transaction-specific inclusion | Senate BCCI report, bank/court records, named transfer records | OFFICIAL ALLEGATION / SECONDARY SYNTHESIS | Rabbit hole, not main narrative | Current record does not establish a CIA-controlled drug-money account. |
| W. Brazil aid leverage/covert action/OPS modernization/repression | Yes | 1962–64 primary records; PFIAB p. 6; Motta pp. 7–20; 1970–73 State records; truth commission | Select project records useful, not required for comparison | USAID project files; Brazilian archives | PRIMARY GOVERNMENT RECORD / STRONG INFERENCE | 15 | Parallel and mutually reinforcing does not equal unified command. |
| W. Brazil completed drug pipeline | No | Current audit expressly finds a break | Yes, but nonessential to revised thesis | Named trafficker/protection/route/finance/U.S. endpoint records | DOCUMENTARY GAP | 15 | State the break; do not manufacture closure. |
| X. Héctor Romero Moran/Charquero → IPA → Special Brigade → Mitrione | No | No matching local record; absent from Part 4 research | Yes—high priority for proposed ending | IPA roster; DIA record; Mitrione report; Uruguayan records; contemporary allegation source | DOCUMENTARY GAP | 18 | Any torture allegation must remain attributed and independently tested. |

### Airframe identity table required for Phase 2

| Attribute | Seal period | Contra period | Present source | Match? | Confidence |
| --- | --- | --- | --- | --- | --- |
| Tail/registration | Not established in canonical record | Not established in canonical record | None adequate | Unknown | None |
| USAF serial | Not established | Not established | None adequate | Unknown | None |
| Manufacturer serial | Not established | Not established | None adequate | Unknown | None |
| Nickname “The Fat Lady” | Published in secondary accounts, not controlled here | Not established as shootdown aircraft nickname | Secondary leads only | Unknown | Low |
| Owner | Not reconstructed | Not reconstructed | No chain | Unknown | None |
| Operator | DEA-cooperating Seal operation is supported | Contra resupply operation/crew is separately supported | Kerry/official reporting, but no identity bridge | Events match only at aircraft type | High that both events occurred; none for identity |
| Dates | 1984 sting | 1986-10-05 shootdown | Separate official/public records | Chronology possible | High |

Present verdict: **same-airframe identity not verified; narrative unusable in that form.**

## 6. SOURCE GAP REPORT

### Tier 1 — must acquire before rewrite

These are source packages, not every individual page.

| # | Source | Why needed | Claims supported | Preferred version | Likely location / URL if known | Priority | Article section |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | FY1974–75 Laos narcotics-control program record | Creates the documentary bridge from Lao military police to U.S./IPA/DEA training | Provost Marshal, 163 personnel, academy, seven U.S. trainees, trafficking findings | Original Embassy/State/AID record with annexes | NARA RG 59/RG 286; State FOIA/FRUS; USAID DEC | Critical | 8 |
| 2 | IPA Narcotics Orientation Course No. 8 publication | Proves date, cohort, countries, curriculum, and Laos/Thailand participation | 1974-12-20, 27 students, commencement and transshipment language | Original IPA/USAID bulletin, program, or newsletter | NARA RG 286; USAID historical records; university/government library catalog | Critical | 8 |
| 3 | FY1966–68 Treasury/FBN annual reports | Establishes recurring FBN presence inside IPA without relying on a historian | Two-week/Spanish course, 19 officers, senior-officer lectures, methods | Original Treasury/FBN reports | HathiTrust/GovInfo/NARA/Treasury library | Critical | 9 |
| 4 | Exact DOJ/Justice IPA alumni report | Supplies the network’s scale and government’s own “valuable contacts” wording | 3,932, 73 countries, 13 chiefs, overseas contacts | Complete issuing report with cover/date/pages | DOJ/LEAA/BNDD archive; GovInfo; NARA | Critical | 9 |
| 5 | IPA/OPS participant rosters and course records | Enables person-level alumni claims and prevents name conflation | Trần Minh Công, Hang Doua, Nazar Haro, Thai/Lao participants | Original rosters, applications, completion lists | NARA RG 286; USAID FOIA; National Archives College Park | Critical | 8–9 |
| 6 | PARU/BPP personnel and training records | Tests the named IPA→PARU→Laos hypothesis | Bill Lair, PARU creation, Laos insertion, Long Tieng, roster match | CIA/Thai primary records and official oral histories | CIA Reading Room; AFHRA; Library of Congress oral histories; Thai archives | Critical | 9 |
| 7 | Seal/Contra C-123 identity packet | Determines whether the article may say “same airplane” | Registration, serials, owners/operators, transfers, shootdown identity | FAA registry history, USAF/manufacturer records, sale/lease/maintenance documents, official shootdown report | FAA historical registry; NTSB/USAF; Iran-Contra collections; National Security Archive | Critical | 12 |
| 8 | CIA Seal/Mena briefing/file-search record | Defines the denial’s actual scope | No file/relationship/operation and search limits | Complete CIA memorandum/briefing with attachments | CIA Reading Room/CREST; congressional Iran-Contra files | High | 17 |
| 9 | Héctor Romero Moran primary packet | Required for the intended Part 4 bridge | Full identity, IPA status, Special Brigade role, Mitrione report, DIA record, allegation provenance | IPA roster + DIA/State/Uruguayan records + original allegation | NARA; DIA FOIA; State/NSA EBB 324; Uruguayan archives | Critical | 18 |
| 10 | Named 1971 seizure records | Upgrades three endpoints from McCoy-attributed accounts | Fort Monmouth, Vientiane–New York, Sopsaisana/Orly, quantity/brand/destination | Customs/BNDD/court and French diplomatic/customs files | NARA/DEA FOIA; PACER/archive; French diplomatic archives | High | 7 |
| 11 | Full 1972 CIA Laos IG investigation | Tests the method behind official denial/concessions | Interview universe, manifests, agents/allies, non-suppression, recommendations | Missing attachment, interview memos, exhibits, field notes | CIA FOIA for CIA-RDP74B00415R000400020027-3 and related job/file | High | 6 / 17 |
| 12 | Air America/AID contracts and payment records | Controls the >$83m claim and the infrastructure claim | Contract numbers, modifications, aircraft assignments, payments | Signed contracts, invoices, Bisson reels/company records | NARA RG 286; UT Dallas Air America archive; Texas Tech Vietnam Center | High | 6 |
| 13 | XKAT formation/aircraft record | Separates documented support from alleged cargo | Incorporation, ownership, U.S. aid, aircraft transfers, routes | Lao company file, AID grant/loan, aircraft registrations, Shackley original | USAID/NARA; CIA Reading Room; Air America archives | High | 6 |
| 14 | Contra contractor payment records | Tests the exact $806,452.32 number | SETCO/Vortex/other government-funded contractor totals | Vouchers/contracts/audit schedules | State/NHAO records; Kerry exhibits; CIA OIG working papers | High | 13 |

**Tier 1 count: 14 source packages.**

### Tier 2 — must have because they contain unique testimony

| # | Source | Why needed | Claims supported | Preferred version | Likely location / URL if known | Priority | Article section |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | McCoy interview-note collection | Audits the unique Ouane, Thao Ma, Ger Su Yang, village, Hmong, and USAID testimony as a single archival package | A–E and named village/official quotations | Original notebooks, recordings, transcripts, correspondence | University of Wisconsin/McCoy papers or publisher archive; finding aid to confirm | Critical | 4–6 |
| 2 | Harper & Row/McCoy/CIA correspondence and review materials | Shows precisely what CIA challenged and what source material publisher reviewed | Ouane notes, accuracy dispute, publication history | Original correspondence and legal/editorial review | McCoy/publisher papers; CIA Reading Room | High | 6 / 17 |
| 3 | Don Schanche papers/interviews with Buell | Controls the quotation and named village/buyer details | Crop substitution, cultivation quote, medicine/surplus, buyer-change theory | Notes, correspondence, interview transcript | University/manuscript archive; publisher records | High | 4 |
| 4 | Bill Lair oral history/interview | Primary-upgrades PARU development and Laos operations | BPP/PARU, insertion, training, communications | Full audio/transcript from preserving institution | Air Force/Library of Congress/CIA-history collections | High | 9 |
| 5 | Trần Minh Công oral history/biographical source | Establishes career chronology without narcotics insinuation | Da Nang/Saigon roles, 1969 course, academy command | University oral history or official RVN biography | Vietnam archive/university special collections | Medium | 9 |
| 6 | Hang Doua oral/biographical record | Tests academy, Malaysia, Long Tieng, and later training claims | N | Original interview/official file | Lao diaspora archive, USAID/CIA records, university collections | High | 9 |
| 7 | Miguel Nazar Haro testimony/proceedings corpus | Separates allegation source and adjudication from CIA liaison/career | P buckets 3–9 | Sworn testimony, indictment/docket, official correspondence | U.S./Mexican court and congressional archives; CIA/DOJ/DEA FOIA | High | 9 |
| 8 | Former Air America/Contra personnel records or oral histories | Tests individual employment continuity | Hasenfus, Cooper, other named alumni | Employment file plus sworn/recorded testimony | Air America Association archive; Iran-Contra depositions; OIG files | High | 11 |

**Tier 2 count: 8 source packages.** Existing copies of McCoy and Schanche remain usable; this tier seeks the unique underlying testimony and records needed for unusually consequential claims.

### Tier 3 — should replace mirror/discovery sources

| Source | Why needed | Claims supported | Preferred version | Likely location / URL if known | Priority | Article section |
| --- | --- | --- | --- | --- | --- | --- |
| Canonical editions behind AnyFlip/akha.org/abuse-drug/dokumen.pub/Chooper’s Guide leads | Prevents mirror provenance from being mistaken for authority | Any claim currently discovered through a weak host | Publisher, archive, government, or court copy | Issuer catalog, Internet Archive controlled scan, library database | Medium | Any |
| Original Shackley text behind Scott’s note | Removes one level of citation dependency | XKAT formation/support | First edition/memoir page or archival record | Library/publisher copy | High | 6 |
| Original Mae Salong field study and CIA/BNDD assessment | Controls road/lab/tonnage claims | Road effects and labs | Journal scan + declassified assessment | Journal of the Siam Society; CIA Reading Room/NARA | High | 6 |
| Original newspaper/case records behind McCoy’s seizure notes | Replaces a single book’s summary | 1971 endpoints | Contemporary clipping from newspaper archive plus government file | Newspaper archive/Customs record | High | 7 |
| Official BCCI reports and court/bank records | Replaces secondary finance synthesis | Narrow context only | Senate report, court exhibits, bank records | GovInfo/Senate archive/court collection | Medium | Rabbit hole |
| Original Brazilian documents referenced by NSA index pages | Preserves issuing-agency classification | Brazil policy/repression | Already-downloaded PDFs where present; acquire only missing item | National Security Archive/NARA | Medium | 15 |

### Tier 4 — interesting but too weak or nonessential

| Source / lead | Why nonessential now | Possible use | Classification |
| --- | --- | --- | --- |
| Broad Mena conspiracy literature without a specific aircraft or document target | Encourages guilt by association and cannot repair airframe identity | Later source-discovery pass only | FUTURE RABBIT HOLE |
| General BCCI/Nugan Hand expansion | Finance tangent overwhelms the article and lacks transaction-level CIA/drug commingling | One sentence at most if needed | OMIT / FUTURE RABBIT HOLE |
| Brazil Huanchaca/Mingolla/Condor cocaine leads without case files | Current source chain cannot connect OPS/CIA-backed structures to a protected U.S.-bound route | Separate future investigation | FUTURE RABBIT HOLE |
| Complete Kerry exhibit hunt without a named claim target | High cost and likely repetition | Acquire only exhibits tied to a retained claim | DEFER |
| Additional secondary repetitions of McCoy | Do not add independent witnesses | Bibliographic context only | OMIT |
| Afghanistan/Pakistan comparison | Large new theater, weak USAID relevance, substantial BCCI/opium complexity | Future comparative article | OMIT |

## 7. PART 2 → PART 3 CONTINUITY

Part 2’s authoritative trail is `output/article.md`, `output/research_dossier.md`, `output/audit.md`, and the cited official records in `shared_sources/`: the CIA-held Pike reproduction, Rockefeller Commission, Family Jewels, and CIA-RDP80B01083A000100120014-7. Part 3 should use one compact callback, not repeat Part 2’s reveal.

| Part 2 fact | Source | Evidence level | How Part 3 may refer to it | What Part 3 must not exaggerate |
| --- | --- | --- | --- | --- |
| OPS/IPA provided the overt route; IPS was a CIA proprietary follow-on school | Pike reproduction, reproduced report p. 89; Rockefeller Commission printed p. 235/local PDF 12 | OFFICIAL INVESTIGATIVE FINDING | “Part 2 found a concealed CIA junction behind the overt academy.” | Not every IPA student attended IPS; OPS and CIA were not institutionally identical. |
| A 14-week OPS course could be followed by four weeks at IPS | Pike reproduction | OFFICIAL INVESTIGATIVE FINDING | Establish the mechanism before showing later narcotics courses/alumni | Do not apply sequence universally or to a named alumnus without his course record. |
| Students generally did not know IPS was CIA-controlled | Pike; Rockefeller | OFFICIAL INVESTIGATIVE FINDING | Explain concealment/compartmentation in one clause | Individual knowledge cannot be ruled out. |
| Instructors assessed pro-American orientation; lists and biographies went to CIA components for operational use | Pike | OFFICIAL INVESTIGATIVE FINDING | “The academy produced information and candidates as well as instruction.” | Assessment/spotting is not completed recruitment. |
| CIA Police Group maintained daily OPS/IPA liaison and participant-information exchange | Family Jewels PDF 607/original 00597 | PRIMARY GOVERNMENT RECORD | Direct factual callback supporting network/access thesis | Daily liaison does not mean CIA directed every course or foreign graduate. |
| Police Group placed CIA-sponsored participants and arranged briefings/tours | Family Jewels 607–608 | PRIMARY GOVERNMENT RECORD | Allows Part 3 to ask what specific narcotics courses and alumni did | CIA sponsorship of some participants cannot be generalized to all students in a roster. |
| Selected people received additional briefings/training | Family Jewels 608 | PRIMARY GOVERNMENT RECORD | Supports the need to inspect course-specific and person-specific records | Redacted activity cannot be filled with speculation. |
| The seventh Terrorist Technical Investigations Course had a bounded 26-person cohort, AID/CIA/foreign funding, IPA phase, and CIA-facility phase | Family Jewels 610–612 | PRIMARY GOVERNMENT RECORD | A model for how to describe one specialist course precisely; contrast with Course No. 8 only after obtaining its record | Do not apply explosives/booby-trap content to general IPA or narcotics curricula. |
| Roughly 5,000 officers received CIA school/special-course training over 20+ years | Pike; Rockefeller | OFFICIAL INVESTIGATIVE FINDING, approximate | Background scale if essential | Not the same population as 3,932 IPA graduates; do not combine counts. |
| A redacted CIA employee served more than ten years as OPS director | Family Jewels 105–106 | PRIMARY GOVERNMENT RECORD | Usually omit; if used, say redacted | Do not identify the person as Byron Engle without unredacted proof. |
| CIA/USAID relationship boundaries were adjacent/compartmented, not simple identity | Combined record | CORROBORATED ACCOUNT / STRONG INFERENCE | Preserve distinct institutional actors throughout | “USAID was CIA” and “CIA ran every OPS program” are unsupported. |

Recommended callback logic: Part 2 established an overt academy with concealed CIA junctions, daily liaison, participant assessment, and course-specific covert augmentation. Part 3 then asks what happened when narcotics training and alumni relationships appeared in the same transnational police network. The new claim must arise from new documents, not from re-labeling all graduates as intelligence assets.

## 8. PART 3 → PART 4 CONTINUITY

Part 4’s authoritative current scope is Uruguay, 1969–70, and the provenance of claims that Dan Mitrione taught torture. It establishes that Uruguayan torture predated Mitrione; the Otero and Hevia allegations have different provenance; the famous quotation/live-subject story is not established fact; OPS advisers participated in kidnapping-response operations; and the August 9, 1970 State cable proposed raising a death threat against prisoners.

The proposed Moran bridge is not in the current Part 4 article, dossier, sources, or series memory. A repository-wide search found no relevant Héctor Romero Moran/Moran Charquero source. Part 3 cannot currently end on him as fact.

The responsible bridge, after acquisition, would be:

1. Establish Moran’s full identity and IPA attendance from a roster.
2. Establish his Montevideo Special Brigade role/title from Uruguayan or U.S. records.
3. Establish what Mitrione reported about him from the actual report.
4. Identify the DIA record and its scope.
5. Trace the contemporaneous torture allegation to its original speaker/publication and state whether it was corroborated.
6. End with the evidentiary question Part 4 actually answers: what can be proved about Mitrione personally, and what institutional responsibility remains when the famous personal allegation is uncertain?

If the Moran packet is not acquired, the fallback final transition should be institutional rather than biographical: the academy created cross-border relationships and specialist networks; the next article tests the most famous claim attached to one OPS adviser inside an abusive Uruguayan police system. That bridge is supportable now, but it is less specific than the approved target.

Part 3 must not spoil Part 4’s strongest finding—the State death-threat cable—or prejudge the torture allegation. It may identify Mitrione, Uruguay, the Special Brigade only if sourced, and the unresolved difference between capacity, operational cooperation, and personal instruction.

## 9. CURRENT → PROPOSED ARTICLE STRUCTURE

| Current section | Recommendation | Proposed section | Reason |
| --- | --- | --- | --- |
| THE DENIAL | KEEP BUT REWRITE | 1. THE DENIAL THAT OPENED THE DOOR | Retain official denial/concessions as the framing problem, but do not exhaust rebuttals before the evidence. |
| FOLLOW THE PIPELINE | KEEP BUT EXPAND | 2. FOLLOW THE PIPELINES | Define physical, personnel, training, finance, and enforcement pipelines; plural avoids claiming one command chain. |
| BEFORE THE DRUGS CAME THE FILES | KEEP BUT CONDENSE | 3. BEFORE THE DRUGS CAME THE FILES | Use Part 2 callback and minimal Vietnam institutional precedent; do not reopen the old article’s full MSU architecture. |
| WHAT THE ACCESS BOUGHT | MERGE | 3 and 9 | Access belongs first to the Part 2 callback, then to alumni/network consequences. |
| THE GOLDEN TRIANGLE | KEEP BUT EXPAND/SPLIT | 4. THE GOLDEN TRIANGLE WAS ALREADY THERE | Establish preexisting economy; add Buell/Schanche H3s and buyer-change limit. |
| THE ARMY THAT GREW WHERE OPIUM GREW | MERGE/MOVE | 4–5 | Integrate Vang Pao/proxy economy with actual collection mechanics. |
| WHAT AIR AMERICA CARRIED | SPLIT INTO H3S | 5–6 | Separate village collection, pre-helicopter transport, Air America, XKAT, and loading-control findings. |
| THE WAR CAME FIRST | MOVE | 17. THE STRONGEST CASE AGAINST THIS | This is the best conventional explanation and belongs penultimate. |
| FROM OPIUM TO HEROIN | REWRITE | 7. THE PIPELINE REACHES THE UNITED STATES | Replace a generic commodity transition with three controlled endpoint cases and explicit documentary breaks. |
| WHAT THE KERRY COMMITTEE ACTUALLY FOUND | MOVE/MERGE | 13–14 | Put findings inside named Contra logistics/enforcement mechanisms, not as report summary. |
| THE INSPECTOR GENERAL’S PROBLEM | MOVE/MERGE | 13–14 and 17 | Use OIG actor-level evidence in narrative; reserve institutional denials/method limits for rebuttal. |
| THE MEMO THAT CREATED A BLIND SPOT | KEEP BUT CONDENSE/MOVE | 10 and 14 | Introduce Section 660/narcotics continuity briefly, then use the 1982 MOU where enforcement conflict is analyzed. |
| WHEN LAW ENFORCEMENT GOT TOO CLOSE | KEEP BUT EXPAND | 14. WHEN LAW ENFORCEMENT GOT TOO CLOSE | Preserve Hyde, SETCO, Zavala, Bueso and case-specific mechanisms; avoid a generalized protection claim. |
| THEN THERE IS BRAZIL | REWRITE/MOVE | 15. BRAZIL: WHERE THE DRUG TRAIL BREAKS... | Use as controlled comparison after Contra evidence, not a surprise second main case. |
| THE SECURITY STATE THAT FOLLOWED | CONDENSE/MERGE | 15 | Keep only what proves access/capacity/political-action comparison and named institutional consequences. |
| THE BRAZIL BREAK IN THE FILE | KEEP AS CORE, REWRITE | 15 | Make the missing drug chain explicit and visible. |
| SO WAS THE CIA TRAFFICKING DRUGS? | MERGE | 16–17 | Replace binary question with a mechanism synthesis and strongest opposing case. |
| THE ORDINARY EXPLANATION | KEEP, MOVE | 17. THE STRONGEST CASE AGAINST THIS | Required second-to-last narrative section. |
| THE PROBLEM WITH THAT EXPLANATION | MERGE | 17 | Present rebuttal and its residual problems in one fair section. |
| THE PIPELINE | REWRITE | 16. WHAT THE PIPELINE ACTUALLY WAS | State bounded synthesis before rebuttal; avoid the current conclusion’s command-chain ambiguity. |
| Current conclusion/Part 4 teaser (embedded before FAQ) | REPLACE | 18. THE FILES LEAD TO DAN MITRIONE | Use Moran only if sourced; otherwise use institutional fallback. |
| FREQUENTLY ASKED QUESTIONS / related articles | KEEP AFTER NARRATIVE | Utility sections | Preserve exact five FAQs, related links, subscribe/share markers after the final narrative bridge. |

The approved 18-section order is logically sound. Sections 8–10 should be treated as one documentary act: the Laos narcotics program reintroduces the academy; Course No. 8 shows the specific transnational classroom; the alumni/FBN material explains network continuity; Section 660 then shows why narcotics training survived the broader police-assistance ban. If the Tier 1 academy records do not arrive, that act must shrink rather than be padded with Part 2 material.

### Narrative bottlenecks and transitions

- **Too many names:** Group actors by evidentiary function—village witnesses, Lao generals, airlines, academy alumni, Contra contractors—not by biography. Give only Moran the full final bridge if proved.
- **Chronology confusion:** Use four visible time blocks: 1960s–71 Laos; 1966–75 academy/narcotics continuity; 1980s Contra/Seal; Brazil as a controlled comparison placed near the end. A compact dated rail can prevent backtracking.
- **Geographic whiplash:** Each theater change must answer the preceding section: commodity endpoint → training network → legal continuity → aviation/personnel continuity → enforcement conflict → comparison.
- **Repetitive CIA caveats:** State the evidence ladder once, then use short source-specific limits. Consolidate the full denial/alternative case in Section 17.
- **Guilt by association:** Every named alumnus needs a demonstrated institutional role. Do not infer narcotics complicity from geography, training, CIA liaison, or later office.
- **Source dump:** Reports should appear when they change a mechanism. Avoid sections named only after Kerry/OIG documents.
- **Disconnected rabbit holes:** BCCI, Mena, Nazar Haro, and Brazil can each consume an article. Retain only if they close a required link.
- **Aircraft drama:** Do not let a visually attractive “same plane” claim survive a failed identity table.

## 10. SOURCE-GUIDANCE ARCHITECTURE

### 10.1 Current support

No current Codex-first control file provides the requested source-specific contract.

The closest equivalents are dispersed:

- filename/provenance in source inventories and extraction indexes;
- title/kind/path/reliability in the legacy `sources` table;
- claim/excerpt/verified/support/reliability/author/date in legacy `evidence` records;
- source/page/evidence/contrary evidence/documentary break in Part 3’s CSV ledger;
- allowed/forbidden implications in prose inside the evidence atlases and final checks.

There is no standard representation of `SECTIONS`, `SUPPORTS`, `ATTRIBUTION_RULE`, `CONTRADICTS`, `DO_NOT_USE_TO_PROVE`, `KNOWN_LIMITATIONS`, `QUOTE_RULE`, or `RESEARCH_NOTES`. More importantly, `codex_articles.generate_prompt()` does not discover such metadata, the writer is not guaranteed to see it, and `validate()` cannot enforce it.

### 10.2 Minimum clean extension

Phase 2 should create one article-local structured file:

`research/PART_03_SOURCE_GUIDANCE.json`

JSON is preferred over Markdown or YAML because this repository already uses JSON for configuration/manifests, Python can validate it without a new dependency, and exact enums/IDs can be tested. A short generated/readable Markdown view may be added later, but JSON should be canonical.

Recommended shape:

```json
{
  "schema_version": 1,
  "evidence_levels": [
    "DOCUMENTED FACT",
    "PRIMARY GOVERNMENT RECORD",
    "OFFICIAL INVESTIGATIVE FINDING",
    "CORROBORATED ACCOUNT",
    "NAMED FIRSTHAND INTERVIEW",
    "PUBLISHED ATTRIBUTED ACCOUNT",
    "SWORN TESTIMONY",
    "OFFICIAL ALLEGATION",
    "SECONDARY SCHOLARLY SYNTHESIS",
    "STRONG INFERENCE",
    "PLAUSIBLE CONNECTION",
    "SPECULATION",
    "DOCUMENTARY GAP"
  ],
  "sources": [
    {
      "source_id": "P3-MCCOY-1972",
      "filename": "52_Alfred_McCoy___The_politics_of_heroin_in_Southeast_Asia.pdf",
      "title": "The Politics of Heroin in Southeast Asia",
      "author": "Alfred W. McCoy",
      "date": "1972",
      "provenance": "Original published book; local scan; mixed field interviews and synthesis",
      "source_type": "BOOK_INTERVIEW",
      "primary_or_secondary": "MIXED",
      "sections": [4, 5, 6, 7],
      "supports": ["P3-B-HELICOPTER-COLLECTION", "P3-C-OUANE-TESTIMONY"],
      "evidence_level": "NAMED FIRSTHAND INTERVIEW",
      "attribution_rule": "Name McCoy and the interviewee for testimony; do not present as an official finding",
      "contradicts": ["Blanket no-carriage proposition"],
      "do_not_use_to_prove": ["CIA institutional order", "continuous village-to-U.S. load"],
      "known_limitations": ["Interview notes not local", "later authors often depend on this source"],
      "quote_rule": "Exact quotation requires printed/PDF page and comparison to scan",
      "research_notes": "Count underlying witnesses, not repeating books"
    }
  ]
}
```

Claim IDs should be stable and appear in the Phase 2 ledger/outline. The file should also distinguish the hosting/preservation layer from authorship: `CIA_AUTHORED`, `CIA_INTERNAL`, `CIA_DECLASSIFIED_THIRD_PARTY`, `PRESS_CLIPPING_IN_CIA_FILE`, `CONGRESSIONAL_MATERIAL`, `COURT_RECORD`, `BOOK_INTERVIEW`, and similar values.

### 10.3 Consumption and enforcement

For Part 3 only, the minimum implementation is procedural: explicitly name the JSON in the revised `ARTICLE_BRIEF.md` and one manually generated Part 3 prompt, require the writer to read it before outlining, and require each major outline section/claim ledger row to cite source IDs. No Python change is necessary to start Phase 2.

If generalized later, `codex_articles.generate_prompt()` can discover an optional `research/SOURCE_GUIDANCE.json` or article-local configured path, summarize source IDs/sections/constraints, and require it. A small schema loader can validate fields, enums, duplicate IDs, relative filenames, and references. Validation can enforce structure and references; it cannot determine historical truth, whether a source really supports a claim, or whether a paraphrase subtly overreaches. Those remain evidence-editor duties.

## 11. WRR EDITOR CHANGES REQUIRED

| File | Function/class/config | Current behavior | Problem | Minimal change | Test required | Article-specific or global? |
| --- | --- | --- | --- | --- | --- | --- |
| Part 3 `ARTICLE_BRIEF.md` | Control file | Describes old Vietnam/Brazil scope | Contradicts approved Laos/IPA/Contra architecture | Replace in Phase 2 with approved scope, structure, exclusions, evidence taxonomy, and source-guidance path | No application test; editorial review | Article-specific |
| `research/PART_03_SOURCE_GUIDANCE.json` | New control file | Absent | Writer lacks source-use permissions/limits | Create populated JSON after acquisition; stable IDs and section mappings | JSON/schema/reference check | Article-specific, mandatory |
| Part 3 claim ledger | `PART_03_CLAIM_LEDGER_V3.csv` or JSON ledger | V2 covers old architecture and four-level-ish judgments | New claims I–X and 13 evidence levels absent | Create V3; retain old IDs/history; add guidance source IDs, attribution and forbidden-inference columns | Referential/manual audit | Article-specific |
| Part 3 prompt | `CODEX_PROMPT.md` | Generated before revision | Does not mention the new guidance or mandatory structure | Regenerate after brief/guidance; preserve series context | Inspect generated prompt | Article-specific |
| `white_rabbit/codex_articles.py` | `generate_prompt()` | Inventories files; generic ledger instructions | Optional source guidance is invisible unless brief names it | Later: discover optional guidance path and require reading | Extend `test_status_and_prompt_refresh` | Global, optional after Part 3 |
| New `white_rabbit/source_guidance.py` or small helper | Schema loader | None | No structural validation | Later: validate JSON schema, enums, IDs, safe relative filenames | New unit tests for malformed enums, duplicates, traversal, missing source | Global, optional |
| `white_rabbit/codex_articles.py` | `validate()` | Mechanical publication validation | Cannot ensure major claims cite guidance IDs or preserve evidence levels | Later: if a structured claim manifest exists, validate references only; issue warning, not truth certification | Fixture pass/fail tests | Global, optional |
| `white_rabbit/codex_series.py` | `generate_prompt()` | Injects prior paths/memory and shared inventories | Does not inject claim-level Part 2 dependencies or a sourced Part 4 bridge | For Part 3, use a local continuity matrix; later allow optional structured continuity file | Prompt test if generalized | Article-specific first |
| Part 3 continuity control | New `research/PART_03_CONTINUITY_MATRIX.json` or section in guidance | Current continuity lives in prose | Easy to exaggerate spotting→recruitment or spoil Part 4 | Store prior claim IDs, allowed recap, forbidden escalation, next-part bridge status | Reference/manual review | Article-specific |
| Quote verification | New Phase 2 quote ledger | No automatic check | Exact quotes can lose source/page/context | Record quote, source ID, PDF/printed page, verified flag, surrounding-context note | Manual evidence audit; optional schema test | Article-specific first |
| `white_rabbit/editorial_diagnostics.py` | `analyze_editorial_style()` | Style-only advisory metrics | No evidentiary role | No change for Phase 2 | Existing tests sufficient | Global; no change |
| `substack_source_linker.py` / `sources.csv` | Exact link phrase mapping | Verifies anchor mechanics | Can create false confidence in source adequacy | No code change; audit must continue to separate mechanics from evidence | Existing linker/validator tests | Global; no change |
| `schemas.py` / `evidence_db.py` | Legacy evidence models | Four support types, coarse reliability, separate pipeline | Tempting but not connected to Codex series | Do not retrofit for Part 3; consider future migration only after article-local design proves useful | Migration tests if ever done | Global, deferred |

No code or configuration change is required during Phase 1. The smallest safe Phase 2 implementation begins entirely inside the Part 3 workspace.

## 12. VISUAL PLAN

1. **Laos pipeline map.** Nodes: producing villages/Long Pot/Nam Ou, Long Tieng, Vientiane, Ban Houei Sai, Mae Salong, Gulf of Siam/South Vietnam, Fort Monmouth/New York/Orly. Use solid lines for documented routes, dashed lines for named testimony, dotted lines for inference, and visible breaks where no continuous shipment exists. Do not imply every node belongs to one load.
2. **“The Academy Reappears” document spread.** Pair the FY1974–75 Laos program page with the original IPA Course No. 8 page. Only create after both originals are acquired. Highlight the Lao military-police/U.S. training fields and the course roster/date, not an interpretive caption claiming asset recruitment.
3. **Buell/Schanche economic flow.** Sweet-potato substitution failure → wartime cultivation advice → medicines reduce local medicinal consumption (attributed) → greater available surplus (inference) → Communist purchasing → reported buyer change. Visually label what is Schanche’s observation versus his theory.
4. **Village collection sequence.** Pony/bamboo phase → 1969–70 helicopter insertion → several-day village circuit → radio pickup → reported return toward Long Tieng. Caption as Ger Su Yang/village testimony; do not draw an Air America logo unless aircraft identity is proved for that leg.
5. **Air America/AID dual-use operations table.** Contract, aircraft assignment, base/route, documented cargo/task, and source. Place official loading-control concession beside it. This makes infrastructure visible without labeling aid flights “drug flights.”
6. **Police network flow.** OPS → IPA → course/participant → alumni/national institution → documented security or narcotics-control role. Use a separate dotted intelligence-access layer based on Part 2. Do not render “contact” as “asset.”
7. **Section 660 legal fork.** Broad police-assistance prohibition on one branch; DEA/FBI/narcotics exceptions and later functional continuity on the other. Keep compact so Part 5 retains the full legislative story.
8. **Contra knowledge/enforcement matrix.** Rows for SETCO, Vortex, Morales, Hull, Hyde, Bueso; columns for narcotics information, operational value, continued use, enforcement/reporting outcome, evidentiary status. This is clearer than another route map.
9. **Seal C-123 airframe timeline—conditional.** Tail, USAF/manufacturer serial, owner/operator, dates, event. Generate only after the identity table shows a verified match. If identity fails, use two separate aircraft/event cards explicitly marked “identity not established,” or omit.
10. **Brazil documentary break.** A short four-lane diagram—aid/security capacity, CIA political action, repression/abuse, narcotics hypothesis—with the drug route stopping at the missing named actor/transport/finance/U.S. endpoint. The break is the visual conclusion.

## 13. OVERCLAIM / EVIDENCE RISKS

- **Source conflation:** McCoy, Scott, and later authors often share the same underlying interview. Kerry and later books often share the same investigative record. Count witnesses/documents, not titles.
- **Guilt by association:** Academy attendance, employment, geography, CIA liaison, or later office does not establish narcotics complicity.
- **Testimony → fact conversion:** Ouane, Thao Ma, Ger Su Yang, Hmong sources, and Schanche are valuable testimony with different access and incentives; they are not official adjudications.
- **CIA-hosted document confusion:** A press clipping, book excerpt, suppressed-report reproduction, or congressional item in the Reading Room is not CIA-authored. Record the originating author/body and preservation layer separately.
- **Regional tonnage → route tonnage error:** Golden Triangle, KMT, or annual production estimates cannot be assigned to the Mae Salong road, a single caravan, airline, or American-built route without load-specific evidence.
- **Aircraft identity error:** Same type, nickname, theater, or later operator does not establish the same airframe. Registration, military/manufacturer serial, ownership, dates, and transfer chain must agree.
- **Contact → asset error:** “Valuable contacts overseas” describes liaison utility, not recruited CIA assets. Part 2 proves spotting/assessment and sponsored participants, not completed recruitment of every alumnus.
- **Institutional overlap → command/control error:** CIA, AID/USAID, OPS, IPA, FBN/BNDD/DEA, State, contractors, and local institutions must remain distinct even where they coordinate.
- **Law-enforcement conflict → deliberate trafficking error:** A reporting gap, delayed case, leniency request, returned money, or prosecution concern can prove accommodation or operational priority without proving that officials desired trafficking.
- **Temporal mismatch:** Do not join 1960s Laos, 1974 academy training, 1984 Seal, 1986 Contra logistics, and later allegations as if contemporaneous. Each continuity claim needs an explicit bridge.
- **Mirrored-source reliability:** Weak hosts can reveal a source but do not establish its identity or completeness. Replace them with the original edition/record.
- **Official denial scope:** “No institutional policy,” “no evidence found,” “no knowing U.S.-pilot participation,” “no CIA file,” and “no Mena operation” are not interchangeable.
- **Development effect → intent:** AID roads, rice, medicine, relief, or aircraft support may materially alter an economy without being designed to promote narcotics.
- **Named endpoint → continuous chain:** The 1971 seizures show endpoints; they do not trace a specific village crop through Long Tieng, a refinery, courier, and U.S. dealer.
- **Section 660 continuity → replacement:** Narcotics and federal-agency exceptions preserved functions; DEA did not simply replace OPS.
- **Corporate → personnel continuity:** Former Air America personnel in a later network, if proved, do not mean Air America became the Contra air network.
- **Brazil analogy → Brazil drug pipeline:** Brazil strongly supports access, political alignment, capacity, and abuse knowledge. It does not presently support a completed protected cocaine route.
- **Attributed torture allegation → finding:** Moran/Mitrione allegations must retain the speaker, date, source, and corroboration status; Part 4’s core purpose is to test precisely this conversion.

## 14. RECOMMENDED THESIS

The conservative candidate is supported clause by clause:

- **“U.S. aid and covert programs built access”** — documented by Part 2, Agee, MSU, OPS, and country records.
- **“logistics”** — documented by Air America/AID contracts/assignments and Contra contractor records.
- **“security relationships and allied networks”** — documented across Laos, IPA/Police Group, Contra, and Brazil.
- **“repeatedly intersected with narcotics economies”** — strongly supported in Laos and Contra cases; should not be generalized to every program/country.
- **“strategic priorities sometimes limited enforcement”** — official Laos concessions, MOU/reporting history, Hyde, Seal political disclosure, Zavala, and other bounded cases support this.

The stronger candidate also survives if calibrated:

- **“knowingly preserved”** — supportable for selected relationships after documented warnings, especially Laos non-suppression and Hyde; not as a universal policy.
- **“materially enabled”** — supportable for infrastructure, territorial resilience, transport capacity, and operational relationships; direct drug carriage/finance is uneven.
- **“allies embedded in narcotics economies”** — supportable for Laos and some Contra-linked actors.
- **“tolerance, logistics, access, and selective non-enforcement”** — strongest synthesis.
- **“not a centrally directed CIA drug cartel”** — accurate evidentiary boundary.

Recommended final wording:

> Across Laos and the Contra war, U.S. aid and covert systems built transport, access, and security relationships around allies operating inside narcotics economies. When officials learned of the risk, they sometimes preserved those relationships and subordinated enforcement to strategic utility. The record is strongest for infrastructure, knowledge, tolerance, and selective non-enforcement—not for a centrally directed CIA drug pipeline into the United States.

This formulation avoids two weaknesses in the previous thesis. It does not imply every aid activity was covert, and it does not use “materially enabled” as a shortcut for knowing carriage of particular drug loads. Brazil should be presented as the comparison that proves security/access architecture while exposing the absence of a narcotics chain.

## 15. PHASE 2 IMPLEMENTATION PLAN

1. **Freeze the audit as the Phase 1 authority.** Do not edit article prose or regenerate the prompt yet.
2. **Acquire Tier 1 in dependency order:** Laos FY1974–75 program; IPA Course No. 8; FBN reports; alumni report/rosters; PARU records; Moran packet; Seal airframe and CIA denial; endpoint records; official contract/IG/XKAT/payment packets.
3. **Acquire Tier 2 unique testimony selectively.** Prioritize McCoy notes, Schanche materials, Bill Lair, and any person retained in the outline.
4. **Run integrity and provenance checks.** Hash/copy originals into `sources/`; record issuer, archive URL/ID, date, authorship classification, page count, OCR quality, and derivative parent.
5. **Create `research/PART_03_SOURCE_GUIDANCE.json`.** Populate allowed proofs, forbidden proofs, attribution/quote rules, contradictions, limitations, sections, and stable source IDs.
6. **Build Claim Ledger V3 and quote ledger.** Give every major planned claim one required evidence category and at least one guidance source ID; mark documentary gaps explicitly.
7. **Resolve three go/no-go gates:** (a) same C-123 identity; (b) named IPA→PARU link; (c) Moran bridge. If a gate fails, replace or remove its narrative unit—never soften an unsupported fact into insinuation.
8. **Update the Part 3 brief.** Replace the obsolete Vietnam/Brazil scope with the approved 18-section architecture, thesis boundary, evidence taxonomy, and utility-section requirements.
9. **Refresh series continuity controls.** Record exact Part 2 facts allowed for callback and the evidence-controlled Part 4 bridge. Update series memory only after findings are verified; do not alter Part 2 or Part 4 prose.
10. **Generate a fresh Part 3 Codex prompt.** Confirm that it names the source-guidance and continuity controls and inventories all new sources.
11. **Lock the outline before drafting.** Keep Section 17 as the second-to-last narrative rebuttal/limitations section and Section 18 as the final Part 4 transition. Cut any section whose evidence gate remains open.
12. **Draft from the ledger, not from the current article.** Reuse verified findings, not sentences or old structure. Keep Brazil condensed and BCCI outside the main line.
13. **Run independent evidence, continuity, quote, aircraft-identity, and source-dependency passes.** Then run voice, anti-AI, formatting, and visual passes without removing qualifiers.
14. **Reconcile publication links and source CSV only after prose stabilizes.** Link original/public-facing sources; confirm exact phrase/destination and source adequacy separately.
15. **Validate and export.** Run the series validator, review all warnings, and run the full test suite only if application/config code changed. Record any unsupported but intentionally retained editorial choice in the audit.

Phase 1 made no application or configuration changes, downloaded no sources, changed no adjacent article, and did not rewrite Part 3. The reconciliation baseline of 192 passing tests therefore remains the relevant test result.
