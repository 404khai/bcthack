"""Creates a compact writing-style fingerprint from prior reviews."""

from __future__ import annotations

from statistics import mean

from task_a.schemas import PersonaInput


class PersonaBuilder:
    def build_style_fingerprint(self, persona: PersonaInput) -> dict[str, float | int | bool]:
        word_counts = [len(review.text.split()) for review in persona.history if review.text]
        rating_values = [review.rating for review in persona.history]
        return {
            "review_count": len(persona.history),
            "avg_words": round(mean(word_counts), 2) if word_counts else 0.0,
            "avg_rating": round(mean(rating_values), 2) if rating_values else 0.0,
            "uses_first_person": any(" i " in f" {review.text.lower()} " for review in persona.history),
            "uses_exclamation": any("!" in review.text for review in persona.history),
        }
