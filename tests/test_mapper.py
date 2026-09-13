"""Mapper tests (implementation.md P2 task 2.3)."""
from __future__ import annotations

from core.models import BusinessInputs, FieldDecision, FieldStatus
from tools import mapper, template_store


def _template():
    return template_store.get_template("mutual_nda")


def _sample_inputs():
    return BusinessInputs(
        disclosing_party="Zycus Inc.",
        receiving_party="Northwind Vendor Solutions Pvt. Ltd.",
        effective_date="use today's date",
        term="2 years",
        governing_law="Delaware, USA",
        survival_period="3 years",
        purpose="Evaluating a vendor relationship",
        special_clause="",
        payment_terms="",
        contract_value="",
    )


def test_is_required_true_for_required_placeholder_field():
    assert mapper.is_required(_template(), "governing_law") is True


def test_is_required_false_for_optional_placeholder_field():
    assert mapper.is_required(_template(), "special_clause") is False


def test_is_required_false_for_unmapped_field():
    assert mapper.is_required(_template(), "payment_terms") is False


def test_placeholder_for_field_matches():
    tpl = _template()
    assert mapper.placeholder_for_field(tpl, "governing_law") == "GOVERNING LAW"
    assert mapper.placeholder_for_field(tpl, "special_clause") == "SPECIAL CLAUSE, IF ANY"
    assert mapper.placeholder_for_field(tpl, "effective_date") == "EFFECTIVE DATE"


def test_placeholder_for_field_none_for_unmapped():
    tpl = _template()
    assert mapper.placeholder_for_field(tpl, "payment_terms") is None
    assert mapper.placeholder_for_field(tpl, "contract_value") is None


def test_unmapped_input_fields_are_exactly_payment_and_value():
    tpl = _template()
    unmapped = mapper.unmapped_input_fields(tpl, _sample_inputs())
    assert set(unmapped) == {"payment_terms", "contract_value"}


def test_map_decisions_to_placeholders():
    tpl = _template()
    decisions = [
        FieldDecision(field="governing_law", status=FieldStatus.AUTO_FILLED, gate="G11_default",
                      value_for_document="Delaware, USA", reason="ok"),
        FieldDecision(field="term", status=FieldStatus.AUTO_FILLED, gate="G11_default",
                      value_for_document="2 years", reason="ok"),
    ]
    result = mapper.map_decisions_to_placeholders(tpl, decisions)
    assert result["GOVERNING LAW"] == "Delaware, USA"
    assert result["TERM"] == "2 years"
    # placeholders with no matching decision resolve to None, not KeyError
    assert result["SURVIVAL PERIOD"] is None


def test_map_decisions_to_placeholders_covers_every_placeholder():
    tpl = _template()
    result = mapper.map_decisions_to_placeholders(tpl, [])
    assert set(result.keys()) == set(tpl.placeholders.keys())
    assert all(v is None for v in result.values())
