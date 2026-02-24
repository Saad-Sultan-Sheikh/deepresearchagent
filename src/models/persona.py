"""PersonaInput Pydantic model — seed data for each research target."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class PersonaInput(BaseModel):
    """Seed information provided about a research target."""

    persona_id: str = Field(..., description="Unique identifier e.g. persona_001")
    full_name: str = Field(..., description="Primary full name of the target")
    aliases: list[str] = Field(default_factory=list, description="Known aliases or name variants")
    date_of_birth: Optional[str] = Field(None, description="ISO date or partial e.g. '1982-04-15' or '1982'")
    nationalities: list[str] = Field(default_factory=list)
    known_locations: list[str] = Field(default_factory=list, description="Cities, countries, addresses")
    employers: list[str] = Field(default_factory=list, description="Current/known employers or organisations")
    education: list[str] = Field(default_factory=list)
    social_profiles: list[str] = Field(default_factory=list, description="URLs or handles")
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    notes: str = Field(default="", description="Free-form seed notes / context")
    risk_seed: str = Field(
        default="UNKNOWN",
        description="Operator's initial risk hint: LOW | MEDIUM | HIGH | UNKNOWN",
    )
