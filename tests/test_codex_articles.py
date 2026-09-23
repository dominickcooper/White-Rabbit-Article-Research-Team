import csv
import json
from pathlib import Path
import shutil
import subprocess
import sys
from zipfile import ZipFile

import pytest

from white_rabbit import codex_articles as app
from white_rabbit.archive_db import ArchiveDB, resolve_archive_dir
from white_rabbit.archive_retrieval import rebuild_archive_search_index, retrieve_archive_memory


@pytest.fixture
def root(tmp_path):
    for name in (*app.AUTHORITY, "templates/ARTICLE_BRIEF_TEMPLATE.md", "white_rabbit_codex_config.json"):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(app.ROOT / name, target)
    return tmp_path


@pytest.fixture
def ready(root):
    project = app.new_project(root, "Synthetic export fixture")
    output = project / "output"
    for name in app.DELIVERABLES:
        (output / name).write_text("Synthetic test material.\n", encoding="utf-8")
    (output / "seo.md").write_text("\n\n".join(f"## {field}\nTest value" for field in app.SEO_FIELDS), encoding="utf-8")
    article = """# Synthetic fixture — café

## Records

[Record](https://example.org/document) and **bold** with *emphasis*.

> Synthetic quotation for rendering tests.

- First item
- Second item

1. Numbered item

| Field | Value |
| --- | --- |
| Test | Data |

[IMAGE: fixture note | ALT: fixture alt text]

[[SUBSCRIBE]]

[[SHARE]]

## FAQ
""" + "\n\n".join(f"### Question {i}?\nAnswer {i}." for i in range(1, 6)) + """

## YOU MAY BE INTERESTED IN THESE ARTICLES

[Earlier](https://rabbit.example/p/earlier)
[Callback](https://rabbit.example/p/earlier#detail)
[Other](https://rabbit.example/p/other)
"""
    (output / "article.md").write_text(article, encoding="utf-8")
    (output / "sources.csv").write_text("source_number,phrase,link\n1,Record,https://example.org/document\n", encoding="utf-8")
    cfg = app.config(root)
    cfg["internal_hosts"] = ["rabbit.example"]
    (root / "white_rabbit_codex_config.json").write_text(json.dumps(cfg), encoding="utf-8")
    return project


@pytest.mark.parametrize("topic,slug", [("Hello, World!", "hello-world"), ("Café & Records", "cafe-records"), ("CON", "article-con")])
def test_slug(topic, slug):
    assert app.slugify(topic) == slug


def test_empty_slug_rejected():
    with pytest.raises(ValueError):
        app.slugify("?!")


def test_new_refuses_overwrite(root):
    project = app.new_project(root, "A topic")
    sentinel = project / "ARTICLE_BRIEF.md"
    sentinel.write_text("User's work", encoding="utf-8")
    with pytest.raises(FileExistsError):
        app.new_project(root, "A topic")
    assert sentinel.read_text() == "User's work"
    assert list((project / "output").iterdir()) == []
    assert all((project / p).is_dir() for p in ("sources", "research", "output"))


@pytest.mark.parametrize("slug", ["../outside", "C:\\outside", "a/b", "..", "UPPER"])
def test_path_rejected(root, slug):
    with pytest.raises(ValueError):
        app.project_path(root, slug)


def test_config_escape_rejected(root):
    cfg = app.config(root)
    cfg["projects_dir"] = "../escape"
    (root / "white_rabbit_codex_config.json").write_text(json.dumps(cfg))
    with pytest.raises(ValueError):
        app.new_project(root, "topic")


def test_status_and_prompt_refresh(root, capsys):
    assert app.main(["new", "A topic"], root=root) == 0
    project = app.project_path(root, "a-topic")
    sources = project / "sources" / "nested"
    sources.mkdir()
    (sources / "private.txt").write_text("PRIVATE CONTENT MUST NOT BE EMBEDDED")
    report = app.status(root, project)
    assert report["source_count"] == 1
    assert report["article_brief"] and report["codex_prompt"]
    assert not report["validation_ready"]
    assert app.main(["status", "a-topic"], root=root) == 0
    assert app.main(["prompt", "a-topic"], root=root) == 0
    prompt = (project / "CODEX_PROMPT.md").read_text(encoding="utf-8")
    assert "nested/private.txt" in prompt
    assert "PRIVATE CONTENT" not in prompt
    assert all(path in prompt for path in app.AUTHORITY)
    assert all(name in prompt for name in app.DELIVERABLES)
    assert "Adversarial evidence audit" in prompt and "local White Rabbit archive" in prompt
    assert str(root) not in prompt


