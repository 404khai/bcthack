"""Anthropic SDK wrapper with simple retry logic."""

from __future__ import annotations

import asyncio
from os import getenv

from anthropic import AnthropicError, AsyncAnthropic


class AnthropicLLMClient:
    """Async Anthropic client with bounded retries for transient errors."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        resolved_api_key = api_key or getenv("ANTHROPIC_API_KEY")
        if not resolved_api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable is required.")
        self.client = AsyncAnthropic(api_key=resolved_api_key)
        self.model = model or getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest")

    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 700,
        temperature: float = 0.3,
        retries: int = 3,
    ) -> str:
        delay_seconds = 1.0
        last_error: Exception | None = None

        for attempt in range(1, retries + 1):
            try:
                response = await self.client.messages.create(
                    model=self.model,
                    system=system_prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                return "".join(
                    block.text for block in response.content if getattr(block, "text", None)
                ).strip()
            except AnthropicError as error:
                last_error = error
                if attempt == retries:
                    break
                await asyncio.sleep(delay_seconds)
                delay_seconds *= 2

        raise RuntimeError("Anthropic text generation failed after retries.") from last_error
