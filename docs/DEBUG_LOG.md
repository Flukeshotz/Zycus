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
