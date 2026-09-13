"""
Scenario eval runner (architecture.md §13, D-39, D-49, D-60).

Grades every scenario in evals/scenarios/ against its exact expected
readiness, per-field status/gate, QA result, and document text — not "looks
about right." --offline uses FakeLLM (free, no network); --live uses the
real Groq API and needs GROQ_API_KEY set.

Pacing & repeat support (P6, D-60):
- --pace: paces requests to stay within Groq free-tier limits (8,000 tokens/min),
  sleeping when remaining tokens are low.
- --repeat N: runs the suite N times sequentially to detect flaky responses.
- Generates evals/results/latest.md with a detailed markdown table.

Usage:
    python -m evals.run --offline
    python -m evals.run --offline --only S01,S05
    python -m evals.run --live --only S01,S02,S05,S06,S08,S14 --repeat 2 --pace
    python -m evals.run --live --pace
"""
from __future__ import annotations

import argparse
import io
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import docx as docx_lib

from core.fake_llm import FakeLLM
from core.models import BusinessInputs, RunResult
from core.orchestrator import render_docx, run
from evals.scenario_schema import Scenario, load_all_scenarios


@dataclass
class ScenarioOutcome:
    scenario: Scenario
    passed: bool
    problems: list[str]
    actual_readiness: str
    duration_s: float
    tokens_by_model: dict[str, int] = field(default_factory=dict)
    remaining_rate_limit_tokens: str | None = None


def _extract_text(docx_bytes: bytes) -> str:
    try:
        doc = docx_lib.Document(io.BytesIO(docx_bytes))
    except Exception:
        return ""
    return "\n".join(p.text for p in doc.paragraphs)


def evaluate_scenario(
    scenario: Scenario, llm, now: datetime, tz: str, mode: str
) -> ScenarioOutcome:
    t0 = time.perf_counter()
    inputs = BusinessInputs(**scenario.inputs)
    result: RunResult = run(
        inputs, llm, now, tz=tz, simulate_ai_failure=scenario.simulate_ai_failure
    )
    duration = time.perf_counter() - t0

    problems: list[str] = []
    decisions_by_field = {d.field: d for d in result.decisions}

    if result.readiness.value != scenario.expected.readiness:
        problems.append(
            f"readiness: expected {scenario.expected.readiness}, got {result.readiness.value}"
        )

    for field_name, expected_status in scenario.expected.fields.items():
        actual = decisions_by_field.get(field_name)
        if actual is None:
            problems.append(f"{field_name}: no decision produced")
        elif actual.status.value != expected_status:
            problems.append(
                f"{field_name}: expected status {expected_status}, got {actual.status.value}"
            )

    for field_name, expected_gate in scenario.expected.gate.items():
        actual = decisions_by_field.get(field_name)
        if actual and actual.gate != expected_gate:
            problems.append(f"{field_name}: expected gate {expected_gate}, got {actual.gate}")

    if result.qa.passed != scenario.expected.qa_pass:
        failed = [c.check_id for c in result.qa.checks if not c.passed]
        problems.append(
            f"qa_pass: expected {scenario.expected.qa_pass}, got {result.qa.passed} (failed: {failed})"
        )

    if scenario.expected.text_absent or scenario.expected.text_contains:
        docx_bytes = render_docx(result)
        full_text = _extract_text(docx_bytes).lower()
        for literal in scenario.expected.text_absent:
            if literal.lower() in full_text:
                problems.append(
                    f"text_absent violated: {literal!r} found in the rendered document"
                )
        for literal in scenario.expected.text_contains:
            if literal.lower() not in full_text:
                problems.append(
                    f"text_contains violated: {literal!r} not found in the rendered document"
                )

    for field_name, substrings in scenario.expected.info_notes_contain.items():
        actual = decisions_by_field.get(field_name)
        notes = " ".join(actual.info_notes).lower() if actual else ""
        for substr in substrings:
            if substr.lower() not in notes:
                problems.append(
                    f"{field_name}: info_notes missing substring {substr!r} (got {actual.info_notes if actual else []!r})"
                )

    for field_name, substr in scenario.expected.reason_contains.items():
        actual = decisions_by_field.get(field_name)
        reason = actual.reason if actual else ""
        if substr.lower() not in reason.lower():
            problems.append(f"{field_name}: reason missing substring {substr!r} (got {reason!r})")

    if scenario.expected.clause_source:
        expected_source = scenario.expected.clause_source.get(mode)
        if expected_source is not None:
            actual_source = (
                result.clause.proposed_text_source if result.clause else "none"
            )
            if actual_source != expected_source:
                problems.append(
                    f"clause_source[{mode}]: expected {expected_source}, got {actual_source}"
                )

    # Collect token usage and remaining tokens
    tokens_by_model: dict[str, int] = {}
    remaining_tokens: str | None = None
    for step in result.trace:
        if step.model and step.total_tokens:
            tokens_by_model[step.model] = (
                tokens_by_model.get(step.model, 0) + step.total_tokens
            )
        if step.remaining_rate_limit_tokens:
            remaining_tokens = step.remaining_rate_limit_tokens

    return ScenarioOutcome(
        scenario=scenario,
        passed=not problems,
        problems=problems,
        actual_readiness=result.readiness.value,
        duration_s=duration,
        tokens_by_model=tokens_by_model,
        remaining_rate_limit_tokens=remaining_tokens,
    )


