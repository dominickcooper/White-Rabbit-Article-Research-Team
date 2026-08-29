from pathlib import Path

import pytest

from white_rabbit.config import Settings
from white_rabbit.pipeline import SingleArticlePipeline
from white_rabbit.schemas import (
    AnchorChoice, AnchorMap, ArticleMetadata, ArticleOutline, AuditReport,
    EvidenceExtraction, ExtractedEvidence, OutlineSection,
    ResearchPlan, ResearchQuestion, WebResearchResult,
)


class FakeProvider:
    def __init__(self, invented_marker: bool = False):
        self.invented_marker = invented_marker

    def plan_research(self, topic, angle, style, max_questions):
        return ResearchPlan(questions=[ResearchQuestion(
            id="RQ-1", category="records", question="What does the local record establish?",
            search_query="no web result test", priority=5, reason="test"
        )])

    def web_research(self, qid, question, search_query):
        return WebResearchResult(question_id=qid, question=question, search_query=search_query, notes="No citations for offline test.", citations=[])

    def extract_evidence_from_text(self, **kwargs):
        return EvidenceExtraction(items=[ExtractedEvidence(
            claim="Project Night Window began in 2001.", excerpt="Project Night Window began in 2001.",
            reliability="primary", entities=["Project Night Window"], significance="Establishes the date."
        )])

    def build_outline(self, topic, angle, evidence_packet, style):
        return ArticleOutline(
            working_title="Night Window Test", thesis="A sourced test.", opening_hook="A dated record.",
            sections=[OutlineSection(heading="THE RECORD", purpose="Show record", evidence_ids=["EV-0001"], key_points=["date"])],
            ending_move="Return to the record."
        )

    def write_article(self, topic, angle, outline, evidence_packet, style):
        if self.invented_marker:
            return "# Night Window Test\n\n**Project Night Window** began in 2001. [[EV-0001]] Invented claim. [[EV-7777]]\n"
        return "# Night Window Test\n\n## THE RECORD\n\n**Project Night Window** began in 2001. [[EV-0001]]\n\n## FAQ\n\n### Is it documented?\n\nYes, in the supplied test source."

    def audit_article(self, article, evidence_packet):
        return AuditReport(pass_for_publish=True, findings=[])

    def revise_article(self, article, audit, evidence_packet, style):
        return article

    def choose_anchors(self, marker_contexts):
        return AnchorMap(anchors=[AnchorChoice(evidence_id="EV-0001", phrase="Project Night Window")])

    def metadata(self, article, topic):
        return ArticleMetadata(
            title="Night Window Test", meta_title="Night Window Test", meta_description="A test article used to validate the pipeline.",
            slug="night-window-test", primary_keyword="Night Window", secondary_keywords=["test"], sizzle="Test.", banner_image_prompt="1980s airbrush test poster."
        )


def _settings(root: Path) -> Settings:
    return Settings(
        root=root, workspace=root / "workspace", style_path=root / "config" / "white_rabbit_style.md",
        gemini_api_key="fake", model="fake", research_questions=1, web_sources_per_query=1,
        local_chunks=2, max_evidence_items=10, http_timeout=5, sitemap_url="",
        archive_sync_before_run=False,
    )


def test_pipeline_with_local_source_and_no_live_api(tmp_path: Path):
    root = tmp_path / "app"
    (root / "config").mkdir(parents=True)
    (root / "config" / "white_rabbit_style.md").write_text("Test style", encoding="utf-8")
    source_dir = root / "sources"
    source_dir.mkdir()
    (source_dir / "record.txt").write_text("Project Night Window began in 2001.", encoding="utf-8")

    out = SingleArticlePipeline(_settings(root), FakeProvider()).run(
        topic="Night Window", project="test", sources_folder=source_dir, skip_archive_sync=True
    )
    assert (out / "article_substack.docx").exists()
    assert (out / "article_linked.md").exists()
    csv_text = (out / "sources.csv").read_text(encoding="utf-8-sig")
    assert "source_number,phrase,link" in csv_text
    assert "http" not in csv_text


def test_pipeline_rejects_invented_evidence_markers(tmp_path: Path):
    root = tmp_path / "app"
    (root / "config").mkdir(parents=True)
    (root / "config" / "white_rabbit_style.md").write_text("Test style", encoding="utf-8")
    source_dir = root / "sources"
    source_dir.mkdir()
    (source_dir / "record.txt").write_text("Project Night Window began in 2001.", encoding="utf-8")

    with pytest.raises(RuntimeError, match="invented/unknown evidence markers"):
        SingleArticlePipeline(_settings(root), FakeProvider(invented_marker=True)).run(
            topic="Night Window", project="test", sources_folder=source_dir, skip_archive_sync=True
        )
