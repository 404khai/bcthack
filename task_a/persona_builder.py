
"""Builds stylistic fingerprints from raw persona review history."""

from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

from shared.user_profile import ReviewRecord, StyleFingerprint, build_style_fingerprint
from task_a.schemas import ReviewHistoryEntry, UserPersona

PIDGIN_TERMS = {
    "abeg",
    "dey",
    "no",
    "oga",
    "sha",
    "wahala",
    "wetin",
}
LOCAL_REFERENCES = {
    "abuja",
    "ibadan",
    "ikeja",
    "jumia",
    "lagos",
    "naija",
    "shoprite",
    "suya",
    "yaba",
    "jollof",
}
TOKEN_PATTERN = re.compile(r"[A-Za-z']+")


class PersonaBuilder:
    """Derives a `StyleFingerprint` using lightweight NLP heuristics."""

    def build(self, user_id: str, review_history: Iterable[ReviewHistoryEntry]) -> StyleFingerprint:
        """Builds a style fingerprint for a given user from historical reviews."""
        records = [
            ReviewRecord(
                review_id=f"{user_id}-history-{index}",
                item_id=entry.item_id,
                source="task_a",
                rating=entry.rating,
                review_text=entry.text,
                category=entry.category,
                created_at=entry.created_at,
                metadata=entry.attributes,
            )
            for index, entry in enumerate(review_history, start=1)
        ]
        fingerprint = build_style_fingerprint(records)
        merged_signals = sorted(set(fingerprint.nigerian_signals) | self._detect_nigerian_signals(review_history))
        return StyleFingerprint(
            avg_rating=fingerprint.avg_rating,
            rating_std=fingerprint.rating_std,
            avg_review_length=fingerprint.avg_review_length,
            vocabulary_size=fingerprint.vocabulary_size,
            top_phrases=fingerprint.top_phrases,
            sentiment_profile=fingerprint.sentiment_profile,
            formality_score=fingerprint.formality_score,
            nigerian_signals=merged_signals,
        )

    def from_persona(self, persona: UserPersona) -> StyleFingerprint:
        """Builds a style fingerprint directly from a Task A persona payload."""
        return self.build(persona.user_id, persona.review_history)

    def _detect_nigerian_signals(self, review_history: Iterable[ReviewHistoryEntry]) -> set[str]:
        """Finds Nigerian pidgin markers and local references in the review corpus."""
        token_counter: Counter[str] = Counter()
        for entry in review_history:
            tokens = [match.group(0).lower() for match in TOKEN_PATTERN.finditer(entry.text)]
            token_counter.update(tokens)
        candidates = set(token_counter) & (PIDGIN_TERMS | LOCAL_REFERENCES)
        return candidates
