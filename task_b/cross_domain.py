
"""Cross-domain preference transfer for Task B."""

from __future__ import annotations

import json
from os import getenv

from shared.llm_client import AnthropicLLMClient
from shared.prompts import TASK_B_CROSS_DOMAIN_SYSTEM, TASK_B_CROSS_DOMAIN_USER

PreferenceMap = dict[str, float]

CLAUDE_MODEL_NAME = "claude-sonnet-4-20250514"
DOMAIN_BRIDGES = {
    "goodreads:movies": {"intense storytelling": 0.8, "nollywood crime drama": 0.72},
    "goodreads:food": {"bold flavors": 0.76, "spicy dishes": 0.7},
    "books:food": {"immersive ambience": 0.62, "complex flavors": 0.68},
    "books:entertainment": {"character depth": 0.74, "slow-burn tension": 0.69},
}


class CrossDomainBridge:
    """Infers target-domain preferences from another domain using Claude or heuristics."""

    def __init__(self, llm_client: AnthropicLLMClient | None = None) -> None:
        self._llm_client = llm_client

    async def infer_cross_domain_preferences(
        self,
        source_reviews: list[str],
        target_domain: str,
    ) -> PreferenceMap:
        """Builds a weighted preference map for a new domain from source reviews."""
        if not source_reviews:
            return {}

        client = self._get_llm_client()
        if client is not None:
            try:
                response = await client.generate_text(
                    system_prompt=TASK_B_CROSS_DOMAIN_SYSTEM,
                    user_prompt=TASK_B_CROSS_DOMAIN_USER.format(
                        source_reviews="\n".join(f"- {review}" for review in source_reviews[:8]),
                        target_domain=target_domain,
                    ),
                    max_tokens=220,
                    temperature=0.35,
                )
                parsed = json.loads(response)
                if isinstance(parsed, dict):
                    return {
                        str(key): max(0.0, min(1.0, float(value)))
                        for key, value in parsed.items()
                    }
            except Exception:
                pass

        lowered_reviews = " ".join(source_reviews).lower()
        inferred: PreferenceMap = {}
        if "thriller" in lowered_reviews or "dark" in lowered_reviews:
            inferred["intense tone"] = 0.82
        if "history" in lowered_reviews or "literary" in lowered_reviews:
            inferred["cultural depth"] = 0.74
        if "productivity" in lowered_reviews or "self-help" in lowered_reviews:
            inferred["practical value"] = 0.71
        domain_key = f"goodreads:{target_domain.lower()}"
        inferred.update(DOMAIN_BRIDGES.get(domain_key, {}))
        return inferred

    def _get_llm_client(self) -> AnthropicLLMClient | None:
        if self._llm_client is not None:
            return self._llm_client
        if not getenv("ANTHROPIC_API_KEY"):
            return None
        self._llm_client = AnthropicLLMClient(model=CLAUDE_MODEL_NAME)
        return self._llm_client
