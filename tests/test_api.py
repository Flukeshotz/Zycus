"""
API integration tests (implementation.md P4 task 4.4). Uses FastAPI's
TestClient with LLM_MODE=fake, so everything runs offline. Verifies:
- health has no secrets
- run S01 → valid envelope with signature
- render "accept" → readiness updates, no new LLM call
- tampered result → 400
- oversized input → 422
- signing round-trip
"""
from __future__ import annotations

import base64
import json
import os

import pytest

# Force fake mode and a known signing secret BEFORE importing the app.
os.environ["LLM_MODE"] = "fake"
os.environ["GROQ_API_KEY"] = ""
os.environ["SERVE_STATIC"] = "false"
os.environ["RUN_SIGNING_SECRET"] = "a" * 64

# Clear lru_cache for config so env vars above take effect
from core.config import get_settings
get_settings.cache_clear()

from fastapi.testclient import TestClient

from app import app
from core.models import ReviewerActionType

client = TestClient(app)

SAMPLE_INPUTS = {
    "contract_type": "mutual_nda",
    "disclosing_party": "Zycus Inc.",
    "receiving_party": "Northwind Vendor Solutions Pvt. Ltd.",
    "effective_date": "To be filled \u2014 use today's date",
    "term": "2 years from effective date",
    "governing_law": "State of Delaware, USA",
    "survival_period": "3 years after termination",
    "purpose": "Evaluating a potential vendor relationship for procurement software integration",
    "special_clause": "Receiving party wants a carve-out allowing disclosure to their affiliates without prior written consent",
    "payment_terms": "Not applicable \u2014 this is a Mutual NDA, not a commercial agreement",
    "contract_value": "",
}


