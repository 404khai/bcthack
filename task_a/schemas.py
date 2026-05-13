
"""Pydantic models for Task A endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ReviewHistoryEntry(BaseModel):
    """Historical review entry used to infer style and rating behavior."""

    item_id: str = Field(..., description="Identifier of an item previously reviewed by the user.")
    text: str = Field(..., description="Historical review text written by the user.")
    rating: float = Field(..., ge=1.0, le=5.0, description="Historical star rating given by the user.")
    category: str = Field(..., description="Category of the historical item.")
    created_at: str | None = Field(None, description="Optional timestamp associated with the review.")
    attributes: dict[str, Any] = Field(default_factory=dict, description="Optional metadata about the reviewed item.")


class UserPersona(BaseModel):
    """Structured persona payload supplied to the review generation service."""

    user_id: str = Field(..., description="Unique user identifier.")
    platform: str = Field("unknown", description="Dataset or platform source for the persona.")
    review_history: list[ReviewHistoryEntry] = Field(
        default_factory=list,
        description="Prior user reviews used to infer writing style.",
    )
    preferences: dict[str, Any] = Field(
        default_factory=dict,
        description="Preference hints such as favorite categories, brands, or tones.",
    )


class ItemDetails(BaseModel):
    """Target item details for which a review should be generated."""

    item_id: str = Field(..., description="Identifier of the target item to review.")
    name: str = Field(..., description="Human-readable item name.")
    category: str = Field(..., description="Item category.")
    attributes: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured attributes describing the item, such as taste, ambience, or build quality.",
    )


class ReviewRequest(BaseModel):
    """Request body for the Task A review generation endpoint."""

    user_persona: UserPersona = Field(..., description="Persona profile used for behavioral mimicry.")
    item_details: ItemDetails = Field(..., description="Item details for which a review should be generated.")
    nigerian_mode: bool = Field(False, description="Enables Nigerian contextualization in the generated response.")
    nigerian_intensity: str = Field("medium", description="Intensity of Nigerian contextualization (light, medium, full).")


class ReviewResponse(BaseModel):
    """Generated review payload returned by the Task A service."""

    user_id: str = Field(..., description="Unique user identifier.")
    item_id: str = Field(..., description="Identifier of the item that was reviewed.")
    rating: float = Field(..., ge=1.0, le=5.0, description="Predicted star rating.")
    review_text: str = Field(..., description="Generated review text written in the user's inferred style.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence in the generated review and rating.")
    style_notes: str = Field(..., description="Human-readable summary of the style constraints used in generation.")
    style_fingerprint: dict[str, Any] = Field(..., description="Derived stylistic summary of the persona.")
    nigerian_mode: bool = Field(..., description="Indicates whether Nigerian contextualization was applied.")


class HealthResponse(BaseModel):
    """Simple service health payload."""

    status: str = Field(..., description="Service health status.")
    service: str = Field(..., description="Name of the responding service.")
