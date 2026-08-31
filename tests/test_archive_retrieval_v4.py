from pathlib import Path

from white_rabbit.archive_db import ArchiveDB
from white_rabbit.archive_retrieval import rebuild_archive_search_index, retrieve_archive_memory


def _add(db, root, title, slug, body, *, status="full", links=None):
    d = root / slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "article.md").write_text(body, encoding="utf-8")
    article, _, _ = db.upsert_article(
        title=title,
        slug=slug,
        canonical_url=f"https://example.substack.com/p/{slug}",
        published_date="2026-01-01",
        author="White Rabbit",
        content_hash=slug + status,
        content_status=status,
        local_dir=str(d),
        word_count=len(body.split()),
    )
    db.replace_links(article.canonical_url, links or [])
    return article


def test_v4_curates_concepts_and_rejects_single_word_rabbit_holes(tmp_path: Path):
    db_path = tmp_path / "knowledge" / "white_rabbit.db"
    root = tmp_path / "articles"
    db = ArchiveDB(db_path)
    try:
        _add(
            db, root, "Flock Safety Camera Network", "flock",
            """# Flock Safety Camera Network

## WHICH BRINGS US TO FLOCK
Flock Safety operates automatic license plate readers and ALPR roadside cameras. The network records vehicle movements, searchable license plate sightings, location tracking, police data, infrared surveillance imagery, and cross-jurisdiction camera networks. The patent US12322186B1 describes infrared wavelengths. Money people bring patent camera patent camera into the discussion.
""",
        )
        _add(
            db, root, "Patent Extensions in Pharmaceuticals", "pharma-patent",
            """# Patent Extensions

Drug companies use patent extensions, secondary patents, reform proposals, and clinical benefit claims to extend pharmaceutical monopolies.
""",
        )
        _add(
            db, root, "Broken Jail Cameras", "jail-camera",
            """# Broken Cameras

A jail had broken surveillance cameras outside a prison cell. Investigators reviewed camera failures and guard logs.
""",
        )
        _add(
            db, root, "Digital Location Profiles", "digital-location",
            """# Digital Location Profiles

Technology platforms aggregate location tracking, travel routes, movement histories, searchable behavioral data, databases, and analytics into persistent digital profiles.
""",
        )
    finally:
        db.close()

    rebuild_archive_search_index(db_path, force=True)
    results = retrieve_archive_memory(db_path, query="Flock Safety surveillance", article_limit=10, min_score=0.0)
    slugs = [r.article.slug for r in results]
    assert slugs[0] == "flock"
    assert "pharma-patent" not in slugs
    assert "jail-camera" not in slugs
    assert "digital-location" in slugs

    direct = results[0]
    assert direct.connection_tier == "DIRECT"
    assert "patent" not in direct.expanded_concepts
    assert "camera" not in direct.expanded_concepts
    assert "brings" not in direct.expanded_concepts
    assert "money people" not in direct.expanded_concepts
    assert any(
        phrase in direct.expanded_concepts
        for phrase in ("license plate", "license plate readers", "vehicle movements", "location tracking", "roadside cameras")
    )


def test_v4_returns_section_local_sources_not_whole_article_links(tmp_path: Path):
    db_path = tmp_path / "knowledge" / "white_rabbit.db"
    root = tmp_path / "articles"
    db = ArchiveDB(db_path)
    try:
        _add(
            db, root, "Glitter to Flock", "glitter-flock",
            """# Glitter to Flock

## Glitter history
Glitter manufacturing began decades ago.
[Old glitter article](https://example.com/glitter-history)
[Glitter company](https://example.com/glitter-company)

## WHICH BRINGS US TO FLOCK
Flock Safety ALPR cameras record license plates, vehicle movements, location tracking and searchable police surveillance data.
[Flock patent US12322186B1](https://patents.google.com/patent/US12322186B1/en)
[Flock Safety](https://www.flocksafety.com/)

## Another rabbit hole
Unrelated corporate material appears here.
[Unrelated corporate source](https://example.com/unrelated)
""",
        )
    finally:
        db.close()

    rebuild_archive_search_index(db_path, force=True)
    results = retrieve_archive_memory(db_path, query="Flock Safety surveillance", article_limit=3, min_score=0.0)
    assert results
    top = results[0]
    urls = [x["url"] for x in top.links if x["type"] == "external_research"]
    assert "https://patents.google.com/patent/US12322186B1/en" in urls
    assert "https://www.flocksafety.com/" in urls
    assert "https://example.com/glitter-history" not in urls
    assert "https://example.com/glitter-company" not in urls
    assert "https://example.com/unrelated" not in urls
    assert top.research_source_count == 2


def test_v4_connection_tiers_and_preview_penalty(tmp_path: Path):
    db_path = tmp_path / "knowledge" / "white_rabbit.db"
    root = tmp_path / "articles"
    db = ArchiveDB(db_path)
    try:
        _add(
            db, root, "Flock Safety", "flock",
            "# Flock Safety\n\nFlock Safety ALPR license plate readers track vehicle movements and police sightings across a camera network.",
        )
        _add(
            db, root, "Location Data Infrastructure", "location-full",
            "# Location Data\n\nSurveillance infrastructure combines location tracking, vehicle movement databases, analytics, searchable records and cross-jurisdiction data.",
        )
        _add(
            db, root, "Location Data Preview", "location-preview",
            "# Location Data\n\nSurveillance infrastructure combines location tracking, vehicle movement databases, analytics, searchable records and cross-jurisdiction data.",
            status="preview_only",
        )
    finally:
        db.close()

    rebuild_archive_search_index(db_path, force=True)
    results = retrieve_archive_memory(db_path, query="Flock Safety surveillance", article_limit=10, min_score=0.0)
    by_slug = {r.article.slug: r for r in results}
    assert by_slug["flock"].connection_tier == "DIRECT"
    assert by_slug["location-full"].connection_tier in {"RELATED INFRASTRUCTURE", "HISTORICAL / CONCEPTUAL PRECEDENT"}
    assert by_slug["location-preview"].preview_penalty < 1.0
    assert by_slug["location-preview"].score < by_slug["location-full"].score
