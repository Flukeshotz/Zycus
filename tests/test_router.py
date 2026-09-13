"""
Router tests (implementation.md P2 task 2.5): one test per gate G1..G11,
proving gate order (a higher-priority gate wins even when a lower one would
also match), plus the readiness rollup.
"""
from __future__ import annotations

from core.models import (
    Confidence,
    FieldStatus,
    Interpretation,
    NormalizedField,
    Readiness,
    ReviewerActionType,
    RuleFinding,
)
from core.router import FieldContext, readiness, route_field


def _nf(interpretation=Interpretation.CLEAR, confidence=Confidence.HIGH, value="x") -> NormalizedField:
    return NormalizedField(
        field="f", raw_value="x", normalized_value=value, duration_months=None,
        interpretation=interpretation, confidence=confidence, reason="test",
    )


def _ctx(**kwargs) -> FieldContext:
    defaults = dict(
        name="term",
        raw_value="2 years",
        required=True,
        is_na_field=False,
        normalized=_nf(),
        findings=[],
        ai_error=None,
        parser_mismatch=False,
    )
    defaults.update(kwargs)
    return FieldContext(**defaults)


# ---------------------------------------------------------------------------
# One test per gate, in priority order
# ---------------------------------------------------------------------------


def test_g1_missing():
    ctx = _ctx(required=True, normalized=_nf(interpretation=Interpretation.MISSING, value=None))
    d = route_field(ctx)
    assert d.status == FieldStatus.BLOCKED_MISSING
    assert d.gate == "G1_missing"


def test_g1_does_not_fire_when_not_required():
    ctx = _ctx(name="special_clause", required=False,
               normalized=_nf(interpretation=Interpretation.MISSING, value=None))
    d = route_field(ctx)
    assert d.gate != "G1_missing"


def test_g2_identity_conflict_beats_g6_rule_violation():
    # Both an identity-conflict finding AND a generic violation finding are
    # present; G2 must win because it's checked first.
    ctx = _ctx(
        name="disclosing_party", required=True,
        findings=[
            RuleFinding(code="PARTY-IDENTICAL", field="disclosing_party", severity="violation", message="x"),
            RuleFinding(code="NO-ENTITY-DESIGNATOR", field="disclosing_party", severity="violation", message="x"),
        ],
    )
    d = route_field(ctx)
    assert d.status == FieldStatus.BLOCKED_MISSING
    assert d.gate == "G2_identity_conflict"


def test_g3_not_applicable():
    ctx = _ctx(name="payment_terms", required=False, is_na_field=True, raw_value="Not applicable — this is an NDA")
    d = route_field(ctx)
    assert d.status == FieldStatus.NOT_APPLICABLE
    assert d.gate == "G3_not_applicable"


def test_g4_wrong_template_signal():
    ctx = _ctx(name="payment_terms", required=False, is_na_field=True, raw_value="Net 90")
    d = route_field(ctx)
    assert d.status == FieldStatus.NEEDS_REVIEW
    assert d.gate == "G4_wrong_template"


def test_g5_risk_shifting_always_fires_even_at_high_confidence():
    # Special clause non-empty -> NEEDS_REVIEW no matter how confident the
    # Normalizer/Analyst is (D-10). This is the core trust guarantee.
    ctx = _ctx(
        name="special_clause", required=False, raw_value="affiliate carve-out",
        normalized=_nf(interpretation=Interpretation.CLEAR, confidence=Confidence.HIGH),
    )
    d = route_field(ctx)
    assert d.status == FieldStatus.NEEDS_REVIEW
    assert d.gate == "G5_risk_shifting"


def test_g5_does_not_fire_when_special_clause_empty():
    ctx = _ctx(name="special_clause", required=False, raw_value="",
               normalized=_nf(interpretation=Interpretation.CLEAR, value=None))
    d = route_field(ctx)
    assert d.gate != "G5_risk_shifting"


def test_g6_rule_violation():
    ctx = _ctx(
        name="term", raw_value="10 years",
        normalized=_nf(interpretation=Interpretation.CLEAR, value="120 months"),
        findings=[RuleFinding(code="NDA-TERM-01", field="term", severity="violation", message="too long")],
    )
    d = route_field(ctx)
    assert d.status == FieldStatus.NEEDS_REVIEW
    assert d.gate == "G6_rule_violation"
    # The value is real and belongs in the document — flagged, not hidden.
    assert d.value_for_document == "120 months"


def test_g4_wrong_template_value_is_never_shown():
    ctx = _ctx(name="payment_terms", required=False, is_na_field=True, raw_value="Net 90",
               normalized=_nf(value="Net 90"))
    d = route_field(ctx)
    assert d.gate == "G4_wrong_template"
    assert d.value_for_document is None


