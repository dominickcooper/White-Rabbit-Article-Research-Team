from __future__ import annotations

import json
from pathlib import Path
from threading import Thread
from urllib.error import URLError
from urllib.request import urlopen

import pytest

from white_rabbit.intelligence_vault.database import VaultDB
from white_rabbit.intelligence_vault.exploration import (
    connection_paths, entity_profile, graph_data, investigations_data,
    timeline_csv, timeline_data,
)
from white_rabbit.intelligence_vault.ingestion import ingest_document
from white_rabbit.intelligence_vault.web import handler_for
from http.server import ThreadingHTTPServer


def dated(value: str, precision: str = "year", certainty: str = "certain") -> dict:
    return {"value": value, "precision": precision, "certainty": certainty}


def fictional_network(tmp_path: Path) -> tuple[VaultDB, dict[str, str]]:
    db = VaultDB(tmp_path / "vault.db")
    ids = {
        "avery": db.add_entity("person", "Avery North", aliases=["A. North"],
                               details={"birth_value": "1925", "birth_precision": "year", "biography": "Signals officer."}),
        "blake": db.add_entity("person", "Blake Rowan"),
        "casey": db.add_entity("person", "Casey Vale"),
        "unit": db.add_entity("organization", "47th Analysis Unit", details={"organization_kind": "military_unit"}),
        "bank": db.add_entity("organization", "Northstar Bank", details={"organization_kind": "bank"}),
        "event": db.add_entity("event", "Operation Lantern", details={
            "event_kind": "operation", "start_value": "1962-03", "start_precision": "month",
            "start_certainty": "probable", "end_value": "1962-08", "end_precision": "month",
            "end_certainty": "uncertain",
        }),
        "place": db.add_entity("place", "West Germany", details={"place_kind": "country"}),
    }
    source = tmp_path / "lantern.txt"
    source.write_text("Avery served in the 47th Unit. The Unit retained Northstar Bank.", encoding="utf-8")
    document, revision, _ = ingest_document(db, source)
    ids["document"] = document
    claim = db.add_claim("Avery served in the 47th Analysis Unit.", entity_ids=[ids["avery"], ids["unit"]],
                         historical_start=dated("1960"), historical_end=dated("1962"))
    db.add_claim_evidence(claim, revision, locator="line 1", original_wording="Avery served in the 47th Unit.")
    ids["avery_unit"] = db.add_relationship(
        ids["avery"], ids["unit"], "served_in", revision_id=revision, claim_id=claim,
        locator="line 1", original_wording="Avery served in the 47th Unit.",
        historical_start=dated("1960"), historical_end=dated("1962"),
    )
    ids["blake_unit"] = db.add_relationship(
        ids["blake"], ids["unit"], "served_in",
        historical_start=dated("1961", "approximate", "possible"), historical_end=dated("1963"),
    )
    ids["unit_bank"] = db.add_relationship(
        ids["unit"], ids["bank"], "financial_relationship", classification="ACCEPTED TESTIMONY",
        revision_id=revision, locator="line 1", original_wording="The Unit retained Northstar Bank.",
        historical_start=dated("1962"), historical_end=dated("1965"),
    )
    ids["casey_bank"] = db.add_relationship(
        ids["casey"], ids["bank"], "director_of", classification="CORROBORATED INFERENCE",
        historical_start=dated("1970"), historical_end=dated("1975"),
    )
    db.add_relationship(ids["event"], ids["place"], "occurred_in", directed=True,
                        historical_start=dated("1962-03", "month", "probable"),
                        historical_end=dated("1962-08", "month", "uncertain"))
    inv_a = db.add_investigation("Lantern Files")
    inv_b = db.add_investigation("Northstar Ledger")
    ids["inv_a"], ids["inv_b"] = inv_a, inv_b
    for entity in (ids["avery"], ids["unit"], ids["event"]):
        db.attach_investigation(entity, inv_a)
    for entity in (ids["avery"], ids["bank"]):
        db.attach_investigation(entity, inv_b)
    db.attach_document_investigation(document, inv_a, "field report")
    db.attach_document_investigation(document, inv_b, "shared source")
    return db, ids


