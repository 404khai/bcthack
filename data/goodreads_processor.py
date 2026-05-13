"""Goodreads dataset processor with book-derived items and per-user holdouts."""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from os import getenv
from pathlib import Path
from typing import Any, Iterator

from tqdm import tqdm

from shared.user_profile import ReviewRecord, UserProfile, build_style_fingerprint


@dataclass(slots=True)
class ItemRecord:
    """Represents a book/item from Goodreads."""

    item_id: str
    name: str
    category: str
    avg_rating: float
    review_count: int
    metadata: dict[str, Any]


class GoodreadsProcessor:
    """Processes Goodreads sample files into user profiles, items, and reviews."""

    def __init__(self) -> None:
        self.reviews_path = Path(getenv("GR_REVIEWS_PATH", "data/sample/goodreads_reviews_sample.json"))
        self.books_path = Path(getenv("GR_BOOKS_PATH", "data/sample/goodreads_books_sample.json"))

    def load_all(self) -> tuple[list[UserProfile], list[ItemRecord], list[ReviewRecord]]:
        """Compatibility wrapper for older call sites."""
        return self.process(sample_only=False)

    def process(self, sample_only: bool = False) -> tuple[list[UserProfile], list[ItemRecord], list[ReviewRecord]]:
        """Returns (users, items, reviews) with book-derived item records."""
        books = self._load_books()
        if not self.reviews_path.exists():
            print(f"Warning: Reviews file not found at {self.reviews_path}")
            return [], list(books.values()), []

        min_reviews = 2 if sample_only else 10
        max_users = 100 if sample_only else 2000

        user_counts: Counter[str] = Counter()
        user_order: list[str] = []
        seen_users: set[str] = set()

        for record in tqdm(self._iter_jsonl(self.reviews_path), desc="[Goodreads] Counting reviews"):
            user_id = str(record.get("user_id", "")).strip()
            book_id = str(record.get("book_id", "")).strip()
            if not user_id or not book_id:
                continue

            user_counts[user_id] += 1
            if user_id not in seen_users:
                seen_users.add(user_id)
                user_order.append(user_id)

        eligible = {user_id for user_id, count in user_counts.items() if count >= min_reviews}
        selected_original_ids = [user_id for user_id in user_order if user_id in eligible][:max_users]
        selected_set = set(selected_original_ids)

        reviews_by_user: dict[str, list[tuple[float, ReviewRecord]]] = defaultdict(list)
        all_reviews: list[ReviewRecord] = []
        book_review_counts: Counter[str] = Counter()

        for record in tqdm(self._iter_jsonl(self.reviews_path), desc="[Goodreads] Collecting reviews"):
            original_user_id = str(record.get("user_id", "")).strip()
            book_id = str(record.get("book_id", "")).strip()
            review_id = str(record.get("review_id", "")).strip()
            if original_user_id not in selected_set or not book_id or not review_id:
                continue

            item_id = f"goodreads_{book_id}"
            user_id = f"goodreads_{original_user_id}"
            book = books.get(item_id)
            category = book.category if book else "books"
            genre_names = book.metadata.get("genres", []) if book else []
            sort_key = self._sort_timestamp(record.get("date_updated") or record.get("date_added"))

            review = ReviewRecord(
                review_id=f"goodreads_{review_id}",
                item_id=item_id,
                source="goodreads",
                rating=self._safe_float(record.get("rating"), default=0.0),
                review_text=str(record.get("review_text", "")).strip(),
                category=category,
                created_at=str(record.get("date_added", "")).strip() or None,
                metadata={
                    "user_id": user_id,
                    "original_user_id": original_user_id,
                    "book_id": book_id,
                    "title": book.name if book else "Unknown Book",
                    "genres": genre_names,
                    "author_id": book.metadata.get("author_id", "unknown") if book else "unknown",
                },
            )

            reviews_by_user[user_id].append((sort_key, review))
            all_reviews.append(review)
            book_review_counts[item_id] += 1

        users: list[UserProfile] = []
        filtered_reviews: list[ReviewRecord] = []
        for original_user_id in selected_original_ids:
            user_id = f"goodreads_{original_user_id}"
            timed_reviews = reviews_by_user.get(user_id, [])
            if len(timed_reviews) < min_reviews:
                continue

            sorted_reviews = [review for _, review in sorted(timed_reviews, key=lambda pair: pair[0])]
            holdout_count = max(1, math.ceil(len(sorted_reviews) * 0.2))
            split_index = max(1, len(sorted_reviews) - holdout_count)
            train_reviews = sorted_reviews[:split_index]
            held_out_reviews = sorted_reviews[split_index:]

            fingerprint = build_style_fingerprint(train_reviews)
            preferred_categories = [
                category
                for category, _ in Counter(
                    genre
                    for review in train_reviews
                    for genre in review.metadata.get("genres", [])
                    if genre
                ).most_common(5)
            ]

            users.append(
                UserProfile(
                    user_id=user_id,
                    platform="goodreads",
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
            filtered_reviews.extend(sorted_reviews)

        items = [
            item
            for item_id, item in books.items()
            if book_review_counts.get(item_id, 0) > 0
        ]
        for item in items:
            item.review_count = book_review_counts.get(item.item_id, 0)

        return users, items, filtered_reviews

    def _load_books(self) -> dict[str, ItemRecord]:
        """Loads books from the Goodreads sample into item records."""
        books: dict[str, ItemRecord] = {}
        if not self.books_path.exists():
            print(f"Warning: Books file not found at {self.books_path}")
            return books

        for record in tqdm(self._iter_jsonl(self.books_path), desc="[Goodreads] Loading books"):
            book_id = str(record.get("book_id", "")).strip()
            if not book_id:
                continue

            authors = record.get("authors", []) or []
            author_id = authors[0].get("author_id", "unknown") if authors else "unknown"
            shelves = record.get("popular_shelves", []) or []
            genres = self._extract_genres(record)
            category = ""
            if shelves and isinstance(shelves[0], dict):
                category = str(shelves[0].get("name", "")).strip()
            if not category:
                category = genres[0] if genres else "books"

            item_id = f"goodreads_{book_id}"
            books[item_id] = ItemRecord(
                item_id=item_id,
                name=str(record.get("title", "Unknown Book")).strip(),
                category=category,
                avg_rating=self._safe_float(record.get("average_rating"), default=0.0),
                review_count=0,
                metadata={
                    "book_id": book_id,
                    "author_id": author_id,
                    "authors": authors,
                    "genres": genres,
                    "description": str(record.get("description", ""))[:500],
                    "language_code": str(record.get("language_code", "")).strip(),
                },
            )

        print(f"[Goodreads] Loaded {len(books)} books")
        return books

    @staticmethod
    def _extract_genres(record: dict[str, Any]) -> list[str]:
        """Extracts ordered genre-like labels from Goodreads book metadata."""
        genres = record.get("genres", []) or []
        if genres:
            sorted_genres = sorted(
                genres,
                key=lambda genre: GoodreadsProcessor._safe_int(genre.get("count")),
                reverse=True,
            )
            return [str(genre.get("name", "")).strip() for genre in sorted_genres if str(genre.get("name", "")).strip()]

        shelves = record.get("popular_shelves", []) or []
        return [
            str(shelf.get("name", "")).strip()
            for shelf in shelves
            if isinstance(shelf, dict) and str(shelf.get("name", "")).strip()
        ]

    @staticmethod
    def _iter_jsonl(file_path: Path) -> Iterator[dict[str, Any]]:
        """Reads a JSONL file line by line."""
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

    @staticmethod
    def _sort_timestamp(value: Any) -> float:
        """Parses Goodreads timestamps into sortable numeric values."""
        text = str(value or "").strip()
        if not text:
            return 0.0
        for fmt in ("%a %b %d %H:%M:%S %z %Y", "%a %b %d %H:%M:%S %Y"):
            try:
                return datetime.strptime(text, fmt).timestamp()
            except ValueError:
                continue
        return 0.0
