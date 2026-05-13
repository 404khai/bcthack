"""Yelp dataset processor with proper joins and metadata extraction."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from os import getenv
from pathlib import Path
from typing import Any, Iterable

from shared.embeddings import EmbeddingService
from shared.user_profile import ReviewRecord, StyleFingerprint, UserProfile, build_style_fingerprint


@dataclass(slots=True)
class ItemRecord:
    """Represents a business/item from Yelp."""

    item_id: str
    name: str
    category: str
    avg_rating: float
    review_count: int
    metadata: dict[str, Any]


class YelpProcessor:
    """Processes Yelp sample files into user profiles, items, and reviews."""

    def __init__(self) -> None:
        self.reviews_path = Path(
            getenv("YELP_REVIEWS_PATH", "data/sample/yelp_reviews_sample.json")
        )
        self.users_path = Path(
            getenv("YELP_USERS_PATH", "data/sample/yelp_users_sample.json")
        )
        self.business_path = Path(
            getenv("YELP_BUSINESS_PATH", "data/sample/yelp_business_sample.json")
        )

    def load_all(self) -> tuple[list[UserProfile], list[ItemRecord], list[ReviewRecord]]:
        """Loads and joins Yelp data, returning users, items, and reviews."""
        businesses = self._load_businesses()
        users = self._load_users()
        reviews = self._load_reviews(businesses, users)

        user_profiles = self._build_user_profiles(reviews)
        items = list(businesses.values())
        all_reviews = [review for user_reviews in reviews.values() for review in user_reviews]

        return user_profiles, items, all_reviews

    def _load_businesses(self) -> dict[str, ItemRecord]:
        """Loads business records from the sample file."""
        businesses: dict[str, ItemRecord] = {}
        if not self.business_path.exists():
            print(f"Warning: Yelp business file not found at {self.business_path}")
            return businesses

        with self.business_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    business_id = obj.get("business_id")
                    if not business_id:
                        continue

                    categories_str = obj.get("categories", "")
                    categories = [cat.strip() for cat in categories_str.split(",")] if categories_str else []
                    primary_category = categories[0] if categories else "restaurant"

                    businesses[business_id] = ItemRecord(
                        item_id=business_id,
                        name=obj.get("name", "Unknown business"),
                        category=primary_category,
                        avg_rating=float(obj.get("stars", 3.5)),
                        review_count=int(obj.get("review_count", 0)),
                        metadata={
                            "city": obj.get("city", ""),
                            "state": obj.get("state", ""),
                            "categories": categories_str,
                            "attributes": obj.get("attributes", {}),
                        },
                    )
                except (json.JSONDecodeError, ValueError, KeyError):
                    continue
        return businesses

    def _load_users(self) -> dict[str, dict[str, Any]]:
        """Loads user metadata from the sample file."""
        users: dict[str, dict[str, Any]] = {}
        if not self.users_path.exists():
            print(f"Warning: Yelp users file not found at {self.users_path}")
            return users

        with self.users_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    user_id = obj.get("user_id")
                    if user_id:
                        users[user_id] = obj
                except json.JSONDecodeError:
                    continue
        return users

    def _load_reviews(
        self,
        businesses: dict[str, ItemRecord],
        users: dict[str, dict[str, Any]],
    ) -> dict[str, list[ReviewRecord]]:
        """Loads reviews and joins with business and user data."""
        reviews_by_user: dict[str, list[ReviewRecord]] = defaultdict(list)
        if not self.reviews_path.exists():
            print(f"Warning: Yelp reviews file not found at {self.reviews_path}")
            return reviews_by_user

        with self.reviews_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    user_id = obj.get("user_id")
                    business_id = obj.get("business_id")
                    if not user_id or not business_id:
                        continue

                    business = businesses.get(business_id)
                    category = business.category if business else "restaurant"
                    business_name = business.name if business else "Unknown business"

                    reviews_by_user[user_id].append(
                        ReviewRecord(
                            review_id=obj.get("review_id", f"yelp_{len(reviews_by_user[user_id])}"),
                            item_id=business_id,
                            source="yelp",
                            rating=float(obj.get("stars", 3.5)),
                            review_text=obj.get("text", ""),
                            category=category,
                            created_at=obj.get("date"),
                            metadata={
                                "business_name": business_name,
                                "user_name": users.get(user_id, {}).get("name", "Unknown user"),
                                "user_review_count": users.get(user_id, {}).get("review_count", 0),
                            },
                        )
                    )
                except (json.JSONDecodeError, ValueError, KeyError):
                    continue
        return reviews_by_user

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
                    platform="yelp",
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
    processor = YelpProcessor()
    users, items, reviews = processor.load_all()
    print(f"Loaded {len(users)} users, {len(items)} items, {len(reviews)} reviews")