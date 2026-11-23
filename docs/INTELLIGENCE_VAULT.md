# White Rabbit Intelligence Vault — Phases 1–3

## Purpose and architecture

The Vault is an additive, local, provenance-first subsystem. It does not replace the
Codex article, series, archive, Gemini, or distribution workflows. Its SQLite database is
`knowledge/intelligence_vault.db`, which is intentionally ignored by Git. Original files are
preserved under the ignored `knowledge/intelligence_vault_evidence/` content-addressed archive.
Stable UUID-based
IDs separate identity from names. Versioned migrations run transactionally with foreign
keys enabled. Schema version 4 upgrades existing Phase 1–3 databases in place and adds
query indexes plus explicit source-document investigation memberships.

The model has four entity kinds (people, organizations, events, and places), aliases,
investigations, documents with immutable revisions, claims, claim evidence, relationships,
relationship evidence, conflicts, and merge suggestions. Historical start/end values each
retain precision and certainty. Source creation dates, historical dates, and import dates
are separate fields.

### Schema map

| Area | Tables | Purpose |
|---|---|---|
| Identity | `entities`, `aliases`, four `*_details` tables, `import_entity_bindings` | Stable identity, explicit import bindings, and type-specific metadata |
| Investigations | `investigations`, `entity_investigations`, `document_investigations` | Explicitly reuse identities and sources across projects |
| Sources | `documents`, `document_locations`, `document_revisions` | Original locators, classification, hash, text, immutable revisions |
| Evidence | `claims`, `claim_evidence`, `claim_entities` | Atomic statements, wording, locations, dependency and entity links |
| Network | `relationships`, `relationship_evidence` | Typed, dated, classified edges with direct provenance |
| Review | `conflicts`, `merge_suggestions` | Preserve disagreement and defer ambiguous identity decisions |
| AI extraction | `extraction_jobs`, `extraction_chunks`, `extraction_proposals`, `extraction_quality_issues`, `extraction_approval_history` | Resumable inference, isolated proposals, quality review, and complete decision history |

## Source-authority behavior

The Vault follows `research_library/methodologies/SOURCE_AUTHORITY_AND_CANON.md`.
Published White Rabbit findings may be stored as `PUBLISHED WHITE RABBIT CANON` and
author-supplied material defaults to authority level 2. Testimony, allegations, facts,
interpretations, and conclusions remain distinct claim types. Conflicting claims are kept
and linked in the review queue. Corroboration dependency groups prevent repeated accounts
from being represented as independent streams. Phase 1 never contacts an AI or external
search service and never automatically imports the existing archive.

## Installation and startup

Use Python 3.12 and the repository environment:

```powershell
.venv\Scripts\python.exe -m white_rabbit vault init
.venv\Scripts\python.exe -m white_rabbit vault serve
```

Then open `http://127.0.0.1:8765`. The local interface provides search, statistics,
review queues, entity profiles through `/api/entities/<id>`, and manual entry/edit APIs.
Bind to the default loopback address unless access from another machine is intentional.

## Core workflows

Ingest a readable TXT, Markdown, CSV, JSON, DOCX, or text-extractable PDF without extracting
claims:

```powershell
.venv\Scripts\python.exe -m white_rabbit vault ingest path\to\source.pdf
```

Import a validated extraction package, search, inspect, and export:

```powershell
.venv\Scripts\python.exe -m white_rabbit vault import-json extraction.vault.json
.venv\Scripts\python.exe -m white_rabbit vault search "Office of Policy Coordination"
.venv\Scripts\python.exe -m white_rabbit vault show ENT-uuid
.venv\Scripts\python.exe -m white_rabbit vault show-document DOC-uuid
.venv\Scripts\python.exe -m white_rabbit vault review
.venv\Scripts\python.exe -m white_rabbit vault events 1940 1950
.venv\Scripts\python.exe -m white_rabbit vault export backups\vault-export.json
.venv\Scripts\python.exe -m white_rabbit vault backup knowledge\intelligence_vault_backups\phase-1-1
.venv\Scripts\python.exe -m white_rabbit vault --db knowledge\restored-vault.db restore knowledge\intelligence_vault_backups\phase-1-1
```

Manual commands include `add-entity`, `add-claim`, and `add-relationship`; use `--help`
on any command for arguments. The web API supports `POST /api/entities`, `/api/claims`,
and `/api/relationships`, plus `PATCH /api/entities/<id>`.