def test_g5_special_clause_value_never_shown_by_router():
    # The Assembler resolves §4 content from run_result.clause + reviewer
    # action, not from FieldDecision.value_for_document (D-12).
    ctx = _ctx(name="special_clause", required=False, raw_value="affiliate carve-out",
               normalized=_nf(value="affiliate carve-out"))
    d = route_field(ctx)
    assert d.gate == "G5_risk_shifting"
    assert d.value_for_document is None


def test_g6_ignores_info_only_findings():
    ctx = _ctx(
        name="survival_period",
        findings=[RuleFinding(code="NDA-SURV-01-INFO", field="survival_period", severity="info", message="fyi")],
    )
    d = route_field(ctx)
    assert d.gate != "G6_rule_violation"
    assert d.info_notes == ["fyi"]


def test_g7_ai_unavailable_beats_g8_ambiguity():
    ctx = _ctx(
        ai_error="rate_limited",
        normalized=_nf(interpretation=Interpretation.AMBIGUOUS, confidence=Confidence.LOW),
    )
    d = route_field(ctx)
    assert d.status == FieldStatus.NEEDS_REVIEW
    assert d.gate == "G7_ai_unavailable"


def test_g8_ambiguous_interpretation():
    ctx = _ctx(normalized=_nf(interpretation=Interpretation.AMBIGUOUS))
    d = route_field(ctx)
    assert d.status == FieldStatus.NEEDS_REVIEW
    assert d.gate == "G8_ambiguity"


def test_g8_low_confidence_even_if_interpretation_clear():
    ctx = _ctx(normalized=_nf(interpretation=Interpretation.CLEAR, confidence=Confidence.LOW))
    d = route_field(ctx)
    assert d.status == FieldStatus.NEEDS_REVIEW
    assert d.gate == "G8_ambiguity"


def test_g9_cross_check_mismatch():
    ctx = _ctx(parser_mismatch=True)
    d = route_field(ctx)
    assert d.status == FieldStatus.NEEDS_REVIEW
    assert d.gate == "G9_crosscheck"


def test_g10_assumption():
    ctx = _ctx(name="effective_date", normalized=_nf(interpretation=Interpretation.DERIVED, value="13 September 2026"))
    d = route_field(ctx)
    assert d.status == FieldStatus.AUTO_FILLED_WITH_ASSUMPTION
    assert d.gate == "G10_assumption"
    assert d.value_for_document == "13 September 2026"


def test_g11_default():
    ctx = _ctx()
    d = route_field(ctx)
    assert d.status == FieldStatus.AUTO_FILLED
    assert d.gate == "G11_default"
    assert d.value_for_document == "x"


# ---------------------------------------------------------------------------
# Gate ordering sanity: earlier gate always wins over a later one that would
# also match on the same context.
# ---------------------------------------------------------------------------


def test_missing_beats_ambiguous():
    ctx = _ctx(
        required=True,
        normalized=_nf(interpretation=Interpretation.MISSING, confidence=Confidence.LOW, value=None),
    )
    d = route_field(ctx)
    assert d.gate == "G1_missing"


def test_rule_violation_beats_derived_assumption():
    ctx = _ctx(
        normalized=_nf(interpretation=Interpretation.DERIVED, value="120 months"),
        findings=[RuleFinding(code="NDA-TERM-01", field="term", severity="violation", message="too long")],
    )
    d = route_field(ctx)
    assert d.gate == "G6_rule_violation"  # not G10, even though interpretation is derived


# ---------------------------------------------------------------------------
# Readiness rollup
# ---------------------------------------------------------------------------


def test_readiness_ready_when_all_auto_filled_or_na():
    decisions = [
        route_field(_ctx(name="a", normalized=_nf())),
        route_field(_ctx(name="b", is_na_field=True, required=False, raw_value="")),
    ]
    assert readiness(decisions) == Readiness.READY_FOR_SIGNATURE_REVIEW


def test_readiness_needs_review_when_any_review_item_unresolved():
    decisions = [
        route_field(_ctx(name="a", normalized=_nf())),
        route_field(_ctx(name="special_clause", raw_value="affiliate", required=False)),
    ]
    assert readiness(decisions) == Readiness.NEEDS_REVIEW


def test_readiness_blocked_dominates_needs_review():
    decisions = [
        route_field(_ctx(name="special_clause", raw_value="affiliate", required=False)),
        route_field(_ctx(name="governing_law", required=True,
                          normalized=_nf(interpretation=Interpretation.MISSING, value=None))),
    ]
    assert readiness(decisions) == Readiness.BLOCKED


def test_readiness_treats_reviewed_item_as_resolved():
    d = route_field(_ctx(name="special_clause", raw_value="affiliate", required=False))
    d.reviewer_action = ReviewerActionType.ACCEPT_PROPOSED
    assert readiness([d]) == Readiness.READY_FOR_SIGNATURE_REVIEW
