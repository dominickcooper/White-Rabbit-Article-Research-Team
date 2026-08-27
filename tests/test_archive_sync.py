from pathlib import Path

from white_rabbit.archive_sync import SubstackArchiveSync


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
