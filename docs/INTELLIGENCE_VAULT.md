# White Rabbit Intelligence Vault — Phase 1

## Purpose and architecture

The Vault is an additive, local, provenance-first subsystem. It does not replace the
Codex article, series, archive, Gemini, or distribution workflows. Its SQLite database is
`knowledge/intelligence_vault.db`, which is intentionally ignored by Git. Stable UUID-based
IDs separate identity from names. Versioned migrations run transactionally with foreign
keys enabled.

The model has four entity kinds (people, organizations, events, and places), aliases,
investigations, documents with immutable revisions, claims, claim evidence, relationships,
relationship evidence, conflicts, and merge suggestions. Historical start/end values each
retain precision and certainty. Source creation dates, historical dates, and import dates
are separate fields.

### Schema map

| Area | Tables | Purpose |
|---|---|---|
| Identity | `entities`, `aliases`, four `*_details` tables | Stable identity and type-specific metadata |
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
```

Manual commands include `add-entity`, `add-claim`, and `add-relationship`; use `--help`
on any command for arguments. The web API supports `POST /api/entities`, `/api/claims`,
and `/api/relationships`, plus `PATCH /api/entities/<id>`.

## Structured import format

The JSON format is schema-versioned and validated by Pydantic. Entity and claim `ref`
values are local import references:

```json
{
  "schema_version": 1,
  "document": {"path": "memo.pdf", "title": "Memo", "authority_level": 2},
  "entities": [
    {"ref": "person-a", "entity_type": "person", "name": "Example Name", "aliases": []},
    {"ref": "unit-a", "entity_type": "organization", "name": "Example Unit", "aliases": []}
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

An unchanged file hash is idempotent. A changed file creates a new immutable revision;
older extracted text and evidence links remain intact. Exact name or alias collisions create
merge suggestions rather than automatic merges.
Copies at different paths with the same hash share one document identity while retaining
each observed location.

## Backup and recovery

Stop writers and copy `knowledge/intelligence_vault.db` plus any `-wal` and `-shm` files,
or use the `export` command for a portable JSON snapshot. Original source files are never
replaced. Recovery is copying a consistent SQLite backup back to the same location; test a
restored copy with `vault stats` before using it.

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
PDFs, has no authentication (loopback use only), and offers basic duplicate matching rather
than probabilistic entity resolution. It does not automatically ingest the archive, invoke an
LLM, rank suspiciousness, merge identities, or turn connection candidates into facts.
