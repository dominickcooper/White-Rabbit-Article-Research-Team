import csv
import json
from argparse import Namespace

import codex_article
from white_rabbit import cli


def configure(monkeypatch, tmp_path, **overrides):
    config = {
        **codex_article.DEFAULT_CONFIG,
        "default_word_min": 10,
        "image_marker_min": 1,
        "internal_link_min": 1,
        **overrides,
    }
    config_path = tmp_path / "white_rabbit_codex_config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setattr(codex_article, "ROOT", tmp_path)
    monkeypatch.setattr(codex_article, "CONFIG_PATH", config_path)
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "ARTICLE_BRIEF_TEMPLATE.md").write_text(
        "# {{TOPIC}}\n\nSlug: {{PROJECT_SLUG}}\n", encoding="utf-8"
    )
    return config


def write_valid_project(tmp_path, slug="sample"):
    out = tmp_path / "article_projects" / slug / "output"
    out.mkdir(parents=True)
    article = """# A Test Investigation

A useful description of this controlled validation fixture.

## THE DOCUMENT

This [documented fact](https://example.gov/record) gives the fixture enough words to pass validation cleanly.

[IMAGE: A primary document on a desk | ALT: Primary source document]

[[SUBSCRIBE]]

[[SHARE]]

## FAQ

### What happened?
Answer one.

### Who documented it?
Answer two.

### Is the record public?
Answer three.

### What remains uncertain?
Answer four.

### Why does it matter?
Answer five.

## YOU MAY BE INTERESTED IN THESE ARTICLES

- [Prior reporting](https://thewhiterabbitreport.substack.com/p/prior-reporting)
- [Prior reporting again](https://thewhiterabbitreport.substack.com/p/prior-reporting/)
"""
    (out / "article.md").write_text(article, encoding="utf-8")
    for name in ("research_dossier.md", "outline.md", "seo.md", "audit.md"):
        (out / name).write_text("complete", encoding="utf-8")
    with (out / "sources.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source_number", "phrase", "link"])
        writer.writerow(["1", "documented fact", "https://example.gov/record"])
    return out


def test_slug_generation():
    assert codex_article.slugify("  The CIA & Main Street!  ") == "the-cia-main-street"


def test_project_scaffolding_prompt_and_existing_file_preservation(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    args = Namespace(topic="Test Topic", slug=None, force=False)
    assert codex_article.cmd_new(args) == 0
    project = tmp_path / "article_projects" / "test-topic"
    assert {p.name for p in project.iterdir()} == {
        "ARTICLE_BRIEF.md", "CODEX_PROMPT.md", "sources", "research", "output"
    }
    prompt = (project / "CODEX_PROMPT.md").read_text(encoding="utf-8")
    assert "AGENTS.md" in prompt
    assert "docs/CODEX_WORKFLOW.md" not in prompt  # authority is reached through AGENTS.md
    (project / "ARTICLE_BRIEF.md").write_text("author edits", encoding="utf-8")
    assert codex_article.cmd_new(args) == 0
    assert (project / "ARTICLE_BRIEF.md").read_text(encoding="utf-8") == "author edits"


def test_validator_accepts_complete_contract(monkeypatch, tmp_path):
    cfg = configure(monkeypatch, tmp_path)
    write_valid_project(tmp_path)
    errors, warnings, metrics = codex_article.validation_report("sample", cfg)
    assert errors == []
    assert metrics["faq_questions"] == 5
    assert metrics["source_csv_rows"] == 1
    assert metrics["internal_link_occurrences"] == 2
    assert metrics["unique_internal_white_rabbit_articles"] == 1


def test_validator_rejects_nonexact_phrase_and_tracking(monkeypatch, tmp_path):
    cfg = configure(monkeypatch, tmp_path)
    out = write_valid_project(tmp_path)
    (out / "sources.csv").write_text(
        "source_number,phrase,link\n1,Documented Fact,https://example.gov/record?utm_source=test\n",
        encoding="utf-8",
    )
    errors, _, _ = codex_article.validation_report("sample", cfg)
    assert any("do not appear exactly" in error for error in errors)
    assert any("tracking parameters" in error for error in errors)


def test_absolute_archive_path_discovery(monkeypatch, tmp_path):
    archive = tmp_path / "external-archive"
    (archive / "articles" / "one").mkdir(parents=True)
    (archive / "articles" / "one" / "article.md").write_text("one", encoding="utf-8")
    cfg = configure(monkeypatch, tmp_path, archive_dir=str(archive))
    assert codex_article.archive_dir(cfg) == archive
    assert codex_article.archive_article_count(cfg) == 1


def test_module_cli_exposes_codex_article_commands(monkeypatch, tmp_path):
    configure(monkeypatch, tmp_path)
    assert cli.main(["article", "new", "CLI Topic", "--slug", "cli-topic"]) == 0
    assert (tmp_path / "article_projects" / "cli-topic" / "CODEX_PROMPT.md").exists()
