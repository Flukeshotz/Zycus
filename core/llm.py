"""
GroqLLM (architecture.md §8, D-55–D-60). Thin, reusable plumbing over the
official `groq` SDK: strict-schema structured calls and tool-loop turns,
with exception mapping to AIUnavailable and usage/rate-limit-header
recording for the trace. This module knows nothing about NDAs — agent
prompts and business logic live in agents/normalizer.py and
agents/clause_analyst.py, which call into the generic methods here.

Implements the same LLMClient protocol as FakeLLM (core/fake_llm.py), so
the orchestrator never needs to know which one it's holding.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, TypeVar

from groq import APIConnectionError, APIStatusError, APITimeoutError, Groq, RateLimitError
from pydantic import BaseModel, ValidationError

from core.config import Settings, get_settings
from core.exceptions import AIUnavailable
from core.models import BusinessInputs, ClauseAssessment
from core.schema import strict_schema

T = TypeVar("T", bound=BaseModel)


@dataclass
class CallInfo:
    """Usage/rate-limit detail from the most recent call, for the trace
    (D-34, D-60). Never carries the request content or the API key."""

    model: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    remaining_rate_limit_tokens: str | None


def _map_sdk_exception(e: Exception) -> AIUnavailable:
    # RateLimitError subclasses APIStatusError, so it must be checked first.
    if isinstance(e, RateLimitError):
        return AIUnavailable("rate_limited")
    if isinstance(e, APITimeoutError):
        return AIUnavailable("timeout")
    if isinstance(e, APIConnectionError):
        return AIUnavailable("network")
    if isinstance(e, APIStatusError):
        return AIUnavailable(f"api_error_{e.status_code}")
    return AIUnavailable("unknown_error")


class GroqLLM:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self._client = Groq(api_key=self.settings.groq_api_key, timeout=20.0, max_retries=2)
        # Side-channel state the orchestrator reads after a call to enrich
        # the trace — set by structured_call/tool_turn (last_call) and by
        # agents/clause_analyst.py's research loop (the other two). Not part
        # of the LLMClient protocol; FakeLLM has none of these, so callers
        # must use getattr(llm, "last_call", None) rather than assume they
        # exist (D-46 keeps FakeLLM's interface minimal on purpose).
        self.last_call: CallInfo | None = None
        self.last_tool_calls: list[dict] = []
        self.last_auto_retrieved: list[str] = []

    # --- LLMClient protocol ---------------------------------------------------

    def normalize(self, inputs: BusinessInputs):
        from agents.normalizer import normalize as _normalize

        return _normalize(inputs, self)

    def assess_clause(self, special_clause: str) -> ClauseAssessment:
        from agents.clause_analyst import assess_clause as _assess_clause

        return _assess_clause(special_clause, self)

    # --- generic plumbing ---------------------------------------------------

    def structured_call(
        self,
        *,
        model: str,
        schema_model: type[T],
        schema_name: str,
        system: str,
        user: str,
        reasoning_effort: str,
        temperature: float,
        max_completion_tokens: int,
        reasoning_format: str | None = None,
    ) -> T:
        """One strict-json_schema call. NEVER pass `tools` here — Groq does
        not support tools together with response_format (D-58)."""
        schema = strict_schema(schema_model)
        kwargs: dict[str, Any] = dict(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {"name": schema_name, "strict": True, "schema": schema},
            },
            reasoning_effort=reasoning_effort,
            temperature=temperature,
            max_completion_tokens=max_completion_tokens,
        )
        # Mutually exclusive on Groq — set exactly one.
        if reasoning_format is not None:
            kwargs["reasoning_format"] = reasoning_format
        else:
            kwargs["include_reasoning"] = False

        try:
            raw = self._client.chat.completions.with_raw_response.create(**kwargs)
        except (RateLimitError, APITimeoutError, APIConnectionError, APIStatusError) as e:
            raise _map_sdk_exception(e) from e

        completion = raw.parse()
        self._record_usage(model, completion, raw)

        content = completion.choices[0].message.content
        try:
            return schema_model.model_validate_json(content)
        except (ValidationError, json.JSONDecodeError) as e:
            raise AIUnavailable("invalid_output") from e

    def tool_turn(
        self,
        *,
        model: str,
        messages: list[dict],
        tools: list[dict],
        reasoning_effort: str,
        temperature: float,
        max_completion_tokens: int,
    ):
        """One turn of a tool-calling loop. NEVER pass `response_format`
        here — see structured_call's docstring. Returns the raw SDK message
        object (has .content, .tool_calls)."""
        try:
            raw = self._client.chat.completions.with_raw_response.create(
                model=model,
                messages=messages,
                tools=tools,
                reasoning_effort=reasoning_effort,
                include_reasoning=False,
                temperature=temperature,
                max_completion_tokens=max_completion_tokens,
            )
        except (RateLimitError, APITimeoutError, APIConnectionError, APIStatusError) as e:
            raise _map_sdk_exception(e) from e

        completion = raw.parse()
        self._record_usage(model, completion, raw)
        return completion.choices[0].message

    def _record_usage(self, model: str, completion, raw) -> None:
        usage = getattr(completion, "usage", None)
        self.last_call = CallInfo(
            model=model,
            prompt_tokens=getattr(usage, "prompt_tokens", None) if usage else None,
            completion_tokens=getattr(usage, "completion_tokens", None) if usage else None,
            total_tokens=getattr(usage, "total_tokens", None) if usage else None,
            remaining_rate_limit_tokens=raw.headers.get("x-ratelimit-remaining-tokens"),
        )
