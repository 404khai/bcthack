
"""Task B recommendation orchestration layer."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import chain

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


@dataclass(slots=True)
class StrategyPlan:
    """Captures the selected retrieval strategy and reasoning notes."""

    strategy: str
    notes: list[str]


class RecommendationAgent:
    """Implements a reasoning-first recommendation loop for Task B."""

    def __init__(self) -> None:
        self.retriever = MultiSourceRetriever()
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
        thinking = self._build_reasoning_prompt(
            query=request.query,
            user_profile=request.user_persona,
            request_context=request.request_context,
            refined_preferences=refined_preferences,
        )
        plan = self._plan_strategy(request.user_persona, request.request_context, request.enable_cross_domain)
        candidates = await self._retrieve_candidates(request, plan, refined_preferences)
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
    ) -> list[str]:
        """Builds a transparent pre-retrieval reasoning chain for the response."""
        history_depth = len(user_profile.history)
        explicit_preferences = user_profile.preferences if isinstance(user_profile.preferences, dict) else {}
        return [
            f"Think: interpret the query as '{query}' with target category '{request_context.category or 'unspecified'}'.",
            f"Think: user history contains {history_depth} prior interactions, so the request is treated as {'warm' if history_depth >= 2 else 'cold'} start.",
            f"Plan: explicit persona preferences are {explicit_preferences or 'not provided'} and conversation refinements are {refined_preferences or 'none yet'}.",
            f"Plan: constraints considered before retrieval are {request_context.constraints or ['none']} and attributes {request_context.item_attributes or 'not provided'}.",
        ]

    def _plan_strategy(
        self,
        user_profile: UserPersona,
        request_context: RequestContext,
        enable_cross_domain: bool,
    ) -> StrategyPlan:
        """Selects collaborative, content, cold-start, or hybrid retrieval strategy."""
        if self.cold_start.detect_cold_start(user_profile):
            return StrategyPlan(
                strategy="cold_start_hybrid",
                notes=["Plan: use explicit preferences, Nigerian defaults, and popularity fallback because history is sparse."],
            )
        if enable_cross_domain and request_context.target_domain:
            return StrategyPlan(
                strategy="hybrid_cross_domain",
                notes=["Plan: blend history retrieval with cross-domain transfer into the requested target domain."],
            )
        return StrategyPlan(
            strategy="warm_history_content_hybrid",
            notes=["Plan: use user-history retrieval first, then content retrieval to diversify candidates."],
        )

    async def _retrieve_candidates(
        self,
        request: RecommendRequest,
        plan: StrategyPlan,
        refined_preferences: dict[str, float],
    ) -> list:
        """Retrieves candidates according to the selected plan and deduplicates them."""
        context = request.request_context
        category = context.category or self._infer_primary_category(request.user_persona)
        if plan.strategy == "cold_start_hybrid":
            candidates = await self.cold_start.handle(request.user_persona, context)
            return self._deduplicate_candidates(candidates)

        history_candidates = await self.retriever.query_by_user_history(
            user_id=request.user_persona.user_id,
            category=category or request.query,
            top_k=max(10, request.top_k * 3),
        )
        content_attributes = dict(context.item_attributes)
        for key, value in refined_preferences.items():
            content_attributes.setdefault(key, value)
        content_candidates = await self.retriever.query_by_content(
            item_attributes=content_attributes or {"query": request.query},
            top_k=max(10, request.top_k * 3),
        )

        cross_domain_candidates = []
        if plan.strategy == "hybrid_cross_domain" and context.target_domain:
            source_reviews = [entry.text for entry in request.user_persona.history if entry.text]
            inferred_preferences = await self.cross_domain.infer_cross_domain_preferences(
                source_reviews=source_reviews,
                target_domain=context.target_domain,
            )
            cross_domain_candidates = await self.retriever.query_cross_domain(
                source_domain=request.user_persona.platform,
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
        if not combined:
            combined = await self.cold_start.handle(request.user_persona, context)
        return self._deduplicate_candidates(combined)

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
