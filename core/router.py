"""
Confidence Router (architecture.md §5, D-08, D-09, D-13). The whole flag-vs-
act decision lives here as an ordered chain of gates — nothing else in the
system decides a field's status. `route_field` is a pure function: no I/O, no
randomness, no reading of raw free text for its own decision (only the
precomputed signals on FieldContext, D-14) — which is exactly what makes it
unit-testable one gate at a time (tests/test_router.py) and explainable in
the demo ("here's the exact rule that fired, and why it fires before the
others").

Gate order encodes the trust hierarchy: safety gates (missing, identity
conflict, risk-shifting, rule violation, AI unavailable) are checked before
convenience gates (ambiguity, cross-check, assumption). Nothing risk-shifting
or rule-violating can be rescued by high model confidence — confidence is
only consulted at G8, and even there it can only add a flag, never remove
one (D-09).
"""
from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from typing import Callable

from core.models import (
    Confidence,
    FieldDecision,
    FieldStatus,
    Interpretation,
    NormalizedField,
    Readiness,
    RuleFinding,
)
from tools.rulebook import display_field_name
from tools.rulebook import value_is_empty_or_na as _value_is_empty_or_na

_REASON_TEMPLATES: dict[str, str] = {
    "G1_missing": "{field} is required but was not provided.",
    "G2_identity_conflict": "{field}: the disclosing and receiving party names are identical.",
    "G3_not_applicable": "{field} does not apply to a Mutual NDA and has been omitted from the draft.",
    "G4_wrong_template": (
        "{field} was supplied but does not apply to a Mutual NDA — "
        "wrong template or missing agreement?"
    ),
    "G5_risk_shifting": (
        "This request changes who may receive Confidential Information, so it always "
        "requires human review, regardless of how standard it may appear."
    ),
    "G6_rule_violation": "{field} falls outside the standard range or list for this contract type.",
    "G7_ai_unavailable": "AI analysis was unavailable for {field}; flagged for manual review as a safe fallback.",
    "G8_ambiguity": "{field} could not be confidently interpreted from the input provided.",
    "G9_crosscheck": "The automatic parser and the AI's reading of {field} disagree.",
    "G10_assumption": "{field} was not given an explicit value; a reasonable assumption was applied.",
    "G11_default": "{field} was filled in directly from the value provided.",
}


@dataclass
class FieldContext:
    """
    Everything route_field needs for one field, already resolved by the
    orchestrator from BusinessInputs + NormalizedInputs + rule-engine
    findings + (live mode) AI error state + the parser cross-check. Building
    this is the orchestrator's job (core/orchestrator.py); route_field only
    ever reads it.
    """

    name: str
    raw_value: str
    required: bool
    is_na_field: bool
    normalized: NormalizedField
    findings: list[RuleFinding] = dataclass_field(default_factory=list)
    ai_error: str | None = None
    parser_mismatch: bool = False

    @property
    def value_present(self) -> bool:
        return bool(self.raw_value and self.raw_value.strip())

    @property
    def value_is_empty_or_na(self) -> bool:
        # Deliberately shares tools.rulebook's N/A-signal matcher so "Not
        # applicable — this is an NDA, not a commercial agreement" and a
        # bare "N/A" are recognized identically wherever this is checked.
        return _value_is_empty_or_na(self.raw_value)

    def has_finding(self, code: str) -> bool:
        return any(f.code == code for f in self.findings)

    def has_violation(self) -> bool:
        return any(f.severity == "violation" for f in self.findings)

    def parser_disagrees(self) -> bool:
        return self.parser_mismatch

    @property
    def info_notes(self) -> list[str]:
        return [f.message for f in self.findings if f.severity == "info"]

    def decision(self, status: FieldStatus, gate: str) -> FieldDecision:
        return FieldDecision(
            field=self.name,
            status=status,
            gate=gate,
            value_for_document=self._value_for_document(status, gate),
            reason=self._reason(status, gate),
            info_notes=self.info_notes,
        )

    # Gates whose NEEDS_REVIEW still carries a real, displayable value: the
    # field belongs in the document, it's just flagged (e.g. term="10 years"
    # outside the standard range, or an ambiguous phrasing kept verbatim).
    # G4 (wrong-template signal) and G5 (special_clause) are excluded
    # deliberately — G4's value must never be inserted (D-16), and
    # special_clause's §4 content is resolved by the Assembler from
    # run_result.clause + reviewer_action, not from here.
    _REVIEW_GATES_WITH_VISIBLE_VALUE = frozenset(
        {"G6_rule_violation", "G8_ambiguity", "G9_crosscheck"}
    )

    def _value_for_document(self, status: FieldStatus, gate: str) -> str | None:
        if status in (FieldStatus.AUTO_FILLED, FieldStatus.AUTO_FILLED_WITH_ASSUMPTION):
            return self.normalized.normalized_value or (self.raw_value or None)
        if status == FieldStatus.NEEDS_REVIEW and gate in self._REVIEW_GATES_WITH_VISIBLE_VALUE:
            return self.normalized.normalized_value or (self.raw_value or None)
        return None

    def _reason(self, status: FieldStatus, gate: str) -> str:
        if gate == "G6_rule_violation":
            violations = [f.message for f in self.findings if f.severity == "violation"]
            if violations:
                return violations[0]
        if gate == "G2_identity_conflict":
            matches = [f.message for f in self.findings if f.code == "PARTY-IDENTICAL"]
            if matches:
                return matches[0]
        template = _REASON_TEMPLATES.get(gate, "{field} was flagged.")
        reason = template.format(field=display_field_name(self.name))
        if gate == "G5_risk_shifting" and self.ai_error is not None:
            # G5 always wins the *status* for special_clause (D-10 — this is
            # never rescued or blocked by AI availability), but the reviewer
            # still needs to know no automated risk assessment could run.
            reason += " AI analysis was unavailable, so no automated risk assessment could be prepared — review manually."
        return reason


