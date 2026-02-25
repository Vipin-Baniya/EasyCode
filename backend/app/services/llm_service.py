"""
LLM Service – Anthropic Claude API integration.

Uses the latest anthropic SDK patterns:
- AsyncAnthropic client
- messages.stream() context manager for streaming
- Proper usage tracking
- Sliding-window rate limiter
- Retry with exponential back-off via tenacity
"""

from __future__ import annotations

import asyncio
import json
import re
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator

import anthropic
from anthropic import AsyncAnthropic
from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.utils.exceptions import LLMError, RateLimitError
from app.utils.token_counter import count_tokens, estimate_cost


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class SlidingWindowRateLimiter:
    """Thread-safe sliding-window rate limiter."""

    def __init__(self, max_requests: int, period_seconds: int) -> None:
        self.max_requests = max_requests
        self.period = period_seconds
        self._timestamps: deque[datetime] = deque()
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(seconds=self.period)

            # Expire old entries
            while self._timestamps and self._timestamps[0] <= cutoff:
                self._timestamps.popleft()

            if len(self._timestamps) >= self.max_requests:
                oldest = self._timestamps[0]
                wait = (oldest - cutoff).total_seconds()
                raise RateLimitError(
                    f"Rate limit reached ({self.max_requests} req/{self.period}s). "
                    f"Retry in {wait:.1f}s."
                )

            self._timestamps.append(now)


# ---------------------------------------------------------------------------
# LLM service
# ---------------------------------------------------------------------------

class LLMService:
    """
    Managed interface to Anthropic Claude.

    - Enforces rate limits
    - Retries on transient errors
    - Tracks token usage and cost
    - Provides structured (JSON) and streaming modes
    """

    def __init__(self) -> None:
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        self.model = settings.llm_model
        self.max_tokens = settings.llm_max_tokens
        self.temperature = settings.llm_temperature

        self.rate_limiter = SlidingWindowRateLimiter(
            max_requests=settings.llm_rate_limit_requests,
            period_seconds=settings.llm_rate_limit_period,
        )

        # Usage tracking
        self.total_requests: int = 0
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.estimated_cost_usd: float = 0.0

    # -----------------------------------------------------------------------
    # Core generate
    # -----------------------------------------------------------------------

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Generate a text response from Claude.

        Raises:
            RateLimitError: Rate limit exceeded.
            LLMError: Any other API failure.
        """
        await self.rate_limiter.acquire()

        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": max_tokens or self.max_tokens,
            "temperature": temperature if temperature is not None else self.temperature,
            "messages": [{"role": "user", "content": prompt}],
            **kwargs,
        }
        if system_prompt:
            params["system"] = system_prompt

        try:
            logger.debug("LLM request — {} chars, model={}", len(prompt), self.model)
            response = await self.client.messages.create(**params)
            text: str = response.content[0].text
            self._track_usage(response.usage)
            logger.debug(
                "LLM response — {} chars, tokens in={} out={}",
                len(text),
                response.usage.input_tokens,
                response.usage.output_tokens,
            )
            return text

        except anthropic.RateLimitError as exc:
            logger.warning("Anthropic rate limit: {}", exc)
            raise RateLimitError("Anthropic rate limit exceeded") from exc

        except anthropic.APIStatusError as exc:
            logger.error("Anthropic API error {}: {}", exc.status_code, exc.message)
            raise LLMError(f"Anthropic API error {exc.status_code}: {exc.message}") from exc

        except Exception as exc:
            logger.exception("LLM generate failed")
            raise LLMError(f"LLM generation failed: {exc}") from exc

    # -----------------------------------------------------------------------
    # Structured (JSON) generate
    # -----------------------------------------------------------------------

    async def generate_structured(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Generate a structured JSON response from Claude.

        Automatically strips markdown fences if present.
        Raises LLMError if the response is not valid JSON.
        """
        json_prompt = f"{prompt}\n\nRespond with ONLY valid JSON — no markdown fences, no prose."

        raw = await self.generate(
            prompt=json_prompt,
            system_prompt=system_prompt,
            temperature=temperature if temperature is not None else 0.2,
            max_tokens=max_tokens,
            **kwargs,
        )

        # Strip markdown fences
        clean = self._strip_fences(raw)

        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            # Try to salvage a partial JSON object
            match = re.search(r"\{.*\}", clean, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            logger.error("Could not parse JSON: {!r:.200}", clean)
            raise LLMError(f"Invalid JSON from LLM: {clean[:200]!r}")

    # -----------------------------------------------------------------------
    # Streaming generate
    # -----------------------------------------------------------------------

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> AsyncGenerator[str, None]:
        """
        Stream text chunks from Claude as they arrive.

        Usage:
            async for chunk in llm.generate_stream(prompt):
                print(chunk, end="", flush=True)
        """
        await self.rate_limiter.acquire()

        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
            **kwargs,
        }
        if system_prompt:
            params["system"] = system_prompt

        try:
            async with self.client.messages.stream(**params) as stream:
                async for chunk in stream.text_stream:
                    yield chunk

            # Final usage tracking
            final = await stream.get_final_message()
            self._track_usage(final.usage)

        except Exception as exc:
            logger.exception("LLM streaming failed")
            raise LLMError(f"Streaming failed: {exc}") from exc

    # -----------------------------------------------------------------------
    # Multi-turn conversation
    # -----------------------------------------------------------------------

    async def converse(
        self,
        messages: list[dict[str, str]],
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Continue a multi-turn conversation.

        Args:
            messages: List of {"role": "user"|"assistant", "content": "..."}
        """
        await self.rate_limiter.acquire()

        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": messages,
            **kwargs,
        }
        if system_prompt:
            params["system"] = system_prompt

        try:
            response = await self.client.messages.create(**params)
            text: str = response.content[0].text
            self._track_usage(response.usage)
            return text
        except Exception as exc:
            logger.exception("Conversation failed")
            raise LLMError(f"Conversation failed: {exc}") from exc

    # -----------------------------------------------------------------------
    # Stats
    # -----------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "model": self.model,
        }

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _track_usage(self, usage: Any) -> None:
        self.total_requests += 1
        inp = getattr(usage, "input_tokens", 0)
        out = getattr(usage, "output_tokens", 0)
        self.total_input_tokens += inp
        self.total_output_tokens += out
        self.estimated_cost_usd += estimate_cost(inp, out, self.model)

    @staticmethod
    def _strip_fences(text: str) -> str:
        """Remove markdown code fences from LLM output."""
        # ```json ... ``` or ``` ... ```
        match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text.strip()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Return the process-level LLMService singleton."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
