"""
Scenario file schema (architecture.md §13, D-49).

Structural validation only — this does not run the pipeline. evals/run.py
(P2+) loads scenarios through this schema, then feeds `.inputs` through the
real orchestrator and compares its `RunResult` against `.expected`.

Written in P1, deliberately before the pipeline logic exists (test-first,
D-49): these files are the specification the deterministic core and agents
must satisfy, not a description of whatever the code happens to do.
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

from core.models import FieldStatus, Readiness

SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"

_VALID_STATUSES = {s.value for s in FieldStatus}
_VALID_READINESS = {r.value for r in Readiness}


class ScenarioExpected(BaseModel):
    readiness: str
    fields: dict[str, str]
    qa_pass: bool
    text_absent: list[str] = Field(default_factory=list)
    text_contains: list[str] = Field(default_factory=list)
    info_notes_contain: dict[str, list[str]] = Field(default_factory=dict)
    reason_contains: dict[str, str] = Field(default_factory=dict)
    gate: dict[str, str] = Field(default_factory=dict)
    # {"offline": "none", "live": "ai_drafted"} — proposed_text_source differs
    # by mode since FakeLLM's keyword search != a live Clause Analyst (D-46).
    clause_source: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _valid_enum_values(self) -> "ScenarioExpected":
        if self.readiness not in _VALID_READINESS:
            raise ValueError(f"unknown readiness value: {self.readiness!r}")
        bad = {f: s for f, s in self.fields.items() if s not in _VALID_STATUSES}
        if bad:
            raise ValueError(f"unknown field status value(s): {bad}")
        return self


class Scenario(BaseModel):
    id: str
    title: str
    must_pass: bool = False
    simulate_ai_failure: bool = False
    inputs: dict[str, str]
    expected: ScenarioExpected


def load_scenario(path: Path) -> Scenario:
    with path.open() as f:
        raw = json.load(f)
    scenario = Scenario.model_validate(raw)
    file_id = path.stem.split("_", 1)[0]
    if scenario.id != file_id:
        raise ValueError(
            f"scenario id {scenario.id!r} in {path.name} does not match filename prefix {file_id!r}"
        )
    return scenario


def load_all_scenarios() -> list[Scenario]:
    return [load_scenario(p) for p in sorted(SCENARIOS_DIR.glob("S*.json"))]
