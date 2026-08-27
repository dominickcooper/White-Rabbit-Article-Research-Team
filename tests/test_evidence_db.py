from pathlib import Path

from white_rabbit.evidence_db import EvidenceDB
from white_rabbit.schemas import ExtractedEvidence


def test_evidence_ids_and_packet(tmp_path: Path):
    db = EvidenceDB(tmp_path / "e.sqlite3")
    sid = db.add_source(title="Official Record", source_kind="public_web", url="https://example.gov/record", reliability="primary")
    eid = db.add_evidence(
        sid,
        ExtractedEvidence(
            claim="The agency created the program in 2001.",
            excerpt="created the program in 2001",
            reliability="primary",
            entities=["Agency"],
            significance="Establishes chronology.",
        ),
        excerpt_verified=True,
    )
    assert eid == "EV-0001"
    packet = db.build_packet()
    assert "EV-0001" in packet
    assert "https://example.gov/record" in packet
    assert "VERIFIED" in packet
    db.close()
