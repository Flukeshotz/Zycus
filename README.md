# Zycus Contract Authoring Agent

An AI agent system that drafts a Mutual NDA from a template and business inputs — fills in what
it's confident about, and flags anything missing, ambiguous, or non-standard for a human to
decide. Built for the Zycus Product Intern (AI PM Track) take-home, Track A.

**Live URL:** https://zycus-blond.vercel.app

## What it does

> Rules, not the AI, decide what's safe. Anything that shifts legal risk always goes to a human,
> and a final checker makes sure no blanks or wrong names reach the document.

An autonomous AI agent system that drafts a Mutual Non-Disclosure Agreement (NDA) from a standard template and raw business inputs. It deterministically fills standard terms, resolves relative dates, flags missing or ambiguous inputs, performs a two-phase tool research loop to assess non-standard clause requests against an approved library, validates required legal safeguards, enforces zero-token human-in-the-loop (HITL) review via HMAC-SHA256 signed envelopes, and compiles pixel-faithful `.docx` documents.

Full design: [docs/architecture.md](docs/architecture.md) · every decision and why:
[docs/decision.md](docs/decision.md) · phase-by-phase build plan: [docs/implementation.md](docs/implementation.md).

## Stack

Python 3.12 · FastAPI (deployed as a Vercel Function) · [Groq](https://groq.com) (`gpt-oss-20b`,
`gpt-oss-120b`, `qwen3.8-27b`) · python-docx · a static HTML/CSS/JS frontend · optional Gemini
fallback on rate limits.

## Environment Variables

Configure these in `.env` locally (copied from `.env.example`) or in Vercel Project Settings:

- `GROQ_API_KEY` — Groq API authentication key
- `RUN_SIGNING_SECRET` — HMAC-SHA256 signing secret for stateless HITL envelopes (≥32 bytes)
- `APP_TIMEZONE` — Timezone for effective date resolution and audit timestamps (e.g. `Asia/Kolkata`)
- `MODEL_NORMALIZER` — Model ID for field intake normalization (default `openai/gpt-oss-20b`)
- `MODEL_ANALYST` — Model ID for two-phase clause assessment tool loop (default `openai/gpt-oss-120b`)
- `MODEL_VERIFIER` — Model ID for clause safeguard verification (default `qwen/qwen3.8-27b`)
- `MODEL_FALLBACK` — Fallback model ID (default `gemini-3.5-flash`)
- `PARALLEL` — Run intake normalization and clause analysis concurrently (`true`/`false`)
- `LLM_MODE` — Execution mode (`live` for Groq API, `fake` for offline testing)
- `SERVE_STATIC` — Serve `public/` directory via FastAPI locally (`true`/`false`)
- `GEMINI_API_KEY` — Optional Gemini API key for cross-provider fallback
- `ENABLE_FALLBACK` — Enable Gemini fallback on Groq rate limits (`true`/`false`)
- `FORCE_AI_FAILURE` — Force fallback degraded path for outage demonstrations (`true`/`false`)

## Run Locally

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # fill in your keys and secrets
python scripts/sdk_smoke.py   # verify Groq API connectivity and models
uvicorn app:app --reload --env-file .env
```

Open <http://127.0.0.1:8000/> (requires `SERVE_STATIC=true` in `.env`).

## Live Fallback (ngrok)

If Vercel experiences platform unavailability during evaluation:

```bash
source .venv/bin/activate
SERVE_STATIC=true LLM_MODE=live uvicorn app:app --port 8000 &
ngrok http 8000
```
Share the generated `https://<id>.ngrok-free.app` URL as the live fallback.

## Status

Currently at **Phase 5** (Vercel Production Deploy + Live Smoke Test complete) of the build plan in [docs/implementation.md](docs/implementation.md). Production deployment is live and passing all smoke tests.

## Not Legal Advice

This is a simplified, non-binding sample for evaluation purposes. Output is a draft for human review, not legal advice.