## Structured import format

The JSON format is schema-versioned and strictly validated by Pydantic. Entity and claim
`ref` values are local import references. An entity is never assigned to a pre-existing
identity merely because its name or alias matches. Use `known_entity_id` only after a human
has confirmed the identity. Otherwise the import creates a distinct stable entity and a
reviewable match suggestion. Re-imports remain idempotent through the document/ref binding.

```json
{
  "schema_version": 1,
  "document": {"path": "memo.pdf", "title": "Memo", "authority_level": 2},
  "entities": [
    {"ref": "person-a", "entity_type": "person", "name": "Example Name", "aliases": []},
    {"ref": "unit-a", "known_entity_id": "ENT-confirmed-uuid",
     "entity_type": "organization", "name": "Example Unit", "aliases": []}
  ],
  "claims": [{
    "ref": "claim-a", "statement": "Example Name served in Example Unit.",
    "original_wording": "...", "claim_type": "fact", "status": "DOCUMENTED RECORD",
    "entity_refs": ["person-a", "unit-a"], "locator": "page 4",
    "historical_start": {"value": "1942", "precision": "year", "certainty": "certain"}
  }],
  "relationships": [{
    "subject_ref": "person-a", "object_ref": "unit-a", "relationship_type": "served_in",
    "claim_ref": "claim-a", "locator": "page 4", "classification": "DOCUMENTED RECORD"
  }],
  "conflicts": []
}
```

The complete structured import is one database transaction. Any entity, claim, relationship,
or conflict failure rolls back the document and every other database write from that import.
An unchanged file hash is idempotent. A changed file creates a new immutable revision;
older extracted text and evidence links remain intact. Exact name or alias collisions create
merge suggestions rather than automatic merges.
Copies at different paths with the same hash share one document identity while retaining
each observed location.

The original file is copied, byte-for-byte, to `intelligence_vault_evidence/sha256/<prefix>/<hash>`.
The database stores the relative archived path, SHA-256 hash, and original path. Later changes
or removal of the original do not affect the preserved copy. Existing schema-v1 documents
must be re-ingested once to populate their archived path.

## Historical dates and overlap

Dates retain `exact`, `month`, `year`, `approximate`, or `unknown` precision plus `certain`,
`probable`, `possible`, `uncertain`, or `unknown` certainty. A known start with no end is
open-ended; a missing start is insufficient chronology. Overlap queries return one of four
states: `definite_overlap`, `possible_overlap`, `no_overlap`, or `insufficient_evidence`.
Year/month boundary ranges and uncertainty are never silently collapsed to a Boolean.

## Backup and recovery

Use `vault backup` for a complete bundle. It uses SQLite's online backup API, runs an integrity
check, includes the content-addressed evidence archive, and records hashes in `manifest.json`.
`vault restore` verifies every hash before restoring the database and evidence. The JSON
`export` command now includes every application table, including all entity-detail tables,
investigations, memberships, import bindings, evidence locations, and review records.
Original source files are never replaced. Always restore to a separate database first and
confirm it with `vault stats` before replacing a working copy.

## Local API safety

The browser server can bind only to `127.0.0.1`, `localhost`, or `::1`. It validates the Host
header to resist DNS rebinding, rejects cross-origin writes, does not enable CORS, requires
`application/json`, rejects transfer-encoded or malformed bodies, and caps request bodies at
256 KiB. Payloads use strict schemas and security headers disable framing, MIME sniffing, and
caching. Document ingestion remains a CLI operation rather than a large HTTP upload.

## Phase 2 document intelligence

Phase 2 uses the enforced workflow **Document → Extract → Validate → Reconcile → Preview →
Approve → Commit**. Model output is stored only in extraction tables. It cannot write directly
to accepted entities, claims, relationships, or conflicts. A proposal enters accepted knowledge
only after an approval decision and `extraction-commit`.

### Providers and privacy

- `manual` validates offline extraction JSON keyed by stable chunk ID or ordinal.
- `mock` is deterministic and intended for tests and fictional demonstrations.
- `gemini` uses the repository's existing structured-output and retry infrastructure.

