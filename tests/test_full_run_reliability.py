from pathlib import Path

from white_rabbit.archive_sync import SubstackArchiveSync
from white_rabbit.gemini_provider import GeminiProvider
from white_rabbit.schemas import EvidenceExtraction, ExtractedEvidence


def test_long_source_chunk_selection_prefers_relevant_later_section():
    noise = ("gardening recipes weather sports entertainment " * 900)
    relevant = (
        "COINTELPRO Church Committee FBI counterintelligence program disrupt neutralize "
        "Black nationalist surveillance memorandum " * 220
    )
    text = noise + "\n\n" + relevant + "\n\n" + noise
    chunks = GeminiProvider._select_source_chunks(
        text,
        "COINTELPRO Church Committee FBI surveillance",
        chunk_chars=5000,
        overlap=300,
        max_chunks=3,
    )
    assert 1 <= len(chunks) <= 3
    assert any("COINTELPRO" in chunk for chunk in chunks)


def test_evidence_schema_has_hard_output_bounds():
    schema = EvidenceExtraction.model_json_schema()
    assert schema["properties"]["source_summary"]["maxLength"] == 1200
    assert schema["properties"]["items"]["maxItems"] == 12
    item_schema = schema["$defs"]["ExtractedEvidence"]["properties"]
    assert item_schema["claim"]["maxLength"] == 1200
    assert item_schema["excerpt"]["anyOf"][0]["maxLength"] == 1200


def test_malformed_sitemap_recovers_post_urls(tmp_path: Path):
    syncer = SubstackArchiveSync(
        publication_url="https://example.substack.com",
        archive_root=tmp_path / "archive",
        db_path=tmp_path / "knowledge" / "white_rabbit.db",
        request_delay_ms=0,
    )
    malformed = """<?xml version='1.0'?>
    <urlset>
      <url><loc>https://example.substack.com/p/one</loc></url>
      <url><loc>https://example.substack.com/p/two</loc><bad>\x0b</bad></url>
      <url><loc>https://other.example.com/not-a-post</loc></url>
    </urlset>"""

    class Response:
        text = malformed

    try:
        syncer._get = lambda url: Response()  # type: ignore[method-assign]
        found = syncer._discover_from_sitemap("https://example.substack.com/sitemap")
        assert found == {
            "https://example.substack.com/p/one",
            "https://example.substack.com/p/two",
        }
    finally:
        syncer.close()


def test_evidence_model_rejects_unbounded_copying():
    try:
        ExtractedEvidence(claim="x" * 1300)
    except Exception:
        pass
    else:
        raise AssertionError("Expected oversized claim to be rejected")
