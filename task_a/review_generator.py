
"""Review generation logic for the Task A user modeling agent."""

from __future__ import annotations

import logging
from os import getenv
from typing import Any

from shared.llm_client import GeminiLLMClient
from shared.nigerian_adapter import NigerianContextAdapter
from shared.prompts import TASK_A_REVIEW_SYSTEM, TASK_A_REVIEW_USER
from shared.user_profile import StyleFingerprint, UserProfile
from shared.vector_store import VectorStore
from task_a.schemas import ItemDetails

logger = logging.getLogger(__name__)
FALLBACK_REVIEW_TEMPLATE = (
    "I tried {item_name} in the {item_category} category and found it {tone}. "
    "{attribute_sentence} {phrase_sentence}{sentiment_sentence}"
)


class ReviewGenerator:
    """Generates persona-aligned review text using Claude with deterministic fallback."""

    def __init__(
        self,
        vector_store: VectorStore | None = None,
        llm_client: GeminiLLMClient | None = None,
    ) -> None:
        self.vector_store = vector_store or VectorStore()
        self._llm_client = llm_client

    async def generate(
        self,
        user_profile: UserProfile,
        item_details: ItemDetails,
        *,
        nigerian_mode: bool = False,
        nigerian_intensity: str = "medium",
    ) -> str:
        """Generates a review that mirrors the user's historical writing style."""
        style = user_profile.style_fingerprint
        example_reviews = await self.retrieve_example_reviews(user_profile, item_details.category)
        logger.info("[GENERATOR] Few-shot examples count: %s", len(example_reviews))
        formatted_examples = self._format_examples(example_reviews)
        client = self._get_llm_client()
        if client is not None:
            logger.info("[GENERATOR] Using LLM path")
            system_prompt = TASK_A_REVIEW_SYSTEM.format(
                avg_rating=f"{style.avg_rating:.2f}",
                rating_std=f"{style.rating_std:.2f}",
                min_words=max(20, int(style.avg_review_length * 0.8)),
                max_words=max(30, int(style.avg_review_length * 1.2)),
                formality_score=f"{style.formality_score:.2f}",
                sentiment_distribution=style.sentiment_profile,
                vocabulary_size=style.vocabulary_size,
                top_phrases=", ".join(style.top_phrases[:6]) or "none",
                nigerian_signals=", ".join(style.nigerian_signals) or "none",
                preferred_categories=", ".join(user_profile.preferred_categories) or "unknown",
                history_count=len(user_profile.review_history),
            )
            user_prompt = TASK_A_REVIEW_USER.format(
                user_id=user_profile.user_id,
                platform=user_profile.platform,
                preferred_categories=", ".join(user_profile.preferred_categories) or "unknown",
                item_id=item_details.item_id,
                item_name=item_details.name,
                item_category=item_details.category,
                item_attributes=self._format_attributes_for_prompt(item_details.attributes),
                example_reviews=formatted_examples,
            )
            logger.info("[GENERATOR] System prompt length: %s", len(system_prompt))
            try:
                review_text = await client.complete(
                    system=system_prompt,
                    user=user_prompt,
                    max_tokens=500,
                )
                logger.info("[GENERATOR] Raw LLM output: %s", review_text[:200])
                return await self._adapt_output(review_text, nigerian_mode, nigerian_intensity)
            except Exception as e:
                logger.error("[GENERATOR] LLM call failed: %s", e, exc_info=True)
        reason = "LLM unavailable" if client is None else "LLM call failed"
        logger.info("[GENERATOR] Using fallback path — reason: %s", reason)
        return await self._fallback_review(style, item_details, example_reviews, nigerian_mode, nigerian_intensity)

    async def retrieve_example_reviews(
        self,
        user_profile: UserProfile,
        item_category: str,
        limit: int = 5,
    ) -> list[str]:
        """Retrieves similar historical reviews from ChromaDB for few-shot grounding."""
        if user_profile.review_history:
            local_examples = [
                review.review_text.strip()
                for review in user_profile.review_history
                if review.review_text.strip()
            ]
            if local_examples:
                return local_examples[:limit]

        candidate_user_ids = self._candidate_user_ids(user_profile)
        for candidate_user_id in candidate_user_ids:
            try:
                results = self.vector_store.query(
                    collection_name="reviews",
                    query_texts=[item_category],
                    n_results=max(3, min(limit, 5)),
                    where={"user_id": candidate_user_id},
                )
            except Exception:
                continue

            documents = results.get("documents", [[]])
            if documents and documents[0]:
                return [str(document).strip() for document in documents[0][:limit] if str(document).strip()]

        return []

    def _get_llm_client(self) -> GeminiLLMClient | None:
        if self._llm_client is not None:
            return self._llm_client
        if not getenv("GEMINI_API_KEY"):
            return None
        self._llm_client = GeminiLLMClient()
        return self._llm_client

    async def _fallback_review(
        self,
        style: StyleFingerprint,
        item_details: ItemDetails,
        example_reviews: list[str],
        nigerian_mode: bool,
        nigerian_intensity: str,
    ) -> str:
        tone = self._resolve_tone(style)
        attribute_sentence = self._format_attributes(item_details.attributes)
        phrase_sentence = ""
        if style.top_phrases:
            phrase_sentence = f"I keep coming back to words like '{style.top_phrases[0]}' when describing things I enjoy. "
        sentiment_sentence = self._resolve_sentiment_sentence(style, example_reviews)
        review = FALLBACK_REVIEW_TEMPLATE.format(
            item_name=item_details.name,
            item_category=item_details.category,
            tone=tone,
            attribute_sentence=attribute_sentence,
            phrase_sentence=phrase_sentence,
            sentiment_sentence=sentiment_sentence,
        ).strip()
        return await self._adapt_output(review, nigerian_mode, nigerian_intensity)

    def _resolve_tone(self, style: StyleFingerprint) -> str:
        if style.sentiment_profile.get("positive", 0.0) >= 0.5:
            return "genuinely satisfying"
        if style.sentiment_profile.get("negative", 0.0) >= 0.4:
            return "a bit inconsistent"
        return "fairly balanced"

    def _format_attributes(self, attributes: dict[str, Any]) -> str:
        if not attributes:
            return "I focused mostly on the overall experience."
        pairs = [
            f"{key.replace('_', ' ')}: {value}"
            for key, value in list(attributes.items())[:4]
        ]
        return f"What stood out most was {', '.join(pairs)}."

    def _resolve_sentiment_sentence(self, style: StyleFingerprint, example_reviews: list[str]) -> str:
        if style.sentiment_profile.get("negative", 0.0) > style.sentiment_profile.get("positive", 0.0):
            return "Even with some good parts, I still noticed a few rough edges."
        if example_reviews:
            return "It lines up with the kind of practical detail I usually include in my reviews."
        return "It matches the kind of measured reaction I tend to have."

    async def _adapt_output(self, review_text: str, nigerian_mode: bool, nigerian_intensity: str) -> str:
        logger.info(
            "Nigerian adapter called: %s, intensity: %s",
            nigerian_mode,
            nigerian_intensity,
        )
        adapter = NigerianContextAdapter(enabled=nigerian_mode)
        return await adapter.adapt_review(review_text.strip(), intensity=nigerian_intensity)

    def _candidate_user_ids(self, user_profile: UserProfile) -> list[str]:
        """Builds possible ChromaDB user identifiers for review retrieval."""
        uid = user_profile.user_id
        platform = user_profile.platform
        candidates = [uid]

        if not uid.startswith(f"{platform}_"):
            candidates.append(f"{platform}_{uid}")

        if uid.startswith(f"{platform}_"):
            candidates.append(uid[len(platform) + 1 :])

        return candidates

    def _format_examples(self, example_reviews: list[str]) -> str:
        """Formats few-shot examples clearly for the prompt."""
        if not example_reviews:
            return "- No examples available. User may be a cold-start profile."
        return "\n".join(
            f"Example {index}:\n{review.strip()}"
            for index, review in enumerate(example_reviews[:3], start=1)
            if review.strip()
        ) or "- No examples available. User may be a cold-start profile."

    def _format_attributes_for_prompt(self, attributes: dict[str, Any]) -> str:
        """Formats item attributes as a clean description for the LLM prompt."""
        if not attributes:
            return "- No structured attributes provided."
        return "\n".join(
            f"- {key.replace('_', ' ')}: {value}"
            for key, value in attributes.items()
        )
