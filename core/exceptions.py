"""
Shared exceptions (D-13, D-46).

AIUnavailable is raised by any LLMClient implementation — FakeLLM here in
P2, GroqLLM in P3 — when an AI step cannot complete: timeout, rate limit,
refusal, schema validation failure, or a simulated failure for
testing/demo purposes (S14, the "Simulate AI outage" toggle). The
orchestrator catches this and routes the affected field to gate G7
(NEEDS_REVIEW) — it is never silently swallowed, and the system never falls
back to inserting unvetted text just because the AI step failed.
"""
from __future__ import annotations


class AIUnavailable(Exception):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)
