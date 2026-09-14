"""
FakeLLM (architecture.md §3 #17, D-46) — a deterministic, network-free
implementation of the LLMClient protocol. Powers three things with one
implementation, deliberately, so they can't drift apart:

  (a) unit tests and the offline eval mode (--offline), so the whole
      product is proven before any real API call exists;
  (b) P2 development itself, before GroqLLM (P3) exists at all;
  (c) degraded / simulated-failure mode — raising AIUnavailable from
      assess_clause() when asked to simulate a failure exercises exactly
      the same G7 fallback path a real Groq outage would (S14).

Normalization is entirely parser-based (tools/parser.py) and therefore
never fails, even when simulate_ai_failure is set — this mirrors D-13's
intent precisely: only the genuinely AI-judgment-dependent step (clause
risk assessment) degrades; anything a deterministic parser can resolve on
its own keeps working.
"""
from __future__ import annotations

from typing import Protocol

from core.exceptions import AIUnavailable
from core.models import (
    BusinessInputs,
    ClauseAssessment,
    Confidence,
    Interpretation,
    NormalizedField,
    NormalizedInputs,
)
from tools import clause_library, rulebook
from tools.parser import format_long_date, parse_date, parse_duration


class LLMClient(Protocol):
    """Implemented by FakeLLM (P2) and GroqLLM (P3)."""

    def normalize(self, inputs: BusinessInputs) -> NormalizedInputs: ...
    def assess_clause(self, special_clause: str) -> ClauseAssessment: ...


