import json
from pathlib import Path

import pytest

from white_rabbit.archive_sync import (
    ArticleSnapshot,
    SubstackArchiveSync,
    detect_preview_boundary,
    reconcile_local_preview_statuses,
)


def test_extract_and_store_article(tmp_path: Path):
    html = """
    <html><head>
      <link rel="canonical" href="https://example.substack.com/p/test-post">
      <meta property="og:title" content="Test Post">
      <meta property="article:published_time" content="2026-08-20T10:00:00Z">
      <meta name="author" content="White Rabbit">
    </head><body>
      <div class="available-content">
        <h2>THE RECORD</h2>
        <p>This is a sufficiently long article paragraph containing documented material for testing the archive importer and its Markdown conversion. It needs enough text that the extractor does not reject it as an empty page.</p>
        <p>See <a href="https://example.gov/report.pdf">the government report</a>.</p>
      </div>
    </body></html>
    """
    syncer = SubstackArchiveSync(
        publication_url="https://example.substack.com",
        archive_root=tmp_path / "archive",
        db_path=tmp_path / "knowledge" / "white_rabbit.db",
        request_delay_ms=0,
    )
    try:
        snap = syncer.extract_snapshot(html, "https://example.substack.com/p/test-post")
        assert snap.title == "Test Post"
        assert snap.content_status == "full"
        assert snap.links[0]["anchor"] == "the government report"
        wr_id, created, changed = syncer.store_snapshot(snap)
        assert wr_id == "WR-000001"
        assert created and changed
        assert (tmp_path / "archive" / "articles" / "2026" / "test-post" / "article.md").exists()
        # Re-storing identical content must not create a second article.
        wr_id2, created2, changed2 = syncer.store_snapshot(snap)
        assert wr_id2 == wr_id
        assert not created2
        assert not changed2
    finally:
        syncer.close()


def test_paywall_preview_is_flagged(tmp_path: Path):
    html = """
    <html><head><link rel="canonical" href="https://example.substack.com/p/paid"></head>
    <body><article><h1>Paid</h1><p>This preview contains enough explanatory text to be retained rather than discarded by the importer. It is intentionally a little longer for the test harness to accept it as article text.</p><p>Subscribe to continue reading</p></article></body></html>
    """
    syncer = SubstackArchiveSync(
        publication_url="https://example.substack.com",
        archive_root=tmp_path / "archive",
        db_path=tmp_path / "knowledge" / "white_rabbit.db",
        request_delay_ms=0,
    )
    try:
        snap = syncer.extract_snapshot(html, "https://example.substack.com/p/paid")
        assert snap.content_status == "preview_only"
    finally:
        syncer.close()


@pytest.mark.parametrize("boundary", [
    "Subscribe to continue reading",
    "Continue reading this post for free in the Substack app",
    "This post is for paid subscribers. Upgrade to paid to read the rest.",
    "Continue reading this post. Or purchase a paid subscription.",
])
def test_substack_continuation_boundaries(boundary: str):
    article = f"# Report\n\nA substantial captured preview with documentary material.\n\n{boundary}"
    assert detect_preview_boundary(article)


def test_ordinary_subscription_cta_is_not_a_preview():
    article = """# Full report

This is the complete article, including its conclusion and final evidentiary judgment.

Thanks for reading. Subscribe for free to receive new posts and support my work.
You may also purchase a paid subscription if you want to support this publication.
"""
    assert detect_preview_boundary(article) is None


def test_continuation_language_must_be_near_the_capture_boundary():
    article = (
        "A historical quotation said subscribe to continue reading. "
        + "Complete analysis follows here. " * 300
        + "Final conclusion."
    )
    assert detect_preview_boundary(article) is None


def test_local_reconciliation_updates_status_without_changing_capture(tmp_path: Path):
    archive_root = tmp_path / "archive"
    db_path = tmp_path / "knowledge" / "white_rabbit.db"
    markdown = (
        "# Limited report\n\nA retained source-backed preview that is long enough for storage.\n\n"
        "Continue reading this post for free in the Substack app"
    )
    snapshot = ArticleSnapshot(
        title="Limited report",
        slug="limited-report",
        canonical_url="https://example.substack.com/p/limited-report",
        published_date="2026-09-20T00:00:00Z",
        author="White Rabbit",
        markdown=markdown,
        links=[],
        content_status="full",
    )
    syncer = SubstackArchiveSync(
        publication_url="https://example.substack.com",
        archive_root=archive_root,
        db_path=db_path,
        request_delay_ms=0,
    )
    try:
        syncer.store_snapshot(snapshot)
    finally:
        syncer.close()

    article_path = archive_root / "articles/2026/limited-report/article.md"
    captured = article_path.read_bytes()
    report = reconcile_local_preview_statuses(
        archive_root,
        db_path,
        report_path=archive_root / "sync/preview_reconciliation_report.json",
    )
    metadata = json.loads(article_path.with_name("metadata.json").read_text(encoding="utf-8"))
    assert report["reclassified_records"] == 1
    assert metadata["content_status"] == "preview_only"
    assert report["database"]["preview_only"] == 1
    assert article_path.read_bytes() == captured
