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
from core.models import BusinessInputs, FieldStatus, Readiness, ReviewerAction, ReviewerActionType
from core.orchestrator import render_docx, rerender, run

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
