from white_rabbit.json_repair import parse_structured
from white_rabbit.schemas import EvidenceExtraction


def test_recovers_complete_items_from_truncated_extraction():
    blob = '''{
  "relevant": true,
  "source_summary": "Church Committee overview",
  "items": [
    {"claim": "COINTELPRO was exposed in 1971", "excerpt": "exposed in 1971", "support_type": "documented_fact", "reliability": "primary", "entities": ["COINTELPRO"], "significance": "origin"},
    {"claim": "Book III reviewed FBI programs", "excerpt": "Book III", "support_type": "documented_fact", "reliability": "primary", "entities": ["Church Committee"], "significance": "record"
'''
    parsed = parse_structured(blob, EvidenceExtraction)
    assert parsed.relevant is True
    assert len(parsed.items) == 1
    assert "1971" in parsed.items[0].claim
