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


## Phase 3

### Bug: live effective_date leaked the raw "use today's date" instruction text into the document
- **Symptom:** the very first live run against the real Groq API failed QA check Q2 ("today's date"
  found in slot text), even though the exact same pipeline logic had passed 14/14 offline. The
  rendered document read "...entered into as of **To be filled — use today's date**, by and
  between...".
- **Hypothesis:** `agents/normalizer.py`'s system prompt tells the model *"do not guess an actual
  date; the caller resolves this"* for a DERIVED effective date — correct guidance, since only the
  deterministic layer should decide what "today" means (D-15) — but nothing in the orchestrator
  actually *was* "the caller" that resolves it. FakeLLM never exposed this gap because its
  `_date_field()` always calls `tools/parser.py::parse_date()` directly and sets `normalized_value`
  itself, regardless of interpretation — it never depends on an external resolution step existing.
- **Evidence:** trace showed `normalize` step succeeded (`interpretation=DERIVED`), but
  `FieldContext.value_for_document` for `effective_date` fell through to `raw_value` because
  `normalized.normalized_value` was `None` — exactly what a *compliant* response to the prompt's own
  instruction looks like.
- **Fix:** added `core/orchestrator.py::_canonicalize_parsed_fields()`, called once after
  `_understand()` returns (for both FakeLLM and GroqLLM): if `effective_date` is DERIVED and
  `normalized_value` is still empty, resolve it via `format_long_date(now.date())` using the same
  `now` the whole run is timestamped with.
- **Prevention:** `tests/test_orchestrator.py::TestCanonicalizeParsedFields` reproduces the exact
  fixture a compliant live response looks like (`normalized_value=None`, `interpretation=DERIVED`)
  without needing a live API call, so this class of prompt/orchestrator mismatch can't regress
  silently. `TestS01SampleEndToEnd` also now asserts the resolved value contains no "today" text.
- **Time lost:** ~15 minutes (caught immediately by Q2 — the QA gate did exactly its job).

### Bug: live term/survival_period showed the raw input phrase instead of a clean value
- **Symptom:** on the *same* first live run, Section 3 read "...shall remain in effect for **2 years
  from effective date** from the Effective Date..." — the model's raw input phrase, echoed verbatim,
  producing an awkward, redundant sentence (not caught by QA, since none of "2 years from effective
  date" matches Q2's forbidden-literal list — this one was caught by manually reading the rendered
  document, not automatically).
- **Hypothesis:** the Normalizer prompt asks for "a clean version of the value" in `normalized_value`,
  but the live model returned the raw text unchanged for `term`/`survival_period`, while correctly
  computing `duration_months` (24, 36) — so the *number* was right but the *display text* wasn't.
  FakeLLM can't exhibit this either: its `_duration_field()` always formats `normalized_value` as
  `f"{duration.months} months"` from the parser, never from raw text.
- **Evidence:** live trace + a direct read of the rendered `.docx` (`python -c "import docx; ..."`)
  showing the exact malformed sentence; `duration_months=24` was correct, `normalized_value="2 years
  from effective date"` was not.
- **Fix:** generalized the effective_date fix into `_canonicalize_parsed_fields()`: for `term` and
  `survival_period`, whenever `tools/parser.py::parse_duration()` can parse the raw input, its
  canonical formatting (`"<N> months"` or `"perpetual"`) always wins over whatever the model put in
  `normalized_value` — the parser is now the single source of truth for how these fields *display*,
  regardless of which LLMClient produced the surrounding NormalizedField. This does **not** touch
  `duration_months` itself, so G9's live/parser cross-check is unaffected and still catches a genuine
  disagreement on the *number*, independent of this display-text fix.
