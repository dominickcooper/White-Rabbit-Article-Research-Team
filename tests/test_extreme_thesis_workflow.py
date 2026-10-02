from pathlib import Path
import shutil

import pytest

from white_rabbit import codex_articles as articles
from white_rabbit import codex_series as series


@pytest.fixture
def root(tmp_path: Path) -> Path:
    required = {
        *articles.AUTHORITY,
        series.SERIES_AUTHORITY,
        "templates/ARTICLE_BRIEF_TEMPLATE.md",
        "templates/SERIES_THEMES_TEMPLATE.md",
        "templates/SERIES_PART_PLAN_TEMPLATE.md",
        "white_rabbit_codex_config.json",
    }
    required.update(f"templates/{name}" for name in series.SERIES_FILES.values())
    for name in required:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(articles.ROOT / name, target)
    return tmp_path


@pytest.fixture
def prompt(root: Path) -> str:
    project = articles.new_project(root, "Extreme protocol contract")
    (project / "sources/supplied-book.txt").write_text("author-approved evidence")
    return articles.generate_prompt(root, project)


def test_author_supplied_sources_are_admissible_without_independent_verification(prompt):
    assert "admissible\nevidence without independent recovery or online verification" in prompt
    assert "not an exclusion gate" in prompt


def test_provenance_and_secondary_attribution_are_preserved(prompt):
    assert "Preserve provenance and" in prompt
    assert "must not be silently rewritten as a primary record" in prompt


def test_missing_underlying_archive_does_not_exclude_supplied_claim(prompt):
    assert "never omit a\nsupplied claim solely because" in prompt


def test_book_footnotes_generate_traceable_leads(root, prompt):
    assert "follow bibliographies" in prompt
    assert "BOOK_LEADS.md" in prompt and "BIBLIOGRAPHY_TRACE.csv" in prompt
    book = (articles.ROOT / "templates/BOOK_LEADS_TEMPLATE.md").read_text(encoding="utf-8")
    trace = (articles.ROOT / "templates/BIBLIOGRAPHY_TRACE_TEMPLATE.csv").read_text(encoding="utf-8")
    assert "Footnote / bibliography citation" in book
    assert "underlying_citation" in trace and "next_research_target" in trace


def test_connection_chain_supports_stepping_stones_and_visible_weak_edges(root):
    project = articles.new_project(root, "Connection chain")
    chain = (project / "research/CONNECTION_CHAINS.md").read_text(encoding="utf-8")
    assert "premise for the next research" in chain
    assert all(label in chain for label in ("DIRECT", "STRONG INFERENCE", "PLAUSIBLE", "BROKEN"))


def test_duplicate_evidence_is_not_double_counted(prompt):
    assert "Do not double-count derivative repetitions" in prompt
    methodology = (articles.ROOT / "research_library/methodologies/EXTREME_THESIS_PROTOCOL.md").read_text(encoding="utf-8")
    assert "must not be double-counted" in methodology


def test_zebra_runs_after_case_build_and_disconfirmation(prompt):
    order = [
        "3. Evidence build:",
        "4. Connection engine:",
        "6. Disconfirmation:",
        "7. Zebra adjudication",
        "8. Thesis reduction",
        "10. Story Decision:",
    ]
    positions = [prompt.index(item) for item in order]
    assert positions == sorted(positions)


def test_horse_can_win_and_theory_can_be_contradicted(prompt):
    assert "Horse can win" in prompt
    assert "A controversial theory may fail" in prompt
    assert "CONTRADICTED" in prompt


def test_strong_inference_is_an_allowed_article_level_result(prompt):
    assert "CORROBORATED STRONG INFERENCE" in prompt
    method = (articles.ROOT / "research_library/methodologies/EXTREME_THESIS_PROTOCOL.md").read_text(encoding="utf-8")
    assert "valid article-level conclusion" in method


def test_extreme_thesis_artifacts_are_supported_but_conditional(prompt):
    assert "only if Extreme-Thesis Protocol is active" in prompt
    for name in ("EXTREME_THESIS_LEDGER", "THESIS_REDUCTION", "ZEBRA_ANALYSIS"):
        assert (articles.ROOT / f"templates/{name}_TEMPLATE.md").is_file()


def test_factual_audit_separates_required_claim_types():
    text = (articles.ROOT / "templates/FACTUAL_AUDIT_TEMPLATE.md").read_text(encoding="utf-8")
    assert all(heading in text for heading in (
        "## Direct factual claims", "## Attributed source claims",
        "## Inferential claims and evidence convergence", "## Connection chains",
        "## Historical analogy and continuity",
    ))
    assert "smoking-gun memorandum" in text


def test_editorial_audit_detects_overclaim_and_caveat_collapse():
    text = (articles.ROOT / "templates/EDITORIAL_AUDIT_TEMPLATE.md").read_text(encoding="utf-8")
    assert "OVERCLAIM" in text and "CAVEAT COLLAPSE" in text
    assert "show the receipts" in text and "meaningful boundary once" in text


def test_series_inherits_shared_sources_recursively(root):
    folder = series.new_series(root, "Inheritance test")
    first = series.add_part(root, folder.name, "First")
    shared = folder / "shared_sources/nested/shared.txt"
    shared.parent.mkdir(parents=True)
    shared.write_text("private shared evidence")
    data = series.load(root, folder.name)[1]
    generated = series.generate_prompt(root, folder, data, data["parts"][0])
    assert "nested/shared.txt" in generated
    assert "private shared evidence" not in generated
    assert "admissible evidence" in generated


def test_series_inherits_every_earlier_part_source_and_research_file(root):
    folder = series.new_series(root, "Cumulative test")
    first = series.add_part(root, folder.name, "First")
    second = series.add_part(root, folder.name, "Second")
    (first / "sources/earlier-record.pdf").write_text("source body")
    (first / "research/CLAIMS_LEDGER.md").write_text("earlier finding")
    (first / "output/sources.csv").write_text("source_number,phrase,link\n")
    data = series.load(root, folder.name)[1]
    generated = series.generate_prompt(root, folder, data, data["parts"][1])
    assert "earlier-record.pdf" in generated
    assert "CLAIMS_LEDGER.md" in generated and "output/sources.csv" in generated
    assert "may generate current questions and modern\nsignature searches" in generated
    assert "never copy shared or earlier sources" in generated


def test_ordinary_workflow_remains_functional_without_forced_extreme_artifacts(root):
    project = articles.new_project(root, "Ordinary records request")
    assert (project / "CODEX_PROMPT.md").is_file()
    assert (project / "research/CONNECTION_CHAINS.md").is_file()
    assert not (project / "research/EXTREME_THESIS_LEDGER.md").exists()
    assert not (project / "research/THESIS_REDUCTION.md").exists()
    assert articles.status(root, project)["source_count"] == 0
