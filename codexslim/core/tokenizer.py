"""
Token counting and savings reporting.

Supports OpenAI (tiktoken) and a character-based approximation for
Anthropic models (exact Anthropic tokenizer is not publicly available
as a standalone package at time of writing).
"""

from __future__ import annotations

from dataclasses import dataclass

try:
    import tiktoken
    _TIKTOKEN_AVAILABLE = True
except ImportError:  # pragma: no cover
    _TIKTOKEN_AVAILABLE = False

# Approximate tokens per character for Claude models (empirical average)
_ANTHROPIC_CHARS_PER_TOKEN = 3.5


@dataclass
class TokenReport:
    """Token count comparison between original and slim output."""

    original_tokens: int
    slim_tokens: int
    savings_pct: float
    tokenizer: str

    def __str__(self) -> str:
        return (
            f"[{self.tokenizer}] "
            f"{self.original_tokens:,} → {self.slim_tokens:,} tokens "
            f"({self.savings_pct:.1f}% saved)"
        )


def count_openai(text: str, model: str = "gpt-4o") -> int:
    """Count tokens using tiktoken (OpenAI encoding)."""
    if not _TIKTOKEN_AVAILABLE:
        raise RuntimeError("tiktoken is not installed. Run: pip install tiktoken")
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))


def count_anthropic_approx(text: str) -> int:
    """Approximate token count for Anthropic/Claude models."""
    return max(1, int(len(text) / _ANTHROPIC_CHARS_PER_TOKEN))


def report(
    original: str,
    slim: str,
    tokenizer: str = "openai",
) -> TokenReport:
    """
    Produce a TokenReport comparing original and slim token counts.

    Args:
        original:  Raw source text.
        slim:      Skeletonized source text.
        tokenizer: "openai" | "anthropic" | "both"

    Returns:
        TokenReport (or a list of two if tokenizer="both").
    """
    if tokenizer == "openai":
        orig_count = count_openai(original)
        slim_count = count_openai(slim)
        label = "openai/gpt-4o"
    elif tokenizer == "anthropic":
        orig_count = count_anthropic_approx(original)
        slim_count = count_anthropic_approx(slim)
        label = "anthropic/approx"
    else:
        raise ValueError(f"Unknown tokenizer: {tokenizer!r}. Use 'openai' or 'anthropic'.")

    savings = 100.0 * (orig_count - slim_count) / max(orig_count, 1)
    return TokenReport(
        original_tokens=orig_count,
        slim_tokens=slim_count,
        savings_pct=round(savings, 1),
        tokenizer=label,
    )


def report_both(original: str, slim: str) -> list[TokenReport]:
    """Return token reports for both OpenAI and Anthropic tokenizers."""
    reports = []
    if _TIKTOKEN_AVAILABLE:
        reports.append(report(original, slim, "openai"))
    reports.append(report(original, slim, "anthropic"))
    return reports


class Tokenizer:
    """Wrapper class for token counting orchestration."""
    
    def count(self, original: str, slim: str, backend: str = "openai") -> list[TokenReport]:
        """Count tokens using the specified backend."""
        if backend == "both":
            return report_both(original, slim)
        return [report(original, slim, tokenizer=backend)]

