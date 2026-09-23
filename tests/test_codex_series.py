"""Synthetic workspaces only; no archive/private article content is modified."""
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from white_rabbit import codex_articles as app
from white_rabbit import codex_series as series
from test_codex_articles import root, ready  # Reuse the tested standalone fixtures.


@pytest.fixture
def series_root(root):
    for filename in (*series.SERIES_FILES.values(), "SERIES_PART_PLAN_TEMPLATE.md"):
        shutil.copyfile(app.ROOT / "templates" / filename, root / "templates" / filename)
    shutil.copyfile(app.ROOT / series.SERIES_AUTHORITY, root / series.SERIES_AUTHORITY)
    return root


@pytest.fixture
def pair(series_root):
    folder = series.new_series(series_root, "Test investigation")
    first = series.add_part(series_root, folder.name, "First record")
    second = series.add_part(series_root, folder.name, "Second record")
    return folder, first, second


def manifest(folder):
    return json.loads((folder / "SERIES_MANIFEST.json").read_text(encoding="utf-8"))


def populate(ready, project):
    for name in app.DELIVERABLES:
        shutil.copyfile(ready / "output" / name, project / "output" / name)
    for name, sections in (("research_dossier.md", series.DOSSIER_SECTIONS), ("audit.md", series.AUDIT_SECTIONS)):
        with (project / "output" / name).open("a", encoding="utf-8") as handle:
            handle.write("\n\n" + "\n\n".join(f"## {s}\nSynthetic test assessment." for s in sections))


def test_new_manifest_and_templates(series_root):
    folder = series.new_series(series_root, "Test investigation")
    data = manifest(folder)
    assert data["slug"] == "test-investigation" and data["title"] == "Test investigation"
    assert data["status"] == "planned" and data["planned_parts"] is None and data["parts"] == []
    assert not series.manifest_errors(data, folder.name)
    assert all((folder / name).is_file() for name in series.SERIES_FILES)
    assert all((folder / name).is_dir() for name in ("shared_sources", "shared_research", "articles"))
    assert list((folder / "articles").iterdir()) == []


def test_non_overwrite(series_root):
    folder = series.new_series(series_root, "Test")
    path = folder / "SERIES_BRIEF.md"
    path.write_text("User scope")
    before = (folder / "SERIES_MANIFEST.json").read_bytes()
    with pytest.raises(FileExistsError):
        series.new_series(series_root, "Test")
    assert path.read_text() == "User scope"
    assert (folder / "SERIES_MANIFEST.json").read_bytes() == before


def test_incremental_numbering_and_plan_preservation(series_root, pair):
    folder, first, second = pair
    plan = folder / "SERIES_PLAN.md"
    with plan.open("a") as handle:
        handle.write("\nUSER RESEARCH PLAN\n")
    third = series.add_part(series_root, folder.name, "First record")
    data = manifest(folder)
    assert [p["number"] for p in data["parts"]] == [1, 2, 3]
    assert first.name == "part-01-first-record" and third.name == "part-03-first-record"
    assert [p["previous"] for p in data["parts"]] == [None, first.name, second.name]
    assert [p["next"] for p in data["parts"]] == [second.name, third.name, None]
    assert data["status"] == "active"
    assert "USER RESEARCH PLAN" in plan.read_text()
    assert "PART 3" in plan.read_text()
    assert all((first / x).is_dir() for x in ("sources", "research", "output"))
    assert (first / "ARTICLE_BRIEF.md").is_file() and (first / "CODEX_PROMPT.md").is_file()


def test_collision_does_not_mutate_metadata(series_root, pair):
    folder, _, _ = pair
    blocked = folder / "articles/part-03-third"
    blocked.mkdir()
    (blocked / "note.txt").write_text("User file")
    before = (folder / "SERIES_MANIFEST.json").read_bytes()
    plan = (folder / "SERIES_PLAN.md").read_bytes()
    with pytest.raises(FileExistsError):
        series.add_part(series_root, folder.name, "Third")
    assert (folder / "SERIES_MANIFEST.json").read_bytes() == before
    assert (folder / "SERIES_PLAN.md").read_bytes() == plan
    assert (blocked / "note.txt").read_text() == "User file"


def test_known_count_can_grow(series_root):
    folder = series.new_series(series_root, "Test", 1)
    series.add_part(series_root, folder.name, "One")
    series.add_part(series_root, folder.name, "Two")
    assert manifest(folder)["planned_parts"] == 2


