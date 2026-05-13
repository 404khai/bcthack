"""Goodreads dataset processor with proper joins and metadata extraction."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from os import getenv
from pathlib import Path
from typing import Any, Iterable

from shared.user_profile import ReviewRecord, StyleFingerprint, UserProfile, build_style_fingerprint


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
        self.reviews_path = Path(
            getenv("GR_REVIEWS_PATH", "data/sample/goodreads_reviews_sample.json")
        )
        self.books_path = Path(
            getenv("GR_BOOKS_PATH", "data/sample/goodreads_books_sample.json")
        )

    def load_all(self) -> tuple[list[UserProfile], list[ItemRecord], list[ReviewRecord]]:
        """
        Loads all Goodreads data and returns users, items, and reviews.
        
        Returns:
            Tuple of (users, items, reviews) where:
            - users: List of UserProfile objects
            - items: List of ItemRecord objects for books
            - reviews: List of ReviewRecord objects
        """
        print(f"Loading Goodreads data from {self.reviews_path} and {self.books_path}")
        
        # Load books first to create item records
        books = self._load_books()
        print(f"Loaded {len(books)} books")
        
        # Load reviews and join with books
        users, reviews = self._load_reviews(books)
        print(f"Loaded {len(users)} users and {len(reviews)} reviews")
        
        # Build items from books
        items = self._build_items(books)
        print(f"Built {len(items)} item records")
        
        return users, items, reviews

    def _load_books(self) -> dict[str, dict[str, Any]]:
        """Loads books from the Goodreads books sample file."""
        books: dict[str, dict[str, Any]] = {}
        
        if not self.books_path.exists():
            print(f"Warning: Books file not found at {self.books_path}")
            return books
            
        with self.books_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    book = json.loads(line)
                    book_id = book.get("book_id")
                    if book_id:
                        books[book_id] = book
                except json.JSONDecodeError:
                    continue
                    
        return books

    def _load_reviews(self, books: dict[str, dict[str, Any]]) -> tuple[list[UserProfile], list[ReviewRecord]]:
        """Loads reviews and builds user profiles."""
        if not self.reviews_path.exists():
            print(f"Warning: Reviews file not found at {self.reviews_path}")
            return [], []
            
        # Group reviews by user
        user_reviews: dict[str, list[ReviewRecord]] = defaultdict(list)
        all_reviews: list[ReviewRecord] = []
        
        with self.reviews_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                    
                try:
                    review_data = json.loads(line)
                    user_id = review_data.get("user_id")
                    book_id = review_data.get("book_id")
                    review_id = review_data.get("review_id")
                    
                    if not user_id or not book_id or not review_id:
                        continue
                        
                    # Get book metadata
                    book = books.get(book_id, {})
                    
                    # Extract author information
                    authors = book.get("authors", [])
                    author_id = authors[0].get("author_id") if authors else "unknown"
                    
                    # Extract top 3 genres by count
                    genres_data = book.get("genres", [])
                    # Sort genres by count (convert to int, handle empty strings)
                    sorted_genres = sorted(
                        genres_data,
                        key=lambda g: int(g.get("count", 0)) if g.get("count", "").isdigit() else 0,
                        reverse=True
                    )
                    top_genres = [g.get("name", "") for g in sorted_genres[:3] if g.get("name")]
                    
                    # Create review record
                    review_record = ReviewRecord(
                        review_id=review_id,
                        item_id=book_id,
                        source="goodreads",
                        rating=float(review_data.get("rating", 0)),
                        review_text=review_data.get("review_text", ""),
                        category="books",
                        created_at=review_data.get("date_added"),
                        metadata={
                            "title": book.get("title", "Unknown Book"),
                            "author_id": author_id,
                            "genres": top_genres,
                            "language_code": book.get("language_code", ""),
                            "average_rating": book.get("average_rating", "0.0"),
                        }
                    )
                    
                    user_reviews[user_id].append(review_record)
                    all_reviews.append(review_record)
                    
                except (json.JSONDecodeError, ValueError, KeyError) as e:
                    continue
                    
        # Build user profiles
        users: list[UserProfile] = []
        for user_id, reviews in user_reviews.items():
            if len(reviews) < 2:  # Need at least 2 reviews to build fingerprint
                continue
                
            # Sort reviews by date for deterministic train/test split
            reviews.sort(key=lambda r: r.created_at or "")
            
            # Apply 80/20 split per user
            split_idx = int(len(reviews) * 0.8)
            train_reviews = reviews[:split_idx]
            test_reviews = reviews[split_idx:]
            
            # Build style fingerprint from training reviews
            fingerprint = build_style_fingerprint(train_reviews)
            
            # Extract preferred categories from book genres
            preferred_categories = []
            for review in train_reviews:
                genres = review.metadata.get("genres", [])
                preferred_categories.extend(genres)
            
            # Get top 5 unique categories
            from collections import Counter
            category_counts = Counter(preferred_categories)
            top_categories = [cat for cat, _ in category_counts.most_common(5)]
            
            # Create user profile
            user_profile = UserProfile(
                user_id=user_id,
                platform="goodreads",
                review_history=train_reviews,
                style_fingerprint=fingerprint,
                preferred_categories=top_categories,
                held_out_reviews=test_reviews,
                metadata={
                    "review_count": len(train_reviews),
                    "test_review_count": len(test_reviews),
                }
            )
            
            users.append(user_profile)
            
        return users, all_reviews

    def _build_items(self, books: dict[str, dict[str, Any]]) -> list[ItemRecord]:
        """Builds ItemRecord objects from book data."""
        items: list[ItemRecord] = []
        
        for book_id, book in books.items():
            # Extract author information
            authors = book.get("authors", [])
            author_id = authors[0].get("author_id") if authors else "unknown"
            
            # Extract top 3 genres by count
            genres_data = book.get("genres", [])
            sorted_genres = sorted(
                genres_data,
                key=lambda g: int(g.get("count", 0)) if g.get("count", "").isdigit() else 0,
                reverse=True
            )
            top_genres = [g.get("name", "") for g in sorted_genres[:3] if g.get("name")]
            
            # Use the first genre as category, or "books" as fallback
            category = top_genres[0] if top_genres else "books"
            
            # Parse average rating
            avg_rating_str = book.get("average_rating", "0.0")
            try:
                avg_rating = float(avg_rating_str)
            except ValueError:
                avg_rating = 0.0
                
            # Create item record
            item = ItemRecord(
                item_id=book_id,
                name=book.get("title", "Unknown Book"),
                category=category,
                avg_rating=avg_rating,
                review_count=0,  # We don't have review counts in the sample
                metadata={
                    "authors": authors,
                    "genres": top_genres,
                    "description": book.get("description", "")[:500],
                    "language_code": book.get("language_code", ""),
                    "author_id": author_id,
                }
            )
            
            items.append(item)
            
        return items

    def _read_jsonl(self, file_path: Path) -> Iterable[dict[str, Any]]:
        """Reads a JSONL file line by line."""
        with file_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue