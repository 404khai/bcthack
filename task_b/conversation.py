
"""In-memory conversation state manager for multi-turn recommendations."""

from __future__ import annotations

import json
from os import getenv

from shared.llm_client import AnthropicLLMClient
from task_b.schemas import Turn

PREFERENCE_SUMMARY_SYSTEM_PROMPT = """You summarize recommendation conversations into weighted preference maps.

Return only valid JSON in the form:
{"attribute_name": weight}

Weights should be floats between 0.0 and 1.0.
"""
PREFERENCE_SUMMARY_USER_TEMPLATE = """Conversation history:
{conversation_history}

Extract the user's refined preferences as a compact preference map.
"""
CLAUDE_MODEL_NAME = "claude-sonnet-4-20250514"


class ConversationManager:
    """Stores session turns in memory and summarizes refined preferences."""

    def __init__(self, llm_client: AnthropicLLMClient | None = None) -> None:
        self._sessions: dict[str, list[Turn]] = {}
        self._llm_client = llm_client

    def add_turn(
        self,
        session_id: str,
        user_msg: str,
        assistant_msg: str,
        context: dict[str, object],
    ) -> None:
        """Adds a new conversational turn for a session."""
        self._sessions.setdefault(session_id, []).append(
            Turn(user_message=user_msg, assistant_message=assistant_msg, context=context)
        )

    def get_history(self, session_id: str) -> list[Turn]:
        """Returns the stored history for a session."""
        return list(self._sessions.get(session_id, []))

    async def extract_refined_preferences(self, session_id: str) -> dict[str, float]:
        """Summarizes conversation signals into a weighted preference map."""
        history = self.get_history(session_id)
        if not history:
            return {}

        client = self._get_llm_client()
        history_text = "\n".join(
            f"User: {turn.user_message}\nAssistant: {turn.assistant_message}\nContext: {turn.context}"
            for turn in history
        )
        if client is not None:
            try:
                response = await client.generate_text(
                    system_prompt=PREFERENCE_SUMMARY_SYSTEM_PROMPT,
                    user_prompt=PREFERENCE_SUMMARY_USER_TEMPLATE.format(
                        conversation_history=history_text
                    ),
                    max_tokens=180,
                    temperature=0.2,
                )
                parsed = json.loads(response)
                if isinstance(parsed, dict):
                    return {
                        str(key): max(0.0, min(1.0, float(value)))
                        for key, value in parsed.items()
                    }
            except Exception:
                pass

        preference_counts: dict[str, float] = {}
        for turn in history:
            for constraint in turn.context.get("constraints", []):
                key = str(constraint).lower()
                preference_counts[key] = min(1.0, preference_counts.get(key, 0.0) + 0.3)
            category = turn.context.get("category")
            if category:
                key = str(category).lower()
                preference_counts[key] = min(1.0, preference_counts.get(key, 0.0) + 0.4)
        return preference_counts

    def clear_session(self, session_id: str) -> None:
        """Removes a session and all of its stored turns."""
        self._sessions.pop(session_id, None)

    def _get_llm_client(self) -> AnthropicLLMClient | None:
        if self._llm_client is not None:
            return self._llm_client
        if not getenv("ANTHROPIC_API_KEY"):
            return None
        self._llm_client = AnthropicLLMClient(model=CLAUDE_MODEL_NAME)
        return self._llm_client
