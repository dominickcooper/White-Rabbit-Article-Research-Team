# White Rabbit Intelligence Vault — Phase 1

## Purpose and architecture

The Vault is an additive, local, provenance-first subsystem. It does not replace the
Codex article, series, archive, Gemini, or distribution workflows. Its SQLite database is
`knowledge/intelligence_vault.db`, which is intentionally ignored by Git. Original files are
preserved under the ignored `knowledge/intelligence_vault_evidence/` content-addressed archive.
Stable UUID-based
IDs separate identity from names. Versioned migrations run transactionally with foreign
keys enabled. Schema version 2 upgrades existing Phase 1 databases in place.

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

## Extension roadmap

- Phase 2: an extractor can emit the validated JSON package. It must preserve wording,
  locators, source type, dependency groups, and uncertainty; no API key is needed in Phase 1.
- Phase 3: timeline and graph clients can consume the entity profile/search APIs without
  changing storage. Add pagination before very large interactive datasets.
- Phase 4: discovery implementations conform to `DiscoveryProvider` in `discovery.py`.
  Providers return reviewable candidates and never silently write relationships. The included
  shared-affiliation provider demonstrates temporal-overlap leads while explicitly refusing
  to infer acquaintance or coordination.

## Known limitations

Phase 1 uses lexical substring search rather than semantic retrieval, does not OCR image-only
PDFs, and has no user authentication because the server is enforced as loopback-only. Identity
suggestions are deterministic signals, not probabilistic adjudications; a human must confirm
matches. It does not automatically ingest the archive, invoke an LLM, rank suspiciousness,
merge identities, or turn connection candidates into facts.

## Phase 1.1 verification

The Phase 1.1 hardening suite covers non-merging identity resolution, explicit known-ID
reuse, contextual match suggestions, mid-import rollback, content-addressed preservation,
schema-v1 migration, lossless export, complete backup/restore, four-state temporal overlap,
strict request parsing, origin/Host checks, body limits, and loopback-only binding. The full
repository regression run completed with **290 passing tests** and no failures.
