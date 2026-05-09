"""Simple heuristic rating predictor for the scaffold phase."""

from __future__ import annotations

from statistics import mean

from task_a.schemas import PersonaInput


class RatingPredictor:
    def predict(self, persona: PersonaInput) -> float:
        if not persona.history:
            return 4.0
        predicted = mean(entry.rating for entry in persona.history)
        return round(min(5.0, max(1.0, predicted)), 1)
