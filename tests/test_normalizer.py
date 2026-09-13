"""Normalizer agent unit tests — the completeness guard only (no network)."""
from __future__ import annotations

from agents.normalizer import _FIELD_NAMES, _ensure_all_fields_present
from core.models import BusinessInputs, Confidence, Interpretation, NormalizedField, NormalizedInputs


def _inputs():
    return BusinessInputs(
        disclosing_party="Zycus Inc.", receiving_party="Northwind Pvt. Ltd.",
        effective_date="today", term="2 years", governing_law="Delaware, USA",
        survival_period="3 years", purpose="eval", special_clause="",
        payment_terms="", contract_value="",
    )


def _complete_field(name: str) -> NormalizedField:
    return NormalizedField(
        field=name, raw_value="x", normalized_value="x", duration_months=None,
        interpretation=Interpretation.CLEAR, confidence=Confidence.HIGH, reason="ok",
    )


class TestEnsureAllFieldsPresent:
    def test_complete_response_unchanged(self):
        result = NormalizedInputs(fields=[_complete_field(n) for n in _FIELD_NAMES])
        filled = _ensure_all_fields_present(result, _inputs())
        assert {f.field for f in filled.fields} == set(_FIELD_NAMES)
        assert len(filled.fields) == 10

    def test_missing_field_filled_conservatively(self):
        partial = NormalizedInputs(fields=[_complete_field(n) for n in _FIELD_NAMES if n != "governing_law"])
        filled = _ensure_all_fields_present(partial, _inputs())
        assert {f.field for f in filled.fields} == set(_FIELD_NAMES)
        gl = next(f for f in filled.fields if f.field == "governing_law")
        assert gl.interpretation == Interpretation.AMBIGUOUS
        assert gl.confidence == Confidence.LOW

    def test_multiple_missing_fields_all_filled(self):
        partial = NormalizedInputs(fields=[_complete_field(n) for n in _FIELD_NAMES[:5]])
        filled = _ensure_all_fields_present(partial, _inputs())
        assert len(filled.fields) == 10
        assert {f.field for f in filled.fields} == set(_FIELD_NAMES)

    def test_empty_response_fully_filled(self):
        empty = NormalizedInputs(fields=[])
        filled = _ensure_all_fields_present(empty, _inputs())
        assert len(filled.fields) == 10
        assert all(f.interpretation == Interpretation.AMBIGUOUS for f in filled.fields)