Gemini is disabled unless `--allow-cloud` is supplied for that job. This is the explicit consent
that document chunks may leave the computer. API keys remain in the environment or local `.env`;
they are never stored in the Vault. No provider performs web research during ingestion. Source
text is marked as untrusted data in the Gemini prompt so instructions embedded in documents are
not followed.

```powershell
# Explicit cloud extraction
.venv\Scripts\python.exe -m white_rabbit vault extract C:\Sources\book.pdf `
  --provider gemini --model gemini-3.7-flash --allow-cloud

# Offline/manual extraction
.venv\Scripts\python.exe -m white_rabbit vault extraction-prepare C:\Sources\book.pdf `
  C:\Sources\book-packet
# Fill book-packet\results.template.json with an offline tool, then:
.venv\Scripts\python.exe -m white_rabbit vault extract C:\Sources\book.pdf `
  --provider manual --manual-results C:\Sources\book-packet\results.template.json
```

No live paid-provider call is made by tests. The system records an estimated input-token count
before processing and stores any provider token/cost metadata returned by a provider.

### Chunking, locators, and resume

PDFs are divided with physical page numbers and printed page labels. DOCX paragraphs and
Markdown sections retain section/line context. Other readable formats receive reproducible line
and absolute character offsets. Chunk IDs derive from the source hash and exact source offsets;
size and overlap are configurable with `--chunk-size`, `--overlap`, and `--max-chunks`.

Every selected chunk is checkpointed independently. Completed unchanged chunks are not sent to
the provider again. Interrupted `processing` chunks return to `pending` on resume; failed chunks
are retried explicitly:

```powershell
.venv\Scripts\python.exe -m white_rabbit vault extraction-status JOB-UUID
.venv\Scripts\python.exe -m white_rabbit vault extraction-retry JOB-UUID `
  --provider gemini --allow-cloud
```

Unreadable PDF pages, provider failures, skipped sections, and incomplete chunk coverage are
reported rather than silently truncated.

### Review and approval

```powershell
.venv\Scripts\python.exe -m white_rabbit vault extraction-review JOB-UUID
.venv\Scripts\python.exe -m white_rabbit vault extraction-review JOB-UUID --approve PROP-UUID
.venv\Scripts\python.exe -m white_rabbit vault extraction-review JOB-UUID --reject PROP-UUID
.venv\Scripts\python.exe -m white_rabbit vault extraction-review JOB-UUID `
  --match PROP-UUID=ENT-CONFIRMED-UUID
.venv\Scripts\python.exe -m white_rabbit vault extraction-review JOB-UUID --approve-all
.venv\Scripts\python.exe -m white_rabbit vault extraction-commit JOB-UUID
```

Bulk approval skips blocking proposals. Bulk rejection may reject every pending proposal.
Approved relationships and claims cannot commit unless their entity dependencies were also
approved or already committed. Confirmed identity matches use the existing `known_entity_id`
boundary; name equality alone never merges a person. Approving a confirmed match adds proposed
aliases and fills previously empty profile fields, but never overwrites conflicting accepted
dates or biography fields.

The browser screen can start a job and the JSON interface provides:

- `POST /api/extractions`
- `GET /api/extractions/<job-id>` and `/review`
- `PATCH /api/extractions/<job-id>/proposals/<proposal-id>`
- `POST /api/extractions/<job-id>/retry` and `/commit`

### Deterministic quality controls

The validator checks verbatim quote existence, exact offsets, page/line/section locators,
historical date syntax, chunk reference consistency, repeated claims, entity/date conflicts,
same-name ambiguity, required testimony/allegation attribution, relationship support, provider
schema violations, lexical claim/passage mismatch, and complete document coverage. Findings are
classified as blocking, warning, or informational. These checks validate extraction fidelity;
they do not apply external credibility tests to author-supplied evidence.

The offline fictional demonstration is in `examples/intelligence_vault_phase2/`.

## Phase 3 historical exploration

Phase 3 replaces the raw JSON landing page with a cohesive local research interface:

**Dashboard | Evidence Library | People & Organizations | Timeline | Red String Board |
Investigations | Review Queue**

Start the real Vault with:

```powershell
.venv\Scripts\python.exe -m white_rabbit vault init
.venv\Scripts\python.exe -m white_rabbit vault serve --port 8765
```

Open `http://127.0.0.1:8765`. The server still refuses non-loopback binding. Cytoscape.js
3.31.2 and its license are vendored under `white_rabbit/intelligence_vault/static/vendor/`;
normal graph use makes no CDN request. Content Security Policy permits scripts, styles, and
connections only from the local server. Imported names and excerpts are inserted through DOM
text nodes, never as HTML.

