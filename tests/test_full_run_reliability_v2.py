from pathlib import Path

from white_rabbit.archive_sync import SubstackArchiveSync
from white_rabbit.gemini_provider import GeminiProvider
from white_rabbit.schemas import EvidenceExtraction
from white_rabbit.web_fetch import is_grounding_redirect, resolve_grounding_redirect


def _contains_key(value, target: str) -> bool:
    if isinstance(value, dict):
        return target in value or any(_contains_key(v, target) for v in value.values())
    if isinstance(value, list):
        return any(_contains_key(v, target) for v in value)
    return False


def test_interactions_schema_strips_unsupported_string_bounds_but_keeps_array_bounds():
    raw = EvidenceExtraction.model_json_schema()
    assert _contains_key(raw, "maxLength")
    cleaned = GeminiProvider._interaction_json_schema(EvidenceExtraction)
    assert not _contains_key(cleaned, "maxLength")
    assert not _contains_key(cleaned, "default")
    assert cleaned["properties"]["items"]["maxItems"] == 12


def test_grounding_redirect_is_resolved_before_destination_fetch(monkeypatch):
    wrapper = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc123"
    destination = "https://vault.fbi.gov/cointel-pro/cointel-pro-part-01/view"

    class FakeResponse:
        status_code = 302
        headers = {"location": destination}
        def __enter__(self): return self
        def __exit__(self, *args): return False

    class FakeClient:
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def stream(self, method, url):
            assert method == "GET"
            assert url == wrapper
            return FakeResponse()

    monkeypatch.setattr("white_rabbit.web_fetch.httpx.Client", lambda **kwargs: FakeClient())
    assert is_grounding_redirect(wrapper)
    assert resolve_grounding_redirect(wrapper) == destination
    assert not is_grounding_redirect(destination)


def test_direct_public_url_is_not_network_resolved(monkeypatch):
    direct = "https://www.fbi.gov/history/famous-cases/cointelpro"

    def fail_client(**kwargs):
        raise AssertionError("direct URL should not invoke redirect resolver network client")

    monkeypatch.setattr("white_rabbit.web_fetch.httpx.Client", fail_client)
    assert resolve_grounding_redirect(direct) == direct


def test_archive_discovery_tries_canonical_sitemap_xml_when_legacy_url_configured(tmp_path: Path):
    syncer = SubstackArchiveSync(
        publication_url="https://example.substack.com",
        archive_root=tmp_path / "archive",
        db_path=tmp_path / "knowledge" / "white_rabbit.db",
        sitemap_url="https://example.substack.com/sitemap",
        request_delay_ms=0,
    )
    seen: list[str] = []

    def fake_sitemap(url, seen_maps=None):
        seen.append(url)
        if url.endswith("/sitemap.xml"):
            return {"https://example.substack.com/p/full-archive-post"}
        return set()

    try:
        syncer._discover_from_sitemap = fake_sitemap  # type: ignore[method-assign]
        syncer._discover_from_feed = lambda: set()  # type: ignore[method-assign]
        syncer._discover_from_archive_page = lambda: set()  # type: ignore[method-assign]
        found = syncer.discover_post_urls()
        assert "https://example.substack.com/sitemap" in seen
        assert "https://example.substack.com/sitemap.xml" in seen
        assert found == ["https://example.substack.com/p/full-archive-post"]
    finally:
        syncer.close()
