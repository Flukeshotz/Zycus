"""
QA Gate tests (implementation.md P2 task 2.7, architecture §9 Q1-Q8).
Covers the AI watch-list items for this task: a RenderedDoc containing
"[GOVERNING LAW]" fails Q1; "N/A" in a slot fails Q2; docx text equals
RenderedDoc text (Q8); plus the sample passing cleanly end to end.
"""
from __future__ import annotations

from core.models import (
    BusinessInputs,
    ClauseAssessment,
    Confidence,
    FieldDecision,
    FieldStatus,
    Readiness,
    ReviewerAction,
    ReviewerActionType,
)
from tools import template_store
from tools.assembler import RenderedRun, build_rendered_doc, write_docx
from tools.qa_gate import run_qa


def _template():
    return template_store.get_template("mutual_nda")


def _inputs(**overrides):
    base = dict(
        disclosing_party="Zycus Inc.",
        receiving_party="Northwind Vendor Solutions Pvt. Ltd.",
        effective_date="use today's date",
        term="2 years from effective date",
        governing_law="State of Delaware, USA",
        survival_period="3 years after termination",
        purpose="Evaluating a potential vendor relationship for procurement software integration",
        special_clause="Receiving party wants a carve-out allowing disclosure to their affiliates without prior written consent",
        payment_terms="Not applicable — this is an NDA, not a commercial agreement",
        contract_value="",
    )
    base.update(overrides)
    return BusinessInputs(**base)


def _auto_filled(field, value, status=FieldStatus.AUTO_FILLED, gate="G11_default"):
    return FieldDecision(field=field, status=status, gate=gate, value_for_document=value, reason="ok")


def _sample_decisions():
    return [
        _auto_filled("disclosing_party", "Zycus Inc."),
        _auto_filled("receiving_party", "Northwind Vendor Solutions Pvt. Ltd."),
        _auto_filled("effective_date", "13 September 2026", status=FieldStatus.AUTO_FILLED_WITH_ASSUMPTION, gate="G10_assumption"),
        _auto_filled("term", "24 months"),
        _auto_filled("survival_period", "36 months"),
        _auto_filled("governing_law", "State of Delaware, USA"),
        _auto_filled("purpose", "Evaluating a potential vendor relationship for procurement software integration"),
        FieldDecision(field="special_clause", status=FieldStatus.NEEDS_REVIEW, gate="G5_risk_shifting",
                      value_for_document=None, reason="risk-shifting clause"),
        FieldDecision(field="payment_terms", status=FieldStatus.NOT_APPLICABLE, gate="G3_not_applicable",
                      value_for_document=None, reason="not applicable"),
        FieldDecision(field="contract_value", status=FieldStatus.NOT_APPLICABLE, gate="G3_not_applicable",
                      value_for_document=None, reason="not applicable"),
    ]


def _sample_clause():
    return ClauseAssessment(
        request_summary="Affiliate disclosure carve-out",
        library_match="affiliate_disclosure",
        deviation="non_standard",
        risks=["Confidential Information could reach non-signatory affiliates"],
        conflicting_sections=[5],
        rule_ids_cited=["NDA-DISC-01"],
        proposed_text="Notwithstanding the foregoing, the Receiving Party may disclose to Affiliates...",
        proposed_text_source="library",
        confidence=Confidence.HIGH,
    )


def _run_full_pipeline(inputs=None, decisions=None, clause=None, readiness=Readiness.NEEDS_REVIEW,
                        reviewer_actions=None):
    template = _template()
    inputs = inputs or _inputs()
    decisions = decisions if decisions is not None else _sample_decisions()
    clause = clause if clause is not None else _sample_clause()
    rendered = build_rendered_doc(template, inputs, decisions, clause, readiness, reviewer_actions)
    docx_bytes = write_docx(rendered)
    report = run_qa(docx_bytes, rendered, template, inputs, decisions, clause, readiness, reviewer_actions)
    return rendered, docx_bytes, report


class TestSamplePassesCleanly:
    def test_full_qa_passes(self):
        _, _, report = _run_full_pipeline()
        failed = [c for c in report.checks if not c.passed]
        assert report.passed, f"failed checks: {failed}"
        assert {c.check_id for c in report.checks} == {f"Q{i}" for i in range(1, 9)}


class TestQ1Placeholders:
    def test_leftover_placeholder_fails_q1(self):
        rendered, _, report = _run_full_pipeline()
        # Tamper: reintroduce a raw placeholder into a template-sourced run.
        rendered.paragraphs[5].runs.append(RenderedRun(text="[GOVERNING LAW]", source="template"))
        docx_bytes = write_docx(rendered)
        template, inputs, decisions, clause = _template(), _inputs(), _sample_decisions(), _sample_clause()
        report2 = run_qa(docx_bytes, rendered, template, inputs, decisions, clause, Readiness.NEEDS_REVIEW)
        q1 = next(c for c in report2.checks if c.check_id == "Q1")
        assert not q1.passed
        assert not report2.passed

    def test_missing_marker_does_not_trip_q1(self):
        decisions = _sample_decisions()
        for d in decisions:
            if d.field == "governing_law":
                d.status, d.gate, d.value_for_document = FieldStatus.BLOCKED_MISSING, "G1_missing", None
        _, _, report = _run_full_pipeline(inputs=_inputs(governing_law=""), decisions=decisions,
                                           readiness=Readiness.BLOCKED)
        q1 = next(c for c in report.checks if c.check_id == "Q1")
        assert q1.passed


