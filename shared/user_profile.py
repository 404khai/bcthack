"""User profile primitives shared across ingestion and serving layers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from statistics import mean
from typing import Any, Iterable


@dataclass(slots=True)
class ReviewRecord:
    review_id: str
    item_id: str
    source: str
    rating: float
    review_text: str
    category: str
    created_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class UserProfile:
    user_id: str
    source: str
    reviews: list[ReviewRecord]
    preferred_categories: list[str]
    average_rating: float
    style_fingerprint: dict[str, Any]
    held_out_reviews: list[ReviewRecord] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_document(self) -> str:
        categories = ", ".join(self.preferred_categories) or "mixed interests"
        style_summary = ", ".join(
            f"{key}={value}" for key, value in self.style_fingerprint.items()
        )
        return (
            f"User {self.user_id} from {self.source} prefers {categories}. "
            f"Average rating: {self.average_rating:.2f}. Style: {style_summary}."
        )

    def to_metadata(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["review_count"] = len(self.reviews)
        payload["held_out_count"] = len(self.held_out_reviews)
        payload["preferred_categories"] = ", ".join(self.preferred_categories)
        payload["style_fingerprint"] = str(self.style_fingerprint)
        payload["reviews"] = [review.review_id for review in self.reviews]
        payload["held_out_reviews"] = [review.review_id for review in self.held_out_reviews]
        return payload


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
        review_list = list(reviews)
        if len(review_list) < self.min_reviews:
            return None

        split_index = max(1, int(len(review_list) * (1 - self.holdout_ratio)))
        train_reviews = review_list[:split_index]
        held_out_reviews = review_list[split_index:]
        categories = self._top_categories(train_reviews)
        style_fingerprint = self._style_fingerprint(train_reviews)
        average_rating = mean(review.rating for review in train_reviews)

        return UserProfile(
            user_id=user_id,
            source=source,
            reviews=train_reviews,
            preferred_categories=categories,
            average_rating=average_rating,
            style_fingerprint=style_fingerprint,
            held_out_reviews=held_out_reviews,
            metadata=metadata or {},
        )

    def _top_categories(self, reviews: list[ReviewRecord], limit: int = 5) -> list[str]:
        counts: dict[str, int] = {}
        for review in reviews:
            counts[review.category] = counts.get(review.category, 0) + 1
        return [
            category
            for category, _ in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:limit]
        ]

    def _style_fingerprint(self, reviews: list[ReviewRecord]) -> dict[str, Any]:
        lengths = [len(review.review_text.split()) for review in reviews if review.review_text]
        exclamation_count = sum(review.review_text.count("!") for review in reviews)
        return {
            "avg_words": round(mean(lengths), 2) if lengths else 0.0,
            "avg_rating": round(mean(review.rating for review in reviews), 2),
            "uses_exclamations": exclamation_count > 0,
            "total_reviews": len(reviews),
        }
