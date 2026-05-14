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

    def count(self, collection_name: str) -> int:
        return self.get_collection(collection_name).count()

    def list_collections(self) -> list[str]:
        return [collection.name for collection in self.client.list_collections()]
