"""ChromaDB wrapper for user, item, and review collections."""

from __future__ import annotations

import logging
from os import getenv
from pathlib import Path
from typing import Any, Sequence

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.config import Settings

logger = logging.getLogger(__name__)


class VectorStore:
    """Thin wrapper around a persistent ChromaDB client."""

    def __init__(self, persist_directory: str | None = None) -> None:
        self.persist_directory = Path(
            persist_directory or getenv("CHROMA_PERSIST_DIR", "./chroma_db")
        )
        self.persist_directory.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(self.persist_directory), settings=Settings(anonymized_telemetry=False)
        )

    def get_collection(self, name: str) -> Collection:
        return self.client.get_or_create_collection(name=name)

    def upsert(
        self,
        collection_name: str,
        ids: Sequence[str],
        documents: Sequence[str],
        metadatas: Sequence[dict[str, Any]],
        embeddings: Sequence[Sequence[float]] | None = None,
    ) -> None:
        collection = self.get_collection(collection_name)
        payload: dict[str, Any] = {
            "ids": list(ids),
            "documents": list(documents),
            "metadatas": list(metadatas),
        }
        if embeddings is not None:
            payload["embeddings"] = [list(vector) for vector in embeddings]
        collection.upsert(**payload)

    def query(
        self,
        collection_name: str,
        query_embeddings: Sequence[Sequence[float]] | None = None,
        query_texts: Sequence[str] | None = None,
        n_results: int = 5,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        collection = self.get_collection(collection_name)
        user_id = where.get("user_id") if where else None
        logger.info("[CHROMADB] Querying for user_id: %s", user_id)
        results = collection.query(
            query_embeddings=query_embeddings,
            query_texts=query_texts,
            n_results=n_results,
            where=where,
        )
        result_count = 0
        documents = results.get("documents")
        if documents and documents[0]:
            result_count = len(documents[0])
        logger.info("[CHROMADB] Query result count: %s", result_count)
        return results

    def get_by_id(self, collection_name: str, record_id: str) -> dict[str, Any] | None:
        """Fetches a single record by ID from a collection."""
        logger.info("[CHROMADB] Fetching %s by id: %s", collection_name, record_id)
        collection = self.get_collection(collection_name)
        results = collection.get(ids=[record_id])
        ids = results.get("ids", [])
        if not ids:
            logger.info("[CHROMADB] No %s record found for id: %s", collection_name, record_id)
            return None

        metadatas = results.get("metadatas", [])
        documents = results.get("documents", [])
        return {
            "id": ids[0],
            "metadata": (metadatas[0] if metadatas else {}) or {},
            "document": (documents[0] if documents else "") or "",
        }

    def _build_user_id_candidates(self, chroma_user_id: str) -> list[str]:
        """Builds possible review metadata user_id values from a Chroma user document ID."""
        candidates = [chroma_user_id]
        for platform in ("yelp_", "amazon_", "goodreads_"):
            if chroma_user_id.startswith(platform):
                stripped = chroma_user_id[len(platform) :]
                if stripped not in candidates:
                    candidates.append(stripped)
                reprefixed = platform + stripped
                if reprefixed not in candidates:
                    candidates.append(reprefixed)
        return candidates

    def query_reviews_for_user(
        self,
        user_id: str,
        query_text: str,
        n_results: int = 5,
    ) -> list[str]:
        """Queries the reviews collection using all candidate user_id variants."""
        candidates = self._build_user_id_candidates(user_id)
        logger.info("[CHROMADB] Trying %d user_id candidates: %s", len(candidates), candidates)

        for candidate in candidates:
            try:
                results = self.query(
                    collection_name="reviews",
                    query_texts=[query_text],
                    n_results=n_results,
                    where={"user_id": candidate},
                )
                documents = results.get("documents", [[]])
                valid = [str(doc).strip() for doc in documents[0] if doc and str(doc).strip()] if documents else []
                if valid:
                    logger.info("[CHROMADB] Found %d reviews with candidate: %s", len(valid), candidate)
                    return valid
            except Exception as error:
                logger.warning("[CHROMADB] Query failed for candidate %s: %s", candidate, error)
                continue

        logger.warning("[CHROMADB] No reviews found for any candidate of: %s", user_id)
        return []

    def count(self, collection_name: str) -> int:
        return self.get_collection(collection_name).count()

    def list_collections(self) -> list[str]:
        return [collection.name for collection in self.client.list_collections()]
