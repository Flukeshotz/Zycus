# Zycus Contract Authoring Agent

An AI agent system that drafts a Mutual NDA from a template and business inputs — fills in what
it's confident about, and flags anything missing, ambiguous, or non-standard for a human to
decide. Built for the Zycus Product Intern (AI PM Track) take-home, Track A.

**Live URL:** _pending Phase 5 deploy_

## What it does

> Rules, not the AI, decide what's safe. Anything that shifts legal risk always goes to a human,
> and a final checker makes sure no blanks or wrong names reach the document.

- Fills a Mutual NDA template from structured business inputs
- Flags missing, ambiguous, or non-standard inputs instead of silently guessing
- Runs a two-phase agent (research with tools, then a strictly-typed decision) to assess
  non-standard clause requests against an approved clause library
- Verifies proposed clause language against required safeguards before showing it to a reviewer
- Produces a clean `.docx` draft plus a review report explaining every decision

Full design: [docs/architecture.md](docs/architecture.md) · every decision and why:
[docs/decision.md](docs/decision.md) · phase-by-phase build plan: [docs/implementation.md](docs/implementation.md).

## Stack

Python 3.12 · FastAPI (deployed as a Vercel Function) · [Groq](https://groq.com) (`gpt-oss-20b`,
`gpt-oss-120b`, `qwen3.8-27b`) · python-docx · a static HTML/JS frontend · optional Gemini
fallback on rate limits.

## Run locally

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # fill in GROQ_API_KEY, RUN_SIGNING_SECRET, etc.
python scripts/sdk_smoke.py   # capability check — confirms the Groq/Gemini APIs behave as expected
uvicorn app:app --reload --env-file .env
```

Open <http://127.0.0.1:8000/> (requires `SERVE_STATIC=true` in `.env`, which `.env.example` sets).

## Status

Currently at the end of **Phase 0** (repo, environment, capability spike, walking skeleton) of the
build plan in [docs/implementation.md](docs/implementation.md). See that file's §0 progress
tracker for what's done.

## Not legal advice

This is a simplified, non-binding sample for evaluation purposes. Output is a draft for human
review, not legal advice.
