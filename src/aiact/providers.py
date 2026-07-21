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

THE TRAP THIS MODULE EXISTS FOR: LiteLLM DOES normalise `reasoning_effort` across OpenAI, Gemini
and Mistral — but for Anthropic it translates it into `thinking={"type": "enabled",
"budget_tokens": N}`, which is exactly the shape Anthropic's current models REJECT with a 400. So
the one parameter that looks portable is the one that must never be used uniformly. Anthropic gets
`thinking={"type": "adaptive"}` written out explicitly; everyone else gets `reasoning_effort`.

`verified` is deliberate: a profile is only True once its parameter shape has been checked against
that provider's current documentation. An unverified profile is the conservative fallback — plain
`temperature`, no caching, no reasoning parameters — which works everywhere and wastes money
nowhere it would break. Fill one in when you have checked it, not when you assume it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Anthropic models on the adaptive-thinking request surface: sampling parameters removed,
# reasoning depth via thinking + effort.
_ANTHROPIC_ADAPTIVE = (
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-sonnet-5",
    "claude-fable-5",
    "claude-mythos-5",
)

# OpenAI's reasoning family rejects temperature/top_p the same way Anthropic's does; depth is
# `reasoning_effort`. (The gpt-4.x family still accepts temperature — hence the split.)
_OPENAI_REASONING = ("gpt-5", "o1", "o3", "o4")

# Anthropic's minimum cacheable prefix, in TOKENS. Below it a cache_control marker is silently
# ignored — no error, no cache, no signal. Per-model because the family spans 1024-4096 and
# guessing high means silently losing a cache we could have had.
_ANTHROPIC_CACHE_MIN = {
    "claude-opus-4-8": 4096,
    "claude-opus-4-7": 4096,
    "claude-opus-4-6": 4096,
    "claude-opus-4-5": 4096,
    "claude-haiku-4-5": 4096,
    "claude-fable-5": 2048,
    "claude-sonnet-4-6": 2048,
    "claude-sonnet-4-5": 1024,
}
_ANTHROPIC_CACHE_MIN_DEFAULT = 4096  # conservative for an unlisted Claude model


def _anthropic_cache_min(name: str) -> int:
    for prefix, minimum in _ANTHROPIC_CACHE_MIN.items():
        if name.startswith(prefix):
            return minimum
    return _ANTHROPIC_CACHE_MIN_DEFAULT


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
        """Whether to mark `text` as a cache breakpoint.

        Deliberately does NOT gate on cache_min_tokens. A marker on a too-short prefix is silently
        ignored at zero cost — no error, no write, no charge — whereas skipping a marker that WOULD
        have qualified silently loses the saving. The asymmetry says: always try where the provider
        supports it, and let the usage counters report what actually happened. `cache_min_tokens`
        is kept for diagnosis, not for gating; an estimate is not a good enough reason to opt out
        of a saving (ours was wrong by 19% and cost us exactly that)."""
        return self.supports_cache_control and bool(text)


# MEASURED against this corpus, not assumed: 17,589 chars of Article 3 came back as 3,800 prompt
# tokens from Anthropic. The earlier 4.0 guess over-counted by ~19% — enough to convince us a
# prefix cleared a 4096-token minimum when it did not, so every cache marker we emitted was
# silently ignored. Statutory text compresses well (heavy repeated boilerplate), the opposite of
# the intuition that dense numbering tokenises badly.
_CHARS_PER_TOKEN = 4.75


def estimate_tokens(text: str) -> int:
    """Rough token estimate, for DIAGNOSTICS only — never for billing or context budgets.

    Real counts come from the provider's own usage block; use those. This exists so we can say
    "your prefix is around N tokens and this model needs M" when caching silently does nothing."""
    return int(len(text) / _CHARS_PER_TOKEN)


def profile_for(model: str, effort: str = "high") -> ProviderProfile:
    """Resolve the request shape for a LiteLLM model string (e.g. 'anthropic/claude-opus-4-8')."""
    provider, _, bare = model.rpartition("/")
    name = bare

    if any(name.startswith(prefix) for prefix in _ANTHROPIC_ADAPTIVE):
        return ProviderProfile(
            profile_id="anthropic-adaptive",
            completion_kwargs={
                "thinking": {"type": "adaptive"},
                "output_config": {"effort": effort},
            },
            supports_cache_control=True,
            cache_min_tokens=_anthropic_cache_min(name),
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
            cache_min_tokens=_anthropic_cache_min(name),
            verified=True,
            notes=(
                "Accepts temperature; has no adaptive-thinking or effort parameter (Haiku 4.5 and "
                "Sonnet 4.5 error on effort). Do NOT reach for reasoning_effort here — see below."
            ),
        )

    if provider == "openai" and any(name.startswith(p) for p in _OPENAI_REASONING):
        return ProviderProfile(
            profile_id="openai-reasoning",
            completion_kwargs={"reasoning_effort": effort},
            supports_cache_control=False,
            verified=True,
            notes=(
                "temperature/top_p are rejected on the reasoning family whenever reasoning is "
                "active — same trap as Anthropic's, different error text. Depth is "
                "`reasoning_effort`. Prompt caching is AUTOMATIC with no control surface, so there "
                "is no breakpoint to place: our stable-prefix-first prompt layout still helps it, "
                "we just cannot mark it."
            ),
        )

    if provider == "openai":
        return ProviderProfile(
            profile_id="openai-classic",
            completion_kwargs={"temperature": 0.0},
            supports_cache_control=False,
            verified=True,
            notes="The gpt-4.x family still accepts sampling parameters and has no reasoning knob.",
        )

    if provider in ("gemini", "vertex_ai"):
        return ProviderProfile(
            profile_id="google-gemini",
            completion_kwargs={"reasoning_effort": effort},
            supports_cache_control=False,
            verified=True,
            notes=(
                "LiteLLM maps reasoning_effort onto Gemini's thinking_level. temperature is "
                "deliberately omitted: Gemini 3 is tuned around its default and lowering it is "
                "documented as counter-productive. Caching exists but as a SEPARATE explicit API, "
                "not an inline marker — nothing to place here."
            ),
        )

    if provider == "mistral":
        return ProviderProfile(
            profile_id="mistral",
            completion_kwargs={"temperature": 0.0},
            supports_cache_control=False,
            verified=True,
            notes=(
                "Accepts temperature. Reasoning depth applies only to the reasoning-tuned models "
                "(Magistral), not to Large/Medium — so it is not sent here. EU-hosted: the reason "
                "this vendor is on the list at all for an EU-regulation compliance tool."
            ),
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
