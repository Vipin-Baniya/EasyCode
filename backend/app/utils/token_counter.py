"""
Token counting utilities.

Uses tiktoken (cl100k_base encoding) when available,
falls back to a character-based estimate (÷4) otherwise.
"""

from __future__ import annotations

from loguru import logger

_encoder = None


def _get_encoder():
    """Lazy-load tiktoken encoder."""
    global _encoder
    if _encoder is None:
        try:
            import tiktoken
            _encoder = tiktoken.get_encoding("cl100k_base")
        except ImportError:
            logger.debug("tiktoken not installed – using character estimate for token counting")
            _encoder = False  # sentinel: tried but not available
    return _encoder


def count_tokens(text: str) -> int:
    """
    Count tokens in text.

    Uses cl100k_base (Claude/GPT-4 compatible) when tiktoken is installed,
    otherwise estimates as len(text) // 4.
    """
    enc = _get_encoder()
    if enc:
        try:
            return len(enc.encode(text))
        except Exception:
            pass
    # Fallback: approx 4 chars per token
    return max(1, len(text) // 4)


def estimate_cost(input_tokens: int, output_tokens: int, model: str = "claude-sonnet-4-20250514") -> float:
    """
    Estimate API cost in USD.

    Prices as of 2025-02 (claude.ai pricing page).
    """
    pricing: dict[str, tuple[float, float]] = {
        # model: (input $/M tokens, output $/M tokens)
        "claude-sonnet-4-20250514": (3.0, 15.0),
        "claude-opus-4-20250514": (15.0, 75.0),
        "claude-haiku-4-5-20251001": (0.25, 1.25),
    }
    rates = pricing.get(model, (3.0, 15.0))
    return (input_tokens / 1_000_000 * rates[0]) + (output_tokens / 1_000_000 * rates[1])