@pytest.mark.parametrize("count", [0, -1])
def test_invalid_planned_count(series_root, count):
    with pytest.raises(ValueError):
        series.new_series(series_root, "Test", count)


def test_prompt_authority_discovery_and_correct_commands(series_root, pair):
    folder, first, second = pair
    shared = folder / "shared_sources/nested"
    shared.mkdir()
    (shared / "source.txt").write_text("PRIVATE TEXT MUST NOT BE EMBEDDED")
    (second / "sources/specific.txt").write_text("PRIVATE PART TEXT")
    (folder / "shared_research/notes.md").write_text("Additional working notes")
    with (folder / "SERIES_CONTINUITY.md").open("a") as handle:
        handle.write("\n## PART 1\nPreviously established synthetic result.\n")
    data = manifest(folder)
    prompt = series.generate_prompt(series_root, folder, data, data["parts"][1])
    assert all(p in prompt for p in (*app.AUTHORITY, series.SERIES_AUTHORITY, *series.SERIES_FILES))
    assert "nested/source.txt" in prompt and "specific.txt" in prompt and "notes.md" in prompt
    assert "PRIVATE TEXT" not in prompt and "PRIVATE PART TEXT" not in prompt
    assert "Previously established synthetic result" in prompt
    assert first.name in prompt and '"part_number": 2' in prompt
    assert f"series validate {folder.name} {second.name}" in prompt
    assert f"series export {folder.name} {second.name}" in prompt
    assert f"python codex_article.py validate {second.name}" not in prompt
    assert "NON-FINAL:" in prompt and "FINALE: Do NOT" not in prompt
    assert all(name in prompt for name in series.DOSSIER_SECTIONS + series.AUDIT_SECTIONS)
    assert "REVEALS SAFE TO TEASE" in prompt and "REVEALS TO WITHHOLD" in prompt


def test_status_inventory(series_root, pair, capsys):
    folder, first, _ = pair
    (folder / "shared_sources/a.txt").write_text("Test")
    assert app.main(["series", "status", folder.name], root=series_root) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["part_count"] == 2 and report["shared_source_count"] == 1
    assert all(report["required_files"].values())
    assert "master_dossier.md" in report["shared_research_files"]
    assert report["parts"][0]["slug"] == first.name
    assert not report["parts"][0]["deliverables"]["validation_ready"]


def test_finale_clear_and_extend(series_root, pair):
    folder, first, second = pair
    series.update_part(series_root, folder.name, second.name, finale=True)
    prompt = (second / "CODEX_PROMPT.md").read_text(encoding="utf-8")
    assert "FINALE: Do NOT tease another installment" in prompt
    assert "NON-FINAL:" not in prompt
    assert "HISTORICAL ANALOGY" in prompt
    with pytest.raises(ValueError, match="Clear"):
        series.add_part(series_root, folder.name, "Third")
    with pytest.raises(ValueError, match="last part"):
        series.update_part(series_root, folder.name, first.name, finale=True)
    series.update_part(series_root, folder.name, second.name, finale=False)
    third = series.add_part(series_root, folder.name, "Third", finale=True)
    data = manifest(folder)
    assert [p["finale"] for p in data["parts"]] == [False, False, True]
    assert data["parts"][1]["next"] == third.name and data["planned_parts"] == 3


def test_url_refresh_and_prior_completed_paths(series_root, pair):
    folder, first, second = pair
    (first / "output/article.md").write_text("Synthetic finalized text")
    url = "https://publication.example/p/first"
    series.update_part(series_root, folder.name, first.name, url=url)
    data = manifest(folder)
    assert data["parts"][0]["published_url"] == url and data["parts"][0]["status"] == "published"
    prompt = (second / "CODEX_PROMPT.md").read_text(encoding="utf-8")
    assert url in prompt
    assert f"{first.name}/output/article.md" in prompt
    assert f"{first.name}/output/audit.md" in prompt
    assert f"{first.name}/output/research_dossier.md" in prompt


@pytest.mark.parametrize("url", ["file:///secret", "javascript:alert(1)", "https://x.test/a?utm_source=x", "https://x.test:bad/a", "https://x.test/a(b)"])
def test_bad_url_rejected_without_change(series_root, pair, url):
    folder, first, _ = pair
    before = (folder / "SERIES_MANIFEST.json").read_bytes()
    with pytest.raises(ValueError):
        series.update_part(series_root, folder.name, first.name, url=url)
    assert (folder / "SERIES_MANIFEST.json").read_bytes() == before


