
"""Review generation logic for the Task A user modeling agent."""

from __future__ import annotations

from os import getenv
from typing import Any

from shared.llm_client import AnthropicLLMClient
from shared.nigerian_adapter import NigerianContextAdapter
from shared.user_profile import StyleFingerprint, UserProfile
from shared.vector_store import VectorStore
from task_a.schemas import ItemDetails

CLAUDE_MODEL_NAME = "claude-sonnet-4-20250514"
SYSTEM_PROMPT_TEMPLATE = """You are simulating a real user's review style for a recommendation hackathon benchmark.

Match the user's style fingerprint closely:
- Average review length target: {min_words}-{max_words} words
- Formality score target: {formality_score}
- Sentiment distribution: {sentiment_distribution}
- Vocabulary size target: approximately {vocabulary_size} unique tokens across their corpus
- Common phrases to echo naturally when appropriate: {top_phrases}
- Nigerian signals seen historically: {nigerian_signals}

Instructions:
1. Write a single review in first-person if the examples suggest it.
2. Match the user's tone, sentence length, and lexical richness.
3. Reflect the user's historical sentiment balance instead of writing generic praise.
4. Mention item attributes only when they sound natural in a user review.
5. If Nigerian mode is enabled, use Nigerian expressions or local references naturally and sparingly.
6. Do not mention that you are an AI or that you were given style instructions.
7. Output review text only.
"""
USER_PROMPT_TEMPLATE = """User profile summary:
- User ID: {user_id}
- Platform: {platform}
- Preferred categories: {preferred_categories}

Target item:
- Item ID: {item_id}
- Name: {item_name}
- Category: {item_category}
- Attributes: {item_attributes}

Few-shot context from similar reviews:
{example_reviews}

Write a realistic user review for the target item.
"""
FALLBACK_REVIEW_TEMPLATE = (
    "I tried {item_name} in the {item_category} category and found it {tone}. "
    "{attribute_sentence} {phrase_sentence}{sentiment_sentence}"
)


class ReviewGenerator:
    """Generates persona-aligned review text using Claude with deterministic fallback."""

    def __init__(
        self,
        vector_store: VectorStore | None = None,
        llm_client: AnthropicLLMClient | None = None,
    ) -> None:
        self.vector_store = vector_store or VectorStore()
        self._llm_client = llm_client

    async def generate(
        self,
        user_profile: UserProfile,
        item_details: ItemDetails,
        *,
        nigerian_mode: bool = False,
    ) -> str:
        """Generates a review that mirrors the user's historical writing style."""
        style = user_profile.style_fingerprint
        example_reviews = await self.retrieve_example_reviews(user_profile, item_details.category)
        client = self._get_llm_client()
        if client is not None:
            system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
                min_words=max(20, int(style.avg_review_length * 0.8)),
                max_words=max(30, int(style.avg_review_length * 1.2)),
                formality_score=f"{style.formality_score:.2f}",
                sentiment_distribution=style.sentiment_profile,
                vocabulary_size=style.vocabulary_size,
                top_phrases=", ".join(style.top_phrases[:6]) or "none",
                nigerian_signals=", ".join(style.nigerian_signals) or "none",
            )
            user_prompt = USER_PROMPT_TEMPLATE.format(
                user_id=user_profile.user_id,
                platform=user_profile.platform,
                preferred_categories=", ".join(user_profile.preferred_categories) or "unknown",
                item_id=item_details.item_id,
                item_name=item_details.name,
                item_category=item_details.category,
                item_attributes=item_details.attributes,
                example_reviews="\n".join(f"- {review}" for review in example_reviews) or "- No examples available",
            )
            try:
                review_text = await client.generate_text(
                    system_prompt=system_prompt,
                    user_prompt=user_prompt,
                    max_tokens=500,
                    temperature=0.55,
                )
                return self._adapt_output(review_text, nigerian_mode)
            except Exception:
                pass
        return self._fallback_review(style, item_details, example_reviews, nigerian_mode)

    async def retrieve_example_reviews(
        self,
        user_profile: UserProfile,
        item_category: str,
        limit: int = 5,
    ) -> list[str]:
        """Retrieves similar historical reviews from ChromaDB for few-shot grounding."""
        try:
            results = self.vector_store.query(
                collection_name="reviews",
                query_texts=[item_category],
                n_results=max(3, min(limit, 5)),
                where={"user_id": user_profile.user_id},
            )
        except Exception:
            return [review.review_text for review in user_profile.review_history[:3]]

        documents = results.get("documents", [[]])
        if not documents or not documents[0]:
            return [review.review_text for review in user_profile.review_history[:3]]
        return [str(document) for document in documents[0][:limit]]

    def _get_llm_client(self) -> AnthropicLLMClient | None:
        if self._llm_client is not None:
            return self._llm_client
        if not getenv("ANTHROPIC_API_KEY"):
            return None
        self._llm_client = AnthropicLLMClient(model=CLAUDE_MODEL_NAME)
        return self._llm_client

    def _fallback_review(
        self,
        style: StyleFingerprint,
        item_details: ItemDetails,
        example_reviews: list[str],
        nigerian_mode: bool,
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
        return self._adapt_output(review, nigerian_mode)

    def _resolve_tone(self, style: StyleFingerprint) -> str:
        if style.sentiment_profile.get("positive", 0.0) >= 0.5:
            return "genuinely satisfying"
        if style.sentiment_profile.get("negative", 0.0) >= 0.4:
            return "a bit inconsistent"
        return "fairly balanced"

    def _format_attributes(self, attributes: dict[str, Any]) -> str:
        if not attributes:
            return "I focused mostly on the overall experience."
        pairs = [f"{key}={value}" for key, value in list(attributes.items())[:4]]
        return f"What stood out most was {', '.join(pairs)}."

    def _resolve_sentiment_sentence(self, style: StyleFingerprint, example_reviews: list[str]) -> str:
        if style.sentiment_profile.get("negative", 0.0) > style.sentiment_profile.get("positive", 0.0):
            return "Even with some good parts, I still noticed a few rough edges."
        if example_reviews:
            return "It lines up with the kind of practical detail I usually include in my reviews."
        return "It matches the kind of measured reaction I tend to have."

    def _adapt_output(self, review_text: str, nigerian_mode: bool) -> str:
        adapter = NigerianContextAdapter(enabled=nigerian_mode)
        return adapter.adapt_text(review_text.strip())