- **Prevention:** `tests/test_orchestrator.py::TestCanonicalizeParsedFields` reproduces this exact bug
  (`normalized_value` set to the raw phrase, `duration_months` correct) and asserts the canonical
  value wins; also covers perpetual survival and an ambiguous term (must stay untouched, since the
  parser can't parse it either). Re-ran live after the fix: QA passed, Section 3 reads "...for 24
  months from the Effective Date. ...survive termination for a period of 36 months." — confirmed by
  re-reading the actual generated `.docx`, not just trusting `qa.passed`.
- **Time lost:** ~15 minutes (found by manually reading document output — a reminder that QA's
  forbidden-literal scan (Q2) is not a substitute for actually reading a live-generated document at
  least once per phase).

**Both fixes share one lesson:** FakeLLM's correctness at 14/14 offline said nothing about whether a
real, prompt-compliant model response would behave the same way — the two are different behaviors
that happen to converge on the *same field statuses* while producing *different displayed text*. The
first live run is what actually exercises the gap between "the router routes correctly" (proven
offline) and "the document reads correctly" (only checkable against a real model).

### Bug: intermittent effective_date failure via G8 ambiguity in live evals
- **Symptom:** `evals.run --live --only S01,S04,S07,S08` failed on S01 (`effective_date: expected
  status AUTO_FILLED_WITH_ASSUMPTION, got NEEDS_REVIEW`), even though single runs often passed.
- **Hypothesis:** two interacting causes:
  1. The live model sometimes returned a non-empty string in `normalized_value` (`"use today's date"`)
     rather than `None`, which an earlier `not normalized_value` check treated as "already resolved"
     and skipped.
  2. The prompt in `agents/normalizer.py` lacked confidence definitions; in ~30% of calls, the model
     rated `confidence: "medium"` (reason: *"Date is to be determined; requires current date"*),
     conflating uncertainty in the classification with the fact that the date itself was derived.
     Because gate `G8_ambiguity` checks `confidence in (MEDIUM, LOW)` and precedes `G10_assumption`,
     medium confidence forced `NEEDS_REVIEW`.
- **Evidence:** a 10-iteration live loop revealed 3/10 calls returned `conf=medium` with reasons
  stating the date must be determined at execution.
- **Fix:**
  1. Made `effective_date` canonicalization in `core/orchestrator.py` unconditional for `DERIVED`
     fields: the deterministic parser's resolved date always replaces whatever the model put in
     `normalized_value`.
  2. Added explicit confidence guidelines with examples to `agents/normalizer.py` (`SYSTEM` prompt),
     clarifying that recognizing an explicit instruction like "use today's date" as `derived` is
     high confidence.
- **Prevention:** 10-iteration re-run verified 10/10 calls produced `interp=derived conf=high`;
  regression tests in `tests/test_orchestrator.py::TestCanonicalizeParsedFields` enforce unconditional
  override; live evals (`S01,S04,S07,S08` and `S14`) all 100% green.
- **Time lost:** ~15 minutes.


## Phase 4

### Bug: NameError on ReviewerActionType in `core/orchestrator.py`
- **Symptom:** `POST /api/render` returned HTTP 500 when called with `action="edit"`.
- **Hypothesis:** `ReviewerActionType` enum was referenced in `rerender()` without being imported.
- **Evidence:** Server log in `task-6991.log` reported `NameError: name 'ReviewerActionType' is not defined. Did you mean: 'ReviewerAction'?`.
- **Fix:** Added `ReviewerActionType` to the `core.models` import in `core/orchestrator.py`.
- **Prevention:** `tests/test_api.py::TestRenderAction::test_edit_text_without_safeguards_shows_warning_and_records_decision` tests the `edit` route directly.
- **Time lost:** ~2 minutes.


## Phase 5

### Finding / Deploy Bug: `vercel.json` excludeFiles stripped `evals/scenarios/**`
- **Symptom:** On the Vercel deployment, `GET /api/scenarios` initially returned an empty list `[]`, causing the "Try a scenario" dropdown on the frontend to display no presets.
- **Hypothesis:** `vercel.json`'s `excludeFiles` glob pattern included `evals/scenarios/**`, stripping the JSON scenario definition files from the serverless function bundle.
- **Evidence:** Comparing `vercel.json` against `docs/architecture.md` §10 showed that `evals/results/**` was meant to be excluded, but `evals/scenarios/**` was accidentally added to `excludeFiles`. Locally, the directory existed, but on Vercel lambda filesystem, `Path("evals/scenarios").glob("S*.json")` yielded 0 matches.
- **Fix:** Updated `excludeFiles` in `vercel.json` to `{tests/**,docs/**,scripts/**,evals/results/**}` so `evals/scenarios/` is bundled with `app.py`.
- **Prevention:** Phase 5 live smoke test script explicitly verifies `requests.get(BASE_URL + "/api/scenarios").json()` contains all 14 scenarios and checks `len(scenarios) >= 14`.
- **Time lost:** ~3 minutes.


## Phase 6

### Rate-Limit Management: Dynamic token pacing for Groq free-tier eval runs
- **Symptom:** Sequential live evaluations over multiple models (Normalizer `gpt-oss-20b`, Clause Analyst `gpt-oss-120b`, Verifier `qwen3.8-27b`) risk depleting Groq's 8,000 TPM free-tier quota when run in rapid succession, which could cause 429 errors.
- **Hypothesis:** Groq returns `x-ratelimit-remaining-tokens` in response headers (captured by `GroqLLM.last_call`). Dynamically pacing evaluations based on remaining headroom prevents quota exhaustion without arbitrarily long fixed sleeps.
- **Evidence:** In live runs, remaining tokens dipped as low as 32-42 tokens after complex multi-step scenarios (e.g. S04, S05, S08). With graduated backoff (`<1000` tokens → 20s pause, `<2500` → 12s pause, `<4000` → 6s pause), 6/6 must-pass scenarios completed ×2 repeats (12 executions) with zero flakiness and zero 429s. The full 14-scenario live run subsequently passed 14/14 (100.0%) completely green.
- **Fix:** Implemented smart backoff in `evals/run.py` that inspects `outcome.remaining_rate_limit_tokens` and applies proportional cooldowns between scenarios.
- **Prevention:** Evaluation runner defaults to or provides `--pace` flag; documented in `evals/results/latest.md` and `README.md`.
- **Time lost:** ~5 minutes.




## Post-launch (live UI testing)

### Bug: "tomorrow" / "day after tomorrow" leaked as raw text, and a latent hardcoded-to-today bug
- **Symptom:** Typing "tomorrow" as `effective_date` in the live UI produced a `G8_ambiguity` flag with
  the literal word "tomorrow" shown as the document value — the same class of un-resolved-placeholder
  leak the planted "today's date" issue exists to catch, just for a phrase the original fix didn't
  anticipate. Found by hand-testing the deployed app, not by a written test.
- **Hypothesis:** `tools/parser.py::parse_date` only recognized "today"-style phrasing; anything else
  fell through to `None`, and the live Normalizer's system prompt only exemplified "today" as
  `derived`, so the model called "tomorrow" `ambiguous` instead.
- **Evidence:** `curl /api/run` with `effective_date: "tomorrow"` returned
  `{"status": "NEEDS_REVIEW", "gate": "G8_ambiguity", "value_for_document": "tomorrow"}`.
- **Deeper bug found while fixing it:** `core/orchestrator.py::_canonicalize_parsed_fields` didn't call
  the parser at all for `DERIVED` effective_date — it hardcoded `format_long_date(now.date())`
  unconditionally. Extending the parser and prompt alone would have made the live model start
  classifying "tomorrow" as `derived`, and this hardcoded line would have then silently resolved it
  to **today's** date instead of tomorrow's — a wrong date shipped confidently, worse than the
  original ambiguity flag it replaced. Caught by reasoning through the fix's blast radius before
  shipping it, not by a failing test (no test exercised a non-"today" DERIVED value at the time).
- **Fix:** Extended `parse_date` with `timedelta`-based offsets for "tomorrow" (+1) and "day after
  tomorrow" (+2), checked in that order since the latter contains the former as a substring. Updated
  `agents/normalizer.py`'s system prompt to classify both as `derived`. Changed
  `_canonicalize_parsed_fields` to re-parse `inputs.effective_date` with the same parser instead of
  assuming a zero offset, falling back to today only when the parser can't resolve the text at all.
- **Prevention:** `tests/test_parser.py` (pattern-order test for the tomorrow/day-after-tomorrow
  substring collision), `tests/test_orchestrator.py::TestCanonicalizeParsedFields` (explicit
  regression: a DERIVED "tomorrow" must resolve to tomorrow's date, not today's) and
  `TestRelativeEffectiveDateEndToEnd` (full pipeline, both phrases). Verified live against the real
  Groq deployment for all three phrases before and after. Logged as D-73.
- **Time lost:** ~20 minutes.