def test_duplicate_publication_url_rejected(series_root, pair):
    folder, first, second = pair
    series.update_part(series_root, folder.name, first.name, url="https://x.test/p/one")
    with pytest.raises(ValueError, match="already assigned"):
        series.update_part(series_root, folder.name, second.name, url="https://x.test/p/one#section")


@pytest.mark.parametrize("field,value", [("number", 7), ("previous", "bad"), ("next", "bad"), ("finale", "yes"), ("status", "unknown"), ("slug", "../../escape"), ("updated_at", "yesterday")])
def test_corrupt_manifest_rejected(series_root, pair, field, value):
    folder, _, second = pair
    data = manifest(folder)
    data["parts"][1][field] = value
    (folder / "SERIES_MANIFEST.json").write_text(json.dumps(data))
    assert app.main(["series", "validate", folder.name, second.name], root=series_root) == 1


@pytest.mark.parametrize("command", [["status", "missing"], ["add", "missing", "Test"], ["status", "../outside"]])
def test_invalid_series(series_root, command):
    assert app.main(["series", *command], root=series_root) == 1


@pytest.mark.parametrize("command", ["prompt", "validate", "export", "set-url"])
def test_invalid_part(series_root, pair, command):
    folder, _, _ = pair
    args = ["series", command, folder.name, "../missing"]
    if command == "set-url":
        args.append("https://x.test/p/test")
    assert app.main(args, root=series_root) == 1


def test_series_validation_and_export_reuses_publisher(series_root, pair, ready):
    folder, first, _ = pair
    populate(ready, first)
    before = (first / "output/article.md").read_bytes()
    assert app.main(["series", "validate", folder.name, first.name], root=series_root) == 0
    assert app.main(["series", "export", folder.name, first.name], root=series_root) == 0
    assert (first / "output/article_substack.docx").is_file()
    assert (first / "output/article_substack.html").is_file()
    assert (first / "output/article.md").read_bytes() == before
    assert not (series_root / "article_projects" / first.name).exists()


def test_completion_status_is_explicit_and_validated(series_root, pair, ready):
    folder, first, second = pair
    with pytest.raises(ValueError, match="Completion blocked"):
        series.update_part(series_root, folder.name, first.name, status="complete")
    for project in (first, second):
        populate(ready, project)
    series.update_part(series_root, folder.name, second.name, finale=True)
    series.update_part(series_root, folder.name, first.name, status="complete")
    series.update_part(series_root, folder.name, second.name, status="complete")
    assert manifest(folder)["status"] == "complete"


def test_series_links_are_not_double_counted(series_root, pair, ready):
    folder, first, second = pair
    populate(ready, first)
    populate(ready, second)
    series.update_part(series_root, folder.name, first.name, url="https://rabbit.example/p/earlier")
    data = manifest(folder)
    report = series.validate(series_root, folder, data, data["parts"][1])
    assert report["result"] == "PASS"
    assert report["series_internal_links"] == 2
    assert report["unique_series_articles"] == 1
    assert report["white_rabbit_archive_links"] == 1
    assert report["internal_link_occurrences"] == 3


def test_missing_memory_blocks_export(series_root, pair, ready):
    folder, first, _ = pair
    populate(ready, first)
    (folder / "SERIES_TIMELINE.md").unlink()
    assert app.main(["series", "export", folder.name, first.name], root=series_root) == 1
    assert not (first / "output/article_substack.docx").exists()


def test_missing_series_audit_blocks_export(series_root, pair, ready):
    folder, first, _ = pair
    populate(ready, first)
    (first / "output/audit.md").write_text("Only standalone audit")
    assert app.main(["series", "export", folder.name, first.name], root=series_root) == 1


@pytest.mark.parametrize("words,expected", [(50, "PASS"), (310, "FAIL")])
def test_duplicate_paragraph_warning_and_failure(series_root, pair, ready, words, expected):
    folder, first, second = pair
    for project in (first, second):
        populate(ready, project)
        path = project / "output/article.md"
        paragraph = " ".join(f"synthetic{i}" for i in range(words))
        path.write_text(path.read_text(encoding="utf-8").replace("## Records", paragraph + "\n\n## Records"), encoding="utf-8")
    series.update_part(series_root, folder.name, first.name, status="complete")
    data = manifest(folder)
    report = series.validate(series_root, folder, data, data["parts"][1])
    assert report["result"] == expected
    assert report["duplication_matches"][0]["words"] == words
    assert any("Duplicated paragraphs" in e for e in report["warnings"] + report["errors"])
    if expected == "FAIL":
        assert app.main(["series", "export", folder.name, second.name], root=series_root) == 1
        assert not (second / "output/article_substack.docx").exists()