def route_field(f: FieldContext) -> FieldDecision:
    gates: list[tuple[str, Callable[[], bool], FieldStatus]] = [
        ("G1_missing", lambda: f.required and f.normalized.interpretation == Interpretation.MISSING,
         FieldStatus.BLOCKED_MISSING),
        ("G2_identity_conflict", lambda: f.has_finding("PARTY-IDENTICAL"),
         FieldStatus.BLOCKED_MISSING),
        ("G3_not_applicable", lambda: f.is_na_field and f.value_is_empty_or_na,
         FieldStatus.NOT_APPLICABLE),
        ("G4_wrong_template", lambda: f.is_na_field and not f.value_is_empty_or_na,
         FieldStatus.NEEDS_REVIEW),
        ("G5_risk_shifting", lambda: f.name == "special_clause" and f.value_present,
         FieldStatus.NEEDS_REVIEW),
        ("G6_rule_violation", lambda: f.has_violation(),
         FieldStatus.NEEDS_REVIEW),
        ("G7_ai_unavailable", lambda: f.ai_error is not None,
         FieldStatus.NEEDS_REVIEW),
        ("G8_ambiguity", lambda: f.normalized.interpretation == Interpretation.AMBIGUOUS
         or f.normalized.confidence in (Confidence.MEDIUM, Confidence.LOW),
         FieldStatus.NEEDS_REVIEW),
        ("G9_crosscheck", lambda: f.parser_disagrees(),
         FieldStatus.NEEDS_REVIEW),
        ("G10_assumption", lambda: f.normalized.interpretation == Interpretation.DERIVED,
         FieldStatus.AUTO_FILLED_WITH_ASSUMPTION),
    ]
    for gate_id, condition, status in gates:
        if condition():
            return f.decision(status, gate_id)
    return f.decision(FieldStatus.AUTO_FILLED, "G11_default")


def readiness(decisions: list[FieldDecision]) -> Readiness:
    """
    Document-level readiness (architecture §5.1): any BLOCKED_MISSING ->
    BLOCKED; else any NEEDS_REVIEW *without* a recorded reviewer_action ->
    NEEDS_REVIEW; else READY_FOR_SIGNATURE_REVIEW. A reviewer_action means a
    human already made the call on that item (D-63).
    """
    if any(d.status == FieldStatus.BLOCKED_MISSING for d in decisions):
        return Readiness.BLOCKED
    unresolved_review = [
        d for d in decisions
        if d.status == FieldStatus.NEEDS_REVIEW and d.reviewer_action is None
    ]
    if unresolved_review:
        return Readiness.NEEDS_REVIEW
    return Readiness.READY_FOR_SIGNATURE_REVIEW
