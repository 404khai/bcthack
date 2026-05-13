"""Amazon Electronics processor with mode-aware sampling and derived items."""

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
    """Represents a product/item from Amazon."""

    item_id: str
    name: str
    category: str
    avg_rating: float
    review_count: int
    metadata: dict[str, Any]


class AmazonProcessor:
    """Processes Amazon Electronics reviews, deriving items from review history."""

    def __init__(self) -> None:
        self.reviews_path = Path(
            getenv("AMAZON_REVIEWS_PATH", "data/sample/amazon_reviews_sample.json")
        )

    def load_all(self) -> tuple[list[UserProfile], list[ItemRecord], list[ReviewRecord]]:
        """Compatibility wrapper for older call sites."""
        return self.process(sample_only=False)

    def process(self, sample_only: bool = False) -> tuple[list[UserProfile], list[ItemRecord], list[ReviewRecord]]:
        """Returns (users, items, reviews) using a two-pass JSONL scan."""
        if not self.reviews_path.exists():
            print(f"Warning: Amazon reviews file not found at {self.reviews_path}")
            return [], [], []

        min_reviews = 2 if sample_only else 5
        max_users = 100 if sample_only else 2000

        user_counts: Counter[str] = Counter()
        user_order: list[str] = []
        seen_users: set[str] = set()
        total_lines = 0
        first_three_records: list[dict[str, Any]] = []

        for record in tqdm(self._iter_jsonl(), desc="[Amazon] Counting reviews"):
            total_lines += 1
            reviewer_id = str(record.get("reviewerID", "")).strip()
            asin = str(record.get("asin", "")).strip()
            if not reviewer_id or not asin:
                continue

            if len(first_three_records) < 3:
                first_three_records.append(
                    {
                        "reviewerID": reviewer_id,
                        "asin": asin,
                        "overall": record.get("overall"),
                        "summary": record.get("summary", ""),
                    }
                )

            user_counts[reviewer_id] += 1
            if reviewer_id not in seen_users:
                seen_users.add(reviewer_id)
                user_order.append(reviewer_id)

        eligible = {reviewer_id for reviewer_id, count in user_counts.items() if count >= min_reviews}
        selected = [reviewer_id for reviewer_id in user_order if reviewer_id in eligible][:max_users]
        selected_set = set(selected)

        print(f"[Amazon] Total lines scanned: {total_lines}")
        print(f"[Amazon] Unique reviewers found: {len(user_counts)}")
        print(f"[Amazon] Reviewers with {min_reviews}+ reviews: {len(eligible)}")
        print(f"[Amazon] Selected {len(selected)} users")
        if first_three_records:
            print(f"[Amazon] First 3 parsed records: {first_three_records}")

        reviews_by_user: dict[str, list[tuple[int, ReviewRecord]]] = defaultdict(list)
        asin_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        total_collected = 0

        for record in tqdm(self._iter_jsonl(), desc="[Amazon] Collecting records"):
            reviewer_id = str(record.get("reviewerID", "")).strip()
            asin = str(record.get("asin", "")).strip()
            if reviewer_id not in selected_set or not asin:
                continue

            unix_review_time = self._safe_int(record.get("unixReviewTime"))
            summary = str(record.get("summary", "")).strip()
            review = ReviewRecord(
                review_id=f"amazon_{reviewer_id}_{asin}_{unix_review_time}",
                item_id=f"amazon_{asin}",
                source="amazon",
                rating=self._safe_float(record.get("overall"), default=0.0),
                review_text=str(record.get("reviewText", "")).strip(),
                category="Electronics",
                created_at=str(record.get("reviewTime", "")).strip() or None,
                metadata={
                    "summary": summary,
                    "reviewer_name": str(record.get("reviewerName", "")).strip(),
                    "unix_review_time": unix_review_time,
                    "user_id": f"amazon_{reviewer_id}",
                    "asin": asin,
                },
            )
            reviews_by_user[f"amazon_{reviewer_id}"].append((unix_review_time, review))
            asin_groups[asin].append(
                {
                    "summary": summary,
                    "rating": review.rating,
                }
            )
            total_collected += 1

        print(f"[Amazon] Collected {total_collected} reviews for selected users")

        users: list[UserProfile] = []
        all_reviews: list[ReviewRecord] = []
        for user_id in [f"amazon_{reviewer_id}" for reviewer_id in selected]:
            timed_reviews = reviews_by_user.get(user_id, [])
            if len(timed_reviews) < min_reviews:
                continue

            sorted_reviews = [review for _, review in sorted(timed_reviews, key=lambda pair: pair[0])]
            holdout_count = max(1, math.ceil(len(sorted_reviews) * 0.2))
            split_index = max(1, len(sorted_reviews) - holdout_count)
            train_reviews = sorted_reviews[:split_index]
            held_out_reviews = sorted_reviews[split_index:]

            fingerprint = build_style_fingerprint(train_reviews)
            users.append(
                UserProfile(
                    user_id=user_id,
                    platform="amazon",
                    review_history=train_reviews,
                    style_fingerprint=fingerprint,
                    preferred_categories=["Electronics"],
                    held_out_reviews=held_out_reviews,
                    metadata={
                        "review_count": len(train_reviews),
                        "test_review_count": len(held_out_reviews),
                    },
                )
            )
            all_reviews.extend(sorted_reviews)

        items = self._build_items(asin_groups)
        print(f"[Amazon] Derived {len(items)} unique items from {len(asin_groups)} asins")

        return users, items, all_reviews

    def _build_items(self, asin_groups: dict[str, list[dict[str, Any]]]) -> list[ItemRecord]:
        """Derives ItemRecord rows from grouped ASIN review aggregates."""
        items: list[ItemRecord] = []
        for asin, entries in asin_groups.items():
            if len(entries) < 2:
                continue

            summaries = Counter(
                entry["summary"] for entry in entries if str(entry["summary"]).strip()
            )
            most_common_summary = summaries.most_common(1)[0][0] if summaries else f"Amazon product {asin}"
            ratings = [self._safe_float(entry["rating"], default=0.0) for entry in entries]
            avg_rating = sum(ratings) / len(ratings) if ratings else 0.0

            items.append(
                ItemRecord(
                    item_id=f"amazon_{asin}",
                    name=most_common_summary,
                    category="Electronics",
                    avg_rating=round(avg_rating, 3),
                    review_count=len(entries),
                    metadata={
                        "description": f"Electronics product. Top review: {most_common_summary}",
                        "asin": asin,
                        "top_summaries": dict(summaries.most_common(5)),
                    },
                )
            )
        return items

    def _iter_jsonl(self) -> Iterator[dict[str, Any]]:
        """Streams Amazon reviews line by line without loading the file into memory."""
        with self.reviews_path.open("r", encoding="utf-8") as handle:
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
        """Converts a value to int with a zero fallback."""
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0


if __name__ == "__main__":
    processor = AmazonProcessor()
    users, items, reviews = processor.process(sample_only=True)
    print(f"Loaded {len(users)} users, {len(items)} items, {len(reviews)} reviews")
