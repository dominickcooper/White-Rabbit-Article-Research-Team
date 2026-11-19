from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .temporal import HistoricalDate


EntityType = Literal["person", "organization", "event", "place"]


class TemporalValue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str | None = None
    precision: Literal["exact", "month", "year", "approximate", "unknown"] = "unknown"
    certainty: Literal["certain", "probable", "possible", "uncertain", "unknown"] = "unknown"

    @model_validator(mode="after")
    def valid_value(self) -> "TemporalValue":
        if self.value is None:
            if self.precision != "unknown":
                raise ValueError("a missing date value must use unknown precision")
            return self
        HistoricalDate(self.value, self.precision, self.certainty).bounds()
        return self


class DocumentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1)
    title: str | None = None
    author: str | None = None
    document_date: str | None = None
    source_classification: str = "author_supplied"
    authority_level: int = Field(default=2, ge=1, le=3)


class EntityInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: str = Field(min_length=1, max_length=200)
    known_entity_id: str | None = None
    entity_type: EntityType
    name: str = Field(min_length=1, max_length=500)
    aliases: list[str] = Field(default_factory=list)
    description: str = ""
    details: dict = Field(default_factory=dict)


class ClaimInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ref: str | None = None
    statement: str = Field(min_length=1)
    original_wording: str | None = None
    claim_type: Literal["fact", "testimony", "allegation", "interpretation", "conclusion"] = "fact"
    status: Literal[
        "DOCUMENTED RECORD", "ACCEPTED TESTIMONY", "PUBLISHED WHITE RABBIT CANON",
        "CORROBORATED INFERENCE", "PLAUSIBLE CONNECTION", "SPECULATION", "CONTRADICTED",
    ] = "DOCUMENTED RECORD"
    historical_start: TemporalValue = Field(default_factory=TemporalValue)
    historical_end: TemporalValue = Field(default_factory=TemporalValue)
    entity_refs: list[str] = Field(default_factory=list)
    locator: str | None = None
    independent: bool = True
    dependency_group: str | None = None


class RelationshipInput(BaseModel):
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
    original_wording: str | None = None
    locator: str | None = None


class ConflictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    claim_ref_a: str
    claim_ref_b: str
    reason: str = ""
    requires_author_review: bool = True


class VaultImport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    document: DocumentInput
    entities: list[EntityInput] = Field(default_factory=list)
    claims: list[ClaimInput] = Field(default_factory=list)
    relationships: list[RelationshipInput] = Field(default_factory=list)
    conflicts: list[ConflictInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_refs(self) -> "VaultImport":
        refs = [item.ref for item in self.entities] + [item.ref for item in self.claims if item.ref]
        if len(refs) != len(set(refs)):
            raise ValueError("entity and claim refs must be unique")
        entity_refs = {item.ref for item in self.entities}
        claim_refs = {item.ref for item in self.claims if item.ref}
        for claim in self.claims:
            if set(claim.entity_refs) - entity_refs:
                raise ValueError(f"claim {claim.ref or claim.statement!r} contains unknown entity refs")
        for relationship in self.relationships:
            if relationship.subject_ref not in entity_refs or relationship.object_ref not in entity_refs:
                raise ValueError("relationship contains unknown entity refs")
            if relationship.claim_ref and relationship.claim_ref not in claim_refs:
                raise ValueError("relationship contains an unknown claim ref")
        for conflict in self.conflicts:
            if conflict.claim_ref_a not in claim_refs or conflict.claim_ref_b not in claim_refs:
                raise ValueError("conflict contains unknown claim refs")
        return self