def test_graph_accepted_edges_evidence_candidates_and_no_invented_acquaintance(tmp_path: Path):
    db, ids = fictional_network(tmp_path)
    try:
        result = graph_data(db, focus_id=ids["unit"], depth=1, include_candidates=True,
                            include_documents=True, limit=100)
        accepted = {edge["id"] for edge in result["edges"] if edge["edge_kind"] == "accepted"}
        assert ids["avery_unit"] in accepted and ids["blake_unit"] in accepted
        assert all(edge["relationship_type"] != "personal_acquaintance" for edge in result["edges"])
        candidate = next(item for item in result["candidates"] if {item["subject_entity_id"], item["object_entity_id"]} == {ids["avery"], ids["blake"]})
        assert candidate["classification_kind"] == "exploratory_candidate"
        assert "does not establish personal contact" in candidate["explanation"]
        supported = next(item for item in result["edges"] if item["id"] == ids["avery_unit"])
        assert supported["evidence"][0]["locator"] == "line 1"
        assert any(node["entity_type"] == "document" for node in result["nodes"])
    finally:
        db.close()


def test_time_aware_graph_uses_four_state_model(tmp_path: Path):
    db, ids = fictional_network(tmp_path)
    try:
        confirmed = graph_data(db, focus_id=ids["unit"], depth=1, start="1961", end="1961",
                               temporal_mode="confirmed")
        possible = graph_data(db, focus_id=ids["unit"], depth=1, start="1961", end="1961",
                              temporal_mode="possible")
        wrong_period = graph_data(db, focus_id=ids["unit"], depth=1, start="1950", end="1950",
                                  temporal_mode="all")
        assert ids["avery_unit"] in {edge["id"] for edge in confirmed["edges"]}
        assert ids["blake_unit"] in {edge["id"] for edge in possible["edges"]}
        assert all(edge["temporal_overlap"] == "no_overlap" for edge in wrong_period["edges"])
        # 'all' deliberately shows date-incompatible edges, but never labels them active.
    finally:
        db.close()


def test_shortest_paths_directed_undirected_and_temporal_incompatibility(tmp_path: Path):
    db, ids = fictional_network(tmp_path)
    try:
        undirected = connection_paths(db, ids["avery"], ids["casey"], max_depth=4)
        assert undirected["paths"][0]["hop_count"] == 3
        assert undirected["paths"][0]["temporal_compatibility"]["state"] == "temporally_incompatible"
        assert "not proof" in undirected["paths"][0]["meaning_boundary"]
        directed = connection_paths(db, ids["avery"], ids["casey"], max_depth=4, respect_direction=True)
        assert directed["paths"] == []
        reverse_undirected = connection_paths(db, ids["casey"], ids["avery"], max_depth=4)
        assert reverse_undirected["paths"]
    finally:
        db.close()


def test_timeline_mixed_precision_ranges_source_filter_and_exports(tmp_path: Path):
    db, ids = fictional_network(tmp_path)
    try:
        result = timeline_data(db, start="1960", end="1965", source_id=ids["document"], limit=100)
        relationship = next(item for item in result["items"] if item["id"] == ids["avery_unit"])
        assert relationship["historical_start_precision"] == "year"
        assert relationship["evidence"][0]["document_id"] == ids["document"]
        events = timeline_data(db, start="1962-01", end="1962-12", event_type="operation")
        event = next(item for item in events["items"] if item["id"] == ids["event"])
        assert event["historical_start"] == "1962-03" and event["historical_start_precision"] == "month"
        assert event["temporal_overlap"] == "possible_overlap"
        csv_text = timeline_csv(events)
        assert "historical_start_precision" in csv_text and "1962-03" in csv_text
        assert json.loads(json.dumps(events))["window"] == {"start": "1962-01", "end": "1962-12"}
    finally:
        db.close()


def test_profile_preserves_claim_relationship_document_and_investigation_references(tmp_path: Path):
    db, ids = fictional_network(tmp_path)
    try:
        profile = entity_profile(db, ids["avery"])
        assert profile and "A. North" in profile["aliases"]
        assert profile["claims"][0]["evidence"][0]["locator"] == "line 1"
        assert profile["relationships"][0]["evidence"][0]["document_id"] == ids["document"]
        assert {item["id"] for item in profile["investigations"]} == {ids["inv_a"], ids["inv_b"]}
        assert profile["documents"][0]["id"] == ids["document"]
    finally:
        db.close()


