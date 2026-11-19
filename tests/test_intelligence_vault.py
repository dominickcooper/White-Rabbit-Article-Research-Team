from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

from white_rabbit.intelligence_vault.database import VaultDB
from white_rabbit.intelligence_vault.discovery import SharedAffiliationProvider
from white_rabbit.intelligence_vault.ingestion import ingest_document, import_structured, sha256_file
from white_rabbit.intelligence_vault.temporal import HistoricalDate, ranges_overlap


def test_initialization_migration_foreign_keys_and_persistence(tmp_path: Path):
    path = tmp_path / "vault.db"
    with VaultDB(path) as db:
        assert db.stats()["schema_version"] == 1
        assert db.conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        person = db.add_entity("person", "Ada Example", description="Fictional")
        db.update_entity(person, canonical_name="Ada Historical Example")
    with VaultDB(path) as db:
        assert db.get_entity(person)["canonical_name"] == "Ada Historical Example"


def test_source_hash_revision_and_unchanged_reingestion(tmp_path: Path):
    source = tmp_path / "memo.txt"
    source.write_text("First version", encoding="utf-8")
    with VaultDB(tmp_path / "vault.db") as db:
        doc, rev1, changed = ingest_document(db, source)
        assert changed and sha256_file(source)
        assert ingest_document(db, source) == (doc, rev1, False)
        source.write_text("Second version", encoding="utf-8")
        doc2, rev2, changed2 = ingest_document(db, source)
        assert doc2 == doc and rev2 != rev1 and changed2
        rows = db.conn.execute("SELECT revision_number, extracted_text FROM document_revisions ORDER BY revision_number").fetchall()
        assert [(r[0], r[1]) for r in rows] == [(1, "First version"), (2, "Second version")]


def test_copied_document_hash_preserves_alternate_location_without_duplicate(tmp_path: Path):
    first = tmp_path / "first.txt"; second = tmp_path / "second.txt"
    first.write_text("Identical record", encoding="utf-8"); second.write_text("Identical record", encoding="utf-8")
    with VaultDB(tmp_path / "vault.db") as db:
        document, revision, _ = ingest_document(db, first)
        assert ingest_document(db, second) == (document, revision, False)
        assert db.stats()["documents"] == 1
        assert {Path(item["location"]).name for item in db.get_document(document)["locations"]} == {"first.txt", "second.txt"}


def test_alias_resolution_and_ambiguous_identity_review(tmp_path: Path):
    with VaultDB(tmp_path / "vault.db") as db:
        first = db.add_entity("person", "Robert Example", aliases=["Bob Example"])
        assert db.resolve_entity("Bob Example")[0]["id"] == first
        db.add_entity("person", "Bob Example")
        assert len(db.resolve_entity("Bob Example", "person")) == 2
        assert len(db.list_review()["merge_suggestions"]) == 1


@pytest.mark.parametrize(
    "a_start,a_end,b_start,b_end,expected",
    [("1942", "1945", "1944", "1948", True), ("1942", "1943", "1944", "1948", False), (None, None, "1944", "1948", None)],
)
def test_exact_approximate_and_open_date_overlap(a_start, a_end, b_start, b_end, expected):
    def d(value):
        return HistoricalDate(value, "year" if value else "unknown", "possible" if value else "unknown")
    assert ranges_overlap(d(a_start), d(a_end), d(b_start), d(b_end)) is expected


def test_relationship_provenance_and_original_wording(tmp_path: Path):
    source = tmp_path / "record.md"; source.write_text("Alpha served in Unit Seven.", encoding="utf-8")
    with VaultDB(tmp_path / "vault.db") as db:
        _, revision, _ = ingest_document(db, source)
        alpha = db.add_entity("person", "Alpha Example")
        unit = db.add_entity("organization", "Unit Seven")
        claim = db.add_claim("Alpha served in Unit Seven.", original_wording="Alpha served in Unit Seven.", entity_ids=[alpha, unit])
        db.add_claim_evidence(claim, revision, locator="paragraph 1", original_wording="Alpha served in Unit Seven.")
        rel = db.add_relationship(alpha, unit, "served_in", revision_id=revision, claim_id=claim, locator="paragraph 1", original_wording="Alpha served in Unit Seven.")
        row = db.conn.execute("SELECT * FROM relationship_evidence WHERE relationship_id=?", (rel,)).fetchone()
        assert row["revision_id"] == revision and row["original_wording"] == "Alpha served in Unit Seven."
        document_id = db.conn.execute("SELECT document_id FROM document_revisions WHERE id=?", (revision,)).fetchone()[0]
        profile = db.get_document(document_id)
        assert profile["claims"][0]["locator"] == "paragraph 1"
        assert profile["relationships"][0]["id"] == rel


