"""Generates test fixture JSON files for CI/unit testing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def create_yelp_fixtures() -> None:
    """Creates Yelp test fixture files."""
    output_dir = Path("data/sample/test_fixtures")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Yelp reviews sample
    reviews_data = [
        {
            "review_id": "yelp_rev_1",
            "user_id": "user_1",
            "business_id": "biz_1",
            "stars": 5.0,
            "text": "Amazing food and great service! Will definitely come back.",
            "date": "2023-01-15",
        },
        {
            "review_id": "yelp_rev_2",
            "user_id": "user_1",
            "business_id": "biz_2",
            "stars": 4.0,
            "text": "Good atmosphere but a bit pricey.",
            "date": "2023-02-20",
        },
        {
            "review_id": "yelp_rev_3",
            "user_id": "user_2",
            "business_id": "biz_1",
            "stars": 3.0,
            "text": "Average experience, nothing special.",
            "date": "2023-03-10",
        },
    ]
    
    # Yelp users sample
    users_data = [
        {
            "user_id": "user_1",
            "name": "Alice",
            "review_count": 42,
            "average_stars": 4.2,
            "elite": "2022,2023",
            "fans": 5,
        },
        {
            "user_id": "user_2",
            "name": "Bob",
            "review_count": 18,
            "average_stars": 3.8,
            "elite": "",
            "fans": 2,
        },
    ]
    
    # Yelp businesses sample
    businesses_data = [
        {
            "business_id": "biz_1",
            "name": "Joe's Diner",
            "city": "Las Vegas",
            "state": "NV",
            "stars": 4.5,
            "review_count": 120,
            "categories": "Restaurants, American, Diners",
        },
        {
            "business_id": "biz_2",
            "name": "Sushi Palace",
            "city": "Los Angeles",
            "state": "CA",
            "stars": 4.2,
            "review_count": 85,
            "categories": "Restaurants, Japanese, Sushi",
        },
    ]
    
    # Write files
    with (output_dir / "yelp_reviews_sample.json").open("w", encoding="utf-8") as f:
        for item in reviews_data:
            f.write(json.dumps(item) + "\n")
            
    with (output_dir / "yelp_users_sample.json").open("w", encoding="utf-8") as f:
        for item in users_data:
            f.write(json.dumps(item) + "\n")
            
    with (output_dir / "yelp_business_sample.json").open("w", encoding="utf-8") as f:
        for item in businesses_data:
            f.write(json.dumps(item) + "\n")
            
    print(f"Created Yelp fixtures with {len(reviews_data)} reviews, {len(users_data)} users, {len(businesses_data)} businesses")


def create_amazon_fixtures() -> None:
    """Creates Amazon test fixture files."""
    output_dir = Path("data/sample/test_fixtures")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Amazon reviews sample
    reviews_data = [
        {
            "reviewerID": "A1X",
            "asin": "B001",
            "reviewText": "Great product, works perfectly!",
            "overall": 5.0,
            "summary": "Excellent buy",
            "unixReviewTime": 1609459200,
            "reviewerName": "John D.",
        },
        {
            "reviewerID": "A1X",
            "asin": "B002",
            "reviewText": "Decent quality but overpriced.",
            "overall": 3.0,
            "summary": "Okay product",
            "unixReviewTime": 1609545600,
            "reviewerName": "John D.",
        },
        {
            "reviewerID": "A2Y",
            "asin": "B001",
            "reviewText": "Not as good as expected.",
            "overall": 2.0,
            "summary": "Disappointing",
            "unixReviewTime": 1609632000,
            "reviewerName": "Jane S.",
        },
        {
            "reviewerID": "A2Y",
            "asin": "B003",
            "reviewText": "Best purchase I've made this year!",
            "overall": 5.0,
            "summary": "Amazing",
            "unixReviewTime": 1609718400,
            "reviewerName": "Jane S.",
        },
    ]
    
    # Write file
    with (output_dir / "amazon_reviews_sample.json").open("w", encoding="utf-8") as f:
        for item in reviews_data:
            f.write(json.dumps(item) + "\n")
            
    print(f"Created Amazon fixtures with {len(reviews_data)} reviews")


def create_goodreads_fixtures() -> None:
    """Creates Goodreads test fixture files."""
    output_dir = Path("data/sample/test_fixtures")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Goodreads reviews sample
    reviews_data = [
        {
            "user_id": "u1",
            "book_id": "b1",
            "review_id": "r1",
            "rating": 5,
            "review_text": "One of the best books I've ever read!",
            "date_added": "Tue Jan 20 18:50:49 -0800 2023",
            "date_updated": "Wed Jan 21 12:27:43 -0800 2023",
            "read_at": "Wed Jan 21 12:27:42 -0800 2023",
            "started_at": "",
            "n_votes": 10,
            "n_comments": 3,
        },
        {
            "user_id": "u1",
            "book_id": "b2",
            "review_id": "r2",
            "rating": 4,
            "review_text": "Enjoyable read with interesting characters.",
            "date_added": "Sun Oct 12 14:49:51 -0700 2022",
            "date_updated": "Fri Oct 17 16:15:57 -0700 2022",
            "read_at": "",
            "started_at": "",
            "n_votes": 5,
            "n_comments": 1,
        },
        {
            "user_id": "u2",
            "book_id": "b1",
            "review_id": "r3",
            "rating": 3,
            "review_text": "It was okay, but didn't live up to the hype.",
            "date_added": "Fri Jun 06 11:23:28 -0700 2023",
            "date_updated": "Sun Jun 15 15:24:30 -0700 2023",
            "read_at": "",
            "started_at": "",
            "n_votes": 2,
            "n_comments": 0,
        },
        {
            "user_id": "u2",
            "book_id": "b3",
            "review_id": "r4",
            "rating": 5,
            "review_text": "Absolutely loved it! Couldn't put it down.",
            "date_added": "Wed Jun 04 08:55:26 -0700 2023",
            "date_updated": "Wed Jun 04 12:36:50 -0700 2023",
            "read_at": "Wed Jun 04 12:36:50 -0700 2023",
            "started_at": "Wed Jun 04 00:00:00 -0700 2023",
            "n_votes": 8,
            "n_comments": 2,
        },
    ]
    
    # Goodreads books sample
    books_data = [
        {
            "book_id": "b1",
            "title": "The Great Novel",
            "authors": [{"author_id": "a1", "role": ""}],
            "genres": [
                {"count": "1500", "name": "fiction"},
                {"count": "800", "name": "literary"},
                {"count": "300", "name": "classic"},
            ],
            "description": "A timeless story about life, love, and human nature.",
            "average_rating": "4.5",
            "language_code": "eng",
        },
        {
            "book_id": "b2",
            "title": "Mystery Mansion",
            "authors": [{"author_id": "a2", "role": ""}],
            "genres": [
                {"count": "1200", "name": "mystery"},
                {"count": "600", "name": "thriller"},
                {"count": "200", "name": "suspense"},
            ],
            "description": "A gripping mystery set in an old mansion with dark secrets.",
            "average_rating": "4.2",
            "language_code": "eng",
        },
        {
            "book_id": "b3",
            "title": "Science Explained",
            "authors": [{"author_id": "a3", "role": ""}],
            "genres": [
                {"count": "900", "name": "non-fiction"},
                {"count": "500", "name": "science"},
                {"count": "150", "name": "education"},
            ],
            "description": "Complex scientific concepts explained in simple terms.",
            "average_rating": "4.7",
            "language_code": "eng",
        },
    ]
    
    # Write files
    with (output_dir / "goodreads_reviews_sample.json").open("w", encoding="utf-8") as f:
        for item in reviews_data:
            f.write(json.dumps(item) + "\n")
            
    with (output_dir / "goodreads_books_sample.json").open("w", encoding="utf-8") as f:
        for item in books_data:
            f.write(json.dumps(item) + "\n")
            
    print(f"Created Goodreads fixtures with {len(reviews_data)} reviews, {len(books_data)} books")


def validate_fixtures() -> None:
    """Validates that the created fixtures match expected formats."""
    output_dir = Path("data/sample/test_fixtures")
    
    # Check Yelp files
    yelp_files = [
        "yelp_reviews_sample.json",
        "yelp_users_sample.json",
        "yelp_business_sample.json",
    ]
    
    for filename in yelp_files:
        filepath = output_dir / filename
        if not filepath.exists():
            print(f"Missing file: {filepath}")
            continue
            
        with filepath.open("r", encoding="utf-8") as f:
            lines = f.readlines()
            print(f"{filename}: {len(lines)} lines")
            
            # Validate first line is valid JSON
            if lines:
                try:
                    json.loads(lines[0].strip())
                except json.JSONDecodeError:
                    print(f"  ERROR: Invalid JSON in first line of {filename}")
                    
    # Check Amazon file
    amazon_file = output_dir / "amazon_reviews_sample.json"
    if amazon_file.exists():
        with amazon_file.open("r", encoding="utf-8") as f:
            lines = f.readlines()
            print(f"amazon_reviews_sample.json: {len(lines)} lines")
            
    # Check Goodreads files
    goodreads_files = [
        "goodreads_reviews_sample.json",
        "goodreads_books_sample.json",
    ]
    
    for filename in goodreads_files:
        filepath = output_dir / filename
        if not filepath.exists():
            print(f"Missing file: {filepath}")
            continue
            
        with filepath.open("r", encoding="utf-8") as f:
            lines = f.readlines()
            print(f"{filename}: {len(lines)} lines")


def main() -> None:
    """Main entry point for test fixture generation."""
    print("Generating test fixtures for CI/unit testing...")
    print("=" * 60)
    
    # Create fixtures
    create_yelp_fixtures()
    create_amazon_fixtures()
    create_goodreads_fixtures()
    
    print("\n" + "=" * 60)
    print("Fixture Generation Complete")
    print("=" * 60)
    
    # Validate
    validate_fixtures()
    
    print("\nTest fixtures created in: data/sample/test_fixtures/")
    print("Use these files for CI testing without real data.")


if __name__ == "__main__":
    main()