### Red String Board

The board uses distinct shapes and colors for people, organizations, events, places, and
optionally source documents. It supports pan, zoom, dragging, search/focus, fit, force,
hierarchical, circle and grid layouts, plus one-, two-, or three-hop expansion. It never sends
the complete database to the browser: responses are bounded to 500 identity nodes and have an
opaque continuation cursor. Search, relationship type, investigation, date window, and temporal
state filters run on the server.

Accepted relationships are solid edges. `ACCEPTED TESTIMONY` and `CORROBORATED INFERENCE`
retain their stored classification. The optional dashed amber overlay is generated by the
read-only deterministic discovery boundary and is labelled `exploratory_candidate`. It is not
written to `relationships`. A shared military unit or employer may produce an institutional
overlap candidate, but the UI and API explicitly state that this does not establish personal
contact, coordination, or common command.

Selecting an accepted edge shows its direction, classification, complete historical range and
precision, source document, stored passage, locator, revision ID, and claim reference. Selecting
a candidate shows its deterministic basis instead. JSON, PNG, and locally generated SVG exports
retain stable node and edge IDs.

### Timeline

The master timeline renders events and accepted dated relationships as ranges rather than
flattening them to points. Year values remain years; approximate or uncertain values receive a
visibly dashed style and are never displayed as invented exact days. Month and exact dates keep
their stored precision. Open-ended ranges remain open-ended in the API.

Filters cover person/organization/event ID, event type, country/place, investigation, source,
and historical window. Selecting a range opens its evidence and can focus the corresponding
identity on the graph. Zoom changes the historical scale from broad decades toward the available
year/month/day precision. Timeline results are bounded to 500 records with a continuation cursor
and export as JSON or UTF-8 CSV.

### Time-aware graph and path tracing

For a selected period, every accepted edge receives one of the existing temporal states:

- `definite_overlap` — show under Confirmed overlap;
- `possible_overlap` — show under Possible overlap;
- `insufficient_evidence` — show under Undated; or
- `no_overlap` — excluded by active-overlap views, but visible and labelled under All relationships.

The “How are these two connected?” tool performs a deterministic breadth-first traversal of
accepted `relationships`. Depth is capped at six, results at ten paths, and the UI defaults to
four and five respectively. Relationship-type filtering and direction-aware traversal are
optional. Adjacency is fetched only for the current traversal frontier, avoiding an unbounded
all-pairs search. Each result includes intermediate stable IDs, edge evidence, dates, a chain-wide
temporal state, and the fixed boundary that graph connectedness is not proof of historical
interaction.

### Profiles and investigation comparison

Profile pages combine type-specific details, aliases, career/affiliation relationships, claims,
source passages, documents, timeline records, explicit investigation memberships, open identity
matches, and claim conflicts. Empty fields stay empty; the profile service does not fabricate
biography or chronology.

Investigation comparison uses only `entity_investigations` and `document_investigations`.
It highlights identities and source documents explicitly attached to two or more selected
investigations. Shared names, keywords, or inferred source relevance do not create memberships.

### Read APIs and exports

Phase 3 endpoints are read-only:

| Endpoint | Purpose |
|---|---|
| `GET /api/graph` | Bounded graph, hop expansion, temporal/investigation/type filters, candidate overlay |
| `GET /api/relationships/<id>/detail` | Accepted edge, evidence passages, locators, and source metadata |
| `GET /api/timeline` | Bounded events and relationship ranges with four-state overlap |
| `GET /api/paths` | Limited deterministic shortest accepted paths |
| `GET /api/profiles/<entity-id>` | Evidence-backed person, organization, event, or place profile |
| `GET /api/investigations` | Explicit memberships and cross-investigation comparison |
| `GET /api/exports/timeline.csv` | Stable-ID timeline handoff |

Graph and path JSON, profile JSON, graph SVG/PNG, and timeline JSON/CSV exports preserve stable
IDs, classifications, source/revision references, passages, and locators for a later handoff to
the article research engine.

### Fictional demonstration and benchmark

