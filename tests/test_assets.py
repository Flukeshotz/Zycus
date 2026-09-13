"""
Phase 1 exit-gate tests (implementation.md P1, D-49).

Covers: template loads with exactly 8 placeholders and 8 sections in order;
rulebook and clause library load and validate; all 14 scenario files
validate, with must_pass flags on the required subset; strict_schema still
passes on the real models (belt-and-braces re-check of Phase 0's spike).
"""
from __future__ import annotations

import pytest

from core.models import NormalizedInputs, ClauseAssessment, VerificationResult
from core.schema import strict_schema
from evals.scenario_schema import load_all_scenarios
from tools import clause_library, rulebook, template_store

EXPECTED_PLACEHOLDERS = {
    "EFFECTIVE DATE",
    "DISCLOSING PARTY",
    "RECEIVING PARTY",
    "PURPOSE OF DISCLOSURE",
    "TERM",
    "SURVIVAL PERIOD",
    "SPECIAL CLAUSE, IF ANY",
    "GOVERNING LAW",
}

EXPECTED_SECTIONS = ["preamble", "1", "2", "3", "4", "5", "6", "7"]

MUST_PASS_IDS = {"S01", "S02", "S05", "S06", "S08", "S14"}


# ---------------------------------------------------------------------------
# Template
# ---------------------------------------------------------------------------


def test_template_loads():
    tpl = template_store.get_template("mutual_nda")
    assert tpl.id == "mutual_nda"
    assert tpl.title == "MUTUAL NON-DISCLOSURE AGREEMENT"


def test_template_has_exactly_8_placeholders():
    tpl = template_store.get_template("mutual_nda")
    assert set(tpl.placeholders.keys()) == EXPECTED_PLACEHOLDERS
    assert len(tpl.placeholders) == 8


def test_template_sections_in_order():
    tpl = template_store.get_template("mutual_nda")
    assert tpl.sections == EXPECTED_SECTIONS


def test_only_special_clause_is_optional():
    tpl = template_store.get_template("mutual_nda")
    optional = [name for name, spec in tpl.placeholders.items() if not spec.required]
    assert optional == ["SPECIAL CLAUSE, IF ANY"]


def test_unsupported_contract_type_raises():
    with pytest.raises(template_store.UnsupportedContractType):
        template_store.get_template("nonexistent_contract_type")


def test_get_section_returns_verbatim_text():
    text = template_store.get_section("mutual_nda", "4")
    assert "Restrictions on Use and Disclosure" in text
    assert "[SPECIAL CLAUSE, IF ANY]" in text


# ---------------------------------------------------------------------------
# Rulebook
# ---------------------------------------------------------------------------


def test_rulebook_loads():
    rb = rulebook.get_rulebook()
    assert rb.version == 1
    assert "Zycus Inc." in rb.our_entities


def test_rulebook_has_expected_rule_ids():
    rb = rulebook.get_rulebook()
    ids = {r.id for r in rb.rules}
    assert ids == {"NDA-TERM-01", "NDA-SURV-01", "NDA-LAW-01", "NDA-DISC-01"}


def test_rulebook_not_applicable_list():
    fields = rulebook.not_applicable_fields("mutual_nda")
    assert set(fields) == {
        "payment_terms", "contract_value", "indemnification_cap", "liability_cap",
    }


def test_rulebook_entity_helpers():
    assert rulebook.is_our_entity("Zycus Inc.")
    assert rulebook.is_our_entity("  zycus inc.  ")  # case/whitespace tolerant
    assert not rulebook.is_our_entity("Northwind Vendor Solutions Pvt. Ltd.")
    assert rulebook.has_entity_designator("Northwind Vendor Solutions Pvt. Ltd.")
    assert not rulebook.has_entity_designator("Northwind")


def test_rulebook_get_rules_by_topic():
    rules = rulebook.get_rules_by_topic("disclosure_to_third_parties")
    assert len(rules) == 1
    assert rules[0].id == "NDA-DISC-01"


def test_rulebook_rejects_duplicate_ids(tmp_path, monkeypatch):
    import yaml
    from tools.rulebook import Rulebook

    bad = {
        "version": 1,
        "our_entities": ["Zycus Inc."],
        "entity_designators": ["Inc."],
        "rules": [{"id": "DUP"}, {"id": "DUP"}],
        "not_applicable_for": {"mutual_nda": []},
    }
    with pytest.raises(ValueError, match="duplicate rule ids"):
        Rulebook.model_validate(bad)


# ---------------------------------------------------------------------------
# Clause library
# ---------------------------------------------------------------------------


def test_clause_library_loads():
    entries = clause_library.get_library()
    assert len(entries) >= 1
    assert clause_library.get_entry("affiliate_disclosure") is not None


def test_clause_library_search_matches_affiliate_request():
    results = clause_library.search(
        "Receiving party wants a carve-out allowing disclosure to their affiliates "
        "without prior written consent"
    )
    assert results
    assert results[0].id == "affiliate_disclosure"


def test_clause_library_search_no_match_returns_empty():
    results = clause_library.search("a completely unrelated request about pineapples")
    assert results == []


def test_clause_library_entry_satisfies_required_safeguards():
    entry = clause_library.get_entry("affiliate_disclosure")
    rule = rulebook.get_rule("NDA-DISC-01")
    required = set(rule.required_safeguards)
    assert required.issubset(set(entry.satisfies))


# ---------------------------------------------------------------------------
# Scenario files
# ---------------------------------------------------------------------------


def test_all_14_scenarios_load_and_validate():
    scenarios = load_all_scenarios()
    assert len(scenarios) == 14
    assert {s.id for s in scenarios} == {f"S{i:02d}" for i in range(1, 15)}


def test_must_pass_flags_on_required_subset():
    scenarios = {s.id: s for s in load_all_scenarios()}
    for sid in MUST_PASS_IDS:
        assert scenarios[sid].must_pass, f"{sid} should be must_pass"
    for sid, s in scenarios.items():
        if sid not in MUST_PASS_IDS:
            assert not s.must_pass, f"{sid} should not be must_pass"


def test_s14_simulates_ai_failure():
    scenarios = {s.id: s for s in load_all_scenarios()}
    assert scenarios["S14"].simulate_ai_failure is True
    for sid, s in scenarios.items():
        if sid != "S14":
            assert s.simulate_ai_failure is False, f"{sid} should not simulate AI failure"


def test_scenario_inputs_cover_all_business_input_fields():
    from core.models import BusinessInputs

    expected_fields = set(BusinessInputs.model_fields.keys())
    for s in load_all_scenarios():
        assert set(s.inputs.keys()) == expected_fields, f"{s.id} has mismatched input fields"


# ---------------------------------------------------------------------------
# Strict schema re-check (belt-and-braces on top of the Phase 0 spike)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("model", [NormalizedInputs, ClauseAssessment, VerificationResult])
def test_llm_output_models_pass_strict_schema(model):
    schema = strict_schema(model)
    _assert_strict(schema)


def _assert_strict(node, path="root"):
    if isinstance(node, dict):
        if node.get("type") == "object" or "properties" in node:
            assert node.get("additionalProperties") is False, f"{path}: additionalProperties not false"
            props = node.get("properties", {})
            assert set(node.get("required", [])) == set(props.keys()), f"{path}: required != properties"
        for k, v in node.items():
            _assert_strict(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _assert_strict(v, f"{path}[{i}]")
