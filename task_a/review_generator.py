"""Review generation logic with a deterministic Phase 1 fallback."""

from __future__ import annotations

from typing import Any

from shared.nigerian_adapter import NigerianContextAdapter


class ReviewGenerator:
    async def generate(
        self,
        *,
        persona: Any,
        item_name: str,
        item_description: str,
        style_fingerprint: dict,
        fallback_rating: float,
        nigerian_mode: bool,
    ) -> str:
        tone = "enthusiastic" if fallback_rating >= 4 else "measured"
        review = (
            f"I tried {item_name} and found it {tone}. "
            f"{item_description.strip()} "
            f"This fits my usual preferences with an average rating tendency of "
            f"{style_fingerprint.get('avg_rating', 0)}."
        )
        adapter = NigerianContextAdapter(enabled=nigerian_mode)
        return adapter.adapt_text(review)
