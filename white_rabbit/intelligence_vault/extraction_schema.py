from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .schema import TemporalValue
from .temporal import HistoricalDate


class ProposalEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: str = Field(min_length=1, max_length=200)
    identity_key: str | None = Field(default=None, max_length=300)
    entity_type: Literal["person", "organization", "event", "place"]
    name: str = Field(min_length=1, max_length=500)
    aliases: list[str] = Field(default_factory=list, max_length=50)
    description: str = Field(default="", max_length=5000)
    details: dict = Field(default_factory=dict)
    supporting_passage: str = Field(min_length=1, max_length=5000)
    passage_start: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def valid_detail_dates(self) -> "ProposalEntity":
        prefixes = ("birth", "death") if self.entity_type == "person" else ("start", "end") if self.entity_type == "event" else ()
        for prefix in prefixes:
            value = self.details.get(f"{prefix}_value")
            if value:
                HistoricalDate(
                    str(value), self.details.get(f"{prefix}_precision", "unknown"),
                    self.details.get(f"{prefix}_certainty", self.details.get("date_certainty", "unknown")),
                ).bounds()
        return self


class ProposalClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: str = Field(min_length=1, max_length=200)
    statement: str = Field(min_length=1, max_length=5000)
    original_passage: str = Field(min_length=1, max_length=5000)
    passage_start: int | None = Field(default=None, ge=0)
    claim_type: Literal["fact", "testimony", "allegation", "interpretation", "conclusion"] = "fact"
    status: Literal[
        "DOCUMENTED RECORD", "ACCEPTED TESTIMONY", "PUBLISHED WHITE RABBIT CANON",
        "CORROBORATED INFERENCE", "PLAUSIBLE CONNECTION", "SPECULATION", "CONTRADICTED",
    ] = "DOCUMENTED RECORD"
    attribution: str | None = Field(default=None, max_length=1000)
    entity_refs: list[str] = Field(default_factory=list)
    historical_start: TemporalValue = Field(default_factory=TemporalValue)
    historical_end: TemporalValue = Field(default_factory=TemporalValue)
    independent: bool = True
    dependency_group: str | None = Field(default=None, max_length=300)


class ProposalRelationship(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject_ref: str
    object_ref: str
    relationship_type: str = Field(min_length=1, max_length=200)
    directed: bool = True
    classification: Literal[
        "DOCUMENTED RECORD", "ACCEPTED TESTIMONY", "PUBLISHED WHITE RABBIT CANON",
        "CORROBORATED INFERENCE", "PLAUSIBLE CONNECTION", "SPECULATION", "CONTRADICTED",
    ] = "DOCUMENTED RECORD"
    historical_start: TemporalValue = Field(default_factory=TemporalValue)
    historical_end: TemporalValue = Field(default_factory=TemporalValue)
    claim_ref: str | None = None
    supporting_passage: str = Field(min_length=1, max_length=5000)
    passage_start: int | None = Field(default=None, ge=0)


class ProposalDocumentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_type: str = Field(min_length=1, max_length=200)
    title: str | None = Field(default=None, max_length=1000)
    author: str | None = Field(default=None, max_length=500)
    sender: str | None = Field(default=None, max_length=500)
    recipient: str | None = Field(default=None, max_length=500)
    document_date: str | None = Field(default=None, max_length=100)
    description: str = Field(default="", max_length=5000)
    supporting_passage: str = Field(min_length=1, max_length=5000)
    passage_start: int | None = Field(default=None, ge=0)


class ChunkExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entities: list[ProposalEntity] = Field(default_factory=list, max_length=100)
    claims: list[ProposalClaim] = Field(default_factory=list, max_length=150)
    relationships: list[ProposalRelationship] = Field(default_factory=list, max_length=150)
    document_metadata: list[ProposalDocumentMetadata] = Field(default_factory=list, max_length=20)
    skipped_or_unreadable: list[str] = Field(default_factory=list, max_length=50)
    notes: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def references_exist(self) -> "ChunkExtraction":
        entity_refs = {item.ref for item in self.entities}
        claim_refs = {item.ref for item in self.claims}
        if len(entity_refs) != len(self.entities) or len(claim_refs) != len(self.claims):
            raise ValueError("entity and claim refs must be unique within a chunk")
        for claim in self.claims:
            if set(claim.entity_refs) - entity_refs:
                raise ValueError("claim contains unknown entity refs")
        for relationship in self.relationships:
            if relationship.subject_ref not in entity_refs or relationship.object_ref not in entity_refs:
                raise ValueError("relationship contains unknown entity refs")
            if relationship.claim_ref and relationship.claim_ref not in claim_refs:
                raise ValueError("relationship contains an unknown claim ref")
        return self


class ProviderResult(BaseModel):
    extraction: ChunkExtraction
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    provider_request_id: str | None = None
