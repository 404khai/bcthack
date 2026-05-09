"""Fallback candidate generation when user history is sparse."""

from __future__ import annotations

from task_b.schemas import RecommendRequest, RecommendationItem


class ColdStartHandler:
    def generate_candidates(self, request: RecommendRequest) -> list[RecommendationItem]:
        preferences = request.user_persona.preferences or ["general discovery"]
        return [
            RecommendationItem(
                item_id=f"cold-{index}",
                title=f"Starter recommendation for {preference}",
                category=preference,
                score=round(0.75 - (index * 0.05), 3),
                explanation="Generated from the user's explicit preferences because no warm history was available.",
                source="cold_start",
            )
            for index, preference in enumerate(preferences[: request.top_k])
        ]
