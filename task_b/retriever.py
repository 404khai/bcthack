
"""Async multi-source retriever for Task B."""

from __future__ import annotations

import asyncio
from typing import Any

from shared.embeddings import EmbeddingService
from shared.vector_store import VectorStore
from task_b.schemas import Item


class MultiSourceRetriever:
    """Queries ChromaDB using history, content, and cross-domain retrieval strategies."""

    def __init__(
        self,
        vector_store: VectorStore | None = None,
        embeddings: EmbeddingService | None = None,
    ) -> None:
        self.vector_store = vector_store or VectorStore()
        self.embeddings = embeddings or EmbeddingService()

    async def query_by_user_history(
        self,
        user_id: str,
        category: str,
        top_k: int = 20,
    ) -> list[Item]:
        """Retrieves candidates using a user's historical category preference signal."""
        return await asyncio.to_thread(
            self._query_reviews_by_user,
            user_id=user_id,
            query_text=category or user_id,
            top_k=top_k,
        )

    async def query_by_content(
        self,
        item_attributes: dict[str, Any],
        top_k: int = 20,
    ) -> list[Item]:
        """Retrieves candidates using the current request's item attributes."""
        content_query = " ".join(f"{key} {value}" for key, value in item_attributes.items()).strip()
        query_text = content_query or "popular relevant items"
        return await asyncio.to_thread(
            self._query_collection,
            query_text=query_text,
            collection_name="items",
            top_k=top_k,
            source="content",
            where=None,
        )

    async def query_cross_domain(
        self,
        source_domain: str,
        target_domain: str,
        user_id: str,
        top_k: int = 20,
    ) -> list[Item]:
        """Retrieves candidates for a target domain based on a different source domain."""
        cross_domain_query = f"{source_domain} preferences transferred to {target_domain} for {user_id}"
        return await asyncio.to_thread(
            self._query_collection,
            query_text=cross_domain_query,
            collection_name="items",
            top_k=top_k,
            source="cross_domain",
            where=None,
        )

    def _query_collection(
        self,
        query_text: str,
        collection_name: str,
        top_k: int,
        source: str,
        where: dict[str, object] | None,
    ) -> list[Item]:
        try:
            embedding = self.embeddings.embed_query(query_text)
            results = self.vector_store.query(
                collection_name=collection_name,
                query_embeddings=[embedding] if embedding else None,
                query_texts=None if embedding else [query_text],
                n_results=top_k,
                where=where,
            )
        except Exception:
            return self._fallback_items(query_text=query_text, source=source, top_k=top_k)

        documents = results.get("documents", [[]])[0] if results.get("documents") else []
        metadatas = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
        distances = results.get("distances", [[]])[0] if results.get("distances") else []
        ids = results.get("ids", [[]])[0] if results.get("ids") else []

        if not documents:
            return self._fallback_items(query_text=query_text, source=source, top_k=top_k)

        items: list[Item] = []
        for index, document in enumerate(documents):
            metadata = metadatas[index] if index < len(metadatas) else {}
            distance = distances[index] if index < len(distances) else 0.35
            item_id = str(metadata.get("item_id") or ids[index] if index < len(ids) else f"{source}-{index}")
            items.append(
                Item(
                    item_id=item_id,
                    title=str(document),
                    category=str(metadata.get("category", "unknown")),
                    source=str(metadata.get("source", source)),
                    similarity_score=round(max(0.0, 1.0 - float(distance)), 4),
                    metadata=dict(metadata),
                )
            )
        return items

    def _query_reviews_by_user(
        self,
        user_id: str,
        query_text: str,
        top_k: int,
    ) -> list[Item]:
        """Queries the review collection with a user filter and projects results into items."""
        try:
            embedding = self.embeddings.embed_query(query_text)
            results = self.vector_store.query(
                collection_name="reviews",
                query_embeddings=[embedding] if embedding else None,
                query_texts=None if embedding else [query_text],
                n_results=top_k,
                where={"user_id": user_id},
            )
        except Exception:
            return self._fallback_items(query_text=query_text, source="history", top_k=top_k)

        documents = results.get("documents", [[]])[0] if results.get("documents") else []
        metadatas = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
        distances = results.get("distances", [[]])[0] if results.get("distances") else []
        ids = results.get("ids", [[]])[0] if results.get("ids") else []

        if not documents:
            return self._fallback_items(query_text=query_text, source="history", top_k=top_k)

        items: list[Item] = []
        for index, document in enumerate(documents):
            metadata = metadatas[index] if index < len(metadatas) else {}
            distance = distances[index] if index < len(distances) else 0.3
            review_id = ids[index] if index < len(ids) else f"history-{index}"
            item_id = str(metadata.get("item_id", review_id))
            items.append(
                Item(
                    item_id=item_id,
                    title=str(document)[:120],
                    category=str(metadata.get("category", "unknown")),
                    source=str(metadata.get("source", "history")),
                    similarity_score=round(max(0.0, 1.0 - float(distance)), 4),
                    metadata={**dict(metadata), "matched_review_id": review_id},
                )
            )
        return items

    def _fallback_items(self, query_text: str, source: str, top_k: int) -> list[Item]:
        defaults = [
            ("lagos-jollof", "Lagos Jollof Spot", "restaurant"),
            ("nollywood-crime", "Nollywood Crime Series Night", "entertainment"),
            ("suya-express", "Suya Express Grill", "food"),
            ("book-cafe", "Quiet Book Cafe Hangout", "experience"),
            ("smart-accessory", "Reliable Everyday Gadget Pick", "electronics"),
        ]
        items: list[Item] = []
        for index, (item_id, title, category) in enumerate(defaults[:top_k]):
            items.append(
                Item(
                    item_id=item_id,
                    title=f"{title} for {query_text[:40]}".strip(),
                    category=category,
                    source=source,
                    similarity_score=round(max(0.45, 0.88 - (index * 0.08)), 4),
                    metadata={"fallback": True},
                )
            )
        return items
