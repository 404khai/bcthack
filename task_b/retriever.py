
"""Async multi-source retriever for Task B."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from shared.vector_store import VectorStore
from task_b.schemas import Item

logger = logging.getLogger(__name__)


class MultiSourceRetriever:
    """Queries ChromaDB using history, content, and cross-domain retrieval strategies."""

    def __init__(
        self,
        vector_store: VectorStore | None = None,
    ) -> None:
        self.vector_store = vector_store or VectorStore()

    async def query_by_user_history(
        self,
        user_id: str,
        category: str,
        top_k: int = 20,
    ) -> list[Item]:
        """Retrieves candidates using a user's historical category preference signal."""
        history_items = await self.retrieve_user_history_items(user_id=user_id, top_k=top_k)
        return [
            Item(
                item_id=item["item_id"],
                title=item.get("title") or item["item_id"],
                category=item.get("category") or "unknown",
                source="user_history",
                similarity_score=float(item.get("similarity_score", 0.75)),
                metadata=dict(item.get("metadata", {})),
            )
            for item in history_items
            if item.get("item_id")
        ]

    async def query_by_content(
        self,
        item_attributes: dict[str, Any],
        top_k: int = 20,
    ) -> list[Item]:
        """Retrieves candidates using the current request's item attributes."""
        content_query = " ".join(f"{key} {value}" for key, value in item_attributes.items()).strip()
        query_text = content_query or "popular relevant items"
        category = str(item_attributes.get("category", "")).strip() or None
        candidates = await self.retrieve_candidates(
            user_id="",
            category=category,
            query_text=query_text,
            top_k=top_k,
            platform=str(item_attributes.get("platform", "")).strip() or None,
        )
        return [self._candidate_to_item(candidate) for candidate in candidates]

    async def query_cross_domain(
        self,
        source_domain: str,
        target_domain: str,
        user_id: str,
        top_k: int = 20,
    ) -> list[Item]:
        """Retrieves candidates for a target domain based on a different source domain."""
        cross_domain_query = f"{source_domain} preferences transferred to {target_domain} for {user_id}"
        candidates = await self.retrieve_candidates(
            user_id=user_id,
            category=target_domain,
            query_text=cross_domain_query,
            top_k=top_k,
            platform=None,
        )
        items = [self._candidate_to_item(candidate) for candidate in candidates]
        for item in items:
            item.source = "cross_domain"
        return items

    async def retrieve_candidates(
        self,
        user_id: str,
        category: str,
        query_text: str,
        top_k: int = 20,
        platform: str | None = None,
    ) -> list[dict[str, Any]]:
        """Retrieves real item candidates from ChromaDB."""
        return await asyncio.to_thread(
            self._retrieve_candidates_sync,
            user_id,
            category,
            query_text,
            top_k,
            platform,
        )

    async def retrieve_user_history_items(
        self,
        user_id: str,
        top_k: int = 10,
    ) -> list[dict[str, Any]]:
        """Retrieves items the user has reviewed before."""
        return await asyncio.to_thread(self._retrieve_user_history_items_sync, user_id, top_k)

    def _retrieve_candidates_sync(
        self,
        user_id: str,
        category: str,
        query_text: str,
        top_k: int,
        platform: str | None,
    ) -> list[dict[str, Any]]:
        logger.info(
            "[RETRIEVER] Querying items for category=%s query=%s",
            category,
            query_text[:50],
        )
        candidates: list[dict[str, Any]] = []

        where: dict[str, Any] | None = None
        if category:
            where = {"category": {"$eq": category}}
            if platform:
                where = {"$and": [where, {"platform": {"$eq": platform}}]}
        elif platform:
            where = {"platform": {"$eq": platform}}

        try:
            results = self.vector_store.query(
                collection_name="items",
                query_texts=[query_text],
                n_results=min(top_k, 20),
                where=where,
            )
            candidates = self._results_to_candidates(
                results,
                default_category=category,
                source="chromadb_semantic",
            )
            logger.info("[RETRIEVER] Category query returned %d candidates", len(candidates))
        except Exception as error:
            logger.warning("[RETRIEVER] Category query failed: %s", error)

        if not candidates:
            try:
                results = self.vector_store.query(
                    collection_name="items",
                    query_texts=[query_text],
                    n_results=min(top_k, 20),
                )
                candidates = self._results_to_candidates(
                    results,
                    default_category=category,
                    source="chromadb_semantic_fallback",
                )
                logger.info("[RETRIEVER] Fallback query returned %d candidates", len(candidates))
            except Exception as error:
                logger.error("[RETRIEVER] Fallback query also failed: %s", error)

        return candidates[:top_k]

    def _retrieve_user_history_items_sync(
        self,
        user_id: str,
        top_k: int,
    ) -> list[dict[str, Any]]:
        """Retrieves actual reviewed items for a user from the reviews collection."""
        candidates = self._build_user_id_candidates(user_id)
        for candidate in candidates:
            try:
                results = self.vector_store.query(
                    collection_name="reviews",
                    query_texts=["user review history"],
                    n_results=top_k,
                    where={"user_id": candidate},
                )
                ids = results.get("ids", [[]])[0] if results.get("ids") else []
                metadatas = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
                if ids:
                    logger.info("[RETRIEVER] Found %d history items for %s", len(ids), candidate)
                    history_items: list[dict[str, Any]] = []
                    for meta in metadatas:
                        if not meta:
                            continue
                        item_id = str(meta.get("item_id", "")).strip()
                        if not item_id:
                            continue
                        item_record = self.vector_store.get_by_id("items", item_id)
                        item_metadata = item_record.get("metadata", {}) if item_record else {}
                        history_items.append(
                            {
                                "item_id": item_id,
                                "title": item_metadata.get("name", item_id),
                                "rating": float(meta.get("rating", 3.0)),
                                "category": item_metadata.get("category") or meta.get("category", ""),
                                "similarity_score": 0.82,
                                "metadata": {
                                    **item_metadata,
                                    "rating": float(meta.get("rating", 3.0)),
                                    "history_user_id": candidate,
                                },
                            }
                        )
                    if history_items:
                        return history_items[:top_k]
            except Exception:
                continue
        return []

    def _results_to_candidates(
        self,
        results: dict[str, Any],
        *,
        default_category: str,
        source: str,
    ) -> list[dict[str, Any]]:
        docs = results.get("documents", [[]])[0] if results.get("documents") else []
        ids = results.get("ids", [[]])[0] if results.get("ids") else []
        metas = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
        distances = results.get("distances", [[]])[0] if results.get("distances") else []

        candidates: list[dict[str, Any]] = []
        for doc, item_id, meta, dist in zip(docs, ids, metas, distances):
            if doc and str(doc).strip():
                meta = meta or {}
                candidates.append(
                    {
                        "item_id": item_id,
                        "title": meta.get("name", item_id),
                        "category": meta.get("category", default_category or "unknown"),
                        "source": source,
                        "similarity_score": round(1 - float(dist), 3),
                        "metadata": meta,
                    }
                )
        return candidates

    def _candidate_to_item(self, candidate: dict[str, Any]) -> Item:
        return Item(
            item_id=str(candidate["item_id"]),
            title=str(candidate.get("title") or candidate["item_id"]),
            category=str(candidate.get("category") or "unknown"),
            source=str(candidate.get("source") or "chromadb"),
            similarity_score=float(candidate.get("similarity_score", 0.0)),
            metadata=dict(candidate.get("metadata", {})),
        )

    def _build_user_id_candidates(self, user_id: str) -> list[str]:
        candidates = [user_id]
        for platform in ("yelp_", "amazon_", "goodreads_"):
            if user_id.startswith(platform):
                stripped = user_id[len(platform) :]
                if stripped not in candidates:
                    candidates.append(stripped)
                reprefixed = platform + stripped
                if reprefixed not in candidates:
                    candidates.append(reprefixed)
        return candidates
