from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field


class ResearchQuestion(BaseModel):
    id: str
    category: str
    question: str
    search_query: str
    priority: int = Field(ge=1, le=5)
    reason: str


class ResearchPlan(BaseModel):
    thesis_options: list[str] = Field(default_factory=list)
    questions: list[ResearchQuestion]
    conventional_explanations_to_test: list[str] = Field(default_factory=list)
    primary_source_targets: list[str] = Field(default_factory=list)
    likely_entities: list[str] = Field(default_factory=list)


class SourceThesis(BaseModel):
    author_objective: str
    source_inventory: list[str] = Field(default_factory=list)
    principal_thesis: str
    supporting_theories: list[str] = Field(default_factory=list)
    accepted_testimony: list[str] = Field(default_factory=list)
    canon_premises: list[str] = Field(default_factory=list)
    key_entities: list[str] = Field(default_factory=list)
    initial_connections: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    predicted_footprints: list[str] = Field(default_factory=list)
    source_conflicts: list[str] = Field(default_factory=list)
    external_research_objectives: list[str] = Field(default_factory=list)
    thesis_version: int = 1
    status: Literal["LOCKED", "AUTHOR THESIS DECISION REQUIRED", "AUTHOR APPROVED REVISION"] = "LOCKED"


class CitationRef(BaseModel):
    title: str = ""
    url: str


class WebResearchResult(BaseModel):
    question_id: str
    question: str
    search_query: str
    notes: str
    citations: list[CitationRef] = Field(default_factory=list)


SupportType = Literal[
    "documented_fact",
    "strong_inference",
    "plausible_connection",
    "speculation",
]
Reliability = Literal["primary", "high_quality_secondary", "secondary", "unknown"]


class ExtractedEvidence(BaseModel):
    # Hard bounds are intentional: these fields are emitted through Gemini structured
    # output. Without JSON-schema limits, very large sources can cause the model to
    # copy huge passages and eventually return truncated/invalid JSON.
    claim: str = Field(max_length=1200)
    excerpt: Optional[str] = Field(default=None, max_length=1200)
    published_date: Optional[str] = Field(default=None, max_length=120)
    author: Optional[str] = Field(default=None, max_length=300)
    support_type: SupportType = "documented_fact"
    reliability: Reliability = "unknown"
    entities: list[str] = Field(default_factory=list, max_length=25)
    significance: str = Field(default="", max_length=900)


class EvidenceExtraction(BaseModel):
    relevant: bool = True
    source_summary: str = Field(default="", max_length=1200)
    items: list[ExtractedEvidence] = Field(default_factory=list, max_length=12)


class OutlineSection(BaseModel):
    heading: str
    purpose: str
    evidence_ids: list[str] = Field(default_factory=list)
    key_points: list[str] = Field(default_factory=list)


class ArticleOutline(BaseModel):
    working_title: str
    thesis: str
    opening_hook: str
    sections: list[OutlineSection]
    ending_move: str


class WriterPacket(BaseModel):
    author_objective: str
    locked_thesis: str
    thesis_version: int = 1
    strongest_findings: list[str] = Field(default_factory=list)
    accepted_testimony: list[str] = Field(default_factory=list)
    canon_premises: list[str] = Field(default_factory=list)
    characters_and_relationships: list[str] = Field(default_factory=list)
    connection_chains: list[str] = Field(default_factory=list)
    investigated_rabbit_holes: list[str] = Field(default_factory=list)
    documentary_details: list[str] = Field(default_factory=list)
    chronology: list[str] = Field(default_factory=list)
    narrative_surprises: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    factual_boundaries: list[str] = Field(default_factory=list)
    source_locators: list[str] = Field(default_factory=list)
    reveal_sequence: list[str] = Field(default_factory=list)
    gold_voice_lessons: list[str] = Field(default_factory=list)


class AuditFinding(BaseModel):
    severity: Literal["blocker", "warning", "note"]
    category: Literal[
        "unsupported_claim",
        "overstatement",
        "citation_mismatch",
        "missing_counterevidence",
        "style",
        "repetition",
        "thesis_drift",
        "defensive_sequence",
        "narrative",
        "other",
    ]
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
    locator: str = ""
    excerpt: str = ""
    required_constraint: str = ""
    minimum_correction: str = ""
    recommendation: str = ""


class AuditReport(BaseModel):
    pass_for_publish: bool
    findings: list[AuditFinding] = Field(default_factory=list)


class AnchorChoice(BaseModel):
    evidence_id: str
    phrase: str


class AnchorMap(BaseModel):
    anchors: list[AnchorChoice] = Field(default_factory=list)


class ArticleMetadata(BaseModel):
    title: str
    meta_title: str
    meta_description: str
    slug: str
    primary_keyword: str
    secondary_keywords: list[str] = Field(default_factory=list)
    sizzle: str
    banner_image_prompt: str


class ArchiveRelevanceJudgment(BaseModel):
    wr_id: str
    score: int = Field(ge=1, le=5)
    reason: str
    relationship: str = ""
    research_leads: list[str] = Field(default_factory=list)
    source_urls_to_reopen: list[str] = Field(default_factory=list)


class ArchiveRelevanceBatch(BaseModel):
    judgments: list[ArchiveRelevanceJudgment] = Field(default_factory=list)
