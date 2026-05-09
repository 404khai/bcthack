"""Ranks recommendation candidates with lightweight heuristics."""

from __future__ import annotations

from shared.nigerian_adapter import NigerianContextAdapter
from task_b.schemas import RecommendRequest, RecommendationItem


class RecommendationRanker:
    def rank(
        self,
        request: RecommendRequest,
        candidates: list[RecommendationItem],
    ) -> list[RecommendationItem]:
        adapter = NigerianContextAdapter(enabled=request.nigerian_mode)
        ranked = sorted(candidates, key=lambda item: item.score, reverse=True)[: request.top_k]
        return [
            RecommendationItem(
                item_id=item.item_id,
                title=item.title,
                category=adapter.adapt_category(item.category),
                score=item.score,
                explanation=adapter.adapt_text(item.explanation),
                source=item.source,
            )
            for item in ranked
        ]
