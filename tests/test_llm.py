"""
GroqLLM unit tests (implementation.md P3 task 3.2). Covers exception
mapping and construction only — no network calls. Live behavior is verified
via the CLI and evals/run.py --live per implementation.md's Verification
section, not in the default pytest suite (keeps `pytest -q` free, fast, and
offline).
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from groq import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError

from core.exceptions import AIUnavailable
from core.llm import GroqLLM, _map_sdk_exception


def _fake_settings(**overrides):
    from core.config import Settings

    base = dict(
        groq_api_key="gsk_fake_for_construction_only",
        gemini_api_key="",
        run_signing_secret="x" * 64,
        app_timezone="Asia/Kolkata",
        model_normalizer="openai/gpt-oss-20b",
        model_analyst="openai/gpt-oss-120b",
        model_verifier="qwen/qwen3.8-27b",
        model_fallback="gemini-3.5-flash",
        parallel=True,
        enable_fallback=False,
        llm_mode="live",
        serve_static=False,
        force_ai_failure=False,
    )
    base.update(overrides)
    return Settings(**base)


class TestConstruction:
    def test_constructs_without_network_call(self):
        llm = GroqLLM(settings=_fake_settings())
        assert llm.last_call is None
        assert llm.settings.model_normalizer == "openai/gpt-oss-20b"


class TestExceptionMapping:
    def test_rate_limit_error(self):
        e = RateLimitError("rate limited", response=MagicMock(status_code=429), body=None)
        mapped = _map_sdk_exception(e)
        assert isinstance(mapped, AIUnavailable)
        assert mapped.reason == "rate_limited"

    def test_timeout_error(self):
        e = APITimeoutError(request=MagicMock())
        mapped = _map_sdk_exception(e)
        assert mapped.reason == "timeout"

    def test_connection_error(self):
        e = APIConnectionError(request=MagicMock())
        mapped = _map_sdk_exception(e)
        assert mapped.reason == "network"

    def test_generic_status_error(self):
        e = APIStatusError("bad request", response=MagicMock(status_code=400), body=None)
        mapped = _map_sdk_exception(e)
        assert mapped.reason == "api_error_400"

    def test_rate_limit_checked_before_generic_status(self):
        # RateLimitError IS-A APIStatusError — must map to rate_limited, not
        # a generic api_error_429.
        e = RateLimitError("rate limited", response=MagicMock(status_code=429), body=None)
        assert _map_sdk_exception(e).reason == "rate_limited"

    def test_unknown_exception_still_maps_safely(self):
        mapped = _map_sdk_exception(ValueError("something unrelated"))
        assert isinstance(mapped, AIUnavailable)
        assert mapped.reason == "unknown_error"
