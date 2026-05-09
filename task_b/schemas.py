
"""Pydantic models for Task B endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class InteractionHistoryEntry(BaseModel):
    """Historical interaction signal used for personalization."""

    item_id: str = Field(..., description="Identifier of an item the user has interacted with.")
    signal: str = Field(..., description="Interaction signal such as viewed, liked, purchased, or reviewed.")
    category: str = Field(..., description="Category associated with the prior interaction.")
    rating: float | None = Field(None, ge=1.0, le=5.0, description="Optional rating supplied by the user.")
    text: str | None = Field(None, description="Optional free-text review or note from the user.")
    attributes: dict[str, Any] = Field(default_factory=dict, description="Optional metadata for the interacted item.")


class UserPersona(BaseModel):
    """Persona payload used by the Task B recommendation agent."""

    user_id: str = Field(..., description="Unique user identifier.")
    platform: str = Field("unknown", description="Dataset or platform source for the persona.")
    preferences: dict[str, Any] = Field(
        default_factory=dict,
        description="Known interests, preference hints, demographics, or contextual constraints.",
    )
    history: list[InteractionHistoryEntry] = Field(
        default_factory=list,
        description="Historical interactions used for warm-start retrieval and ranking.",
    )
    persona_text: str | None = Field(
        None,
        description="Optional natural-language persona summary for cold-start reasoning.",
    )


class RequestContext(BaseModel):
    """Structured request context that helps retrieval and ranking."""

    category: str | None = Field(None, description="Primary category the user is currently interested in.")
    target_domain: str | None = Field(None, description="Optional target domain for cross-domain recommendations.")
    item_attributes: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured attributes that describe the desired item or experience.",
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Explicit constraints such as budget, location, tone, or dietary needs.",
    )


class Item(BaseModel):
    """Recommendation candidate returned by retrieval components."""

    item_id: str = Field(..., description="Identifier of the candidate item.")
    title: str = Field(..., description="Human-readable item title.")
    category: str = Field(..., description="Category or domain of the candidate.")
    source: str = Field(..., description="Origin of the candidate item.")
    similarity_score: float = Field(..., description="Retriever similarity score before reranking.")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional structured metadata used by downstream ranking.",
    )


class RankedItem(BaseModel):
    """Final ranked recommendation with explanation and confidence."""

    item: Item = Field(..., description="Underlying recommendation candidate.")
    score: float = Field(..., description="Reranked score between 0 and 10.")
    explanation: str = Field(..., description="Human-readable rationale for this recommendation.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence assigned by the ranking layer.")


class Turn(BaseModel):
    """Conversation turn stored for multi-turn recommendation sessions."""

    user_message: str = Field(..., description="The message sent by the user.")
    assistant_message: str = Field(..., description="The message returned by the assistant.")
    context: dict[str, Any] = Field(default_factory=dict, description="Structured turn context used for later refinement.")


class RecommendRequest(BaseModel):
    """Single-shot Task B recommendation request."""

    user_persona: UserPersona = Field(..., description="Persona profile used to personalize recommendations.")
    query: str = Field(..., description="Natural-language request that describes what the user wants.")
    request_context: RequestContext = Field(
        default_factory=RequestContext,
        description="Structured context that sharpens retrieval and ranking.",
    )
    top_k: int = Field(5, ge=1, le=20, description="Maximum number of recommendations to return.")
    session_id: str | None = Field(None, description="Optional session identifier to associate the response with a conversation.")
    nigerian_mode: bool = Field(False, description="Enables Nigerian contextualization and defaults.")
    enable_cross_domain: bool = Field(True, description="Allows cross-domain preference transfer when ranking items.")


class ChatRequest(BaseModel):
    """Multi-turn chat request for conversational recommendation."""

    session_id: str = Field(..., description="Conversation session identifier.")
    user_persona: UserPersona = Field(..., description="Persona profile used to personalize recommendations.")
    message: str = Field(..., description="Latest user message in the conversation.")
    request_context: RequestContext = Field(
        default_factory=RequestContext,
        description="Structured context for the current conversational turn.",
    )
    top_k: int = Field(5, ge=1, le=20, description="Maximum number of recommendations to return.")
    nigerian_mode: bool = Field(False, description="Enables Nigerian contextualization and defaults.")
    enable_cross_domain: bool = Field(True, description="Allows cross-domain preference transfer when ranking items.")


class RecommendResponse(BaseModel):
    """Single-shot recommendation response."""

    user_id: str = Field(..., description="Unique user identifier.")
    recommendations: list[RankedItem] = Field(..., description="Ranked personalized recommendations.")
    thinking: list[str] = Field(..., description="Reasoning steps produced before retrieval and ranking.")
    strategy: str = Field(..., description="Retrieval strategy selected by the planner.")
    session_id: str | None = Field(None, description="Optional session identifier associated with the response.")
    nigerian_mode: bool = Field(..., description="Indicates whether Nigerian contextualization was applied.")


class ChatResponse(BaseModel):
    """Conversational recommendation response with chat-oriented messaging."""

    session_id: str = Field(..., description="Conversation session identifier.")
    assistant_message: str = Field(..., description="Natural-language assistant reply for the current turn.")
    recommendations: list[RankedItem] = Field(..., description="Ranked personalized recommendations.")
    thinking: list[str] = Field(..., description="Reasoning steps produced before retrieval and ranking.")
    refined_preferences: dict[str, float] = Field(
        default_factory=dict,
        description="Preference map inferred from conversation history.",
    )
    nigerian_mode: bool = Field(..., description="Indicates whether Nigerian contextualization was applied.")


class SessionHistoryResponse(BaseModel):
    """Returns conversation history for a stored recommendation session."""

    session_id: str = Field(..., description="Conversation session identifier.")
    turns: list[Turn] = Field(..., description="Ordered conversation turns stored for the session.")


class SessionClearResponse(BaseModel):
    """Acknowledges the removal of a conversation session."""

    session_id: str = Field(..., description="Conversation session identifier.")
    cleared: bool = Field(..., description="Indicates whether the session state was cleared.")


class HealthResponse(BaseModel):
    """Simple service health payload."""

    status: str = Field(..., description="Service health status.")
    service: str = Field(..., description="Name of the responding service.")
