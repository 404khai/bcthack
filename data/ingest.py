"""Master ingestion orchestration script for ChromaDB collections."""

from __future__ import annotations

import argparse
import json
from os import getenv
from pathlib import Path
from typing import Any

from tqdm import tqdm

from data.amazon_processor import AmazonProcessor, ItemRecord as AmazonItemRecord
from data.goodreads_processor import GoodreadsProcessor, ItemRecord as GoodreadsItemRecord
from data.yelp_processor import YelpProcessor, ItemRecord as YelpItemRecord
from shared.embeddings import EmbeddingService
from shared.user_profile import ReviewRecord, UserProfile
from shared.vector_store import VectorStore


def build_parser() -> argparse.ArgumentParser:
    """Builds CLI argument parser with all required options."""
    parser = argparse.ArgumentParser(
        description="Ingest Yelp, Amazon, and Goodreads data into ChromaDB collections."
    )
    parser.add_argument(
        "--sample-only",
        action="store_true",
        help="Process only first 100 users per dataset (for testing)",
    )
    parser.add_argument(
        "--skip-yelp",
        action="store_true",
        help="Skip Yelp dataset ingestion",
    )
    parser.add_argument(
        "--skip-amazon",
        action="store_true",
        help="Skip Amazon dataset ingestion",
    )
    parser.add_argument(
        "--skip-goodreads",
        action="store_true",
        help="Skip Goodreads dataset ingestion",
    )
    parser.add_argument(
        "--chroma-dir",
        type=Path,
        default=Path(getenv("CHROMA_PERSIST_DIR", "chroma_data")),
        help="Directory for ChromaDB persistence",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Batch size for ChromaDB inserts (default: 100)",
    )
    return parser


def build_user_document(user: UserProfile) -> str:
    """Builds a searchable document summary for vector storage."""
    categories = ", ".join(user.preferred_categories) or "mixed interests"
    sentiment = ", ".join(
        f"{key}={value:.2f}" for key, value in user.style_fingerprint.sentiment_profile.items()
    )
    phrases = ", ".join(user.style_fingerprint.top_phrases[:5]) or "no dominant phrases"
    return (
        f"User {user.user_id} on {user.platform} prefers {categories}. "
        f"Average rating {user.style_fingerprint.avg_rating:.2f} with rating deviation "
        f"{user.style_fingerprint.rating_std:.2f}. "
        f"Average review length {user.style_fingerprint.avg_review_length:.1f} words, "
        f"vocabulary size {user.style_fingerprint.vocabulary_size}, "
        f"formality {user.style_fingerprint.formality_score:.2f}. "
        f"Top phrases: {phrases}. Sentiment profile: {sentiment}."
    )


def build_item_document(item: Any) -> str:
    """Builds a searchable document for an item."""
    if isinstance(item, YelpItemRecord):
        return f"{item.name} - {item.category} - Rating: {item.avg_rating:.1f}"
    elif isinstance(item, AmazonItemRecord):
        return f"{item.name} - {item.category} - Rating: {item.avg_rating:.1f}"
    elif isinstance(item, GoodreadsItemRecord):
        return f"{item.name} by {item.metadata.get('author_id', 'unknown author')} - {item.category} - Rating: {item.avg_rating:.1f}"
    else:
        return f"{item.name} - {item.category}"


def build_review_document(review: ReviewRecord) -> str:
    """Builds a searchable document for a review."""
    return review.review_text


def ensure_platform_prefix(platform: str, value: str) -> str:
    """Prefixes an identifier only once with its platform namespace."""
    prefix = f"{platform}_"
    return value if value.startswith(prefix) else f"{prefix}{value}"


