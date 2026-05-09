"""Pydantic models for Task A endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReviewHistoryEntry(BaseModel):
    item_id: str = Field(..., description="Identifier of an item previously reviewed by the user.")
    text: str = Field(..., description="Historical review text written by the user.")
    rating: float = Field(..., ge=1.0, le=5.0, description="Historical star rating given by the user.")
    category: str = Field(..., description="Category of the historical item.")


class PersonaInput(BaseModel):
    user_id: str = Field(..., description="Unique user identifier.")
    source: str = Field(..., description="Dataset or system source for the persona.")
    preferences: list[str] = Field(default_factory=list, description="Known user interests or preferred categories.")
    history: list[ReviewHistoryEntry] = Field(default_factory=list, description="Prior user reviews used to infer writing style.")


class ItemInput(BaseModel):
    item_id: str = Field(..., description="Identifier of the target item to review.")
    name: str = Field(..., description="Human-readable item name.")
    description: str = Field(..., description="Short item description used in generation.")
    category: str = Field(..., description="Item category.")


class GenerateReviewRequest(BaseModel):
    user_persona: PersonaInput = Field(..., description="Persona profile used for behavioral mimicry.")
    item: ItemInput = Field(..., description="Item details for which a review should be generated.")
    nigerian_mode: bool = Field(False, description="Enables Nigerian contextualization in the generated response.")


class GenerateReviewResponse(BaseModel):
    user_id: str = Field(..., description="Unique user identifier.")
    item_id: str = Field(..., description="Identifier of the item that was reviewed.")
    rating: float = Field(..., ge=1.0, le=5.0, description="Predicted star rating.")
    review: str = Field(..., description="Generated review text written in the user's inferred style.")
    style_fingerprint: dict = Field(..., description="Derived stylistic summary of the persona.")
    source: str = Field(..., description="Persona source dataset or system.")
    nigerian_mode: bool = Field(..., description="Indicates whether Nigerian contextualization was applied.")


class HealthResponse(BaseModel):
    status: str = Field(..., description="Service health status.")
    service: str = Field(..., description="Name of the responding service.")
