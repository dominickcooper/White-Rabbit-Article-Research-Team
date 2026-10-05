from pathlib import Path
import shutil

import pytest

from white_rabbit import codex_articles as articles
from white_rabbit import codex_series as series
from white_rabbit.editorial_diagnostics import analyze_editorial_style


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
def contract() -> str:
    return (articles.ROOT / "research_library/methodologies/SOURCE_AUTHORITY_AND_CANON.md").read_text(
        encoding="utf-8"
    )


@pytest.fixture
def prompt(root: Path) -> str:
    project = articles.new_project(root, "Source authority contract")
    (project / "sources/witness.txt").write_text("A named witness described an event.", encoding="utf-8")
    return articles.generate_prompt(root, project)


def test_published_white_rabbit_articles_are_project_canon(contract, prompt):
    assert "Level 1 — Published White Rabbit canon" in contract
    assert "Level 1\nproject canon" in prompt
    assert "voice canon" in prompt


def test_canon_is_not_automatically_reverified(contract, prompt):
    assert "without\nindependent re-verification" in contract
    assert "without automatic re-verification or re-teaching" in prompt
    assert "author requests it" in prompt and "unresolved/speculative" in prompt


def test_author_supplied_material_is_accepted_factual_material(contract, prompt):
    assert "Level 2 — Author-supplied source corpus" in contract
    assert "accepted factual source material" in contract
    assert "admissible\nevidence without independent recovery or online verification" in prompt


def test_accepted_testimony_becomes_a_downstream_premise_with_provenance(contract, prompt):
    assert "Accepted testimony becomes a premise" in contract
    assert "Assume good-faith truth" in contract
    assert "ACCEPTED TESTIMONY as its internal source type" in prompt
    assert "must not be silently rewritten as a primary record" in prompt


def test_corroboration_opens_new_connection_chains(contract, prompt):
    assert "Corroborating evidence may strengthen the testimony" in contract
    assert "identify the new branch\n   it opens" in prompt
    queue = (articles.ROOT / "templates/RABBIT_HOLE_QUEUE_TEMPLATE.md").read_text(encoding="utf-8")
    assert "TESTIMONY → NAMED PERSON / PROGRAM /" in queue


def test_missing_smoking_gun_does_not_reset_accepted_testimony(contract, prompt):
    assert "missing signed order, confession, declassification, or second\nwitness does not reset" in contract
    assert "Do not require one smoking-gun" in prompt


def test_genuine_contradiction_triggers_author_review_without_silent_weakening(contract, prompt):
    assert "EXISTING CANON" in contract
    assert "NEW CONTRADICTORY EVIDENCE" in contract
    assert "AUTHOR REVIEW NEEDED" in prompt
    assert "Do not silently rewrite, erase, or automatically downgrade" in contract


def test_new_external_material_keeps_ordinary_verification(contract, prompt):
    assert "Level 3 — Newly discovered external material" in contract
    assert "ordinary\nevidence and provenance workflow" in contract
    assert "Apply ordinary verification to Level 3" in prompt


def test_connection_chains_do_not_reset_at_each_edge(contract):
    assert "does not return to zero at the next\nnode" in contract
    chain = (articles.ROOT / "templates/CONNECTION_CHAINS_TEMPLATE.md").read_text(encoding="utf-8")
    assert "Published canon, accepted testimony" in chain
    assert "New branch opened" in chain


def test_ai_tic_audit_flags_repeated_this_does_not_prove_with_locations():
    report = analyze_editorial_style(
        "# Draft\n\nThis does not prove control.\n\nThis does not prove command.\n"
    )
    item = next(item for item in report["ai_tics"] if item["phrase"] == "this does not prove")
    assert item["count"] == 2
    assert item["locations"] == ["line 3", "line 5"]
    assert item["necessary"] == "EDITORIAL REVIEW REQUIRED"
    assert any("repeated AI-tic" in warning for warning in report["warnings"])


def test_ai_tic_audit_flags_repeated_not_x_but_y():
    report = analyze_editorial_style(
        "# Draft\n\nIt is not access but control.\n\nThis is not overlap but architecture.\n"
    )
    item = next(item for item in report["ai_tics"] if item["phrase"] == "not X but Y")
    assert item["count"] == 2
    assert "affirmative finding" in item["recommended_action"]


def test_ai_tic_audit_flags_better_question_and_stronger_conclusion():
    report = analyze_editorial_style(
        "# Draft\n\nThe better question is who paid. The better question is who knew.\n\n"
        "The stronger conclusion is control. The stronger conclusion is coordination.\n"
    )
    counts = {item["phrase"]: item["count"] for item in report["ai_tics"]}
    assert counts["the better question"] == 2
    assert counts["the stronger conclusion"] == 2


def test_publication_may_state_strong_cumulative_inference_without_research_labels(contract):
    style = (articles.ROOT / "docs/WHITE_RABBIT_STYLE.md").read_text(encoding="utf-8")
    assert "State the conclusion the cumulative chain supports" in contract
    assert "Publication prose asserts before it defends" in style
    assert "not mandatory phrases\nfor publication prose" in contract


def test_story_decision_covers_canon_plain_statement_and_real_caveats():
    story = (articles.ROOT / "templates/STORY_DECISION_TEMPLATE.md").read_text(encoding="utf-8")
    for heading in (
        "## What is already published White Rabbit canon?",
        "## What accepted testimony becomes a premise?",
        "## What new facts expand rather than merely corroborate?",
        "## Strongest connection chain",
        "## What is the article willing to state plainly?",
        "## Which caveats genuinely change the story?",
        "## Which caveats are defensive habits to remove?",
    ):
        assert heading in story


def test_factual_and_editorial_audits_cover_overclaim_and_defensive_collapse():
    factual = (articles.ROOT / "templates/FACTUAL_AUDIT_TEMPLATE.md").read_text(encoding="utf-8")
    editorial = (articles.ROOT / "templates/EDITORIAL_AUDIT_TEMPLATE.md").read_text(encoding="utf-8")
    assert "OVERCLAIM" in factual and "DEFENSIVE COLLAPSE" in factual
    assert "DEFENSIVE COLLAPSE" in editorial
    assert "Phrase / construction | Count | Locations | Necessary?" in editorial
    assert "draft fails this audit" in editorial


def test_project_creation_does_not_rewrite_existing_published_articles(root):
    published = root / "research_library/previous_white_rabbit_articles/articles/2026/canon/article.md"
    published.parent.mkdir(parents=True)
    published.write_text("Published canon stays byte-for-byte intact.\n", encoding="utf-8")
    before = published.read_bytes()
    articles.new_project(root, "Do not rewrite archive")
    assert published.read_bytes() == before


def test_series_prompt_distinguishes_published_canon_from_complete_unpublished(root):
    folder = series.new_series(root, "Canon status series")
    first = series.add_part(root, folder.name, "First")
    second = series.add_part(root, folder.name, "Second")
    manifest = series.load(root, folder.name)[1]
    manifest["parts"][0]["status"] = "published"
    generated = series.generate_prompt(root, folder, manifest, manifest["parts"][1])
    assert "Published earlier parts are Level 1 canon" in generated
    assert "Complete but\nunpublished parts" in generated
    assert first.is_dir() and second.is_dir()


def test_non_investigative_and_legacy_entry_points_remain_available():
    from white_rabbit import cli, distribution

    assert callable(cli.main)
    assert callable(distribution.main)
    assert articles.slugify("Ordinary Utility") == "ordinary-utility"