def process_dataset(
    platform: str,
    processor: Any,
    skip_flag: bool,
    sample_only: bool,
    embeddings: EmbeddingService,
    store: VectorStore,
    batch_size: int,
    split_manifest: dict[str, Any],
) -> tuple[int, int, int, int]:
    """Processes a single dataset and returns statistics."""
    if skip_flag:
        print(f"Skipping {platform} dataset")
        return 0, 0, 0, 0
        
    print(f"\nProcessing {platform} dataset...")
    
    try:
        # Processors own sampling decisions so users/items/reviews stay aligned.
        if hasattr(processor, "process"):
            users, items, reviews = processor.process(sample_only=sample_only)
        else:
            users, items, reviews = processor.load_all()
            
        if not users:
            print(f"No users found for {platform}")
            return 0, 0, 0, 0
            
        print(f"  Found {len(users)} users, {len(items)} items, {len(reviews)} reviews")
        
        # Prepare data for ChromaDB
        user_ids = [ensure_platform_prefix(platform, user.user_id) for user in users]
        user_docs = [build_user_document(user) for user in users]
        user_metadatas = []
        
        for user in users:
            metadata = {
                "platform": platform,
                "avg_rating": user.style_fingerprint.avg_rating,
                "review_count": len(user.review_history),
                "top_categories": ", ".join(user.preferred_categories[:3]),
                "avg_review_length": user.style_fingerprint.avg_review_length,
                "vocabulary_size": user.style_fingerprint.vocabulary_size,
            }
            user_metadatas.append(metadata)
            
        # Batch insert users
        print(f"  Inserting {len(users)} users into ChromaDB...")
        for i in tqdm(range(0, len(users), batch_size), desc="Users"):
            batch_ids = user_ids[i:i+batch_size]
            batch_docs = user_docs[i:i+batch_size]
            batch_metadatas = user_metadatas[i:i+batch_size]
            batch_embeddings = embeddings.embed_texts(batch_docs)
            
            store.upsert(
                collection_name="users",
                ids=batch_ids,
                documents=batch_docs,
                metadatas=batch_metadatas,
                embeddings=batch_embeddings,
            )
            
        # Prepare items
        item_ids = [ensure_platform_prefix(platform, item.item_id) for item in items]
        item_docs = [build_item_document(item) for item in items]
        item_metadatas = []
        
        for item in items:
            metadata = {
                "platform": platform,
                "category": item.category,
                "avg_rating": item.avg_rating,
                "name": item.name,
            }
            item_metadatas.append(metadata)
            
        # Batch insert items
        print("  Creating items collection...")
        store.get_collection("items")
        print(f"  Inserting {len(items)} items into ChromaDB...")
        for i in tqdm(range(0, len(items), batch_size), desc="Items"):
            batch_ids = item_ids[i:i+batch_size]
            batch_docs = item_docs[i:i+batch_size]
            batch_metadatas = item_metadatas[i:i+batch_size]
            batch_embeddings = embeddings.embed_texts(batch_docs)
            
            store.upsert(
                collection_name="items",
                ids=batch_ids,
                documents=batch_docs,
                metadatas=batch_metadatas,
                embeddings=batch_embeddings,
            )
            
        # Prepare reviews and track test split
        review_ids = []
        review_docs = []
        review_metadatas = []
        test_review_ids = []
        
        for user in users:
            # Training reviews
            for review in user.review_history:
                review_ids.append(ensure_platform_prefix(platform, review.review_id))
                review_docs.append(build_review_document(review))
                review_metadatas.append({
                    "user_id": user.user_id,
                    "item_id": review.item_id,
                    "rating": float(review.rating),
                    "platform": platform,
                    "is_test_split": "false",
                })
                
            # Test reviews (held out)
            for review in user.held_out_reviews:
                review_ids.append(ensure_platform_prefix(platform, review.review_id))
                review_docs.append(build_review_document(review))
                review_metadatas.append({
                    "user_id": user.user_id,
                    "item_id": review.item_id,
                    "rating": float(review.rating),
                    "platform": platform,
                    "is_test_split": "true",
                })
                test_review_ids.append(ensure_platform_prefix(platform, review.review_id))
                
        # Batch insert reviews
        print(f"  Inserting {len(review_ids)} reviews into ChromaDB...")
        for i in tqdm(range(0, len(review_ids), batch_size), desc="Reviews"):
            batch_ids = review_ids[i:i+batch_size]
            batch_docs = review_docs[i:i+batch_size]
            batch_metadatas = review_metadatas[i:i+batch_size]
            batch_embeddings = embeddings.embed_texts(batch_docs)
            
            store.upsert(
                collection_name="reviews",
                ids=batch_ids,
                documents=batch_docs,
                metadatas=batch_metadatas,
                embeddings=batch_embeddings,
            )
            
        # Update split manifest
        train_review_ids = [
            ensure_platform_prefix(platform, review.review_id)
            for user in users
            for review in user.review_history
        ]
        split_manifest[platform] = {"train": train_review_ids, "test": test_review_ids}
        
        return len(users), len(items), len(review_ids), len(test_review_ids)
        
    except Exception as e:
        print(f"Error processing {platform} dataset: {e}")
        return 0, 0, 0, 0