def test_cross_investigation_comparison_uses_only_explicit_memberships(tmp_path: Path):
    db, ids = fictional_network(tmp_path)
    try:
        result = investigations_data(db, {ids["inv_a"], ids["inv_b"]})
        assert [item["id"] for item in result["shared_entities"]] == [ids["avery"]]
        assert ids["unit"] not in {item["id"] for item in result["shared_entities"]}
        assert [item["id"] for item in result["shared_documents"]] == [ids["document"]]
    finally:
        db.close()


def test_graph_and_timeline_pagination_empty_and_large_sets(tmp_path: Path):
    with VaultDB(tmp_path / "empty.db") as empty:
        assert graph_data(empty)["nodes"] == []
        assert timeline_data(empty)["items"] == []
    with VaultDB(tmp_path / "large.db") as db:
        hub = db.add_entity("organization", "Hub")
        for index in range(35):
            person = db.add_entity("person", f"Person {index:03d}")
            db.add_relationship(person, hub, "member_of", historical_start=dated(str(1900 + index)))
        first = graph_data(db, limit=10)
        second = graph_data(db, limit=10, cursor=first["page"]["next_cursor"])
        assert len(first["nodes"]) == 10 and first["page"]["next_cursor"]
        assert {x["id"] for x in first["nodes"]}.isdisjoint({x["id"] for x in second["nodes"]})
        timeline = timeline_data(db, limit=10)
        later = timeline_data(db, limit=10, cursor=timeline["page"]["next_cursor"])
        assert len(timeline["items"]) == len(later["items"]) == 10


def test_exploration_services_are_read_only(tmp_path: Path):
    db, ids = fictional_network(tmp_path)
    try:
        before = db.conn.total_changes
        graph_data(db, focus_id=ids["unit"], depth=3, include_candidates=True)
        timeline_data(db, start="1900", end="2000")
        connection_paths(db, ids["avery"], ids["casey"])
        entity_profile(db, ids["avery"])
        investigations_data(db, {ids["inv_a"], ids["inv_b"]})
        assert db.conn.total_changes == before
    finally:
        db.close()


def test_local_frontend_assets_and_read_endpoints_render_without_inline_untrusted_html(tmp_path: Path):
    static = Path(__file__).parents[1] / "white_rabbit" / "intelligence_vault" / "static"
    html = (static / "index.html").read_text(encoding="utf-8")
    script = (static / "app.js").read_text(encoding="utf-8")
    assert "Red String Board" in html and "script src=\"/static/vendor/cytoscape.min.js\"" in html
    assert 'id="extract-start"' in html and 'id="new-entity-add"' in html
    assert "onclick=" not in html
    assert "textContent" in script and "innerHTML" not in script
    assert (static / "vendor" / "cytoscape.min.js").stat().st_size > 400_000
    db, ids = fictional_network(tmp_path)
    db.close()
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(tmp_path / "vault.db"))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        try:
            root = urlopen(f"http://127.0.0.1:{server.server_port}/", timeout=5)
        except URLError as exc:
            if isinstance(exc.reason, PermissionError):
                pytest.skip("sandbox blocks loopback browser integration")
            raise
        html = root.read().decode()
        assert "Red String Board" in html and "script src=\"/static/vendor/cytoscape.min.js\"" in html
        assert "onclick=" not in html
        graph = json.loads(urlopen(
            f"http://127.0.0.1:{server.server_port}/api/graph?focus={ids['unit']}&depth=2", timeout=5
        ).read())
        assert graph["nodes"] and graph["edges"]
        profile = json.loads(urlopen(
            f"http://127.0.0.1:{server.server_port}/api/profiles/{ids['avery']}", timeout=5
        ).read())
        assert profile["canonical_name"] == "Avery North"
        served_script = urlopen(f"http://127.0.0.1:{server.server_port}/static/app.js", timeout=5).read().decode()
        assert served_script == script
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
