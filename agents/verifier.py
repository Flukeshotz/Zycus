"""
Verifier (architecture.md §3 #10, D-27, D-53). Ships in two stages:

  Stage 1 (here, built in P2 rather than deferred to P3 — S01 needs a
  populated RunResult.verification and this check has no live/offline
  distinction at all, so there is no reason to gate it behind an LLM
  existing): deterministic. A library-matched clause is verified by
  checking the entry's own `satisfies` list against the rule's
  `required_safeguards` — the library text is approved precisely because it
  satisfies them, so this is a lookup, not a judgment call. AI-drafted or
  reviewer-edited text has no such guarantee and is marked "not verified" —
  it stays NEEDS_REVIEW regardless (G5 already guarantees that), this only
  affects the confidence badge shown on the review card.

  Stage 2 (P6, stretch, D-53): an LLM (a different model family than the
  Clause Analyst, D-56) quotes evidence for each safeguard from the actual
  proposed text, and code checks each quote literally appears in it. Not
  built yet — until it exists, stage 1's result is authoritative.
"""
from __future__ import annotations

from core.models import ClauseAssessment, SafeguardCheck, VerificationResult
from tools import clause_library, rulebook


def verify_stage1(clause: ClauseAssessment) -> VerificationResult:
    required = _required_safeguards()

    if clause.proposed_text_source != "library" or not clause.library_match:
        # ai_drafted or none: no independent guarantee any safeguard is
        # present — mark all required safeguards unverified (D-53).
        return VerificationResult(checks=[
            SafeguardCheck(safeguard_id=sg, present=False, evidence_quote=None)
            for sg in required
        ])

    entry = clause_library.get_entry(clause.library_match)
    satisfied = set(entry.satisfies) if entry else set()
    return VerificationResult(checks=[
        SafeguardCheck(safeguard_id=sg, present=sg in satisfied, evidence_quote=None)
        for sg in required
    ])


def _required_safeguards() -> list[str]:
    rule = rulebook.get_rule("NDA-DISC-01")
    return list(getattr(rule, "required_safeguards", []) or [])
