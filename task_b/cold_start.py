
"""Cold-start strategies for Task B."""

from __future__ import annotations

import json
from os import getenv
from typing import Any

from shared.llm_client import AnthropicLLMClient
from shared.nigerian_adapter import NigerianContextAdapter
from shared.prompts import TASK_B_COLD_START_SYSTEM, TASK_B_COLD_START_USER
from task_b.schemas import Item, RequestContext, UserPersona

CLAUDE_MODEL_NAME = "claude-sonnet-4-20250514"
POPULARITY_FALLBACKS = {
    "restaurant": [
        ("popular-jollof", "Popular Jollof Kitchen", "restaurant", 0.72),
        ("lagos-rooftop", "Lagos Rooftop Lounge", "restaurant", 0.68),
    ],
    "movies": [
        ("nollywood-top", "Trending Nollywood Crime Series", "movies", 0.74),
        ("cinema-hit", "Weekend Cinema Crowd Favorite", "movies", 0.66),
    ],
    "food": [
        ("suya-night", "Late-Night Suya Spot", "food", 0.75),
        ("pepper-soup", "Pepper Soup Comfort Bowl", "food", 0.69),
    ],
    "default": [
        ("popular-local", "Popular Local Discovery", "experience", 0.65),
        ("city-favorite", "City Favorite Pick", "experience", 0.61),
    ],
}


class ColdStartHandler:
    """Handles recommendations when user history is empty or too sparse."""

    def __init__(self, llm_client: AnthropicLLMClient | None = None) -> None:
        self._llm_client = llm_client

    def detect_cold_start(self, user_profile: UserPersona) -> bool:
        """Returns `True` when the user lacks sufficient interaction history."""
        return len(user_profile.history) < 2

    async def handle(
        self,
        user_profile: UserPersona,
        request_context: RequestContext,
        nigerian_mode: bool = False,
    ) -> list[Item]:
        """Builds hybrid cold-start candidates using explicit and default signals."""
        adapter = NigerianContextAdapter(enabled=nigerian_mode)
        
        explicit_preferences = await self._extract_explicit_preferences(user_profile, request_context, nigerian_mode)
        category = (request_context.category or "default").lower()
        
        if nigerian_mode:
            defaults_list = adapter.get_cultural_defaults(category)
            nigerian_defaults = [
                Item(
                    item_id=f"ng-default-{idx}",
                    title=title,
                    category=category if category != "default" else "experience",
                    source="nigerian_default",
                    similarity_score=0.8,
                    metadata={"fallback": True}
                )
                for idx, title in enumerate(defaults_list)
            ]
        else:
            nigerian_defaults = []
            
        popularity_items = self._build_items(POPULARITY_FALLBACKS.get(category, POPULARITY_FALLBACKS["default"]), "popularity")

        weighted_items: dict[str, Item] = {}
        for item in nigerian_defaults:
            item.similarity_score = round(item.similarity_score * 1.0, 4)
            weighted_items[item.item_id] = item
        for item in popularity_items:
            boosted = round(item.similarity_score * 0.9, 4)
            weighted_items[item.item_id] = item.model_copy(update={"similarity_score": boosted})
        for index, (preference, weight) in enumerate(explicit_preferences.items(), start=1):
            item_id = f"explicit-{index}"
            weighted_items[item_id] = Item(
                item_id=item_id,
                title=f"Starter match for {preference}",
                category=category if category != "default" else "experience",
                source="explicit_preference",
                similarity_score=round(min(0.95, 0.55 + (weight * 0.4)), 4),
                metadata={"preference": preference, "weight": weight},
            )
        return sorted(weighted_items.values(), key=lambda item: item.similarity_score, reverse=True)

    async def _extract_explicit_preferences(
        self,
        user_profile: UserPersona,
        request_context: RequestContext,
        nigerian_mode: bool = False,
    ) -> dict[str, float]:
        persona_text = user_profile.persona_text or ""
        if isinstance(user_profile.preferences, dict):
            existing_preferences = user_profile.preferences
        else:
            existing_preferences = {}

        if nigerian_mode and not persona_text and not existing_preferences:
            # Assume user is in Lagos unless stated otherwise
            existing_preferences["location"] = "Lagos, Nigeria"

        client = self._get_llm_client()
        if client is not None and (persona_text or existing_preferences):
            try:
                response = await client.generate_text(
                    system_prompt=TASK_B_COLD_START_SYSTEM,
                    user_prompt=TASK_B_COLD_START_USER.format(
                        persona_text=persona_text or "No persona text provided.",
                        preferences=existing_preferences,
                        request_context=request_context.model_dump(),
                    ),
                    max_tokens=200,
                    temperature=0.25,
                )
                parsed = json.loads(response)
                if isinstance(parsed, dict):
                    return {
                        str(key): max(0.0, min(1.0, float(value)))
                        for key, value in parsed.items()
                    }
            except Exception:
                pass

        fallback_preferences: dict[str, float] = {}
        favorite_categories = existing_preferences.get("favorite_categories")
        if isinstance(favorite_categories, list):
            for category in favorite_categories[:5]:
                fallback_preferences[str(category).lower()] = 0.7
        if request_context.category:
            fallback_preferences[request_context.category.lower()] = 0.78
        if persona_text:
            lowered = persona_text.lower()
            if "spicy" in lowered:
                fallback_preferences["spicy flavors"] = 0.72
            if "thriller" in lowered:
                fallback_preferences["intense storytelling"] = 0.76
            if "lagos" in lowered:
                fallback_preferences["lagos experiences"] = 0.68
        return fallback_preferences

    def _build_items(
        self,
        rows: list[tuple[str, str, str, float]],
        source: str,
    ) -> list[Item]:
        return [
            Item(
                item_id=item_id,
                title=title,
                category=category,
                source=source,
                similarity_score=score,
                metadata={"fallback": True},
            )
            for item_id, title, category, score in rows
        ]

    def _get_llm_client(self) -> AnthropicLLMClient | None:
        if self._llm_client is not None:
            return self._llm_client
        if not getenv("ANTHROPIC_API_KEY"):
            return None
        self._llm_client = AnthropicLLMClient(model=CLAUDE_MODEL_NAME)
        return self._llm_client
