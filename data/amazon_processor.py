"""Amazon Electronics dataset processor with derived item records."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from os import getenv
from pathlib import Path
from typing import Any, Iterable

from shared.user_profile import ReviewRecord, StyleFingerprint, UserProfile, build_style_fingerprint


@dataclass(slots=True)
class ItemRecord:
    """Represents a product/item from Amazon."""

    item_id: str
    name: str
    category: str
    avg_rating: float
    review_count: int
    metadata: dict[str, Any]


class AmazonProcessor:
    """Processes Amazon Electronics reviews, deriving items from unique ASINs."""

    def __init__(self) -> None:
        self.reviews_path = Path(
            getenv("AMAZON_REVIEWS_PATH", "data/sample/amazon_reviews_sample.json")
        )

    def load_all(self) -> tuple[list[UserProfile], list[ItemRecord], list[ReviewRecord]]:
        """Loads Amazon data, deriving items from reviews, returning users, items, and reviews."""
        reviews_by_user, item_summaries = self._load_reviews_and_summaries()
        items = self._build_items(item_summaries)

        user_profiles = self._build_user_profiles(reviews_by_user)
        all_reviews = [review for user_reviews in reviews_by_user.values() for review in user_reviews]

        return user_profiles, items, all_reviews

    def _load_reviews_and_summaries(
        self,
    ) -> tuple[dict[str, list[ReviewRecord]], dict[str, dict[str, Any]]]:
        """Loads reviews and collects summary statistics per ASIN."""
        reviews_by_user: dict[str, list[ReviewRecord]] = defaultdict(list)
        item_summaries: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "summary_counts": Counter(),
                "ratings": [],
                "review_count": 0,
            }
        )

        if not self.reviews_path.exists():
            print(f"Warning: Amazon reviews file not found at {self.reviews_path}")
            return reviews_by_user, item_summaries

        with self.reviews_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    user_id = obj.get("reviewerID")
                    asin = obj.get("asin")
                    summary = obj.get("summary", "").strip()
                    if not user_id or not asin:
                        continue

                    review_record = ReviewRecord(
                        review_id=obj.get("review_id", f"amz_{len(reviews_by_user[user_id])}"),
                        item_id=asin,
                        source="amazon",
                        rating=float(obj.get("overall", 3.5)),
                        review_text=obj.get("reviewText", ""),
                        category="Electronics",
                        created_at=obj.get("reviewTime"),
                        metadata={
                            "summary": summary,
                            "reviewer_name": obj.get("reviewerName", ""),
                        },
                    )

                    reviews_by_user[user_id].append(review_record)

                    item_summaries[asin]["summary_counts"][summary] += 1
                    item_summaries[asin]["ratings"].append(float(obj.get("overall", 3.5)))
                    item_summaries[asin]["review_count"] += 1

                except (json.JSONDecodeError, ValueError, KeyError):
                    continue

        return reviews_by_user, item_summaries

    def _build_items(self, item_summaries: dict[str, dict[str, Any]]) -> list[ItemRecord]:
        """Builds ItemRecord objects from aggregated ASIN statistics."""
        items: list[ItemRecord] = []
        for asin, summary in item_summaries.items():
            if not summary["summary_counts"]:
                continue

            most_common_summary, count = summary["summary_counts"].most_common(1)[0]
            avg_rating = (
                sum(summary["ratings"]) / len(summary["ratings"])
                if summary["ratings"]
                else 3.5
            )

            items.append(
                ItemRecord(
                    item_id=asin,
                    name=most_common_summary or f"Amazon product {asin}",
                    category="Electronics",
                    avg_rating=round(avg_rating, 2),
                    review_count=summary["review_count"],
                    metadata={
                        "top_summaries": dict(summary["summary_counts"].most_common(5)),
                        "avg_rating": round(avg_rating, 2),
                        "rating_count": len(summary["ratings"]),
                    },
                )
            )
        return items

    def _build_user_profiles(self, reviews_by_user: dict[str, list[ReviewRecord]]) -> list[UserProfile]:
        """Builds UserProfile objects from grouped reviews."""
        profiles: list[UserProfile] = []
        for user_id, reviews in reviews_by_user.items():
            if len(reviews) < 10:
                continue

            style_fingerprint = build_style_fingerprint(reviews)
            categories = list({review.category for review in reviews if review.category})

            profiles.append(
                UserProfile(
                    user_id=user_id,
                    platform="amazon",
                    review_history=reviews,
                    style_fingerprint=style_fingerprint,
                    preferred_categories=categories[:5],
                    metadata={
                        "review_count": len(reviews),
                        "avg_rating": style_fingerprint.avg_rating,
                    },
                )
            )
        return profiles


if __name__ == "__main__":
    processor = AmazonProcessor()
    users, items, reviews = processor.load_all()
    print(f"Loaded {len(users)} users, {len(items)} items, {len(reviews)} reviews")