from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from white_rabbit.local_sources import read_local_document
from .database import VaultDB
from .schema import VaultImport


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def evidence_archive_root(db: VaultDB) -> Path:
    return db.path.resolve().parent / "intelligence_vault_evidence"


def preserve_source(path: Path, archive_root: Path, file_hash: str | None = None) -> str:
    """Copy an input into the private content-addressed archive without modifying it."""
    path, archive_root = path.resolve(), archive_root.resolve()
    digest = file_hash or sha256_file(path)
    relative = Path("sha256") / digest[:2] / digest
    destination = archive_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha256_file(destination) != digest:
            raise RuntimeError(f"evidence archive integrity failure: {destination}")
        return relative.as_posix()
    temporary = destination.with_name(f".{digest}.{uuid4().hex}.tmp")
    try:
        shutil.copyfile(path, temporary)
        if sha256_file(temporary) != digest:
            raise RuntimeError("source changed while it was being archived")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return relative.as_posix()


def ingest_document(db: VaultDB, path: Path, **metadata: Any) -> tuple[str, str, bool]:
    path = path.resolve()
    digest = sha256_file(path)
    archived_path = preserve_source(path, evidence_archive_root(db), digest)
    document = read_local_document(path)
    if sha256_file(path) != digest:
        raise RuntimeError("source changed while it was being extracted")
    archived_size = (evidence_archive_root(db) / archived_path).stat().st_size
    return db.add_document_revision(
        title=metadata.pop("title", document.title), file_hash=digest, archived_path=archived_path,
        extracted_text=document.text, byte_size=archived_size, original_file=str(path), **metadata,
    )


def import_structured(db: VaultDB, path: Path) -> dict[str, Any]:
    try:
        package = VaultImport.model_validate_json(path.read_text(encoding="utf-8"))
    except (ValidationError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid Vault import {path}: {exc}") from exc
    source = Path(package.document.path)
    if not source.is_absolute():
        source = (path.parent / source).resolve()
    with db.transaction():
        document_id, revision_id, changed = ingest_document(
            db, source,
            title=package.document.title or source.stem,
            author=package.document.author,
            document_date=package.document.document_date,
            source_classification=package.document.source_classification,
            authority_level=package.document.authority_level,
        )
        refs: dict[str, str] = {}
        imported_entities: list[str] = []
        for item in package.entities:
            bound = db.get_import_binding(document_id, item.ref)
            if item.known_entity_id:
                db.validate_known_entity(item.known_entity_id, item.entity_type)
                entity_id = item.known_entity_id
            elif bound:
                entity_id = bound
                db.validate_known_entity(entity_id, item.entity_type)
            else:
                # Names and aliases create candidates, never automatic identity assignments.
                entity_id = db.add_entity(
                    item.entity_type, item.name, aliases=item.aliases, description=item.description,
                    details=item.details,
                )
                imported_entities.append(entity_id)
            db.bind_import_entity(document_id, item.ref, entity_id)
            for alias in item.aliases:
                db.add_alias(entity_id, alias)
            refs[item.ref] = entity_id
        for item in package.claims:
            entity_ids = [refs[ref] for ref in item.entity_refs]
            claim_id = db.add_claim(
                item.statement, original_wording=item.original_wording, claim_type=item.claim_type, status=item.status,
                historical_start=item.historical_start.model_dump(), historical_end=item.historical_end.model_dump(),
                entity_ids=entity_ids,
            )
            db.add_claim_evidence(
                claim_id, revision_id, locator=item.locator or "", original_wording=item.original_wording,
                independent=item.independent, dependency_group=item.dependency_group,
            )
            if item.ref:
                refs[item.ref] = claim_id
        relationship_ids = []
        for item in package.relationships:
            relationship_ids.append(db.add_relationship(
                refs[item.subject_ref], refs[item.object_ref], item.relationship_type, directed=item.directed,
                classification=item.classification, historical_start=item.historical_start.model_dump(),
                historical_end=item.historical_end.model_dump(), revision_id=revision_id,
                claim_id=refs.get(item.claim_ref) if item.claim_ref else None,
                locator=item.locator or "", original_wording=item.original_wording,
            ))
        for entity_id in imported_entities:
            db.refresh_match_suggestions(entity_id)
        conflict_ids = [db.add_conflict(
            refs[item.claim_ref_a], refs[item.claim_ref_b], reason=item.reason,
            requires_author_review=item.requires_author_review,
        ) for item in package.conflicts]
    return {"document_id": document_id, "revision_id": revision_id, "source_changed": changed,
            "entities": len(package.entities), "claims": len(package.claims),
            "relationships": relationship_ids, "conflicts": conflict_ids}
