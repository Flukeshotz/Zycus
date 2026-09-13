"""
Central settings loader. Reads from the environment (Vercel sets these directly;
locally, .env is loaded via python-dotenv if it's installed and present).

Never print or return secret values. core/config.py exposes only booleans for
key presence (groq_key_configured / gemini_key_configured) — see D-65, D-69.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache

# Load .env locally if python-dotenv is available. On Vercel this import
# silently fails (dev-only dependency, not in requirements.txt) and env vars
# come from the platform instead — this is intentional (D-64).
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


def _bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _str(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    # --- Secrets (never logged, never returned by any API route) ---
    groq_api_key: str
    gemini_api_key: str
    run_signing_secret: str

    # --- Non-secret config ---
    app_timezone: str
    model_normalizer: str
    model_analyst: str
    model_verifier: str
    model_fallback: str
    parallel: bool
    enable_fallback: bool
    llm_mode: str  # "live" | "fake"
    serve_static: bool
    force_ai_failure: bool

    # --- Derived, safe-to-expose booleans ---
    @property
    def groq_key_configured(self) -> bool:
        return bool(self.groq_api_key)

    @property
    def gemini_key_configured(self) -> bool:
        return bool(self.gemini_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings(
        groq_api_key=_str("GROQ_API_KEY", ""),
        gemini_api_key=_str("GEMINI_API_KEY", ""),
        run_signing_secret=_str("RUN_SIGNING_SECRET", ""),
        app_timezone=_str("APP_TIMEZONE", "Asia/Kolkata"),
        model_normalizer=_str("MODEL_NORMALIZER", "openai/gpt-oss-20b"),
        model_analyst=_str("MODEL_ANALYST", "openai/gpt-oss-120b"),
        model_verifier=_str("MODEL_VERIFIER", "qwen/qwen3.8-27b"),
        model_fallback=_str("MODEL_FALLBACK", "gemini-3.5-flash"),
        parallel=_bool("PARALLEL", True),
        enable_fallback=_bool("ENABLE_FALLBACK", True),
        llm_mode=_str("LLM_MODE", "live"),
        serve_static=_bool("SERVE_STATIC", False),
        force_ai_failure=_bool("FORCE_AI_FAILURE", False),
    )
