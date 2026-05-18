
"""Claude-backed reranker for Task B candidates."""

from dotenv import load_dotenv
load_dotenv(override=True)

import json
import logging
from os import getenv

from shared.llm_client import GeminiLLMClient
from shared.nigerian_adapter import NigerianContextAdapter
from shared.prompts import TASK_B_RERANK_SYSTEM, TASK_B_RERANK_USER
from task_b.schemas import Item, RankedItem, RequestContext, UserPersona

logger = logging.getLogger(__name__)

class LLMRanker:
    """Reranks retrieved candidates using Claude with deterministic fallback logic."""

    def __init__(self, llm_client: GeminiLLMClient | None = None) -> None:
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
                llm_candidates = candidates[:8]
                logger.info("[RANKER] Calling LLM for %d candidates", len(llm_candidates))
                response = await client.complete(
                    system=(
                        TASK_B_RERANK_SYSTEM
                        + "\nFor each item, write 2-3 sentences explaining WHY this specific "
                          "item matches this specific user's preferences. Reference the item's actual "
                          "name, category, and the user's known interests. Do not use generic phrases "
                          "like 'aligns with preferences'."
                    ),
                    user=TASK_B_RERANK_USER.format(
                        user_profile=user_profile.model_dump(),
                        query_context=query_context.model_dump(),
                        candidates=[candidate.model_dump() for candidate in llm_candidates],
                    ),
                    max_tokens=4096,
                )
                parsed = json.loads(self._extract_json_payload(response))
                ranked = await self._parse_ranked_response(parsed, candidates, adapter)
                if ranked:
                    logger.info("[RANKER] LLM explanation sample: %s", ranked[0].explanation[:100])
                    return ranked
                logger.warning("[RANKER] LLM returned no usable ranked rows; falling back.")
            except Exception as error:
                logger.error("[RANKER] LLM failed: %s", error, exc_info=True)

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
                f"{candidate.title} is a relevant match because it sits in the {candidate.category} category "
                f"and carries metadata that overlaps with the current request for "
                f"{query_context.category or 'this type of item'}. It remains a heuristic fallback "
                f"because the LLM ranking step did not return a usable explanation."
            )
            adapted_explanation = await adapter.adapt_recommendation_explanation(explanation, candidate.category)
            confidence = max(0.35, min(0.95, candidate.similarity_score))
            ranked.append(
                RankedItem(
                    item=candidate.model_copy(
                        update={"category": adapter.adapt_category(candidate.category)}
                    ),
                    score=round(max(0.0, min(10.0, score)), 3),
                    confidence=round(confidence, 3),
                    explanation=adapted_explanation,
                )
            )
        return sorted(ranked, key=lambda item: item.score, reverse=True)

    def _get_llm_client(self) -> GeminiLLMClient | None:
        if self._llm_client is not None:
            return self._llm_client
        if not getenv("GEMINI_API_KEY"):
            return None
        self._llm_client = GeminiLLMClient()
        return self._llm_client

    def _extract_json_payload(self, response: str) -> str:
        """Strips markdown and salvages complete JSON objects from truncated arrays."""
        cleaned = response.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        start = cleaned.find("[")
        if start == -1:
            return "[]"

        candidate = cleaned[start:]
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

        salvaged: list[str] = []
        depth = 0
        obj_start: int | None = None
        in_string = False
        escape = False

        for index, char in enumerate(candidate[1:], start=1):
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
                continue

            if char == "{":
                if depth == 0:
                    obj_start = index
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0 and obj_start is not None:
                    obj_str = candidate[obj_start : index + 1]
                    try:
                        json.loads(obj_str)
                        salvaged.append(obj_str)
                    except json.JSONDecodeError:
                        pass
                    obj_start = None

        if salvaged:
            logger.warning(
                "[RANKER] Salvaged %d complete objects from truncated JSON",
                len(salvaged),
            )
            return "[" + ",".join(salvaged) + "]"

        logger.error("[RANKER] Could not salvage any JSON objects from response")
        return "[]"
