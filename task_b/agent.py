
"""Task B recommendation orchestration layer."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from itertools import chain

from shared.vector_store import VectorStore
from task_b.cold_start import ColdStartHandler
from task_b.conversation import ConversationManager
from task_b.cross_domain import CrossDomainBridge
from task_b.ranker import LLMRanker
from task_b.retriever import MultiSourceRetriever
from task_b.schemas import (
    ChatRequest,
    ChatResponse,
    RecommendRequest,
    RecommendResponse,
    RequestContext,
    RankedItem,
    SessionHistoryResponse,
    UserPersona,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class StrategyPlan:
    """Captures the selected retrieval strategy and reasoning notes."""

    strategy: str
    notes: list[str]


class RecommendationAgent:
    """Implements a reasoning-first recommendation loop for Task B."""

    def __init__(self) -> None:
        self.vector_store = VectorStore()
        self.retriever = MultiSourceRetriever(vector_store=self.vector_store)
        self.cold_start = ColdStartHandler()
        self.cross_domain = CrossDomainBridge()
        self.conversation = ConversationManager()
        self.ranker = LLMRanker()

    async def recommend(self, request: RecommendRequest) -> RecommendResponse:
        """Runs the full reasoning loop for a single-shot recommendation request."""
        return await self._recommend_internal(request, persist_turn=True)

    async def _recommend_internal(
        self,
        request: RecommendRequest,
        *,
        persist_turn: bool,
    ) -> RecommendResponse:
        """Runs the shared recommendation flow with optional session persistence."""
        conversation_history = self.conversation.get_history(request.session_id) if request.session_id else []
        refined_preferences = (
            await self.conversation.extract_refined_preferences(request.session_id)
            if request.session_id
            else {}
        )
        chroma_user = self.vector_store.get_by_id("users", request.user_persona.user_id)
        review_count = self._extract_review_count(chroma_user)
        is_warm = await self._is_warm_user(request.user_persona.user_id)
        logger.info("[AGENT_B] User warm: %s", is_warm)
        thinking = self._build_reasoning_prompt(
            query=request.query,
            user_profile=request.user_persona,
            request_context=request.request_context,
            refined_preferences=refined_preferences,
            review_count=review_count,
            is_warm=is_warm,
            chroma_user=chroma_user,
        )
        plan = self._plan_strategy(
            is_warm=is_warm,
            request_context=request.request_context,
            enable_cross_domain=request.enable_cross_domain,
            source_platform=(chroma_user or {}).get("metadata", {}).get("platform", request.user_persona.platform),
        )
        candidates, retrieval_notes = await self._retrieve_candidates(
            request,
            plan,
            refined_preferences,
            chroma_user,
            is_warm,
        )
        thinking.extend(retrieval_notes)
        ranked = await self.ranker.rerank(
            candidates=candidates,
            user_profile=request.user_persona,
            query_context=request.request_context,
            nigerian_mode=request.nigerian_mode,
        )
        final_ranked = ranked[: request.top_k]
        if request.session_id and persist_turn:
            self.conversation.add_turn(
                session_id=request.session_id,
                user_msg=request.query,
                assistant_msg=self._format_assistant_message(final_ranked),
                context={
                    "category": request.request_context.category,
                    "constraints": request.request_context.constraints,
                    "strategy": plan.strategy,
                    "conversation_turns_seen": len(conversation_history),
                },
            )
        return RecommendResponse(
            user_id=request.user_persona.user_id,
            recommendations=final_ranked,
            thinking=thinking + plan.notes,
            strategy=plan.strategy,
            session_id=request.session_id,
            nigerian_mode=request.nigerian_mode,
        )

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Runs the reasoning loop for a conversational recommendation turn."""
        recommend_response = await self._recommend_internal(
            RecommendRequest(
                user_persona=request.user_persona,
                query=request.message,
                request_context=request.request_context,
                top_k=request.top_k,
                session_id=request.session_id,
                nigerian_mode=request.nigerian_mode,
                enable_cross_domain=request.enable_cross_domain,
            ),
            persist_turn=False,
        )
        refined_preferences = await self.conversation.extract_refined_preferences(request.session_id)
        assistant_message = self._format_chat_message(recommend_response.recommendations)
        self.conversation.add_turn(
            session_id=request.session_id,
            user_msg=request.message,
            assistant_msg=assistant_message,
            context={
                "category": request.request_context.category,
                "constraints": request.request_context.constraints,
                "mode": "chat",
            },
        )
        return ChatResponse(
            session_id=request.session_id,
            assistant_message=assistant_message,
            recommendations=recommend_response.recommendations,
            thinking=recommend_response.thinking,
            refined_preferences=refined_preferences,
            nigerian_mode=request.nigerian_mode,
        )

    async def get_session_history(self, session_id: str) -> SessionHistoryResponse:
        """Returns stored conversation history for a session."""
        return SessionHistoryResponse(
            session_id=session_id,
            turns=self.conversation.get_history(session_id),
        )

    def clear_session(self, session_id: str) -> None:
        """Clears in-memory state for a session."""
        self.conversation.clear_session(session_id)

    def _build_reasoning_prompt(
        self,
        *,
        query: str,
        user_profile: UserPersona,
        request_context: RequestContext,
        refined_preferences: dict[str, float],
        review_count: int,
        is_warm: bool,
        chroma_user: dict | None,
    ) -> list[str]:
        """Builds a transparent pre-retrieval reasoning chain for the response."""
        explicit_preferences = user_profile.preferences if isinstance(user_profile.preferences, dict) else {}
        preferred_categories = self._preferred_categories_from_chroma(chroma_user)
        return [
            f"Think: interpret the query as '{query}' with target category '{request_context.category or 'unspecified'}'.",
            f"Think: user has {review_count} stored interactions, treated as {'warm' if is_warm else 'cold start'}.",
            f"Plan: explicit persona preferences are {explicit_preferences or 'not provided'} and conversation refinements are {refined_preferences or 'none yet'}.",
            f"Plan: constraints considered before retrieval are {request_context.constraints or ['none']} and attributes {request_context.item_attributes or 'not provided'}.",
            f"Plan: top categories from history are {preferred_categories or ['unknown']}.",
        ]

    def _plan_strategy(
        self,
        *,
        is_warm: bool,
        request_context: RequestContext,
        enable_cross_domain: bool,
        source_platform: str,
    ) -> StrategyPlan:
        """Selects collaborative, content, cold-start, or hybrid retrieval strategy."""
        if not is_warm:
            return StrategyPlan(
                strategy="cold_start_hybrid",
                notes=["Plan: try live Chroma retrieval first, then use cold-start defaults only if real candidates are sparse."],
            )
        if enable_cross_domain and request_context.target_domain and source_platform.lower() != request_context.target_domain.lower():
            return StrategyPlan(
                strategy="hybrid_cross_domain",
                notes=[f"Plan: blend warm-user retrieval with cross-domain transfer from {source_platform} into {request_context.target_domain}."],
            )
        return StrategyPlan(
            strategy="warm_history_content_hybrid",
            notes=["Plan: use Chroma user-history retrieval first, then semantic item retrieval to diversify candidates."],
        )

    async def _retrieve_candidates(
        self,
        request: RecommendRequest,
        plan: StrategyPlan,
        refined_preferences: dict[str, float],
        chroma_user: dict | None,
        is_warm: bool,
    ) -> tuple[list, list[str]]:
        """Retrieves candidates according to the selected plan and deduplicates them."""
        context = request.request_context
        category = context.category or self._infer_primary_category(request.user_persona) or ""
        target_platform = self._target_platform_for_request(request)
        preferred_categories = self._preferred_categories_from_chroma(chroma_user)
        retrieval_category = category or (preferred_categories[0] if preferred_categories else "")
        history_candidates = await self.retriever.query_by_user_history(
            user_id=request.user_persona.user_id,
            category=retrieval_category or request.query,
            top_k=max(10, request.top_k * 3),
        )
        content_attributes = dict(context.item_attributes)
        if retrieval_category:
            content_attributes.setdefault("category", retrieval_category)
        if target_platform:
            content_attributes.setdefault("platform", target_platform)
        for key, value in refined_preferences.items():
            content_attributes.setdefault(key, value)
        content_candidates = await self.retriever.query_by_content(
            item_attributes=content_attributes or {"query": request.query},
            top_k=max(10, request.top_k * 3),
        )
        if not content_candidates:
            raw_candidates = await self.retriever.retrieve_candidates(
                user_id=request.user_persona.user_id,
                category=retrieval_category,
                query_text=request.query,
                top_k=max(10, request.top_k * 3),
                platform=target_platform,
            )
            content_candidates = [
                self.retriever._candidate_to_item(candidate)
                for candidate in raw_candidates
            ]

        cross_domain_candidates = []
        cross_domain_notes: list[str] = []
        if plan.strategy == "hybrid_cross_domain" and context.target_domain:
            source_platform = (chroma_user or {}).get("metadata", {}).get("platform", request.user_persona.platform)
            logger.info("[AGENT_B] Cross-domain: %s → %s", source_platform, context.target_domain)
            source_reviews = self.vector_store.query_reviews_for_user(
                request.user_persona.user_id,
                context.target_domain,
                n_results=max(8, request.top_k * 2),
            )
            inferred_preferences = await self.cross_domain.infer_cross_domain_preferences(
                source_reviews=source_reviews,
                target_domain=context.target_domain,
            )
            cross_domain_notes.append(
                f"Think: cross-domain inference applied from {source_platform} to {context.target_domain} using {len(source_reviews)} source reviews."
            )
            cross_domain_candidates = await self.retriever.query_cross_domain(
                source_domain=source_platform,
                target_domain=context.target_domain,
                user_id=request.user_persona.user_id,
                top_k=max(8, request.top_k * 2),
            )
            for candidate in cross_domain_candidates:
                candidate.metadata["inferred_preferences"] = inferred_preferences
                candidate.similarity_score = round(
                    min(0.99, candidate.similarity_score + (sum(inferred_preferences.values()) * 0.02)),
                    4,
                )

        combined = list(chain(history_candidates, content_candidates, cross_domain_candidates))
        deduped = self._deduplicate_candidates(combined)
        retrieval_notes = [
            f"Think: retrieved {len(deduped)} real candidates from ChromaDB.",
            f"Think: top candidate is {deduped[0].title if deduped else 'none'}.",
        ]
        retrieval_notes.extend(cross_domain_notes)

        if not deduped or (not is_warm and len(deduped) < request.top_k):
            fallback_candidates = await self.cold_start.handle(
                request.user_persona,
                context,
                nigerian_mode=request.nigerian_mode,
            )
            deduped = self._deduplicate_candidates(list(chain(deduped, fallback_candidates)))
            retrieval_notes.append(
                f"Think: supplemented with {len(fallback_candidates)} cold-start candidates because real retrieval was sparse."
            )

        return deduped, retrieval_notes

    def _deduplicate_candidates(self, candidates: list) -> list:
        """Deduplicates candidates while keeping the strongest similarity score."""
        merged: dict[str, object] = {}
        for candidate in candidates:
            existing = merged.get(candidate.item_id)
            if existing is None or candidate.similarity_score > existing.similarity_score:
                merged[candidate.item_id] = candidate
        return sorted(
            merged.values(),
            key=lambda item: item.similarity_score,
            reverse=True,
        )

    def _infer_primary_category(self, user_profile: UserPersona) -> str | None:
        favorite_categories = user_profile.preferences.get("favorite_categories")
        if isinstance(favorite_categories, list) and favorite_categories:
            return str(favorite_categories[0])
        if user_profile.history:
            return user_profile.history[0].category
        return None

    async def _is_warm_user(self, user_id: str) -> bool:
        """Returns True if user has stored reviews in ChromaDB."""
        try:
            results = self.vector_store.get_by_id("users", user_id)
            if results and results.get("metadata"):
                review_count = int(results["metadata"].get("review_count", 0))
                logger.info("[AGENT_B] User %s has %d reviews in ChromaDB", user_id, review_count)
                return review_count >= 3
        except Exception as error:
            logger.warning("[AGENT_B] Could not check user warmth: %s", error)
        return False

    def _extract_review_count(self, chroma_user: dict | None) -> int:
        if not chroma_user:
            return 0
        return int((chroma_user.get("metadata") or {}).get("review_count", 0))

    def _preferred_categories_from_chroma(self, chroma_user: dict | None) -> list[str]:
        if not chroma_user:
            return []
        raw_categories = (chroma_user.get("metadata") or {}).get("preferred_categories", "")
        if isinstance(raw_categories, str):
            return [category.strip() for category in raw_categories.split(",") if category.strip()]
        if isinstance(raw_categories, list):
            return [str(category).strip() for category in raw_categories if str(category).strip()]
        return []

    def _target_platform_for_request(self, request: RecommendRequest) -> str | None:
        domain = (request.request_context.target_domain or request.request_context.category or "").lower()
        if domain in {"food", "restaurants", "restaurant"}:
            return "yelp"
        if domain in {"books", "book"}:
            return "goodreads"
        if domain in {"electronics", "product", "shopping"}:
            return "amazon"
        platform = request.user_persona.platform.lower()
        return platform if platform in {"yelp", "goodreads", "amazon"} else None

    def _format_assistant_message(self, ranked_items: list[RankedItem]) -> str:
        if not ranked_items:
            return "I could not find a strong recommendation yet, but I can refine the search with more detail."
        titles = ", ".join(item.item.title for item in ranked_items[:3])
        return f"Top recommendation set prepared: {titles}."

    def _format_chat_message(self, ranked_items: list[RankedItem]) -> str:
        if not ranked_items:
            return "I need a bit more detail to narrow this down well."
        top_pick = ranked_items[0]
        return (
            f"My leading suggestion is {top_pick.item.title} because {top_pick.explanation} "
            f"I also kept a few alternatives ready."
        )
