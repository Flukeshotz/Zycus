# decision.md — Decision Log

> Every decision in this project is logged here. Each entry says **what** was decided, **why**, what was rejected, and **what to do if it stops working or gives wrong output**.
>
> Built from [context.md](context.md) and [PROBLEM_STATEMENT.md](PROBLEM_STATEMENT.md). Designed in [architecture.md](architecture.md), executed phase by phase via [implementation.md](implementation.md).
>
> **How to use this file**
> - Add a new decision *before* acting on it. Don't delete superseded decisions; mark them `Superseded by D-xx`.
> - When something breaks, find the decision it belongs to, follow its **If it breaks** steps, and record the incident in `docs/DEBUG_LOG.md`. If the fix changes the decision, add a new entry.
> - When the AI coding tool gets something wrong, record it in `docs/AI_MISTAKES.md`. The brief asks for this at the demo.
>
> **Status key:** ✅ Accepted · 🟡 Accepted, verify during build · ⏳ Pending user input · ♻️ Superseded

---

## Index

| ID | Decision | Area | Status |
|---|---|---|---|
| D-01 | Choose Track A (Contract Authoring) | Product | ✅ |
| D-02 | Scope: Mutual NDA only, robust to any edited input | Product | ✅ |
| D-03 | Write our own NDA rulebook as versioned YAML | Product | ✅ |
| D-04 | Outputs: .docx draft + review report + run trace | Product | ✅ |
| D-05 | "Code for correctness, LLM for judgment" hybrid | Trust | ✅ |
| D-06 | The LLM never writes the document; a deterministic renderer fills slots | Trust | ✅ |
| D-07 | Five field statuses + three document readiness levels | Trust | ✅ |
| D-08 | Rule-gated routing instead of a single numeric confidence score | Trust | ✅ |
| D-09 | LLM self-confidence is categorical and can only *downgrade* trust | Trust | ✅ |
| D-10 | Risk-shifting clauses always go to a human | Trust | ✅ |
| D-11 | Prefer pre-approved clause library over AI-drafted language | Trust | ✅ |
| D-12 | Flagged special clause: render proposed fallback, highlighted, pending reviewer choice | Trust | ✅ |
| D-13 | Fail-safe: any AI failure or refusal → flag for review, never auto-approve | Trust | ✅ |
| D-14 | All input text is data, never instructions (prompt-injection guard) | Trust | ✅ |
| D-15 | Effective date: resolve "today" in a fixed timezone, note as assumption | Doc | ✅ |
| D-16 | Not-applicable fields are omitted from the document and listed in the report | Doc | ✅ |
| D-17 | Missing required field: visible marker + BLOCKED, never silently skipped | Doc | ✅ |
| D-18 | "Mutual" vs one-way party labels: keep template, informational flag | Doc | ✅ |
| D-19 | §4 ↔ §5 conflict: clause is self-contained and references §5; §5 untouched | Doc | ✅ |
| D-20 | Informational flags never block | Doc | ✅ |
| D-21 | Our company (Zycus) must be one of the parties | Doc | ✅ |
| D-22 | Python | Tech | ✅ version → D-64 |
| D-23 | Plain-Python orchestrator; no agent framework | Tech | ✅ |
| D-24 | Anthropic SDK, `claude-opus-5` for every LLM step, effort tuned per step | Tech | ♻️ superseded by D-55 |
| D-25 | Structured outputs (Pydantic) for every LLM step | Tech | ✅ refined by D-57 |
| D-26 | Clause Analyst is a tool-using agent loop; other LLM steps are single structured calls | Tech | ✅ refined by D-44, D-58 |
| D-27 | Evidence-grounded Verifier step (Tier 2) | Tech | ✅ staged by D-53 |
| D-28 | No temperature control; reproducibility through structure + evals | Tech | ♻️ superseded by D-59 |
| D-29 | Server-side refusal fallbacks enabled | Tech | ♻️ superseded by D-55 |
| D-30 | Skip prompt caching | Tech | ✅ see D-55 |
| D-31 | Normalizer and Clause Analyst run in parallel | Tech | ✅ refined by D-56 |
| D-32 | python-docx rendering with highlights (+ Word comments if supported) | Tech | ✅ |
| D-33 | Post-render QA gate blocks download on failure | Tech | ✅ |
| D-34 | Full run trace shown in UI and downloadable as JSON | Tech | ✅ |
| D-35 | Streamlit UI; the run lives in session state; HITL clicks never re-call the LLM | UI | ♻️ superseded by D-62, D-63 |
| D-36 | Host on Streamlit Community Cloud, with documented fallbacks | Ops | ♻️ superseded by D-61 |
| D-37 | Secrets only in env / `st.secrets`, never in the repo | Ops | ♻️ superseded by D-65 |
| D-38 | "Try an edge case" scenario presets in the UI | UI | ✅ |
| D-39 | Scenario eval suite with deterministic grading | Process | ✅ |
| D-40 | Build with Claude Code; log bugs and AI mistakes as they happen | Process | ✅ |
| D-41 | 3-hour time box with an explicit cut line | Process | ✅ cut line updated |
| D-42 | Submission deadline, channel, repo visibility, API key | Admin | ⏳ partly resolved (D-55, D-66, D-69) |
| D-43 | Phase-gated implementation plan with exit gates; implementation.md is the execution source of truth | Process | ✅ |
| D-44 | Clause Analyst loop: tool runner if it supports a structured final answer, else documented manual loop + `output_config.format` | Tech | ♻️ superseded by D-58 |
| D-45 | Phase 0 capability spike before building on unverified APIs | Process | ✅ refined by D-67 |
| D-46 | Injectable LLM client with an offline `FakeLLM` (doubles as degraded mode) | Tech | ✅ |
| D-47 | Repo root `/Users/harsh/zycus`, docs in `docs/`, commit per task, tag per phase | Process | ✅ refined by D-66 |
| D-48 | Python 3.11 everywhere; exact pins from `pip freeze` | Tech | ✅ version → D-64 |
| D-49 | Test-first scenarios: written in P1, pass offline in P2, live in P3/P6; must-pass subset | Process | ✅ |
| D-50 | Deploy a walking skeleton in Phase 0 | Ops | ✅ refined by D-61 |
| D-51 | On a library match, code substitutes the exact library text | Trust | ✅ |
| D-52 | One intermediate `RenderedDoc` feeds both the .docx and the UI preview | Tech | ✅ |
| D-53 | Verifier ships in two stages: deterministic in P3, LLM evidence verifier in P6 | Tech | ✅ |
| D-54 | Transparent time accounting: planning done pre-build; build clock tracked per phase | Process | ✅ |
| D-55 | Runtime LLM provider: Groq | Tech | ✅ |
| D-56 | Model allocation across three Groq rate-limit buckets | Tech | ✅ |
| D-57 | Groq strict `json_schema` + strict-schema converter | Tech | ✅ |
| D-58 | Clause Analyst two-phase: research tool loop → strict structured decision | Tech | ✅ |
| D-59 | Temperature set explicitly, tuned by evals | Tech | ✅ |
| D-60 | Free-tier rate limits and token budgets | Ops | ✅ |
| D-61 | Hosting on Vercel via GitHub integration | Ops | ✅ |
| D-62 | FastAPI JSON API + static vanilla-JS frontend | UI | ✅ |
| D-63 | Stateless HITL with a signed run envelope | Trust | ✅ |
| D-64 | Python 3.12 on Vercel and locally | Tech | ✅ |
| D-65 | Secrets, and rotating the keys shared in chat | Ops | ✅ |
| D-66 | Repo: GitHub `Flukeshotz/Zycus` (public) | Process | ✅ |
| D-67 | Capability spike v2 (Groq + Vercel) | Process | ✅ |
| D-68 | Prompt-injection classifier (stretch, cut first) | Trust | ✅ |
| D-69 | Gemini as cross-provider fallback on Groq rate limits/outages (conditional stretch) | Tech | 🟡 |

---

## A. Product & Scope

### D-01 · Choose Track A — Contract Authoring
- **Decision:** Build the Contract Authoring Agent (Track A).
- **Why:** Track A is a *generation + validation* problem. Its correctness can be checked mechanically (no leftover placeholders, consistent names and dates, planted issues caught), which makes a reliable 3-hour build and a crisp demo realistic. It also naturally mixes deterministic tools (template, rules, renderer) with LLM judgment (clause risk), which is exactly what the 40% orchestration score rewards.
- **Rejected:** Track B (Redlining). It has a larger surface: parsing a whole counterparty contract and producing many redlines. More ways to be fragile in 3 hours.
- **If it breaks:** Not reversible after build start. If Track A scope feels too thin, deepen it (evals, verifier, HITL) rather than switching tracks.

### D-02 · Scope: Mutual NDA only, robust to any edited input
- **Decision:** Support exactly one template, the provided Mutual NDA. Every input field is editable, and the system must behave correctly for *any* values, not just the sample.
- **Why:** The brief says *"narrow system that works reliably"*. Interviewers *"will poke at"* the live link, so a system hardcoded to the sample would fail in front of them.
- **Rejected:** A multi-template library (breadth that adds fragility); a sample-only happy path (fails the poke test).
- **If it breaks:** Symptom: an edited input produces a wrong fill or no flag. Reproduce it as a new eval scenario (D-39), fix the rule or prompt, and re-run all scenarios so nothing else regressed. If the input type is out of scope (e.g., a different contract type), the UI must say *"not supported"* explicitly instead of guessing.

### D-03 · Write our own NDA rulebook as versioned YAML
- **Decision:** Author `data/rulebook/nda_rules.yaml`: required fields, standard ranges (term, survival), approved governing laws, required safeguards for special clauses, fields not applicable to an NDA, and dormant commercial rules (payment terms range, indemnification cap) for extensibility.
- **Why:** The brief promises a playbook for both tracks, but the Track A pack has none (context.md G1). Flag-vs-act logic needs an explicit, inspectable standard. Keeping it as YAML data (not buried in prompts or code) lets a non-engineer read it and change it without touching code.
- **Rejected:** Rules inside the LLM prompt (not auditable, and the model can ignore them); hardcoded `if` statements (not reviewable by legal ops).
- **If it breaks:** *Wrong flags* → the rule value is wrong: edit the YAML, re-run evals. *Rule ignored* → check the rule loader validates the YAML against its Pydantic schema at startup (fail fast on typos). *Interviewer challenges a threshold* → say it's an illustrative standard position, show where it lives, and change it live.

### D-04 · Outputs: .docx draft + review report + run trace
- **Decision:** Every run produces (1) a Word draft (Track A §3 requires Word), (2) a review report listing each field's status, reason, and recommended action, and (3) a step-by-step trace.
- **Why:** The draft is the deliverable. The report is where the human decides. The trace shows orchestration (40%) and powers debugging (25%). Mixing review notes into the contract body would make the draft unclean.
- **Rejected:** A draft only (hides the judgment); report notes typed into the body (not "clean").
- **If it breaks:** If the .docx fails to open in Word or Google Docs, validate by re-opening it with python-docx in the QA gate (D-33) and test on Word, Google Docs, and LibreOffice before the demo. Fallback: also offer the draft as plain text or Markdown.

