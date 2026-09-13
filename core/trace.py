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

from core.models import TraceStep, TraceStepKind


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
        self._started_at = datetime.now(timezone.utc).isoformat()
        self._start = time.perf_counter()

    def finalize(self) -> TraceStep:
        duration_ms = (time.perf_counter() - self._start) * 1000
        return TraceStep(
            name=self.name, kind=self.kind, status=self.status,
            started_at=self._started_at, duration_ms=duration_ms,
            model=self.model, input_summary=self.input_summary,
            output_summary=self.output_summary, error=self.error,
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
