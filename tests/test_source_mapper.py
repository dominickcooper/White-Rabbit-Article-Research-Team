from types import SimpleNamespace

from white_rabbit.pipeline import verify_excerpt
from white_rabbit.schemas import AnchorChoice, AnchorMap
from white_rabbit.source_mapper import build_source_rows


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


def test_unknown_evidence_marker_is_warned_not_linked():
    article = "A claim with no vault record. [[EV-9999]]"
    anchors = AnchorMap(anchors=[AnchorChoice(evidence_id="EV-9999", phrase="claim")])
    cleaned, rows, warnings = build_source_rows(article, anchors, {})
    assert rows == []
    assert any("Unknown evidence marker: EV-9999" in w for w in warnings)
    assert "[[EV-" not in cleaned


def test_invalid_anchor_falls_back_to_entity_then_warns():
    article = "The Oversight Board issued the memo in 2019. [[EV-0001]]"
    anchors = AnchorMap(anchors=[AnchorChoice(evidence_id="EV-0001", phrase="this phrase is not in the article")])
    lookup = {"EV-0001": pair("https://example.gov/memo", ["Oversight Board"])}
    cleaned, rows, warnings = build_source_rows(article, anchors, lookup)
    assert rows[0].phrase == "Oversight Board"
    assert rows[0].phrase in cleaned
    assert not warnings


def test_verify_excerpt_requires_exact_normalized_match():
    source = "Project Night Window began in 2001 after the review."
    assert verify_excerpt("Project Night Window began in 2001", source)
    assert verify_excerpt("project   night window began in 2001", source)
    assert not verify_excerpt("Project Night Window began in 1999", source)
    assert not verify_excerpt("", source)
