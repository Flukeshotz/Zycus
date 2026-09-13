# AI Mistakes Log

Where Claude Code (the AI coding tool) got something wrong while building this, and how it was
caught and corrected. The brief asks for this explicitly at the demo (R26) — kept separate from
DEBUG_LOG.md, which is about *runtime* bugs, not *build-time* AI mistakes.

Format per entry: **What it generated → How it was caught → Correction → Prompt change for next time.**

---

## Phase 0

*(none yet)*

---

## Phase 4

### Omission of the 4th HITL action "Edit text" and `edited_text` propagation
- **What it generated:** The initial frontend implementation only provided three HITL action buttons (`accept_proposed`, `use_as_requested`, `remove`), omitting the fourth action `edit` ("Edit text"). In addition, `FieldDecision` did not have an `edited_text` field, so any edited text was not preserved across stateless envelope round-trips.
- **How it was caught:** Verification step 3 in `docs/implementation.md` ("Edit text without safeguards → warning shown; decision recorded") and architecture §5.4.
- **Correction:** Added `edited_text` to `FieldDecision`, wired the "Edit text" button with an inline editor in `public/app.js`, implemented deterministic safeguard keyword validation in `rerender()`, and added automated integration tests in `tests/test_api.py`.
- **Prompt change for next time:** Ensure all HITL options listed in the architecture spec are verified in unit tests and UI controls before closing the phase.
