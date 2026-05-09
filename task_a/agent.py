"""Task A orchestration layer."""

from __future__ import annotations

from task_a.persona_builder import PersonaBuilder
from task_a.rating_predictor import RatingPredictor
from task_a.review_generator import ReviewGenerator
from task_a.schemas import GenerateReviewRequest, GenerateReviewResponse


class UserModelingAgent:
    def __init__(self) -> None:
        self.persona_builder = PersonaBuilder()
        self.review_generator = ReviewGenerator()
        self.rating_predictor = RatingPredictor()

    async def generate_review(self, request: GenerateReviewRequest) -> GenerateReviewResponse:
        style_fingerprint = self.persona_builder.build_style_fingerprint(request.user_persona)
        predicted_rating = self.rating_predictor.predict(request.user_persona)
        review_text = await self.review_generator.generate(
            persona=request.user_persona,
            item_name=request.item.name,
            item_description=request.item.description,
            style_fingerprint=style_fingerprint,
            fallback_rating=predicted_rating,
            nigerian_mode=request.nigerian_mode,
        )
        return GenerateReviewResponse(
            user_id=request.user_persona.user_id,
            item_id=request.item.item_id,
            rating=predicted_rating,
            review=review_text,
            style_fingerprint=style_fingerprint,
            source=request.user_persona.source,
            nigerian_mode=request.nigerian_mode,
        )
