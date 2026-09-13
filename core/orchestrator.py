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
from datetime import datetime

from agents.verifier import verify_stage1
from core.exceptions import AIUnavailable
from core.fake_llm import FakeLLM, LLMClient
from core.models import (
    BusinessInputs,
    ClauseAssessment,
    FieldDecision,
    NormalizedField,
    QAReport,
    Readiness,
    ReviewerAction,
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
) -> RunResult:
    contract_type = inputs.contract_type
    trace = Trace()

    with trace.step("intake", TraceStepKind.TOOL) as step:
        template = template_store.get_template(contract_type)
        step.output_summary = f"template={template.id}, {len(template.placeholders)} placeholders"

    normalized_by_field, clause, clause_ai_error = _understand(inputs, llm, tz, simulate_ai_failure, trace)

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
            d.reviewer_action = actions_by_field[d.field].action

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
            ReviewerAction(field=d.field, action=d.reviewer_action)
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
) -> tuple[dict[str, NormalizedField], ClauseAssessment | None, str | None]:
    fallback = FakeLLM(tz=tz)

    with trace.step("normalize", TraceStepKind.AGENT) as step:
        try:
            if simulate_ai_failure:
                raise AIUnavailable("simulated")
            normalized = llm.normalize(inputs)
            step.output_summary = "normalized via LLM"
        except AIUnavailable as e:
            normalized = fallback.normalize(inputs)
            step.output_summary = f"fell back to deterministic parser ({e.reason})"
    normalized_by_field = {f.field: f for f in normalized.fields}

    clause: ClauseAssessment | None = None
    clause_ai_error: str | None = None
    if inputs.special_clause.strip():
        with trace.step("assess_clause", TraceStepKind.AGENT) as step:
            try:
                if simulate_ai_failure:
                    raise AIUnavailable("simulated")
                clause = llm.assess_clause(inputs.special_clause)
                clause = _apply_library_substitution(clause)  # D-51
                step.output_summary = f"deviation={clause.deviation}, source={clause.proposed_text_source}"
            except AIUnavailable as e:
                clause_ai_error = e.reason
                step.status = "error"
                step.error = e.reason
                step.output_summary = "AI analysis unavailable"

    return normalized_by_field, clause, clause_ai_error


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

    if args.live:
        try:
            from core.llm import GroqLLM  # not built until Phase 3

            llm: LLMClient = GroqLLM()
        except ImportError:
            print("--live requires core/llm.py (Phase 3) — not built yet. Falling back to --offline.")
            llm = FakeLLM(tz=args.tz)
    else:
        llm = FakeLLM(tz=args.tz)

    now = datetime.now(ZoneInfo(args.tz))
    result = run(inputs, llm, now, tz=args.tz, simulate_ai_failure=args.simulate_ai_failure)

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

    args.out_dir.mkdir(parents=True, exist_ok=True)
    docx_bytes = render_docx(result)
    out_path = args.out_dir / f"{result.run_id}.docx"
    out_path.write_bytes(docx_bytes)
    print()
    print(f"Wrote {out_path}")
    return 0 if result.qa.passed else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_cli())