The checked-in demonstration imports only `examples/intelligence_vault_phase3/lantern_field_report.md`
into a new disposable database and refuses to overwrite an existing file:

```powershell
.venv\Scripts\python.exe examples\intelligence_vault_phase3\load_demo.py `
  --db knowledge\phase3_demo.db
.venv\Scripts\python.exe -m white_rabbit vault `
  --db knowledge\phase3_demo.db serve --port 8765
```

The demo includes a three-hop institutional path, accepted testimony, a corroborated inference,
mixed date precision, source locators, and two people in the same military unit without an
accepted acquaintance edge.

On the development machine, the reproducible local benchmark returned a one-hop graph over
2,500 accepted relationships in **70.1 ms** and a 500-item timeline page from 2,500 relationships
in **90.0 ms**. Both responses were capped at 500 items. Re-run with:

```powershell
.venv\Scripts\python.exe examples\intelligence_vault_phase3\benchmark.py --relationships 2500
```

## Extension roadmap

- Phase 4: discovery implementations conform to `DiscoveryProvider` in `discovery.py`.
  Providers return reviewable candidates and never silently write relationships. The included
  shared-affiliation provider demonstrates temporal-overlap leads while explicitly refusing
  to infer acquaintance or coordination.

### Phase 4 readiness

Accepted graph reads, deterministic path traversal, temporal compatibility, explicit candidate
classification, stable exports, and the `DiscoveryProvider` boundary are now separate services.
Phase 4 can add reviewed multi-hop lead generators and scoring without changing `relationships`
or presenting an unapproved conclusion as accepted history. Any new engine should return
candidates with their basis and require the existing human promotion boundary.

## Phase 4 — Evidence Archive Importer

Phase 4 adds a resumable, offline-first ZIP/folder intake pipeline to the existing Vault. It
does not create a second database. Originals enter the existing content-addressed evidence
archive, extracted text enters `document_revisions`, and documents receive explicit investigation
membership. Claims, identities, events, and relationships still pass through the existing
Document → Extract → Validate → Reconcile → Preview → Approve → Commit boundary; importing a
file never promotes an allegation to accepted knowledge.

Launch the loopback-only application:

```powershell
.venv\Scripts\python.exe -m white_rabbit vault serve --port 8765
```

Open `http://127.0.0.1:8765`, select **Import Archive**, enter an absolute local ZIP/folder path,
preview the inventory, select an existing investigation ID or enter a new investigation name,
and start the job. The browser sends only the path and options to the local server; it does not
upload the archive. Per-file checkpoints support pause, resume, cancel, and retry. Completed
conversions are reused by SHA-256 plus conversion configuration, while every archive path remains
recorded as provenance.

The equivalent CLI workflow is:

```powershell
.venv\Scripts\python.exe -m white_rabbit vault archive-preview "C:\path\evidence.zip"
.venv\Scripts\python.exe -m white_rabbit vault archive-import "C:\path\evidence.zip" --investigation "Investigation Name"
.venv\Scripts\python.exe -m white_rabbit vault archive-status IMP-ID
.venv\Scripts\python.exe -m white_rabbit vault archive-action IMP-ID resume
```

For the real archive, preview first and review its storage estimate. Do not begin costly media
conversion until local capacity and desired Whisper model have been confirmed:

```powershell
.venv\Scripts\python.exe -m white_rabbit vault archive-preview "C:\Users\Cody\Downloads\Monarch.zip"
.venv\Scripts\python.exe -m white_rabbit vault archive-import "C:\Users\Cody\Downloads\Monarch.zip" `
  --investigation "Monarch Legacy Program" --whisper-model small
