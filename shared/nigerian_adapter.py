"""Utilities for optional Nigerian contextualization."""

from __future__ import annotations

from dataclasses import dataclass
from os import getenv
from typing import Literal
import asyncio

from shared.llm_client import AnthropicLLMClient
from shared.prompts import (
    NIGERIAN_ADAPT_LIGHT,
    NIGERIAN_ADAPT_MEDIUM,
    NIGERIAN_ADAPT_FULL,
)

NIGERIAN_LEXICON = {
    "positive": [
        "e dey sweet",
        "burst my brain",
        "correct",
        "value for money no lie",
        "too much",
    ],
    "negative": [
        "wahala",
        "no try am",
        "sapa no let me enjoy",
        "e no make brain",
    ],
    "food": [
        "suya",
        "jollof",
        "puff puff",
        "pepper soup",
        "buka",
    ],
    "places": [
        "Lagos Island",
        "Abuja",
        "Lekki",
        "Victoria Island",
    ],
    "retail": [
        "Shoprite",
        "Jumia",
        "Konga",
    ],
    "entertainment": [
        "Afrobeats",
        "Nollywood",
    ]
}


class NigerianContextAdapter:
    """Adapts text and recommendations to sound authentically Nigerian."""

    def __init__(self, enabled: bool = False, llm_client: AnthropicLLMClient | None = None) -> None:
        self.enabled = enabled
        self._llm_client = llm_client

    @classmethod
    def from_env(cls) -> "NigerianContextAdapter":
        """Instantiates adapter based on environment variable."""
        raw_value = getenv("NIGERIAN_MODE", "false").strip().lower()
        return cls(enabled=raw_value in {"1", "true", "yes", "on"})

    def _get_llm_client(self) -> AnthropicLLMClient | None:
        if self._llm_client is not None:
            return self._llm_client
        if not getenv("ANTHROPIC_API_KEY"):
            return None
        self._llm_client = AnthropicLLMClient(model="claude-sonnet-4-20250514")
        return self._llm_client

    async def adapt_review(self, review_text: str, intensity: Literal["light", "medium", "full"] = "medium") -> str:
        """Adapts a review using Claude based on intensity."""
        if not self.enabled or not review_text:
            return review_text
            
        client = self._get_llm_client()
        if client is None:
            return self.adapt_text(review_text) # Fallback to old behavior if no client

        prompt_template = {
            "light": NIGERIAN_ADAPT_LIGHT,
            "medium": NIGERIAN_ADAPT_MEDIUM,
            "full": NIGERIAN_ADAPT_FULL,
        }.get(intensity, NIGERIAN_ADAPT_MEDIUM)

        try:
            adapted_text = await client.generate_text(
                system_prompt="You are a cultural adapter.",
                user_prompt=prompt_template.format(text=review_text),
                max_tokens=300,
                temperature=0.4,
            )
            return adapted_text.strip()
        except Exception:
            return self.adapt_text(review_text)

    async def adapt_recommendation_explanation(self, explanation: str, category: str) -> str:
        """Adapts an explanation specifically, incorporating category context if needed."""
        if not self.enabled or not explanation:
            return explanation

        client = self._get_llm_client()
        if client is None:
            return self.adapt_text(explanation)
            
        # We can just use the medium prompt for explanations
        user_prompt = f"Adapt this recommendation explanation for a '{category}' item to have a natural, warm Nigerian flavor without stereotypes:\n\n{explanation}"
        
        try:
            adapted_text = await client.generate_text(
                system_prompt="You are a cultural adapter.",
                user_prompt=user_prompt,
                max_tokens=150,
                temperature=0.4,
            )
            return adapted_text.strip()
        except Exception:
            return self.adapt_text(explanation)

    def get_cultural_defaults(self, category: str) -> list[str]:
        """Returns popular Nigerian defaults for a given category."""
        category = category.lower()
        if category in ["restaurant", "food", "dining"]:
            return ["Jollof rice", "Suya spot", "Buka", "Pepper soup"]
        elif category in ["book", "books", "literature"]:
            return ["Chimamanda Ngozi Adichie", "Wole Soyinka", "Chinua Achebe"]
        elif category in ["movie", "movies", "film"]:
            return ["Nollywood blockbusters", "Afrobeats documentaries", "Trending international movies"]
        elif category in ["product", "retail", "shopping", "electronics"]:
            return ["Jumia electronics", "Konga deals", "Shoprite groceries"]
        else:
            return ["Lagos popular spots", "Trending Naija picks"]

    def adapt_text(self, text: str) -> str:
        """Fallback synchronous adaptation if LLM fails or is unavailable."""
        if not self.enabled or not text:
            return text
        replacements = {
            "supermarket": "Shoprite",
            "delivery": "dispatch",
            "spicy": "peppery",
            "great": "correct",
        }
        adapted = text
        for source, target in replacements.items():
            adapted = adapted.replace(source, target)
        return adapted

    def adapt_category(self, category: str) -> str:
        """Adapts category names."""
        if not self.enabled:
            return category
        mappings = {
            "grocery": "supermarket",
            "online retail": "Jumia-style marketplace",
            "barbecue": "suya spot",
            "restaurant": "buka",
        }
        return mappings.get(category.lower(), category)
