import json
from pathlib import Path
import shutil

import pytest

from white_rabbit import codex_articles as articles
from white_rabbit import codex_series as series
from white_rabbit import editorial_memory as memory


@pytest.fixture
def root(tmp_path):
    for name in (*articles.AUTHORITY, "templates/ARTICLE_BRIEF_TEMPLATE.md", "white_rabbit_codex_config.json"):
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(articles.ROOT / name, target)
    return tmp_path


def test_editorial_memory_initialization_is_non_destructive(root):
    folder = memory.initialize(root)
    assert all((folder / name).is_file() for name in memory.MEMORY_FILES)
    assert (folder / "pending_learnings").is_dir()
    voice = folder / "VOICE_CANON.md"
    voice.write_text("human canon", encoding="utf-8")
    memory.initialize(root)
    assert voice.read_text(encoding="utf-8") == "human canon"


def test_gold_registry_loads_real_articles_and_skips_missing(root):
    folder = memory.initialize(root)
    real = root / "gold.md"
    real.write_text("# Gold", encoding="utf-8")
    entries = [
        {"path": "gold.md", "title": "Real", "tags": ["history"], "notes": "", "approved": True},
        {"path": "missing.md", "title": "Missing", "tags": [], "notes": "", "approved": True},
        {"path": "gold.md", "title": "Unapproved", "tags": [], "notes": "", "approved": False},
    ]
    (folder / "GOLD_ARTICLES.json").write_text(json.dumps(entries), encoding="utf-8")
    assert [item["title"] for item in memory.load_gold_articles(root)] == ["Real"]
    assert {item["title"] for item in memory.load_gold_articles(root, include_missing=True)} == {"Real", "Missing"}


def test_new_project_has_story_connection_and_audit_artifacts(root):
    project = articles.new_project(root, "Connections")
    assert all((project / relative).is_file() for relative in articles.EDITORIAL_ARTIFACTS)
    prompt = (project / "CODEX_PROMPT.md").read_text(encoding="utf-8")
    assert "DO NOT DRAFT THE ARTICLE DIRECTLY FROM THE CLAIMS LEDGER" in prompt
    assert "STORY_DECISION.md" in prompt and "Connection engine" in prompt


def test_old_project_validation_warns_but_does_not_fail_for_new_artifacts(root, monkeypatch):
    project = root / "article_projects/old"
    for name in ("sources", "research", "output"):
        (project / name).mkdir(parents=True, exist_ok=True)
    (project / "ARTICLE_BRIEF.md").write_text("old", encoding="utf-8")
    (project / "CODEX_PROMPT.md").write_text("old", encoding="utf-8")
    # Isolate the compatibility assertion from publication-format errors.
    monkeypatch.setattr(articles, "DELIVERABLES", ())
    report = articles.validate(root, project)
    assert any("workflow artifact missing" in warning for warning in report["warnings"])


def test_learning_prepares_diff_prompt_and_no_fake_postmortem(root):
    project = articles.new_project(root, "Learning")
    article = project / "output/article.md"
    article.write_text("# Draft\n\n## Opening\n\nThe record does not prove the claim.\n", encoding="utf-8")
    snapshot = memory.preserve_pre_human_snapshot(root, project)
    article.write_text("# Final\n\n## The document\n\nI found the record. What changed?\n\n## Ending\n\nThe next question is larger.\n", encoding="utf-8")
    result = memory.learn(root, project, review=True)
    folder = Path(result["revision_dir"])
    assert snapshot.is_file()
    assert (folder / "editorial_diff.md").is_file()
    diff = (folder / "editorial_diff.md").read_text(encoding="utf-8")
    assert all(heading in diff for heading in ("# EDITORIAL DIFF", "## SECTION CHANGES",
                                                "## PARAGRAPH RHYTHM CHANGES", "## ENTITY / PERSON CHANGES"))
    prompt = (folder / "LEARNING_PROMPT.md").read_text(encoding="utf-8")
    assert "DO NOT merely summarize the textual diff" in prompt
    assert "WHAT CODEX MISSED" in prompt and "candidate_learnings.json" in prompt
    postmortem = (folder / "editorial_postmortem.md").read_text(encoding="utf-8")
    assert "STATUS: AWAITING CODEX ANALYSIS" in postmortem
    assert "Required human analysis" not in postmortem
    candidate = json.loads((folder / "candidate_learnings.json").read_text(encoding="utf-8"))
    assert candidate["schema_version"] == 2 and candidate["analysis_status"] == "awaiting_codex_analysis"
    assert memory.learning_status(root, "learning")["status"] == "AWAITING_CODEX_ANALYSIS"


def test_standalone_learning_cli_and_status(root, capsys):
    project = articles.new_project(root, "CLI Learning")
    article = project / "output/article.md"
    article.write_text("# Draft\n\nOld.\n", encoding="utf-8")
    memory.preserve_pre_human_snapshot(root, project)
    article.write_text("# Final\n\nNew investigation.\n", encoding="utf-8")
    assert articles.main(["learn", project.name, "--review"], root=root) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "AWAITING_CODEX_ANALYSIS"
    assert articles.main(["learning-status", project.name], root=root) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "AWAITING_CODEX_ANALYSIS"


