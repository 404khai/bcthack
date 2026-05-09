"""Vector-store backed retriever for Task B."""

from __future__ import annotations

from shared.embeddings import EmbeddingService
from shared.vector_store import VectorStore
from task_b.schemas import RecommendRequest, RecommendationItem


class Retriever:
    def __init__(self) -> None:
        self.vector_store = VectorStore()
        self.embeddings = EmbeddingService()

    def retrieve(self, request: RecommendRequest) -> list[RecommendationItem]:
        if not request.query.strip():
            return []
        embedding = self.embeddings.embed_query(request.query)
        if not embedding:
            return []
        results = self.vector_store.query(
            collection_name="items",
            query_embeddings=[embedding],
            n_results=request.top_k,
        )
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        recommendations: list[RecommendationItem] = []
        for index, document in enumerate(documents):
            metadata = metadatas[index]
            recommendations.append(
                RecommendationItem(
                    item_id=str(metadata.get("item_id", f"item-{index}")),
                    title=document,
                    category=str(metadata.get("category", "unknown")),
                    score=round(1.0 - (index * 0.05), 3),
                    explanation="Retrieved from the shared item knowledge base based on semantic similarity.",
                    source=str(metadata.get("source", "shared")),
                )
            )
        return recommendations
