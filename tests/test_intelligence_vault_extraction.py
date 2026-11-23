from __future__ import annotations

import json
from pathlib import Path

import pymupdf
import pytest

from white_rabbit.intelligence_vault.database import VaultDB
from white_rabbit.intelligence_vault.extraction import (
    ExtractionConfig, bulk_decide, commit_approved, create_extraction_job, decide_proposal,
    extraction_review, prepare_manual_packet, process_extraction_job,
)
from white_rabbit.intelligence_vault.extraction_schema import ChunkExtraction
from white_rabbit.intelligence_vault.providers import (
    ExtractionProvider, ManualExtractionProvider, MockExtractionProvider, build_provider,
)


def _entity(ref: str, name: str, passage: str, *, identity: str | None = None,
            details: dict | None = None, entity_type: str = "person") -> dict:
    return {"ref": ref, "identity_key": identity, "entity_type": entity_type, "name": name,
            "details": details or {}, "supporting_passage": passage}


def _claim(ref: str, statement: str, passage: str, *, entities: list[str] | None = None,
           claim_type: str = "fact", attribution: str | None = None) -> dict:
    return {"ref": ref, "statement": statement, "original_passage": passage,
            "entity_refs": entities or [], "claim_type": claim_type, "attribution": attribution}


def _run(db: VaultDB, source: Path, provider: MockExtractionProvider,
         config: ExtractionConfig | None = None) -> str:
    job_id, _ = create_extraction_job(db, source, provider, config=config or ExtractionConfig(1000, 100))
    process_extraction_job(db, job_id, provider)
    return job_id


def test_extract_preview_approve_commit_preserves_people_event_relationship_and_attribution(tmp_path: Path):
    passage = "Witness Mara Vale told the author that she met Colonel Ivo Reed at Northstar Agency on June 4, 1962."
    source = tmp_path / "history.md"
    source.write_text("# Chapter One\n" + passage + "\n" + ("Context and chronology. " * 30), encoding="utf-8")
    provider = MockExtractionProvider({0: {
        "entities": [
            _entity("mara", "Mara Vale", "Mara Vale", identity="mara-vale", details={"birth_value": "1920", "birth_precision": "year"}),
            _entity("ivo", "Ivo Reed", "Colonel Ivo Reed", identity="ivo-reed"),
            _entity("agency", "Northstar Agency", "Northstar Agency", identity="northstar", entity_type="organization"),
            _entity("meeting", "Northstar meeting", passage, identity="northstar-meeting-1962", entity_type="event",
                    details={"event_kind": "meeting", "start_value": "1962-06-04", "start_precision": "exact", "start_certainty": "certain"}),
        ],
        "claims": [_claim("claim", "Mara Vale stated that she met Ivo Reed at Northstar Agency.", passage,
                          entities=["mara", "ivo", "agency", "meeting"], claim_type="testimony", attribution="Mara Vale, as reported by the author")],
        "relationships": [{"subject_ref": "mara", "object_ref": "agency", "relationship_type": "met_at",
                           "claim_ref": "claim", "supporting_passage": passage,
                           "historical_start": {"value": "1962-06-04", "precision": "exact", "certainty": "certain"}}],
        "document_metadata": [{"document_type": "interview notes", "sender": "Mara Vale",
                               "recipient": "the author", "document_date": "1962-06-04",
                               "supporting_passage": passage}],
    }})
    with VaultDB(tmp_path / "vault.db") as db:
        job = _run(db, source, provider)
        review = extraction_review(db, job)
        assert {p["proposal_type"] for p in review["proposals"]} == {"entity", "document_update", "claim", "relationship"}
        assert all(p["status"] == "pending" for p in review["proposals"])
        bulk_decide(db, job, "approve")
        committed = commit_approved(db, job)
        assert committed and db.stats()["entities"] == 4 and db.stats()["claims"] == 1
        claim = db.conn.execute("SELECT * FROM claims").fetchone()
        evidence = db.conn.execute("SELECT * FROM claim_evidence").fetchone()
        locator = json.loads(evidence["locator"])
        assert claim["claim_type"] == "testimony" and evidence["original_wording"] == passage
        assert evidence["attribution"] == "Mara Vale, as reported by the author"
        assert locator["section"] == "Chapter One" and locator["locator_incomplete"] is False
        assert db.conn.execute("SELECT COUNT(*) FROM extraction_approval_history WHERE action='commit'").fetchone()[0] >= 1
        assert db.get_document(review["job"]["document_id"])["metadata"]["sender"] == "Mara Vale"


