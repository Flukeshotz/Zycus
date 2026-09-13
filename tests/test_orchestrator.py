"""
Orchestrator integration tests (implementation.md P2 task 2.9). Exercises
the full offline pipeline end to end — this is the test that most directly
proves architecture §4's sample walkthrough is actually true of the code,
not just the docs.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from core.fake_llm import FakeLLM
from core.models import (
    BusinessInputs,
    Confidence,
    FieldStatus,
    Interpretation,
    NormalizedField,
    Readiness,
    ReviewerAction,
    ReviewerActionType,
)
from core.orchestrator import _canonicalize_parsed_fields, render_docx, rerender, run

SAMPLE_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_inputs.json"


def _sample_inputs() -> BusinessInputs:
    with SAMPLE_PATH.open() as f:
        return BusinessInputs(**json.load(f))


def _now():
    return datetime.now(ZoneInfo("Asia/Kolkata"))


def _decision(result, field):
    return next(d for d in result.decisions if d.field == field)


class TestS01SampleEndToEnd:
    def setup_method(self):
        self.result = run(_sample_inputs(), FakeLLM(), _now())

    def test_readiness_needs_review(self):
        assert self.result.readiness == Readiness.NEEDS_REVIEW

    def test_all_ten_fields_routed(self):
        assert {d.field for d in self.result.decisions} == {
            "disclosing_party", "receiving_party", "effective_date", "term",
            "governing_law", "survival_period", "purpose", "special_clause",
            "payment_terms", "contract_value",
        }

    def test_effective_date_auto_filled_with_assumption(self):
        d = _decision(self.result, "effective_date")
        assert d.status == FieldStatus.AUTO_FILLED_WITH_ASSUMPTION
        assert d.gate == "G10_assumption"
        # Regression (found live, P3): must be a resolved date, never the
        # raw "use today's date" instruction text leaking into the document.
        assert d.value_for_document is not None
        assert "today" not in d.value_for_document.lower()
        assert d.value_for_document[0].isdigit()

    def test_simple_fields_auto_filled(self):
        for field in ("disclosing_party", "receiving_party", "purpose", "term",
                       "survival_period", "governing_law"):
            d = _decision(self.result, field)
            assert d.status == FieldStatus.AUTO_FILLED, field

    def test_special_clause_needs_review_via_g5(self):
        d = _decision(self.result, "special_clause")
        assert d.status == FieldStatus.NEEDS_REVIEW
        assert d.gate == "G5_risk_shifting"

    def test_payment_and_contract_value_not_applicable(self):
        assert _decision(self.result, "payment_terms").status == FieldStatus.NOT_APPLICABLE
        assert _decision(self.result, "contract_value").status == FieldStatus.NOT_APPLICABLE

    def test_clause_assessment_present_with_library_match(self):
        assert self.result.clause is not None
        assert self.result.clause.library_match == "affiliate_disclosure"
        assert self.result.clause.proposed_text_source == "library"

    def test_verification_stage1_present(self):
        assert self.result.verification is not None
        assert len(self.result.verification.checks) == 4
        assert all(c.present for c in self.result.verification.checks)

    def test_survival_longer_than_term_info_note(self):
        d = _decision(self.result, "survival_period")
        assert any("survive" in note.lower() for note in d.info_notes)

    def test_document_notes_present(self):
        assert len(self.result.document_notes) == 3

    def test_qa_passes(self):
        assert self.result.qa.passed, self.result.qa.checks

    def test_docx_bytes_renderable(self):
        docx_bytes = render_docx(self.result)
        assert docx_bytes[:2] == b"PK"  # docx is a zip archive

    def test_trace_has_steps(self):
        assert len(self.result.trace) >= 5
        names = {s.name for s in self.result.trace}
        assert "assess_clause" in names
        assert "qa" in names


class TestS02MissingGoverningLaw:
    def test_blocked_readiness_and_marker(self):
        inputs = _sample_inputs().model_copy(update={"governing_law": ""})
        result = run(inputs, FakeLLM(), _now())
        assert result.readiness == Readiness.BLOCKED
        d = _decision(result, "governing_law")
        assert d.status == FieldStatus.BLOCKED_MISSING
        assert result.qa.passed
        docx_bytes = render_docx(result)
        assert docx_bytes[:2] == b"PK"


class TestS06EmptySpecialClause:
    def test_ready_for_signature_review(self):
        inputs = _sample_inputs().model_copy(update={"special_clause": ""})
        result = run(inputs, FakeLLM(), _now())
        assert result.readiness == Readiness.READY_FOR_SIGNATURE_REVIEW
        d = _decision(result, "special_clause")
        assert d.status == FieldStatus.AUTO_FILLED
        assert result.clause is None  # never called — nothing to assess
        assert result.qa.passed


class TestS14AIDown:
    def test_special_clause_needs_review_and_reason_mentions_ai(self):
        # G5 (risk-shifting) is the gate that fires — per architecture §5.2's
        # exact order, a non-empty special clause is ALWAYS G5 regardless of
        # AI availability (D-10: never rescued OR blocked by AI state). The
        # reason text still surfaces the AI-unavailable condition.
        result = run(_sample_inputs(), FakeLLM(), _now(), simulate_ai_failure=True)
        d = _decision(result, "special_clause")
        assert d.status == FieldStatus.NEEDS_REVIEW
        assert d.gate == "G5_risk_shifting"
        assert "AI" in d.reason

    def test_other_fields_still_resolve_via_deterministic_fallback(self):
        result = run(_sample_inputs(), FakeLLM(), _now(), simulate_ai_failure=True)
        d = _decision(result, "effective_date")
        assert d.status == FieldStatus.AUTO_FILLED_WITH_ASSUMPTION

    def test_qa_still_passes_degraded(self):
        result = run(_sample_inputs(), FakeLLM(), _now(), simulate_ai_failure=True)
        assert result.qa.passed
        docx_bytes = render_docx(result)
        assert docx_bytes[:2] == b"PK"  # a safe draft is still produced (D-13)


class TestRerenderNoLLMCall:
    def test_accept_proposed_updates_readiness_without_new_llm_calls(self):
        result = run(_sample_inputs(), FakeLLM(), _now())
        agent_steps_before = [s for s in result.trace if s.kind.value == "agent"]

        action = ReviewerAction(field="special_clause", action=ReviewerActionType.ACCEPT_PROPOSED)
        updated = rerender(result, [action])

        agent_steps_after = [s for s in updated.trace if s.kind.value == "agent"]
        assert len(agent_steps_after) == len(agent_steps_before)  # no new agent/LLM steps
        assert updated.readiness == Readiness.READY_FOR_SIGNATURE_REVIEW
        d = _decision(updated, "special_clause")
        assert d.reviewer_action == ReviewerActionType.ACCEPT_PROPOSED
        assert updated.qa.passed

    def test_rerender_docx_reflects_accepted_text(self):
        result = run(_sample_inputs(), FakeLLM(), _now())
        action = ReviewerAction(field="special_clause", action=ReviewerActionType.ACCEPT_PROPOSED)
        updated = rerender(result, [action])
        docx_bytes = render_docx(updated, [action])
        assert docx_bytes[:2] == b"PK"


class TestCanonicalizeParsedFields:
    """
    Regression tests for two live-only bugs found in P3's first live run —
    neither reproducible offline, since FakeLLM already builds
    normalized_value from the parser (it can't exhibit either failure mode).
    """

    def test_effective_date_fills_in_a_compliant_derived_response(self):
        # The Normalizer's own system prompt correctly instructs it not to
        # guess an actual date for a DERIVED effective_date — a compliant
        # response therefore has normalized_value=None, exactly like this
        # fixture. Before the fix, the raw "use today's date" instruction
        # text leaked straight into the rendered document (caught by QA Q2).
        normalized_by_field = {
            "effective_date": NormalizedField(
                field="effective_date", raw_value="To be filled — use today's date",
                normalized_value=None, duration_months=None,
                interpretation=Interpretation.DERIVED, confidence=Confidence.HIGH,
                reason="Resolved 'today' to the caller.",
            )
        }
        _canonicalize_parsed_fields(normalized_by_field, _sample_inputs(), _now(), "Asia/Kolkata")
        result = normalized_by_field["effective_date"]
        assert result.normalized_value is not None
        assert "today" not in result.normalized_value.lower()

    def test_derived_effective_date_always_overridden_even_when_non_empty(self):
        # Regression within a regression: a live response was observed
        # returning a non-empty but still-unresolved echo of the input
        # ("use today's date") rather than null — the original fix's `not
        # normalized_value` guard treated that as "already resolved" and
        # skipped it, so G9 then flagged it as a parser mismatch. A DERIVED
        # value must always be overridden, unconditionally.
        now = _now()
        normalized_by_field = {
            "effective_date": NormalizedField(
                field="effective_date", raw_value="use today's date",
                normalized_value="use today's date", duration_months=None,
                interpretation=Interpretation.DERIVED, confidence=Confidence.MEDIUM, reason="x",
            )
        }
        _canonicalize_parsed_fields(normalized_by_field, _sample_inputs(), now, "Asia/Kolkata")
        result = normalized_by_field["effective_date"].normalized_value
        assert result != "use today's date"
        assert result[0].isdigit()

    def test_derived_effective_date_with_a_wrong_guessed_date_is_still_overridden(self):
        normalized_by_field = {
            "effective_date": NormalizedField(
                field="effective_date", raw_value="use today's date",
                normalized_value="1 January 2030", duration_months=None,
                interpretation=Interpretation.DERIVED, confidence=Confidence.HIGH, reason="x",
            )
        }
        _canonicalize_parsed_fields(normalized_by_field, _sample_inputs(), _now(), "Asia/Kolkata")
        assert normalized_by_field["effective_date"].normalized_value != "1 January 2030"

    def test_effective_date_does_not_touch_a_clear_explicit_date(self):
        normalized_by_field = {
            "effective_date": NormalizedField(
                field="effective_date", raw_value="1 October 2026",
                normalized_value="1 October 2026", duration_months=None,
                interpretation=Interpretation.CLEAR, confidence=Confidence.HIGH, reason="x",
            )
        }
        _canonicalize_parsed_fields(normalized_by_field, _sample_inputs(), _now(), "Asia/Kolkata")
        assert normalized_by_field["effective_date"].normalized_value == "1 October 2026"

    def test_term_raw_phrase_echoed_by_model_is_replaced_with_canonical_value(self):
        # The exact live bug: the model put the raw input phrase in
        # normalized_value instead of a clean value, producing "...for 2
        # years from effective date from the Effective Date..." in the
        # rendered document.
        inputs = _sample_inputs()  # term = "2 years from effective date"
        normalized_by_field = {
            "term": NormalizedField(
                field="term", raw_value=inputs.term,
                normalized_value="2 years from effective date",  # echoed raw text, the bug
                duration_months=24, interpretation=Interpretation.CLEAR,
                confidence=Confidence.HIGH, reason="x",
            )
        }
        _canonicalize_parsed_fields(normalized_by_field, inputs, _now(), "Asia/Kolkata")
        assert normalized_by_field["term"].normalized_value == "24 months"

    def test_survival_perpetual_canonicalized(self):
        inputs = _sample_inputs().model_copy(update={"survival_period": "perpetual"})
        normalized_by_field = {
            "survival_period": NormalizedField(
                field="survival_period", raw_value="perpetual", normalized_value="perpetual",
                duration_months=None, interpretation=Interpretation.CLEAR,
                confidence=Confidence.HIGH, reason="x",
            )
        }
        _canonicalize_parsed_fields(normalized_by_field, inputs, _now(), "Asia/Kolkata")
        assert normalized_by_field["survival_period"].normalized_value == "perpetual"

    def test_ambiguous_term_left_untouched(self):
        inputs = _sample_inputs().model_copy(update={"term": "until the project is completed"})
        normalized_by_field = {
            "term": NormalizedField(
                field="term", raw_value=inputs.term, normalized_value=None, duration_months=None,
                interpretation=Interpretation.AMBIGUOUS, confidence=Confidence.LOW, reason="x",
            )
        }
        _canonicalize_parsed_fields(normalized_by_field, inputs, _now(), "Asia/Kolkata")
        assert normalized_by_field["term"].normalized_value is None  # parser also can't parse it

    def test_missing_fields_are_a_no_op(self):
        normalized_by_field: dict = {}
        _canonicalize_parsed_fields(normalized_by_field, _sample_inputs(), _now(), "Asia/Kolkata")
        assert normalized_by_field == {}
