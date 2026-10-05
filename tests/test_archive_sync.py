import json
import zipfile
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


def test_structured_dates_access_and_substack_ui_cleaning(tmp_path: Path):
    html = """
    <html><head>
      <link rel="canonical" href="https://example.substack.com/p/clean-post">
      <meta property="og:title" content="Clean Post">
      <script type="application/ld+json">{
        "@context":"https://schema.org", "@type":"NewsArticle",
        "datePublished":"2025-04-03T10:00:00Z",
        "dateModified":"2025-04-04T11:00:00Z",
        "isAccessibleForFree":false
      }</script>
    </head><body><article><div class="body markup">
      <p>This authored opening paragraph contains enough documentary detail to qualify as preserved body prose for the archive and its factual retrieval index.</p>
      <div class="digestPostEmbed-flwiST"><p>Related story copied preview</p><a>Read full story</a></div>
      <p>This second authored paragraph remains after the related-post card is removed and gives the test enough real prose for a partial paid preview.</p>
      <div class="subscription-widget-wrap">Subscribe for free</div>
    </div></article></body></html>
    """
    syncer = SubstackArchiveSync(
        publication_url="https://example.substack.com",
        archive_root=tmp_path / "archive",
        db_path=tmp_path / "knowledge" / "white_rabbit.db",
        request_delay_ms=0,
    )
    try:
        snap = syncer.extract_snapshot(html, "https://example.substack.com/p/clean-post")
        assert snap.published_date == "2025-04-03T10:00:00Z"
        assert snap.updated_date == "2025-04-04T11:00:00Z"
        assert snap.access_level == "PARTIAL_PREVIEW"
        assert snap.markdown.startswith("# Clean Post")
        assert "Read full story" not in snap.markdown
        assert "Subscribe for free" not in snap.markdown
        assert "second authored paragraph" in snap.markdown
    finally:
        syncer.close()


def test_owner_export_import_reads_posts_only_and_marks_full(tmp_path: Path):
    export = tmp_path / "export"
    export.mkdir()
    (export / "posts.csv").write_text(
        "post_id,title,slug,post_date,body_html\n"
        '42,Owner Full Post,owner-full,2024-02-01T00:00:00Z,"<p>This is the complete owner-exported article body with enough authored prose to pass extraction and be indexed honestly as full owner material rather than an anonymous preview.</p>"\n',
        encoding="utf-8",
    )
    (export / "subscribers.csv").write_text("email\nprivate@example.com\n", encoding="utf-8")
    syncer = SubstackArchiveSync(
        publication_url="https://example.substack.com",
        archive_root=tmp_path / "archive",
        db_path=tmp_path / "knowledge" / "white_rabbit.db",
        request_delay_ms=0,
    )
    try:
        report = syncer.import_author_export(export)
        assert len(report["imported"]) == 1
        metadata = json.loads(
            (tmp_path / "archive/articles/2024/owner-full/metadata.json").read_text(encoding="utf-8")
        )
        assert metadata["access_level"] == "FULL_AUTHOR_EXPORT"
        assert metadata["source_origin"] == "author_export"
        assert "private@example.com" not in json.dumps(report)
    finally:
        syncer.close()


def test_owner_export_zip_imports_only_published_posts_and_preserves_structure(tmp_path: Path):
    export_zip = tmp_path / "owner-export.zip"
    full_html = """
    <h2>The documented record</h2>
    <p>This is a complete paid article from the owner export, containing enough authored
    prose to establish that the protected body is full rather than a public preview.</p>
    <figure><img src="https://cdn.example/evidence.png" alt="Evidence chart"><figcaption>Evidence caption</figcaption></figure>
    <p>Review the <a href="https://archives.gov/example">primary archive record</a> before drawing the conclusion.</p>
    """
    with zipfile.ZipFile(export_zip, "w") as archive:
        archive.writestr(
            "posts.csv",
            "post_id,post_date,is_published,email_sent_at,inbox_sent_at,type,audience,title,subtitle,podcast_url\n"
            '42.paid-investigation,2025-02-01T00:00:00Z,true,,,newsletter,only_paid,"Paid Investigation","Owner subtitle",\n'
            '43.unpublished-draft,,false,,,newsletter,only_paid,"",,\n',
        )
        archive.writestr("posts/42.paid-investigation.html", full_html)
        archive.writestr("posts/43.unpublished-draft.html", "<p>Private unfinished draft text.</p>")
        archive.writestr("email_list.publication.csv", "email\nprivate@example.com\n")
        archive.writestr("posts/42.paid-investigation.opens.csv", b"\xff\xfeprivate analytics")

    syncer = SubstackArchiveSync(
        publication_url="https://example.substack.com",
        archive_root=tmp_path / "archive",
        db_path=tmp_path / "knowledge" / "white_rabbit.db",
        request_delay_ms=0,
    )
    try:
        report = syncer.import_author_export(export_zip)
        assert report["published_rows"] == 1
        assert report["unpublished_rows_excluded"] == 1
        assert report["private_entries_ignored"] == 1
        assert report["analytics_entries_ignored"] == 1
        assert report["summary"]["full_author_export"] == 1
        assert report["summary"]["new_published"] == 1

        article_dir = tmp_path / "archive/articles/2025/paid-investigation"
        markdown = (article_dir / "article.md").read_text(encoding="utf-8")
        metadata = json.loads((article_dir / "metadata.json").read_text(encoding="utf-8"))
        links = json.loads((article_dir / "links.json").read_text(encoding="utf-8"))
        assert metadata["canonical_url"] == "https://example.substack.com/p/paid-investigation"
        assert metadata["export_post_id"] == "42.paid-investigation"
        assert metadata["audience"] == "only_paid"
        assert metadata["subtitle"] == "Owner subtitle"
        assert metadata["publication_status"] == "published"
        assert metadata["access_level"] == "FULL_AUTHOR_EXPORT"
        assert "## The documented record" in markdown
        assert "Evidence caption" in markdown
        assert "evidence.png" in markdown
        assert links == [{
            "anchor": "primary archive record",
            "url": "https://archives.gov/example",
            "type": "external",
        }]
        assert "Private unfinished draft text" not in markdown
        assert "private@example.com" not in json.dumps(report)
    finally:
        syncer.close()