class FakeLLM:
    def __init__(self, tz: str = "Asia/Kolkata", simulate_ai_failure: bool = False):
        self.tz = tz
        self.simulate_ai_failure = simulate_ai_failure

    # --- normalize ----------------------------------------------------------

    def normalize(self, inputs: BusinessInputs) -> NormalizedInputs:
        fields = [
            self._text_field("disclosing_party", inputs.disclosing_party),
            self._text_field("receiving_party", inputs.receiving_party),
            self._date_field("effective_date", inputs.effective_date),
            self._duration_field("term", inputs.term),
            self._text_field("governing_law", inputs.governing_law),
            self._duration_field("survival_period", inputs.survival_period),
            self._text_field("purpose", inputs.purpose),
            self._special_clause_field(inputs.special_clause),
            self._na_field("payment_terms", inputs.payment_terms),
            self._na_field("contract_value", inputs.contract_value),
        ]
        return NormalizedInputs(fields=fields)

    def _text_field(self, field: str, raw: str) -> NormalizedField:
        if not raw or not raw.strip():
            return NormalizedField(
                field=field, raw_value=raw, normalized_value=None, duration_months=None,
                interpretation=Interpretation.MISSING, confidence=Confidence.HIGH,
                reason="No value provided.",
            )
        return NormalizedField(
            field=field, raw_value=raw, normalized_value=raw.strip(), duration_months=None,
            interpretation=Interpretation.CLEAR, confidence=Confidence.HIGH,
            reason="Value provided directly.",
        )

    def _date_field(self, field: str, raw: str) -> NormalizedField:
        if not raw or not raw.strip():
            return NormalizedField(
                field=field, raw_value=raw, normalized_value=None, duration_months=None,
                interpretation=Interpretation.MISSING, confidence=Confidence.HIGH,
                reason="No value provided.",
            )
        parsed = parse_date(raw, self.tz)
        if parsed is None:
            return NormalizedField(
                field=field, raw_value=raw, normalized_value=None, duration_months=None,
                interpretation=Interpretation.AMBIGUOUS, confidence=Confidence.LOW,
                reason="Could not confidently parse a calendar date from this text.",
            )
        formatted = format_long_date(parsed.value)
        interpretation = (
            Interpretation.DERIVED if parsed.interpretation == "derived" else Interpretation.CLEAR
        )
        reason = (
            f"Resolved the relative date reference to {formatted} in {self.tz}."
            if interpretation == Interpretation.DERIVED
            else "Explicit date provided."
        )
        return NormalizedField(
            field=field, raw_value=raw, normalized_value=formatted, duration_months=None,
            interpretation=interpretation, confidence=Confidence.HIGH, reason=reason,
        )

    def _duration_field(self, field: str, raw: str) -> NormalizedField:
        if not raw or not raw.strip():
            return NormalizedField(
                field=field, raw_value=raw, normalized_value=None, duration_months=None,
                interpretation=Interpretation.MISSING, confidence=Confidence.HIGH,
                reason="No value provided.",
            )
        duration = parse_duration(raw)
        if duration is None:
            return NormalizedField(
                field=field, raw_value=raw, normalized_value=None, duration_months=None,
                interpretation=Interpretation.AMBIGUOUS, confidence=Confidence.LOW,
                reason="Could not confidently parse a duration from this text.",
            )
        if duration.kind == "perpetual":
            return NormalizedField(
                field=field, raw_value=raw, normalized_value="perpetual", duration_months=None,
                interpretation=Interpretation.CLEAR, confidence=Confidence.HIGH,
                reason="Parsed as a perpetual (non-expiring) duration.",
            )
        return NormalizedField(
            field=field, raw_value=raw, normalized_value=f"{duration.months} months",
            duration_months=duration.months, interpretation=Interpretation.CLEAR,
            confidence=Confidence.HIGH, reason=f"Parsed as {duration.months} months.",
        )

    def _na_field(self, field: str, raw: str) -> NormalizedField:
        if rulebook.value_is_empty_or_na(raw):
            return NormalizedField(
                field=field, raw_value=raw, normalized_value=None, duration_months=None,
                interpretation=Interpretation.NOT_APPLICABLE, confidence=Confidence.HIGH,
                reason="Recognized as not applicable to this contract type.",
            )
        return NormalizedField(
            field=field, raw_value=raw, normalized_value=raw.strip(), duration_months=None,
            interpretation=Interpretation.CLEAR, confidence=Confidence.HIGH,
            reason="A real value was supplied for a field that does not apply to this contract type.",
        )

    def _special_clause_field(self, raw: str) -> NormalizedField:
        if not raw or not raw.strip():
            return NormalizedField(
                field="special_clause", raw_value=raw, normalized_value=None, duration_months=None,
                interpretation=Interpretation.NOT_APPLICABLE, confidence=Confidence.HIGH,
                reason="No special clause was requested.",
            )
        return NormalizedField(
            field="special_clause", raw_value=raw, normalized_value=raw.strip(), duration_months=None,
            interpretation=Interpretation.CLEAR, confidence=Confidence.HIGH,
            reason="A special clause was requested; see the clause assessment for risk analysis.",
        )

    # --- assess_clause --------------------------------------------------------

    def assess_clause(self, special_clause: str) -> ClauseAssessment:
        if self.simulate_ai_failure:
            raise AIUnavailable("simulated")

        matches = clause_library.search(special_clause)
        if matches:
            entry = matches[0]
            # This FakeLLM only ever matches the single affiliate-disclosure
            # entry currently in the library, so citing NDA-DISC-01 / §5
            # directly here is a deliberate offline-mode shortcut (D-46) —
            # the live Clause Analyst (P3) derives this generally via tools.
            rule = rulebook.get_rule("NDA-DISC-01")
            return ClauseAssessment(
                request_summary=special_clause.strip(),
                library_match=entry.id,
                deviation="non_standard",
                risks=[
                    "Confidential Information could reach entities that never signed this Agreement.",
                    "Without added safeguards, there is no need-to-know limit or liability for affiliate breaches.",
                ],
                conflicting_sections=[5],
                rule_ids_cited=[rule.id],
                proposed_text=entry.text,
                proposed_text_source="library",
                confidence=Confidence.HIGH,
            )

        return ClauseAssessment(
            request_summary=special_clause.strip(),
            library_match=None,
            deviation="non_standard",
            risks=["This request has no matching approved fallback and needs manual legal review."],
            conflicting_sections=[],
            rule_ids_cited=[],
            proposed_text=None,
            proposed_text_source="none",
            confidence=Confidence.MEDIUM,
        )
