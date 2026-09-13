# Debug Log

Running diary of real failures hit while building, per docs/implementation.md §1.3.
Format per entry: **Symptom → Hypothesis → Evidence → Fix → Prevention → Time lost.**

This file is a demo asset (deck slide 4, D-40) — entries are written live, not reconstructed after the fact.

---

## Phase 0

*(no failures yet — the capability spike passed 10/10 on the first run; see docs/decision.md "Phase 0 Spike Results")*

### Finding: Vercel CDN auto-serves `public/index.html` at `/`, bypassing the FastAPI route
- **Symptom:** `GET /` on the live deployment returned `200` with the page body directly, not
  the `307` redirect to `/index.html` that `app.py`'s `@app.get("/")` handler returns. Locally
  (`uvicorn`, no CDN) the same route correctly returns `307`.
- **Hypothesis:** Vercel's FastAPI static-file promotion (architecture.md §10.1) serves
  `public/index.html` from the CDN as the default document at `/`, and CDN-served files bypass
  the function entirely (confirmed by response headers: `etag`/`last-modified` from the CDN, no
  `x-vercel-*` function markers) — not a routing bug in our code.
- **Evidence:** `curl -sI https://zycus-blond.vercel.app/` shows `cache-control: public,
  max-age=0, must-revalidate` and CDN-style caching headers; the same request locally goes
  through `uvicorn` and returns the `RedirectResponse`.
- **Fix:** none needed — this is the desired end-user behavior (the app loads at `/` with one
  fewer hop than the redirect). The `@app.get("/")` handler is kept as a harmless fallback for
  local dev without `SERVE_STATIC` and for any future case where `public/index.html` is absent.
- **Prevention:** documented here so a later phase doesn't mistake it for a bug when `/` doesn't
  appear to hit `app.py`.
- **Time lost:** ~3 minutes.


## Phase 2

### Bug: Q8 (docx round-trip) false-failed whenever a BLOCKED banner was present
- **Symptom:** `test_blocked_readiness_and_marker` (S02, missing governing law) failed QA check Q8
  ("docx text does not match RenderedDoc.full_text after reopening") even though the document
  itself was correct — Q1-Q7 all passed.
- **Hypothesis:** `RenderedDoc.full_text` and `write_docx()` build their output in a different
  paragraph order when a banner is present.
- **Evidence:** `write_docx()` adds the banner paragraph, then the title paragraph, then the body.
  `RenderedDoc.full_text` (in `tools/assembler.py`) listed `[self.title, banner, *paragraphs]` —
  title before banner, the reverse of what the .docx writer actually produces. Q8 normalizes and
  compares these two strings; with the order swapped, a real (correct) document could never match.
- **Fix:** reordered `full_text` to `[banner, title, *paragraphs]` to match `write_docx()` exactly,
  with a comment noting the two must stay in lockstep.
- **Prevention:** `tests/test_orchestrator.py::TestS02MissingGoverningLaw` now covers a BLOCKED
  run end-to-end, including `render_docx()` producing valid bytes — this exact class of ordering
  bug can't regress silently again.
- **Time lost:** ~10 minutes.

### Non-bug: S14's expected gate for `special_clause` was wrong (G7, not G5)
- **Symptom:** `test_special_clause_needs_review_via_g7` failed — the router set gate
  `G5_risk_shifting`, not `G7_ai_unavailable`, when `simulate_ai_failure=True`.
- **Hypothesis:** either the router's gate order was wrong, or the Phase 1 scenario file's
  expectation (written before the router existed) was wrong.
- **Evidence:** architecture.md §5.2's gate table and the router pseudocode in implementation.md
  both place G5 *before* G7 deliberately ("nothing risk-shifting can be rescued... by AI
  availability"). A non-empty special clause is G5 by design, regardless of whether the AI could
  analyze it — the human review requirement doesn't depend on AI uptime.
- **Fix:** this was **not a code bug** — corrected the test's expectation and
  `evals/scenarios/S14_ai_down.json`'s `gate` field to `G5_risk_shifting` (both were my own
  Phase 1 assumption, made before the router's exact precedence was implemented). Also enriched
  `FieldContext._reason()` so that when G5 fires *and* `ai_error` is set, the reason text still
  says AI analysis was unavailable — the reviewer needs that context even though it isn't what
  determined the status.
- **Prevention:** scenario files are a specification, but a wrong assumption in one is still
  possible — this is exactly why `evals/run.py` (task 2.10) prints *actual vs. expected*, not just
  pass/fail, so a mismatch like this is diagnosable at a glance rather than a mystery.
- **Time lost:** ~10 minutes.