```

The importer prioritizes the named Monarch PDF/PPTX/media sources in
`prioritized_review_queue.csv`. Every job also produces `inventory.csv`, `manifest.json`,
`catalog.md`, `folder_tree.txt`, `conversion_status.csv`, and `extraction_errors.csv`; all are
downloadable from the Import Archive screen.

### Security and conversion boundaries

- ZIP entries are never executed. Absolute/traversal paths, symlinks, normalized path collisions,
  over-limit entries, excessive expansion ratios, corrupt archives, and unsupported formats are
  rejected, quarantined, or reported.
- Extraction is sequential and one member is materialized at a time. Temporary members are removed
  after each checkpoint. Preview reports expanded bytes, estimated storage, and available storage.
- SHA-256 controls evidence preservation and deduplication. CRC32 and filenames are inventory data,
  not identity. Duplicate paths retain exact source-archive and relative-path associations.
- PDF locators retain pages; PPTX locators retain slides, notes, and tables; spreadsheets retain
  sheet/row locators; local Whisper transcripts retain timestamps and SRT derivatives; images retain
  dimensions, thumbnails, and optional OCR warnings/confidence. OCR and transcripts are derivatives,
  never independent corroborating sources.
- No cloud service is used by archive intake. Any later cloud extraction still requires explicit
  consent for that extraction job. Private, sensitive, or potentially illegal material should be
  paused and handled manually; the importer does not redistribute or publish evidence.

Base conversion dependencies are in `requirements.txt`: PyMuPDF, python-pptx, openpyxl, and Pillow.
Media/OCR extras are in `requirements-media.txt`. FFmpeg/ffprobe and Tesseract must be installed as
local system tools. Missing optional tools produce per-file warnings without discarding originals.

### Phase 4 verification

Synthetic tests cover unsafe ZIP members, normalized collisions, symlinks, expansion limits,
mixed supported/unsupported content, content-hash deduplication across paths, exact byte
preservation, source metadata and locators, full-text search, report generation, idempotent job
processing, pause/resume/retry, corrupt PDFs, storage limits, investigation membership, and the
human-approval boundary. No Monarch media or private archive was processed by the test suite.

## Known limitations

The Vault uses lexical substring search rather than semantic retrieval. Image-only PDF pages are
flagged for review but do not yet run through the image OCR path automatically. The server has no
user authentication because it is enforced as loopback-only. Identity
suggestions are deterministic signals, not probabilistic adjudications; a human must confirm
matches. It does not automatically ingest the archive, invoke an LLM without an explicit
provider choice (and cloud consent where applicable), rank suspiciousness,
merge identities, or turn connection candidates into facts. Archive intake requires a trusted
local absolute path rather than a native OS file-picker dialog. Media processing is sequential to
bound resource use; it does not yet expose a configurable worker pool or generate video contact
sheets. Gemini cost is estimated unless the
provider exposes usage metadata. Very large proposal sets currently use JSON/CLI review without
pagination or a rich side-by-side visual diff. Phase 3 graph and timeline pages are capped at
500 records; very dense networks will benefit from future server-side aggregation and graph
clustering. Country filtering follows directly stored place edges rather than inventing a
geographic hierarchy. The current date parser supports CE years 0001–9999, not BCE chronology.
The only candidate overlay shipped in Phase 3 is shared-affiliation overlap; it has no invented
probability or coordination score.

## Phase 1.1 verification

The Phase 1.1 hardening suite covers non-merging identity resolution, explicit known-ID
reuse, contextual match suggestions, mid-import rollback, content-addressed preservation,
schema-v1 migration, lossless export, complete backup/restore, four-state temporal overlap,
strict request parsing, origin/Host checks, body limits, and loopback-only binding. The full
repository regression run completed with **290 passing tests** and no failures.

## Phase 2 verification

The Phase 2 suite uses fictional local documents and deterministic providers. It covers people,
organizations, events, document metadata, relationships, attributed testimony, PDF page labels,
verbatim quote checks, long-document chunk coverage, overlap deduplication, same-name identities,
confirmed identity matches, contradictions, derivative evidence groups, interruption/resume,
provider and schema failures, rejection isolation, approved provenance, unchanged-job idempotence,
manual chunk packets, and explicit cloud consent. The final full repository regression run
completed with **302 passing tests** and no failures. No paid or live provider request was made.

## Phase 3 verification

The Phase 3 suite uses only fictional local records. It covers accepted graph nodes and edges,
source passages and locators, directed and undirected traversal, shortest multi-hop institutional
paths, mixed date precision, definite/possible/no/insufficient overlap, temporally incompatible
chains, candidate separation, the no-invented-acquaintance boundary, profile provenance,
explicit cross-investigation entity and document memberships, pagination, empty and larger
datasets, read-only behavior, locally hosted assets, CSP-safe rendering, and HTTP integration.
The application was also exercised in a real browser at 1366×768, including graph expansion,
candidate overlays, timeline evidence, path tracing, and investigation comparison. The final
full repository regression run completed with **311 passing tests in 45.79 seconds**, with no
failures or skips.