class TestQ2ForbiddenLiterals:
    def test_forbidden_literal_in_slot_fails_q2(self):
        rendered, _, _ = _run_full_pipeline()
        rendered.paragraphs[5].runs.append(RenderedRun(text="N/A", source="slot"))
        docx_bytes = write_docx(rendered)
        template, inputs, decisions, clause = _template(), _inputs(), _sample_decisions(), _sample_clause()
        report = run_qa(docx_bytes, rendered, template, inputs, decisions, clause, Readiness.NEEDS_REVIEW)
        q2 = next(c for c in report.checks if c.check_id == "Q2")
        assert not q2.passed
        assert not report.passed

    def test_forbidden_word_in_template_text_does_not_trip_q2(self):
        # "template"-sourced text is never scanned by Q2 — only "slot" runs.
        rendered, _, report = _run_full_pipeline()
        rendered.paragraphs[0].runs.append(RenderedRun(text="This mentions payment in prose.", source="template"))
        docx_bytes = write_docx(rendered)
        template, inputs, decisions, clause = _template(), _inputs(), _sample_decisions(), _sample_clause()
        report2 = run_qa(docx_bytes, rendered, template, inputs, decisions, clause, Readiness.NEEDS_REVIEW)
        q2 = next(c for c in report2.checks if c.check_id == "Q2")
        assert q2.passed


class TestQ4Sections:
    def test_missing_section_fails_q4(self):
        rendered, _, _ = _run_full_pipeline()
        del rendered.paragraphs[3]  # drop section "3"
        docx_bytes = write_docx(rendered)
        template, inputs, decisions, clause = _template(), _inputs(), _sample_decisions(), _sample_clause()
        report = run_qa(docx_bytes, rendered, template, inputs, decisions, clause, Readiness.NEEDS_REVIEW)
        q4 = next(c for c in report.checks if c.check_id == "Q4")
        assert not q4.passed


class TestQ5NonSlotTextUnchanged:
    def test_reworded_template_text_fails_q5(self):
        rendered, _, _ = _run_full_pipeline()
        # Reword a "template"-sourced run — a silent rewording bug.
        for run in rendered.paragraphs[0].runs:
            if run.source == "template" and "Mutual Non-Disclosure Agreement" in run.text:
                run.text = run.text.replace("Mutual Non-Disclosure Agreement", "Confidentiality Agreement")
        docx_bytes = write_docx(rendered)
        template, inputs, decisions, clause = _template(), _inputs(), _sample_decisions(), _sample_clause()
        report = run_qa(docx_bytes, rendered, template, inputs, decisions, clause, Readiness.NEEDS_REVIEW)
        q5 = next(c for c in report.checks if c.check_id == "Q5")
        assert not q5.passed


class TestQ6ClauseMatchesDecision:
    def test_tampered_special_clause_fails_q6(self):
        rendered, _, _ = _run_full_pipeline()
        section4 = rendered.paragraphs[4]
        for run in section4.runs:
            if run.source == "slot" and run.highlight == "yellow":
                run.text = "The Receiving Party may disclose to anyone at its sole discretion."
        docx_bytes = write_docx(rendered)
        template, inputs, decisions, clause = _template(), _inputs(), _sample_decisions(), _sample_clause()
        report = run_qa(docx_bytes, rendered, template, inputs, decisions, clause, Readiness.NEEDS_REVIEW)
        q6 = next(c for c in report.checks if c.check_id == "Q6")
        assert not q6.passed

    def test_accepted_clause_matches_q6(self):
        action = ReviewerAction(field="special_clause", action=ReviewerActionType.ACCEPT_PROPOSED)
        _, _, report = _run_full_pipeline(reviewer_actions=[action])
        q6 = next(c for c in report.checks if c.check_id == "Q6")
        assert q6.passed


class TestQ7ReadinessBanner:
    def test_blocked_without_banner_fails_q7(self):
        decisions = _sample_decisions()
        for d in decisions:
            if d.field == "governing_law":
                d.status, d.gate, d.value_for_document = FieldStatus.BLOCKED_MISSING, "G1_missing", None
        rendered = build_rendered_doc(_template(), _inputs(governing_law=""), decisions, _sample_clause(), Readiness.BLOCKED)
        rendered.banner = None  # tamper: drop the banner
        docx_bytes = write_docx(rendered)
        report = run_qa(docx_bytes, rendered, _template(), _inputs(governing_law=""), decisions,
                         _sample_clause(), Readiness.BLOCKED)
        q7 = next(c for c in report.checks if c.check_id == "Q7")
        assert not q7.passed

    def test_ready_state_passes_q7(self):
        _, _, report = _run_full_pipeline(readiness=Readiness.READY_FOR_SIGNATURE_REVIEW)
        q7 = next(c for c in report.checks if c.check_id == "Q7")
        assert q7.passed


class TestQ8DocxRoundTrip:
    def test_docx_text_matches_rendered_text(self):
        _, _, report = _run_full_pipeline()
        q8 = next(c for c in report.checks if c.check_id == "Q8")
        assert q8.passed

    def test_corrupt_docx_fails_q8(self):
        rendered, _, _ = _run_full_pipeline()
        template, inputs, decisions, clause = _template(), _inputs(), _sample_decisions(), _sample_clause()
        report = run_qa(b"not a real docx file", rendered, template, inputs, decisions, clause, Readiness.NEEDS_REVIEW)
        q8 = next(c for c in report.checks if c.check_id == "Q8")
        assert not q8.passed
        assert not report.passed
