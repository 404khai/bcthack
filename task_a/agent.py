
"""Task A orchestration layer."""

from __future__ import annotations

import logging
import re
from time import perf_counter

from shared.user_profile import ReviewRecord, StyleFingerprint, UserProfile
from shared.vector_store import VectorStore
from task_a.persona_builder import PersonaBuilder
from task_a.rating_predictor import RatingPredictor
from task_a.review_generator import ReviewGenerator
from task_a.schemas import ReviewRequest, ReviewResponse

logger = logging.getLogger(__name__)


class UserModelingAgent:
    """Coordinates persona analysis, review generation, and rating prediction."""

    def __init__(self) -> None:
        self.vector_store = VectorStore()
        self.persona_builder = PersonaBuilder()
        self.review_generator = ReviewGenerator(vector_store=self.vector_store)
        self.rating_predictor = RatingPredictor()

    async def run(self, request: ReviewRequest) -> ReviewResponse:
        """Runs the full Task A pipeline and logs the duration of each step."""
        timings: dict[str, float] = {}
        logger.info("[AGENT] Starting for user: %s", request.user_persona.user_id)

        start = perf_counter()
        chroma_user = self.vector_store.get_by_id("users", request.user_persona.user_id)
        logger.info("[AGENT] ChromaDB fetch result: %s", chroma_user)
        review_history = self._build_review_records(request)
        if chroma_user is not None:
            style_fingerprint = self._rebuild_fingerprint_from_chroma(chroma_user)
            preferred_categories = self._preferred_categories_from_metadata(
                chroma_user["metadata"],
                request,
            )
        else:
            style_fingerprint = self.persona_builder.build(
                request.user_persona.user_id,
                request.user_persona.review_history,
            )
            preferred_categories = self._preferred_categories(request.user_persona)
        logger.info("[AGENT] Style fingerprint: %s", style_fingerprint)
        user_profile = UserProfile(
            user_id=request.user_persona.user_id,
            platform=request.user_persona.platform,
            review_history=review_history,
            style_fingerprint=style_fingerprint,
            preferred_categories=preferred_categories,
            metadata=self._merged_metadata(chroma_user, request),
        )
        timings["persona_builder"] = perf_counter() - start

        start = perf_counter()
        prompt = (
            f"user_id={request.user_persona.user_id}; "
            f"platform={request.user_persona.platform}; "
            f"item={request.item_details.name}; "
            f"category={request.item_details.category}; "
            f"attrs={request.item_details.attributes}"
        )
        logger.info("[AGENT] Calling LLM with prompt length: %s", len(prompt))
        will_call_adapter = request.nigerian_mode
        logger.info(
            "[AGENT] Nigerian mode: %s, calling adapter: %s",
            request.nigerian_mode,
            will_call_adapter,
        )
        review_text = await self.review_generator.generate(
            user_profile,
            request.item_details,
            nigerian_mode=request.nigerian_mode,
            nigerian_intensity=getattr(request, "nigerian_intensity", "medium"),
        )
        logger.info(
            "[AGENT] LLM response received (%d chars): %s",
            len(review_text),
            review_text[:300],
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

    def _rebuild_fingerprint_from_chroma(self, chroma_user: dict) -> StyleFingerprint:
        metadata = chroma_user.get("metadata", {})
        document_text = chroma_user.get("document", "") or ""
        sentiment_profile = metadata.get("sentiment_profile")
        if not isinstance(sentiment_profile, dict):
            sentiment_profile = {
                "positive": float(metadata.get("sentiment_positive", 0.34)),
                "neutral": float(metadata.get("sentiment_neutral", 0.33)),
                "negative": float(metadata.get("sentiment_negative", 0.33)),
            }

        rating_std = self._parse_float_from_document(
            pattern=r"rating deviation ([\d.]+)",
            document_text=document_text,
            default=float(metadata.get("rating_std", 0.0)),
        )
        formality_score = self._parse_float_from_document(
            pattern=r"formality ([\d.]+)",
            document_text=document_text,
            default=float(metadata.get("formality_score", 0.5)),
        )

        top_phrases = self._split_metadata_list(metadata.get("top_phrases", ""))
        if not top_phrases:
            phrases_match = re.search(r"Top phrases: ([^.]+)\.", document_text)
            if phrases_match:
                top_phrases = [
                    phrase.strip()
                    for phrase in phrases_match.group(1).split(",")
                    if phrase.strip() and phrase.strip().lower() != "none"
                ]

        for key in ("positive", "neutral", "negative"):
            match = re.search(rf"{key}=([\d.]+)", document_text)
            if match:
                sentiment_profile[key] = float(match.group(1))

        fingerprint = StyleFingerprint(
            avg_rating=float(metadata.get("avg_rating", 3.5)),
            rating_std=rating_std,
            avg_review_length=float(metadata.get("avg_review_length", 60.0)),
            vocabulary_size=int(metadata.get("vocabulary_size", 0)),
            top_phrases=top_phrases,
            sentiment_profile={
                "positive": float(sentiment_profile.get("positive", 0.34)),
                "neutral": float(sentiment_profile.get("neutral", 0.33)),
                "negative": float(sentiment_profile.get("negative", 0.33)),
            },
            formality_score=formality_score,
            nigerian_signals=self._split_metadata_list(metadata.get("nigerian_signals", "")),
        )
        logger.info(
            "[AGENT] Rebuilt fingerprint from ChromaDB: avg_rating=%s, review_count=%s, vocab=%s",
            fingerprint.avg_rating,
            metadata.get("review_count"),
            fingerprint.vocabulary_size,
        )
        return fingerprint

    def _parse_float_from_document(self, pattern: str, document_text: str, default: float) -> float:
        match = re.search(pattern, document_text)
        return float(match.group(1)) if match else default

    def _preferred_categories_from_metadata(self, metadata: dict, request: ReviewRequest) -> list[str]:
        categories = self._split_metadata_list(metadata.get("preferred_categories", ""))
        if categories:
            return categories
        return self._preferred_categories(request.user_persona)

    def _merged_metadata(self, chroma_user: dict | None, request: ReviewRequest) -> dict:
        merged: dict = {"preferences": request.user_persona.preferences}
        if chroma_user is not None:
            merged.update(chroma_user.get("metadata", {}))
        return merged

    def _split_metadata_list(self, raw_value: object) -> list[str]:
        if isinstance(raw_value, list):
            return [str(item).strip() for item in raw_value if str(item).strip()]
        if isinstance(raw_value, str):
            return [part.strip() for part in raw_value.split(",") if part.strip()]
        return []

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
