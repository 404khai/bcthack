"""Gemini SDK wrapper with simple retry logic, retaining original Anthropic interface."""

from __future__ import annotations

import asyncio
import logging
from os import getenv

import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted

logger = logging.getLogger(__name__)

class AnthropicLLMClient:
    """Async Gemini client masquerading as Anthropic client with bounded retries for transient errors."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        resolved_api_key = api_key or getenv("GEMINI_API_KEY")
        if not resolved_api_key:
            raise ValueError("GEMINI_API_KEY environment variable is required.")
        
        genai.configure(api_key=resolved_api_key)
        self.model = "gemini-2.5-flash"
        self.free_tier_mode = getenv("FREE_TIER_MODE", "false").lower() == "true"

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
                if self.free_tier_mode:
                    await asyncio.sleep(1.0)

                # Initialize model with system instruction
                model_instance = genai.GenerativeModel(
                    model_name=self.model,
                    system_instruction=system_prompt
                )

                def _generate():
                    return model_instance.generate_content(
                        user_prompt,
                        generation_config=genai.types.GenerationConfig(
                            max_output_tokens=max_tokens,
                            temperature=temperature,
                        )
                    )

                response = await asyncio.to_thread(_generate)
                return response.text
            except ResourceExhausted as error:
                last_error = error
                if attempt == retries:
                    break
                logger.warning(f"Rate limit hit. Retrying in {delay_seconds}s...")
                await asyncio.sleep(delay_seconds)
                delay_seconds *= 2
            except Exception as error:
                last_error = error
                if attempt == retries:
                    break
                logger.warning(f"Error calling Gemini API: {error}. Retrying in {delay_seconds}s...")
                await asyncio.sleep(delay_seconds)
                delay_seconds *= 2

        raise RuntimeError("Text generation failed after retries.") from last_error

    # Alias to match exactly what the prompt requested, just in case
    async def complete(self, system: str, user: str, max_tokens: int = 700) -> str:
        return await self.generate_text(system, user, max_tokens=max_tokens)


async def test_connection():
    print("Testing Gemini connection...")
    try:
        client = AnthropicLLMClient()
        response = await client.generate_text("You are a helpful assistant.", "Say hello", max_tokens=50)
        print(f"Response: {response}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
