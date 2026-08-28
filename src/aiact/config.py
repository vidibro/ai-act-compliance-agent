"""Runtime configuration via pydantic-settings.

Settings are read from environment variables (prefix AIACT_) and an optional .env file.
Only what the schema layer and near-future layers need is declared here; provider wiring
(LangGraph, Chroma, LiteLLM, Langfuse) is added as those layers are built.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AIACT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM provider (LiteLLM routes by this model string). The request SHAPE for whatever this
    # names is resolved at call time by aiact.providers — vendors disagree on sampling, reasoning
    # depth, and caching, so none of it is hardcoded in the brain.
    llm_model: str = "anthropic/claude-haiku-4-5"
    # Reasoning depth, for providers that expose it. Ignored by profiles that have no such knob.
    #
    # Portable vocabulary: "high" | "medium" | "low" | "none". Each provider profile translates it
    # into that vendor's own shape — "none" is NOT passed through as a literal, because it means
    # different things per vendor and is impossible on some (see providers.py).
    llm_effort: str = "none"

    # Per-job overrides, because the two jobs measured in opposite directions.
    classify_effort: str | None = None
    judge_effort: str | None = None

    def effort_for(self, job: Literal["classify", "judge", "grade"]) -> str:
        """Reasoning depth for one job, falling back to the shared default."""
        override = {
            "classify": self.classify_effort,
            "judge": self.judge_effort,
            "grade": self.grader_effort,
        }[job]
        return override or self.llm_effort

    grader_model: str = ""
    grader_effort: str | None = None

    def model_for_grading(self) -> str:
        """The grader's model, falling back to the shared default."""
        return self.grader_model or self.llm_model

    # Optional LiteLLM PROXY in front of the provider. Empty = talk to the vendor directly.
    llm_api_base: str = Field(
        default="",
        validation_alias=AliasChoices("AIACT_LLM_API_BASE", "LITELLM_PROXY_URL"),
    )

    # Vector store (Chroma, local). Retrieval indexes the document being CHECKED, not the law.
    chroma_path: str = "./chroma"

    # Policy / reproducibility.
    act_version_date: date = date(2026, 7, 27)
    policy_spec_path: str = "./data/policy/spec.yaml"
    # Literal article text, fetched by scripts/fetch_articles.py. The SINGLE store of enacted
    # wording: rules cite a provision, the loader resolves the text from here. Never duplicated
    # into the spec.
    policy_articles_path: str = "./data/policy/articles"
    # Verbatim annex text (Annex III = the high-risk areas, Annex IV = the Art. 11 checklist).
    policy_annexes_path: str = "./data/policy/annexes"
    # Versioned normative-assurance inputs, generated artifacts, and report. The runtime pipeline
    # does not consume them; assurance loaders and checks resolve the active Act version here.
    policy_normative_coverage_path: str = "./data/policy/normative-coverage"


def get_settings() -> Settings:
    """Construct Settings from the environment. Kept as a function so later layers can wrap it
    with caching without changing call sites."""
    return Settings()
