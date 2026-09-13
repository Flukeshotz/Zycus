"""
FastAPI entrypoint — Vercel zero-config Python function (D-61, D-62).

Phase 0: only the health check and static-file wiring exist. Pipeline routes
(/api/run, /api/render, /api/scenarios, /api/rulebook) are added in P4.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from core.config import get_settings

app = FastAPI(title="Zycus Contract Authoring Agent")


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
        "phase": "P0 walking skeleton",
    }


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