def _semantic_candidates(folder: Path):
    (folder / "editorial_postmortem.md").write_text(
        "# EDITORIAL POSTMORTEM\n\n## EXECUTIVE FINDING\n\nThe final turned background into an investigation.\n",
        encoding="utf-8")
    data = {
        "schema_version": 2, "key": folder.name, "analysis_status": "analyzed",
        "automatic_promotion": False,
        "candidate_learnings": [
            {"id": "personnel-pass", "category": "CONNECTION_ADDED",
             "lesson": "Follow significant personnel across institutions before fixing the story spine.",
             "evidence": "The final promoted a career bridge that the draft treated as background.",
             "scope": "investigative", "confidence": "high", "status": "pending",
             "promote_to": "EDITORIAL_LESSONS.md"},
            {"id": "specific-name", "category": "FRAMING_CHANGE",
             "lesson": "Use this article's exact document as the opening.",
             "evidence": "This opening worked for this article.", "scope": "article-specific",
             "confidence": "medium", "status": "pending", "promote_to": "EDITORIAL_LESSONS.md"},
        ]}
    path = folder / "candidate_learnings.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path, data


def test_semantic_candidate_schema_scopes_and_explicit_approval(root):
    project = articles.new_project(root, "Learning")
    article = project / "output/article.md"
    article.write_text("# Draft\n\nOld opening.\n", encoding="utf-8")
    memory.preserve_pre_human_snapshot(root, project)
    article.write_text("# Final\n\nA stronger document-led opening.\n", encoding="utf-8")
    result = memory.learn(root, project, review=True)
    folder = Path(result["revision_dir"])
    (folder / "editorial_postmortem.md").write_text(
        "# EDITORIAL POSTMORTEM\n\n## EXECUTIVE FINDING\n\nSubstantive analysis is underway.\n",
        encoding="utf-8")
    assert memory.learning_status(root, "learning")["status"] == "ANALYZED"
    candidate_path, data = _semantic_candidates(folder)
    assert memory.validate_candidates(data) == []
    assert {c["scope"] for c in data["candidate_learnings"]} == {"investigative", "article-specific"}
    assert memory.learning_status(root, "learning")["status"] == "AWAITING_HUMAN_REVIEW"
    lessons = memory.initialize(root) / "EDITORIAL_LESSONS.md"
    before = lessons.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="explicitly approved"):
        memory.promote(root, "learning")
    assert lessons.read_text(encoding="utf-8") == before

    # Article-specific approval alone is deliberately insufficient for permanent memory.
    data["candidate_learnings"][1]["status"] = "approved"
    candidate_path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="non-article-specific"):
        memory.promote(root, "learning")

    data["candidate_learnings"][0]["status"] = "approved"
    candidate_path.write_text(json.dumps(data), encoding="utf-8")
    assert memory.learning_status(root, "learning")["status"] == "READY_FOR_PROMOTION"
    assert memory.promote(root, "learning")["promoted"] == 1
    assert "Follow significant personnel" in lessons.read_text(encoding="utf-8")
    saved = json.loads(candidate_path.read_text(encoding="utf-8"))
    assert saved["candidate_learnings"][0]["status"] == "promoted"
    assert saved["candidate_learnings"][1]["status"] == "approved"  # never silently globalized


def test_invalid_candidate_schema_and_legacy_history_are_reported(root):
    legacy = memory.initialize(root) / "pending_learnings/legacy.json"
    legacy.write_text(json.dumps({"candidate_learnings": ["old freeform lesson"]}), encoding="utf-8")
    report = memory.learning_status(root, "legacy")
    assert report["status"] == "AWAITING_CODEX_ANALYSIS"
    with pytest.raises(ValueError, match="legacy string schema"):
        memory.promote(root, "legacy")


def test_seeded_or_renamed_series_pair_preserves_snapshots(root):
    draft = root / "old-draft.md"
    final = root / "human-final.md"
    draft.write_text("# Draft\n\nOld story.\n", encoding="utf-8")
    final.write_text("# Final\n\nNew story and connection.\n", encoding="utf-8")
    key = "example-series__part-05-renamed-installment"
    result = memory.seed_comparison(root, key, draft, final)
    folder = Path(result["revision_dir"])
    before = (folder / "final_published.md").read_bytes()
    final.write_text("changed source after preservation", encoding="utf-8")
    memory.seed_comparison(root, key, draft, final)
    assert (folder / "final_published.md").read_bytes() == before
    assert "SERIES CONTINUITY" not in (folder / "editorial_postmortem.md").read_text(encoding="utf-8")
    assert memory.learning_status(root, key)["status"] == "AWAITING_CODEX_ANALYSIS"


def _identity_article(title: str, subject: str, entities: str, domain: str,
                      *, thesis: str = "") -> str:
    paragraphs = []
    for index in range(18):
        paragraphs.append(
            f"{entities} appear in document {index}. {subject} shapes the investigation. "
            f"{thesis or subject} changes what the record means for the reader."
        )
    return (f"# {title}\n\n## THE DOCUMENT\n\n" + "\n\n".join(paragraphs[:9])
            + f"\n\n## THE PAYOFF\n\n" + "\n\n".join(paragraphs[9:])
            + f"\n\n[Primary source](https://{domain}/record)\n")


