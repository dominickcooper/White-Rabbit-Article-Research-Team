from white_rabbit.archive_db import ArchiveArticle
from white_rabbit.archive_retrieval import ArchiveMemory
from white_rabbit.archive_reranker import apply_archive_rerank, format_candidates_for_rerank
from white_rabbit.schemas import ArchiveRelevanceBatch, ArchiveRelevanceJudgment


def article(wr_id: str, title: str) -> ArchiveArticle:
    return ArchiveArticle(
        wr_id=wr_id,
        title=title,
        slug=wr_id.lower(),
        canonical_url=f"https://thewhiterabbitreport.substack.com/p/{wr_id.lower()}",
        published_date="2026-01-01",
        author="WR",
        content_hash="x",
        content_status="full",
        local_dir=".",
        word_count=1000,
        last_seen="now",
        last_synced="now",
    )


def memory(wr_id: str, title: str, *, direct: bool = False, score: float = 0.5) -> ArchiveMemory:
    return ArchiveMemory(
        article=article(wr_id, title),
        excerpt="Relevant excerpt about cameras, vehicle tracking, and databases.",
        score=score,
        links=[{"type":"external_research","anchor":"Source","url":"https://example.com/source"}],
        exact_phrases=("flock safety",) if direct else (),
        connection_tier="DIRECT" if direct else "RELATED INFRASTRUCTURE",
        connection_type="direct entity match" if direct else "strong conceptual connection",
        best_section="Relevant section",
    )


def test_rerank_keeps_four_and_five_and_drops_three():
    memories = [
        memory("WR-1", "Direct", direct=True, score=1.0),
        memory("WR-2", "Good", score=0.5),
        memory("WR-3", "Weak", score=0.4),
    ]
    batch = ArchiveRelevanceBatch(judgments=[
        ArchiveRelevanceJudgment(wr_id="WR-1", score=5, reason="direct", relationship="direct"),
        ArchiveRelevanceJudgment(wr_id="WR-2", score=4, reason="useful", relationship="infrastructure"),
        ArchiveRelevanceJudgment(wr_id="WR-3", score=3, reason="context only", relationship="context"),
    ])
    results = apply_archive_rerank(memories, batch, min_score=4)
    by_id = {r.memory.article.wr_id: r for r in results}
    assert by_id["WR-1"].included is True
    assert by_id["WR-2"].included is True
    assert by_id["WR-3"].included is False


def test_direct_match_is_retained_even_if_gemini_scores_low():
    memories = [memory("WR-1", "Direct", direct=True)]
    batch = ArchiveRelevanceBatch(judgments=[
        ArchiveRelevanceJudgment(wr_id="WR-1", score=2, reason="mistaken low score")
    ])
    result = apply_archive_rerank(memories, batch, min_score=4)[0]
    assert result.included is True
    assert "direct" in result.inclusion_reason


def test_candidate_packet_contains_only_section_local_sources():
    m = memory("WR-1", "Direct", direct=True)
    text = format_candidates_for_rerank([m], max_source_links_per_article=1)
    assert "https://example.com/source" in text
    assert "WR-1" in text
    assert "Relevant section" in text
