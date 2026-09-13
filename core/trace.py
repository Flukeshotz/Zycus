"""
Trace (architecture.md §3 #18, §8, D-34). Records every pipeline step so the
UI (Agent Trace tab, P4) and debugging can see exactly what happened and
why. P2 populates the basic step shape (name, kind, status, timing,
summaries); P3 extends the same TraceStep with model/token/tool-call detail
for live LLM steps — nothing here needs to change for that, since those
fields are already optional on TraceStep (core/models.py).
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import datetime, timezone

from core.models import ToolCallRecord, TraceStep, TraceStepKind


class _StepHandle:
    """Mutable handle yielded by Trace.step(); lets the caller set
    output_summary/status/error/model before the step is finalized."""

    def __init__(self, name: str, kind: TraceStepKind):
        self.name = name
        self.kind = kind
        self.status: str = "ok"
        self.input_summary: str | None = None
        self.output_summary: str | None = None
        self.error: str | None = None
        self.model: str | None = None
        self.prompt_tokens: int | None = None
        self.completion_tokens: int | None = None
        self.total_tokens: int | None = None
        self.remaining_rate_limit_tokens: str | None = None
        self.served_by: str | None = None
        self.tool_calls: list[ToolCallRecord] = []
        self._started_at = datetime.now(timezone.utc).isoformat()
        self._start = time.perf_counter()

    def tool_call(self, name: str, arguments_summary: str, output_summary: str, is_error: bool = False) -> None:
        self.tool_calls.append(ToolCallRecord(
            name=name, arguments_summary=arguments_summary,
            output_summary=output_summary, is_error=is_error,
        ))

    def record_usage(self, call_info) -> None:
        """`call_info` is a core.llm.CallInfo — duck-typed here (reads
        .model/.prompt_tokens/.completion_tokens/.total_tokens/
        .remaining_rate_limit_tokens) to avoid core/trace.py importing
        core/llm.py. Never records the API key or full prompt/response text
        (architecture §8's guardrail) — only usage counts and headers."""
        self.model = call_info.model
        self.prompt_tokens = call_info.prompt_tokens
        self.completion_tokens = call_info.completion_tokens
        self.total_tokens = call_info.total_tokens
        self.remaining_rate_limit_tokens = call_info.remaining_rate_limit_tokens

    def finalize(self) -> TraceStep:
        duration_ms = (time.perf_counter() - self._start) * 1000
        return TraceStep(
            name=self.name, kind=self.kind, status=self.status,
            started_at=self._started_at, duration_ms=duration_ms,
            model=self.model, prompt_tokens=self.prompt_tokens,
            completion_tokens=self.completion_tokens, total_tokens=self.total_tokens,
            remaining_rate_limit_tokens=self.remaining_rate_limit_tokens,
            served_by=self.served_by, tool_calls=self.tool_calls,
            input_summary=self.input_summary, output_summary=self.output_summary,
            error=self.error,
        )


class Trace:
    def __init__(self):
        self.steps: list[TraceStep] = []

    @contextmanager
    def step(self, name: str, kind: TraceStepKind):
        handle = _StepHandle(name, kind)
        try:
            yield handle
        except Exception as e:  # noqa: BLE001 — record the crash, then let it propagate
            handle.status = "error"
            handle.error = str(e)
            self.steps.append(handle.finalize())
            raise
        else:
            self.steps.append(handle.finalize())
