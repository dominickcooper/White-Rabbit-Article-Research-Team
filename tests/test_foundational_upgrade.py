import inspect
import json
from pathlib import Path
import shutil

from white_rabbit import codex_articles, codex_series
from white_rabbit.editorial_diagnostics import analyze_editorial_style
from white_rabbit.editorial_memory import ensure_project_artifacts
from white_rabbit.investigative_workflow import (
    network_convergences,
    quality_gate_report,
    rabbit_hole_completion,
    thesis_fidelity,
    writer_context_manifest,
)


def _source_thesis(thesis: str) -> str:
    return f"""# Source Thesis

## Principal source-derived thesis

{thesis}
"""


def _story_decision(investigation: str, outcome: str, decision: str) -> str:
    return f"""# Story Decision

Thesis fidelity outcome: {outcome}
Author thesis decision: {decision}

## Selected central investigation

{investigation}
"""


def test_new_project_artifacts_include_controlled_handoff(tmp_path):
    root = tmp_path / "repo"
    project = root / "article_projects" / "fixture"
    project.mkdir(parents=True)
    shutil.copyfile(codex_articles.ROOT / "white_rabbit_codex_config.json", root / "white_rabbit_codex_config.json")

    created = ensure_project_artifacts(root, project)

    created_names = {path.relative_to(project).as_posix() for path in created}
    assert {
        "research/SOURCE_THESIS.md",
        "research/WRITER_PACKET.md",
        "research/SEMANTIC_EDITORIAL_REVIEW.md",
        "research/QUALITY_GATES.md",
    } <= created_names


def test_prompt_contract_locks_source_thesis_before_external_research():
    prompt_source = inspect.getsource(codex_articles.generate_prompt)
    source_step = prompt_source.index("1. Source Thesis")
    canon_step = prompt_source.index("2. Canon retrieval")
    evidence_step = prompt_source.index("3. Evidence build")
    assert source_step < canon_step < evidence_step
    assert "explicit author objective → thesis" in prompt_source
    assert "AUTHOR THESIS DECISION REQUIRED" in prompt_source
    assert "canon_packet" in prompt_source and "voice_packet" in prompt_source
    assert "DO NOT DRAFT THE ARTICLE DIRECTLY FROM THE CLAIMS LEDGER" in prompt_source
    assert "to the independent auditor" in prompt_source
    assert "Evidence Integrity Editor: independently compare" in prompt_source


def test_series_prompt_inherits_thesis_lock_and_requires_part_source_thesis():
    source = inspect.getsource(codex_series.generate_prompt)
    assert "Before external research, complete the current part's research/SOURCE_THESIS.md" in source
    assert "AUTHOR THESIS DECISION REQUIRED" in source
    assert "shared sources" in source.casefold()
    assert "Published earlier parts are Level 1 canon" in source


def test_thesis_change_cannot_pass_silently_but_can_pass_after_author_approval():
    source = _source_thesis(
        "The selected witness accounts identify a covert personnel and logistics network connecting Dallas operations."
    )
    changed = "The article will instead examine administrative disclosure failures in a later commission inquiry."
    unapproved = thesis_fidelity(
        source, _story_decision(changed, "FUNDAMENTAL CHANGE PROPOSED", "REQUIRED")
    )
    approved = thesis_fidelity(
        source, _story_decision(changed, "FUNDAMENTAL CHANGE PROPOSED", "APPROVED")
    )
    assert unapproved["status"] == "NEEDS REVIEW"
    assert "AUTHOR THESIS DECISION REQUIRED" in unapproved["reason"]
    assert approved["status"] == "PASS"


def test_network_convergence_counts_dependency_groups_not_repeated_reports():
    convergences = network_convergences([
        {"path_id": "book-a", "dependency_group": "witness-a", "nodes": ["Shared Bank", "Officer"]},
        {"path_id": "article-copy", "dependency_group": "witness-a", "nodes": ["Shared Bank"]},
        {"path_id": "registry-b", "dependency_group": "record-b", "nodes": ["Shared Bank", "Company"]},
    ])
    bank = next(row for row in convergences if row["node"] == "Shared Bank")
    assert bank["path_ids"] == ["article-copy", "book-a", "registry-b"]
    assert bank["dependency_groups"] == ["record-b", "witness-a"]
    assert bank["independent_streams"] == 2
    assert bank["requires_investigation"] is True
    assert bank["unified_command_established"] is False