def test_contradictory_supplied_claims_are_both_preserved(tmp_path: Path):
    with VaultDB(tmp_path / "vault.db") as db:
        a = db.add_claim("The meeting occurred.", status="ACCEPTED TESTIMONY")
        b = db.add_claim("The meeting did not occur.", status="ACCEPTED TESTIMONY")
        conflict = db.add_conflict(a, b, reason="Two supplied witnesses disagree")
        review = db.list_review()["conflicts"][0]
        assert review["id"] == conflict and review["requires_author_review"] == 1
        assert db.stats()["claims"] == 2


def test_structured_import_search_export_and_idempotence(tmp_path: Path):
    source = tmp_path / "testimony.txt"; source.write_text("A witness account.", encoding="utf-8")
    package = tmp_path / "import.json"
    package.write_text(json.dumps({
        "schema_version": 1,
        "document": {"path": "testimony.txt", "title": "Witness Account", "source_classification": "author_supplied"},
        "entities": [{"ref": "p1", "entity_type": "person", "name": "Casey Witness", "aliases": ["C. Witness"]}],
        "claims": [{"ref": "c1", "statement": "Casey described the event.", "claim_type": "testimony", "status": "ACCEPTED TESTIMONY", "entity_refs": ["p1"], "locator": "line 1", "original_wording": "A witness account."}],
        "relationships": [], "conflicts": []
    }), encoding="utf-8")
    with VaultDB(tmp_path / "vault.db") as db:
        first = import_structured(db, package)
        second = import_structured(db, package)
        assert first["source_changed"] is True and second["source_changed"] is False
        assert db.stats()["entities"] == 1 and db.stats()["claims"] == 1
        assert db.search("Witness")["entities"]
        exported = db.export()
        assert exported["tables"]["claim_evidence"][0]["locator"] == "line 1"


def test_shared_unit_overlap_is_candidate_not_personal_relationship(tmp_path: Path):
    with VaultDB(tmp_path / "vault.db") as db:
        alice = db.add_entity("person", "Alice Fiction")
        ben = db.add_entity("person", "Ben Fiction")
        unit = db.add_entity("organization", "Fictional 101st Unit")
        db.add_relationship(alice, unit, "served_in", historical_start={"value": "1942", "precision": "year"}, historical_end={"value": "1945", "precision": "year"})
        db.add_relationship(ben, unit, "served_in", historical_start={"value": "1944", "precision": "year"}, historical_end={"value": "1948", "precision": "year"})
        candidates = SharedAffiliationProvider().discover(db)
        assert len(candidates) == 1 and "does not establish personal contact" in candidates[0].explanation
        assert db.conn.execute("SELECT COUNT(*) FROM relationships WHERE subject_entity_id IN (?,?) AND object_entity_id IN (?,?)", (alice, ben, alice, ben)).fetchone()[0] == 0


def test_foreign_key_rejects_untraceable_relationship(tmp_path: Path):
    with VaultDB(tmp_path / "vault.db") as db:
        person = db.add_entity("person", "Only Person")
        with pytest.raises(sqlite3.IntegrityError):
            db.add_relationship(person, "ENT-missing", "served_in")


def test_event_filter_and_manual_record_edits(tmp_path: Path):
    with VaultDB(tmp_path / "vault.db") as db:
        event = db.add_entity("event", "Fictional Hearing", details={
            "event_kind": "hearing", "start_value": "1952-03-04", "start_precision": "exact",
            "end_value": "1952-03-04", "end_precision": "exact", "date_certainty": "certain",
        })
        claim = db.add_claim("The hearing opened.")
        person = db.add_entity("person", "Hearing Witness")
        relationship = db.add_relationship(person, event, "appeared_at")
        db.update_claim(claim, statement="The fictional hearing opened.")
        db.update_relationship(relationship, classification="ACCEPTED TESTIMONY")
        assert db.events_between("1952-01-01", "1952-12-31")[0]["canonical_name"] == "Fictional Hearing"
        assert db.search("fictional hearing")["claims"][0]["id"] == claim
        assert db.get_entity(person)["relationships"][0]["classification"] == "ACCEPTED TESTIMONY"
