"""
Clause Analyst unit tests (no network) — tool execution, evidence
accounting, auto-retrieval, and rule-citation validation. The full
research -> decision flow against the real API is verified live via
evals/run.py --live --only S01,S04,S07,S08 per implementation.md.
"""
from __future__ import annotations

import json

from agents.clause_analyst import (
    EvidencePack,
    _ensure_minimum,
    _execute_tool,
    _validate_rule_citations,
)
from core.models import ClauseAssessment, Confidence


class TestExecuteTool:
    def test_get_rules_known_topic(self):
        evidence = EvidencePack()
        output = _execute_tool("get_rules", json.dumps({"topic": "disclosure_to_third_parties"}), evidence)
        data = json.loads(output)
        assert data
        assert data[0]["id"] == "NDA-DISC-01"
        assert evidence.rules["disclosure_to_third_parties"] == data

    def test_get_rules_unknown_topic_returns_empty(self):
        evidence = EvidencePack()
        output = _execute_tool("get_rules", json.dumps({"topic": "nonexistent"}), evidence)
        assert json.loads(output) == []

    def test_search_clause_library_matches(self):
        evidence = EvidencePack()
        output = _execute_tool(
            "search_clause_library",
            json.dumps({"query": "disclose to affiliates without consent"}),
            evidence,
        )
        data = json.loads(output)
        assert data
        assert data[0]["id"] == "affiliate_disclosure"
        assert evidence.library_results == data

    def test_get_template_section_known(self):
        evidence = EvidencePack()
        output = _execute_tool("get_template_section", json.dumps({"section": "5"}), evidence)
        data = json.loads(output)
        assert "Permitted Disclosures" in data["text"]
        assert evidence.template_sections["5"] == data["text"]

    def test_get_template_section_unknown_returns_error_not_exception(self):
        evidence = EvidencePack()
        output = _execute_tool("get_template_section", json.dumps({"section": "99"}), evidence)
        data = json.loads(output)
        assert "error" in data

    def test_unknown_tool_name(self):
        evidence = EvidencePack()
        output = _execute_tool("delete_everything", "{}", evidence)
        assert output.startswith("ERROR:")

    def test_malformed_json_arguments(self):
        evidence = EvidencePack()
        output = _execute_tool("get_rules", "{not valid json", evidence)
        assert output.startswith("ERROR:")

    def test_empty_arguments_string(self):
        evidence = EvidencePack()
        output = _execute_tool("get_rules", "", evidence)
        assert json.loads(output) == []  # topic defaults to "" -> no matching rules


class TestEnsureMinimum:
    def test_fills_both_when_model_skipped_everything(self):
        evidence = EvidencePack()
        _ensure_minimum(evidence, "affiliate disclosure request")
        assert evidence.rules
        assert evidence.library_results
        assert set(evidence.auto_retrieved) == {"get_rules", "search_clause_library"}

    def test_does_not_overwrite_existing_evidence(self):
        evidence = EvidencePack()
        _execute_tool("get_rules", json.dumps({"topic": "disclosure_to_third_parties"}), evidence)
        _ensure_minimum(evidence, "affiliate disclosure request")
        assert evidence.auto_retrieved == ["search_clause_library"]

    def test_no_auto_retrieval_when_model_did_its_job(self):
        evidence = EvidencePack()
        _execute_tool("get_rules", json.dumps({"topic": "disclosure_to_third_parties"}), evidence)
        _execute_tool("search_clause_library", json.dumps({"query": "affiliate"}), evidence)
        _ensure_minimum(evidence, "affiliate disclosure request")
        assert evidence.auto_retrieved == []


class TestRuleIds:
    def test_rule_ids_collected_across_topics(self):
        evidence = EvidencePack()
        _execute_tool("get_rules", json.dumps({"topic": "disclosure_to_third_parties"}), evidence)
        assert "NDA-DISC-01" in evidence.rule_ids()

    def test_empty_evidence_has_no_rule_ids(self):
        assert EvidencePack().rule_ids() == set()


class TestValidateRuleCitations:
    def _assessment(self, rule_ids_cited):
        return ClauseAssessment(
            request_summary="x", library_match=None, deviation="non_standard",
            risks=[], conflicting_sections=[], rule_ids_cited=rule_ids_cited,
            proposed_text=None, proposed_text_source="none", confidence=Confidence.MEDIUM,
        )

    def test_valid_citation_kept(self):
        evidence = EvidencePack()
        _execute_tool("get_rules", json.dumps({"topic": "disclosure_to_third_parties"}), evidence)
        assessment = self._assessment(["NDA-DISC-01"])
        result = _validate_rule_citations(assessment, evidence)
        assert result.rule_ids_cited == ["NDA-DISC-01"]

    def test_invented_citation_stripped(self):
        evidence = EvidencePack()
        _execute_tool("get_rules", json.dumps({"topic": "disclosure_to_third_parties"}), evidence)
        assessment = self._assessment(["NDA-DISC-01", "NDA-MADE-UP-99"])
        result = _validate_rule_citations(assessment, evidence)
        assert result.rule_ids_cited == ["NDA-DISC-01"]

    def test_no_evidence_strips_all_citations(self):
        evidence = EvidencePack()
        assessment = self._assessment(["NDA-DISC-01"])
        result = _validate_rule_citations(assessment, evidence)
        assert result.rule_ids_cited == []
