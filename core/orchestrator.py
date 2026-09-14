"""
Orchestrator (architecture.md §3 #3, §11, D-13, D-46, D-51). The single
place that wires every tool and agent together: intake -> normalize ->
assess the special clause -> verify (stage 1) -> deterministic rules ->
route every field -> assemble -> QA. `run()` is the whole pipeline for a
fresh submission; `rerender()` is the HITL path — it never calls an LLM
(D-12, D-63), only re-applies reviewer decisions and re-renders.

Failure policy (D-13): a failed `normalize()` call falls back to FakeLLM's
deterministic parser-based normalizer (which is, precisely, "the
deterministic fallback parser" the architecture describes — not a separate
implementation of it). A failed `assess_clause()` call has no such
fallback — clause risk judgment is never safely replaced by a keyword
match when the AI is known to be down (D-46) — so it becomes `clause=None`
and routes special_clause through gate G7.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from agents.verifier import verify_stage1
from core.config import get_settings
from core.exceptions import AIUnavailable
from core.fake_llm import FakeLLM, LLMClient
from core.llm import GroqLLM
from core.models import (
    BusinessInputs,
    ClauseAssessment,
    FieldDecision,
    Interpretation,
    NormalizedField,
    QAReport,
    Readiness,
    ReviewerAction,
    ReviewerActionType,
    RuleFinding,
    RunResult,
    TraceStepKind,
)
from core.router import FieldContext, readiness as compute_readiness, route_field
from core.trace import Trace
from tools import clause_library, mapper, rulebook, template_store
from tools.assembler import RenderedDoc, build_rendered_doc, write_docx
from tools.parser import format_long_date, parse_date, parse_duration
from tools.qa_gate import run_qa
from tools.template_store import Template

_ROUTABLE_FIELDS = [
    "disclosing_party", "receiving_party", "effective_date", "term", "governing_law",
    "survival_period", "purpose", "special_clause", "payment_terms", "contract_value",
]


def run(
    inputs: BusinessInputs,
    llm: LLMClient,
    now: datetime,
    tz: str = "Asia/Kolkata",
    simulate_ai_failure: bool = False,
    parallel: bool | None = None,
) -> RunResult:
    contract_type = inputs.contract_type
    trace = Trace()
    if parallel is None:
        parallel = get_settings().parallel

    with trace.step("intake", TraceStepKind.TOOL) as step:
        template = template_store.get_template(contract_type)
        step.output_summary = f"template={template.id}, {len(template.placeholders)} placeholders"

    normalized_by_field, clause, clause_ai_error = _understand(
        inputs, llm, tz, simulate_ai_failure, trace, parallel,
    )
    _canonicalize_parsed_fields(normalized_by_field, inputs, now, tz)

    verification = None
    if clause is not None:
        with trace.step("verify_stage1", TraceStepKind.RULE) as step:
            verification = verify_stage1(clause)
            present = sum(1 for c in verification.checks if c.present)
            step.output_summary = f"{present}/{len(verification.checks)} safeguards present"

    with trace.step("rule_engine", TraceStepKind.RULE) as step:
        findings = rulebook.evaluate(inputs, normalized_by_field)
        step.output_summary = f"{len(findings)} findings"

    findings_by_field: dict[str | None, list[RuleFinding]] = defaultdict(list)
    for f in findings:
        findings_by_field[f.field].append(f)

    with trace.step("router", TraceStepKind.RULE) as step:
        decisions = _route_all_fields(
            inputs, template, contract_type, normalized_by_field, findings_by_field,
            clause_ai_error, tz,
        )
        overall_readiness = compute_readiness(decisions)
        step.output_summary = f"readiness={overall_readiness.value}"

    document_notes = [
        f.message for f in findings if f.field is None and f.severity == "info"
    ]

    with trace.step("assemble", TraceStepKind.RENDER) as step:
        rendered, docx_bytes, qa = _render_and_qa(
            template, inputs, decisions, clause, overall_readiness, None,
        )
        step.output_summary = f"{len(rendered.paragraphs)} paragraphs, banner={bool(rendered.banner)}"

    with trace.step("qa", TraceStepKind.QA) as step:
        step.status = "ok" if qa.passed else "error"
        step.output_summary = f"passed={qa.passed}, {sum(1 for c in qa.checks if not c.passed)} failed checks"

    return RunResult(
        run_id=str(uuid.uuid4()),
        created_at=now.isoformat(),
        inputs=inputs,
        readiness=overall_readiness,
        decisions=decisions,
        clause=clause,
        verification=verification,
        qa=qa,
        trace=trace.steps,
        document_notes=document_notes,
    )


def rerender(run_result: RunResult, reviewer_actions: list[ReviewerAction]) -> RunResult:
    """The HITL path (D-12, D-63): applies reviewer decisions to the stored
    FieldDecisions, recomputes readiness, and re-renders + re-QAs. No LLM
    call, no new agent trace steps — only render/qa steps are appended."""
    template = template_store.get_template(run_result.inputs.contract_type)

    actions_by_field = {a.field: a for a in reviewer_actions}
    decisions = [d.model_copy() for d in run_result.decisions]
    for d in decisions:
        if d.field in actions_by_field:
            action_item = actions_by_field[d.field]
            d.reviewer_action = action_item.action
            if action_item.edited_text is not None:
                d.edited_text = action_item.edited_text
            if action_item.action == ReviewerActionType.EDIT:
                text = (action_item.edited_text or "").lower()
                safeguard_checks = {
                    "affiliate_defined": "affiliate" in text,
                    "need_to_know": "need to know" in text or "need-to-know" in text,
                    "equivalent_obligations": any(w in text for w in ["equivalent", "bound", "obligation"]),
                    "receiving_party_liable": any(w in text for w in ["liable", "liability", "responsible"]),
                }
                missing = [sg.replace("_", "-") for sg, ok in safeguard_checks.items() if not ok]
                if missing:
                    warning = f"Warning: edited text lacks required safeguard(s): {', '.join(missing)} (human decision stands)"
                    existing = [n for n in d.info_notes if not n.startswith("Warning: edited text lacks")]
                    d.info_notes = existing + [warning]

    overall_readiness = compute_readiness(decisions)

    trace = Trace()
    trace.steps = list(run_result.trace)
    with trace.step("rerender", TraceStepKind.RENDER) as step:
        rendered, docx_bytes, qa = _render_and_qa(
            template, run_result.inputs, decisions, run_result.clause, overall_readiness, reviewer_actions,
        )
        step.output_summary = f"{len(rendered.paragraphs)} paragraphs, banner={bool(rendered.banner)}"
    with trace.step("qa", TraceStepKind.QA) as step:
        step.status = "ok" if qa.passed else "error"
        step.output_summary = f"passed={qa.passed}"

    return run_result.model_copy(update={
        "decisions": decisions,
        "readiness": overall_readiness,
        "qa": qa,
        "trace": trace.steps,
    })


def render_docx(run_result: RunResult, reviewer_actions: list[ReviewerAction] | None = None) -> bytes:
    """Re-derive .docx bytes for an existing RunResult on demand — no LLM
    call, no stored bytes anywhere (RunResult stays small and signable)."""
    template = template_store.get_template(run_result.inputs.contract_type)
    if reviewer_actions is None:
        reviewer_actions = [
            ReviewerAction(field=d.field, action=d.reviewer_action, edited_text=d.edited_text)
            for d in run_result.decisions if d.reviewer_action is not None
        ]
    _, docx_bytes, _ = _render_and_qa(
        template, run_result.inputs, run_result.decisions, run_result.clause,
        run_result.readiness, reviewer_actions,
    )
    return docx_bytes


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _understand(
    inputs: BusinessInputs, llm: LLMClient, tz: str, simulate_ai_failure: bool, trace: Trace,
    parallel: bool,
) -> tuple[dict[str, NormalizedField], ClauseAssessment | None, str | None]:
    """
    Runs the Normalizer and Clause Analyst concurrently when `parallel` is
    set (D-31, D-56 — separate Groq model buckets, so they don't compete for
    one rate-limit window). Each task builds its own isolated Trace/step
    rather than appending to the shared `trace` from a worker thread, and
    — critically — the concurrent Clause Analyst call uses a SEPARATE
    GroqLLM instance from `llm` when `llm` is a GroqLLM: both tasks would
    otherwise write to the same instance's `last_call`/`last_tool_calls`
    side-channel attributes at the same time, corrupting whichever trace
    step reads them second. FakeLLM has no such state, so offline mode is
    unaffected either way.
    """
    fallback = FakeLLM(tz=tz)
    has_clause = bool(inputs.special_clause.strip())

    assess_llm = llm
    if parallel and has_clause and isinstance(llm, GroqLLM):
        assess_llm = GroqLLM(settings=llm.settings)

    def do_normalize():
        local_trace = Trace()
        with local_trace.step("normalize", TraceStepKind.AGENT) as step:
            try:
                if simulate_ai_failure:
                    raise AIUnavailable("simulated")
                normalized = llm.normalize(inputs)
                step.output_summary = "normalized via LLM"
                call_info = getattr(llm, "last_call", None)
                if call_info is not None:
                    step.record_usage(call_info)
            except AIUnavailable as e:
                normalized = fallback.normalize(inputs)
                step.output_summary = f"fell back to deterministic parser ({e.reason})"
        return normalized, local_trace.steps[0]

    def do_assess_clause():
        if not has_clause:
            return None, None, None
        local_trace = Trace()
        with local_trace.step("assess_clause", TraceStepKind.AGENT) as step:
            clause_result: ClauseAssessment | None = None
            clause_error: str | None = None
            try:
                if simulate_ai_failure:
                    raise AIUnavailable("simulated")
                clause_result = assess_llm.assess_clause(inputs.special_clause)
                clause_result = _apply_library_substitution(clause_result)  # D-51
                step.output_summary = f"deviation={clause_result.deviation}, source={clause_result.proposed_text_source}"
                call_info = getattr(assess_llm, "last_call", None)
                if call_info is not None:
                    step.record_usage(call_info)
                for tc in getattr(assess_llm, "last_tool_calls", None) or []:
                    step.tool_call(tc.get("name", "?"), tc.get("arguments", ""), "ok")
                auto = getattr(assess_llm, "last_auto_retrieved", None) or []
                if auto:
                    step.output_summary += f" (auto_retrieved={auto})"
            except AIUnavailable as e:
                clause_error = e.reason
                step.status = "error"
                step.error = e.reason
                step.output_summary = "AI analysis unavailable"
        return clause_result, clause_error, local_trace.steps[0]

    if parallel and has_clause:
        with ThreadPoolExecutor(max_workers=2) as executor:
            normalize_future = executor.submit(do_normalize)
            assess_future = executor.submit(do_assess_clause)
            normalized, normalize_step = normalize_future.result()
            clause, clause_ai_error, assess_step = assess_future.result()
    else:
        normalized, normalize_step = do_normalize()
        clause, clause_ai_error, assess_step = do_assess_clause()

    trace.steps.append(normalize_step)
    if assess_step is not None:
        trace.steps.append(assess_step)

    normalized_by_field = {f.field: f for f in normalized.fields}
    return normalized_by_field, clause, clause_ai_error


def _canonicalize_parsed_fields(
    normalized_by_field: dict[str, NormalizedField], inputs: BusinessInputs, now: datetime, tz: str,
) -> None:
    """
    The deterministic parser (tools/parser.py) is the source of truth for
    how date/duration fields are *displayed* — never whatever text the live
    Normalizer happened to put in normalized_value. This fixes real
    live-only bugs found in P3's first live run and in later live testing
    (D-73), none of which FakeLLM could exhibit (it already builds
    normalized_value from the parser):

      1. effective_date: the Normalizer's own system prompt (correctly)
         instructs it not to guess an actual date for a "derived" value —
         only the deterministic layer resolves relative date references
         (D-15, extended by D-73 beyond "today" to "tomorrow" / "day after
         tomorrow"). Observed live responses varied: sometimes
         normalized_value=None (clean deferral), sometimes a non-empty but
         still-unresolved echo like "use today's date" (a placeholder in
         different clothes). Both must be overridden by the parser's
         resolved value — trusting a non-empty string here is never correct
         for a DERIVED field, since the model was explicitly told not to
         compute one.

         D-73: this must call parse_date() on the actual raw input rather
         than assuming DERIVED always means "today" — an earlier version
         hardcoded format_long_date(now.date()), which would have silently
         resolved a DERIVED "tomorrow" to today's date the moment the
         Normalizer (or a future prompt update) started classifying
         "tomorrow" as derived instead of ambiguous. Falls back to today's
         date only if the parser itself can't resolve the raw text — the
         same safe default as before, now reached deliberately rather than
         unconditionally.
      2. term / survival_period: the model echoed the raw input phrase
         ("2 years from effective date") into normalized_value instead of
         a clean value, producing an awkward, redundant sentence in the
         document ("...for 2 years from effective date from the Effective
         Date...").

    This does NOT touch duration_months — G9's cross-check (core/router.py,
    via _parser_mismatch below) still compares the model's own reported
    duration_months against the parser's, independently of this display fix.
    Mutates in place.
    """
    date_nf = normalized_by_field.get("effective_date")
    if date_nf and date_nf.interpretation == Interpretation.DERIVED:
        # Unconditional: a DERIVED value is never trustworthy from the
        # model, whether it left normalized_value empty or filled it with
        # an unresolved echo of the input (both observed live) — only the
        # parser's resolution is ever correct here. Re-parse the raw input
        # ourselves rather than assuming "today" (D-73) — the offset
        # (today / tomorrow / day after tomorrow / N days ...) must come
        # from what the user actually typed.
        parsed = parse_date(inputs.effective_date, tz)
        if parsed is not None:
            resolved = format_long_date(parsed.value)
            if date_nf.normalized_value != resolved:
                normalized_by_field["effective_date"] = date_nf.model_copy(
                    update={"normalized_value": resolved}
                )
        else:
            # D-75: found live with "in 2 months" — the model classified it
            # DERIVED (our prompt's "derived" examples don't cover months,
            # but the model over-generalized from the day-based ones), and
            # our deterministic parser genuinely cannot resolve it. This
            # must NEVER fall back to format_long_date(now.date()) — that
            # was the exact shape of the D-74 bug, just reached through a
            # different door. When the model's classification and the
            # parser's own capability disagree, downgrade to AMBIGUOUS so
            # G8 routes it to a human with the raw text visible, instead of
            # G10 auto-filling a confident, silently wrong date.
            normalized_by_field["effective_date"] = date_nf.model_copy(
                update={"interpretation": Interpretation.AMBIGUOUS, "normalized_value": None}
            )

    for field_name in ("term", "survival_period"):
        nf = normalized_by_field.get(field_name)
        if nf is None:
            continue
        duration = parse_duration(getattr(inputs, field_name))
        if duration is None:
            continue  # genuinely unparseable — nothing canonical to prefer
        canonical = "perpetual" if duration.kind == "perpetual" else f"{duration.months} months"
        if nf.normalized_value != canonical:
            normalized_by_field[field_name] = nf.model_copy(update={"normalized_value": canonical})


def _apply_library_substitution(clause: ClauseAssessment) -> ClauseAssessment:
    """D-51: when the analyst names a library match, code — not the model —
    supplies the final text, so approved language can never be paraphrased."""
    if not clause.library_match:
        return clause
    entry = clause_library.get_entry(clause.library_match)
    if entry is None:
        return clause
    return clause.model_copy(update={"proposed_text": entry.text, "proposed_text_source": "library"})


def _route_all_fields(
    inputs: BusinessInputs,
    template: Template,
    contract_type: str,
    normalized_by_field: dict[str, NormalizedField],
    findings_by_field: dict[str | None, list[RuleFinding]],
    clause_ai_error: str | None,
    tz: str,
) -> list[FieldDecision]:
    na_fields = set(rulebook.not_applicable_fields(contract_type))
    decisions: list[FieldDecision] = []
    for field_name in _ROUTABLE_FIELDS:
        raw_value = getattr(inputs, field_name)
        nf = normalized_by_field.get(field_name)
        if nf is None:
            continue  # defensive — every routable field is always normalized
        ctx = FieldContext(
            name=field_name,
            raw_value=raw_value,
            required=mapper.is_required(template, field_name),
            is_na_field=field_name in na_fields,
            normalized=nf,
            findings=findings_by_field.get(field_name, []),
            ai_error=clause_ai_error if field_name == "special_clause" else None,
            parser_mismatch=_parser_mismatch(field_name, raw_value, nf, tz),
        )
        decisions.append(route_field(ctx))
    return decisions


def _parser_mismatch(field_name: str, raw_value: str, nf: NormalizedField, tz: str) -> bool:
    """G9: does the deterministic parser disagree with the Normalizer's
    reading of this field? Only meaningful for date/duration fields; a value
    neither can parse is left to G8 (ambiguity), not flagged as a mismatch."""
    if not raw_value or not raw_value.strip():
        return False
    if field_name == "effective_date":
        parsed = parse_date(raw_value, tz)
        if parsed is None:
            return False
        expected = format_long_date(parsed.value)
        return nf.normalized_value is not None and nf.normalized_value != expected
    if field_name in ("term", "survival_period"):
        duration = parse_duration(raw_value)
        if duration is None:
            return False
        if duration.kind == "perpetual":
            return nf.normalized_value is not None and nf.normalized_value != "perpetual"
        return nf.duration_months is not None and nf.duration_months != duration.months
    return False


def _render_and_qa(
    template: Template,
    inputs: BusinessInputs,
    decisions: list[FieldDecision],
    clause: ClauseAssessment | None,
    readiness_value: Readiness,
    reviewer_actions: list[ReviewerAction] | None,
) -> tuple[RenderedDoc, bytes, QAReport]:
    rendered = build_rendered_doc(template, inputs, decisions, clause, readiness_value, reviewer_actions)
    docx_bytes = write_docx(rendered)
    qa = run_qa(docx_bytes, rendered, template, inputs, decisions, clause, readiness_value, reviewer_actions)
    return rendered, docx_bytes, qa


# ---------------------------------------------------------------------------
# CLI — implementation.md task 2.9:
#   python -m core.orchestrator data/sample_inputs.json --offline
# writes out/*.docx and prints the decision table.
# ---------------------------------------------------------------------------


def _cli() -> int:  # pragma: no cover — exercised manually, not by pytest
    import argparse
    import json
    import time
    from pathlib import Path
    from zoneinfo import ZoneInfo

    parser = argparse.ArgumentParser(description="Run the contract authoring pipeline from a JSON input file.")
    parser.add_argument("input_file", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true", default=True, help="Use FakeLLM (default).")
    mode.add_argument("--live", action="store_true", help="Use GroqLLM (available from Phase 3).")
    parser.add_argument("--simulate-ai-failure", action="store_true")
    parser.add_argument("--tz", default="Asia/Kolkata")
    parser.add_argument("--out-dir", type=Path, default=Path("out"))
    args = parser.parse_args()

    with args.input_file.open() as f:
        inputs = BusinessInputs(**json.load(f))

    llm: LLMClient
    if args.live:
        if not get_settings().groq_key_configured:
            print("--live requires GROQ_API_KEY to be set (see .env). Falling back to --offline.")
            llm = FakeLLM(tz=args.tz)
        else:
            llm = GroqLLM()
    else:
        llm = FakeLLM(tz=args.tz)

    now = datetime.now(ZoneInfo(args.tz))
    start = time.perf_counter()
    result = run(inputs, llm, now, tz=args.tz, simulate_ai_failure=args.simulate_ai_failure)
    elapsed_s = time.perf_counter() - start

    print(f"run_id: {result.run_id}")
    print(f"readiness: {result.readiness.value}")
    print()
    print(f"{'field':<20} {'status':<28} {'gate':<20} reason")
    print("-" * 110)
    for d in result.decisions:
        print(f"{d.field:<20} {d.status.value:<28} {d.gate:<20} {d.reason}")
    if result.document_notes:
        print()
        print("Document-level notes:")
        for note in result.document_notes:
            print(f"  - {note}")
    print()
    print(f"QA: {'PASS' if result.qa.passed else 'FAIL'}")
    for c in result.qa.checks:
        if not c.passed:
            print(f"  ✗ {c.check_id} {c.name}: {c.detail}")

    _print_trace_summary(result, elapsed_s)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    docx_bytes = render_docx(result)
    out_path = args.out_dir / f"{result.run_id}.docx"
    out_path.write_bytes(docx_bytes)
    print()
    print(f"Wrote {out_path}")
    return 0 if result.qa.passed else 1


def _print_trace_summary(result: RunResult, elapsed_s: float) -> None:  # pragma: no cover
    """Task 3.8: trace summary, tokens per model, tool calls, latency."""
    print()
    print(f"Trace ({len(result.trace)} steps, {elapsed_s:.2f}s wall-clock):")
    tokens_by_model: dict[str, int] = defaultdict(int)
    agent_calls = 0
    tool_calls = 0
    for step in result.trace:
        detail = f"  {step.name:<16} {step.kind.value:<8} {step.status:<6} {step.duration_ms:7.1f}ms"
        if step.model:
            detail += f"  model={step.model}"
        if step.total_tokens:
            detail += f"  tokens={step.total_tokens}"
            tokens_by_model[step.model or "?"] += step.total_tokens
        if step.remaining_rate_limit_tokens:
            detail += f"  remaining_tpm={step.remaining_rate_limit_tokens}"
        if step.kind == TraceStepKind.AGENT:
            agent_calls += 1
        if step.tool_calls:
            tool_calls += len(step.tool_calls)
            detail += f"  tool_calls={[tc.name for tc in step.tool_calls]}"
        print(detail)
        if step.output_summary:
            print(f"      -> {step.output_summary}")
    print()
    print(f"LLM agent steps: {agent_calls} | tool calls: {tool_calls}")
    if tokens_by_model:
        print("Tokens per model:")
        for model, total in tokens_by_model.items():
            print(f"  {model}: {total}")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())
