"""Gemini SDK wrapper with simple retry logic."""

from __future__ import annotations

from dotenv import load_dotenv
load_dotenv(override=True)

import asyncio
import logging
from os import getenv

from google import genai
from google.genai import types
from google.api_core.exceptions import ResourceExhausted

logger = logging.getLogger(__name__)


class GeminiLLMClient:
    """Async Gemini client with bounded retries for transient errors."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        resolved_api_key = api_key or getenv("GEMINI_API_KEY")
        if not resolved_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. "
                "Ensure it exists in your .env file and load_dotenv() runs first."
            )
        
        self.client = genai.Client(api_key=resolved_api_key)
        self.model = "gemini-2.5-flash"
        self.free_tier_mode = getenv("FREE_TIER_MODE", "false").lower() == "true"
        self.last_finish_reason: str | None = None
        self.last_response_length: int = 0
        logger.info("[LLM] Gemini client initialized with key: %s...", resolved_api_key[:8])

    async def generate_text(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.3,
        retries: int = 3,
    ) -> str:
        delay_seconds = 1.0
        last_error: Exception | None = None
        effective_max_tokens = max(max_tokens, 1024)

        for attempt in range(1, retries + 1):
            try:
                if self.free_tier_mode:
                    await asyncio.sleep(1.0)
                logger.info("[LLM] Sending request: max_output_tokens=%d", effective_max_tokens)

                def _generate():
                    return self.client.models.generate_content(
                        model=self.model,
                        contents=user_prompt,
                        config=types.GenerateContentConfig(
                            system_instruction=system_prompt,
                            max_output_tokens=effective_max_tokens,
                            temperature=temperature,
                        )
                    )

                response = await asyncio.to_thread(_generate)
                full_text = response.text or ""
                finish_reason = None
                candidates = getattr(response, "candidates", None) or []
                if candidates:
                    finish_reason = getattr(candidates[0], "finish_reason", None)
                self.last_finish_reason = str(finish_reason) if finish_reason is not None else None
                self.last_response_length = len(full_text)
                logger.info(
                    "[LLM] Response: %d chars, finish_reason=%s",
                    len(full_text),
                    finish_reason,
                )
                if str(finish_reason) in ("MAX_TOKENS", "2"):
                    logger.warning(
                        "[LLM] TRUNCATED by token limit — increase max_output_tokens"
                    )
                return full_text
            except ResourceExhausted as error:
                last_error = error
                if attempt == retries:
                    break
                logger.warning(f"Rate limit hit. Retrying in {delay_seconds}s...")
                await asyncio.sleep(delay_seconds)
                delay_seconds *= 2
            except Exception as error:
                # Also handle 429 errors that might not be caught by ResourceExhausted
                error_str = str(error).lower()
                is_rate_limit = "429" in error_str or "quota" in error_str or "exhausted" in error_str
                
                last_error = error
                if attempt == retries:
                    break
                    
                if is_rate_limit:
                    logger.warning(f"Rate limit hit. Retrying in {delay_seconds}s...")
                else:
                    logger.warning(f"Error calling Gemini API: {error}. Retrying in {delay_seconds}s...")
                    
                await asyncio.sleep(delay_seconds)
                delay_seconds *= 2

        raise RuntimeError("Text generation failed after retries.") from last_error

    async def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        return await self.generate_text(system, user, max_tokens=max_tokens)


# Backward-compatible alias for older imports that still reference the old name.
AnthropicLLMClient = GeminiLLMClient


async def test_connection():
    print("Testing Gemini connection...")
    try:
        client = GeminiLLMClient()
        response = await client.complete("You are a helpful assistant.", "Say hello", max_tokens=50)
        print(f"Response: {response}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_connection())
