"""Yelp dataset processor with business joins and per-user holdout splits."""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from os import getenv
from pathlib import Path
from typing import Any, Iterator

from tqdm import tqdm

from shared.user_profile import ReviewRecord, UserProfile, build_style_fingerprint


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
        self.reviews_path = Path(getenv("YELP_REVIEWS_PATH", "data/sample/yelp_reviews_sample.json"))
        self.users_path = Path(getenv("YELP_USERS_PATH", "data/sample/yelp_users_sample.json"))
        self.business_path = Path(getenv("YELP_BUSINESS_PATH", "data/sample/yelp_business_sample.json"))

    def load_all(self) -> tuple[list[UserProfile], list[ItemRecord], list[ReviewRecord]]:
        """Compatibility wrapper for older call sites."""
        return self.process(sample_only=False)

    def process(self, sample_only: bool = False) -> tuple[list[UserProfile], list[ItemRecord], list[ReviewRecord]]:
        """Returns (users, items, reviews) with business-derived items and 80/20 user splits."""
        businesses = self._load_businesses()
        if not self.reviews_path.exists():
            print(f"Warning: Yelp reviews file not found at {self.reviews_path}")
            return [], list(businesses.values()), []

        min_reviews = 2 if sample_only else 10
        max_users = 100 if sample_only else 2000

        user_counts: Counter[str] = Counter()
        user_order: list[str] = []
        seen_users: set[str] = set()

        for record in tqdm(self._iter_jsonl(self.reviews_path), desc="[Yelp] Counting reviews"):
            user_id = str(record.get("user_id", "")).strip()
            business_id = str(record.get("business_id", "")).strip()
            if not user_id or not business_id:
                continue

            user_counts[user_id] += 1
            if user_id not in seen_users:
                seen_users.add(user_id)
                user_order.append(user_id)

        eligible = {user_id for user_id, count in user_counts.items() if count >= min_reviews}
        selected_original_ids = [user_id for user_id in user_order if user_id in eligible][:max_users]
        selected_set = set(selected_original_ids)
        selected_users = self._load_selected_users(selected_set)

        reviews_by_user: dict[str, list[ReviewRecord]] = defaultdict(list)
        all_reviews: list[ReviewRecord] = []
        referenced_item_ids: set[str] = set()

        for record in tqdm(self._iter_jsonl(self.reviews_path), desc="[Yelp] Collecting reviews"):
            original_user_id = str(record.get("user_id", "")).strip()
            business_id = str(record.get("business_id", "")).strip()
            if original_user_id not in selected_set or not business_id:
                continue

            item_id = f"yelp_{business_id}"
            user_id = f"yelp_{original_user_id}"
            business = businesses.get(item_id)
            category = business.category if business else "restaurant"
            review = ReviewRecord(
                review_id=f"yelp_{str(record.get('review_id', '')).strip() or business_id}",
                item_id=item_id,
                source="yelp",
                rating=self._safe_float(record.get("stars"), default=0.0),
                review_text=str(record.get("text", "")).strip(),
                category=category,
                created_at=str(record.get("date", "")).strip() or None,
                metadata={
                    "business_name": business.name if business else "Unknown business",
                    "user_id": user_id,
                    "original_user_id": original_user_id,
                    "business_id": business_id,
                    "user_name": selected_users.get(original_user_id, {}).get("name", "Unknown user"),
                    "user_review_count": selected_users.get(original_user_id, {}).get("review_count", 0),
                },
            )
            reviews_by_user[user_id].append(review)
            all_reviews.append(review)
            referenced_item_ids.add(item_id)

        users: list[UserProfile] = []
        filtered_reviews: list[ReviewRecord] = []
        for original_user_id in selected_original_ids:
            user_id = f"yelp_{original_user_id}"
            user_reviews = reviews_by_user.get(user_id, [])
            if len(user_reviews) < min_reviews:
                continue

            user_reviews.sort(key=lambda review: review.created_at or "")
            holdout_count = max(1, math.ceil(len(user_reviews) * 0.2))
            split_index = max(1, len(user_reviews) - holdout_count)
            train_reviews = user_reviews[:split_index]
            held_out_reviews = user_reviews[split_index:]

            fingerprint = build_style_fingerprint(train_reviews)
            preferred_categories = [
                category
                for category, _ in Counter(review.category for review in train_reviews if review.category).most_common(5)
            ]

            users.append(
                UserProfile(
                    user_id=user_id,
                    platform="yelp",
                    review_history=train_reviews,
                    held_out_reviews=held_out_reviews,
                    style_fingerprint=fingerprint,
                    preferred_categories=preferred_categories,
                    metadata={
                        "review_count": len(train_reviews),
                        "test_review_count": len(held_out_reviews),
                    },
                )
            )
            filtered_reviews.extend(user_reviews)

        items = [item for item_id, item in businesses.items() if item_id in referenced_item_ids]
        return users, items, filtered_reviews

    def _load_businesses(self) -> dict[str, ItemRecord]:
        """Loads business records from the sample file into item records."""
        businesses: dict[str, ItemRecord] = {}
        if not self.business_path.exists():
            print(f"Warning: Yelp business file not found at {self.business_path}")
            return businesses

        for record in tqdm(self._iter_jsonl(self.business_path), desc="[Yelp] Loading businesses"):
            business_id = str(record.get("business_id", "")).strip()
            if not business_id:
                continue

            categories_raw = str(record.get("categories", "")).strip()
            categories = [category.strip() for category in categories_raw.split(",") if category.strip()]
            primary_category = categories[0] if categories else "restaurant"

            item_id = f"yelp_{business_id}"
            businesses[item_id] = ItemRecord(
                item_id=item_id,
                name=str(record.get("name", "Unknown business")).strip(),
                category=primary_category,
                avg_rating=self._safe_float(record.get("stars"), default=0.0),
                review_count=self._safe_int(record.get("review_count")),
                metadata={
                    "business_id": business_id,
                    "categories": categories_raw,
                    "city": str(record.get("city", "")).strip(),
                    "state": str(record.get("state", "")).strip(),
                    "attributes": record.get("attributes", {}) or {},
                },
            )

        print(f"[Yelp] Loaded {len(businesses)} businesses")
        return businesses

    def _load_selected_users(self, selected_user_ids: set[str]) -> dict[str, dict[str, Any]]:
        """Loads only metadata for selected users from the Yelp users JSONL file."""
        if not self.users_path.exists():
            print(f"Warning: Yelp users file not found at {self.users_path}")
            return {}

        users: dict[str, dict[str, Any]] = {}
        for record in tqdm(self._iter_jsonl(self.users_path), desc="[Yelp] Loading users"):
            user_id = str(record.get("user_id", "")).strip()
            if user_id in selected_user_ids:
                users[user_id] = record
        return users

    @staticmethod
    def _iter_jsonl(file_path: Path) -> Iterator[dict[str, Any]]:
        """Streams a JSONL file line by line."""
        with file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                raw = line.strip()
                if not raw:
                    continue
                try:
                    yield json.loads(raw)
                except json.JSONDecodeError:
                    continue

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        """Converts a value to float with a fallback."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_int(value: Any) -> int:
        """Converts a value to int with a fallback."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0


if __name__ == "__main__":
    processor = YelpProcessor()
    users, items, reviews = processor.process(sample_only=True)
    print(f"Loaded {len(users)} users, {len(items)} items, {len(reviews)} reviews")
