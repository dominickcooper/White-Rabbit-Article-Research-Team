from pathlib import Path
from white_rabbit.archive_db import ArchiveDB
from white_rabbit.archive_retrieval import retrieve_archive_memory


def _add(db, root, title, slug, body, links=None):
    d = root / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "article.md").write_text(body, encoding="utf-8")
    article, _, _ = db.upsert_article(
        title=title,
        slug=slug,
        canonical_url=f"https://example.substack.com/p/{slug}",
        published_date="2026-01-01",
        author="White Rabbit",
        content_hash=slug,
        content_status="full",
        local_dir=str(d),
        word_count=len(body.split()),
    )
    db.replace_links(article.canonical_url, links or [])


def test_hybrid_archive_search_prefers_title_body_and_link_matches(tmp_path):
    db_path = tmp_path / "archive.db"
    articles = tmp_path / "articles"
    db = ArchiveDB(db_path)
    try:
        _add(db, articles, "Glitter Conspiracy and Flock Safety", "glitter-flock",
             "Flock Safety ALPR cameras connect vehicle movement to searchable surveillance databases.",
             [{"anchor": "Flock Safety", "url": "https://www.flocksafety.com", "type": "external"}])
        _add(db, articles, "Operation Gladio History", "gladio",
             "Cold War stay-behind networks and covert operations in Europe.")
    finally:
        db.close()

    results = retrieve_archive_memory(db_path, query="Flock Safety surveillance", article_limit=5)
    assert results
    assert results[0].article.slug == "glitter-flock"
    assert "flock" in results[0].matched_terms
    assert results[0].score > 0