def test_rabbit_hole_requires_actual_pursuit_and_documents_blocked_or_deferred():
    shallow = rabbit_hole_completion({
        "disposition": "EXHAUSTED", "searches": ["one keyword"],
        "records_read": ["one result"], "stopping_reason": "nothing else",
    })
    blocked = rabbit_hole_completion({
        "disposition": "BLOCKED", "blocker": "Archive box is closed under identifier X-14."
    })
    deferred = rabbit_hole_completion({
        "disposition": "DEFERRED", "stopping_reason": "Lower priority than the dated payment records."
    })
    assert not shallow["valid"]
    assert any("one failed search" in error for error in shallow["errors"])
    assert blocked["valid"] and deferred["valid"]


def test_writer_context_excludes_exploratory_material_from_primary_packet(tmp_path):
    project = tmp_path / "fixture"
    for relative in (
        "ARTICLE_BRIEF.md", "research/SOURCE_THESIS.md", "research/WRITER_PACKET.md",
        "research/STORY_SPINE.md", "research/STYLE_PROFILE.md",
        "research/ZEBRA_ANALYSIS.md", "research/THESIS_REDUCTION.md",
        "output/research_dossier.md",
    ):
        path = project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(relative, encoding="utf-8")
    manifest = writer_context_manifest(project)
    assert "research/WRITER_PACKET.md" in manifest["writer_primary"]
    assert "research/ZEBRA_ANALYSIS.md" not in manifest["writer_primary"]
    assert "research/ZEBRA_ANALYSIS.md" in manifest["writer_lookup_only"]
    assert "research/ZEBRA_ANALYSIS.md" in manifest["auditor_full_research"]


def test_quality_gates_are_independent_and_software_never_approves_publication(tmp_path):
    project = tmp_path / "fixture"
    research = project / "research"
    research.mkdir(parents=True)
    (research / "SOURCE_THESIS.md").write_text(_source_thesis(
        "Witness accounts identify a covert personnel network with money logistics and Dallas access."
    ), encoding="utf-8")
    (research / "STORY_DECISION.md").write_text(_story_decision(
        "A commission's later document-handling process and public transparency reforms.",
        "REFINED", "NOT REQUIRED",
    ), encoding="utf-8")
    (research / "QUALITY_GATES.md").write_text(
        "| Gate | Status | Evidence |\n| --- | --- | --- |\n"
        "| B | PASS | Researcher says complete. |\n"
        "| C | PASS | Showrunner says aligned. |\n",
        encoding="utf-8",
    )
    report = quality_gate_report(project, technical_pass=True)
    assert report["gates"]["A"]["status"] == "PASS"
    assert report["gates"]["C"]["status"] == "NEEDS REVIEW"
    assert report["gates"]["D"]["status"] == "NOT RUN"
    assert report["gates"]["E"]["status"] == "NOT RUN"
    assert report["gates"]["F"]["status"] == "NOT RUN"
    assert report["gates"]["G"]["status"] == "AUTHOR APPROVAL REQUIRED"
    assert report["publication_status"] == "AUTHOR APPROVAL REQUIRED"


def test_semantic_diagnostic_catches_frozen_v1_failure_without_editing_it():
    article = codex_articles.ROOT / "article_projects/zrrifle/output/article.md"
    if not article.is_file():
        return
    before = article.read_bytes()
    report = analyze_editorial_style(before.decode("utf-8-sig"))
    categories = {finding["category"] for finding in report["semantic_rhetoric"]}
    assert {"DEFENSIVE SEQUENCE", "THESIS SUBSTITUTION", "PREMATURE ADJUDICATION"} <= categories
    assert article.read_bytes() == before


def test_one_compact_material_qualifier_does_not_trigger_defensive_sequence():
    article = """# A record

The dated ledger places the officer at the company on June 4.

The ledger does not establish who ordered the payment.

Two days later, the same account paid the courier named in the earlier memorandum.
"""
    categories = {finding["category"] for finding in analyze_editorial_style(article)["semantic_rhetoric"]}
    assert "DEFENSIVE SEQUENCE" not in categories
    assert "THESIS SUBSTITUTION" not in categories


def test_model_role_handoff_is_explicit_and_manual():
    workflow = (codex_articles.ROOT / "research_library/methodologies/INVESTIGATION_TO_STORY_HANDOFF.md").read_text(
        encoding="utf-8"
    )
    assert "GPT-5.6 Sol High" in workflow
    assert "GPT-6 Astra" in workflow
    assert "does not invoke or switch models" in workflow
    assert "separate Codex task/turn" in workflow
