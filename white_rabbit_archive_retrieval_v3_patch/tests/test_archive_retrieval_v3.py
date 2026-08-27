from pathlib import Path

from white_rabbit.archive_db import ArchiveDB
from white_rabbit.archive_retrieval import (
    _detect_query_entities,
    rebuild_archive_search_index,
    retrieve_archive_memory,
)


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
    return article


def test_entity_parser_keeps_brand_atomic_and_acronym_separate():
    assert _detect_query_entities("Flock Safety surveillance") == ("flock safety",)
    assert _detect_query_entities("Flock Safety ALPR surveillance") == ("flock safety", "alpr")


def test_entity_gate_rejects_standalone_safety_false_positives(tmp_path: Path):
    db_path = tmp_path / "knowledge" / "white_rabbit.db"
    root = tmp_path / "articles"
    db = ArchiveDB(db_path)
    try:
        _add(
            db, root, "Flock Safety and the Camera Network", "flock",
            "# Flock Safety\n\nFlock Safety ALPR cameras record license plates and vehicle movements. Police can search surveillance sightings across jurisdictions.",
        )
        _add(
            db, root, "Private Camera Networks and Location Tracking", "camera-networks",
            "# Camera Networks\n\nAutomatic license plate readers connect police cameras, vehicle tracking, searchable location data, and cross-jurisdiction surveillance networks.",
        )
        _add(
            db, root, "Vaccine Safety Surveillance", "vaccines",
            "# Vaccine Safety\n\nPublic health agencies operate vaccine safety surveillance systems for adverse-event monitoring and medical safety reviews.",
        )
        _add(
            db, root, "Drug Safety at the FDA", "drug-safety",
            "# Drug Safety\n\nThe FDA evaluates pharmaceutical safety and adverse events for approved medications.",
        )
    finally:
        db.close()

    rebuild_archive_search_index(db_path, force=True)
    results = retrieve_archive_memory(db_path, query="Flock Safety surveillance", article_limit=10, min_score=0.0)
    slugs = [r.article.slug for r in results]
    assert slugs[0] == "flock"
    assert "camera-networks" in slugs
    assert "vaccines" not in slugs
    assert "drug-safety" not in slugs
    conceptual = next(r for r in results if r.article.slug == "camera-networks")
    assert conceptual.connection_type in {"strong conceptual connection", "background connection"}
    assert conceptual.expanded_concepts


def test_internal_links_are_canonicalized_and_junk_share_links_removed(tmp_path: Path):
    db_path = tmp_path / "knowledge" / "white_rabbit.db"
    root = tmp_path / "articles"
    db = ArchiveDB(db_path)
    try:
        target = _add(
            db, root, "BlackRock's Aladdin: The AI Quietly Watching", "blackrocks-aladdin",
            "# BlackRock's Aladdin\n\nFinancial surveillance and analytics.",
        )
        _add(
            db, root, "Flock Safety Sources", "flock",
            """# Flock Safety Sources

Flock Safety ALPR surveillance and vehicle tracking.
[Read full story](https://example.substack.com/p/blackrocks-aladdin?utm_source=substack&utm_medium=email)
[BlackRock research](https://example.substack.com/p/blackrocks-aladdin?utm_source=substack)
[Share](https://example.substack.com/p/flock?action=share&utm_source=substack)
[DOJ report](https://www.justice.gov/report.pdf)
""",
        )
    finally:
        db.close()

    results = retrieve_archive_memory(db_path, query="Flock Safety surveillance", article_limit=3, min_score=0.0)
    flock = next(r for r in results if r.article.slug == "flock")
    internal = [x for x in flock.links if x["type"] == "internal_article"]
    assert len(internal) == 1
    assert internal[0]["url"] == target.canonical_url
    assert internal[0]["anchor"] == target.title
    assert internal[0]["title"] == target.title
    assert not any(x.get("original_anchor", "").lower() == "share" for x in internal)