def test_validation_pass_and_counts(root, ready, capsys):
    report = app.validate(root, ready)
    assert report["errors"] == []
    assert report["result"] == "PASS"
    assert report["internal_link_occurrences"] == 3
    assert report["unique_internal_white_rabbit_articles"] == 2
    assert report["external_links"] == 1
    assert report["source_csv_rows"] == 1
    assert app.main(["validate", ready.name], root=root) == 0
    assert "RESULT: PASS" in capsys.readouterr().out


def test_empty_project_fails(root):
    project = app.new_project(root, "Empty")
    report = app.validate(root, project)
    assert report["result"] == "FAIL"
    assert any("article.md" in e for e in report["errors"])
    assert app.main(["validate", "empty"], root=root) == 1


@pytest.mark.parametrize("old,new,error", [
    ("### Question 5?", "Question 5?", "exactly 5"),
    ("## FAQ", "## FAQ\n### Extra?\nAnswer.", "exactly 5"),
    ("[[SUBSCRIBE]]", "", "subscribe_markers"),
    ("[[SHARE]]", "", "share_markers"),
    (" | ALT: fixture alt text", "", "image_markers"),
    ("https://example.org/document)", "https://example.org/document", "Malformed"),
    ("https://example.org/document", "https://example.org/document?utm_source=x", "Tracking"),
    ("## YOU MAY BE INTERESTED IN THESE ARTICLES", "## Related", "related"),
])
def test_article_failures(root, ready, old, new, error):
    path = ready / "output/article.md"
    path.write_text(path.read_text(encoding="utf-8").replace(old, new), encoding="utf-8")
    assert any(error in e for e in app.validate(root, ready)["errors"])


@pytest.mark.parametrize("row,error", [
    (["1", "record", "https://example.org/document"], "exact phrase absent"),
    (["1", "Record", "https://example.org/wrong"], "exact destination"),
    (["1", "Record", "javascript:alert(1)"], "invalid URL"),
    (["1", "Record", "https://example.org/document?utm_medium=email"], "tracking"),
    (["1", "Record", "https://example.org:bad/path"], "invalid URL"),
    (["1", "Record", "https://example.org/a b"], "invalid URL"),
    (["1", "Record"], "three nonempty"),
    (["x", "Record", "https://example.org/document"], "positive integer"),
])
def test_csv_failures(root, ready, row, error):
    with (ready / "output/sources.csv").open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([["source_number", "phrase", "link"], row])
    assert any(error in e for e in app.validate(root, ready)["errors"])


def test_duplicate_csv_and_empty_seo(root, ready):
    path = ready / "output/sources.csv"
    with path.open("a") as handle:
        handle.write("1,Record,https://example.org/document\n")
    (ready / "output/seo.md").write_text("## Meta Title\n")
    errors = app.validate(root, ready)["errors"]
    assert any("duplicate" in e for e in errors)
    assert any("SEO" in e for e in errors)


def test_empty_seo_section_not_satisfied_by_next_heading(root, ready):
    path = ready / "output/seo.md"
    path.write_text(path.read_text().replace("## Meta Title\nTest value", "## Meta Title\n"))
    assert any("Meta Title" in e for e in app.validate(root, ready)["errors"])


def test_code_examples_cannot_satisfy_article_requirements(root, ready):
    path = ready / "output/article.md"
    text = path.read_text(encoding="utf-8")
    path.write_text("~~~markdown\n" + text + "\n~~~\n", encoding="utf-8")
    assert app.validate(root, ready)["faq_questions"] == 0


