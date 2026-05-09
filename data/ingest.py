"""Master ingestion command for sample and real dataset subsets."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from data.amazon_processor import AmazonProcessor
from data.goodreads_processor import GoodreadsProcessor
from data.yelp_processor import YelpProcessor
from shared.embeddings import EmbeddingService
from shared.user_profile import UserProfile
from shared.vector_store import VectorStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest dataset subsets into ChromaDB.")
    parser.add_argument("--yelp", type=Path, default=Path("data/sample/yelp_sample.jsonl"))
    parser.add_argument("--amazon", type=Path, default=Path("data/sample/amazon_sample.jsonl"))
    parser.add_argument("--goodreads", type=Path, default=Path("data/sample/goodreads_sample.jsonl"))
    parser.add_argument("--use-sample-data", action="store_true")
    return parser


def upsert_profiles(store: VectorStore, embeddings: EmbeddingService, profiles: Iterable[UserProfile]) -> None:
    profile_list = list(profiles)
    if not profile_list:
        return

    documents = [profile.to_document() for profile in profile_list]
    vectors = embeddings.embed_texts(documents)
    store.upsert(
        collection_name="users",
        ids=[profile.user_id for profile in profile_list],
        documents=documents,
        metadatas=[profile.to_metadata() for profile in profile_list],
        embeddings=vectors,
    )

    item_ids: list[str] = []
    item_docs: list[str] = []
    item_metadata: list[dict[str, str]] = []
    review_ids: list[str] = []
    review_docs: list[str] = []
    review_metadata: list[dict[str, str | float]] = []

    for profile in profile_list:
        for review in profile.reviews + profile.held_out_reviews:
            item_ids.append(f"{review.source}:{review.item_id}")
            item_docs.append(
                review.metadata.get("title")
                or review.metadata.get("business_name")
                or review.category
            )
            item_metadata.append(
                {
                    "source": review.source,
                    "item_id": review.item_id,
                    "category": review.category,
                }
            )
            review_ids.append(review.review_id)
            review_docs.append(review.review_text)
            review_metadata.append(
                {
                    "user_id": profile.user_id,
                    "item_id": review.item_id,
                    "source": review.source,
                    "rating": review.rating,
                    "category": review.category,
                }
            )

    store.upsert(
        collection_name="items",
        ids=item_ids,
        documents=item_docs,
        metadatas=item_metadata,
        embeddings=embeddings.embed_texts(item_docs),
    )
    store.upsert(
        collection_name="reviews",
        ids=review_ids,
        documents=review_docs,
        metadatas=review_metadata,
        embeddings=embeddings.embed_texts(review_docs),
    )


def main() -> None:
    args = build_parser().parse_args()
    processors = {
        "yelp": (YelpProcessor(), args.yelp),
        "amazon": (AmazonProcessor(), args.amazon),
        "goodreads": (GoodreadsProcessor(), args.goodreads),
    }

    store = VectorStore()
    embeddings = EmbeddingService()

    for source, (processor, path) in processors.items():
        if not path.exists():
            if args.use_sample_data:
                continue
            raise FileNotFoundError(f"Input file for {source} not found: {path}")
        profiles = processor.load_profiles(path)
        upsert_profiles(store, embeddings, profiles)
        print(f"Ingested {len(profiles)} {source} user profiles from {path}")

    print("Collections:", ", ".join(store.list_collections()))


if __name__ == "__main__":
    main()