def test_pdf_page_and_printed_label_locator_is_verified(tmp_path: Path):
    pdf = tmp_path / "pages.pdf"
    document = pymupdf.open()
    document.new_page().insert_text((72, 72), "First page background only.")
    document.new_page().insert_text((72, 72), "The second page records Project Lantern on March 3, 1951.")
    document.set_page_labels([{"startpage": 0, "prefix": "A-", "style": "D", "firstpagenum": 10}])
    document.save(pdf); document.close()
    passage = "The second page records Project Lantern on March 3, 1951."
    provider = MockExtractionProvider(callback=lambda chunk: ChunkExtraction.model_validate({
        "claims": [_claim("lantern", "Project Lantern was recorded on March 3, 1951.", passage)]
    }) if passage in chunk.text else ChunkExtraction())
    with VaultDB(tmp_path / "vault.db") as db:
        job = _run(db, pdf, provider, ExtractionConfig(500, 50))
        claim = next(p for p in extraction_review(db, job)["proposals"] if p["proposal_type"] == "claim")
        locator = claim["payload"]["evidence"][0]["locator"]
        assert locator["page_number"] == 2 and locator["page_label"] == "A-11"
        assert not [i for i in extraction_review(db, job)["issues"] if i["code"] == "claim_quote_missing"]


def test_long_document_all_chunks_resume_and_repeated_entity_reconciles(tmp_path: Path):
    source = tmp_path / "long.txt"
    source.write_text("\n".join(f"Section {i}: Agent Rowan worked for Meridian Office. " + "detail " * 40 for i in range(12)), encoding="utf-8")
    calls: list[int] = []
    def callback(chunk):
        calls.append(chunk.ordinal)
        passage = next((line for line in chunk.text.splitlines() if "Agent Rowan" in line), None)
        if not passage:
            return ChunkExtraction()
        return ChunkExtraction.model_validate({
            "entities": [_entity("rowan", "Agent Rowan", passage, identity="rowan-meridian")],
            "claims": [_claim("service", "Agent Rowan worked for Meridian Office.", passage, entities=["rowan"])],
        })
    provider = MockExtractionProvider(callback=callback)
    with VaultDB(tmp_path / "vault.db") as db:
        job = _run(db, source, provider, ExtractionConfig(500, 80))
        status = extraction_review(db, job)["job"]
        assert status["chunk_completed"] == status["chunk_total"] and status["chunk_total"] > 3
        review = extraction_review(db, job)
        assert len([p for p in review["proposals"] if p["proposal_type"] == "entity"]) == 1
        claims = [p for p in review["proposals"] if p["proposal_type"] == "claim"]
        assert len(claims) == 1 and len(claims[0]["payload"]["evidence"]) > 1
        first_calls = len(calls)
        process_extraction_job(db, job, provider)
        assert len(calls) == first_calls
        limited_job, _ = create_extraction_job(db, source, provider, config=ExtractionConfig(500, 80, 2))
        process_extraction_job(db, limited_job, provider)
        limited = extraction_review(db, limited_job)
        assert limited["job"]["chunk_total"] == 2
        assert any(issue["code"] == "configured_chunk_limit" for issue in limited["issues"])


def test_same_name_people_remain_distinct_and_existing_match_requires_approval(tmp_path: Path):
    source = tmp_path / "names.txt"
    source.write_text("Alex Stone born in 1910 served in Unit A. Alex Stone born in 1940 served in Unit B. " + "x " * 250, encoding="utf-8")
    provider = MockExtractionProvider({0: {"entities": [
        {**_entity("a", "Alex Stone", "Alex Stone born in 1910", identity="alex-1910", details={"birth_value": "1910", "birth_precision": "year"}), "aliases": ["A. Stone"]},
        _entity("b", "Alex Stone", "Alex Stone born in 1940", identity="alex-1940", details={"birth_value": "1940", "birth_precision": "year"}),
    ]}})
    with VaultDB(tmp_path / "vault.db") as db:
        existing = db.add_entity("person", "Alex Stone", details={"birth_value": "1910", "birth_precision": "year"})
        job = _run(db, source, provider)
        entities = [p for p in extraction_review(db, job)["proposals"] if p["proposal_type"] == "entity"]
        assert len(entities) == 2 and all(p["payload"]["candidate_matches"] for p in entities)
        matching = next(p for p in entities if p["payload"]["details"]["birth_value"] == "1910")
        decide_proposal(db, job, matching["id"], "approve", known_entity_id=existing)
        other = next(p for p in entities if p != matching); decide_proposal(db, job, other["id"], "approve")
        commit_approved(db, job)
        assert db.stats()["person"] == 2
        assert "A. Stone" in db.get_entity(existing)["aliases"]


