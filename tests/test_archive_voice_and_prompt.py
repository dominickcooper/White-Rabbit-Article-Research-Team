import json
import shutil
from pathlib import Path

from white_rabbit import codex_articles
from white_rabbit.archive_db import ArchiveDB
from white_rabbit.archive_retrieval import rebuild_archive_search_index
from white_rabbit.archive_voice import extract_authored_paragraphs, retrieve_voice_references


def _register(db_path: Path, article_dir: Path, *, slug: str, title: str, body: str, status: str = "full"):
    article_dir.mkdir(parents=True, exist_ok=True)
    (article_dir / "article.md").write_text(body, encoding="utf-8")
    db = ArchiveDB(db_path)
    try:
        db.upsert_article(
            title=title,
            slug=slug,
            canonical_url=f"https://example.substack.com/p/{slug}",
            published_date="2025-01-01T00:00:00Z",
            author="White Rabbit",
            content_hash=slug,
            content_status=status,
            local_dir=str(article_dir),
            word_count=len(body.split()),
        )
    finally:
        db.close()


def test_voice_segmentation_excludes_quotes_cards_and_ui():
    body = """# Investigation

The contract file named the intelligence adviser, and that sent me into the personnel records. Three pages later, the same man appeared beside the police program we had been tracing.

> Another person's long quoted statement should not become an author voice example in the voice corpus under any circumstances.

[Related story](https://example.com) Read full story

The record did something useful here. It turned an abstract contractor network into a sequence of people, dates, and decisions that a reader can follow without a glossary.

Subscribe for free to receive new posts and support my work.
"""
    paragraphs, stats = extract_authored_paragraphs(body)
    joined = " ".join(text for _, _, text in paragraphs)
    assert "contract file named" in joined
    assert "record did something useful" in joined
    assert "Another person's" not in joined
    assert "Related story" not in joined
    assert "Subscribe for free" not in joined
    assert stats["quotation_blocks_excluded"] == 1
    assert stats["ui_blocks_excluded"] >= 2


def test_voice_retrieval_uses_full_bodies_and_excludes_previews(tmp_path: Path):
    db_path = tmp_path / "knowledge/white_rabbit.db"
    body = (
        "# Contractor Trail\n\n"
        "The CIA contract led to a police adviser whose personnel file opened the next part of the network. "
        "I followed the dates, and the same contractor appeared inside the overseas program two years later. "
        "That was the receipt that changed the question."
    )
    _register(db_path, tmp_path / "articles/full", slug="full", title="Contractor Trail", body=body)
    _register(db_path, tmp_path / "articles/preview", slug="preview", title="Preview Trail", body=body, status="preview_only")
    result = retrieve_voice_references(db_path, "CIA intelligence contractor network", root=tmp_path)
    assert result.passages
    assert {p.article.slug for p in result.passages} == {"full"}
    assert result.partial_articles_excluded == 1


def test_codex_prompt_injects_distinct_live_canon_and_voice_packets(tmp_path: Path):
    required = {
        *codex_articles.AUTHORITY,
        "templates/ARTICLE_BRIEF_TEMPLATE.md",
        "white_rabbit_codex_config.json",
        "research_library/editorial_memory/VOICE_CANON.md",
        "research_library/editorial_memory/ANTI_PATTERNS.md",
        "research_library/editorial_memory/EDITORIAL_LESSONS.md",
        "research_library/editorial_memory/GOLD_ARTICLES.json",
    }
    from white_rabbit.editorial_memory import PROJECT_TEMPLATES
    required.update(f"templates/{name}" for name in PROJECT_TEMPLATES.values())
    for name in required:
        source = codex_articles.ROOT / name
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    project = codex_articles.new_project(tmp_path, "Intelligence contractor network")
    body = (
        "# The Contractor File\n\n"
        "The intelligence contract named a police adviser, and the personnel record connected him to the overseas program. "
        "I followed the name into the next file. That document changed the investigation by showing who moved between the agency and its contractor."
    )
    _register(
        tmp_path / "knowledge/white_rabbit.db",
        tmp_path / "research_library/previous_white_rabbit_articles/articles/2025/contractor-file",
        slug="contractor-file",
        title="The Contractor File",
        body=body,
    )
    rebuild_archive_search_index(tmp_path / "knowledge/white_rabbit.db", force=True)
    prompt = codex_articles.generate_prompt(tmp_path, project)
    assert "# PUBLISHED WHITE RABBIT CANON — RANKED FACTUAL RETRIEVAL" in prompt
    assert "# WHITE RABBIT VOICE REFERENCES — AUTHORED PROSE ONLY" in prompt
    assert "https://example.substack.com/p/contractor-file" in prompt
    assert "Authored passage:" in prompt
