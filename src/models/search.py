"""Search-layer Pydantic models — queries, raw results, metadata."""

from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class SearchCategory(str, Enum):
    IDENTITY = "identity"
    EMPLOYMENT = "employment"
    EDUCATION = "education"
    SOCIAL = "social"
    FINANCIAL = "financial"
    LEGAL = "legal"
    ASSOCIATES = "associates"
    NEWS = "news"
    GENERAL = "general"


class SearchQuery(BaseModel):
    query_id: str = Field(..., description="Unique ID e.g. q_001")
    text: str = Field(..., description="Raw search string")
    category: SearchCategory = Field(default=SearchCategory.GENERAL)
    priority: int = Field(default=5, ge=1, le=10, description="1=lowest, 10=highest")
    rationale: str = Field(default="", description="Why this query was generated")


class RawResult(BaseModel):
    result_id: str
    query_id: str
    source_api: str = Field(..., description="tavily | brave | exa")
    url: str
    title: str
    snippet: str
    full_content: Optional[str] = None
    published_date: Optional[str] = None
    relevance_score: float = Field(default=0.0, ge=0.0, le=1.0)
    retrieved_at: str = Field(..., description="ISO datetime")


class SearchMeta(BaseModel):
    api: str
    query_id: str
    result_count: int
    latency_ms: float
    success: bool
    error: Optional[str] = None


class SearchPlan(BaseModel):
    """Structured output from the planner LLM."""
    queries: list[SearchQuery]
    strategy: str = Field(..., description="High-level explanation of the search strategy")