def test_quote_failure_and_missing_attribution_block_approval(tmp_path: Path):
    source = tmp_path / "claims.txt"; source.write_text("A witness discussed Operation Ember. " + "x " * 300, encoding="utf-8")
    provider = MockExtractionProvider({0: {"claims": [
        _claim("badquote", "An invented detail.", "This quotation is not present."),
        _claim("unattributed", "A witness alleged misconduct.", "A witness discussed Operation Ember.", claim_type="allegation"),
    ]}})
    with VaultDB(tmp_path / "vault.db") as db:
        job = _run(db, source, provider)
        review = extraction_review(db, job)
        assert {i["code"] for i in review["issues"]} >= {"claim_quote_missing", "missing_attribution"}
        for proposal in review["proposals"]:
            with pytest.raises(ValueError, match="blocking"):
                decide_proposal(db, job, proposal["id"], "approve")
        assert bulk_decide(db, job, "reject") == 2
        assert commit_approved(db, job) == {}


def test_interrupted_failed_and_malformed_provider_outputs_can_resume(tmp_path: Path):
    source = tmp_path / "resume.txt"; source.write_text("Recoverable source. " + "x " * 300, encoding="utf-8")
    failing = MockExtractionProvider({0: RuntimeError("temporary outage")})
    with VaultDB(tmp_path / "vault.db") as db:
        job, _ = create_extraction_job(db, source, failing, config=ExtractionConfig(500, 50))
        first = process_extraction_job(db, job, failing)
        assert first["chunk_failed"] >= 1
        with pytest.raises(ValueError, match="blocking quality"):
            commit_approved(db, job)
        passage = "Recoverable source."
        recovered = MockExtractionProvider(callback=lambda chunk: ChunkExtraction.model_validate({
            "claims": [_claim("recovered", "The source was recovered.", passage)]
        }) if passage in chunk.text else ChunkExtraction())
        final = process_extraction_job(db, job, recovered, retry_failed=True)
        assert final["chunk_failed"] == 0 and final["chunk_completed"] == final["chunk_total"]

    malformed = tmp_path / "malformed.txt"; malformed.write_text("Malformed output source. " + "x " * 300, encoding="utf-8")
    bad = MockExtractionProvider({0: {"unsupported": True}})
    with VaultDB(tmp_path / "bad.db") as db:
        job, _ = create_extraction_job(db, malformed, bad, config=ExtractionConfig(500, 50))
        assert process_extraction_job(db, job, bad)["chunk_failed"] >= 1

    interrupted_source = tmp_path / "interrupted.txt"
    interrupted_source.write_text("Interrupted but resumable source. " + "z " * 300, encoding="utf-8")
    resumed = MockExtractionProvider(callback=lambda chunk: ChunkExtraction())
    with VaultDB(tmp_path / "interrupted.db") as db:
        job, _ = create_extraction_job(db, interrupted_source, resumed, config=ExtractionConfig(500, 50))
        with db.transaction():
            db.conn.execute("UPDATE extraction_jobs SET status='processing' WHERE id=?", (job,))
            db.conn.execute("UPDATE extraction_chunks SET status='processing' WHERE job_id=? AND ordinal=0", (job,))
        status = process_extraction_job(db, job, resumed)
        assert status["chunk_completed"] == status["chunk_total"]


def test_rejected_proposals_never_enter_accepted_graph(tmp_path: Path):
    source = tmp_path / "reject.txt"; source.write_text("Dana North appeared in the record. " + "x " * 300, encoding="utf-8")
    provider = MockExtractionProvider({0: {"entities": [_entity("dana", "Dana North", "Dana North appeared in the record.", identity="dana")]}})
    with VaultDB(tmp_path / "vault.db") as db:
        job = _run(db, source, provider)
        proposal = extraction_review(db, job)["proposals"][0]
        decide_proposal(db, job, proposal["id"], "reject")
        assert commit_approved(db, job) == {}
        assert db.stats()["entities"] == 0


