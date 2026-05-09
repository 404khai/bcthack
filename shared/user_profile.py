
"""User profile primitives shared across ingestion and serving layers."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from statistics import mean
from typing import Any, Iterable

TOKEN_PATTERN = re.compile(r"[A-Za-z']+")
PHRASE_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "for",
    "from",
    "i",
    "in",
    "is",
    "it",
    "my",
    "of",
    "on",
    "that",
    "the",
    "this",
    "to",
    "was",
    "with",
}
POSITIVE_WORDS = {
    "amazing",
    "awesome",
    "balanced",
    "beautiful",
    "clean",
    "delicious",
    "excellent",
    "fresh",
    "friendly",
    "good",
    "great",
    "love",
    "nice",
    "perfect",
    "solid",
    "strong",
    "tasty",
    "wonderful",
}
NEGATIVE_WORDS = {
    "average",
    "bad",
    "bland",
    "cold",
    "confusing",
    "delay",
    "disappointing",
    "expensive",
    "late",
    "messy",
    "noisy",
    "poor",
    "slow",
    "thin",
    "uncomfortable",
    "weak",
    "worst",
}
FORMAL_WORDS = {
    "however",
    "overall",
    "particularly",
    "pleasant",
    "recommend",
    "service",
    "quality",
    "experience",
    "atmosphere",
    "appreciate",
    "satisfying",
}
INFORMAL_WORDS = {
    "cool",
    "guy",
    "lol",
    "nah",
    "pretty",
    "really",
    "super",
    "wow",
    "y'all",
}
NIGERIAN_TERMS = {
    "abeg",
    "buka",
    "chop",
    "danfo",
    "dey",
    "ehen",
    "jollof",
    "jumia",
    "lagos",
    "naija",
    "pepper",
    "pidgin",
    "shoprite",
    "suya",
    "wahala",
}


@dataclass(slots=True)
class ReviewRecord:
    """Represents a single historical review written by a user."""

    review_id: str
    item_id: str
    source: str
    rating: float
    review_text: str
    category: str
    created_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """Returns the review body using the naming expected by Task A schemas."""
        return self.review_text


@dataclass(slots=True)
class StyleFingerprint:
    """Summarizes a user's writing style and rating behavior."""

    avg_rating: float
    rating_std: float
    avg_review_length: float
    vocabulary_size: int
    top_phrases: list[str]
    sentiment_profile: dict[str, float]
    formality_score: float
    nigerian_signals: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Serializes the fingerprint into JSON-friendly primitives."""
        return asdict(self)


@dataclass(slots=True)
class UserProfile:
    """Represents a user persona enriched with a derived style fingerprint."""

    user_id: str
    platform: str
    review_history: list[ReviewRecord]
    style_fingerprint: StyleFingerprint
    preferred_categories: list[str] = field(default_factory=list)
    held_out_reviews: list[ReviewRecord] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def source(self) -> str:
        """Compatibility alias for older code paths that used `source`."""
        return self.platform

    @property
    def reviews(self) -> list[ReviewRecord]:
        """Compatibility alias for older code paths that used `reviews`."""
        return self.review_history

    @property
    def average_rating(self) -> float:
        """Returns the average rating captured by the style fingerprint."""
        return self.style_fingerprint.avg_rating

    def to_document(self) -> str:
        """Builds a searchable document summary for vector storage."""
        categories = ", ".join(self.preferred_categories) or "mixed interests"
        sentiment = ", ".join(
            f"{key}={value:.2f}" for key, value in self.style_fingerprint.sentiment_profile.items()
        )
        phrases = ", ".join(self.style_fingerprint.top_phrases[:5]) or "no dominant phrases"
        return (
            f"User {self.user_id} on {self.platform} prefers {categories}. "
            f"Average rating {self.style_fingerprint.avg_rating:.2f} with rating deviation "
            f"{self.style_fingerprint.rating_std:.2f}. "
            f"Average review length {self.style_fingerprint.avg_review_length:.1f} words, "
            f"vocabulary size {self.style_fingerprint.vocabulary_size}, "
            f"formality {self.style_fingerprint.formality_score:.2f}. "
            f"Top phrases: {phrases}. Sentiment profile: {sentiment}."
        )

    def to_metadata(self) -> dict[str, Any]:
        """Builds flat metadata suitable for ChromaDB persistence."""
        return {
            "user_id": self.user_id,
            "platform": self.platform,
            "review_count": len(self.review_history),
            "held_out_count": len(self.held_out_reviews),
            "preferred_categories": ", ".join(self.preferred_categories),
            "avg_rating": self.style_fingerprint.avg_rating,
            "rating_std": self.style_fingerprint.rating_std,
            "avg_review_length": self.style_fingerprint.avg_review_length,
            "vocabulary_size": self.style_fingerprint.vocabulary_size,
            "formality_score": self.style_fingerprint.formality_score,
            "nigerian_signals": ", ".join(self.style_fingerprint.nigerian_signals),
            **self.metadata,
        }


def build_style_fingerprint(review_history: Iterable[ReviewRecord]) -> StyleFingerprint:
    """Derives a `StyleFingerprint` from a collection of historical reviews."""
    reviews = [review for review in review_history if review.review_text.strip()]
    if not reviews:
        return StyleFingerprint(
            avg_rating=3.5,
            rating_std=0.0,
            avg_review_length=60.0,
            vocabulary_size=0,
            top_phrases=[],
            sentiment_profile={"positive": 0.34, "neutral": 0.33, "negative": 0.33},
            formality_score=0.5,
            nigerian_signals=[],
        )

    ratings = [review.rating for review in reviews]
    lengths = [len(_tokenize(review.review_text)) for review in reviews]
    token_lists = [_tokenize(review.review_text) for review in reviews]
    vocabulary = {token for tokens in token_lists for token in tokens}
    phrase_counts = _extract_top_phrases(token_lists)
    sentiment_counts = Counter(_classify_sentiment(tokens) for tokens in token_lists)
    nigerian_signals = sorted({signal for tokens in token_lists for signal in _detect_nigerian_signals(tokens)})
    formality_values = [_estimate_formality(tokens) for tokens in token_lists]
    total = len(reviews)

    return StyleFingerprint(
        avg_rating=round(mean(ratings), 3),
        rating_std=round(_std_dev(ratings), 3),
        avg_review_length=round(mean(lengths), 2),
        vocabulary_size=len(vocabulary),
        top_phrases=[phrase for phrase, _ in phrase_counts.most_common(8)],
        sentiment_profile={
            "positive": round(sentiment_counts.get("positive", 0) / total, 3),
            "neutral": round(sentiment_counts.get("neutral", 0) / total, 3),
            "negative": round(sentiment_counts.get("negative", 0) / total, 3),
        },
        formality_score=round(mean(formality_values), 3),
        nigerian_signals=nigerian_signals,
    )


class UserProfileBuilder:
    """Builds `UserProfile` instances from normalized review records."""

    def __init__(self, holdout_ratio: float = 0.2, min_reviews: int = 3) -> None:
        self.holdout_ratio = holdout_ratio
        self.min_reviews = min_reviews

    def build(
        self,
        user_id: str,
        source: str,
        reviews: Iterable[ReviewRecord],
        metadata: dict[str, Any] | None = None,
    ) -> UserProfile | None:
        """Builds a user profile and reserves a held-out slice for evaluation."""
        review_list = list(reviews)
        if len(review_list) < self.min_reviews:
            return None

        split_index = max(1, int(len(review_list) * (1 - self.holdout_ratio)))
        train_reviews = review_list[:split_index]
        held_out_reviews = review_list[split_index:]
        preferred_categories = self._top_categories(train_reviews)
        fingerprint = build_style_fingerprint(train_reviews)

        return UserProfile(
            user_id=user_id,
            platform=source,
            review_history=train_reviews,
            style_fingerprint=fingerprint,
            preferred_categories=preferred_categories,
            held_out_reviews=held_out_reviews,
            metadata=metadata or {},
        )

    def _top_categories(self, reviews: list[ReviewRecord], limit: int = 5) -> list[str]:
        counts: Counter[str] = Counter(review.category for review in reviews)
        return [category for category, _ in counts.most_common(limit)]


def _tokenize(text: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]


def _extract_top_phrases(token_lists: list[list[str]]) -> Counter[str]:
    phrases: Counter[str] = Counter()
    for tokens in token_lists:
        for size in (2, 3):
            for index in range(len(tokens) - size + 1):
                phrase_tokens = tokens[index : index + size]
                if phrase_tokens[0] in PHRASE_STOPWORDS or phrase_tokens[-1] in PHRASE_STOPWORDS:
                    continue
                phrase = " ".join(phrase_tokens)
                phrases[phrase] += 1
    return phrases


def _classify_sentiment(tokens: list[str]) -> str:
    positive_hits = sum(token in POSITIVE_WORDS for token in tokens)
    negative_hits = sum(token in NEGATIVE_WORDS for token in tokens)
    if positive_hits > negative_hits:
        return "positive"
    if negative_hits > positive_hits:
        return "negative"
    return "neutral"


def _estimate_formality(tokens: list[str]) -> float:
    if not tokens:
        return 0.5
    formal_hits = sum(token in FORMAL_WORDS for token in tokens)
    informal_hits = sum(token in INFORMAL_WORDS for token in tokens)
    contractions = sum("'" in token for token in tokens)
    raw_score = 0.5 + ((formal_hits - informal_hits - contractions) / max(4, len(tokens)))
    return max(0.0, min(1.0, raw_score))


def _detect_nigerian_signals(tokens: list[str]) -> set[str]:
    return {token for token in tokens if token in NIGERIAN_TERMS}


def _std_dev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = mean(values)
    variance = sum((value - avg) ** 2 for value in values) / len(values)
    return math.sqrt(variance)
