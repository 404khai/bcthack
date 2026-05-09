"""Sentence-transformers wrapper used by both services."""

from __future__ import annotations

from functools import cached_property
from os import getenv
from typing import Iterable, List

from sentence_transformers import SentenceTransformer


class EmbeddingService:
    """Creates dense vectors with a locally hosted sentence-transformers model."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or getenv(
            "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
        )

    @cached_property
    def model(self) -> SentenceTransformer:
        return SentenceTransformer(self.model_name)

    def embed_texts(self, texts: Iterable[str]) -> List[List[float]]:
        text_list = [text.strip() for text in texts if text and text.strip()]
        if not text_list:
            return []
        embeddings = self.model.encode(text_list, convert_to_numpy=True, normalize_embeddings=True)
        return embeddings.tolist()

    def embed_query(self, text: str) -> List[float]:
        results = self.embed_texts([text])
        return results[0] if results else []
