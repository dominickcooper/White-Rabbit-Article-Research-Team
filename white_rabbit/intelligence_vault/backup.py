from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
from uuid import uuid4

from .database import VaultDB
from .ingestion import evidence_archive_root, sha256_file


def create_backup_bundle(db: VaultDB, destination: Path) -> Path:
    """Create an atomic directory bundle containing a SQLite snapshot and evidence files."""
    destination = destination.resolve()
    if destination.exists():
        raise FileExistsError(f"backup destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / f".{destination.name}.{uuid4().hex}.tmp"
    temporary.mkdir()
    try:
        db.backup_to(temporary / "vault.db")
        archive = evidence_archive_root(db)
        if archive.exists():
            shutil.copytree(archive, temporary / "evidence")
        evidence_hashes = {}
        evidence_dir = temporary / "evidence"
        if evidence_dir.exists():
            evidence_hashes = {
                item.relative_to(evidence_dir).as_posix(): sha256_file(item)
                for item in sorted(evidence_dir.rglob("*")) if item.is_file()
            }
        manifest = {
            "format": "white-rabbit-intelligence-vault-backup",
            "format_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "database_sha256": sha256_file(temporary / "vault.db"),
            "evidence_sha256": evidence_hashes,
        }
        (temporary / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    return destination


def restore_backup_bundle(bundle: Path, destination_db: Path) -> Path:
    """Verify and restore a complete bundle without trusting manifest paths."""
    bundle, destination_db = bundle.resolve(), destination_db.resolve()
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("format") != "white-rabbit-intelligence-vault-backup" or manifest.get("format_version") != 1:
        raise ValueError("unsupported Vault backup bundle")
    snapshot = bundle / "vault.db"
    if sha256_file(snapshot) != manifest.get("database_sha256"):
        raise ValueError("backup database hash mismatch")
    evidence_source = bundle / "evidence"
    expected = manifest.get("evidence_sha256", {})
    for relative, digest in expected.items():
        candidate = (evidence_source / relative).resolve()
        if not candidate.is_relative_to(evidence_source.resolve()) or not candidate.is_file():
            raise ValueError("invalid evidence path in backup manifest")
        if sha256_file(candidate) != digest:
            raise ValueError(f"backup evidence hash mismatch: {relative}")

    evidence_destination = destination_db.parent / "intelligence_vault_evidence"
    for relative, digest in expected.items():
        existing = evidence_destination / relative
        if existing.exists() and sha256_file(existing) != digest:
            raise ValueError(f"existing evidence conflicts with backup: {relative}")

    VaultDB.restore_from(snapshot, destination_db)
    for relative, digest in expected.items():
        source = evidence_source / relative
        target = evidence_destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if sha256_file(target) != digest:
                raise ValueError(f"existing evidence conflicts with backup: {relative}")
            continue
        temporary = target.with_name(f".{target.name}.{uuid4().hex}.tmp")
        try:
            shutil.copyfile(source, temporary)
            if sha256_file(temporary) != digest:
                raise RuntimeError(f"restored evidence failed integrity check: {relative}")
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()
    return destination_db
