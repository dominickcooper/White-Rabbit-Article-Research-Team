from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

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


def ingest_document(db: VaultDB, path: Path, **metadata: Any) -> tuple[str, str, bool]:
    path = path.resolve()
    document = read_local_document(path)
    return db.add_document_revision(
        title=metadata.pop("title", document.title), file_hash=sha256_file(path),
        extracted_text=document.text, byte_size=path.stat().st_size, original_file=str(path), **metadata,
    )


def import_structured(db: VaultDB, path: Path) -> dict[str, Any]:
    try:
        package = VaultImport.model_validate_json(path.read_text(encoding="utf-8"))
    except (ValidationError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid Vault import {path}: {exc}") from exc
    document_path = package.document.get("path")
    if not document_path:
        raise ValueError("document.path is required")
    source = Path(document_path)
    if not source.is_absolute():
        source = (path.parent / source).resolve()
    document_id, revision_id, changed = ingest_document(
        db, source,
        title=package.document.get("title", source.stem),
        author=package.document.get("author"),
        document_date=package.document.get("document_date"),
        source_classification=package.document.get("source_classification", "author_supplied"),
        authority_level=int(package.document.get("authority_level", 2)),
    )
    refs: dict[str, str] = {}
    for item in package.entities:
        matches = db.resolve_entity(item.name, item.entity_type)
        if len(matches) == 1:
            entity_id = matches[0]["id"]
            for alias in item.aliases:
                db.add_alias(entity_id, alias)
        else:
            entity_id = db.add_entity(item.entity_type, item.name, aliases=item.aliases, description=item.description,
                                      details=item.details)
        if item.ref:
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
    conflict_ids = [db.add_conflict(refs[item.claim_ref_a], refs[item.claim_ref_b], reason=item.reason,
                                    requires_author_review=item.requires_author_review) for item in package.conflicts]
    return {"document_id": document_id, "revision_id": revision_id, "source_changed": changed,
            "entities": len(package.entities), "claims": len(package.claims),
            "relationships": relationship_ids, "conflicts": conflict_ids}