class TestHealth:
    def test_health_returns_ok(self):
        res = client.get("/api/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "ok"

    def test_health_has_no_secrets(self):
        res = client.get("/api/health")
        text = res.text
        # Must not contain any API key or signing secret
        assert "gsk_" not in text
        assert os.environ.get("GROQ_API_KEY", "") not in text or not os.environ.get("GROQ_API_KEY")
        assert "RUN_SIGNING_SECRET" not in text
        assert "a" * 64 not in text  # our test signing secret


class TestScenarios:
    def test_scenarios_returns_list(self):
        res = client.get("/api/scenarios")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        assert len(data) >= 14
        assert data[0]["id"] == "S01"
        assert "inputs" in data[0]


class TestRulebook:
    def test_rulebook_returns_yaml_text(self):
        res = client.get("/api/rulebook")
        assert res.status_code == 200
        data = res.json()
        assert "text" in data
        assert "NDA-DISC-01" in data["text"]


class TestRunPipeline:
    def setup_method(self):
        res = client.post("/api/run", json={"inputs": SAMPLE_INPUTS})
        assert res.status_code == 200
        self.envelope = res.json()

    def test_envelope_has_required_fields(self):
        assert "run_result" in self.envelope
        assert "signature" in self.envelope
        assert "preview_html" in self.envelope

    def test_signature_is_hex_string(self):
        sig = self.envelope["signature"]
        assert isinstance(sig, str)
        assert len(sig) == 64  # SHA256 hex

    def test_run_result_has_decisions(self):
        rr = self.envelope["run_result"]
        assert len(rr["decisions"]) == 10

    def test_readiness_is_needs_review(self):
        assert self.envelope["run_result"]["readiness"] == "NEEDS_REVIEW"

    def test_preview_html_is_string(self):
        assert isinstance(self.envelope["preview_html"], str)
        assert len(self.envelope["preview_html"]) > 100

    def test_docx_base64_present_when_qa_passed(self):
        rr = self.envelope["run_result"]
        if rr["qa"]["passed"]:
            assert self.envelope["docx_base64"] is not None
            # Verify it's valid base64 that starts with PK (zip/docx)
            docx_bytes = base64.b64decode(self.envelope["docx_base64"])
            assert docx_bytes[:2] == b"PK"

    def test_qa_passed(self):
        assert self.envelope["run_result"]["qa"]["passed"]


class TestRenderAction:
    def setup_method(self):
        res = client.post("/api/run", json={"inputs": SAMPLE_INPUTS})
        assert res.status_code == 200
        self.original = res.json()

    def test_accept_proposed_updates_readiness(self):
        render_req = {
            "run_result": self.original["run_result"],
            "signature": self.original["signature"],
            "reviewer_actions": [
                {"field": "special_clause", "action": "accept_proposed"},
            ],
        }
        res = client.post("/api/render", json=render_req)
        assert res.status_code == 200
        updated = res.json()
        assert updated["run_result"]["readiness"] == "READY_FOR_SIGNATURE_REVIEW"

    def test_render_does_not_add_agent_trace_steps(self):
        """HITL clicks must never call the LLM (D-12)."""
        original_agent_steps = sum(
            1 for s in self.original["run_result"]["trace"]
            if s["kind"] == "agent"
        )
        render_req = {
            "run_result": self.original["run_result"],
            "signature": self.original["signature"],
            "reviewer_actions": [
                {"field": "special_clause", "action": "accept_proposed"},
            ],
        }
        res = client.post("/api/render", json=render_req)
        updated = res.json()
        updated_agent_steps = sum(
            1 for s in updated["run_result"]["trace"]
            if s["kind"] == "agent"
        )
        assert updated_agent_steps == original_agent_steps

    def test_tampered_status_returns_400(self):
        tampered = json.loads(json.dumps(self.original["run_result"]))
        tampered["readiness"] = "READY_FOR_SIGNATURE_REVIEW"
        render_req = {
            "run_result": tampered,
            "signature": self.original["signature"],
            "reviewer_actions": [],
        }
        res = client.post("/api/render", json=render_req)
        assert res.status_code == 400
        assert "signature" in res.json()["detail"].lower() or "Signature" in res.json()["detail"]

    def test_edit_text_without_safeguards_shows_warning_and_records_decision(self):
        """Task 4.5 & Verification step 3: Edit text without safeguards -> warning shown; decision recorded."""
        render_req = {
            "run_result": self.original["run_result"],
            "signature": self.original["signature"],
            "reviewer_actions": [
                {
                    "field": "special_clause",
                    "action": "edit",
                    "edited_text": "We can share with any external company whenever we choose.",
                },
            ],
        }
        res = client.post("/api/render", json=render_req)
        assert res.status_code == 200
        updated = res.json()
        assert updated["run_result"]["readiness"] == "READY_FOR_SIGNATURE_REVIEW"
        d = next(d for d in updated["run_result"]["decisions"] if d["field"] == "special_clause")
        assert d["reviewer_action"] == "edit"
        assert d["edited_text"] == "We can share with any external company whenever we choose."
        # Warning shown in info_notes
        assert any("Warning: edited text lacks required safeguard" in note for note in d["info_notes"])
        # Preview HTML contains the edited text
        assert "We can share with any external company whenever we choose." in updated["preview_html"]
        # Docx base64 is present and valid
        assert updated["docx_base64"] is not None

    def test_edit_text_with_safeguards_has_no_warning(self):
        safe_text = (
            "The Receiving Party may disclose to its Affiliates who have a need to know "
            "and are bound by confidentiality obligations, provided the Receiving Party remains liable."
        )
        render_req = {
            "run_result": self.original["run_result"],
            "signature": self.original["signature"],
            "reviewer_actions": [
                {"field": "special_clause", "action": "edit", "edited_text": safe_text},
            ],
        }
        res = client.post("/api/render", json=render_req)
        assert res.status_code == 200
        updated = res.json()
        d = next(d for d in updated["run_result"]["decisions"] if d["field"] == "special_clause")
        assert not any("Warning: edited text lacks" in note for note in d["info_notes"])
        assert safe_text in updated["preview_html"]

    def test_use_as_requested_inserts_original_request(self):
        render_req = {
            "run_result": self.original["run_result"],
            "signature": self.original["signature"],
            "reviewer_actions": [
                {"field": "special_clause", "action": "use_as_requested"},
            ],
        }
        res = client.post("/api/render", json=render_req)
        assert res.status_code == 200
        updated = res.json()
        assert updated["run_result"]["readiness"] == "READY_FOR_SIGNATURE_REVIEW"
        d = next(d for d in updated["run_result"]["decisions"] if d["field"] == "special_clause")
        assert d["reviewer_action"] == "use_as_requested"
        assert "Receiving party wants a carve-out allowing disclosure" in updated["preview_html"]

    def test_remove_clause_empties_slot(self):
        render_req = {
            "run_result": self.original["run_result"],
            "signature": self.original["signature"],
            "reviewer_actions": [
                {"field": "special_clause", "action": "remove"},
            ],
        }
        res = client.post("/api/render", json=render_req)
        assert res.status_code == 200
        updated = res.json()
        assert updated["run_result"]["readiness"] == "READY_FOR_SIGNATURE_REVIEW"
        d = next(d for d in updated["run_result"]["decisions"] if d["field"] == "special_clause")
        assert d["reviewer_action"] == "remove"


class TestInputValidation:
    def test_oversized_input_returns_422(self):
        oversized = dict(SAMPLE_INPUTS)
        oversized["special_clause"] = "x" * 2001
        res = client.post("/api/run", json={"inputs": oversized})
        assert res.status_code == 422

    def test_oversized_edited_text_returns_422(self):
        res = client.post("/api/run", json={"inputs": SAMPLE_INPUTS})
        envelope = res.json()
        render_req = {
            "run_result": envelope["run_result"],
            "signature": envelope["signature"],
            "reviewer_actions": [
                {"field": "special_clause", "action": "edit", "edited_text": "y" * 2001},
            ],
        }
        render_res = client.post("/api/render", json=render_req)
        assert render_res.status_code == 422


class TestSigning:
    def test_sign_verify_round_trip(self):
        from core.models import RunResult
        from core.signing import sign, verify

        res = client.post("/api/run", json={"inputs": SAMPLE_INPUTS})
        rr = RunResult(**res.json()["run_result"])
        sig = sign(rr)
        assert verify(rr, sig)

    def test_modified_result_fails_verification(self):
        from core.models import RunResult
        from core.signing import sign, verify

        res = client.post("/api/run", json={"inputs": SAMPLE_INPUTS})
        rr = RunResult(**res.json()["run_result"])
        sig = sign(rr)
        # Modify a field
        tampered = rr.model_copy(update={"readiness": "READY_FOR_SIGNATURE_REVIEW"})
        assert not verify(tampered, sig)
