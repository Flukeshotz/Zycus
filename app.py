"""
FastAPI entrypoint — Vercel zero-config Python function (D-61, D-62).

Routes:
  GET  /api/health     — liveness + config sanity
  GET  /api/scenarios   — scenario presets (D-38)
  GET  /api/rulebook    — transparency tab
  POST /api/run         — full pipeline (LLM)
  POST /api/render      — apply reviewer actions (NO LLM, D-12/D-63)
  GET  /                — redirect to index.html
"""
from __future__ import annotations

import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, field_validator

from core.config import get_settings
from core.fake_llm import FakeLLM, LLMClient
from core.models import (
    BusinessInputs,
    RenderRequest,
    ReviewerAction,
    RunEnvelope,
    RunResult,
)
from core.orchestrator import render_docx, rerender, run
from core.signing import sign, verify
from tools.preview import rendered_doc_to_html
from tools.assembler import build_rendered_doc
from tools.template_store import get_template

app = FastAPI(title="Zycus Contract Authoring Agent")

# --- Input length caps (D-60) ------------------------------------------------
MAX_FIELD_LEN = 2000
MAX_EDITED_TEXT_LEN = 2000
INPUT_FIELDS = [
    "disclosing_party", "receiving_party", "effective_date", "term",
    "governing_law", "survival_period", "purpose", "special_clause",
    "payment_terms", "contract_value",
]


# --- Request/response models ------------------------------------------------

class RunRequest(BaseModel):
    inputs: BusinessInputs
    simulate_ai_failure: bool = False

    @field_validator("inputs")
    @classmethod
    def check_field_lengths(cls, v: BusinessInputs) -> BusinessInputs:
        for field_name in INPUT_FIELDS:
            val = getattr(v, field_name, "")
            if len(val) > MAX_FIELD_LEN:
                raise ValueError(f"Field '{field_name}' exceeds {MAX_FIELD_LEN} characters")
        return v


# --- Helpers ------------------------------------------------------------------

def _get_llm() -> LLMClient:
    settings = get_settings()
    if settings.llm_mode == "live":
        if settings.groq_key_configured:
            from core.llm import GroqLLM
            return GroqLLM()
        # Fall back to fake if key not configured
    return FakeLLM(tz=settings.app_timezone)


def _build_envelope(result: RunResult) -> dict[str, Any]:
    """Build and return a RunEnvelope as a dict, including preview_html
    and docx_base64."""
    sig = sign(result)

    # Build preview HTML from the same RenderedDoc as the .docx (D-52)
    template = get_template(result.inputs.contract_type)
    rendered = build_rendered_doc(
        template, result.inputs, result.decisions, result.clause,
        result.readiness,
        [ReviewerAction(field=d.field, action=d.reviewer_action, edited_text=d.edited_text)
         for d in result.decisions if d.reviewer_action is not None],
    )
    preview_html = rendered_doc_to_html(rendered)

    docx_base64: str | None = None
    if result.qa.passed:
        docx_bytes = render_docx(result)
        docx_base64 = base64.b64encode(docx_bytes).decode()

    envelope = RunEnvelope(
        run_result=result,
        signature=sig,
        preview_html=preview_html,
        docx_base64=docx_base64,
    )
    return envelope.model_dump(mode="json")


# --- Routes -------------------------------------------------------------------

@app.get("/api/health")
def health():
    settings = get_settings()
    now = datetime.now(ZoneInfo(settings.app_timezone))
    return {
        "status": "ok",
        "today_in_tz": now.isoformat(),
        "today_long_form": f"{now.day} {now:%B %Y}",
        "timezone": settings.app_timezone,
        "groq_key_configured": settings.groq_key_configured,
        "gemini_key_configured": settings.gemini_key_configured,
        "fallback_enabled": settings.enable_fallback,
        "models": {
            "normalizer": settings.model_normalizer,
            "analyst": settings.model_analyst,
            "verifier": settings.model_verifier,
            "fallback": settings.model_fallback,
        },
        "llm_mode": settings.llm_mode,
    }


@app.get("/api/scenarios")
def scenarios():
    scenarios_dir = Path(__file__).resolve().parent / "evals" / "scenarios"
    results = []
    for path in sorted(scenarios_dir.glob("S*.json")):
        with path.open() as f:
            data = json.load(f)
        results.append({
            "id": data["id"],
            "title": data["title"],
            "inputs": data["inputs"],
            "simulate_ai_failure": data.get("simulate_ai_failure", False),
        })
    return results


@app.get("/api/rulebook")
def rulebook_text():
    rulebook_path = Path(__file__).resolve().parent / "data" / "rulebook" / "nda_rules.yaml"
    return {"text": rulebook_path.read_text()}


@app.post("/api/run")
def run_pipeline(req: RunRequest):
    settings = get_settings()
    llm = _get_llm()
    now = datetime.now(ZoneInfo(settings.app_timezone))
    simulate = req.simulate_ai_failure or settings.force_ai_failure
    result = run(req.inputs, llm, now, tz=settings.app_timezone, simulate_ai_failure=simulate)
    return _build_envelope(result)


@app.post("/api/render")
def render_action(req: RenderRequest):
    # Validate edited text length
    for action in req.reviewer_actions:
        if action.edited_text and len(action.edited_text) > MAX_EDITED_TEXT_LEN:
            raise HTTPException(status_code=422, detail=f"Edited text for '{action.field}' exceeds {MAX_EDITED_TEXT_LEN} characters")

    # Verify signature (D-63)
    if not verify(req.run_result, req.signature):
        raise HTTPException(status_code=400, detail="Signature invalid — regenerate the draft")

    # Apply reviewer actions and re-render — NO LLM CALL (D-12, D-63)
    updated = rerender(req.run_result, req.reviewer_actions)
    return _build_envelope(updated)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return RedirectResponse("/vercel.svg", status_code=307)


@app.get("/")
def root():
    return RedirectResponse("/index.html", status_code=307)


# --- Local-only static file serving ---------------------------------------
# On Vercel, public/ is served by the CDN directly; do NOT mount it here
# (architecture.md §10, D-62). Locally there is no CDN, so mount it when
# SERVE_STATIC=true so `uvicorn app:app` still serves the frontend.
_settings = get_settings()
if _settings.serve_static:
    from fastapi.staticfiles import StaticFiles

    app.mount("/", StaticFiles(directory="public", html=True), name="static")
