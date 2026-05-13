
"""Claude-backed reranker for Task B candidates."""

from __future__ import annotations

import json
from os import getenv
from typing import Any

from shared.llm_client import AnthropicLLMClient
from shared.nigerian_adapter import NigerianContextAdapter
from shared.prompts import TASK_B_RERANK_SYSTEM, TASK_B_RERANK_USER
from task_b.schemas import Item, RankedItem, RequestContext, UserPersona

CLAUDE_MODEL_NAME = "claude-sonnet-4-20250514"

class LLMRanker:
    """Reranks retrieved candidates using Claude with deterministic fallback logic."""

    def __init__(self, llm_client: AnthropicLLMClient | None = None) -> None:
        self._llm_client = llm_client

    async def rerank(
        self,
        candidates: list[Item],
        user_profile: UserPersona,
        query_context: RequestContext,
        *,
        nigerian_mode: bool = False,
    ) -> list[RankedItem]:
        """Returns reranked candidates with explanations and confidence values."""
        if not candidates:
            return []

        client = self._get_llm_client()
        adapter = NigerianContextAdapter(enabled=nigerian_mode)
        if client is not None:
            try:
                response = await client.generate_text(
                    system_prompt=TASK_B_RERANK_SYSTEM,
                    user_prompt=TASK_B_RERANK_USER.format(
                        user_profile=user_profile.model_dump(),
                        query_context=query_context.model_dump(),
                        candidates=[candidate.model_dump() for candidate in candidates[:20]],
                    ),
                    max_tokens=700,
                    temperature=0.25,
                )
                parsed = json.loads(response)
                ranked = await self._parse_ranked_response(parsed, candidates, adapter)
                if ranked:
                    return ranked
            except Exception:
                pass

        return await self._fallback_rank(candidates, user_profile, query_context, adapter)

    async def _parse_ranked_response(
        self,
        parsed: object,
        candidates: list[Item],
        adapter: NigerianContextAdapter,
    ) -> list[RankedItem]:
        candidate_map = {candidate.item_id: candidate for candidate in candidates}
        if not isinstance(parsed, list):
            return []
        ranked_items: list[RankedItem] = []
        for row in parsed:
            if not isinstance(row, dict):
                continue
            item_id = str(row.get("item_id", ""))
            candidate = candidate_map.get(item_id)
            if candidate is None:
                continue
                
            explanation = str(row.get("explanation", "Recommended based on profile fit."))
            adapted_explanation = await adapter.adapt_recommendation_explanation(explanation, candidate.category)
            
            ranked_items.append(
                RankedItem(
                    item=candidate.model_copy(
                        update={"category": adapter.adapt_category(candidate.category)}
                    ),
                    score=round(max(0.0, min(10.0, float(row.get("score", 0.0)))), 3),
                    confidence=round(max(0.0, min(1.0, float(row.get("confidence", 0.5)))), 3),
                    explanation=adapted_explanation,
                )
            )
        return sorted(ranked_items, key=lambda item: item.score, reverse=True)

    async def _fallback_rank(
        self,
        candidates: list[Item],
        user_profile: UserPersona,
        query_context: RequestContext,
        adapter: NigerianContextAdapter,
    ) -> list[RankedItem]:
        favorite_categories = user_profile.preferences.get("favorite_categories", [])
        favorite_set = {str(category).lower() for category in favorite_categories} if isinstance(favorite_categories, list) else set()
        target_category = (query_context.category or "").lower()
        ranked: list[RankedItem] = []
        for candidate in candidates:
            score = candidate.similarity_score * 10
            if candidate.category.lower() == target_category and target_category:
                score += 1.0
            if candidate.category.lower() in favorite_set:
                score += 0.8
            explanation = (
                f"{candidate.title} fits the request because it aligns with "
                f"{query_context.category or 'the stated intent'} and the user's known preferences."
            )
            adapted_explanation = await adapter.adapt_recommendation_explanation(explanation, candidate.category)
            confidence = max(0.35, min(0.95, candidate.similarity_score))
            ranked.append(
                RankedItem(
                    item=candidate.model_copy(
                        update={"category": adapter.adapt_category(candidate.category)}
                    ),
                    score=round(min(10.0, score), 3),
                    confidence=round(confidence, 3),
                    explanation=adapted_explanation,
                )
            )
        return sorted(ranked, key=lambda item: item.score, reverse=True)

    def _get_llm_client(self) -> AnthropicLLMClient | None:
        if self._llm_client is not None:
            return self._llm_client
        if not getenv("ANTHROPIC_API_KEY"):
            return None
        self._llm_client = AnthropicLLMClient(model=CLAUDE_MODEL_NAME)
        return self._llm_client
