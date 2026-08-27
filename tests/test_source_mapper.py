from types import SimpleNamespace

from white_rabbit.schemas import AnchorChoice, AnchorMap
from white_rabbit.source_mapper import build_source_rows, strip_markers


def pair(url, entities=None):
    evidence = SimpleNamespace(entities=entities or [])
    source = SimpleNamespace(url=url)
    return evidence, source


def test_exact_anchor_and_duplicate_url_deduped():
    article = "**Agency Alpha** signed the contract. [[EV-0001]] Later, Agency Alpha expanded it. [[EV-0002]]"
    anchors = AnchorMap(anchors=[
        AnchorChoice(evidence_id="EV-0001", phrase="Agency Alpha"),
        AnchorChoice(evidence_id="EV-0002", phrase="Agency Alpha"),
    ])
    lookup = {
        "EV-0001": pair("https://example.gov/a", ["Agency Alpha"]),
        "EV-0002": pair("https://example.gov/a", ["Agency Alpha"]),
    }
    cleaned, rows, warnings = build_source_rows(article, anchors, lookup)
    assert "[[EV-" not in cleaned
    assert len(rows) == 1
    assert rows[0].phrase == "Agency Alpha"
    assert not warnings


def test_private_source_has_no_public_csv_row():
    article = "A private memo used the phrase Night Window. [[EV-0001]]"
    anchors = AnchorMap(anchors=[AnchorChoice(evidence_id="EV-0001", phrase="Night Window")])
    evidence = SimpleNamespace(entities=["Night Window"])
    source = SimpleNamespace(url=None)
    cleaned, rows, warnings = build_source_rows(article, anchors, {"EV-0001": (evidence, source)})
    assert rows == []
    assert "Night Window" in cleaned
