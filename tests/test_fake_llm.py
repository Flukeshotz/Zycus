"""FakeLLM tests (implementation.md P2 task 2.8)."""
from __future__ import annotations

import pytest

from core.exceptions import AIUnavailable
from core.fake_llm import FakeLLM
from core.models import BusinessInputs, Interpretation


def _sample_inputs(**overrides) -> BusinessInputs:
    base = dict(
        disclosing_party="Zycus Inc.",
        receiving_party="Northwind Vendor Solutions Pvt. Ltd.",
        effective_date="To be filled — use today's date",
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


class TestNormalize:
    def test_normalizes_all_ten_fields(self):
        llm = FakeLLM()
        result = llm.normalize(_sample_inputs())
        assert {f.field for f in result.fields} == {
            "disclosing_party", "receiving_party", "effective_date", "term",
            "governing_law", "survival_period", "purpose", "special_clause",
            "payment_terms", "contract_value",
        }

    def test_effective_date_derived(self):
        llm = FakeLLM()
        result = llm.normalize(_sample_inputs())
        nf = next(f for f in result.fields if f.field == "effective_date")
        assert nf.interpretation == Interpretation.DERIVED

    def test_explicit_effective_date_is_clear(self):
        llm = FakeLLM()
        result = llm.normalize(_sample_inputs(effective_date="1 October 2026"))
        nf = next(f for f in result.fields if f.field == "effective_date")
        assert nf.interpretation == Interpretation.CLEAR
        assert nf.normalized_value == "1 October 2026"

    def test_term_parses_to_24_months(self):
        llm = FakeLLM()
        result = llm.normalize(_sample_inputs())
        nf = next(f for f in result.fields if f.field == "term")
        assert nf.duration_months == 24
        assert nf.interpretation == Interpretation.CLEAR

    def test_ambiguous_term_flagged(self):
        llm = FakeLLM()
        result = llm.normalize(_sample_inputs(term="until the project is completed"))
        nf = next(f for f in result.fields if f.field == "term")
        assert nf.interpretation == Interpretation.AMBIGUOUS
        assert nf.duration_months is None

    def test_payment_terms_not_applicable(self):
        llm = FakeLLM()
        result = llm.normalize(_sample_inputs())
        nf = next(f for f in result.fields if f.field == "payment_terms")
        assert nf.interpretation == Interpretation.NOT_APPLICABLE

    def test_payment_terms_real_value_is_clear(self):
        llm = FakeLLM()
        result = llm.normalize(_sample_inputs(payment_terms="Net 90"))
        nf = next(f for f in result.fields if f.field == "payment_terms")
        assert nf.interpretation == Interpretation.CLEAR
        assert nf.normalized_value == "Net 90"

    def test_missing_governing_law(self):
        llm = FakeLLM()
        result = llm.normalize(_sample_inputs(governing_law=""))
        nf = next(f for f in result.fields if f.field == "governing_law")
        assert nf.interpretation == Interpretation.MISSING

    def test_empty_special_clause_is_not_applicable(self):
        llm = FakeLLM()
        result = llm.normalize(_sample_inputs(special_clause=""))
        nf = next(f for f in result.fields if f.field == "special_clause")
        assert nf.interpretation == Interpretation.NOT_APPLICABLE

    def test_normalize_never_raises_even_when_simulating_failure(self):
        # Only the AI-judgment step (assess_clause) degrades; deterministic
        # parsing keeps working (D-13, S14).
        llm = FakeLLM(simulate_ai_failure=True)
        result = llm.normalize(_sample_inputs())
        nf = next(f for f in result.fields if f.field == "effective_date")
        assert nf.interpretation == Interpretation.DERIVED


class TestAssessClause:
    def test_matches_affiliate_library_entry(self):
        llm = FakeLLM()
        result = llm.assess_clause(_sample_inputs().special_clause)
        assert result.library_match == "affiliate_disclosure"
        assert result.proposed_text_source == "library"
        assert result.proposed_text is not None
        assert result.deviation == "non_standard"
        assert 5 in result.conflicting_sections

    def test_no_match_returns_none_source(self):
        llm = FakeLLM()
        result = llm.assess_clause("Receiving party wants unrelated permission to use a pet unicorn.")
        assert result.library_match is None
        assert result.proposed_text is None
        assert result.proposed_text_source == "none"

    def test_simulated_failure_raises(self):
        llm = FakeLLM(simulate_ai_failure=True)
        with pytest.raises(AIUnavailable):
            llm.assess_clause("affiliate disclosure")