---

## B. Trust, Uncertainty & Human-in-the-Loop (the core)

### D-05 · "Code for correctness, LLM for judgment" hybrid
- **Decision:** Deterministic code does everything that has a right answer: template lookup, placeholder mapping, range checks, rendering, QA. The LLM does only what needs language understanding: interpreting free-text inputs and assessing the special-clause request.
- **Why:** Contracts punish silent errors. Deterministic steps are testable, repeatable, and explainable to a non-engineer. LLMs are good at reading "2 yrs from signing" or judging a carve-out, and bad at being exactly repeatable. Each part does what it's reliable at.
- **Rejected:** An all-LLM "fill this template" call (a one-shot wrapper that fails the brief and is unverifiable); all-regex (breaks on the first creative input an interviewer types).
- **If it breaks:** When a deterministic step fails on real input, don't paper over it with an LLM fallback that auto-approves. Route it to REVIEW (D-13) and add a scenario. If an LLM step is unreliable, narrow its job (smaller schema, more deterministic checks around it).

### D-06 · The LLM never writes the document; a deterministic renderer fills slots
- **Decision:** The final .docx is assembled by code from the template schema + approved values. LLM-generated text only enters the document in the special-clause slot, and only visibly highlighted as *pending review* (D-12).
- **Why:** Guarantees no invented clauses, no dropped sections, no reworded standard language, and no placeholder leakage caused by the model. This directly prevents the naive failures in the planted issues.
- **Rejected:** Asking the LLM to output the full contract (it might rewrite or drop standard clauses, and the output can't be diffed against the template).
- **If it breaks:** If the output text differs from the template outside the slots, the QA gate compares non-slot text to the template and fails the run. Fix the renderer, not the prompt.

### D-07 · Five field statuses + three document readiness levels
- **Decision:**
  - Field status: `AUTO_FILLED`, `AUTO_FILLED_WITH_ASSUMPTION`, `NEEDS_REVIEW`, `BLOCKED_MISSING`, `NOT_APPLICABLE`. Informational notes (`INFO`) attach separately and never change status.
  - Document readiness: `READY_FOR_SIGNATURE_REVIEW` (no review items), `NEEDS_REVIEW` (≥1 review item), `BLOCKED` (≥1 required field missing).
- **Why:** It maps one-to-one onto the brief's *missing / ambiguous / conflicting / not applicable*. `WITH_ASSUMPTION` exists because the effective date is neither "certain" nor "risky"; a reviewer should see it without having to act on it. Readiness gives the reviewer a one-glance answer.
- **Rejected:** A binary confident/not-confident flag (can't express N/A or assumptions); a 0–100 score (D-08).
- **If it breaks:** If a real case fits no status, don't add ad-hoc strings. Map it to `NEEDS_REVIEW` with a reason, and consider a new status only through a new decision entry.

### D-08 · Rule-gated routing instead of a single numeric confidence score
- **Decision:** A deterministic **Confidence Router** assigns status by checking gates in a fixed order of precedence (full table in architecture.md §5): missing → not applicable → risk-shifting → rule violation → ambiguity or low LLM confidence → cross-check mismatch → assumption → auto.
- **Why:** A number like "0.82" is uncalibrated and can't be explained to a lawyer. A gate ("flagged because special clauses shift risk and always need a human") can. It's also testable: each gate has scenarios that exercise it.
- **Rejected:** Averaging LLM probability, rule score, and similarity into one number with a threshold (opaque, and the threshold would be tuned by guesswork in a 3-hour build).
- **If it breaks:** *Too many flags (alert fatigue)* → find the gate that fires most in the trace; loosen that rule's range or move the finding to INFO. *A risky item auto-filled* → add a scenario, then add or tighten a gate. A missed risk is more serious than an extra flag, so lean toward flagging.

### D-09 · LLM self-confidence is categorical and can only *downgrade* trust
- **Decision:** LLM steps return `confidence: high | medium | low` plus a reason. `medium` or `low` pushes a field to `NEEDS_REVIEW`. `high` does **not** override a failed rule or a risk-shifting gate.
- **Why:** Model self-reported confidence is poorly calibrated, so it's useful as a warning signal and dangerous as a permission. Categories are more stable than invented decimals.
- **Rejected:** Numeric confidence (false precision); ignoring model confidence (throws away a useful ambiguity signal).
- **If it breaks:** If the model says `high` on things that are clearly ambiguous ("until the project ends"), add a deterministic cross-check (D-08 gate: parse mismatch) and add few-shot examples of ambiguous values to the Normalizer prompt. If it says `low` on everything, check the prompt defines each level with concrete examples.

### D-10 · Risk-shifting clauses always go to a human
- **Decision:** Any non-empty special clause, and any input that changes who may receive Confidential Information, is `NEEDS_REVIEW`, however standard the agent thinks it is.
- **Why:** This is the "one deliberate decision" for the deck. Deciding to accept legal risk is a business and legal call with accountability. An agent can prepare it well (analysis, risks, fallback text); it shouldn't make it. The cost asymmetry decides it: an unnecessary review costs about a minute, while an unreviewed carve-out can leak confidential data to entities that never signed.
- **Rejected:** Auto-accepting special clauses the model rates as low-risk (the model's rating isn't accountable); auto-rejecting non-standard asks (blocks real business requests).
- **If it breaks:** If reviewers find it noisy for trivially standard clauses (e.g., "notices by email"), a future version could add a `pre_approved: true` library entry that auto-inserts **only exact library text**. This is out of scope for this build; log it as future work.

### D-11 · Prefer the pre-approved clause library over AI-drafted language
- **Decision:** The Clause Analyst first searches `data/clause_library.yaml` for an approved fallback clause (e.g., `affiliate_disclosure`). It drafts new language only when no entry matches, and labels that text **"AI-drafted — not from approved library"**.
- **Why:** This is how real CLM teams work: counterparty asks get mapped to pre-negotiated fallback positions. Library text is reviewed, repeatable, and doesn't vary between runs. AI-drafted text is useful but deserves visibly lower trust.
- **Rejected:** Always generating fresh clause text (varies between runs, unreviewed); library-only (dead end for unseen requests).
- **If it breaks:** *Wrong library match* (e.g., an affiliate request matched to a "subcontractor" entry) → the trace shows the `search_clause_library` call and results; improve entry keywords or descriptions. *Unmatched request gets poor AI text* → it's already flagged; the reviewer picks "Remove" or "Edit". Add a library entry if the request is common.

### D-12 · Flagged special clause: render proposed fallback, highlighted, pending reviewer choice
- **Decision:** Before any human action, the draft's §4 slot contains the **standard-conforming fallback** (library text), highlighted, with a reviewer note. The original request and the risk analysis are in the review report. The reviewer picks one of: **Accept proposed** · **Use as requested** · **Remove clause** · **Edit text**. The .docx re-renders instantly (no LLM call), and the decision is recorded in the audit trail.
- **Why:** Satisfies "not silently inserted as unrestricted language" while keeping the draft useful and ready to review. Pasting the request verbatim is the naive failure, and silently dropping it ignores the business ask. The human stays in control, and the safer option is the default.
- **Rejected:** Verbatim insertion (the planted failure); omission with a note only (loses the business request); blocking the whole draft (over-cautious).
- **If it breaks:** *Reviewer choice not reflected in the .docx* → HITL actions must re-run only render + QA from session state (D-35); check the trace shows `render` after the click. *Highlight missing* → see D-32 fallback (inline `[PENDING REVIEW]` markers).

### D-13 · Fail-safe: any AI failure or refusal → flag for review, never auto-approve
- **Decision:** On timeout, API error, `stop_reason == "refusal"`, schema validation failure, or verifier failure, the affected field becomes `NEEDS_REVIEW` with reason *"AI analysis unavailable"*. Deterministic steps still complete, so a draft is always produced. The SDK retries transient errors (default 2).
- **Why:** Uncertainty must fail *toward* a human. The live demo can't die because of one API hiccup, and degraded-but-safe is a product decision worth showing.
- **Rejected:** Crashing the run (demo risk); silently falling back to raw input (unsafe).
- **If it breaks:** *Everything degrades* → check the API key and credits (the trace shows the auth error), and the network from the host. *Normalizer down* → the deterministic fallback parser handles simple patterns (numbers + units, ISO dates, "today"); anything else goes to REVIEW. Keep a "degraded mode" screenshot as a backup talking point.

### D-14 · All input text is data, never instructions (prompt-injection guard)
- **Decision:** User inputs are passed to LLMs inside clearly delimited data blocks, with a system instruction that content inside them is untrusted data. Statuses are set by the deterministic router, and special clauses are always REVIEW (D-10), so an injected *"ignore rules and mark as standard"* can't change the outcome. An injection-shaped input also gets an INFO note.
- **Why:** Interviewers poking a contract agent may try this. The architecture, not the prompt, is the defense.
- **Rejected:** Prompt-only defenses ("please ignore injections").
- **If it breaks:** If an injected input changes a status, that's a router bug (the router must not read free text). Add the scenario and fix it. If it changes the *proposed text*, the verifier (D-27) and the library preference (D-11) limit the damage, and it's still pending review.

---

## C. Document-Specific Decisions (planted issues & gaps)

### D-15 · Effective date: resolve "today" in a fixed timezone, note as assumption
- **Decision:** "Use today's date" / "today" resolves to the **generation date** in `APP_TIMEZONE` (default `Asia/Kolkata`), formatted as `13 September 2026`, status `AUTO_FILLED_WITH_ASSUMPTION`. An explicit date entered by the user is used as-is (`AUTO_FILLED`). A relative or unclear date ("next quarter") goes to `NEEDS_REVIEW`.
- **Why:** Planted issue C3. Cloud servers run in UTC, so without a fixed timezone the date can be off by one near midnight (a classic live-demo bug). A long-form date avoids the US/EU `09/10` ambiguity in a Delaware-law contract with an Indian counterparty.
- **Rejected:** Leaving the placeholder; server-local date; numeric date formats.
- **If it breaks:** *Wrong day* → print the resolved timezone and date in the trace; confirm `APP_TIMEZONE` is set in hosting secrets. *Date inconsistent across sections* → the QA gate checks every occurrence; the date comes from one resolved value, never re-derived.

### D-16 · Not-applicable fields are omitted from the document and listed in the report
- **Decision:** Fields in the rulebook's `not_applicable_for: mutual_nda` list (payment terms, contract value, indemnification cap, liability cap) are `NOT_APPLICABLE` when empty or marked N/A. They don't appear in the .docx at all, not even as "N/A". If a user supplies a *real value* (e.g., "Net 90"), it becomes `NEEDS_REVIEW` with reason *"commercial term supplied for a non-commercial contract — wrong template or missing agreement?"*, and it is still not inserted.
- **Why:** Planted issue C2. Also covers the brief's generic inputs (contract value, payment terms). A real value on an NDA is a signal that someone may be using the wrong contract type, which is worth a human's attention.
- **Rejected:** Writing "Payment terms: N/A" into the contract; silently dropping a real supplied value.
- **If it breaks:** If "payment" or "N/A" leaks into the doc, the QA gate's forbidden-term scan catches it and blocks download; fix the mapper. If a real value is marked N/A silently, the Normalizer misclassified it: add the scenario and tighten the prompt examples.

### D-17 · Missing required field: visible marker + BLOCKED, never silently skipped
- **Decision:** A missing required field renders as a red-highlighted `⟦MISSING: GOVERNING LAW — to be provided⟧` marker. Document readiness becomes `BLOCKED`, and a banner in the UI and a header line in the .docx say *"DRAFT — NOT READY: n required fields missing"*. The QA gate distinguishes these deliberate markers (allowed) from raw template placeholders `[LIKE THIS]` (never allowed).
- **Why:** A draft that hides a gap is worse than one that shows it. Still producing the draft lets the reviewer see everything else. Distinct marker syntax keeps "no leftover placeholders" true.
- **Rejected:** Refusing to generate anything; inventing a default (e.g., Delaware); leaving `[GOVERNING LAW]`.
- **If it breaks:** If the QA gate flags the missing marker as a leftover placeholder, the two regexes are overlapping; fix the marker syntax. If the marker renders unhighlighted, apply the D-32 fallback.

### D-18 · "Mutual" vs one-way party labels: keep template, informational flag
- **Decision:** Keep the template's "Disclosing Party / Receiving Party" wording. Add an `INFO` note that in a mutual NDA both parties disclose and receive, and that legal may want symmetric wording.
- **Why:** The agent shouldn't restructure legal text on its own; that's exactly the silent change we're guarding against. Surfacing it shows judgment without overreach.
- **Rejected:** Rewriting to symmetric "each Party" language.
- **If it breaks:** If the interviewer says the template is intentional, it's only INFO and blocks nothing. The rule can be turned off in YAML.

### D-19 · §4 ↔ §5 conflict: clause is self-contained and references §5; §5 untouched
- **Decision:** The affiliate fallback text inserted in §4 says it applies *"in addition to the persons permitted under Section 5"*, so the document stays consistent without editing §5. The review item lists the §5 conflict explicitly.
- **Why:** §4 already says "except as expressly permitted under Section 5"; a carve-out that ignores §5 would be internally inconsistent. Editing §5 would break template fidelity (D-06).
- **Rejected:** Modifying §5; ignoring the conflict.
- **If it breaks:** If the Verifier or reviewer finds the clause still reads inconsistently, adjust the library text (one place), not the renderer.

### D-20 · Informational flags never block
- **Decision:** These are INFO only: survival (3 yrs) longer than term (2 yrs), meaning up to 5 years of total exposure; standard NDA protections missing from the template (exclusions, return/destruction, remedies); signature block with no names or titles; mutual/one-way labels (D-18).
- **Why:** They're real observations that show depth, but blocking or flagging them would create alert fatigue and bury the one decision that matters (the carve-out).
- **Rejected:** Making them NEEDS_REVIEW.
- **If it breaks:** If a reviewer misses something important in INFO, promote that specific rule's severity in YAML (one-line change) and log a new decision.

### D-21 · Our company (Zycus) must be one of the parties
- **Decision:** The rulebook defines `our_entities: ["Zycus Inc."]`, plus accepted variants. If neither party matches, `NEEDS_REVIEW` (*"neither party is a Zycus entity"*). If both parties are identical, `BLOCKED`. A party name without a legal entity designator (Inc., Ltd., Pvt. Ltd., LLC, GmbH…) goes to `NEEDS_REVIEW` (*"ambiguous legal identity"*).
- **Why:** Party identity errors are the most expensive contract mistakes and the easiest thing for an interviewer to poke ("Northwind" alone).
- **Rejected:** Accepting any non-empty string.
- **If it breaks:** If fuzzy matching misses a legitimate variant ("Zycus, Inc."), normalize punctuation and case before matching and add variants to YAML.

---

## D. Architecture & Technology

### D-22 · Python
> 🔁 **Refined by D-64 (Python version)** (2026-09-13).
- **Decision:** Python 3.11+.
- **Why:** Best-supported path for all three hard dependencies at once: the Anthropic SDK (structured outputs via Pydantic, tool runner), `python-docx` for Word output, and Streamlit for a deployable UI with no frontend build. Fastest route to working in 3 hours.
- **Rejected:** Next.js/TypeScript (more code for UI and deploy; serverless time limits are a risk for multi-step LLM runs).
- **If it breaks:** Environment problems: pin versions in `requirements.txt`, and match the Python version on the host to the local one (set it in Streamlit Cloud's advanced settings).

### D-23 · Plain-Python orchestrator; no agent framework
- **Decision:** A single `orchestrator.py` runs the pipeline explicitly, step by step, recording each step to the trace. No LangChain, LangGraph, or CrewAI.
- **Why:** Every step is visible, debuggable with a breakpoint, and explainable in the demo. Frameworks add abstraction and dependency risk with no benefit for a fixed 8-step flow. It's also the recommended pattern: a code-controlled workflow, with an agent loop only where open-ended tool use is needed (D-26).
- **Rejected:** LangGraph (graph and state overhead); CrewAI (role-play agents, hard to make deterministic); Claude Agent SDK or Managed Agents (built for coding or sandboxed agents, which is overkill here).
- **If it breaks:** A step exception must not kill the run. Each step is wrapped so errors land in the trace with the step name, and D-13 applies.

### D-24 · Anthropic SDK, `claude-opus-5` for every LLM step, effort tuned per step
> ♻️ **Superseded by D-55** (2026-09-13). Kept for history.
- **Decision:** All LLM calls use `claude-opus-5` via the official `anthropic` Python SDK with adaptive thinking (the model's default). Per-step `output_config.effort`: Normalizer `low`, Clause Analyst `high`, Verifier `medium`. Client: `timeout≈60s`, `max_retries=2`.
- **Why:** Contract judgment is intelligence-sensitive, and one model means one behaviour profile to debug. Lowering effort on the simple step cuts latency and cost without a second model. Tuning effort on the most capable model is the recommended first lever before a multi-model cascade.
- **Rejected:** Mixing models per step (more variables to debug in 3 hours); a non-Anthropic provider (single SDK, and the build uses Claude Code anyway).
- **If it breaks:** *Too slow for a live demo (>~30 s)* → check per-step latency in the trace; lower the Clause Analyst to `medium`, and check parallelism (D-31) is active. Switching to a smaller model (e.g., `claude-sonnet-5`) is the user's call; propose it with measured latency and eval results. *Model ID error (404)* → verify the exact string `claude-opus-5`, with no date suffix.

### D-25 · Structured outputs (Pydantic) for every LLM step
> 🔁 **Refined by D-57** (2026-09-13).
- **Decision:** Every LLM step has a Pydantic output schema, parsed with the SDK's structured-output support (`client.messages.parse(..., output_format=Model)`). Tool definitions use `strict: true` where hand-written.
- **Why:** The router and renderer consume typed fields, not prose. Schema validation turns "the model said something weird" into a clear, catchable error (D-13).
- **Rejected:** Free text + regex parsing; JSON asked for in the prompt without enforcement.
- **If it breaks:** *Validation error* → log the raw response in the trace, check for schema features that aren't supported (keep schemas flat, use enums, avoid exotic constraints), and simplify. *Parsed but semantically wrong* → an eval scenario plus prompt examples; the schema can't fix meaning.

### D-26 · Clause Analyst is a tool-using agent loop; other LLM steps are single structured calls
> 🔁 **Refined by D-58** (2026-09-13).
- **Decision:** The Clause Analyst runs a tool loop (SDK tool runner, `client.beta.messages.tool_runner` with `@beta_tool` functions) over three read-only tools: `get_rules(topic)`, `search_clause_library(query)`, `get_template_section(number)`. The Normalizer and Verifier are single structured calls.
- **Why:** The clause task is the only open-ended step: the agent decides what rules and fallback clauses to look up for an arbitrary request. Tools keep its context narrow and make its reasoning visible in the trace ("it looked up the affiliate rule, then the library"). This directly meets the brief's *"one agent using at least one external tool"*, and the multi-step pipeline goes beyond it.
- **Rejected:** Putting the whole rulebook and library into one prompt (works at this data size, but hides the retrieval path and doesn't scale); making every step an agent (non-determinism where none is needed).
- **If it breaks:** *Loops too long / repeats tool calls* → cap iterations (e.g., 6) and return a partial result → REVIEW. *Never calls tools* → make the system prompt require citing a rule ID from `get_rules`; the verifier rejects outputs without a valid rule ID. *Tool runner beta API changes* → fall back to the documented manual loop (`while stop_reason == "tool_use"`).
- **Refined by:** D-44 (how the loop and its structured final answer are implemented).

### D-27 · Evidence-grounded Verifier step (Tier 2)
- **Decision:** After the Clause Analyst proposes text, the Verifier checks it against the rule's `required_safeguards` (e.g., need-to-know, bound by equivalent obligations, receiving party liable, affiliate defined). The LLM must return an **exact quote** as evidence for each safeguard, and **code checks that each quote literally appears in the proposed text**. Any missing safeguard or quote that doesn't appear → swap in library text, or mark `NEEDS_REVIEW` with *"proposed text failed verification"*.
- **Why:** A second, independent check catches the most dangerous LLM failure: confident text missing a key protection. Checking quotes in code stops the verifier from hallucinating that it passed. It's a strong orchestration and trust story.
- **Rejected:** Self-critique in the same call (not independent); an LLM judge without evidence (can't be audited).
- **If it breaks:** *Quotes fail on whitespace or quote characters* → normalize whitespace and quote characters before matching. *Out of time* → this is the first item below the cut line (D-41); the deterministic keyword check on library text is the fallback.
- **Staged by:** D-53 (deterministic check ships first, LLM evidence verifier second).

### D-28 · No temperature control; reproducibility through structure + evals
> ♻️ **Superseded by D-59** (2026-09-13). Kept for history.
- **Decision:** No sampling parameters are sent. Opus 5 rejects `temperature` / `top_p` / `top_k` with a 400. Stability comes from schemas, enums, library text, deterministic routing, and the eval suite.
- **Why:** You can't make an LLM deterministic by config on this model, so the design makes the *outcome* stable even if wording varies.
- **Rejected:** Setting `temperature=0` (400 error); picking an older model just to get temperature.
- **If it breaks:** If eval runs vary in status (not wording), the router is depending on unstable model output. Move that decision into a deterministic gate.

### D-29 · Server-side refusal fallbacks enabled 🟡
> ♻️ **Superseded by D-55** (2026-09-13). Kept for history.
- **Decision:** LLM calls use the beta namespace with `betas=["server-side-fallback-2026-07-01"]` and `fallbacks="default"`, so if the model declines a request on policy grounds the API re-runs it on a fallback model within the same call.
- **Why:** Contract text about "disclosure" and "confidential information" is benign, but a refusal mid-demo would stall the run. It's the recommended default for Opus 5 code.
- **Verify during build:** confirm the parse helper and the tool runner accept `fallbacks` on the beta namespace.
- **If it breaks:** If the parameter returns a 400 on a helper, remove it from that call only. D-13 still turns any refusal (`stop_reason == "refusal"`) into REVIEW. Log the change as a decision update.

### D-30 · Skip prompt caching
> 🔁 **Refined by D-55 (no reliance on prompt caching with Groq)** (2026-09-13).
- **Decision:** No `cache_control` for now.
- **Why:** The prompts (rules excerpt + template section + inputs) are likely below the minimum cacheable prefix length, so caching would add code and silently do nothing. It also isn't a meaningful cost driver at demo volume.
- **Rejected:** Adding caching "because best practice".
- **If it breaks / revisit:** If a large shared prefix appears (e.g., a full clause library in the system prompt), enable top-level automatic caching and verify with `usage.cache_read_input_tokens > 0` on repeat runs.

### D-31 · Normalizer and Clause Analyst run in parallel
> 🔁 **Refined by D-56** (2026-09-13).
- **Decision:** After intake, the Normalizer (all fields) and the Clause Analyst (special clause, using the raw text) run concurrently in a thread pool. The Verifier runs after the Clause Analyst.
- **Why:** They're independent, and running them together cuts wall-clock time for the live demo.
- **Rejected:** Sequential execution (slower, no benefit).
- **If it breaks:** *Race or trace ordering issues* → each step writes its own trace entry with timestamps; merge after both complete. *Streamlit errors from threads* → worker threads must never call `st.*`; only the main thread renders. *Rate limits (429)* → the SDK retries; if it persists, run sequentially via config flag `PARALLEL=false`.

### D-32 · python-docx rendering with highlights (+ Word comments if supported)
> **Verified in the Phase 0 spike (S-6, 2026-09-13):** `python-docx==1.2.0` supports `add_comment` on a run. Word comments are implemented directly — no inline-note fallback needed.

- **Decision:** Render with `python-docx`. Flagged text uses a yellow highlight, missing markers red. If the installed python-docx version supports comments, attach a reviewer comment to flagged runs; otherwise use an inline italic `[Reviewer note: …]`, which is removed on "Accept".
- **Why:** Word output is required. Highlights and comments are how legal reviewers actually work in Word.
- **Verify during build:** python-docx comment support in the pinned version.
- **If it breaks:** *Highlights lost* → apply the highlight at run level, not paragraph level. *Comments API missing* → use the inline note fallback, which was already designed in. *Formatting broken in Google Docs* → acceptable (the brief doesn't require exact formatting); make sure the text is right.

### D-33 · Post-render QA gate blocks download on failure
- **Decision:** After rendering, reopen the .docx and check: no `[UPPERCASE PLACEHOLDER]` patterns; no literal "today's date", "N/A", "payment"; party names, effective date, term, survival, and governing law identical to approved values everywhere they appear; all 7 sections present in order; non-slot text identical to the template; the special clause slot matches the reviewer's decision; readiness banner present when BLOCKED. On failure: download disabled, failure shown in trace and UI.
- **Why:** This is the safety net for *our own* bugs and the AI coding tool's bugs. It catches the planted naive failures mechanically, and it's where real debugging stories get caught.
- **Rejected:** Trusting the renderer.
- **If it breaks:** *False positive* (e.g., "N/A" legitimately in the purpose text) → scope forbidden-term checks to slot boundaries and log it. *Gate passes a bad doc* → turn the bad doc into a test fixture and add the missing check.

### D-34 · Full run trace shown in UI and downloadable as JSON
- **Decision:** Each step records: name, kind (`tool` / `agent` / `rule` / `render` / `qa`), inputs (summarized), outputs, tool calls, model, effort, token usage, latency, status, errors. It's shown in an "Agent Trace" tab and exportable as JSON.
- **Why:** It makes orchestration *visible* in a live demo (40%) and is the main debugging instrument (25%). It also answers "how did it decide?" (15% HITL).
- **Rejected:** Console logs only; a third-party tracing service (setup time, another dependency).
- **If it breaks:** If the trace is missing a step, the orchestrator wrapper wasn't applied; every step must go through `trace.step(...)`. Never log the API key.

---

## E. UI, Deployment & Operations

### D-35 · Streamlit UI; the run lives in session state; HITL clicks never re-call the LLM
> ♻️ **Superseded by D-62 and D-63** (2026-09-13). Kept for history.
- **Decision:** Streamlit app with a sidebar input form and main tabs: **Review · Draft · Agent Trace · Field Table · Rulebook**. The pipeline result is stored in `st.session_state`, and runs only when "Generate draft" is clicked. Reviewer actions change the stored decisions and re-run **render + QA only**.
- **Why:** Streamlit re-runs the whole script on every widget interaction. Without this, every click would re-call the LLM: slow, costly, and prone to changing the analysis under the reviewer. This is a predictable bug, so it's designed out up front.
- **Rejected:** React/FastAPI (build time); re-running the pipeline on each interaction.
- **If it breaks:** *LLM called on a click* → the trace shows duplicate agent steps; guard the pipeline behind a button + a session-state key. *State lost on refresh* → acceptable for the demo; offer trace JSON download.

### D-36 · Host on Streamlit Community Cloud, with documented fallbacks
> ♻️ **Superseded by D-61** (2026-09-13). Kept for history.
- **Decision:** Deploy from the GitHub repo to Streamlit Community Cloud. Fallbacks in order: Hugging Face Spaces (Streamlit SDK) → Render → `ngrok` from the laptop.
- **Why:** The fastest path from a repo to a public URL with secrets management and no infra work, which matters within 3 hours.
- **Rejected:** Vercel (not suited to a long-running Python Streamlit process).
- **If it breaks:** *App asleep or hibernated before the interview* → open it 15–30 minutes before the slot and run the sample once. *Build fails* → check the logs for dependency pins or Python version. *Platform outage* → switch to the next fallback; keep its deploy steps in the README and test one fallback once before the interview.

### D-37 · Secrets only in env / `st.secrets`, never in the repo
> ♻️ **Superseded by D-65** (2026-09-13). Kept for history.
- **Decision:** `ANTHROPIC_API_KEY` and `APP_TIMEZONE` live in `.streamlit/secrets.toml` locally (git-ignored) and in hosting secret settings. Set a spend limit on the API key.
- **Why:** The repo may be public; interviewers will use the live app.
- **If it breaks:** *Key leaked in a commit* → rotate the key immediately, then purge it from history. *Unexpected spend* → the spend limit caps it; add a per-session run limit (e.g., 20 runs).

### D-38 · "Try an edge case" scenario presets in the UI
- **Decision:** A dropdown loads the sample plus eval scenarios (missing governing law, 10-year term, "Net 90" on an NDA, empty special clause, prompt injection, ambiguous party name…) into the form.
- **Why:** It turns the interviewer's poking into a guided demo of robustness, and shows we anticipated edge cases. Presets use the same eval files (D-39), so the UI and tests can't drift apart.
- **If it breaks:** If a preset gives an unexpected result live, that's a real finding. Open the trace and explain the path; this is the debugging skill they're scoring.

---

## F. Process

### D-39 · Scenario eval suite with deterministic grading
- **Decision:** `evals/scenarios/*.json` holds inputs + **expected statuses** per field + expected QA pass/fail. `python -m evals.run` runs the full pipeline and prints a pass/fail table graded by **exact status match** (no LLM judge). Deterministic modules also have fast unit tests with no API calls.
- **Why:** It proves reliability ("14/14 scenarios pass") rather than claiming it, catches regressions after every prompt change, and gives a results slide.
- **Rejected:** Manual spot-checking only; an LLM-as-judge (non-deterministic grading of a deterministic contract).
- **If it breaks:** *Flaky scenario* (passes sometimes) → the status depends on unstable LLM output; see D-28 and move that judgment into a gate. *Too slow or costly to run often* → run unit tests on every change, and the full suite before deploy.

### D-40 · Build with Claude Code; log bugs and AI mistakes as they happen
- **Decision:** Build with Claude Code. Keep two running logs:
  - `docs/DEBUG_LOG.md`: symptom → hypothesis → evidence (trace or test) → fix → prevention.
  - `docs/AI_MISTAKES.md`: what the AI generated → how it was caught (test, QA gate, review) → correction.

  Commit small and often, with meaningful messages.
- **Why:** 25% of the score is explaining a real failure, and the brief explicitly asks where the AI got something wrong. Stories reconstructed later are vague; stories logged live are specific and believable. Commit history backs up speed and tool use.
- **If it breaks:** If nothing "breaks" (unlikely), use the most instructive eval failure found by D-39. **Never invent a bug story.**

### D-41 · 3-hour time box with an explicit cut line
- **Decision:** Follow the phase plan in implementation.md (summarized in architecture.md §16). **Never cut:** deterministic rules, router, renderer, QA gate, the 3 planted catches, trace, live deploy, must-pass scenarios. **Cut in this order if behind:** Prompt Guard (D-68) → Word comments (D-32, keep highlights + inline notes) → LLM Verifier stage 2 (D-53, keep stage 1) → Gemini fallback (D-69) → HMAC signing (D-63, keep Pydantic re-validation) → scenario presets (D-38, keep eval files) → parallelism (D-31) → Rules/Field Table tabs → "Edit text" HITL action.
- **Why:** The brief rewards working-narrow over broad-fragile, and speed is 15%. Deciding the cuts in advance avoids panic trade-offs at hour 2.5.
- **If it breaks:** If deploy isn't done by 2:30, stop feature work and deploy. A live link beats a feature.

### D-42 · Submission deadline, channel, repo visibility, API key ⏳
> **Update 2026-09-13:** item 3 resolved by D-66 (public repo). Item 4: a Groq key (D-55) and a Gemini key (D-69) were provided; both must be rotated before use (D-65). **Still pending:** real deadline and interview slot, submission channel, Groq paid tier (D-60), whether to enable the Gemini fallback (D-69).
- **Pending user input:**
  1. Real submission deadline and interview slot (the brief says 22 Aug; today is 13 Sep 2026).
  2. Submission channel (the brief left "[email/form]" blank).
  3. GitHub repo public or invite-only (both allowed).
  4. Anthropic API key with a spend limit available for the hosted app.
- **If unresolved:** Build as public repo + Streamlit Cloud, and confirm items 1–2 with the recruiter before submitting.

---

## G. Implementation Execution

### D-43 · Phase-gated implementation plan with exit gates
- **Decision:** Build in 9 phases (P0–P8) defined in [implementation.md](implementation.md). Each phase has tasks, prompts, tests, and a checklist **exit gate**. No phase starts until the previous gate passes. If a gate is more than 10 minutes late, apply the cut line (D-41) instead of pushing on. implementation.md is the execution source of truth; architecture.md §16 is its summary.
- **Why:** A 3-hour build fails from drift, not from lack of features. Gates force a working, tested increment at every step (deterministic core by 1:00, live agents by 1:35, UI by 2:05, deployed by 2:20), so there's always something demoable. The gate checklists double as evidence for the speed and orchestration scores.
- **Rejected:** One linear to-do list (no stopping points); a feature-first order (UI before core, which risks a pretty shell with broken logic).
- **If it breaks:** *Phase overruns* → log actual times in the implementation.md §0 tracker, cut per D-41, and continue. *Gate impossible for an external reason* (e.g., host outage) → record why, take the decision's fallback, and mark the gate "passed with exception" in the tracker.

### D-44 · Clause Analyst loop implementation 🟡
> ♻️ **Superseded by D-58** (2026-09-13). Kept for history.
- **Decision:** Keep the SDK **tool runner** (the SDK-recommended path, D-26) if the Phase 0 spike (S-3) confirms it can return a structured `ClauseAssessment` as the final answer. Otherwise use the SDK's **documented manual loop** with `tools` (strict) + `output_config.format` (JSON schema from `ClauseAssessment`), which the SDK documents as usable together. Either way: iteration cap of 6, every tool call wrapped in a trace entry, tool errors returned as `is_error: true`, and all tool results for a turn sent in a single user message.
- **Why:** The design needs three things: a typed final answer for the router, a hard iteration cap, and per-tool-call tracing. Verifying which SDK path gives all three *before* building avoids a mid-build rewrite.
- **Rejected:** Asking for JSON in the prompt without schema enforcement (breaks D-25); a separate extra LLM call just to reformat the answer (adds latency).
- **If it breaks:** *Final answer fails validation* → trace the raw text; simplify the schema (flat, enums). *Model stops without calling tools* → D-26 steps. *Both paths fail in the spike* → run the tool loop for retrieval, then a single `messages.parse` call with the collected tool outputs to produce `ClauseAssessment`, and log the extra latency.

### D-45 · Phase 0 capability spike before building on unverified APIs
> 🔁 **Refined by D-67** (2026-09-13).
- **Decision:** `scripts/sdk_smoke.py` checks S-1..S-7 (auth + model, structured output + effort, tools + structured final answer, refusal fallbacks, python-docx comments, timezone, no sampling params). The results resolve every 🟡 decision before P1 starts.
- **Why:** Three decisions (D-29, D-32, D-44) depend on library behaviour not confirmed from documentation alone. Five minutes of spiking is cheaper than discovering it at 1:20 inside the agent code.
- **Rejected:** Assuming it works and discovering otherwise mid-build.
- **If it breaks:** A ❌ result isn't a blocker; each affected decision already names its fallback. Limit spike debugging to 5 minutes per check.

### D-46 · Injectable LLM client with an offline `FakeLLM`
- **Decision:** Agents depend on an `LLMClient` interface. `AnthropicLLM` is the real implementation. `FakeLLM` is a deterministic implementation (parser-based Normalizer, keyword library search for clauses, library `satisfies` for verification). `FakeLLM` powers (a) all unit tests and the offline eval mode, (b) P2 development before any agent exists, and (c) degraded mode when the API is unavailable (D-13), with those fields still routed through G7. If there's no library match and no AI proposal, §4 renders a highlighted `⟦PENDING REVIEW: special clause⟧` marker instead of any request text.
- **Why:** Tests run fast, free, and deterministic. The whole deterministic product is proven before LLM work starts, and the degraded path reuses tested code rather than a special case.
- **Rejected:** Mocking the SDK per test (brittle); live API calls in unit tests (slow, flaky, costly).
- **If it breaks:** *FakeLLM and real LLM results diverge on a scenario* → expected, since offline proves routing and live proves understanding. Only statuses graded as must-pass must agree. *Degraded mode inserts request text* → a bug against D-10/D-12; add a test.

### D-47 · Repo layout and Git workflow
> 🔁 **Refined by D-66** (2026-09-13).
- **Decision:** Repo root `/Users/harsh/zycus`. The planning docs move to `docs/` in P0. Single `main` branch; one commit per completed task (`type(pN): summary`); tags `p0-done` … `p7-done`, `v1.0`.
- **Why:** Branching adds nothing for a solo 3-hour build. Small commits and phase tags are timestamped proof of pace and make bisecting a regression quick.
- **Rejected:** Feature branches/PRs (overhead); one big commit at the end (no evidence, no rollback points).
- **If it breaks:** *Bad commit breaks the app* → `git revert` it (don't rewrite pushed history); re-run `pytest -q`. *Doc links break after moving to docs/* → all planning docs sit together, so relative links keep working; fix any README links.

### D-48 · Python 3.11 everywhere; exact pins from `pip freeze`
> 🔁 **Refined by D-64 (Python version)** (2026-09-13).
- **Decision:** Python 3.11 locally and on the host (set in the host's advanced settings). After the P0 install, pin exact versions of the direct dependencies (`anthropic`, `streamlit`, `python-docx`, `pydantic`, `pyyaml`, `pytest`, `tzdata`) from `pip freeze`.
- **Why:** "Works locally, fails on deploy" is the most common late-stage failure. Pins taken from the actually-installed versions avoid guessing version numbers, and `tzdata` guarantees `ZoneInfo` works on slim hosts.
- **Rejected:** Unpinned requirements; guessed version numbers.
- **If it breaks:** *Host install fails on a pin* → read the host build log; relax only that package to the host-compatible version, and re-run tests locally with the same version.

### D-49 · Test-first scenarios with a must-pass subset
- **Decision:** All 14 scenario files are written in P1, before the logic. They must pass **offline** in P2 and **live** in P3 (subset) and P6 (full). The must-pass subset is **S01, S02, S05, S06, S08, S14**: the sample, missing field, wrong-template signal, empty clause, injection, and AI-down. Expected results only change when architecture §5.2 shows the expectation was wrong, and that change is logged here.
- **Why:** Writing expectations first stops the build from quietly redefining "correct" to match whatever the code does. The must-pass set covers the planted issues and the riskiest interviewer pokes.
- **Rejected:** Writing evals at the end (they end up describing the code instead of testing it).
- **If it breaks:** *Pressure to edit expectations to go green* → not allowed without a logged rationale (AI watch-list P6). *Suite too slow live* → run the must-pass subset live and the rest offline; note it in the results.

### D-50 · Deploy a walking skeleton in Phase 0
> 🔁 **Refined by D-61** (2026-09-13).
- **Decision:** Within the first 15 minutes, deploy a minimal `app.py` (title + today's date in `APP_TIMEZONE`) to the production host with secrets configured. Later phases redeploy to the same URL on every push.
- **Why:** It removes deploy, secrets, Python-version, and timezone risk at minute 15 instead of hour 2. It also confirms the D-15 timezone behaviour on the actual server.
- **Rejected:** Deploying for the first time in P5.
- **If it breaks:** If the skeleton can't deploy in P0 within 10 minutes, switch to the D-36 fallback host immediately and record why.

### D-51 · On a library match, code substitutes the exact library text
- **Decision:** When the Clause Analyst returns `library_match`, the orchestrator replaces `proposed_text` with the library entry's exact text and sets `proposed_text_source = "library"`. Model-written wording is kept only when there's no match (`ai_drafted`).
- **Why:** Approved language must be byte-identical to what legal approved (D-11). LLMs paraphrase even when told to copy, and a paraphrase could silently drop a safeguard while still looking "approved".
- **Rejected:** Trusting the model to copy text verbatim; fuzzy-matching the paraphrase against the library.
- **If it breaks:** *Wrong library entry matched* → the substitution faithfully inserts the wrong clause, but it's still `NEEDS_REVIEW` and visible. Fix the entry's keywords (D-11). *Library text doesn't fit the request* → the reviewer uses "Edit text" or "Remove".

### D-52 · One intermediate `RenderedDoc` feeds both the .docx and the UI preview
- **Decision:** The assembler first builds a `RenderedDoc` (paragraphs → runs with highlight/marker/note flags). The python-docx writer and the Streamlit HTML preview both render from it, and the QA gate checks both the `RenderedDoc` and the written .docx.
- **Why:** Two separate rendering paths would eventually disagree, and the reviewer would approve a preview that differs from the downloaded file. One model means one source of truth, and it's easier to unit test than .docx XML.
- **Rejected:** Separate preview logic; previewing by converting .docx → HTML (extra dependency, lossy).
- **If it breaks:** *Preview and docx differ* → a writer-level bug: QA Q3/Q5 run on the docx text and flag it. Add a test that extracts docx text and compares it with the `RenderedDoc` text.

### D-53 · Verifier ships in two stages
- **Decision:**
  - **Stage 1 (P3, never cut):** a deterministic check that the matched library entry's `satisfies` list covers the rule's `required_safeguards`. `ai_drafted` or reviewer-edited text is marked "not verified" and stays `NEEDS_REVIEW`.
  - **Stage 2 (P6, stretch):** the LLM evidence Verifier from D-27 (quotes checked in code) for AI-drafted, edited, and library text.
- **Why:** The safety property (unverified text never passes silently) is guaranteed from P3 at zero risk. The LLM verifier adds depth for the demo only if time allows, which is consistent with the cut line.
- **Rejected:** Building only the LLM verifier (cut risk would remove all verification); building only the deterministic check (can't verify AI-drafted text).
- **If it breaks:** *Stage 2 contradicts stage 1 on library text* → trust stage 1 for library text (it's approved by definition) and log the disagreement as a prompt issue. *Stage 2 unavailable* → stage 1 behaviour applies automatically.

### D-54 · Transparent time accounting
- **Decision:** Planning artifacts (context, problem statement, decisions, architecture, implementation plan) were prepared **before** the build. The **3-hour build clock** starts at P0 and is tracked per phase in the implementation.md §0 tracker, backed up by commit and tag timestamps. If asked, state this split openly.
- **Why:** The brief says "3 hours, strictly" and scores speed relative to effort. Honest, evidence-backed accounting builds trust in an interview. Overclaiming speed is easy to expose and costly.
- **Rejected:** Presenting total effort vaguely; not tracking time.
- **If it breaks:** *The build exceeds 3 hours* → stop at the cut line and report actual time and what was cut. *Interviewer counts planning time* → explain that planning is part of how you direct AI tools well, and show the phase timestamps.

---

## H. Stack Change: Groq + Vercel (2026-09-13)

> The user set the runtime stack: **Groq API** for LLM calls, **Vercel** (connected to GitHub) for hosting, and repo **github.com/Flukeshotz/Zycus**. Facts below were verified the same day: Groq models API with the provided key, Groq docs (structured outputs, tool use, reasoning, rate limits, Python SDK), Vercel docs (FastAPI, function duration), GitHub API (repo public and empty).

### D-55 · Runtime LLM provider: Groq
- **Decision:** All runtime LLM calls go to Groq through the official `groq` Python SDK (`from groq import Groq`, env `GROQ_API_KEY`). The *build* tool is still Claude Code (D-40).
- **Why:** The user chose it and already has a key. Groq's fast inference keeps live-demo latency low. The account has open-weight models with **strict structured outputs** and **tool calling** (`openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.8-27b`). The free tier costs nothing.
- **Supersedes:** D-24 (Anthropic `claude-opus-5`) and D-29 (Anthropic refusal fallbacks; there's no Groq equivalent, so provider failures route to G7 per D-13). D-30: no reliance on prompt caching.
- **Trade-offs accepted:** free-tier limits of 8K tokens/min per model (D-60); structured outputs can't be combined with tool use (D-58); smaller models than frontier ones, so more reliance on the rules, gates, and approved library the architecture already has.
- **If it breaks:** *401* → key rotated or revoked: update the Vercel env var and redeploy. *Model decommissioned* (404 / model not found) → `GET https://api.groq.com/openai/v1/models`, then change the `MODEL_*` env var (models are config, not code). *Quality too low on a scenario* → move that judgment into rules or the library first, then raise `reasoning_effort`, then swap the model via env.

### D-56 · Model allocation across three model rate-limit buckets
- **Decision:**

  | Step | Model (env var) | Reasoning params | Temperature (D-59) | Max completion tokens |
  |---|---|---|---|---|
  | Normalizer | `openai/gpt-oss-20b` (`MODEL_NORMALIZER`) | `reasoning_effort="low"`, `include_reasoning=False` | 0.3 | 1,500 |
  | Clause Analyst: research loop | `openai/gpt-oss-120b` (`MODEL_ANALYST`) | `reasoning_effort="medium"`, `include_reasoning=False` | 0.5 | 1,024 per turn |
  | Clause Analyst: decision | `openai/gpt-oss-120b` (`MODEL_ANALYST`) | `reasoning_effort="medium"`, `include_reasoning=False` | 0.3 | 2,000 |
  | Verifier stage 2 | `qwen/qwen3.8-27b` (`MODEL_VERIFIER`) | `reasoning_effort="low"`, `reasoning_format="hidden"` | 0.2 | 1,500 |

- **Why:** Groq rate limits are **per model**. Spreading the pipeline over three models gives three separate token budgets, which lets the Normalizer and Clause Analyst run in parallel (D-31) without competing for one 8K TPM bucket. The largest model goes where judgment matters (clause risk), the small fast model does extraction, and a **different model family** verifies, so its errors are less likely to line up with the analyst's. All three support strict mode.
- **Refines:** D-31 (parallelism now also spreads rate-limit load).
- **Rejected:** one model for everything (one TPM bucket, so 429s on back-to-back runs); Llama models (not listed on this account).
- **If it breaks:** *Qwen rejects strict mode or reasoning params* → run the verifier on `openai/gpt-oss-20b` and log it. *20b misreads inputs* → switch `MODEL_NORMALIZER` to 120b and watch TPM. *429s while parallel* → `PARALLEL=false`.

### D-57 · Structured outputs: Groq strict `json_schema` + a strict-schema converter
- **Decision:** Every structured call uses `response_format={"type": "json_schema", "json_schema": {"name": ..., "strict": True, "schema": ...}}`. The schema comes from Pydantic via `core/schema.py::strict_schema(Model)`, which recursively sets `additionalProperties: false`, lists **every** property in `required` (optional fields become nullable unions), and strips `default` and unsupported keywords. Responses are parsed with `Model.model_validate_json(...)`, so Pydantic stays as a second check.
- **Why:** Groq strict mode requires all fields to be required and `additionalProperties: false`. Pydantic's default schemas break that rule for optional fields. Constrained decoding guarantees output that parses.
- **Refines:** D-25.
- **If it breaks:** *400 schema rejected* → print the generated schema, simplify (flatten, drop `format`/`pattern`), re-run spike S-7. *Valid JSON, wrong meaning* → eval scenario + prompt examples (D-25).

### D-58 · Clause Analyst as a two-phase agent: research loop → structured decision
- **Decision:**
  - **Phase A (research):** a tool loop on `openai/gpt-oss-120b` with `tools` = `get_rules`, `search_clause_library`, `get_template_section`, **no** `response_format`, max 6 iterations. Tool outputs are compact and collected into an **evidence pack**.
  - **Phase B (decision):** one strict `json_schema` call (no tools) that receives the clause request plus the evidence pack and returns `ClauseAssessment`. Code then checks that cited rule IDs appear in the evidence pack and applies D-51 (exact library text).
- **Why:** Groq's docs state that tool use isn't supported together with Structured Outputs. Splitting keeps both properties: real agentic retrieval (tool calls visible in the trace) and a guaranteed-typed result. Passing the evidence pack instead of the raw transcript keeps the decision prompt small (D-60), and the trace shows exactly what evidence the decision used.
- **Supersedes:** D-44. **Refines:** D-26.
- **Rejected:** asking the tool loop to emit JSON as text (no guarantee); dropping tools and stuffing all rules into one structured call (loses the agent story, doesn't scale).
- **If it breaks:** *Model never calls tools* → the system prompt requires `get_rules` and `search_clause_library` before finishing. If neither was called after 2 iterations, code runs both deterministically and adds the results to the evidence pack, marked `auto_retrieved` in the trace. Never decide without evidence. *Iteration cap hit* → go to Phase B with the evidence collected so far (the clause is already NEEDS_REVIEW via G5). *Malformed tool arguments* (JSON parse error) → return a `role: "tool"` message starting with `ERROR:`; it counts toward the cap.

### D-59 · Temperature is set explicitly and tuned by evals
- **Decision:** Extraction and verification steps use 0.2–0.3; clause reasoning uses 0.5 (table in D-56). Stability is measured by running the must-pass live scenarios **twice** in P6. Any status that flips between runs moves into a deterministic gate (the principle from D-28 stays).
- **Why:** Unlike Opus 5, Groq supports `temperature`. Groq recommends 0.5–0.7 for reasoning models. We follow that for open-ended clause analysis and go lower for extraction and verification, where variety adds nothing. The evals decide whether that holds.
- **Supersedes:** D-28 (which assumed sampling parameters weren't available).
- **If it breaks:** *Repetitive or truncated output at low temperature* → raise that step to 0.5. *Flaky status* → fix with a gate, not by tuning temperature.

### D-60 · Free-tier rate limits and token budgets
- **Facts (Groq docs, 2026-09-13):** free plan, per model: 30 requests/min, 1K requests/day, **8K tokens/min**, 200K tokens/day. A 429 includes `retry-after`; `x-ratelimit-remaining-*` headers are always present.
- **Decision:**
  1. Per-call `max_completion_tokens` caps (D-56).
  2. Compact tools: return only the matched rule, library entry, or section, never whole files.
  3. Short, static prompts.
  4. Input caps: each field ≤ 1,000 characters, special clause ≤ 2,000 (limits token burn and abuse of the public URL).
  5. SDK retries 2× with backoff; client timeout 20 s per call. A persistent 429 → `AIUnavailable("rate_limited")` → G7 degraded path. A safe draft is still produced, with the banner *"AI rate limit reached — safe fallback applied"*.
  6. The trace records prompt/completion tokens and `x-ratelimit-remaining-tokens` for each call (via `with_raw_response`).
  7. Evals: the offline suite runs any time; the live must-pass subset runs sequentially, waiting when remaining tokens are below the next call's estimate; the full live suite runs at most once per day.
  8. Spike S-5 measures real tokens per run. If one run uses more than 6K tokens on `gpt-oss-120b`, move the research phase to `gpt-oss-20b` first.
- **Why:** An interviewer clicking Generate twice in a minute could otherwise exhaust 8K TPM and break the demo. Treating rate limits as a designed degradation rather than an error is the product-judgment answer.
- **Pending user decision (D-42):** upgrade to Groq's paid Developer tier for higher limits before the interview.
- **If it breaks:** *Repeated 429 during the demo* → the TPM window resets each minute, so walk through the degraded draft and trace meanwhile; or switch `MODEL_ANALYST` to `openai/gpt-oss-20b` via env and redeploy. *Daily tokens exhausted* → only the paid tier or the next day helps; prevent it by never running full live evals on interview day.

### D-61 · Hosting on Vercel via GitHub integration
- **Decision:** A Vercel project imported from GitHub `Flukeshotz/Zycus`. Production branch `main`; every push auto-deploys (with preview deploys). FastAPI zero-config entrypoint `app.py` at the repo root. `vercel.json` sets `functions["app.py"].maxDuration = 60` and excludes tests and docs from the bundle. A walking skeleton is deployed in P0 (D-50 kept).
- **Why:** The user chose it and has it connected. Vercel detects a FastAPI `app` in `app.py` automatically and serves `public/` from its CDN. With Fluid compute (on by default) the Hobby plan allows up to 300 s; **60 s is a deliberate fail-fast cap**, well above expected run time.
- **Supersedes:** D-36 (Streamlit Community Cloud).
- **Rejected:** Streamlit on Vercel (Streamlit runs its own long-lived server, not an ASGI app Vercel detects).
- **If it breaks:** *Build fails* → Vercel build logs (dependency or Python version, D-64). *504 timeout* → the trace shows the slow step; check Groq waits (D-60) or the loop cap; raise `maxDuration` (≤ 300) only as a last resort. *Crash on import* → runtime logs in the dashboard or `vercel logs`. *Frontend 404* → confirm `public/` is at the repo root and the `/` redirect route exists. *Platform outage* → local `uvicorn` + ngrok fallback.

### D-62 · UI: FastAPI JSON API + static vanilla-JS single page
- **Decision:** Backend `app.py` (FastAPI) exposes `GET /api/health`, `GET /api/scenarios`, `GET /api/rulebook`, `POST /api/run`, `POST /api/render`. The frontend is `public/index.html` + `public/app.js` + `public/styles.css` with **no build step**, served by the Vercel CDN. Same tabs as before (Review · Draft · Agent Trace · Field Table · Rules). Scenario presets (D-38) come from `/api/scenarios`. `/api/run` accepts `simulate_ai_failure: true` to demo degraded mode (S14) live without changing server config.
- **Why:** Streamlit can't be deployed on Vercel (D-61). A thin JSON API keeps all logic in tested Python (the UI holds no business logic), and the endpoints are testable with FastAPI's `TestClient`. Vanilla JS avoids a Node build pipeline inside a 3-hour window.
- **Supersedes:** D-35 (Streamlit + session state). D-38 kept.
- **Rejected:** a Next.js frontend (second toolchain); server-rendered Jinja/HTMX (HITL state still has to round-trip, so it isn't simpler).
- **If it breaks:** *Stale UI* → the frontend replaces its whole state from each API response. *CORS errors locally* → serve static files from the same origin with `SERVE_STATIC=true`. *Business logic creeping into JS* (e.g., computing status) → move it into the API (AI watch-list P4).

### D-63 · Stateless HITL with a signed run envelope
- **Decision:** `/api/run` returns `{run_result, signature}`, where `signature = HMAC-SHA256(RUN_SIGNING_SECRET, canonical_json(run_result))`. The browser keeps it in memory. Reviewer actions call `/api/render` with `{run_result, signature, reviewer_actions}`. The server verifies the signature, validates the actions (enum; edited text ≤ 2,000 characters), applies them, recomputes readiness, and re-renders + runs QA **with no LLM call**. It returns the preview, the QA result, and the .docx as base64. A review item with a recorded reviewer action counts as resolved for readiness.
- **Why:** Serverless functions keep no memory between requests, so the Streamlit session-state design can't work. Client-held state avoids a database. The signature stops a tampered payload (e.g., flipping NEEDS_REVIEW to AUTO_FILLED) from producing a "ready" document. HITL clicks stay instant and use no tokens.
- **Supersedes:** the session-state part of D-35. D-12's rule that HITL never re-calls the LLM is kept.
- **Rejected:** server-side storage (a database: setup time and another dependency); an unsigned payload.
- **If it breaks:** *Every render returns 400 "signature invalid"* → canonical JSON mismatch: sign and verify with the same serializer, `json.dumps(run_result.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))`. *Secret differs across environments* → set it for Production, Preview, and Development. *Out of time* → cut line: drop signing; the server still re-validates payloads with Pydantic.

### D-64 · Python 3.12 on Vercel and locally
- **Decision:** `.python-version` contains `3.12`, and the local venv uses 3.12. Runtime dependencies go in `requirements.txt` (`fastapi`, `groq`, `python-docx`, `pydantic`, `pyyaml`, `tzdata`) with exact pins from `pip freeze`. Dev-only dependencies go in `requirements-dev.txt` (`pytest`, `httpx`, `uvicorn`, `python-dotenv`).
- **Why:** Vercel's Python runtime supports 3.12–3.14, and its docs use 3.12 as the baseline. The `groq` SDK needs ≥ 3.10. Keeping dev tools out of the function bundle keeps deploys lean.
- **Supersedes:** the 3.11 version in D-22 / D-48. D-48's pinning approach is unchanged.
- **If it breaks:** *Vercel uses a different Python* → check the build log and make sure `.python-version` is at the repo root. *A pin has no wheel for 3.12* → bump only that package.

### D-65 · Secrets, and the Groq key shared in chat
- **Decision:** Env vars: `GROQ_API_KEY`, `RUN_SIGNING_SECRET` (random, 32+ bytes), `APP_TIMEZONE=Asia/Kolkata`, `MODEL_NORMALIZER`, `MODEL_ANALYST`, `MODEL_VERIFIER`, `PARALLEL`. Set them in Vercel → Project → Settings → Environment Variables (Production, Preview, Development) and locally in `.env` (git-ignored; `.env.example` is committed without values). **The Groq key pasted into the planning chat is treated as exposed: rotate it in the Groq console before deploying, and use only the new key.** No key ever goes in code, docs, commits, the trace, or `/api/health`, which reports only `groq_key_configured: true/false`. `FORCE_AI_FAILURE` is never set in Production.
- **Why:** The repo is public (D-66). A leaked key lets anyone burn the free-tier quota the live demo depends on.
- **Supersedes:** D-37 (Anthropic/Streamlit secret names).
- **If it breaks:** *Key committed* → rotate immediately, then purge it from git history. *401 in production* → env var missing for the Production scope, or the old key → update it and **redeploy** (env var changes take effect only on a new deployment).

### D-66 · Code repository: GitHub `Flukeshotz/Zycus` (public)
- **Decision:** Remote `https://github.com/Flukeshotz/Zycus.git` (verified public and empty, default branch `main`, 2026-09-13). The local repo at `/Users/harsh/zycus` is initialized and pointed at this remote. Planning docs move into `docs/` in P0 (D-47).
- **Why:** The user provided it; public satisfies "public or invite-only"; Vercel is already connected to the account.
- **Resolves:** D-42 item 3 (visibility). **Refines:** D-47.
- **If it breaks:** *Push rejected (auth)* → the user authenticates git (`gh auth login` or credential manager). *Vercel not deploying* → check the project's Git connection and that the production branch is `main`.

### D-67 · Capability spike v2 (Groq + Vercel)
- **Decision:** `scripts/sdk_smoke.py` checks:
  - **S-1** auth, and all required models listed.
  - **S-2** strict `json_schema` on `gpt-oss-20b` with `reasoning_effort`, `include_reasoning`, `temperature`, `max_completion_tokens`.
  - **S-3** a tool-call round trip on `gpt-oss-120b`.
  - **S-4** strict `json_schema` on `gpt-oss-120b` and on `qwen/qwen3.8-27b` with `reasoning_format="hidden"`.
  - **S-5** token usage for a realistic run, plus rate-limit headers via `with_raw_response`.
  - **S-6** python-docx comment support.
  - **S-7** the real `ClauseAssessment` strict schema is accepted.
  - **S-8** the deployed walking skeleton's `/api/health` shows today's date in `APP_TIMEZONE`.
  - **S-9** *(stretch)* the Prompt Guard response format.
- **Refines:** D-45 (same principle, new provider).
- **If it breaks:** Each ❌ maps to a named fallback: D-56 model swap, D-57 schema simplification, D-58 auto-retrieval, D-32 inline notes, D-68 regex-only.

### D-68 · Prompt-injection classifier (stretch, cut first)
- **Decision:** If time allows in P6, run `meta-llama/llama-prompt-guard-2-86m` (available on the account) over free-text fields. A positive result adds an INFO note, *"possible prompt injection"*, to the review report and the trace. It **never** changes status; routing already ignores free text (D-14).
- **Why:** Defense in depth, using a purpose-built classifier instead of regex alone, and one more real tool in the orchestration.
- **Rejected:** blocking runs on a positive result (false positives on legal text).
- **If it breaks:** *Unclear response format* → keep only the regex INFO rule (D-14). *512-token context limit* → classify only the first ~1,500 characters.
- **Verified in the Phase 0 spike (S-9, 2026-09-13):** `meta-llama/llama-prompt-guard-2-86m` returns its score as the raw completion text — a stringified float close to 1.0 for a detected injection (e.g. `"0.9995089769363403"`), not a JSON label. The classifier tool must `float()` the content and threshold it (e.g. > 0.5), not `json.loads()` it.

### D-69 · Gemini as a cross-provider fallback (conditional stretch) 🟡
- **Decision:** Use the Gemini key the user provided (verified 2026-09-13; lists `gemini-3.5-flash`, `gemini-3.8-flash`, `gemini-2.5-flash`, among others) **only as a fallback**, never as the primary provider. When a Groq *structured* call (Normalizer, Clause decision, Verifier) still fails with 429 / 5xx / timeout after SDK retries, retry it **once** on `MODEL_FALLBACK` (default `gemini-3.5-flash`). The call goes through Gemini's OpenAI-compatible endpoint (`https://generativelanguage.googleapis.com/v1beta/openai/`, `openai` SDK) with the same `response_format` json_schema shape. The research tool loop does **not** fall back; a Groq failure there triggers D-58 auto-retrieval, and the decision call may then fall back. The trace and the field reason record `served_by: gemini-fallback` as an INFO note. Controlled by `ENABLE_FALLBACK` (default `false`).
- **Build condition:** implement in P6 only if spike S-5 shows a run above ~6K tokens in a Groq model's bucket, a 429 appears during P3–P6 testing, **or** the user doesn't upgrade the Groq tier (D-42). Otherwise document it as ready-to-enable future work.
- **Why:** Groq's free tier of 8K tokens per minute is the biggest live-demo risk (D-60). A second vendor turns "degraded draft" into "full AI analysis" for most rate-limit cases, while D-13 still guarantees a safe draft if both fail. The OpenAI-compatible endpoint uses the same message and schema shapes as the Groq adapter, so this is a small adapter, not a second integration.
- **Trade-offs:** Google marks OpenAI-library compatibility as beta. Free-tier limits are only visible in AI Studio. Google's free-tier terms allow content to be used to improve its products: acceptable for this sample NDA, not for real confidential contracts (documented as a limitation). Mixing providers makes outputs less reproducible, so evals run with `ENABLE_FALLBACK=false`.
- **Rejected:** Gemini as primary (the user chose Groq); falling back on every error, including 400 schema errors (would hide real bugs); falling back mid tool loop (multi-turn state across providers).
- **If it breaks:** *Gemini's compatibility layer rejects the strict schema* → use best-effort JSON + Pydantic validation, or switch this adapter to the native Gemini SDK with a response schema; verify in spike S-10. *Fallback also rate-limited* → G7 degraded path as before. *Key invalid or missing* → `/api/health` shows `gemini_key_configured: false` and the fallback is skipped.
- **Verified in the Phase 0 spike (S-10, 2026-09-13):** a strict `json_schema` call to `gemini-3.5-flash` via the OpenAI-compatible endpoint succeeded end-to-end. The build condition (only implement if P3–P6 testing shows real 429 pressure) still applies — spike S-5 showed 7,728/8,000 tokens/min remaining after one realistic Normalizer-sized call, so headroom looks comfortable and this stays a stretch item, not P3 scope.
- **Security:** same handling as D-65. The Gemini key shared in chat is treated as exposed: rotate it before use, keep it only in Vercel env and `.env` as `GEMINI_API_KEY`, and never commit or log it.

---

---

## H2. Phase 0 Spike Results (2026-09-13)

All 10 capability-spike checks (`scripts/sdk_smoke.py`) passed against the live Groq and Gemini APIs, including both optional stretch checks. No fallback paths were needed.

| Check | Resolves | Result |
|---|---|---|
| S-1 Groq auth + models | D-55 | 14 models visible; all 3 required models present |
| S-2 Strict schema, gpt-oss-20b | D-56, D-57 | Passed |
| S-3 Tool-call round trip, gpt-oss-120b | D-58 | Passed — clean tool_calls → tool result → final answer |
| S-4 Strict schema, gpt-oss-120b + Qwen (`reasoning_format="hidden"`) | D-56 | Passed on both |
| S-5 Token usage + rate-limit headers | D-60 | Realistic Normalizer-sized call: 327 total tokens; 7,728/8,000 TPM remaining after |
| S-6 python-docx Word comments | D-32 | **Supported** — `add_comment` available; 🟡 resolved to ✅ |
| S-7 Real-shape strict schema (nested/enum/list/nullable) | D-57 | Passed |
| S-8 Timezone resolution | D-15 | `Asia/Kolkata` resolves correctly; long-form date `13 September 2026` |
| S-9 Prompt Guard shape (optional) | D-68 | Works, but returns a raw float string, not JSON — implementation note added to D-68 |
| S-10 Gemini fallback (optional) | D-69 | Works end-to-end; kept as a conditional stretch per its original build condition — token headroom (S-5) doesn't currently justify pulling it into P3 |

**Conclusion:** no 🟡 decisions remain. D-32 is the only status flip (🟡 → ✅). D-44/D-58's two-phase design (tools without structured output, then a separate strict-schema decision call) is confirmed necessary and working — S-3 and S-7 together prove the split works end to end.

---

## I. Post-P6 Audit Findings (2026-09-13)

> Logged while auditing the finished build against its own documentation. Each entry either
> reconciles code and docs that had drifted apart, or fixes a concrete defect found by the audit.

### D-70 · Gemini fallback: auto-enable when a key is configured, supersedes `ENABLE_FALLBACK`
- **Decision:** The fallback (D-69) is now controlled by **key presence**, not the `ENABLE_FALLBACK`
  env var: `enable_fallback = bool(GEMINI_API_KEY) and not DISABLE_FALLBACK`. `ENABLE_FALLBACK` is
  dead — the code no longer reads it. `DISABLE_FALLBACK` (default unset/false) is the real opt-out.
  README.md, `.env.example`, architecture.md §8.1/§11/§14, and implementation.md task 6.5 all still
  described the old `ENABLE_FALLBACK`-gated, default-off behavior; fixed to describe this.
- **Why:** D-69's own build condition — *"a 429 appears during P3–P6 testing"* — was met: P6's live
  paced eval runs saw remaining tokens dip to 32–42 out of 8,000 (docs/DEBUG_LOG.md, Phase 6 entry),
  one bad scenario ordering away from a real 429 mid-demo. Auto-enabling whenever a Gemini key is
  present means the safety net is on by default for anyone who configures one, without a second env
  var to remember — the failure mode being guarded against (a rate limit hitting *during the live
  interview demo*) is exactly the one a forgotten `ENABLE_FALLBACK=true` would fail to catch.
- **What stayed the same:** every other part of D-69 — Gemini as fallback-only, one retry, structured
  calls only (never the research tool loop, D-58's own auto-retrieval covers that path instead),
  `served_by: gemini-fallback` recorded on the trace step, D-13's safe-draft guarantee if both
  providers fail.
- **Rejected:** reverting to the original opt-in default — the change is live, evidence-backed, and
  demonstrably improves live-demo resilience; reverting a working safety net to match stale docs
  would fix the discrepancy in the wrong direction.
- **Gap found and fixed alongside this entry:** `evals/run.py` never disabled the fallback during
  eval runs, so the "14/14 100%" P6 result was not guaranteed pure-Groq despite D-69 explicitly
  promising eval reproducibility (*"evals run with ENABLE_FALLBACK=false"*) — fixed by having the
  eval runner set `DISABLE_FALLBACK=true` for the live run unless `--allow-fallback` is passed, and
  by surfacing `served_by` per scenario in `evals/results/latest.md` so any fallback use is visible,
  not silently absorbed into the pass count.
- **If it breaks:** *Fallback fires unexpectedly during an eval a reviewer expected to be pure-Groq*
  → check `evals/results/latest.md`'s `served_by` column, now always shown. *A future contributor
  sets `ENABLE_FALLBACK=false` expecting it to work* → it silently does nothing; `DISABLE_FALLBACK=true`
  is the real switch — this is exactly the confusion this entry exists to prevent from recurring.

### D-71 · UI/UX audit fixes (tables, error handling, test hygiene)
- **Decision:** Three small, low-risk fixes from a post-P6 UI/UX and correctness audit:
  1. `.trace-table` and `.field-table` (public/styles.css) now sit inside an `overflow-x: auto`
     wrapper — at 6–7 columns each, a narrow viewport could force the whole page to scroll
     horizontally instead of just the table, which the artifact/responsive-design convention this
     project otherwise follows explicitly forbids.
  2. `app.js`'s `sendRenderAction()` 422 handler now extracts `detail[0].msg` the same way
     `onGenerate()`'s already did, instead of assuming `detail` is always a plain string — FastAPI's
     own Pydantic validation errors return a list; only the one hand-raised `HTTPException` in
     `/api/render` used a plain string, so this path was one un-exercised validation error away from
     showing `[object Object]` in the toast.
  3. `tests/test_api.py::TestSigning::test_modified_result_fails_verification` tampered
     `RunResult.readiness` via `model_copy(update={"readiness": "READY_FOR_SIGNATURE_REVIEW"})` — a
     plain string, since `model_copy` doesn't re-validate — which still correctly proved the
     signature check fails, but tripped a Pydantic serializer warning on every test run. Changed to
     tamper with a real `Readiness` enum member instead (`Readiness.BLOCKED`), which exercises the
     same code path without the spurious warning.
- **Why:** found during a full post-P6 audit ("check status, find discrepancies, make sure it's
  working exactly as it should") — none of the three are functional regressions in what had already
  shipped, but all three are real gaps between "passes today's tests" and "correct in every case."
- **If it breaks:** *table wrapper changes column sizing* → `overflow-x: auto` on the wrapper only;
  the table's own width rules are untouched. *the 422 fix regresses the string-detail path* →
  `sendRenderAction` now checks `Array.isArray(err.detail)` before indexing, so a plain string still
  renders directly.

### D-72 · P7 deliverables were staged but never pushed — deck.html was 404 in production
- **Decision:** Committed and pushed the P7 finishing work that had been sitting staged locally since
  the P7 commit: `docs/deck.md`, `public/deck.html` (the interactive slide deck), five real UI
  screenshots under `public/screenshots/`, the README's deck-tab header link and deck-doc reference,
  and `pytest.ini`. Also created the `v1.0` tag the P7 tracker row already claimed existed.
- **Why:** README.md already advertised `https://zycus-blond.vercel.app/deck.html` as the live deck
  link, and the P7 tracker row claimed `git tag v1.0` had run — neither was true on disk. A reviewer
  clicking that link before this fix got a 404; `git tag -l` never had `v1.0`. Caught by auditing
  `git status` against what the docs claimed was shipped, not by assuming a clean-looking commit
  history meant everything in it had reached `origin/main`.
- **If it breaks:** *deck.html still 404s after this* → confirm the Vercel deployment actually
  rebuilt from the new commit (check the dashboard's latest deployment SHA); `public/` files need a
  redeploy to reach the CDN, same as any other static asset change.

### D-73 · Relative effective_date resolution extended beyond "today" to "tomorrow" / "day after tomorrow"
- **Decision:** `tools/parser.py::parse_date` now resolves "tomorrow" and "day after tomorrow" the
  same deterministic way it already resolved "today" (D-15) — via `timedelta` offsets, not a guess.
  `agents/normalizer.py`'s system prompt was updated so the live model classifies all three as
  `derived` (previously only "today" was exemplified; "tomorrow" was live-tested and came back
  `ambiguous`, routing to `G8_ambiguity` with the raw word "tomorrow" left in the document — the
  exact class of literal-text leak the assignment's planted issue #3 exists to catch, just for a
  phrase the original fix didn't anticipate). `core/orchestrator.py::_canonicalize_parsed_fields`
  was also fixed: it previously hardcoded `format_long_date(now.date())` for *every* DERIVED
  effective_date, which would have silently resolved a DERIVED "tomorrow" to **today's** date the
  moment the prompt started classifying it as derived — it now re-parses `inputs.effective_date`
  with the same parser instead of assuming the offset is always zero, falling back to today only if
  the parser genuinely can't resolve the text (unchanged safe default for that case).
- **Why:** found by hand-testing the deployed app with "tomorrow" as an effective-date input — a
  natural thing for a reviewer to type, not a contrived edge case. The system's own design principle
  (D-15: only the deterministic layer resolves relative dates, never an LLM guess) applies just as
  much to "tomorrow" as to "today"; leaving it unresolved was an unintentional gap in what the
  pattern covered, not a deliberate scope boundary. Genuinely ambiguous relative phrases ("next
  quarter", "once signed") are deliberately left unresolved — no single fixed date follows from them,
  so `G8_ambiguity` is still the correct, safe outcome there.
- **Verified:** offline (`tests/test_parser.py`, `tests/test_orchestrator.py`, FakeLLM/pipeline
  end-to-end) and live against the real deployment — `tomorrow` → next day's date, `day after
  tomorrow` → two days out, `today` unchanged, all `AUTO_FILLED_WITH_ASSUMPTION`/`G10_assumption`,
  none left ambiguous. 221/221 tests passing (was 215; 6 added).
- **If it breaks:** *a relative phrase resolves to the wrong date* → check `tools/parser.py`'s
  pattern order — "day after tomorrow" must be matched before the bare "tomorrow" pattern, since it
  contains "tomorrow" as a substring. *the live model still classifies "tomorrow" as ambiguous* →
  the prompt is guidance, not a guarantee; `G8_ambiguity` is the safe fallback either way, so this
  degrades to the pre-fix behavior rather than producing a wrong date. *a new relative phrase (e.g.
  "next Monday") needs the same treatment* → do not add it to `_TODAY_PATTERN`-style regex matching
  without a fixed, unambiguous offset — anything genuinely calendar-dependent belongs in
  `G8_ambiguity`, not a guess.

---

## Revision Log
| Date | Change |
|---|---|
| 2026-09-13 | Initial log: D-01 → D-42 created before build start |
| 2026-09-13 | Added D-43 → D-54 (implementation execution). D-26 refined by D-44; D-27 staged by D-53; D-41 cut line updated to match implementation.md |
| 2026-09-13 | Stack change: runtime LLM → Groq (D-55–D-60); hosting → Vercel with FastAPI + static UI and signed stateless HITL (D-61–D-64); secrets and repo (D-65–D-66); spike v2 (D-67); Prompt Guard stretch (D-68); Gemini fallback (D-69). Superseded D-24, D-28, D-29, D-35, D-36, D-37, D-44. D-41 cut line updated |
| 2026-09-13 | Phase 0 spike run: 10/10 checks passed live against Groq + Gemini. D-32 resolved 🟡→✅ (Word comments supported). Implementation notes added to D-68 (raw float response) and D-69 (verified but stays conditional) |
| 2026-09-13 | Post-P6 audit: D-70 (Gemini fallback now auto-enabled by key presence, `ENABLE_FALLBACK` superseded by `DISABLE_FALLBACK`, eval reproducibility fixed), D-71 (table overflow, 422 error handling, test hygiene), D-72 (pushed P7 deliverables that were staged but never reached `origin/main`; created `v1.0`) |
| 2026-09-14 | UI: dark theme replaced with a light theme (flat surfaces, no gradients/blur). D-73: relative effective_date resolution extended to "tomorrow" / "day after tomorrow" (parser, live-model prompt, and a hardcoded-to-today canonicalization bug all fixed); 221/221 tests passing |
