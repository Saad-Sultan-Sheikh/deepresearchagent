"""Entity and relationship models extracted from raw search results."""

from __future__ import annotations

import json
import uuid
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator


class Entity(BaseModel):
    entity_id: str = Field(default_factory=lambda: f"ent_{uuid.uuid4().hex[:8]}")
    label: str = Field(..., description="Person | Organization | Location | Email | Phone | Url | Alias | FinancialAccount")
    value: str = Field(default="")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    source_urls: list[str] = Field(default_factory=list)
    # Backfilled by extractor node after LLM call — not expected from LLM output
    extracted_at: str = Field(default="", description="ISO datetime")
    metadata: dict = Field(default_factory=dict)

    @field_validator("metadata", mode="before")
    @classmethod
    def coerce_metadata(cls, v: Any) -> dict:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return {}
        return v if isinstance(v, dict) else {}


class Relationship(BaseModel):
    relationship_id: str = Field(default_factory=lambda: f"rel_{uuid.uuid4().hex[:8]}")
    type: str = Field(..., description="e.g. WORKS_AT, HAS_EMAIL, ASSOCIATED_WITH")
    source_entity_id: str
    target_entity_id: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence: str = Field(default="")
    properties: dict = Field(default_factory=dict)
    # Backfilled by extractor node after LLM call — not expected from LLM output
    created_at: str = Field(default="", description="ISO datetime")

    @field_validator("properties", mode="before")
    @classmethod
    def coerce_properties(cls, v: Any) -> dict:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except Exception:
                return {}
        return v if isinstance(v, dict) else {}


class Contradiction(BaseModel):
    field: str
    value_a: str
    source_a: str
    value_b: str
    source_b: str
    description: str


class ExtractedEntities(BaseModel):
    """Full set of entities and relationships extracted from search results."""

    persona_id: str
    run_id: str
    extracted_at: str

    # Core identity
    primary_name: Optional[str] = None
    name_variants: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    date_of_birth: Optional[str] = None
    nationalities: list[str] = Field(default_factory=list)

    # Contact
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)

    # Locations
    current_locations: list[str] = Field(default_factory=list)
    historical_locations: list[dict] = Field(default_factory=list)

    # Professional
    current_employers: list[str] = Field(default_factory=list)
    historical_employers: list[dict] = Field(default_factory=list)
    education_history: list[dict] = Field(default_factory=list)

    # Digital
    social_handles: list[str] = Field(default_factory=list)
    websites: list[str] = Field(default_factory=list)

    # Financial
    financial_accounts: list[str] = Field(default_factory=list)
    financial_entities: list[str] = Field(default_factory=list)

    # Social graph
    associates: list[dict] = Field(default_factory=list)

    # Raw graph entities
    entities: list[Entity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)

    # Quality
    contradictions: list[Contradiction] = Field(default_factory=list)
    data_gaps: list[str] = Field(default_factory=list)
    source_count: int = Field(default=0)