def test_registry_identity_and_spoofed_hostname(root, ready):
    cfg = app.config(root)
    cfg["internal_hosts"] = []
    (root / "white_rabbit_codex_config.json").write_text(json.dumps(cfg))
    db_path = root / cfg["archive_db"]
    db = ArchiveDB(db_path)
    try:
        db.upsert_article(title="Earlier", slug="earlier", canonical_url="https://rabbit.example/p/earlier",
                          published_date=None, author=None, content_hash="test", content_status="full",
                          local_dir="absent", word_count=1)
    finally:
        db.close()
    before = db_path.read_bytes()
    path = ready / "output/article.md"
    with path.open("a", encoding="utf-8") as f:
        f.write("\n[Impostor](https://rabbit.example.attacker.test/p/earlier)\n")
    report = app.validate(root, ready)
    assert report["internal_link_occurrences"] == 2
    assert report["unique_internal_white_rabbit_articles"] == 1
    assert db_path.read_bytes() == before


def test_csv_header_and_empty_map_fail(root, ready):
    path = ready / "output/sources.csv"
    path.write_text("number,anchor,url\n")
    errors = app.validate(root, ready)["errors"]
    assert any("CSV header" in e for e in errors)
    assert any("at least one" in e for e in errors)


def test_export_preserves_linked_input(root, ready):
    original = (ready / "output/article.md").read_bytes()
    paths = app.export(root, ready)
    assert paths == [ready / "output/article_substack.docx", ready / "output/article_substack.html"]
    assert (ready / "output/article.md").read_bytes() == original
    html = paths[1].read_text(encoding="utf-8")
    assert all(tag in html for tag in ("<table>", "<blockquote>", "<strong>", "<em>", "<ul>", "<ol>"))
    assert html.count('href="https://example.org/document"') == 1
    assert "café" in html and "[[SUBSCRIBE]]" in html and "ALT:" in html
    with ZipFile(paths[0]) as doc:
        xml = doc.read("word/document.xml").decode()
        rels = doc.read("word/_rels/document.xml.rels").decode()
    assert "w:tbl" in xml and "w:hyperlink" in xml and "[[SHARE]]" in xml
    assert "https://example.org/document" in rels


def test_failed_validation_does_not_export(root, ready):
    (ready / "output/audit.md").unlink()
    with pytest.raises(ValueError, match="Export blocked"):
        app.export(root, ready)
    assert not (ready / "output/article_substack.docx").exists()


def test_entrypoint_from_other_directory_without_provider(tmp_path):
    result = subprocess.run([sys.executable, "-S", str(app.ROOT / "codex_article.py"), "--help"],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "new,status,prompt,validate,export" in result.stdout


def test_archive_path_recovery_and_cache_invalidation(tmp_path):
    db_path = tmp_path / "knowledge/white_rabbit.db"
    historical = r"C:\OtherComputer\Repo\research_library\previous_white_rabbit_articles\articles\2026\fixture"
    db = ArchiveDB(db_path)
    try:
        db.upsert_article(title="Synthetic telescope records", slug="fixture",
                          canonical_url="https://rabbit.example/p/fixture", published_date="2026-01-01",
                          author="Test", content_hash="fixture", content_status="full",
                          local_dir=historical, word_count=30)
    finally:
        db.close()
    assert rebuild_archive_search_index(db_path)["articles"] == 0
    local = tmp_path / "research_library/previous_white_rabbit_articles/articles/2026/fixture"
    local.mkdir(parents=True)
    (local / "article.md").write_text("# Synthetic telescope records\n\nTelescope observations record stars and planets. Observatory documents describe optical astronomy and telescope discoveries.")
    assert resolve_archive_dir(historical, db_path) == local
    result = rebuild_archive_search_index(db_path)
    assert result["rebuilt"] and result["articles"] == 1
    assert not rebuild_archive_search_index(db_path)["rebuilt"]
    assert retrieve_archive_memory(db_path, query="Synthetic Telescope", min_score=0.0)
    db = ArchiveDB(db_path)
    try:
        assert db.list_articles()[0].local_dir == str(local)
        assert db.conn.execute("SELECT local_dir FROM wr_articles").fetchone()[0] == historical
    finally:
        db.close()


def test_archive_recovery_rejects_traversal(tmp_path):
    historical = "C:/Old/research_library/previous_white_rabbit_articles/../../escape"
    assert resolve_archive_dir(historical, tmp_path / "knowledge/db") == Path(historical)
