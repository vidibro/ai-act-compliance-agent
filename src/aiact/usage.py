"""Token usage and cost.

Per-run cost is the number that compounds across a repeatedly-run eval, and it is a product number
too: under BYOK the caller pays per report. LiteLLM returns `usage` on every response.

Everything here is labelled ESTIMATED and means it:
  - Prices are transcribed from vendor pricing pages on the date below. They drift. A model with no
    entry reports tokens and NO cost — never a silent $0, which would read as "free".
  - Providers differ in whether `prompt_tokens` already includes cached-prefix tokens. We assume it
    does and discount the cached share, which is right for the providers we price today but is an
    assumption, not a guarantee.
Use these figures to compare runs and catch order-of-magnitude surprises, not to reconcile a bill.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

PRICES_AS_OF = "2026-07-21"

_MTOK = 1_000_000
_CACHE_WRITE_MULTIPLIER = 1.25  # Anthropic charges a premium to write the cache


@dataclass(frozen=True)
class ModelPrice:
    """USD per million tokens."""

    input_per_mtok: float
    output_per_mtok: float
    cached_input_per_mtok: float | None = None
    note: str = ""


# Keyed by the bare model name (provider prefix stripped), matched longest-first.
PRICES: dict[str, ModelPrice] = {
    # Anthropic
    "claude-haiku-4-5": ModelPrice(1.00, 5.00, 0.10),
    "claude-opus-4-8": ModelPrice(5.00, 25.00, 0.50),
    "claude-opus-4-7": ModelPrice(5.00, 25.00, 0.50),
    "claude-sonnet-5": ModelPrice(3.00, 15.00, 0.30, note="intro $2/$10 through 2026-08-31"),
    "claude-fable-5": ModelPrice(10.00, 50.00, 1.00),
    # OpenAI
    "gpt-5.6-sol": ModelPrice(5.00, 30.00, 0.50),
    "gpt-5.6-terra": ModelPrice(2.50, 15.00, 0.25),
    "gpt-5.6-luna": ModelPrice(1.00, 6.00, 0.10),
    # Google
    "gemini-3.1-pro": ModelPrice(2.00, 12.00, note="rises to $4/$18 above 200K context"),
    "gemini-3.5-flash": ModelPrice(1.50, 9.00),
    "gemini-3-flash": ModelPrice(0.50, 3.00),
    "gemini-2.5-pro": ModelPrice(1.25, 10.00, 0.31, note="$2.50/$15 above 200K context"),
    "gemini-2.5-flash": ModelPrice(0.30, 2.50, 0.075),
    "gemini-2.5-flash-lite": ModelPrice(0.10, 0.40, 0.025),
    # Mistral
    "mistral-large-3": ModelPrice(0.50, 1.50),
    "mistral-medium-3": ModelPrice(0.40, 2.00),
}


def price_for(model: str) -> ModelPrice | None:
    """Longest-prefix match, so 'gemini-3.5-flash' never resolves to 'gemini-3-flash'."""
    name = model.rpartition("/")[2]
    matches = [key for key in PRICES if name.startswith(key)]
    if not matches:
        return None
    return PRICES[max(matches, key=len)]


@dataclass
class Usage:
    """Running tally for one model over one run. Mutable by design — it accumulates."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    cache_creation_tokens: int = 0
    """Tokens WRITTEN to cache. Tracked separately from reads: without it, "written but never
    read" and "never cached at all" look identical."""

    cache_marked_calls: int = 0
    """Calls where we asked for caching. If this is non-zero and both counters above are zero, the
    provider ignored the marker — say so instead of reporting a clean-looking run."""

    unpriced_calls: int = 0
    """Responses that carried no usage block — counted so a partial tally
    cannot pass itself off as a complete one."""

    _lock: Any = field(default_factory=threading.Lock, repr=False, compare=False)
    """The eval judges on a thread pool and every worker lands here; `+=` on an int is
    read-modify-write, so the counts would under-report without it."""

    def record(self, response: Any, cache_marked: bool = False) -> None:
        """Pull whatever the provider reported off a LiteLLM response. Defensive throughout:
        a missing usage block must not crash a classification run."""
        with self._lock:
            self._record(response, cache_marked)

    def _record(self, response: Any, cache_marked: bool = False) -> None:
        self.calls += 1
        self.cache_marked_calls += int(cache_marked)
        usage = getattr(response, "usage", None)
        if usage is None:
            self.unpriced_calls += 1
            return
        self.input_tokens += int(getattr(usage, "prompt_tokens", 0) or 0)
        self.output_tokens += int(getattr(usage, "completion_tokens", 0) or 0)
        self.cached_input_tokens += _cached_tokens(usage)
        self.cache_creation_tokens += _cache_creation_tokens(usage)

    @property
    def cache_was_ignored(self) -> bool:
        """We asked for caching on every marked call and the provider never wrote or read a byte."""
        return bool(self.cache_marked_calls) and not (
            self.cached_input_tokens or self.cache_creation_tokens
        )

    def estimated_cost_usd(self, model: str) -> float | None:
        """None means we have no price on file — report that, never a silent zero."""
        price = price_for(model)
        if price is None:
            return None
        cached = self.cached_input_tokens if price.cached_input_per_mtok is not None else 0
        written = self.cache_creation_tokens
        full_price_input = max(self.input_tokens - cached - written, 0)
        cost = full_price_input / _MTOK * price.input_per_mtok
        cost += self.output_tokens / _MTOK * price.output_per_mtok
        # Cache WRITES are charged at a premium (1.25x input on Anthropic), so a run that only ever
        # writes is more expensive than not caching at all. Counting it keeps that visible.
        cost += written / _MTOK * price.input_per_mtok * _CACHE_WRITE_MULTIPLIER
        if cached:
            assert price.cached_input_per_mtok is not None
            cost += cached / _MTOK * price.cached_input_per_mtok
        return cost + 0.0

    def summary(self, model: str) -> str:
        cost = self.estimated_cost_usd(model)
        money = f"~${cost:.4f}" if cost is not None else "cost unknown (no price on file)"
        cached = ""
        if self.cached_input_tokens or self.cache_creation_tokens:
            cached = (
                f", cache {self.cached_input_tokens:,} read / "
                f"{self.cache_creation_tokens:,} written"
            )
        missing = (
            f", {self.unpriced_calls} call(s) reported no usage" if self.unpriced_calls else ""
        )
        line = (
            f"{money} estimated — {self.calls} calls, "
            f"{self.input_tokens:,} in{cached} / {self.output_tokens:,} out tokens{missing}"
        )
        if self.cache_was_ignored:
            line += (
                f"\n  ! cache marker sent on {self.cache_marked_calls} call(s) and IGNORED — "
                f"prefix is below this model's minimum cacheable size. No saving is being made."
            )
        return line


def _cache_creation_tokens(usage: Any) -> int:
    """Cached-prefix WRITES. Spelled differently again by provider."""
    direct = getattr(usage, "cache_creation_input_tokens", None)
    if direct:
        return int(direct)
    details = getattr(usage, "prompt_tokens_details", None)
    if details is not None:
        return int(getattr(details, "cache_creation_tokens", 0) or 0)
    return 0


def _cached_tokens(usage: Any) -> int:
    """Cached-prefix reads. Providers spell this differently, and some not at all."""
    direct = getattr(usage, "cache_read_input_tokens", None)
    if direct:
        return int(direct)
    details = getattr(usage, "prompt_tokens_details", None)
    if details is not None:
        return int(getattr(details, "cached_tokens", 0) or 0)
    return 0
