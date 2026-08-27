from pathlib import Path

from white_rabbit.archive_db import ArchiveDB
from white_rabbit.archive_retrieval import (
    classify_link,
    clean_article_markdown,
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


def test_cleaner_removes_substack_chrome_but_keeps_article(tmp_path):
    raw = """[Shadow Reports](https://example.substack.com/s/shadow-reports)\n# FLOCK SAFETY INVESTIGATION\n\n[![avatar](https://substackcdn.com/image/fetch/avatar)](https://substack.com/@thewhiterabbitreport)\n[The White Rabbit Report](https://substack.com/@thewhiterabbitreport)\nAug 27, 2026\n\nFlock Safety cameras record vehicle movements across jurisdictions.\n\nThanks for reading The White Rabbit Report! Subscribe for free to receive new posts and support my work.\n"""
    cleaned = clean_article_markdown(raw, "FLOCK SAFETY INVESTIGATION")
    assert "Flock Safety cameras record vehicle movements" in cleaned
    assert "Shadow Reports" not in cleaned
    assert "substackcdn" not in cleaned
    assert "Thanks for reading" not in cleaned


def test_link_classification_filters_substack_chrome():
    article = "https://example.substack.com/p/flock"
    assert classify_link("https://example.substack.com/p/older-story", article) == "internal_article"
    assert classify_link("https://example.substack.com/s/shadow-reports", article) == "ignored"
    assert classify_link("https://substack.com/@thewhiterabbitreport", article) == "ignored"
    assert classify_link("https://www.justice.gov/report.pdf", article) == "external_research"


def test_entity_phrase_and_bm25_demote_generic_safety_matches(tmp_path: Path):
    db_path = tmp_path / "knowledge" / "white_rabbit.db"
    articles = tmp_path / "articles"
    db = ArchiveDB(db_path)
    try:
        _add(
            db, articles,
            "The Glitter Conspiracy and Flock Safety",
            "glitter-flock",
            """# THE GLITTER CONSPIRACY\n\n## From taggants to vehicle tracking\nFlock Safety operates ALPR cameras that record vehicle sightings. The network makes location surveillance searchable across jurisdictions.\n[Primary Flock source](https://www.flocksafety.com/)\n""",
        )
        _add(
            db, articles,
            "Vaccines and Rising Allergies",
            "vaccines",
            """# VACCINE SAFETY\n\nPublic-health researchers conduct ongoing safety surveillance to identify rare adverse events. Vaccine safety surveillance systems monitor reports.\n[CDC](https://www.cdc.gov/)\n""",
        )
        _add(
            db, articles,
            "Capitol Security",
            "capitol",
            """# CAPITOL SECURITY\n\nSecurity cameras and surveillance systems are used to improve public safety around government buildings.\n""",
        )
    finally:
        db.close()

    rebuild = rebuild_archive_search_index(db_path, force=True)
    assert rebuild["articles"] == 3
    assert rebuild["chunks"] >= 3

    results = retrieve_archive_memory(
        db_path,
        query="Flock Safety surveillance",
        article_limit=10,
        min_score=0.0,
    )
    assert results
    assert results[0].article.slug == "glitter-flock"
    assert "flock safety" in results[0].exact_phrases
    scores = {r.article.slug: r.score for r in results}
    assert scores["glitter-flock"] > scores.get("vaccines", 0) + 0.20
    assert scores["glitter-flock"] > scores.get("capitol", 0) + 0.20


def test_search_outputs_only_classified_research_links(tmp_path: Path):
    db_path = tmp_path / "knowledge" / "white_rabbit.db"
    articles = tmp_path / "articles"
    db = ArchiveDB(db_path)
    try:
        _add(
            db, articles,
            "Flock Safety Sources",
            "flock",
            """# Flock Safety Sources\n\nFlock Safety ALPR surveillance.\n[Shadow Reports](https://example.substack.com/s/shadow-reports)\n[Older White Rabbit story](https://example.substack.com/p/older-story)\n[DOJ report](https://www.justice.gov/example/report.pdf)\n""",
        )
    finally:
        db.close()
    memories = retrieve_archive_memory(db_path, query="Flock Safety", article_limit=2, min_score=0.0)
    assert memories
    kinds = {l["type"] for l in memories[0].links}
    assert "external_research" in kinds
    assert "internal_article" in kinds
    urls = {l["url"] for l in memories[0].links}
    assert "https://example.substack.com/s/shadow-reports" not in urls
