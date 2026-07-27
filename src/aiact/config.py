"""Runtime configuration via pydantic-settings.

Settings are read from environment variables (prefix AIACT_) and an optional .env file.
Only what the schema layer and near-future layers need is declared here; provider wiring
(LangGraph, Chroma, LiteLLM, Langfuse) is added as those layers are built.
"""

from __future__ import annotations

from datetime import date

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
    llm_effort: str = "high"

    # Vector store (Chroma, local). Retrieval indexes the document being CHECKED, not the law.
    chroma_path: str = "./chroma"

    # Policy / reproducibility.
    act_version_date: date = date(2024, 7, 12)
    policy_spec_path: str = "./data/policy/spec.yaml"
    # Literal article text, fetched by scripts/fetch_articles.py. The SINGLE store of enacted
    # wording: rules cite a provision, the loader resolves the text from here. Never duplicated
    # into the spec.
    policy_articles_path: str = "./data/policy/articles"
    # Verbatim annex text (Annex III = the high-risk areas, Annex IV = the Art. 11 checklist).
    policy_annexes_path: str = "./data/policy/annexes"


def get_settings() -> Settings:
    """Construct Settings from the environment. Kept as a function so later layers can wrap it
    with caching without changing call sites."""
    return Settings()
