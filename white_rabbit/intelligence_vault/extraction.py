from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from .chunking import DocumentChunk, PreparedSource, SourceSpan, chunk_source, locate_passage, prepare_source
from .database import VaultDB, normalize_name
from .extraction_schema import ChunkExtraction
from .ingestion import ingest_document
from .ingestion import sha256_file
from .providers import ExtractionProvider


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4()}"


@dataclass(frozen=True)
class ExtractionConfig:
    chunk_size: int = 12000
    overlap: int = 1000
    max_chunks: int | None = None
    schema_version: int = 1

    def normalized(self) -> dict[str, Any]:
        return asdict(self)


def prepare_manual_packet(source_path: Path, output_directory: Path, *,
                          config: ExtractionConfig | None = None) -> Path:
    """Write local chunk packets that Codex or another offline tool can inspect."""
    config = config or ExtractionConfig()
    source_path, output_directory = source_path.resolve(), output_directory.resolve()
    if output_directory.exists() and any(output_directory.iterdir()):
        raise FileExistsError(f"manual packet directory is not empty: {output_directory}")
    output_directory.mkdir(parents=True, exist_ok=True)
    prepared = prepare_source(source_path)
    chunks = chunk_source(
        prepared, sha256_file(source_path), chunk_size=config.chunk_size,
        overlap=config.overlap, max_chunks=config.max_chunks,
    )
    manifest = {
        "format": "white-rabbit-vault-manual-extraction-packet", "version": 1,
        "source": str(source_path), "source_sha256": sha256_file(source_path),
        "config": config.normalized(), "chunk_count": len(chunks),
        "unreadable": prepared.unreadable,
    }
    (output_directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for chunk in chunks:
        (output_directory / f"chunk-{chunk.ordinal:05d}.json").write_text(json.dumps({
            "chunk_id": chunk.id, "ordinal": chunk.ordinal, "locator": chunk.locator,
            "source_start": chunk.source_start, "source_end": chunk.source_end,
            "text_hash": chunk.text_hash, "text": chunk.text,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_directory / "results.template.json").write_text(json.dumps({
        str(chunk.ordinal): {"entities": [], "claims": [], "relationships": [],
                             "document_metadata": [], "skipped_or_unreadable": [], "notes": []}
        for chunk in chunks
    }, indent=2), encoding="utf-8")
    return output_directory


def _config_hash(config: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()


def _job_row(db: VaultDB, job_id: str):
    row = db.conn.execute("SELECT * FROM extraction_jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        raise KeyError(f"unknown extraction job: {job_id}")
    return row


def create_extraction_job(db: VaultDB, source_path: Path, provider: ExtractionProvider, *,
                          config: ExtractionConfig | None = None,
                          allow_cloud: bool = False) -> tuple[str, bool]:
    config = config or ExtractionConfig()
    if provider.sends_data_off_device and not allow_cloud:
        raise PermissionError("cloud extraction requires explicit allow_cloud=True")
    document_id, revision_id, _ = ingest_document(db, source_path)
    return _create_extraction_job_for_prepared(
        db, document_id, revision_id, prepare_source(source_path), provider,
        config=config, allow_cloud=allow_cloud,
    )


def create_extraction_job_from_revision(db: VaultDB, revision_id: str, provider: ExtractionProvider, *,
                                        config: ExtractionConfig | None = None,
                                        allow_cloud: bool = False) -> tuple[str, bool]:
    """Stage AI proposals from an importer's stored derivative without duplicating the source document."""
    row = db.conn.execute(
        "SELECT document_id,extracted_text FROM document_revisions WHERE id=?", (revision_id,)
    ).fetchone()
    if not row:
        raise KeyError(f"unknown document revision: {revision_id}")
    text = row["extracted_text"] or ""
    spans, cursor = [], 0
    for number, line in enumerate(text.splitlines(keepends=True), start=1):
        spans.append(SourceSpan(cursor, cursor + len(line), line_start=number, line_end=number))
        cursor += len(line)
    prepared = PreparedSource(text, spans, ["source contained no readable text"] if not text.strip() else [])
    return _create_extraction_job_for_prepared(
        db, row["document_id"], revision_id, prepared, provider,
        config=config or ExtractionConfig(), allow_cloud=allow_cloud,
    )


def _create_extraction_job_for_prepared(db: VaultDB, document_id: str, revision_id: str,
                                        prepared: PreparedSource, provider: ExtractionProvider, *,
                                        config: ExtractionConfig,
                                        allow_cloud: bool) -> tuple[str, bool]:
    if provider.sends_data_off_device and not allow_cloud:
        raise PermissionError("cloud extraction requires explicit allow_cloud=True")
    revision = db.conn.execute("SELECT file_hash FROM document_revisions WHERE id=?", (revision_id,)).fetchone()
    if not revision:
        raise KeyError(f"unknown document revision: {revision_id}")
    config_data = {**config.normalized(), "provider_fingerprint": provider.fingerprint}
    digest = _config_hash(config_data)
    existing = db.conn.execute(
        """SELECT id FROM extraction_jobs
           WHERE revision_id=? AND provider=? AND model=? AND config_hash=?""",
        (revision_id, provider.name, provider.model, digest),
    ).fetchone()
    if existing:
        return str(existing["id"]), False

    chunks = chunk_source(
        prepared, revision["file_hash"], chunk_size=config.chunk_size,
        overlap=config.overlap, max_chunks=config.max_chunks,
    )
    job_id, now = _id("JOB"), _now()
    with db.transaction():
        db.conn.execute(
            """INSERT INTO extraction_jobs(
                   id,document_id,revision_id,provider,model,config_json,config_hash,status,
                   cloud_authorized,chunk_total,estimated_input_tokens,created_at,updated_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (job_id, document_id, revision_id, provider.name, provider.model,
             json.dumps(config_data), digest, "pending", int(allow_cloud), len(chunks),
             sum(max(1, len(chunk.text) // 4) for chunk in chunks), now, now),
        )
        for chunk in chunks:
            db.conn.execute(
                """INSERT INTO extraction_chunks(
                       id,job_id,ordinal,text_hash,source_start,source_end,locator_json,chunk_text,status,updated_at
                   ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (chunk.id, job_id, chunk.ordinal, chunk.text_hash, chunk.source_start, chunk.source_end,
                 json.dumps(chunk.locator), chunk.text, "pending", now),
            )
        for message in prepared.unreadable:
            _add_issue(db, job_id, "warning", "unreadable_section", message)
        if chunks and chunks[-1].source_end < len(prepared.text):
            _add_issue(
                db, job_id, "warning", "configured_chunk_limit",
                f"Processing stopped at character {chunks[-1].source_end} of {len(prepared.text)} because max_chunks was reached",
                details={"processed_end": chunks[-1].source_end, "source_length": len(prepared.text)},
            )
        if not chunks:
            _add_issue(db, job_id, "blocking", "no_readable_chunks", "No readable chunks were produced")
            db.conn.execute(
                "UPDATE extraction_jobs SET status='failed',error=?,updated_at=? WHERE id=?",
                ("No readable chunks were produced", now, job_id),
            )
    return job_id, True


def _chunk_from_row(row) -> DocumentChunk:
    return DocumentChunk(
        row["id"], int(row["ordinal"]), row["chunk_text"], int(row["source_start"]),
        int(row["source_end"]), json.loads(row["locator_json"]), row["text_hash"],
    )


def process_extraction_job(db: VaultDB, job_id: str, provider: ExtractionProvider, *,
                           retry_failed: bool = False) -> dict[str, Any]:
    job = _job_row(db, job_id)
    if job["provider"] != provider.name or job["model"] != provider.model:
        raise ValueError("provider/model does not match the extraction job")
    if provider.sends_data_off_device and not job["cloud_authorized"]:
        raise PermissionError("job was not authorized for cloud processing")
    document = db.get_document(job["document_id"])
    with db.transaction():
        db.conn.execute(
            "UPDATE extraction_chunks SET status='pending',error=NULL WHERE job_id=? AND status='processing'",
            (job_id,),
        )
        if retry_failed:
            db.conn.execute(
                "UPDATE extraction_chunks SET status='pending',error=NULL WHERE job_id=? AND status='failed'",
                (job_id,),
            )
        db.conn.execute("UPDATE extraction_jobs SET status='processing',error=NULL,updated_at=? WHERE id=?", (_now(), job_id))

    rows = db.conn.execute(
        "SELECT * FROM extraction_chunks WHERE job_id=? AND status='pending' ORDER BY ordinal", (job_id,)
    ).fetchall()
    usage = json.loads(job["provider_usage_json"] or "{}")
    for row in rows:
        chunk = _chunk_from_row(row)
        with db.transaction():
            db.conn.execute(
                "UPDATE extraction_chunks SET status='processing',attempts=attempts+1,updated_at=? WHERE id=? AND job_id=?",
                (_now(), chunk.id, job_id),
            )
        try:
            result = provider.extract(chunk, document_title=document["title"])
        except Exception as exc:
            with db.transaction():
                db.conn.execute(
                    "UPDATE extraction_chunks SET status='failed',error=?,updated_at=? WHERE id=? AND job_id=?",
                    (str(exc)[:2000], _now(), chunk.id, job_id),
                )
                _add_issue(db, job_id, "blocking", "provider_failure", f"Chunk {chunk.id} failed: {exc}", chunk_id=chunk.id)
            continue
        meta = result.model_dump(exclude={"extraction"}, exclude_none=True)
        usage[chunk.id] = meta
        with db.transaction():
            db.conn.execute(
                """UPDATE extraction_chunks SET status='completed',extraction_json=?,provider_meta_json=?,
                   error=NULL,updated_at=? WHERE id=? AND job_id=?""",
                (result.extraction.model_dump_json(), json.dumps(meta), _now(), chunk.id, job_id),
            )
            db.conn.execute(
                "DELETE FROM extraction_quality_issues WHERE job_id=? AND chunk_id=? AND code='provider_failure'",
                (job_id, chunk.id),
            )

    counts = db.conn.execute(
        """SELECT COUNT(*) total,
                  SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) completed,
                  SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) failed,
                  SUM(CASE WHEN status IN ('pending','processing') THEN 1 ELSE 0 END) remaining
           FROM extraction_chunks WHERE job_id=?""", (job_id,)
    ).fetchone()
    status = "interrupted" if counts["remaining"] else "review" if counts["completed"] else "failed"
    with db.transaction():
        db.conn.execute(
            """UPDATE extraction_jobs SET status=?,chunk_completed=?,chunk_failed=?,provider_usage_json=?,
               updated_at=?,completed_at=CASE WHEN ?=0 THEN ? ELSE completed_at END WHERE id=?""",
            (status, counts["completed"] or 0, counts["failed"] or 0, json.dumps(usage), _now(),
             counts["remaining"] or 0, _now(), job_id),
        )
    reconcile_job(db, job_id)
    return extraction_status(db, job_id)


def _add_issue(db: VaultDB, job_id: str, severity: str, code: str, message: str, *,
               chunk_id: str | None = None, proposal_id: str | None = None,
               details: dict | None = None) -> str:
    issue_id = _id("ISSUE")
    db.conn.execute(
        "INSERT INTO extraction_quality_issues VALUES (?,?,?,?,?,?,?,?,?)",
        (issue_id, job_id, chunk_id, proposal_id, severity, code, message,
         json.dumps(details or {}), _now()),
    )
    return issue_id


def _entity_key(item: dict, chunk_id: str) -> str:
    if item.get("identity_key"):
        return f"{item['entity_type']}|identity|{normalize_name(item['identity_key'])}"
    details = item.get("details") or {}
    anchors = [details.get("birth_value"), details.get("death_value"), details.get("organization"), details.get("role")]
    if any(anchors):
        return "|".join([item["entity_type"], normalize_name(item["name"]), *(str(value or "") for value in anchors)])
    # A bare same-name record is deliberately not merged across chunks.
    return f"{item['entity_type']}|ambiguous|{normalize_name(item['name'])}|{chunk_id}"


def _quote_evidence(db: VaultDB, job_id: str, chunk: DocumentChunk, passage: str,
                    passage_start: int | None, *, code_prefix: str) -> tuple[dict, str, list[str]]:
    locator, found, ambiguous = locate_passage(chunk, passage, passage_start)
    status, issue_ids = "clean", []
    if not found:
        issue_ids.append(_add_issue(
            db, job_id, "blocking", f"{code_prefix}_quote_missing",
            "Supporting passage was not found verbatim in the source chunk", chunk_id=chunk.id,
            details={"passage": passage[:500]},
        ))
        status = "blocking"
    elif ambiguous:
        issue_ids.append(_add_issue(
            db, job_id, "warning", f"{code_prefix}_quote_ambiguous",
            "Supporting passage occurs multiple times; the first occurrence was used", chunk_id=chunk.id,
        ))
        status = "warning"
    return {"passage": passage, "locator": locator, "chunk_id": chunk.id}, status, issue_ids


def _attach_issues(db: VaultDB, issue_ids: list[str], proposal_id: str) -> None:
    if issue_ids:
        db.conn.executemany(
            "UPDATE extraction_quality_issues SET proposal_id=? WHERE id=?",
            [(proposal_id, issue_id) for issue_id in issue_ids],
        )


def _candidate_matches(db: VaultDB, item: dict) -> list[dict]:
    matches = db.resolve_entity(item["name"], item["entity_type"])
    results = []
    for match in matches:
        signals = ["exact name or alias"]
        profile = db.get_entity(match["id"])
        if item["entity_type"] == "person":
            for field in ("birth_value", "death_value"):
                incoming, existing = (item.get("details") or {}).get(field), profile["details"].get(field)
                if incoming and existing:
                    signals.append(f"{field}: {'match' if incoming == existing else 'conflict'} ({incoming} / {existing})")
        results.append({"entity_id": match["id"], "name": match["canonical_name"], "signals": signals})
    return results


def _upsert_proposal(db: VaultDB, job_id: str, proposal_type: str, dedupe_key: str,
                     payload: dict, quality_status: str) -> str:
    row = db.conn.execute(
        "SELECT * FROM extraction_proposals WHERE job_id=? AND proposal_type=? AND dedupe_key=?",
        (job_id, proposal_type, dedupe_key),
    ).fetchone()
    if row:
        existing = json.loads(row["payload_json"])
        if "evidence" in payload:
            seen = {json.dumps(item, sort_keys=True) for item in existing.get("evidence", [])}
            for evidence in payload["evidence"]:
                encoded = json.dumps(evidence, sort_keys=True)
                if encoded not in seen:
                    existing.setdefault("evidence", []).append(evidence); seen.add(encoded)
        if proposal_type == "entity":
            existing["aliases"] = sorted(set(existing.get("aliases", [])) | set(payload.get("aliases", [])))
            for key, value in (payload.get("details") or {}).items():
                prior = existing.setdefault("details", {}).get(key)
                if prior is not None and prior != "" and prior != value and key.endswith("_value"):
                    _add_issue(
                        db, job_id, "warning", "entity_date_conflict",
                        f"Reconciled entity has conflicting {key}: {prior} / {value}", proposal_id=row["id"],
                    )
                    quality_status = "warning" if quality_status != "blocking" else quality_status
                elif prior is None or prior == "":
                    existing["details"][key] = value
        if proposal_type == "claim":
            for field in ("historical_start", "historical_end"):
                prior, incoming = existing.get(field, {}), payload.get(field, {})
                if prior.get("value") and incoming.get("value") and prior.get("value") != incoming.get("value"):
                    _add_issue(
                        db, job_id, "warning", "claim_date_conflict",
                        f"Repeated claim has conflicting {field} values", proposal_id=row["id"],
                        details={"first": prior, "later": incoming},
                    )
                    quality_status = "warning" if quality_status != "blocking" else quality_status
        if quality_status == "blocking" or row["quality_status"] == "blocking":
            quality_status = "blocking"
        elif quality_status == "warning" or row["quality_status"] == "warning":
            quality_status = "warning"
        db.conn.execute(
            "UPDATE extraction_proposals SET payload_json=?,quality_status=? WHERE id=?",
            (json.dumps(existing, ensure_ascii=False), quality_status, row["id"]),
        )
        return str(row["id"])
    proposal_id = _id("PROP")
    db.conn.execute(
        """INSERT INTO extraction_proposals(
               id,job_id,proposal_type,dedupe_key,payload_json,status,decision_json,
               quality_status,created_at
           ) VALUES (?,?,?,?,?,'pending','{}',?,?)""",
        (proposal_id, job_id, proposal_type, dedupe_key, json.dumps(payload, ensure_ascii=False), quality_status, _now()),
    )
    return proposal_id


def reconcile_job(db: VaultDB, job_id: str) -> None:
    _job_row(db, job_id)
    rows = db.conn.execute(
        "SELECT * FROM extraction_chunks WHERE job_id=? AND status='completed' ORDER BY ordinal", (job_id,)
    ).fetchall()
    entity_refs: dict[tuple[str, str], str] = {}
    claim_refs: dict[tuple[str, str], str] = {}
    with db.transaction():
        db.conn.execute(
            """DELETE FROM extraction_quality_issues WHERE job_id=?
               AND code NOT IN ('provider_failure','unreadable_section','configured_chunk_limit')""", (job_id,)
        )
        for row in rows:
            chunk = _chunk_from_row(row)
            extraction = ChunkExtraction.model_validate_json(row["extraction_json"])
            for note in extraction.skipped_or_unreadable:
                _add_issue(db, job_id, "warning", "provider_skipped_section", note, chunk_id=chunk.id)
            for note in extraction.notes:
                _add_issue(db, job_id, "informational", "provider_note", note, chunk_id=chunk.id)
            for item_model in extraction.entities:
                item = item_model.model_dump()
                evidence, quality, issue_ids = _quote_evidence(
                    db, job_id, chunk, item.pop("supporting_passage"), item.pop("passage_start"), code_prefix="entity"
                )
                key = _entity_key(item, chunk.id)
                payload = {**item, "evidence": [evidence], "candidate_matches": _candidate_matches(db, item)}
                proposal_id = _upsert_proposal(db, job_id, "entity", key, payload, quality)
                _attach_issues(db, issue_ids, proposal_id)
                entity_refs[(chunk.id, item_model.ref)] = proposal_id
            for item_model in extraction.claims:
                item = item_model.model_dump()
                passage = item.pop("original_passage"); passage_start = item.pop("passage_start")
                evidence, quality, issue_ids = _quote_evidence(db, job_id, chunk, passage, passage_start, code_prefix="claim")
                if item["claim_type"] in {"testimony", "allegation"} and not item.get("attribution"):
                    issue_ids.append(_add_issue(
                        db, job_id, "blocking", "missing_attribution",
                        "Testimony and allegations require explicit attribution", chunk_id=chunk.id,
                    ))
                    quality = "blocking"
                statement_terms = {term for term in normalize_name(item["statement"]).split() if len(term) >= 4}
                passage_terms = set(normalize_name(passage).split())
                if statement_terms and len(statement_terms & passage_terms) / len(statement_terms) < 0.25:
                    issue_ids.append(_add_issue(
                        db, job_id, "warning", "claim_scope_warning",
                        "Claim wording has little lexical support in its quoted passage and requires human review",
                        chunk_id=chunk.id,
                    ))
                    quality = "warning" if quality != "blocking" else quality
                item["entity_proposal_ids"] = [entity_refs[(chunk.id, ref)] for ref in item.pop("entity_refs")]
                key = "|".join([
                    normalize_name(item["statement"]),
                    ",".join(sorted(item["entity_proposal_ids"])),
                    normalize_name(item.get("attribution") or ""),
                ])
                proposal_id = _upsert_proposal(db, job_id, "claim", key, {**item, "evidence": [evidence]}, quality)
                _attach_issues(db, issue_ids, proposal_id)
                claim_refs[(chunk.id, item_model.ref)] = proposal_id
                _detect_contradiction(db, job_id, proposal_id, item["statement"])
            for item_model in extraction.relationships:
                item = item_model.model_dump()
                passage = item.pop("supporting_passage"); passage_start = item.pop("passage_start")
                evidence, quality, issue_ids = _quote_evidence(
                    db, job_id, chunk, passage, passage_start, code_prefix="relationship"
                )
                subject = entity_refs[(chunk.id, item.pop("subject_ref"))]
                object_id = entity_refs[(chunk.id, item.pop("object_ref"))]
                claim_ref = item.pop("claim_ref")
                item["subject_proposal_id"], item["object_proposal_id"] = subject, object_id
                item["claim_proposal_id"] = claim_refs.get((chunk.id, claim_ref)) if claim_ref else None
                key = "|".join([
                    subject, object_id, item["relationship_type"],
                    str(item["historical_start"].get("value") or ""), str(item["historical_end"].get("value") or ""),
                ])
                proposal_id = _upsert_proposal(db, job_id, "relationship", key, {**item, "evidence": [evidence]}, quality)
                _attach_issues(db, issue_ids, proposal_id)
            for item_model in extraction.document_metadata:
                item = item_model.model_dump()
                passage = item.pop("supporting_passage"); passage_start = item.pop("passage_start")
                evidence, quality, issue_ids = _quote_evidence(
                    db, job_id, chunk, passage, passage_start, code_prefix="document"
                )
                key = "|".join(normalize_name(str(item.get(field) or "")) for field in (
                    "document_type", "title", "author", "sender", "recipient", "document_date"
                ))
                proposal_id = _upsert_proposal(
                    db, job_id, "document_update", key, {**item, "evidence": [evidence]}, quality
                )
                _attach_issues(db, issue_ids, proposal_id)

        completed = {row["ordinal"] for row in rows}
        _enrich_candidate_matches(db, job_id)
        total = int(db.conn.execute("SELECT chunk_total FROM extraction_jobs WHERE id=?", (job_id,)).fetchone()[0])
        if len(completed) < total:
            _add_issue(db, job_id, "blocking", "incomplete_coverage",
                       f"Only {len(completed)} of {total} chunks completed")
        names: dict[tuple[str, str], list[str]] = {}
        for proposal in db.conn.execute(
            "SELECT id,payload_json FROM extraction_proposals WHERE job_id=? AND proposal_type='entity'", (job_id,)
        ):
            payload = json.loads(proposal["payload_json"])
            names.setdefault((payload["entity_type"], normalize_name(payload["name"])), []).append(proposal["id"])
        for (entity_type, name), proposal_ids in names.items():
            if len(proposal_ids) > 1:
                _add_issue(
                    db, job_id, "warning", "ambiguous_same_name",
                    f"Multiple distinct {entity_type} proposals share the name {name!r}; identity review is required",
                    details={"proposal_ids": proposal_ids},
                )


def _enrich_candidate_matches(db: VaultDB, job_id: str) -> None:
    entity_rows = db.conn.execute(
        "SELECT id,payload_json FROM extraction_proposals WHERE job_id=? AND proposal_type='entity'", (job_id,)
    ).fetchall()
    entities = {row["id"]: json.loads(row["payload_json"]) for row in entity_rows}
    relationship_rows = db.conn.execute(
        "SELECT payload_json FROM extraction_proposals WHERE job_id=? AND proposal_type='relationship'", (job_id,)
    ).fetchall()
    relationships = [json.loads(row["payload_json"]) for row in relationship_rows]
    for proposal_id, payload in entities.items():
        proposed_context = []
        for relationship in relationships:
            if relationship["subject_proposal_id"] != proposal_id:
                continue
            target = entities.get(relationship["object_proposal_id"])
            if target:
                proposed_context.append((
                    relationship["relationship_type"], normalize_name(target["name"]), target["entity_type"],
                    relationship["historical_start"].get("value"), relationship["historical_end"].get("value"),
                ))
        changed = False
        for candidate in payload.get("candidate_matches", []):
            profile = db.get_entity(candidate["entity_id"])
            for relationship_type, target_name, target_type, start, end in proposed_context:
                for accepted in profile.get("relationships", []):
                    if accepted["subject_entity_id"] != candidate["entity_id"]:
                        continue
                    if accepted["relationship_type"] == relationship_type and normalize_name(accepted["object_name"]) == target_name:
                        context = "place" if target_type == "place" else "organization/role"
                        candidate["signals"].append(
                            f"shared {context}: {relationship_type} {accepted['object_name']} ({start or '?'} to {end or 'open'})"
                        )
                        changed = True
        if changed:
            db.conn.execute(
                "UPDATE extraction_proposals SET payload_json=? WHERE id=?",
                (json.dumps(payload, ensure_ascii=False), proposal_id),
            )


def _negation_key(statement: str) -> tuple[str, bool]:
    normalized = normalize_name(statement)
    negative = bool(re.search(r"\b(not|never|no|didn t|wasn t|denied)\b", normalized))
    skeleton = re.sub(r"\b(not|never|no|didn t|wasn t|denied)\b", "", normalized)
    return re.sub(r"\s+", " ", skeleton).strip(), negative


def _detect_contradiction(db: VaultDB, job_id: str, proposal_id: str, statement: str) -> None:
    key, negative = _negation_key(statement)
    for row in db.conn.execute("SELECT id,statement FROM claims"):
        other_key, other_negative = _negation_key(row["statement"])
        if key and key == other_key and negative != other_negative:
            _upsert_proposal(
                db, job_id, "conflict", f"{proposal_id}|{row['id']}",
                {"claim_proposal_id": proposal_id, "existing_claim_id": row["id"],
                 "reason": "Potential contradiction detected from opposite polarity"}, "warning",
            )


def extraction_status(db: VaultDB, job_id: str) -> dict[str, Any]:
    job = dict(_job_row(db, job_id))
    job["config"] = json.loads(job.pop("config_json"))
    job["provider_usage"] = json.loads(job.pop("provider_usage_json"))
    job["chunks"] = [dict(row) for row in db.conn.execute(
        "SELECT id,ordinal,status,attempts,error,locator_json FROM extraction_chunks WHERE job_id=? ORDER BY ordinal",
        (job_id,),
    )]
    for chunk in job["chunks"]:
        chunk["locator"] = json.loads(chunk.pop("locator_json"))
    job["proposal_counts"] = {row["status"]: row["count"] for row in db.conn.execute(
        "SELECT status,COUNT(*) count FROM extraction_proposals WHERE job_id=? GROUP BY status", (job_id,)
    )}
    job["issue_counts"] = {row["severity"]: row["count"] for row in db.conn.execute(
        "SELECT severity,COUNT(*) count FROM extraction_quality_issues WHERE job_id=? GROUP BY severity", (job_id,)
    )}
    return job


def extraction_review(db: VaultDB, job_id: str) -> dict[str, Any]:
    _job_row(db, job_id)
    proposals = []
    for row in db.conn.execute(
        "SELECT * FROM extraction_proposals WHERE job_id=? ORDER BY proposal_type,created_at", (job_id,)
    ):
        item = dict(row); item["payload"] = json.loads(item.pop("payload_json")); item["decision"] = json.loads(item.pop("decision_json"))
        proposals.append(item)
    issues = []
    for row in db.conn.execute(
        "SELECT * FROM extraction_quality_issues WHERE job_id=? ORDER BY severity,created_at", (job_id,)
    ):
        item = dict(row); item["details"] = json.loads(item.pop("details_json")); issues.append(item)
    return {"job": extraction_status(db, job_id), "proposals": proposals, "issues": issues}


def decide_proposal(db: VaultDB, job_id: str, proposal_id: str, action: str, *,
                    known_entity_id: str | None = None) -> None:
    if action not in {"approve", "reject"}:
        raise ValueError("action must be approve or reject")
    proposal = db.conn.execute(
        "SELECT * FROM extraction_proposals WHERE id=? AND job_id=?", (proposal_id, job_id)
    ).fetchone()
    if not proposal:
        raise KeyError(proposal_id)
    if action == "approve" and proposal["quality_status"] == "blocking":
        raise ValueError("blocking proposals cannot be approved until corrected")
    decision = {"known_entity_id": known_entity_id} if known_entity_id else {}
    if known_entity_id:
        payload = json.loads(proposal["payload_json"])
        if proposal["proposal_type"] != "entity":
            raise ValueError("known_entity_id applies only to entity proposals")
        db.validate_known_entity(known_entity_id, payload["entity_type"])
    status = "approved" if action == "approve" else "rejected"
    with db.transaction():
        db.conn.execute(
            "UPDATE extraction_proposals SET status=?,decision_json=?,decided_at=? WHERE id=?",
            (status, json.dumps(decision), _now(), proposal_id),
        )
        db.conn.execute(
            "INSERT INTO extraction_approval_history VALUES (?,?,?,?,?,?)",
            (_id("DECISION"), job_id, proposal_id, action, json.dumps(decision), _now()),
        )


def bulk_decide(db: VaultDB, job_id: str, action: str) -> int:
    quality_clause = " AND quality_status!='blocking'" if action == "approve" else ""
    proposals = db.conn.execute(
        "SELECT id FROM extraction_proposals WHERE job_id=? AND status='pending'" + quality_clause,
        (job_id,),
    ).fetchall()
    for row in proposals:
        decide_proposal(db, job_id, row["id"], action)
    return len(proposals)


def commit_approved(db: VaultDB, job_id: str) -> dict[str, str]:
    job = _job_row(db, job_id)
    if job["status"] not in {"review", "partial_failure", "committed"}:
        raise ValueError(f"job is not ready to commit: {job['status']}")
    blocking = db.conn.execute(
        """SELECT COUNT(*) FROM extraction_quality_issues issue
           LEFT JOIN extraction_proposals proposal ON proposal.id=issue.proposal_id
           WHERE issue.job_id=? AND issue.severity='blocking'
             AND (issue.proposal_id IS NULL OR proposal.status!='rejected')""", (job_id,)
    ).fetchone()[0]
    if blocking:
        raise ValueError(f"job has {blocking} unresolved blocking quality issue(s)")
    approved = db.conn.execute(
        "SELECT * FROM extraction_proposals WHERE job_id=? AND status='approved' ORDER BY CASE proposal_type WHEN 'entity' THEN 1 WHEN 'document_update' THEN 2 WHEN 'claim' THEN 3 WHEN 'relationship' THEN 4 ELSE 5 END",
        (job_id,),
    ).fetchall()
    committed: dict[str, str] = {}
    approved_ids = {row["id"] for row in approved}
    for row in approved:
        payload = json.loads(row["payload_json"])
        if row["proposal_type"] == "claim" and any(ref not in approved_ids and not _committed_id(db, ref) for ref in payload["entity_proposal_ids"]):
            raise ValueError(f"approved claim {row['id']} depends on an unapproved entity")
        if row["proposal_type"] == "relationship":
            dependencies = [payload["subject_proposal_id"], payload["object_proposal_id"]]
            if payload.get("claim_proposal_id"):
                dependencies.append(payload["claim_proposal_id"])
            if any(ref not in approved_ids and not _committed_id(db, ref) for ref in dependencies):
                raise ValueError(f"approved relationship {row['id']} has an unapproved dependency")
        if row["proposal_type"] == "conflict":
            ref = payload["claim_proposal_id"]
            if ref not in approved_ids and not _committed_id(db, ref):
                raise ValueError(f"approved conflict {row['id']} depends on an unapproved claim")

    with db.transaction():
        for row in approved:
            payload, decision = json.loads(row["payload_json"]), json.loads(row["decision_json"])
            proposal_id, kind = row["id"], row["proposal_type"]
            if row["committed_id"]:
                committed[proposal_id] = row["committed_id"]; continue
            if kind == "entity":
                known = decision.get("known_entity_id")
                if known:
                    db.validate_known_entity(known, payload["entity_type"])
                    _apply_approved_profile_updates(db, known, payload)
                    accepted_id = known
                else:
                    accepted_id = db.add_entity(
                        payload["entity_type"], payload["name"], aliases=payload.get("aliases"),
                        description=payload.get("description", ""), details=payload.get("details"),
                    )
                db.bind_import_entity(job["document_id"], f"phase2:{proposal_id}", accepted_id)
            elif kind == "document_update":
                document = db.conn.execute("SELECT * FROM documents WHERE id=?", (job["document_id"],)).fetchone()
                metadata = json.loads(document["metadata_json"] or "{}")
                metadata.update({key: value for key, value in payload.items() if key != "evidence" and value not in {None, ""}})
                db.conn.execute(
                    """UPDATE documents SET title=COALESCE(?,title),author=COALESCE(?,author),
                       document_date=COALESCE(?,document_date),metadata_json=? WHERE id=?""",
                    (payload.get("title"), payload.get("author") or payload.get("sender"),
                     payload.get("document_date"), json.dumps(metadata, ensure_ascii=False), job["document_id"]),
                )
                accepted_id = str(job["document_id"])
            elif kind == "claim":
                entity_ids = [committed.get(ref) or _committed_id(db, ref) for ref in payload["entity_proposal_ids"]]
                accepted_id = db.add_claim(
                    payload["statement"], original_wording=payload["evidence"][0]["passage"],
                    claim_type=payload["claim_type"], status=payload["status"],
                    historical_start=payload["historical_start"], historical_end=payload["historical_end"],
                    entity_ids=entity_ids,
                )
                for evidence in payload["evidence"]:
                    db.add_claim_evidence(
                        accepted_id, job["revision_id"], locator=json.dumps(evidence["locator"], sort_keys=True),
                        original_wording=evidence["passage"], independent=payload.get("independent", True),
                        dependency_group=payload.get("dependency_group"), attribution=payload.get("attribution"),
                    )
            elif kind == "relationship":
                subject = committed.get(payload["subject_proposal_id"]) or _committed_id(db, payload["subject_proposal_id"])
                object_id = committed.get(payload["object_proposal_id"]) or _committed_id(db, payload["object_proposal_id"])
                claim_id = None
                if payload.get("claim_proposal_id"):
                    claim_id = committed.get(payload["claim_proposal_id"]) or _committed_id(db, payload["claim_proposal_id"])
                first = payload["evidence"][0]
                accepted_id = db.add_relationship(
                    subject, object_id, payload["relationship_type"], directed=payload["directed"],
                    classification=payload["classification"], historical_start=payload["historical_start"],
                    historical_end=payload["historical_end"], revision_id=job["revision_id"], claim_id=claim_id,
                    locator=json.dumps(first["locator"], sort_keys=True), original_wording=first["passage"],
                )
                for evidence in payload["evidence"][1:]:
                    db.add_relationship_evidence(
                        accepted_id, job["revision_id"], claim_id=claim_id,
                        locator=json.dumps(evidence["locator"], sort_keys=True),
                        original_wording=evidence["passage"],
                    )
            elif kind == "conflict":
                claim_id = committed.get(payload["claim_proposal_id"]) or _committed_id(db, payload["claim_proposal_id"])
                accepted_id = db.add_conflict(claim_id, payload["existing_claim_id"], reason=payload["reason"])
            else:
                continue
            committed[proposal_id] = accepted_id
            db.conn.execute(
                "UPDATE extraction_proposals SET status='committed',committed_id=? WHERE id=?",
                (accepted_id, proposal_id),
            )
            db.conn.execute(
                "INSERT INTO extraction_approval_history VALUES (?,?,?,?,?,?)",
                (_id("DECISION"), job_id, proposal_id, "commit", json.dumps({"accepted_id": accepted_id}), _now()),
            )
        db.conn.execute(
            "UPDATE extraction_jobs SET status='committed',committed_at=?,updated_at=? WHERE id=?",
            (_now(), _now(), job_id),
        )
    return committed


def _committed_id(db: VaultDB, proposal_id: str) -> str | None:
    row = db.conn.execute("SELECT committed_id FROM extraction_proposals WHERE id=?", (proposal_id,)).fetchone()
    return str(row["committed_id"]) if row and row["committed_id"] else None


def _apply_approved_profile_updates(db: VaultDB, entity_id: str, payload: dict) -> None:
    for alias in payload.get("aliases", []):
        db.add_alias(entity_id, alias)
    current = db.get_entity(entity_id)
    if payload.get("description") and not current.get("description"):
        db.update_entity(entity_id, description=payload["description"])
    table = {
        "person": "person_details", "organization": "organization_details",
        "event": "event_details", "place": "place_details",
    }[payload["entity_type"]]
    existing = current.get("details", {})
    safe_fields = set(existing) - {"entity_id"}
    updates = {
        key: value for key, value in (payload.get("details") or {}).items()
        if key in safe_fields and value is not None and value != ""
        and existing.get(key) in {None, "", "unknown", "other"}
    }
    if updates:
        db.conn.execute(
            f"UPDATE {table} SET " + ",".join(f"{key}=?" for key in updates) + " WHERE entity_id=?",
            (*updates.values(), entity_id),
        )
