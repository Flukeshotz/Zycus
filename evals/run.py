"""
Scenario eval runner (architecture.md §13, D-39, D-49).

Grades every scenario in evals/scenarios/ against its exact expected
readiness, per-field status/gate, QA result, and document text — not "looks
about right." --offline uses FakeLLM (free, no network); --live uses the
real Groq API and needs GROQ_API_KEY set. Free-tier pacing across many
scenarios is a P6 concern (D-60) — --only is how you stay within budget for
now.

Usage:
    python -m evals.run --offline
    python -m evals.run --offline --only S01,S05
    python -m evals.run --live --only S01,S04,S07,S08
"""
from __future__ import annotations

import argparse
import io
from datetime import datetime
from zoneinfo import ZoneInfo

import docx as docx_lib

from core.fake_llm import FakeLLM
from core.models import BusinessInputs
from core.orchestrator import render_docx, run
from evals.scenario_schema import Scenario, load_all_scenarios


def _extract_text(docx_bytes: bytes) -> str:
    try:
        doc = docx_lib.Document(io.BytesIO(docx_bytes))
    except Exception:
        return ""
    return "\n".join(p.text for p in doc.paragraphs)


def evaluate_scenario(scenario: Scenario, llm, now: datetime, tz: str, mode: str) -> tuple[bool, list[str]]:
    inputs = BusinessInputs(**scenario.inputs)
    result = run(inputs, llm, now, tz=tz, simulate_ai_failure=scenario.simulate_ai_failure)

    problems: list[str] = []
    decisions_by_field = {d.field: d for d in result.decisions}

    if result.readiness.value != scenario.expected.readiness:
        problems.append(f"readiness: expected {scenario.expected.readiness}, got {result.readiness.value}")

    for field, expected_status in scenario.expected.fields.items():
        actual = decisions_by_field.get(field)
        if actual is None:
            problems.append(f"{field}: no decision produced")
        elif actual.status.value != expected_status:
            problems.append(f"{field}: expected status {expected_status}, got {actual.status.value}")

    for field, expected_gate in scenario.expected.gate.items():
        actual = decisions_by_field.get(field)
        if actual and actual.gate != expected_gate:
            problems.append(f"{field}: expected gate {expected_gate}, got {actual.gate}")

    if result.qa.passed != scenario.expected.qa_pass:
        failed = [c.check_id for c in result.qa.checks if not c.passed]
        problems.append(f"qa_pass: expected {scenario.expected.qa_pass}, got {result.qa.passed} (failed: {failed})")

    if scenario.expected.text_absent or scenario.expected.text_contains:
        docx_bytes = render_docx(result)
        full_text = _extract_text(docx_bytes).lower()
        for literal in scenario.expected.text_absent:
            if literal.lower() in full_text:
                problems.append(f"text_absent violated: {literal!r} found in the rendered document")
        for literal in scenario.expected.text_contains:
            if literal.lower() not in full_text:
                problems.append(f"text_contains violated: {literal!r} not found in the rendered document")

    for field, substrings in scenario.expected.info_notes_contain.items():
        actual = decisions_by_field.get(field)
        notes = " ".join(actual.info_notes).lower() if actual else ""
        for substr in substrings:
            if substr.lower() not in notes:
                problems.append(f"{field}: info_notes missing substring {substr!r} (got {actual.info_notes if actual else []!r})")

    for field, substr in scenario.expected.reason_contains.items():
        actual = decisions_by_field.get(field)
        reason = actual.reason if actual else ""
        if substr.lower() not in reason.lower():
            problems.append(f"{field}: reason missing substring {substr!r} (got {reason!r})")

    if scenario.expected.clause_source:
        expected_source = scenario.expected.clause_source.get(mode)
        if expected_source is not None:
            actual_source = result.clause.proposed_text_source if result.clause else "none"
            if actual_source != expected_source:
                problems.append(f"clause_source[{mode}]: expected {expected_source}, got {actual_source}")

    return not problems, problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the scenario suite against the pipeline.")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--offline", action="store_true", default=True)
    mode_group.add_argument("--live", action="store_true")
    parser.add_argument("--only", type=str, default=None, help="Comma-separated scenario ids, e.g. S01,S05")
    parser.add_argument("--tz", default="Asia/Kolkata")
    args = parser.parse_args()

    mode = "live" if args.live else "offline"
    scenarios = load_all_scenarios()
    if args.only:
        wanted = set(args.only.split(","))
        scenarios = [s for s in scenarios if s.id in wanted]

    if mode == "live":
        from core.config import get_settings
        from core.llm import GroqLLM

        if not get_settings().groq_key_configured:
            print("--live requires GROQ_API_KEY to be set (see .env).")
            return 2
        llm = GroqLLM()
    else:
        llm = None  # per-scenario FakeLLM below, so simulate_ai_failure is honored per instance

    now = datetime.now(ZoneInfo(args.tz))

    print(f"Running {len(scenarios)} scenario(s) in {mode} mode\n")
    print(f"{'ID':<5} {'Result':<6} {'Must-pass':<10} Title")
    print("-" * 90)

    results: list[tuple[Scenario, bool, list[str]]] = []
    for scenario in scenarios:
        scenario_llm = FakeLLM(tz=args.tz) if mode == "offline" else llm
        passed, problems = evaluate_scenario(scenario, scenario_llm, now, args.tz, mode)
        results.append((scenario, passed, problems))
        mark = "PASS" if passed else "FAIL"
        must = "yes" if scenario.must_pass else ""
        print(f"{scenario.id:<5} {mark:<6} {must:<10} {scenario.title}")
        if not passed:
            for problem in problems:
                print(f"        - {problem}")

    total = len(results)
    passed_count = sum(1 for _, ok, _ in results if ok)
    must_pass_failures = [s.id for s, ok, _ in results if s.must_pass and not ok]

    print()
    print(f"{passed_count}/{total} scenarios passed.")
    if must_pass_failures:
        print(f"MUST-PASS FAILURES: {', '.join(must_pass_failures)}")
    else:
        print("All must-pass scenarios green.")

    return 0 if not must_pass_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
