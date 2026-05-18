"""Simple ChromaDB inspection script for local debugging."""

from __future__ import annotations

import os
from pathlib import Path

import chromadb
from chromadb.config import Settings
from chromadb.errors import InvalidCollectionException


def get_client() -> tuple[chromadb.PersistentClient, Path]:
    """Builds a persistent Chroma client using the active env configuration."""
    active_path = Path(os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")).resolve()
    client = chromadb.PersistentClient(
        path=str(active_path),
        settings=Settings(anonymized_telemetry=False),
    )
    return client, active_path


def print_collection_list(client: chromadb.PersistentClient) -> list[str]:
    """Prints available collections and returns their names."""
    collections = client.list_collections()
    names = [collection.name for collection in collections]

    print("=== AVAILABLE COLLECTIONS ===")
    if not names:
        print("No collections found.")
    else:
        for name in names:
            print(f"- {name}")
    return names


def inspect_users(client: chromadb.PersistentClient, available: set[str]) -> None:
    """Prints a sample of user documents if the collection exists."""
    print("\n=== USERS ===")
    if "users" not in available:
        print("Collection 'users' does not exist. Ingestion likely has not completed yet.")
        return

    try:
        users = client.get_collection("users")
        print(f"Total users: {users.count()}")
        all_users = users.get(limit=500)
        rich_users = [
            (uid, meta)
            for uid, meta in zip(all_users.get("ids", []), all_users.get("metadatas", []))
            if int((meta or {}).get("review_count", 0)) > 5
        ]
        rich_users.sort(key=lambda pair: int((pair[1] or {}).get("review_count", 0)), reverse=True)
        if not rich_users:
            print("No users with more than 5 reviews found.")
            return
        for uid, meta in rich_users[:5]:
            print(
                f"{uid} | reviews: {meta.get('review_count')} | "
                f"platform: {meta.get('platform')} | categories: {meta.get('top_categories')}"
            )
    except InvalidCollectionException:
        print("Collection 'users' is unavailable.")


def inspect_items(client: chromadb.PersistentClient, available: set[str]) -> None:
    """Prints a sample of item documents if the collection exists."""
    print("\n=== ITEMS ===")
    if "items" not in available:
        print("Collection 'items' does not exist.")
        return

    try:
        items = client.get_collection("items")
        print(f"Total items: {items.count()}")
        sample_items = items.get(limit=5)
        ids = sample_items.get("ids", [])
        metadatas = sample_items.get("metadatas", [])
        if not ids:
            print("Items collection exists but is empty.")
            return
        for item_id, meta in zip(ids, metadatas):
            meta = meta or {}
            print(
                f"ID: {item_id} | name: {meta.get('name')} | "
                f"category: {meta.get('category')} | platform: {meta.get('platform')}"
            )

        print("\n=== FOOD ITEM QUERY ===")
        results = items.query(
            query_texts=["restaurant food dining"],
            n_results=10,
        )
        query_ids = results.get("ids", [[]])[0]
        query_metas = results.get("metadatas", [[]])[0]
        for item_id, meta in zip(query_ids, query_metas):
            meta = meta or {}
            print(f"{item_id} | {meta.get('name')} | {meta.get('category')}")
    except InvalidCollectionException:
        print("Collection 'items' is unavailable.")


def inspect_reviews(client: chromadb.PersistentClient, available: set[str]) -> None:
    """Prints the review collection count if it exists."""
    print("\n=== REVIEWS ===")
    if "reviews" not in available:
        print("Collection 'reviews' does not exist.")
        return

    try:
        reviews = client.get_collection("reviews")
        print(f"Total reviews: {reviews.count()}")

        results = reviews.get(
            where={"user_id": "yelp__BcWyKQL16ndpBdggh2kNA"},
            limit=3,
        )
        print("Direct match:", results.get("ids", []))

        # try without platform prefix
        results2 = reviews.get(
            where={"user_id": "_BcWyKQL16ndpBdggh2kNA"},
            limit=3
        )
        print("Without prefix:", results2["ids"])

        # peek at raw stored metadata to see exact format
        sample = reviews.get(limit=3)
        print("Raw stored user_ids:", [m.get("user_id") for m in sample["metadatas"]])

    except InvalidCollectionException:
        print("Collection 'reviews' is unavailable.")


def print_ingestion_status(available: set[str]) -> None:
    """Prints a clearer summary of whether ingestion appears complete."""
    print("\n=== INGESTION STATUS ===")
    expected = {"users", "items", "reviews"}
    missing = expected - available

    if not available:
        print("No Chroma collections were found. Ingestion has not run yet or used a different path.")
        return

    if not missing:
        print("Core ingestion appears complete: users, items, and reviews collections are present.")
        return

    print(
        "Ingestion appears incomplete. Missing core collections: "
        + ", ".join(sorted(missing))
    )


def main() -> None:
    """Runs the local Chroma inspection flow."""
    client, active_path = get_client()
    print(f"=== ACTIVE CHROMA PATH ===\n{active_path}")

    available_names = print_collection_list(client)
    available = set(available_names)

    print_ingestion_status(available)
    inspect_users(client, available)
    inspect_items(client, available)
    inspect_reviews(client, available)


if __name__ == "__main__":
    main()
