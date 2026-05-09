
"""Task A orchestration layer."""

from __future__ import annotations

import logging
from time import perf_counter

from shared.user_profile import ReviewRecord, UserProfile
from task_a.persona_builder import PersonaBuilder
from task_a.rating_predictor import RatingPredictor
from task_a.review_generator import ReviewGenerator
from task_a.schemas import ReviewRequest, ReviewResponse

logger = logging.getLogger(__name__)


class UserModelingAgent:
    """Coordinates persona analysis, review generation, and rating prediction."""

    def __init__(self) -> None:
        self.persona_builder = PersonaBuilder()
        self.review_generator = ReviewGenerator()
        self.rating_predictor = RatingPredictor()

    async def run(self, request: ReviewRequest) -> ReviewResponse:
        """Runs the full Task A pipeline and logs the duration of each step."""
        timings: dict[str, float] = {}

        start = perf_counter()
        review_history = self._build_review_records(request)
        style_fingerprint = self.persona_builder.build(
            request.user_persona.user_id,
            request.user_persona.review_history,
        )
        user_profile = UserProfile(
            user_id=request.user_persona.user_id,
            platform=request.user_persona.platform,
            review_history=review_history,
            style_fingerprint=style_fingerprint,
            preferred_categories=self._preferred_categories(request.user_persona),
            metadata={"preferences": request.user_persona.preferences},
        )
        timings["persona_builder"] = perf_counter() - start

        start = perf_counter()
        review_text = await self.review_generator.generate(
            user_profile,
            request.item_details,
            nigerian_mode=request.nigerian_mode,
        )
        timings["review_generator"] = perf_counter() - start

        start = perf_counter()
        rating = await self.rating_predictor.predict(user_profile, request.item_details, review_text)
        timings["rating_predictor"] = perf_counter() - start

        confidence = self._estimate_confidence(user_profile, review_text, rating)
        style_notes = self._build_style_notes(user_profile)

        logger.info(
            "Task A run complete for user_id=%s item_id=%s timings=%s",
            request.user_persona.user_id,
            request.item_details.item_id,
            {key: round(value, 4) for key, value in timings.items()},
        )

        return ReviewResponse(
            user_id=request.user_persona.user_id,
            item_id=request.item_details.item_id,
            rating=rating,
            review_text=review_text,
            confidence=confidence,
            style_notes=style_notes,
            style_fingerprint=user_profile.style_fingerprint.to_dict(),
            nigerian_mode=request.nigerian_mode,
        )

    def _build_review_records(self, request: ReviewRequest) -> list[ReviewRecord]:
        return [
            ReviewRecord(
                review_id=f"{request.user_persona.user_id}-history-{index}",
                item_id=entry.item_id,
                source=request.user_persona.platform,
                rating=entry.rating,
                review_text=entry.text,
                category=entry.category,
                created_at=entry.created_at,
                metadata=entry.attributes,
            )
            for index, entry in enumerate(request.user_persona.review_history, start=1)
        ]

    def _preferred_categories(self, persona) -> list[str]:
        categories = persona.preferences.get("favorite_categories")
        if isinstance(categories, list):
            return [str(category) for category in categories]
        if persona.review_history:
            return [entry.category for entry in persona.review_history[:5]]
        return []

    def _estimate_confidence(self, user_profile: UserProfile, review_text: str, rating: float) -> float:
        review_length = len(review_text.split())
        target_length = user_profile.style_fingerprint.avg_review_length or 60.0
        length_score = max(0.0, 1.0 - abs(review_length - target_length) / max(target_length, 20.0))
        history_score = min(1.0, len(user_profile.review_history) / 8)
        rating_alignment = 1.0 - min(1.0, abs(rating - user_profile.style_fingerprint.avg_rating) / 2.5)
        confidence = (0.45 * length_score) + (0.35 * history_score) + (0.20 * rating_alignment)
        return round(max(0.1, min(1.0, confidence)), 3)

    def _build_style_notes(self, user_profile: UserProfile) -> str:
        style = user_profile.style_fingerprint
        phrases = ", ".join(style.top_phrases[:3]) or "no repeated phrases"
        nigerian = ", ".join(style.nigerian_signals) or "none detected"
        return (
            f"Avg rating {style.avg_rating:.2f}, rating std {style.rating_std:.2f}, "
            f"avg length {style.avg_review_length:.1f} words, formality {style.formality_score:.2f}, "
            f"top phrases: {phrases}, Nigerian signals: {nigerian}."
        )