def test_contradictory_supplied_documents_create_reviewable_conflict(tmp_path: Path):
    first = tmp_path / "first.txt"; first.write_text("Operation Aurora was active. " + "x " * 300, encoding="utf-8")
    second = tmp_path / "second.txt"; second.write_text("Operation Aurora was not active. " + "y " * 300, encoding="utf-8")
    with VaultDB(tmp_path / "vault.db") as db:
        p1 = MockExtractionProvider({0: {"claims": [_claim("c1", "Operation Aurora was active", "Operation Aurora was active.")]}})
        job1 = _run(db, first, p1); bulk_decide(db, job1, "approve"); commit_approved(db, job1)
        p2 = MockExtractionProvider({0: {"claims": [_claim("c2", "Operation Aurora was not active", "Operation Aurora was not active.")]}})
        job2 = _run(db, second, p2)
        review = extraction_review(db, job2)
        assert any(p["proposal_type"] == "conflict" for p in review["proposals"])


def test_repeated_claims_across_documents_preserve_dependency_and_two_sources(tmp_path: Path):
    first = tmp_path / "account-one.txt"; second = tmp_path / "account-two.txt"
    first.write_text("The Meridian Office opened in 1950. " + "a " * 300, encoding="utf-8")
    second.write_text("The Meridian Office opened in 1950. " + "b " * 300, encoding="utf-8")
    extraction = {"claims": [{
        **_claim("opening", "The Meridian Office opened in 1950.", "The Meridian Office opened in 1950."),
        "independent": False, "dependency_group": "same-archival-register",
    }]}
    with VaultDB(tmp_path / "vault.db") as db:
        for source in (first, second):
            provider = MockExtractionProvider({0: extraction})
            job = _run(db, source, provider); bulk_decide(db, job, "approve"); commit_approved(db, job)
        assert db.stats()["claims"] == 1
        evidence = db.conn.execute("SELECT independent,dependency_group FROM claim_evidence").fetchall()
        assert len(evidence) == 2 and all(not row["independent"] for row in evidence)
        assert {row["dependency_group"] for row in evidence} == {"same-archival-register"}


def test_manual_provider_and_cloud_provider_require_explicit_opt_in(tmp_path: Path):
    source = tmp_path / "manual.txt"; source.write_text("Manual record. " + "x " * 300, encoding="utf-8")
    results = tmp_path / "results.json"; results.write_text(json.dumps({"0": {"claims": [_claim("m", "A manual record exists.", "Manual record.")]}}), encoding="utf-8")
    provider = ManualExtractionProvider(results)
    with VaultDB(tmp_path / "vault.db") as db:
        job, _ = create_extraction_job(db, source, provider, config=ExtractionConfig(500, 50))
        assert process_extraction_job(db, job, provider)["chunk_completed"] >= 1
    with pytest.raises(PermissionError, match="allow-cloud"):
        build_provider("gemini", allow_cloud=False)

    class CloudProvider(ExtractionProvider):
        name = "cloud-test"; model = "test"; sends_data_off_device = True
        def extract(self, chunk, *, document_title): return None
    with VaultDB(tmp_path / "cloud.db") as db:
        with pytest.raises(PermissionError, match="allow_cloud"):
            create_extraction_job(db, source, CloudProvider())
        assert db.stats()["documents"] == 0


def test_checked_in_fictional_manual_demo_processes(tmp_path: Path):
    root = Path(__file__).resolve().parents[1] / "examples" / "intelligence_vault_phase2"
    provider = ManualExtractionProvider(root / "northstar_results.json")
    with VaultDB(tmp_path / "vault.db") as db:
        job, _ = create_extraction_job(db, root / "northstar_testimony.md", provider)
        status = process_extraction_job(db, job, provider)
        assert status["chunk_completed"] == 1 and status["chunk_failed"] == 0
        review = extraction_review(db, job)
        assert len(review["proposals"]) == 5
        assert not [issue for issue in review["issues"] if issue["severity"] == "blocking"]


def test_offline_manual_packet_contains_every_selected_chunk_and_template(tmp_path: Path):
    source = tmp_path / "offline.md"
    source.write_text("# Offline source\n" + ("Historical paragraph with names and dates.\n" * 80), encoding="utf-8")
    packet = prepare_manual_packet(source, tmp_path / "packet", config=ExtractionConfig(500, 50))
    manifest = json.loads((packet / "manifest.json").read_text(encoding="utf-8"))
    chunks = sorted(packet.glob("chunk-*.json"))
    template = json.loads((packet / "results.template.json").read_text(encoding="utf-8"))
    assert manifest["chunk_count"] == len(chunks) == len(template) and len(chunks) > 2
    assert all(json.loads(path.read_text(encoding="utf-8"))["text"] for path in chunks)
