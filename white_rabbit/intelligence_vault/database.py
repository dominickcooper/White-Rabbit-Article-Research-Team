from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterator
from uuid import uuid4


LATEST_SCHEMA_VERSION = 2
ENTITY_TYPES = {"person", "organization", "event", "place"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_id(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


def normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _validate_temporal(value: dict[str, Any]) -> None:
    from .temporal import HistoricalDate
    raw = value.get("value")
    precision = value.get("precision", "unknown")
    certainty = value.get("certainty", "unknown")
    if precision not in {"exact", "month", "year", "approximate", "unknown"}:
        raise ValueError(f"unsupported historical date precision: {precision}")
    if certainty not in {"certain", "probable", "possible", "uncertain", "unknown"}:
        raise ValueError(f"unsupported historical date certainty: {certainty}")
    if raw is None and precision != "unknown":
        raise ValueError("a missing historical date must use unknown precision")
    HistoricalDate(raw, precision, certainty).bounds()


MIGRATIONS = [
    (1, """
    CREATE TABLE entities (
      id TEXT PRIMARY KEY, entity_type TEXT NOT NULL CHECK(entity_type IN ('person','organization','event','place')),
      canonical_name TEXT NOT NULL, normalized_name TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE INDEX idx_entities_name ON entities(normalized_name);
    CREATE TABLE aliases (
      id INTEGER PRIMARY KEY, entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
      alias TEXT NOT NULL, normalized_alias TEXT NOT NULL, alias_type TEXT NOT NULL DEFAULT 'alias',
      UNIQUE(entity_id, normalized_alias)
    );
    CREATE INDEX idx_aliases_name ON aliases(normalized_alias);
    CREATE TABLE person_details (
      entity_id TEXT PRIMARY KEY REFERENCES entities(id) ON DELETE CASCADE,
      birth_value TEXT, birth_precision TEXT NOT NULL DEFAULT 'unknown', death_value TEXT,
      death_precision TEXT NOT NULL DEFAULT 'unknown', biography TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE organization_details (
      entity_id TEXT PRIMARY KEY REFERENCES entities(id) ON DELETE CASCADE,
      organization_kind TEXT NOT NULL DEFAULT 'other'
    );
    CREATE TABLE event_details (
      entity_id TEXT PRIMARY KEY REFERENCES entities(id) ON DELETE CASCADE,
      event_kind TEXT NOT NULL DEFAULT 'other', start_value TEXT, start_precision TEXT NOT NULL DEFAULT 'unknown',
      end_value TEXT, end_precision TEXT NOT NULL DEFAULT 'unknown', date_certainty TEXT NOT NULL DEFAULT 'unknown'
    );
    CREATE TABLE place_details (
      entity_id TEXT PRIMARY KEY REFERENCES entities(id) ON DELETE CASCADE,
      place_kind TEXT NOT NULL DEFAULT 'other', address TEXT, latitude REAL, longitude REAL
    );
    CREATE TABLE investigations (
      id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL
    );
    CREATE TABLE entity_investigations (
      entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
      investigation_id TEXT NOT NULL REFERENCES investigations(id) ON DELETE CASCADE,
      notes TEXT NOT NULL DEFAULT '', PRIMARY KEY(entity_id, investigation_id)
    );
    CREATE TABLE documents (
      id TEXT PRIMARY KEY, title TEXT NOT NULL, author TEXT, document_date TEXT,
      source_classification TEXT NOT NULL DEFAULT 'author_supplied', authority_level INTEGER NOT NULL DEFAULT 2,
      original_file TEXT, original_url TEXT, current_revision_id TEXT, imported_at TEXT NOT NULL,
      CHECK(original_file IS NOT NULL OR original_url IS NOT NULL)
    );
    CREATE UNIQUE INDEX idx_documents_file ON documents(original_file) WHERE original_file IS NOT NULL;
    CREATE UNIQUE INDEX idx_documents_url ON documents(original_url) WHERE original_url IS NOT NULL;
    CREATE TABLE document_locations (
      id INTEGER PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      location TEXT NOT NULL UNIQUE, location_kind TEXT NOT NULL, first_seen TEXT NOT NULL
    );
    CREATE TABLE document_revisions (
      id TEXT PRIMARY KEY, document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      revision_number INTEGER NOT NULL, file_hash TEXT NOT NULL, byte_size INTEGER NOT NULL DEFAULT 0,
      extracted_text TEXT NOT NULL DEFAULT '', imported_at TEXT NOT NULL,
      UNIQUE(document_id, revision_number), UNIQUE(document_id, file_hash)
    );
    CREATE TABLE claims (
      id TEXT PRIMARY KEY, statement TEXT NOT NULL, normalized_statement TEXT NOT NULL,
      original_wording TEXT, claim_type TEXT NOT NULL, epistemic_status TEXT NOT NULL,
      historical_start TEXT, historical_start_precision TEXT NOT NULL DEFAULT 'unknown',
      historical_start_certainty TEXT NOT NULL DEFAULT 'unknown', historical_end TEXT,
      historical_end_precision TEXT NOT NULL DEFAULT 'unknown', historical_end_certainty TEXT NOT NULL DEFAULT 'unknown',
      created_at TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE INDEX idx_claims_statement ON claims(normalized_statement);
    CREATE TABLE claim_evidence (
      claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
      revision_id TEXT NOT NULL REFERENCES document_revisions(id) ON DELETE CASCADE,
      locator TEXT NOT NULL DEFAULT '', original_wording TEXT, independent INTEGER NOT NULL DEFAULT 1,
      dependency_group TEXT, PRIMARY KEY(claim_id, revision_id, locator)
    );
    CREATE TABLE claim_entities (
      claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
      entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
      role TEXT NOT NULL DEFAULT 'subject', PRIMARY KEY(claim_id, entity_id, role)
    );
    CREATE TABLE relationships (
      id TEXT PRIMARY KEY, subject_entity_id TEXT NOT NULL REFERENCES entities(id),
      object_entity_id TEXT NOT NULL REFERENCES entities(id), relationship_type TEXT NOT NULL,
      directed INTEGER NOT NULL DEFAULT 1, classification TEXT NOT NULL,
      historical_start TEXT, historical_start_precision TEXT NOT NULL DEFAULT 'unknown',
      historical_start_certainty TEXT NOT NULL DEFAULT 'unknown', historical_end TEXT,
      historical_end_precision TEXT NOT NULL DEFAULT 'unknown', historical_end_certainty TEXT NOT NULL DEFAULT 'unknown',
      created_at TEXT NOT NULL, CHECK(subject_entity_id != object_entity_id)
    );
    CREATE INDEX idx_relationship_subject ON relationships(subject_entity_id);
    CREATE INDEX idx_relationship_object ON relationships(object_entity_id);
    CREATE TABLE relationship_evidence (
      relationship_id TEXT NOT NULL REFERENCES relationships(id) ON DELETE CASCADE,
      revision_id TEXT NOT NULL REFERENCES document_revisions(id) ON DELETE CASCADE,
      claim_id TEXT REFERENCES claims(id) ON DELETE SET NULL, locator TEXT NOT NULL DEFAULT '',
      original_wording TEXT, PRIMARY KEY(relationship_id, revision_id, locator)
    );
    CREATE TABLE conflicts (
      id TEXT PRIMARY KEY, claim_a_id TEXT NOT NULL REFERENCES claims(id),
      claim_b_id TEXT NOT NULL REFERENCES claims(id), reason TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'open', requires_author_review INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL, CHECK(claim_a_id != claim_b_id)
    );
    CREATE TABLE merge_suggestions (
      id TEXT PRIMARY KEY, entity_a_id TEXT NOT NULL REFERENCES entities(id),
      entity_b_id TEXT NOT NULL REFERENCES entities(id), reason TEXT NOT NULL,
      score REAL NOT NULL, status TEXT NOT NULL DEFAULT 'open', created_at TEXT NOT NULL,
      CHECK(entity_a_id != entity_b_id)
    );
    """),
    (2, """
    ALTER TABLE document_revisions ADD COLUMN archived_path TEXT;
    ALTER TABLE merge_suggestions ADD COLUMN evidence_json TEXT NOT NULL DEFAULT '{}';
    ALTER TABLE person_details ADD COLUMN birth_certainty TEXT NOT NULL DEFAULT 'unknown';
    ALTER TABLE person_details ADD COLUMN death_certainty TEXT NOT NULL DEFAULT 'unknown';
    ALTER TABLE event_details ADD COLUMN start_certainty TEXT NOT NULL DEFAULT 'unknown';
    ALTER TABLE event_details ADD COLUMN end_certainty TEXT NOT NULL DEFAULT 'unknown';
    CREATE TABLE import_entity_bindings (
      document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
      import_ref TEXT NOT NULL,
      entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE RESTRICT,
      created_at TEXT NOT NULL,
      PRIMARY KEY(document_id, import_ref)
    );
    """)
]


class VaultDB:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self._savepoint_number = 0
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.migrate()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "VaultDB":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        if self.conn.in_transaction:
            self._savepoint_number += 1
            name = f"vault_sp_{self._savepoint_number}"
            self.conn.execute(f"SAVEPOINT {name}")
            try:
                yield self.conn
            except Exception:
                self.conn.execute(f"ROLLBACK TO {name}")
                self.conn.execute(f"RELEASE {name}")
                raise
            else:
                self.conn.execute(f"RELEASE {name}")
            return
        try:
            self.conn.execute("BEGIN IMMEDIATE")
            yield self.conn
        except Exception:
            self.conn.rollback()
            raise
        else:
            self.conn.commit()

    def migrate(self) -> None:
        current = int(self.conn.execute("PRAGMA user_version").fetchone()[0])
        if current > LATEST_SCHEMA_VERSION:
            raise RuntimeError(f"Vault schema {current} is newer than supported version {LATEST_SCHEMA_VERSION}")
        for version, sql in MIGRATIONS:
            if version > current:
                try:
                    self.conn.executescript(
                        "BEGIN IMMEDIATE;\n" + sql + f"\nPRAGMA user_version={version};\nCOMMIT;"
                    )
                except Exception:
                    if self.conn.in_transaction:
                        self.conn.rollback()
                    raise

    def add_entity(self, entity_type: str, name: str, *, aliases: list[str] | None = None,
                   description: str = "", details: dict[str, Any] | None = None) -> str:
        if entity_type not in ENTITY_TYPES or not name.strip() or len(name) > 500:
            raise ValueError("valid entity_type and name are required")
        entity_id, now = _stable_id("ENT"), _now()
        with self.transaction():
            self.conn.execute(
                "INSERT INTO entities VALUES (?,?,?,?,?,?,?)",
                (entity_id, entity_type, name.strip(), normalize_name(name), description, now, now),
            )
            for alias in aliases or []:
                self.add_alias(entity_id, alias, commit=False)
            table = {"person": "person_details", "organization": "organization_details",
                     "event": "event_details", "place": "place_details"}[entity_type]
            self.conn.execute(f"INSERT INTO {table}(entity_id) VALUES (?)", (entity_id,))
            if details:
                allowed = {
                    "person": {"birth_value", "birth_precision", "birth_certainty", "death_value", "death_precision", "death_certainty", "biography"},
                    "organization": {"organization_kind"},
                    "event": {"event_kind", "start_value", "start_precision", "start_certainty", "end_value", "end_precision", "end_certainty", "date_certainty"},
                    "place": {"place_kind", "address", "latitude", "longitude"},
                }[entity_type]
                values = {key: value for key, value in details.items() if key in allowed}
                if entity_type == "person":
                    for prefix in ("birth", "death"):
                        if values.get(f"{prefix}_value"):
                            _validate_temporal({
                                "value": values[f"{prefix}_value"],
                                "precision": values.get(f"{prefix}_precision", "unknown"),
                                "certainty": values.get(f"{prefix}_certainty", "unknown"),
                            })
                elif entity_type == "event":
                    for prefix in ("start", "end"):
                        if values.get(f"{prefix}_value"):
                            _validate_temporal({
                                "value": values[f"{prefix}_value"],
                                "precision": values.get(f"{prefix}_precision", "unknown"),
                                "certainty": values.get(f"{prefix}_certainty", values.get("date_certainty", "unknown")),
                            })
                if values:
                    self.conn.execute(
                        f"UPDATE {table} SET " + ",".join(f"{key}=?" for key in values) + " WHERE entity_id=?",
                        (*values.values(), entity_id),
                    )
            self._create_duplicate_suggestions(entity_id, entity_type, [name, *(aliases or [])])
        return entity_id

    def add_alias(self, entity_id: str, alias: str, *, alias_type: str = "alias", commit: bool = True) -> None:
        if not alias.strip():
            return
        if commit:
            with self.transaction():
                self.conn.execute(
                    "INSERT OR IGNORE INTO aliases(entity_id,alias,normalized_alias,alias_type) VALUES (?,?,?,?)",
                    (entity_id, alias.strip(), normalize_name(alias), alias_type),
                )
        else:
            self.conn.execute(
                "INSERT OR IGNORE INTO aliases(entity_id,alias,normalized_alias,alias_type) VALUES (?,?,?,?)",
                (entity_id, alias.strip(), normalize_name(alias), alias_type),
            )

    def _create_duplicate_suggestions(self, entity_id: str, entity_type: str, names: list[str]) -> None:
        normalized = {normalize_name(n) for n in names if normalize_name(n)}
        if not normalized:
            return
        marks = ",".join("?" for _ in normalized)
        rows = self.conn.execute(
            f"""SELECT DISTINCT e.id FROM entities e LEFT JOIN aliases a ON a.entity_id=e.id
                WHERE e.id != ? AND e.entity_type=? AND
                (e.normalized_name IN ({marks}) OR a.normalized_alias IN ({marks}))""",
            (entity_id, entity_type, *normalized, *normalized),
        ).fetchall()
        for row in rows:
            a, b = sorted((entity_id, row["id"]))
            exists = self.conn.execute(
                "SELECT 1 FROM merge_suggestions WHERE entity_a_id=? AND entity_b_id=? AND status='open'", (a, b)
            ).fetchone()
            if not exists:
                self.conn.execute(
                    """INSERT INTO merge_suggestions(
                           id,entity_a_id,entity_b_id,reason,score,status,created_at,evidence_json
                       ) VALUES (?,?,?,?,?,?,?,?)""",
                    (_stable_id("MERGE"), a, b, "possible name or alias match", 0.25, "open", _now(),
                     json.dumps({"signals": ["name_or_alias_match"]})),
                )

    def resolve_entity(self, name: str, entity_type: str | None = None) -> list[dict[str, Any]]:
        norm = normalize_name(name)
        params: list[Any] = [norm, norm]
        type_sql = ""
        if entity_type:
            type_sql, params = " AND e.entity_type=?", [norm, norm, entity_type]
        rows = self.conn.execute(
            """SELECT DISTINCT e.* FROM entities e LEFT JOIN aliases a ON a.entity_id=e.id
               WHERE (e.normalized_name=? OR a.normalized_alias=?)""" + type_sql + " ORDER BY e.canonical_name",
            params,
        ).fetchall()
        return [dict(r) for r in rows]

    def get_import_binding(self, document_id: str, import_ref: str) -> str | None:
        row = self.conn.execute(
            "SELECT entity_id FROM import_entity_bindings WHERE document_id=? AND import_ref=?",
            (document_id, import_ref),
        ).fetchone()
        return str(row["entity_id"]) if row else None

    def bind_import_entity(self, document_id: str, import_ref: str, entity_id: str) -> None:
        existing = self.get_import_binding(document_id, import_ref)
        if existing and existing != entity_id:
            raise ValueError(f"import ref {import_ref!r} is already bound to {existing}")
        with self.transaction():
            self.conn.execute(
                "INSERT OR IGNORE INTO import_entity_bindings VALUES (?,?,?,?)",
                (document_id, import_ref, entity_id, _now()),
            )

    def validate_known_entity(self, entity_id: str, entity_type: str) -> None:
        row = self.conn.execute("SELECT entity_type FROM entities WHERE id=?", (entity_id,)).fetchone()
        if not row:
            raise ValueError(f"unknown known_entity_id: {entity_id}")
        if row["entity_type"] != entity_type:
            raise ValueError(f"known_entity_id {entity_id} is {row['entity_type']}, not {entity_type}")

    def refresh_match_suggestions(self, entity_id: str) -> None:
        entity = self.conn.execute("SELECT * FROM entities WHERE id=?", (entity_id,)).fetchone()
        if not entity:
            raise KeyError(entity_id)
        names = {entity["normalized_name"], *(
            row[0] for row in self.conn.execute("SELECT normalized_alias FROM aliases WHERE entity_id=?", (entity_id,))
        )}
        marks = ",".join("?" for _ in names)
        candidates = self.conn.execute(
            f"""SELECT DISTINCT e.id FROM entities e LEFT JOIN aliases a ON a.entity_id=e.id
                WHERE e.id != ? AND e.entity_type=? AND
                (e.normalized_name IN ({marks}) OR a.normalized_alias IN ({marks}))""",
            (entity_id, entity["entity_type"], *names, *names),
        ).fetchall()
        with self.transaction():
            for candidate in candidates:
                other_id = str(candidate["id"])
                signals, conflicts, score = self._identity_comparison(entity_id, other_id)
                a, b = sorted((entity_id, other_id))
                evidence = json.dumps({"signals": signals, "conflicts": conflicts}, ensure_ascii=False)
                reason = "; ".join(signals + conflicts) or "possible identity match"
                existing = self.conn.execute(
                    "SELECT id FROM merge_suggestions WHERE entity_a_id=? AND entity_b_id=? AND status='open'", (a, b)
                ).fetchone()
                if existing:
                    self.conn.execute(
                        "UPDATE merge_suggestions SET reason=?,score=?,evidence_json=? WHERE id=?",
                        (reason, score, evidence, existing["id"]),
                    )
                else:
                    self.conn.execute(
                        "INSERT INTO merge_suggestions VALUES (?,?,?,?,?,?,?,?)",
                        (_stable_id("MERGE"), a, b, reason, score, "open", _now(), evidence),
                    )

    def _identity_comparison(self, entity_a: str, entity_b: str) -> tuple[list[str], list[str], float]:
        signals = ["name or alias match"]
        conflicts: list[str] = []
        score = 0.25
        kinds = self.conn.execute(
            "SELECT id,entity_type FROM entities WHERE id IN (?,?)", (entity_a, entity_b)
        ).fetchall()
        if kinds and kinds[0]["entity_type"] == "person":
            details = {row["entity_id"]: row for row in self.conn.execute(
                "SELECT * FROM person_details WHERE entity_id IN (?,?)", (entity_a, entity_b)
            )}
            for field, weight in (("birth_value", 0.25), ("death_value", 0.15)):
                left, right = details[entity_a][field], details[entity_b][field]
                label = field.removesuffix("_value")
                if left and right:
                    from .temporal import HistoricalDate
                    prefix = field.removesuffix("_value")
                    left_bounds = HistoricalDate(
                        left, details[entity_a][f"{prefix}_precision"],
                        details[entity_a][f"{prefix}_certainty"],
                    ).bounds()
                    right_bounds = HistoricalDate(
                        right, details[entity_b][f"{prefix}_precision"],
                        details[entity_b][f"{prefix}_certainty"],
                    ).bounds()
                    compatible = left_bounds[0] <= right_bounds[1] and right_bounds[0] <= left_bounds[1]
                    if compatible:
                        qualifier = "matching" if left == right else "compatible"
                        signals.append(f"{qualifier} {label} dates {left} and {right}")
                        score += weight if left == right else weight / 2
                    else:
                        conflicts.append(f"conflicting {label} dates {left} and {right}")
                        score -= weight
        relationships: dict[str, list[sqlite3.Row]] = {}
        for item in (entity_a, entity_b):
            relationships[item] = self.conn.execute(
                """SELECT r.*, e.canonical_name object_name, e.entity_type object_type
                   FROM relationships r JOIN entities e ON e.id=r.object_entity_id
                   WHERE r.subject_entity_id=?""", (item,)
            ).fetchall()
        from .temporal import HistoricalDate, OverlapResult, ranges_overlap
        for left in relationships[entity_a]:
            for right in relationships[entity_b]:
                if left["relationship_type"] != right["relationship_type"] or left["object_entity_id"] != right["object_entity_id"]:
                    continue
                overlap = ranges_overlap(
                    HistoricalDate(left["historical_start"], left["historical_start_precision"], left["historical_start_certainty"]),
                    HistoricalDate(left["historical_end"], left["historical_end_precision"], left["historical_end_certainty"]),
                    HistoricalDate(right["historical_start"], right["historical_start_precision"], right["historical_start_certainty"]),
                    HistoricalDate(right["historical_end"], right["historical_end_precision"], right["historical_end_certainty"]),
                )
                context = "location" if left["object_type"] == "place" else "organization/role"
                signals.append(
                    f"shared {context}: {left['relationship_type']} {left['object_name']} ({overlap.value})"
                )
                score += 0.2 if overlap == OverlapResult.DEFINITE_OVERLAP else 0.1
        return signals, conflicts, max(0.0, min(1.0, score))

    def get_entity(self, entity_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM entities WHERE id=?", (entity_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        detail_table = {"person": "person_details", "organization": "organization_details",
                        "event": "event_details", "place": "place_details"}[row["entity_type"]]
        details = self.conn.execute(f"SELECT * FROM {detail_table} WHERE entity_id=?", (entity_id,)).fetchone()
        result["details"] = dict(details) if details else {}
        result["aliases"] = [r[0] for r in self.conn.execute("SELECT alias FROM aliases WHERE entity_id=?", (entity_id,))]
        result["relationships"] = [dict(r) for r in self.conn.execute(
            """SELECT r.*, s.canonical_name subject_name, o.canonical_name object_name
               FROM relationships r JOIN entities s ON s.id=r.subject_entity_id
               JOIN entities o ON o.id=r.object_entity_id
               WHERE r.subject_entity_id=? OR r.object_entity_id=? ORDER BY r.created_at""", (entity_id, entity_id))]
        result["claims"] = [dict(r) for r in self.conn.execute(
            "SELECT c.* FROM claims c JOIN claim_entities ce ON ce.claim_id=c.id WHERE ce.entity_id=?", (entity_id,))]
        for claim in result["claims"]:
            claim["evidence"] = [dict(r) for r in self.conn.execute(
                """SELECT ce.*, d.title document_title, d.original_file, d.original_url, dr.file_hash
                   FROM claim_evidence ce JOIN document_revisions dr ON dr.id=ce.revision_id
                   JOIN documents d ON d.id=dr.document_id WHERE ce.claim_id=?""", (claim["id"],))]
        for relationship in result["relationships"]:
            relationship["evidence"] = [dict(r) for r in self.conn.execute(
                """SELECT re.*, d.title document_title, d.original_file, d.original_url, dr.file_hash
                   FROM relationship_evidence re JOIN document_revisions dr ON dr.id=re.revision_id
                   JOIN documents d ON d.id=dr.document_id WHERE re.relationship_id=?""", (relationship["id"],))]
        return result

    def update_entity(self, entity_id: str, **changes: Any) -> None:
        allowed = {"canonical_name", "description"}
        fields = {k: v for k, v in changes.items() if k in allowed}
        if not fields:
            return
        if "canonical_name" in fields:
            fields["normalized_name"] = normalize_name(fields["canonical_name"])
        fields["updated_at"] = _now()
        sql = ",".join(f"{key}=?" for key in fields)
        with self.transaction():
            cur = self.conn.execute(f"UPDATE entities SET {sql} WHERE id=?", (*fields.values(), entity_id))
            if cur.rowcount != 1:
                raise KeyError(entity_id)

    def add_investigation(self, name: str, description: str = "") -> str:
        existing = self.conn.execute("SELECT id FROM investigations WHERE name=?", (name,)).fetchone()
        if existing:
            return str(existing["id"])
        investigation_id = _stable_id("INV")
        with self.transaction():
            self.conn.execute(
                "INSERT INTO investigations VALUES (?,?,?,?)", (investigation_id, name, description, _now())
            )
        return investigation_id

    def attach_investigation(self, entity_id: str, investigation_id: str, notes: str = "") -> None:
        with self.transaction():
            self.conn.execute(
                "INSERT OR REPLACE INTO entity_investigations VALUES (?,?,?)",
                (entity_id, investigation_id, notes),
            )

    def add_document_revision(self, *, title: str, file_hash: str, extracted_text: str,
                              byte_size: int = 0, original_file: str | None = None,
                              original_url: str | None = None, author: str | None = None,
                              document_date: str | None = None, source_classification: str = "author_supplied",
                              authority_level: int = 2, archived_path: str | None = None) -> tuple[str, str, bool]:
        if not original_file and not original_url:
            raise ValueError("original_file or original_url is required")
        field, value = ("original_file", original_file) if original_file else ("original_url", original_url)
        existing = self.conn.execute(f"SELECT * FROM documents WHERE {field}=?", (value,)).fetchone()
        now = _now()
        with self.transaction():
            if existing:
                same = self.conn.execute(
                    "SELECT id FROM document_revisions WHERE document_id=? AND file_hash=?",
                    (existing["id"], file_hash),
                ).fetchone()
                if same:
                    if archived_path:
                        self.conn.execute(
                            "UPDATE document_revisions SET archived_path=COALESCE(archived_path,?) WHERE id=?",
                            (archived_path, same["id"]),
                        )
                    return existing["id"], same["id"], False
                document_id = existing["id"]
                number = int(self.conn.execute(
                    "SELECT COALESCE(MAX(revision_number),0)+1 FROM document_revisions WHERE document_id=?", (document_id,)
                ).fetchone()[0])
            else:
                duplicate = self.conn.execute(
                    """SELECT d.id document_id, dr.id revision_id FROM document_revisions dr
                       JOIN documents d ON d.id=dr.document_id WHERE dr.file_hash=? LIMIT 1""", (file_hash,)
                ).fetchone()
                if duplicate:
                    self.conn.execute(
                        "INSERT OR IGNORE INTO document_locations(document_id,location,location_kind,first_seen) VALUES (?,?,?,?)",
                        (duplicate["document_id"], value, "file" if original_file else "url", now),
                    )
                    if archived_path:
                        self.conn.execute(
                            "UPDATE document_revisions SET archived_path=COALESCE(archived_path,?) WHERE id=?",
                            (archived_path, duplicate["revision_id"]),
                        )
                    return str(duplicate["document_id"]), str(duplicate["revision_id"]), False
                document_id, number = _stable_id("DOC"), 1
                self.conn.execute(
                    "INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (document_id, title, author, document_date, source_classification, authority_level,
                     original_file, original_url, None, now),
                )
                self.conn.execute(
                    "INSERT INTO document_locations(document_id,location,location_kind,first_seen) VALUES (?,?,?,?)",
                    (document_id, value, "file" if original_file else "url", now),
                )
            revision_id = _stable_id("REV")
            self.conn.execute(
                """INSERT INTO document_revisions(
                       id,document_id,revision_number,file_hash,byte_size,extracted_text,imported_at,archived_path
                   ) VALUES (?,?,?,?,?,?,?,?)""",
                (revision_id, document_id, number, file_hash, byte_size, extracted_text, now, archived_path),
            )
            self.conn.execute(
                "UPDATE documents SET title=?, author=COALESCE(?,author), document_date=COALESCE(?,document_date), current_revision_id=? WHERE id=?",
                (title, author, document_date, revision_id, document_id),
            )
        return document_id, revision_id, True

    def get_document(self, document_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        if not row:
            return None
        result = dict(row)
        result["locations"] = [dict(r) for r in self.conn.execute(
            "SELECT location, location_kind, first_seen FROM document_locations WHERE document_id=? ORDER BY id", (document_id,))]
        result["revisions"] = [dict(r) for r in self.conn.execute(
            "SELECT id, revision_number, file_hash, byte_size, imported_at, archived_path FROM document_revisions WHERE document_id=? ORDER BY revision_number",
            (document_id,),
        )]
        result["claims"] = [dict(r) for r in self.conn.execute(
            """SELECT c.*, ce.revision_id, ce.locator, ce.original_wording evidence_wording,
                      ce.independent, ce.dependency_group
               FROM claims c JOIN claim_evidence ce ON ce.claim_id=c.id
               JOIN document_revisions dr ON dr.id=ce.revision_id WHERE dr.document_id=?""", (document_id,))]
        result["relationships"] = [dict(r) for r in self.conn.execute(
            """SELECT rel.*, re.revision_id, re.locator, re.original_wording evidence_wording
               FROM relationships rel JOIN relationship_evidence re ON re.relationship_id=rel.id
               JOIN document_revisions dr ON dr.id=re.revision_id WHERE dr.document_id=?""", (document_id,))]
        return result

    def archived_file(self, archived_path: str) -> Path:
        root = (self.path.resolve().parent / "intelligence_vault_evidence").resolve()
        candidate = (root / archived_path).resolve()
        if not candidate.is_relative_to(root):
            raise ValueError("archived path escapes the evidence archive")
        return candidate

    def add_claim(self, statement: str, *, original_wording: str | None = None,
                  claim_type: str = "fact", status: str = "DOCUMENTED RECORD",
                  historical_start: dict[str, Any] | None = None, historical_end: dict[str, Any] | None = None,
                  entity_ids: list[str] | None = None) -> str:
        start, end = historical_start or {}, historical_end or {}
        _validate_temporal(start)
        _validate_temporal(end)
        if not statement.strip() or len(statement) > 10000:
            raise ValueError("claim statement must contain 1-10000 characters")
        normalized = normalize_name(statement)
        existing = self.conn.execute(
            "SELECT id FROM claims WHERE normalized_statement=? AND claim_type=? AND epistemic_status=?",
            (normalized, claim_type, status),
        ).fetchone()
        if existing:
            with self.transaction():
                for entity_id in entity_ids or []:
                    self.conn.execute(
                        "INSERT OR IGNORE INTO claim_entities VALUES (?,?,?)", (existing["id"], entity_id, "subject")
                    )
            return str(existing["id"])
        claim_id, now = _stable_id("CLM"), _now()
        with self.transaction():
            self.conn.execute(
                "INSERT INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (claim_id, statement.strip(), normalized, original_wording, claim_type, status,
                 start.get("value"), start.get("precision", "unknown"), start.get("certainty", "unknown"),
                 end.get("value"), end.get("precision", "unknown"), end.get("certainty", "unknown"), now, now),
            )
            for entity_id in entity_ids or []:
                self.conn.execute("INSERT OR IGNORE INTO claim_entities VALUES (?,?,?)", (claim_id, entity_id, "subject"))
        return claim_id

    def add_claim_evidence(self, claim_id: str, revision_id: str, *, locator: str = "",
                           original_wording: str | None = None, independent: bool = True,
                           dependency_group: str | None = None) -> None:
        with self.transaction():
            self.conn.execute(
                "INSERT OR IGNORE INTO claim_evidence VALUES (?,?,?,?,?,?)",
                (claim_id, revision_id, locator, original_wording, int(independent), dependency_group),
            )

    def update_claim(self, claim_id: str, **changes: Any) -> None:
        allowed = {"statement", "original_wording", "claim_type", "epistemic_status",
                   "historical_start", "historical_start_precision", "historical_start_certainty",
                   "historical_end", "historical_end_precision", "historical_end_certainty"}
        fields = {key: value for key, value in changes.items() if key in allowed}
        if not fields:
            return
        current = self.conn.execute("SELECT * FROM claims WHERE id=?", (claim_id,)).fetchone()
        if not current:
            raise KeyError(claim_id)
        _validate_temporal({
            "value": fields.get("historical_start", current["historical_start"]),
            "precision": fields.get("historical_start_precision", current["historical_start_precision"]),
            "certainty": fields.get("historical_start_certainty", current["historical_start_certainty"]),
        })
        _validate_temporal({
            "value": fields.get("historical_end", current["historical_end"]),
            "precision": fields.get("historical_end_precision", current["historical_end_precision"]),
            "certainty": fields.get("historical_end_certainty", current["historical_end_certainty"]),
        })
        if "statement" in fields:
            fields["normalized_statement"] = normalize_name(fields["statement"])
        fields["updated_at"] = _now()
        with self.transaction():
            cur = self.conn.execute(
                "UPDATE claims SET " + ",".join(f"{key}=?" for key in fields) + " WHERE id=?",
                (*fields.values(), claim_id),
            )
            if cur.rowcount != 1:
                raise KeyError(claim_id)

    def add_relationship(self, subject_id: str, object_id: str, relationship_type: str, *, directed: bool = True,
                         classification: str = "DOCUMENTED RECORD", historical_start: dict[str, Any] | None = None,
                         historical_end: dict[str, Any] | None = None, revision_id: str | None = None,
                         claim_id: str | None = None, locator: str = "", original_wording: str | None = None) -> str:
        start, end = historical_start or {}, historical_end or {}
        _validate_temporal(start)
        _validate_temporal(end)
        if not relationship_type.strip() or len(relationship_type) > 200:
            raise ValueError("relationship_type must contain 1-200 characters")
        existing = self.conn.execute(
            """SELECT id FROM relationships WHERE subject_entity_id=? AND object_entity_id=?
               AND relationship_type=? AND directed=? AND classification=?
               AND COALESCE(historical_start,'')=COALESCE(?,'') AND COALESCE(historical_end,'')=COALESCE(?,'')""",
            (subject_id, object_id, relationship_type, int(directed), classification, start.get("value"), end.get("value")),
        ).fetchone()
        rel_id = str(existing["id"]) if existing else _stable_id("REL")
        with self.transaction():
            if not existing:
                self.conn.execute("INSERT INTO relationships VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                                  (rel_id, subject_id, object_id, relationship_type, int(directed), classification,
                                   start.get("value"), start.get("precision", "unknown"), start.get("certainty", "unknown"),
                                   end.get("value"), end.get("precision", "unknown"), end.get("certainty", "unknown"), _now()))
            if revision_id:
                self.conn.execute("INSERT OR IGNORE INTO relationship_evidence VALUES (?,?,?,?,?)",
                                  (rel_id, revision_id, claim_id, locator, original_wording))
        return rel_id

    def add_conflict(self, claim_a_id: str, claim_b_id: str, *, reason: str = "",
                     requires_author_review: bool = True) -> str:
        existing = self.conn.execute(
            """SELECT id FROM conflicts WHERE ((claim_a_id=? AND claim_b_id=?) OR (claim_a_id=? AND claim_b_id=?))
               AND reason=? AND status='open'""", (claim_a_id, claim_b_id, claim_b_id, claim_a_id, reason)
        ).fetchone()
        if existing:
            return str(existing["id"])
        conflict_id = _stable_id("CONFLICT")
        with self.transaction():
            self.conn.execute(
                "INSERT INTO conflicts VALUES (?,?,?,?,?,?,?)",
                (conflict_id, claim_a_id, claim_b_id, reason, "open", int(requires_author_review), _now()),
            )
        return conflict_id

    def update_relationship(self, relationship_id: str, **changes: Any) -> None:
        allowed = {"relationship_type", "directed", "classification", "historical_start",
                   "historical_start_precision", "historical_start_certainty", "historical_end",
                   "historical_end_precision", "historical_end_certainty"}
        fields = {key: value for key, value in changes.items() if key in allowed}
        if not fields:
            return
        current = self.conn.execute("SELECT * FROM relationships WHERE id=?", (relationship_id,)).fetchone()
        if not current:
            raise KeyError(relationship_id)
        _validate_temporal({
            "value": fields.get("historical_start", current["historical_start"]),
            "precision": fields.get("historical_start_precision", current["historical_start_precision"]),
            "certainty": fields.get("historical_start_certainty", current["historical_start_certainty"]),
        })
        _validate_temporal({
            "value": fields.get("historical_end", current["historical_end"]),
            "precision": fields.get("historical_end_precision", current["historical_end_precision"]),
            "certainty": fields.get("historical_end_certainty", current["historical_end_certainty"]),
        })
        with self.transaction():
            cur = self.conn.execute(
                "UPDATE relationships SET " + ",".join(f"{key}=?" for key in fields) + " WHERE id=?",
                (*fields.values(), relationship_id),
            )
            if cur.rowcount != 1:
                raise KeyError(relationship_id)

    def search(self, query: str, entity_type: str | None = None, limit: int = 50) -> dict[str, list[dict[str, Any]]]:
        like = f"%{query.casefold()}%"
        type_clause, params = (" AND e.entity_type=?", [like, like, entity_type, limit]) if entity_type else ("", [like, like, limit])
        entities = self.conn.execute(
            """SELECT DISTINCT e.* FROM entities e LEFT JOIN aliases a ON a.entity_id=e.id
               WHERE (lower(e.canonical_name) LIKE ? OR lower(COALESCE(a.alias,'')) LIKE ?)""" + type_clause + " LIMIT ?", params
        ).fetchall()
        claims = self.conn.execute("SELECT * FROM claims WHERE lower(statement) LIKE ? LIMIT ?", (like, limit)).fetchall()
        documents = self.conn.execute("SELECT * FROM documents WHERE lower(title) LIKE ? LIMIT ?", (like, limit)).fetchall()
        return {"entities": [dict(r) for r in entities], "claims": [dict(r) for r in claims],
                "documents": [dict(r) for r in documents]}

    def events_between(self, start: str, end: str) -> list[dict[str, Any]]:
        return [dict(r) for r in self.conn.execute(
            """SELECT e.*, d.* FROM entities e JOIN event_details d ON d.entity_id=e.id
               WHERE COALESCE(d.start_value,'9999-12-31') <= ? AND COALESCE(d.end_value,d.start_value,'0001-01-01') >= ?
               ORDER BY d.start_value""", (end, start))]

    def list_review(self) -> dict[str, list[dict[str, Any]]]:
        return {
            "merge_suggestions": [dict(r) for r in self.conn.execute("SELECT * FROM merge_suggestions WHERE status='open'")],
            "conflicts": [dict(r) for r in self.conn.execute("SELECT * FROM conflicts WHERE status='open'")],
        }

    def stats(self) -> dict[str, int]:
        tables = ["entities", "documents", "document_revisions", "claims", "relationships", "conflicts", "merge_suggestions"]
        result = {table: int(self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) for table in tables}
        for kind in sorted(ENTITY_TYPES):
            result[kind] = int(self.conn.execute("SELECT COUNT(*) FROM entities WHERE entity_type=?", (kind,)).fetchone()[0])
        result["schema_version"] = int(self.conn.execute("PRAGMA user_version").fetchone()[0])
        return result

    def export(self) -> dict[str, Any]:
        tables = [
            "entities", "aliases", "person_details", "organization_details", "event_details", "place_details",
            "investigations", "entity_investigations", "documents", "document_locations", "document_revisions",
            "import_entity_bindings", "claims", "claim_evidence", "claim_entities", "relationships",
            "relationship_evidence", "conflicts", "merge_suggestions",
        ]
        return {"schema_version": LATEST_SCHEMA_VERSION,
                "exported_at": _now(),
                "tables": {table: [dict(r) for r in self.conn.execute(f"SELECT * FROM {table}")] for table in tables}}

    def backup_to(self, destination: Path | str) -> Path:
        if self.conn.in_transaction:
            raise RuntimeError("cannot create a backup while a write transaction is active")
        destination = Path(destination).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".tmp")
        if temporary.exists():
            temporary.unlink()
        target = sqlite3.connect(temporary)
        try:
            self.conn.backup(target)
            if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("backup integrity check failed")
        finally:
            target.close()
        temporary.replace(destination)
        return destination

    @staticmethod
    def restore_from(snapshot: Path | str, destination: Path | str) -> Path:
        snapshot, destination = Path(snapshot).resolve(), Path(destination).resolve()
        if not snapshot.is_file():
            raise FileNotFoundError(snapshot)
        if destination.exists():
            raise FileExistsError(f"restore destination already exists: {destination}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".restore-tmp")
        if temporary.exists():
            temporary.unlink()
        source = sqlite3.connect(snapshot)
        source.execute("PRAGMA query_only=ON")
        target = sqlite3.connect(temporary)
        try:
            if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("snapshot failed integrity check")
            source.backup(target)
        finally:
            source.close()
            target.close()
        temporary.replace(destination)
        return destination