def main() -> None:
    """Main entry point for the ingestion script."""
    args = build_parser().parse_args()
    
    # Initialize services
    embeddings = EmbeddingService()
    store = VectorStore(persist_directory=str(args.chroma_dir))
    
    # Initialize processors
    processors = {
        "yelp": YelpProcessor(),
        "amazon": AmazonProcessor(),
        "goodreads": GoodreadsProcessor(),
    }
    
    skip_flags = {
        "yelp": args.skip_yelp,
        "amazon": args.skip_amazon,
        "goodreads": args.skip_goodreads,
    }
    
    # Statistics tracking
    stats: dict[str, tuple[int, int, int, int]] = {}
    split_manifest: dict[str, Any] = {}
    
    print("=" * 60)
    print("Starting ChromaDB Ingestion")
    print("=" * 60)

    # Ensure all core collections exist before ingestion so verification is deterministic.
    for collection_name in ["users", "items", "reviews"]:
        store.get_collection(collection_name)
    
    # Process each dataset
    for platform, processor in processors.items():
        user_count, item_count, review_count, test_count = process_dataset(
            platform=platform,
            processor=processor,
            skip_flag=skip_flags[platform],
            sample_only=args.sample_only,
            embeddings=embeddings,
            store=store,
            batch_size=args.batch_size,
            split_manifest=split_manifest,
        )
        
        stats[platform] = (user_count, item_count, review_count, test_count)
    
    # Save split manifest
    manifest_path = Path("data/splits.json")
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(split_manifest, f, indent=2)
    print(f"\nSaved train/test split manifest to {manifest_path}")
    
    # Print final statistics
    print("\n" + "=" * 60)
    print("Ingestion Complete - Final Statistics")
    print("=" * 60)
    print(f"{'Platform':<12} {'Users':<8} {'Items':<8} {'Reviews':<10} {'Test Reviews':<12}")
    print("-" * 60)
    
    total_users = 0
    total_items = 0
    total_reviews = 0
    total_test = 0
    
    for platform, (users, items, reviews, test) in stats.items():
        print(f"{platform:<12} {users:<8} {items:<8} {reviews:<10} {test:<12}")
        total_users += users
        total_items += items
        total_reviews += reviews
        total_test += test
        
    print("-" * 60)
    print(f"{'TOTAL':<12} {total_users:<8} {total_items:<8} {total_reviews:<10} {total_test:<12}")
    print("=" * 60)
    
    # Verify all core collections exist and print counts.
    collections = store.list_collections()
    print(f"\nChromaDB Collections: {', '.join(collections)}")
    print("Verifying collections after ingestion...")
    for collection in ["users", "items", "reviews"]:
        exists = collection in collections
        count = store.count(collection)
        if exists:
            print(f"  {collection}: {count} documents")
        else:
            print(f"  {collection}: NOT FOUND (count={count})")
            
    print("\nIngestion completed successfully!")


if __name__ == "__main__":
    main()
