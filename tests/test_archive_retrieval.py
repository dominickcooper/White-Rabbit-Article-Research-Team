from pathlib import Path

from white_rabbit.archive_retrieval import format_archive_memory, retrieve_archive_memory
from white_rabbit.archive_sync import ArticleSnapshot, SubstackArchiveSync


def test_retrieval_returns_relevant_previous_article(tmp_path: Path):
    syncer = SubstackArchiveSync(
        publication_url="https://example.substack.com",
        archive_root=tmp_path / "research_library" / "previous_white_rabbit_articles",
        db_path=tmp_path / "knowledge" / "white_rabbit.db",
        request_delay_ms=0,
    )
    try:
        syncer.store_snapshot(ArticleSnapshot(
            title="Flock Safety and ALPR Networks",
            slug="flock-safety",
            canonical_url="https://example.substack.com/p/flock-safety",
            published_date="2026-08-20T00:00:00Z",
            author="White Rabbit",
            markdown="# Flock\n\nFlock Safety automated license plate reader cameras connect vehicle sightings across jurisdictions and raise questions about networked surveillance.",
            links=[{"anchor": "Flock Safety", "url": "https://www.flocksafety.com", "type": "external"}],
            content_status="full",
        ))
        syncer.store_snapshot(ArticleSnapshot(
            title="Unrelated Agriculture Story",
            slug="agriculture",
            canonical_url="https://example.substack.com/p/agriculture",
            published_date="2026-08-19T00:00:00Z",
            author="White Rabbit",
            markdown="# Agriculture\n\nA story about wheat harvest yields and farm machinery.",
            links=[],
            content_status="full",
        ))
    finally:
        syncer.close()

    memories = retrieve_archive_memory(
        tmp_path / "knowledge" / "white_rabbit.db",
        query="Flock Safety ALPR surveillance",
        chunk_limit=5,
        article_limit=1,
    )
    assert len(memories) == 1
    assert memories[0].article.slug == "flock-safety"
    text = format_archive_memory(memories)
    assert "DO NOT treat a prior White Rabbit assertion as proof" in text
    assert "https://www.flocksafety.com" in text