def test_article_identity_accepts_same_article_heavily_revised():
    draft = _identity_article(
        "Operation Lantern", "covert maritime surveillance", "Alice Morgan and Project Lantern",
        "archives.example.gov")
    final = _identity_article(
        "Operation Lantern: The Harbor Network", "harbor intelligence and maritime surveillance",
        "Alice Morgan, Project Lantern, and Harbor Office", "archives.example.gov",
        thesis="The final reorganizes the evidence around the harbor network")
    report = memory.assess_article_identity(draft, final)
    assert report["outcome"] == "same_story"
    assert report["signals"]["title"] > 0


def test_article_identity_allows_thesis_mutation_with_retained_story_anchors():
    draft = _identity_article(
        "The Meridian File", "a failed customs investigation", "Daniel Reyes and Meridian Bureau",
        "records.example.gov", thesis="The draft argues that enforcement failed")
    final = _identity_article(
        "The Meridian File", "a personnel network that survived the customs investigation",
        "Daniel Reyes and Meridian Bureau", "records.example.gov",
        thesis="The final argues that the institutional network is the larger story")
    report = memory.assess_article_identity(draft, final)
    assert report["outcome"] == "same_story"
    assert report["signals"]["title"] == 1.0


def test_learning_blocks_completely_different_article_as_accidental_final(root):
    project = articles.new_project(root, "Identity Guard")
    article = project / "output/article.md"
    article.write_text(_identity_article(
        "Operation Lantern", "covert maritime surveillance", "Alice Morgan and Project Lantern",
        "archives.example.gov"), encoding="utf-8")
    memory.preserve_pre_human_snapshot(root, project)
    article.write_text(_identity_article(
        "The School Lunch Act", "nutrition grants and cafeteria funding", "Maria Chen and Farm Board",
        "agriculture.example.gov"), encoding="utf-8")
    with pytest.raises(ValueError, match="different stories"):
        memory.learn(root, project, review=True)
    assert not (memory.initialize(root) / "revision_history" / project.name / "final_published.md").exists()


def test_intentional_story_replacement_comparison_is_preserved_with_warning(root):
    project = articles.new_project(root, "Replacement Guard")
    article = project / "output/article.md"
    article.write_text(_identity_article(
        "Operation Lantern", "covert maritime surveillance", "Alice Morgan and Project Lantern",
        "archives.example.gov"), encoding="utf-8")
    memory.preserve_pre_human_snapshot(root, project)
    article.write_text(_identity_article(
        "The School Lunch Act", "nutrition grants and cafeteria funding", "Maria Chen and Farm Board",
        "agriculture.example.gov"), encoding="utf-8")
    result = memory.prepare_learning(root, project, comparison_mode="story_replacement")
    folder = Path(result["revision_dir"])
    assert result["article_identity"]["outcome"] == "different_story"
    assert result["comparison_mode"] == "story_replacement"
    assert "Intentional story-replacement comparison" in (folder / "LEARNING_PROMPT.md").read_text(encoding="utf-8")
    metadata = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["comparison_mode"] == "story_replacement"


def test_story_replacement_does_not_seed_false_learning_from_whole_story_deletions(root):
    project = articles.new_project(root, "Deletion Guard")
    article = project / "output/article.md"
    article.write_text(_identity_article(
        "Operation Lantern", "covert maritime surveillance", "Alice Morgan and Project Lantern",
        "archives.example.gov"), encoding="utf-8")
    memory.preserve_pre_human_snapshot(root, project)
    article.write_text(_identity_article(
        "The School Lunch Act", "nutrition grants and cafeteria funding", "Maria Chen and Farm Board",
        "agriculture.example.gov"), encoding="utf-8")
    result = memory.prepare_learning(root, project, comparison_mode="story_replacement")
    folder = Path(result["revision_dir"])
    prompt = (folder / "LEARNING_PROMPT.md").read_text(encoding="utf-8")
    candidate = json.loads((folder / "candidate_learnings.json").read_text(encoding="utf-8"))
    assert "Whole-story deletions are scope evidence only" in prompt
    assert candidate["automatic_promotion"] is False
    assert candidate["candidate_learnings"] == []


def test_series_theme_initializes_without_overwrite(root):
    # Series creation may fall back to canonical templates in this isolated root.
    for destination, template in series.SERIES_FILES.items():
        target = root / "templates" / template
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(articles.ROOT / "templates" / template, target)
    authority = root / series.SERIES_AUTHORITY
    authority.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(articles.ROOT / series.SERIES_AUTHORITY, authority)
    path = series.new_series(root, "Theme Test")
    theme = path / series.SERIES_THEMES
    assert theme.is_file()
    theme.write_text("human themes", encoding="utf-8")
    assert series.ensure_series_themes(root, path, "Theme Test").read_text(encoding="utf-8") == "human themes"