def write_markdown_report(
    outcomes: list[ScenarioOutcome],
    mode: str,
    repeat_count: int,
    out_path: Path,
    tz_str: str,
) -> None:
    now_str = datetime.now(ZoneInfo(tz_str)).strftime("%Y-%m-%d %H:%M:%S %Z")
    total = len(outcomes)
    passed_count = sum(1 for o in outcomes if o.passed)
    must_pass_total = sum(1 for o in outcomes if o.scenario.must_pass)
    must_pass_passed = sum(1 for o in outcomes if o.scenario.must_pass and o.passed)

    total_tokens_by_model: dict[str, int] = {}
    for o in outcomes:
        for m, count in o.tokens_by_model.items():
            total_tokens_by_model[m] = total_tokens_by_model.get(m, 0) + count

    lines: list[str] = [
        "# Scenario Evaluation Report",
        "",
        f"- **Run Date**: {now_str}",
        f"- **Mode**: `{mode}`",
        f"- **Repeats**: {repeat_count}",
        f"- **Overall Pass Rate**: {passed_count}/{total} ({passed_count/total*100:.1f}%)",
        f"- **Must-Pass Pass Rate**: {must_pass_passed}/{must_pass_total} ({must_pass_passed/must_pass_total*100:.1f}%)",
        "",
        "## Token Usage by Model",
        "",
    ]

    if total_tokens_by_model:
        lines.append("| Model | Total Tokens |")
        lines.append("|---|---|")
        for m, count in sorted(total_tokens_by_model.items()):
            lines.append(f"| `{m}` | {count:,} |")
    else:
        lines.append("*No token usage recorded (offline mode or zero model calls).*")

    lines.extend([
        "",
        "## Scenario Results",
        "",
        "| ID | Title | Must-Pass | Expected | Actual | Result | Latency | Tokens | Details |",
        "|---|---|---|---|---|---|---|---|---|",
    ])

    for o in outcomes:
        mark = "✅ PASS" if o.passed else "❌ FAIL"
        must = "**Yes**" if o.scenario.must_pass else "No"
        tokens_str = (
            ", ".join(f"{m.split('/')[-1]}: {t}" for m, t in o.tokens_by_model.items())
            if o.tokens_by_model
            else "—"
        )
        problems_str = "; ".join(o.problems) if o.problems else "—"
        lines.append(
            f"| {o.scenario.id} | {o.scenario.title} | {must} | `{o.scenario.expected.readiness}` | `{o.actual_readiness}` | {mark} | {o.duration_s:.1f}s | {tokens_str} | {problems_str} |"
        )

    lines.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines))
    print(f"\nMarkdown report written to: {out_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the scenario suite against the pipeline.")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--offline", action="store_true", default=False)
    mode_group.add_argument("--live", action="store_true", default=False)
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Comma-separated scenario ids, e.g. S01,S05",
    )
    parser.add_argument("--repeat", type=int, default=1, help="Number of times to run each scenario")
    parser.add_argument(
        "--pace", action="store_true", default=False, help="Pace calls to stay within free-tier limits"
    )
    parser.add_argument("--tz", default="Asia/Kolkata")
    parser.add_argument(
        "--out", default="evals/results/latest.md", help="Output markdown report path"
    )
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
        llm = None

    now = datetime.now(ZoneInfo(args.tz))

    print(
        f"Running {len(scenarios)} scenario(s) in {mode} mode (repeat={args.repeat}, pace={args.pace})\n"
    )
    print(f"{'ID':<5} {'Result':<8} {'Must-pass':<10} {'Latency':<8} Title")
    print("-" * 95)

    all_repeats_outcomes: list[list[ScenarioOutcome]] = []

    for rep in range(args.repeat):
        if args.repeat > 1:
            print(f"\n--- Repeat {rep + 1}/{args.repeat} ---")

        repeat_outcomes: list[ScenarioOutcome] = []
        for i, scenario in enumerate(scenarios):
            scenario_llm = FakeLLM(tz=args.tz) if mode == "offline" else llm
            outcome = evaluate_scenario(scenario, scenario_llm, now, args.tz, mode)
            repeat_outcomes.append(outcome)

            mark = "PASS" if outcome.passed else "FAIL"
            must = "yes" if scenario.must_pass else ""
            print(
                f"{scenario.id:<5} {mark:<8} {must:<10} {outcome.duration_s:>5.1f}s   {scenario.title}"
            )
            if not outcome.passed:
                for problem in outcome.problems:
                    print(f"        - {problem}")

            # Pacing logic (D-60)
            if args.pace and mode == "live" and i < len(scenarios) - 1:
                # Check remaining rate limit tokens
                rem = outcome.remaining_rate_limit_tokens
                wait_sec = 3.0
                if rem:
                    try:
                        rem_val = int(rem)
                        if rem_val < 1000:
                            wait_sec = 20.0
                        elif rem_val < 2500:
                            wait_sec = 12.0
                        elif rem_val < 4000:
                            wait_sec = 6.0
                        if wait_sec > 3.0:
                            print(f"        [Pacing: remaining tokens low ({rem_val}), pausing {wait_sec:.0f}s...]")
                    except ValueError:
                        pass
                time.sleep(wait_sec)

        all_repeats_outcomes.append(repeat_outcomes)

    # Flakiness check across repeats
    flaky_scenarios: list[str] = []
    if args.repeat > 1:
        print("\n--- Flakiness Check Across Repeats ---")
        for idx, scenario in enumerate(scenarios):
            results = [all_repeats_outcomes[r][idx].passed for r in range(args.repeat)]
            if len(set(results)) > 1:
                flaky_scenarios.append(scenario.id)
                print(f"  FLAKY: {scenario.id} flipped between repeats ({results})")
        if not flaky_scenarios:
            print("  Zero flaky scenarios: all repeats consistent!")

    # Write report using the last/primary run
    final_outcomes = all_repeats_outcomes[-1]
    write_markdown_report(
        final_outcomes,
        mode=mode,
        repeat_count=args.repeat,
        out_path=Path(args.out),
        tz_str=args.tz,
    )

    total = len(final_outcomes)
    passed_count = sum(1 for o in final_outcomes if o.passed)
    must_pass_failures = [
        o.scenario.id for o in final_outcomes if o.scenario.must_pass and not o.passed
    ]

    print(f"\n{passed_count}/{total} scenarios passed in final run.")
    if must_pass_failures:
        print(f"MUST-PASS FAILURES: {', '.join(must_pass_failures)}")
    elif flaky_scenarios:
        print(f"FLAKY SCENARIOS: {', '.join(flaky_scenarios)}")
    else:
        print("All must-pass scenarios green.")

    return 0 if (not must_pass_failures and not flaky_scenarios) else 1


if __name__ == "__main__":
    raise SystemExit(main())