def test_owner_export_title_shell_remains_title_only(tmp_path: Path):
    export_zip = tmp_path / "owner-export.zip"
    with zipfile.ZipFile(export_zip, "w") as archive:
        archive.writestr(
            "posts.csv",
            "post_id,post_date,is_published,type,audience,title,subtitle\n"
            "9.coming-soon,2024-09-01T00:00:00Z,true,newsletter,everyone,Coming soon,\n",
        )
        archive.writestr("posts/9.coming-soon.html", "<p>This is The White Rabbit Report.</p>")
    syncer = SubstackArchiveSync(
        publication_url="https://example.substack.com",
        archive_root=tmp_path / "archive",
        db_path=tmp_path / "knowledge" / "white_rabbit.db",
        request_delay_ms=0,
    )
    try:
        report = syncer.import_author_export(export_zip)
        metadata = json.loads(
            (tmp_path / "archive/articles/2024/coming-soon/metadata.json").read_text(encoding="utf-8")
        )
        assert report["summary"]["title_only_after_export"] == 1
        assert metadata["access_level"] == "TITLE_ONLY"
        assert metadata["source_origin"] == "author_export"
        assert metadata["content_status"] == "preview_only"
    finally:
        syncer.close()


def test_public_refresh_never_overwrites_full_author_export(tmp_path: Path):
    syncer = SubstackArchiveSync(
        publication_url="https://example.substack.com",
        archive_root=tmp_path / "archive",
        db_path=tmp_path / "knowledge" / "white_rabbit.db",
        request_delay_ms=0,
    )
    try:
        full = ArticleSnapshot(
            title="Protected post",
            slug="protected-post",
            canonical_url="https://example.substack.com/p/protected-post",
            published_date="2025-01-01T00:00:00Z",
            author="White Rabbit",
            markdown="# Protected post\n\n" + "Complete author-export evidence and analysis. " * 20,
            links=[],
            content_status="full",
            access_level="FULL_AUTHOR_EXPORT",
            source_origin="author_export",
            export_post_id="7.protected-post",
        )
        syncer.store_snapshot(full)
        article_path = tmp_path / "archive/articles/2025/protected-post/article.md"
        original = article_path.read_text(encoding="utf-8")
        preview = ArticleSnapshot(
            title="Protected post",
            slug="protected-post",
            canonical_url="https://example.substack.com/p/protected-post",
            published_date="2025-01-01T00:00:00Z",
            author="White Rabbit",
            markdown="# Protected post\n\nA short public preview. Subscribe to continue reading.",
            links=[],
            content_status="preview_only",
            access_level="PARTIAL_PREVIEW",
            source_origin="public_web",
            http_status=200,
        )
        wr_id, created, changed = syncer.store_snapshot(preview)
        assert wr_id == "WR-000001"
        assert not created and not changed
        assert article_path.read_text(encoding="utf-8") == original
        metadata = json.loads(article_path.with_name("metadata.json").read_text(encoding="utf-8"))
        assert metadata["access_level"] == "FULL_AUTHOR_EXPORT"
        assert metadata["latest_public_observation"]["access_level"] == "PARTIAL_PREVIEW"
        assert metadata["latest_public_observation"]["body_differs_from_author_export"] is True
    finally:
        syncer.close()


def test_source_precedence_prevents_preview_from_downgrading_public_full(tmp_path: Path):
    syncer = SubstackArchiveSync(
        publication_url="https://example.substack.com",
        archive_root=tmp_path / "archive",
        db_path=tmp_path / "knowledge" / "white_rabbit.db",
        request_delay_ms=0,
    )
    try:
        full = ArticleSnapshot(
            title="Public full post",
            slug="public-full",
            canonical_url="https://example.substack.com/p/public-full",
            published_date="2025-01-01T00:00:00Z",
            author="White Rabbit",
            markdown="# Public full post\n\n" + "Complete public article evidence. " * 20,
            links=[],
            content_status="full",
            access_level="FULL_PUBLIC",
            source_origin="public_web",
        )
        syncer.store_snapshot(full)
        article_path = tmp_path / "archive/articles/2025/public-full/article.md"
        original = article_path.read_text(encoding="utf-8")
        preview = ArticleSnapshot(
            title="Public full post",
            slug="public-full",
            canonical_url="https://example.substack.com/p/public-full",
            published_date="2025-01-01T00:00:00Z",
            author="White Rabbit",
            markdown="# Public full post\n\nShort preview. Subscribe to continue reading.",
            links=[],
            content_status="preview_only",
            access_level="PARTIAL_PREVIEW",
            source_origin="public_web",
        )
        _, created, changed = syncer.store_snapshot(preview)
        assert not created and not changed
        assert article_path.read_text(encoding="utf-8") == original
        metadata = json.loads(article_path.with_name("metadata.json").read_text(encoding="utf-8"))
        assert metadata["access_level"] == "FULL_PUBLIC"
        assert metadata["latest_lower_priority_observation"]["access_level"] == "PARTIAL_PREVIEW"
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
