"""Pydantic models for Task B endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class InteractionHistoryEntry(BaseModel):
    item_id: str = Field(..., description="Identifier of an item the user has interacted with.")
    signal: str = Field(..., description="Interaction signal such as viewed, liked, purchased, or reviewed.")
    category: str = Field(..., description="Category associated with the prior interaction.")
    rating: float | None = Field(None, ge=1.0, le=5.0, description="Optional rating supplied by the user.")


class PersonaInput(BaseModel):
    user_id: str = Field(..., description="Unique user identifier.")
    source: str = Field(..., description="Dataset or system source for the persona.")
    preferences: list[str] = Field(default_factory=list, description="Known interests or categories the user enjoys.")
    history: list[InteractionHistoryEntry] = Field(default_factory=list, description="Historical interactions used to personalize retrieval and ranking.")


class RecommendRequest(BaseModel):
    user_persona: PersonaInput = Field(..., description="Persona profile used to personalize recommendations.")
    query: str = Field(..., description="Natural-language request that describes what the user wants.")
    top_k: int = Field(5, ge=1, le=20, description="Maximum number of recommendations to return.")
    conversation_id: str | None = Field(None, description="Optional identifier for continuing a multi-turn recommendation session.")
    nigerian_mode: bool = Field(False, description="Enables Nigerian contextualization in the recommendation explanations.")
    enable_cross_domain: bool = Field(True, description="Allows cross-domain preference transfer when ranking items.")


class RecommendationItem(BaseModel):
    item_id: str = Field(..., description="Identifier of the recommended item.")
    title: str = Field(..., description="Human-readable item or experience title.")
    category: str = Field(..., description="Recommendation category.")
    score: float = Field(..., description="Ranking score assigned by the recommender.")
    explanation: str = Field(..., description="Human-readable reason the item was recommended.")
    source: str = Field(..., description="Origin of the recommendation candidate.")


class RecommendResponse(BaseModel):
    user_id: str = Field(..., description="Unique user identifier.")
    recommendations: list[RecommendationItem] = Field(..., description="Ranked personalized recommendations.")
    thinking: list[str] = Field(..., description="Compact reasoning trace describing how candidates were selected and ranked.")
    nigerian_mode: bool = Field(..., description="Indicates whether Nigerian contextualization was applied.")


class HealthResponse(BaseModel):
    status: str = Field(..., description="Service health status.")
    service: str = Field(..., description="Name of the responding service.")