def test_paragraph_normalization_ignores_boilerplate():
    paragraph = " ".join(["Synthetic"] * 45)
    assert series.paragraphs(paragraph) == series.paragraphs("**" + paragraph.upper().replace(" ", "  ") + "**")
    assert series.paragraphs("## FAQ\n\n" + paragraph) == {}


def test_lock_prevents_overlapping_updates(series_root, pair):
    folder, _, _ = pair
    with series.mutation(folder):
        with pytest.raises(ValueError, match="locked"):
            series.add_part(series_root, folder.name, "Third")
    assert not (folder / ".series.lock").exists()
    assert len(manifest(folder)["parts"]) == 2


def test_cli_new_add_finale_and_prompt(series_root):
    assert app.main(["series", "new", "Example", "--parts", "2"], root=series_root) == 0
    assert app.main(["series", "add", "example", "One"], root=series_root) == 0
    assert app.main(["series", "add", "example", "Two", "--finale"], root=series_root) == 0
    assert app.main(["series", "prompt", "example", "part-02-two"], root=series_root) == 0
    assert app.main(["series", "set-finale", "example", "part-02-two", "--clear"], root=series_root) == 0
    assert app.main(["series", "set-status", "example", "part-01-one", "drafting"], root=series_root) == 0
    assert app.main(["series", "set-url", "example", "part-01-one", "https://x.test/p/one"], root=series_root) == 0


def test_series_help_needs_no_providers(tmp_path):
    result = subprocess.run([sys.executable, "-S", str(app.ROOT / "codex_article.py"), "series", "--help"],
                            cwd=tmp_path, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    assert "set-finale" in result.stdout and "set-url" in result.stdout


@pytest.mark.parametrize("relative", ["../outside", "article_projects", "article_projects/nested"])
def test_unsafe_series_directory_rejected(series_root, relative):
    cfg = app.config(series_root)
    cfg["series_dir"] = relative
    (series_root / "white_rabbit_codex_config.json").write_text(json.dumps(cfg))
    with pytest.raises(ValueError):
        series.new_series(series_root, "Test")


def test_old_configuration_defaults_to_series_projects(series_root):
    cfg = app.config(series_root)
    cfg.pop("series_dir")
    (series_root / "white_rabbit_codex_config.json").write_text(json.dumps(cfg))
    assert series.new_series(series_root, "Test").parent == series_root / "series_projects"


def test_missing_prior_completed_article_fails(series_root, pair, ready):
    folder, first, second = pair
    populate(ready, second)
    series.update_part(series_root, folder.name, first.name, url="https://x.test/p/first")
    data = manifest(folder)
    report = series.validate(series_root, folder, data, data["parts"][1])
    assert any("Completed part missing article.md" in e for e in report["errors"])


def test_repeated_copies_of_same_paragraph_count_toward_large_block():
    paragraph = " ".join(f"synthetic{i}" for i in range(50))
    assert sum(series.paragraphs("\n\n".join([paragraph] * 6)).values()) == 300


def test_metadata_updates_preserve_part_prose_and_brief(series_root, pair):
    folder, first, second = pair
    for project in (first, second):
        (project / "ARTICLE_BRIEF.md").write_text("User-edited brief")
        (project / "output/article.md").write_text("User-owned synthetic prose")
    series.update_part(series_root, folder.name, first.name, url="https://x.test/p/one")
    series.update_part(series_root, folder.name, second.name, finale=True)
    for project in (first, second):
        assert (project / "ARTICLE_BRIEF.md").read_text() == "User-edited brief"
        assert (project / "output/article.md").read_text() == "User-owned synthetic prose"


def test_alternate_dossier_format_warns_for_editorial_review(series_root, pair, ready):
    folder, first, _ = pair
    populate(ready, first)
    path = first / "output/research_dossier.md"
    path.write_text(path.read_text().replace("## WHAT THIS PART ADDS", "### New contribution"))
    data = manifest(folder)
    report = series.validate(series_root, folder, data, data["parts"][0])
    assert report["result"] == "PASS"
    assert any("WHAT THIS PART ADDS" in w for w in report["warnings"])
