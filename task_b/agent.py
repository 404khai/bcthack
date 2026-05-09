"""Task B orchestration layer."""

from __future__ import annotations

from task_b.cold_start import ColdStartHandler
from task_b.conversation import ConversationManager
from task_b.cross_domain import CrossDomainBridge
from task_b.ranker import RecommendationRanker
from task_b.retriever import Retriever
from task_b.schemas import RecommendRequest, RecommendResponse


class RecommendationAgent:
    def __init__(self) -> None:
        self.retriever = Retriever()
        self.cold_start = ColdStartHandler()
        self.cross_domain = CrossDomainBridge()
        self.conversation = ConversationManager()
        self.ranker = RecommendationRanker()

    async def recommend(self, request: RecommendRequest) -> RecommendResponse:
        history = self.conversation.load_history(request.conversation_id)
        retrieved = self.retriever.retrieve(request)
        if not retrieved:
            retrieved = self.cold_start.generate_candidates(request)
        bridged = self.cross_domain.expand_candidates(request, retrieved)
        ranked = self.ranker.rank(request, bridged)
        if request.conversation_id:
            self.conversation.save_turn(request.conversation_id, request.query)
        return RecommendResponse(
            user_id=request.user_persona.user_id,
            recommendations=ranked,
            thinking=[
                f"Loaded {len(history)} previous turns.",
                f"Considered {len(retrieved)} retrieved candidates.",
                f"Expanded to {len(bridged)} candidates after cross-domain reasoning.",
            ],
            nigerian_mode=request.nigerian_mode,
        )
