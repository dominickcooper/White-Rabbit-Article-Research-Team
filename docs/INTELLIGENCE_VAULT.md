# White Rabbit Intelligence Vault — Phases 1–2

## Purpose and architecture

The Vault is an additive, local, provenance-first subsystem. It does not replace the
Codex article, series, archive, Gemini, or distribution workflows. Its SQLite database is
`knowledge/intelligence_vault.db`, which is intentionally ignored by Git. Original files are
preserved under the ignored `knowledge/intelligence_vault_evidence/` content-addressed archive.
Stable UUID-based
IDs separate identity from names. Versioned migrations run transactionally with foreign
keys enabled. Schema version 3 upgrades existing Phase 1/1.1 databases in place.

The model has four entity kinds (people, organizations, events, and places), aliases,
investigations, documents with immutable revisions, claims, claim evidence, relationships,
relationship evidence, conflicts, and merge suggestions. Historical start/end values each
retain precision and certainty. Source creation dates, historical dates, and import dates
are separate fields.

### Schema map

| Area | Tables | Purpose |
|---|---|---|
| Identity | `entities`, `aliases`, four `*_details` tables, `import_entity_bindings` | Stable identity, explicit import bindings, and type-specific metadata |
| Investigations | `investigations`, `entity_investigations` | Reuse one identity across many projects |
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

## Extension roadmap

- Phase 3: timeline and graph clients can consume the entity profile/search APIs without
  changing accepted storage. Extraction proposals already retain the entity IDs, historical
  ranges, provenance, and confidence boundaries needed for reviewed timeline/graph edges.
- Phase 4: discovery implementations conform to `DiscoveryProvider` in `discovery.py`.
  Providers return reviewable candidates and never silently write relationships. The included
  shared-affiliation provider demonstrates temporal-overlap leads while explicitly refusing
  to infer acquaintance or coordination.

### Phase 3 readiness

Accepted Phase 2 records already expose stable entity IDs, typed relationships, exact or
uncertain temporal ranges, event entities, source document/revision IDs, verified locators,
and claim/relationship evidence. A Phase 3 timeline can therefore query event and relationship
ranges without reading model output. A graph client can use accepted edges while displaying
proposal/quality state separately. Before large interactive collections, Phase 3 should add
pagination, graph-specific read endpoints, background-job cancellation, and OCR-derived page
geometry for image-only records. None of those changes require rewriting the accepted schema or
the Phase 2 approval boundary.

## Known limitations

The Vault uses lexical substring search rather than semantic retrieval, does not OCR image-only
PDFs, and has no user authentication because the server is enforced as loopback-only. Identity
suggestions are deterministic signals, not probabilistic adjudications; a human must confirm
matches. It does not automatically ingest the archive, invoke an LLM without an explicit
provider choice (and cloud consent where applicable), rank suspiciousness,
merge identities, or turn connection candidates into facts. Gemini cost is estimated unless the
provider exposes usage metadata. Very large proposal sets currently use JSON/CLI review without
pagination or a rich side-by-side visual diff.

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
