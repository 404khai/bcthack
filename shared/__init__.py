
"""Shared infrastructure for both FastAPI services."""

from .embeddings import EmbeddingService
from .llm_client import AnthropicLLMClient
from .nigerian_adapter import NigerianContextAdapter
from .user_profile import (
    ReviewRecord,
    StyleFingerprint,
    UserProfile,
    UserProfileBuilder,
    build_style_fingerprint,
)
from .vector_store import VectorStore

__all__ = [
    "AnthropicLLMClient",
    "EmbeddingService",
    "NigerianContextAdapter",
    "ReviewRecord",
    "StyleFingerprint",
    "UserProfile",
    "UserProfileBuilder",
    "VectorStore",
    "build_style_fingerprint",
]
