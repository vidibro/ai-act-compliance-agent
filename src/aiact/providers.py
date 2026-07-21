"""The PROVIDER SEAM — how to shape a completion request for a given model.

LiteLLM normalises the *call*, not the *parameters*. `litellm.completion(model=...)` reaches any
provider, but what you may put in that call differs sharply:

  - Anthropic's current models REJECT `temperature` / `top_p` / `top_k` outright (400), and expose
    reasoning depth as `thinking={"type": "adaptive"}` + `output_config={"effort": ...}`.
  - Older Anthropic models accept `temperature` and have no adaptive-thinking parameter.
  - Other vendors accept `temperature`, and express reasoning depth (where they have it) under
    different names with different value spaces.
  - Prompt caching is not portable at all: Anthropic takes an inline `cache_control` marker on a
    content block; other providers cache automatically with no control surface, or via a separate
    API that takes no such marker.

Putting any of that directly in LLMBrain would hardcode one vendor's request shape into the class
whose whole point is that the model is config, not code. So it lives here, keyed by model, and the
brain just splats whatever it is handed.

`verified` is deliberate: a profile is only True once its parameter shape has been checked against
that provider's current documentation. An unverified profile is the conservative fallback — plain
`temperature`, no caching, no reasoning parameters — which works everywhere and wastes money
nowhere it would break. Fill one in when you have checked it, not when you assume it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Anthropic models on the adaptive-thinking request surface: sampling parameters removed,
# reasoning depth via thinking + effort. Verified against Anthropic's model documentation.
_ANTHROPIC_ADAPTIVE = (
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-sonnet-5",
    "claude-fable-5",
    "claude-mythos-5",
)

# Anthropic's minimum cacheable prefix, in tokens. Below it a cache_control marker is silently
# ignored — no error, just no cache. 4096 is the Opus 4.8 figure; it is the largest in the family,
# so using it for the whole group under-caches rather than mis-caches.
_ANTHROPIC_CACHE_MIN_TOKENS = 4096
_ANTHROPIC_LEGACY_CACHE_MIN_TOKENS = 2048


@dataclass(frozen=True)
class ProviderProfile:
    """Everything model-specific about how a completion request is built."""

    profile_id: str
    completion_kwargs: dict[str, Any] = field(default_factory=dict)
    """Splatted into litellm.completion(). Provider-specific by definition."""

    supports_cache_control: bool = False
    """Whether this provider takes an inline cache breakpoint on a content block."""

    cache_min_tokens: int = 0
    """Below this, a cache marker is silently ignored — so we do not bother emitting one."""

    verified: bool = False
    """False = nobody has checked this shape against the provider's current docs. Stay conservative
    until someone has."""

    notes: str = ""

    def caches(self, text: str) -> bool:
        """Whether marking `text` as a cache breakpoint would actually do anything."""
        return self.supports_cache_control and estimate_tokens(text) >= self.cache_min_tokens


def estimate_tokens(text: str) -> int:
    """Rough token estimate — 4 chars per token.

    Only used to decide whether a prefix clears a provider's cache minimum, where being wrong
    costs a missed cache rather than a wrong answer. Do not use it for billing or context budgets;
    count tokens with the provider's own endpoint for that."""
    return len(text) // 4


def profile_for(model: str, effort: str = "high") -> ProviderProfile:
    """Resolve the request shape for a LiteLLM model string (e.g. 'anthropic/claude-opus-4-8')."""
    name = model.split("/")[-1]

    if any(name.startswith(prefix) for prefix in _ANTHROPIC_ADAPTIVE):
        return ProviderProfile(
            profile_id="anthropic-adaptive",
            completion_kwargs={
                "thinking": {"type": "adaptive"},
                "output_config": {"effort": effort},
            },
            supports_cache_control=True,
            cache_min_tokens=_ANTHROPIC_CACHE_MIN_TOKENS,
            verified=True,
            notes=(
                "temperature/top_p/top_k are REJECTED (400) — deliberately absent. Thinking is off "
                "unless asked for: omitting the parameter means no thinking, so it is set "
                "explicitly. Determinism comes from low effort + a tight prompt, not sampling."
            ),
        )

    if name.startswith("claude-"):
        return ProviderProfile(
            profile_id="anthropic-legacy",
            completion_kwargs={"temperature": 0.0},
            supports_cache_control=True,
            cache_min_tokens=_ANTHROPIC_LEGACY_CACHE_MIN_TOKENS,
            verified=True,
            notes="Accepts temperature; no adaptive-thinking parameter.",
        )

    return ProviderProfile(
        profile_id="generic",
        completion_kwargs={"temperature": 0.0},
        supports_cache_control=False,
        verified=False,
        notes=(
            "UNVERIFIED fallback. Sends only what every provider accepts. Reasoning-depth and "
            "caching parameters are omitted because their names and shapes have not been checked "
            "for this provider — omitting them costs money, guessing them costs a 400."
        ),
    )
