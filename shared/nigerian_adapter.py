"""Utilities for optional Nigerian contextualization."""

from __future__ import annotations

from dataclasses import dataclass
from os import getenv


@dataclass(slots=True)
class NigerianContextAdapter:
    enabled: bool = False

    @classmethod
    def from_env(cls) -> "NigerianContextAdapter":
        raw_value = getenv("NIGERIAN_MODE", "false").strip().lower()
        return cls(enabled=raw_value in {"1", "true", "yes", "on"})

    def adapt_text(self, text: str) -> str:
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
        if "jollof" not in adapted.lower():
            adapted = f"{adapted} It even has that jollof-level comfort factor."
        return adapted

    def adapt_category(self, category: str) -> str:
        if not self.enabled:
            return category
        mappings = {
            "grocery": "supermarket",
            "online retail": "Jumia-style marketplace",
            "barbecue": "suya spot",
            "restaurant": "buka",
        }
        return mappings.get(category.lower(), category)
