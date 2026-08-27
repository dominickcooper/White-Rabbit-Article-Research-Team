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
    claim: str
    excerpt: Optional[str] = None
    published_date: Optional[str] = None
    author: Optional[str] = None
    support_type: SupportType = "documented_fact"
    reliability: Reliability = "unknown"
    entities: list[str] = Field(default_factory=list)
    significance: str = ""


class EvidenceExtraction(BaseModel):
    relevant: bool = True
    source_summary: str = ""
    items: list[ExtractedEvidence] = Field(default_factory=list)


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


class AuditFinding(BaseModel):
    severity: Literal["blocker", "warning", "note"]
    category: Literal[
        "unsupported_claim",
        "overstatement",
        "citation_mismatch",
        "missing_counterevidence",
        "style",
        "repetition",
        "other",
    ]
    text: str
    evidence_ids: list[str] = Field(default_factory=list)
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
