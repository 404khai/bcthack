"""In-memory conversation state manager for multi-turn recommendations."""

from __future__ import annotations


class ConversationManager:
    def __init__(self) -> None:
        self._sessions: dict[str, list[str]] = {}

    def load_history(self, conversation_id: str | None) -> list[str]:
        if not conversation_id:
            return []
        return self._sessions.get(conversation_id, [])

    def save_turn(self, conversation_id: str, user_message: str) -> None:
        self._sessions.setdefault(conversation_id, []).append(user_message)
