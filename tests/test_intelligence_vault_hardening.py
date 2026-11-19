from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

from white_rabbit.intelligence_vault.backup import create_backup_bundle, restore_backup_bundle
from white_rabbit.intelligence_vault.database import MIGRATIONS, VaultDB
from white_rabbit.intelligence_vault.ingestion import import_structured, ingest_document, sha256_file
from white_rabbit.intelligence_vault.temporal import HistoricalDate, OverlapResult, ranges_overlap
from white_rabbit.intelligence_vault.web import (
    APIEntity, MAX_BODY_BYTES, is_loopback_host_header, origin_allows_write, parse_json_object, serve,
    validated_body_size,
)


def _write_import(path: Path, source_name: str, entities: list[dict], relationships: list[dict] | None = None) -> None:
    path.write_text(json.dumps({
        "schema_version": 1,
        "document": {"path": source_name, "title": "Identity record"},
        "entities": entities,
        "claims": [],
        "relationships": relationships or [],
        "conflicts": [],
    }), encoding="utf-8")


def test_v1_database_migrates_transactionally_to_latest(tmp_path: Path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript("BEGIN;" + MIGRATIONS[0][1] + "PRAGMA user_version=1; COMMIT;")
    conn.close()
    with VaultDB(path) as db:
        assert db.stats()["schema_version"] == 4
        columns = {row[1] for row in db.conn.execute("PRAGMA table_info(document_revisions)")}
        assert "archived_path" in columns


def test_name_match_creates_distinct_person_and_contextual_suggestion(tmp_path: Path):
    source = tmp_path / "record.txt"; source.write_text("identity evidence", encoding="utf-8")
    package = tmp_path / "record.vault.json"
    with VaultDB(tmp_path / "vault.db") as db:
        organization = db.add_entity("organization", "Example Agency")
        existing = db.add_entity("person", "Jordan Example", details={"birth_value": "1920", "birth_precision": "year"})
        db.add_relationship(
            existing, organization, "served_in",
            historical_start={"value": "1942", "precision": "year", "certainty": "certain"},
            historical_end={"value": "1945", "precision": "year", "certainty": "certain"},
        )
        _write_import(package, source.name, [
            {"ref": "person", "entity_type": "person", "name": "Jordan Example",
             "details": {"birth_value": "1920", "birth_precision": "year"}},
            {"ref": "agency", "known_entity_id": organization, "entity_type": "organization",
             "name": "Example Agency"},
        ], [{
            "subject_ref": "person", "object_ref": "agency", "relationship_type": "served_in",
            "historical_start": {"value": "1943", "precision": "year", "certainty": "certain"},
            "historical_end": {"value": "1944", "precision": "year", "certainty": "certain"},
        }])
        result = import_structured(db, package)
        people = db.resolve_entity("Jordan Example", "person")
        assert len(people) == 2
        imported = db.get_import_binding(result["document_id"], "person")
        assert imported != existing
        suggestion = db.list_review()["merge_suggestions"][0]
        evidence = json.loads(suggestion["evidence_json"])
        assert any("matching birth date" in signal for signal in evidence["signals"])
        assert any("shared organization/role" in signal for signal in evidence["signals"])


def test_explicit_known_entity_id_is_only_automatic_identity_reuse(tmp_path: Path):
    source = tmp_path / "record.txt"; source.write_text("confirmed identity", encoding="utf-8")
    package = tmp_path / "record.vault.json"
    with VaultDB(tmp_path / "vault.db") as db:
        known = db.add_entity("person", "Taylor Confirmed")
        _write_import(package, source.name, [{
            "ref": "person", "known_entity_id": known, "entity_type": "person",
            "name": "Taylor Confirmed", "aliases": ["T. Confirmed"],
        }])
        first = import_structured(db, package)
        second = import_structured(db, package)
        assert first["document_id"] == second["document_id"]
        assert db.get_import_binding(first["document_id"], "person") == known
        assert db.stats()["person"] == 1
        assert "T. Confirmed" in db.get_entity(known)["aliases"]


def test_structured_import_rolls_back_every_database_write_on_mid_import_failure(tmp_path: Path):
    source = tmp_path / "record.txt"; source.write_text("will fail", encoding="utf-8")
    package = tmp_path / "record.vault.json"
    with VaultDB(tmp_path / "vault.db") as db:
        person = db.add_entity("person", "Known Person")
        before = db.export()["tables"]
        _write_import(package, source.name, [
            {"ref": "new", "entity_type": "person", "name": "Inserted Before Failure"},
            {"ref": "wrong-type", "known_entity_id": person, "entity_type": "organization", "name": "Wrong"},
        ])
        with pytest.raises(ValueError, match="not organization"):
            import_structured(db, package)
        after = db.export()["tables"]
        assert after == before


def test_content_addressed_archive_survives_original_change_and_deduplicates(tmp_path: Path):
    source = tmp_path / "memo.txt"; source.write_text("immutable evidence", encoding="utf-8")
    with VaultDB(tmp_path / "knowledge" / "vault.db") as db:
        document, revision, _ = ingest_document(db, source)
        profile = db.get_document(document)
        assert profile["original_file"] == str(source.resolve())
        archived = db.archived_file(profile["revisions"][0]["archived_path"])
        assert archived.is_file() and archived.name == sha256_file(source)
        source.write_text("changed original", encoding="utf-8")
        assert archived.read_text(encoding="utf-8") == "immutable evidence"
        copy = tmp_path / "copy.txt"; copy.write_text("immutable evidence", encoding="utf-8")
        same_document, same_revision, changed = ingest_document(db, copy)
        assert (same_document, same_revision, changed) == (document, revision, False)
        assert len(list((tmp_path / "knowledge" / "intelligence_vault_evidence").rglob(archived.name))) == 1


def test_lossless_export_and_backup_restore_preserve_all_tables_and_evidence(tmp_path: Path):
    source = tmp_path / "source.txt"; source.write_text("preserved source", encoding="utf-8")
    original_path = tmp_path / "original" / "vault.db"
    with VaultDB(original_path) as db:
        person = db.add_entity("person", "Backup Person", details={"birth_value": "1910", "birth_precision": "year"})
        org = db.add_entity("organization", "Backup Organization", details={"organization_kind": "agency"})
        investigation = db.add_investigation("Backup Investigation", "Complete preservation")
        db.attach_investigation(person, investigation, "central figure")
        document, revision, _ = ingest_document(db, source)
        claim = db.add_claim(
            "Backup Person served in Backup Organization.", entity_ids=[person, org],
            historical_start={"value": "1942", "precision": "year", "certainty": "certain"},
            historical_end={"value": "1945", "precision": "year", "certainty": "certain"},
        )
        db.add_claim_evidence(claim, revision, locator="line 1", original_wording="preserved source")
        relationship = db.add_relationship(
            person, org, "served_in", revision_id=revision, claim_id=claim,
            historical_start={"value": "1942-06", "precision": "month", "certainty": "probable"},
            historical_end={"value": "1945", "precision": "approximate", "certainty": "uncertain"},
        )
        expected = db.export()["tables"]
        assert "person_details" in expected and "entity_investigations" in expected
        bundle = create_backup_bundle(db, tmp_path / "bundle")

    restored_path = tmp_path / "restored" / "vault.db"
    restore_backup_bundle(bundle, restored_path)
    with VaultDB(restored_path) as restored:
        assert restored.export()["tables"] == expected
        assert restored.get_entity(person)["relationships"][0]["id"] == relationship
        archived_path = restored.get_document(document)["revisions"][0]["archived_path"]
        assert restored.archived_file(archived_path).read_text(encoding="utf-8") == "preserved source"


@pytest.mark.parametrize("values,expected", [
    (("1942", "year", "certain", "1945", "year", "certain", "1944", "year", "certain", "1948", "year", "certain"), OverlapResult.DEFINITE_OVERLAP),
    (("1944", "year", "certain", "1944", "year", "certain", "1944-06-01", "exact", "certain", "1944-06-01", "exact", "certain"), OverlapResult.POSSIBLE_OVERLAP),
    (("1940-01-01", "exact", "certain", "1941-01-01", "exact", "certain", "1941-01-01", "exact", "certain", "1942-01-01", "exact", "certain"), OverlapResult.DEFINITE_OVERLAP),
    (("1940", "approximate", "uncertain", "1941", "approximate", "uncertain", "1942", "year", "certain", "1943", "year", "certain"), OverlapResult.POSSIBLE_OVERLAP),
    (("1940", "year", "certain", "1941", "year", "certain", "1942", "year", "certain", "1943", "year", "certain"), OverlapResult.NO_OVERLAP),
])
def test_temporal_overlap_states_and_mixed_precision(values, expected):
    a = [HistoricalDate(*values[index:index + 3]) for index in range(0, 12, 3)]
    assert ranges_overlap(*a) == expected


def test_temporal_open_ended_unknown_and_uncertain_boundaries():
    exact = lambda value: HistoricalDate(value, "exact", "certain")
    unknown = HistoricalDate()
    assert ranges_overlap(exact("1950-01-01"), unknown, exact("1960-01-01"), exact("1961-01-01")) == OverlapResult.DEFINITE_OVERLAP
    assert ranges_overlap(unknown, unknown, exact("1960-01-01"), exact("1961-01-01")) == OverlapResult.INSUFFICIENT_EVIDENCE
    assert ranges_overlap(HistoricalDate("1950-01-01", "exact", "uncertain"), unknown, exact("1960-01-01"), exact("1961-01-01")) == OverlapResult.POSSIBLE_OVERLAP


def test_local_api_rejects_cross_origin_malformed_and_oversized_writes():
    assert is_loopback_host_header("127.0.0.1:8765")
    assert is_loopback_host_header("[::1]:8765")
    assert not is_loopback_host_header("evil.example")
    assert origin_allows_write("http://127.0.0.1:8765", 8765)
    assert not origin_allows_write("https://evil.example", 8765)
    assert not origin_allows_write("http://127.0.0.1:9999", 8765)
    assert validated_body_size("application/json; charset=utf-8", "2") == 2
    with pytest.raises(OverflowError):
        validated_body_size("application/json", str(MAX_BODY_BYTES + 1))
    with pytest.raises(ValueError, match="Content-Type"):
        validated_body_size("text/plain", "2")
    with pytest.raises(ValueError, match="transfer"):
        validated_body_size("application/json", "2", "chunked")
    with pytest.raises(ValueError, match="malformed"):
        parse_json_object(b"{bad")
    with pytest.raises(ValueError, match="object"):
        parse_json_object(b"[]")
    assert parse_json_object(b'{"entity_type":"person"}') == {"entity_type": "person"}
    with pytest.raises(ValueError):
        APIEntity.model_validate({"entity_type": "person", "name": "Valid", "unexpected": True})


def test_server_refuses_non_loopback_binding(tmp_path: Path):
    with pytest.raises(ValueError, match="loopback"):
        serve(tmp_path / "vault.db", host="0.0.0.0", port=0)
