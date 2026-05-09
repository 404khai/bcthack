
"""Rating prediction logic for Task A."""

from __future__ import annotations

import re
from os import getenv
from statistics import mean

from shared.llm_client import AnthropicLLMClient
from shared.user_profile import UserProfile
from task_a.schemas import ItemDetails

CLAUDE_MODEL_NAME = "claude-sonnet-4-20250514"
SYSTEM_PROMPT = """You are estimating the most likely star rating a user would assign to an item.

Rules:
- Consider the user's historical rating behavior first.
- Use the generated review text as evidence of sentiment strength.
- Return only a single number between 1.0 and 5.0.
"""
USER_PROMPT_TEMPLATE = """User rating history summary:
- Average rating: {avg_rating}
- Rating standard deviation: {rating_std}
- Preferred categories: {preferred_categories}

Target item:
- Name: {item_name}
- Category: {item_category}
- Attributes: {item_attributes}

Generated review:
{review_text}

What rating would this user most likely give?
"""
POSITIVE_WORDS = {
    "amazing",
    "balanced",
    "beautiful",
    "clean",
    "delicious",
    "enjoyed",
    "excellent",
    "fresh",
    "friendly",
    "good",
    "great",
    "love",
    "nice",
    "perfect",
    "satisfying",
    "solid",
    "strong",
    "tasty",
}
NEGATIVE_WORDS = {
    "average",
    "bad",
    "bland",
    "cold",
    "delay",
    "disappointing",
    "expensive",
    "late",
    "messy",
    "poor",
    "rough",
    "slow",
    "thin",
    "uncomfortable",
    "weak",
}
RATING_PATTERN = re.compile(r"([1-5](?:\.\d+)?)")


class RatingPredictor:
    """Predicts a rating using Claude with a rule-based fallback."""

    def __init__(self, llm_client: AnthropicLLMClient | None = None) -> None:
        self._llm_client = llm_client

    async def predict(
        self,
        user_profile: UserProfile,
        item_details: ItemDetails,
        review_text: str,
    ) -> float:
        """Predicts a star rating for the generated review and clamps it to [1.0, 5.0]."""
        fallback_rating = self._rule_based_fallback(user_profile, review_text)
        client = self._get_llm_client()
        if client is None:
            return fallback_rating
        user_prompt = USER_PROMPT_TEMPLATE.format(
            avg_rating=f"{user_profile.style_fingerprint.avg_rating:.2f}",
            rating_std=f"{user_profile.style_fingerprint.rating_std:.2f}",
            preferred_categories=", ".join(user_profile.preferred_categories) or "unknown",
            item_name=item_details.name,
            item_category=item_details.category,
            item_attributes=item_details.attributes,
            review_text=review_text,
        )
        try:
            response = await client.generate_text(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                max_tokens=32,
                temperature=0.1,
            )
            parsed = self._parse_rating(response)
            if parsed is None:
                return fallback_rating
            return self._clamp(parsed)
        except Exception:
            return fallback_rating

    def _get_llm_client(self) -> AnthropicLLMClient | None:
        if self._llm_client is not None:
            return self._llm_client
        if not getenv("ANTHROPIC_API_KEY"):
            return None
        self._llm_client = AnthropicLLMClient(model=CLAUDE_MODEL_NAME)
        return self._llm_client

    def _rule_based_fallback(self, user_profile: UserProfile, review_text: str) -> float:
        ratings = [review.rating for review in user_profile.review_history]
        base_rating = mean(ratings) if ratings else 3.5
        polarity = self._sentiment_polarity(review_text)
        if polarity > 0:
            base_rating += min(0.8, polarity * 0.35)
        elif polarity < 0:
            base_rating += max(-0.8, polarity * 0.45)
        return self._clamp(round(base_rating, 2))

    def _sentiment_polarity(self, review_text: str) -> float:
        tokens = [token.lower().strip(".,!?;:") for token in review_text.split()]
        positive_hits = sum(token in POSITIVE_WORDS for token in tokens)
        negative_hits = sum(token in NEGATIVE_WORDS for token in tokens)
        return positive_hits - negative_hits

    def _parse_rating(self, value: str) -> float | None:
        match = RATING_PATTERN.search(value)
        if not match:
            return None
        return float(match.group(1))

    def _clamp(self, value: float) -> float:
        return round(min(5.0, max(1.0, value)), 1)
