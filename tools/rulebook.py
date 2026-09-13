"""
Rulebook loader (architecture.md §3 #5, §7.2, D-03).

P1 scope: load and validate data/rulebook/nda_rules.yaml, fail fast on bad
data, and provide lookup helpers (get_rule, get_rules_by_topic) that the
Clause Analyst's get_rules tool and the P2 rule engine both depend on.

The deterministic rule *engine* (evaluate(slots, inputs) -> list[RuleFinding],
gates G1-G11's rule-violation checks) is P2 task 2.4 and is added to this
same module then — kept here rather than a separate file because the engine
reads directly from the same validated Rulebook this loader produces.
"""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

RULEBOOK_PATH = Path(__file__).resolve().parent.parent / "data" / "rulebook" / "nda_rules.yaml"


class Rule(BaseModel):
    """
    Rules in nda_rules.yaml have heterogeneous shapes (a term-range rule looks
    nothing like a disclosure-topic rule). extra="allow" lets each rule carry
    only the fields it needs; the P2 rule engine reads them with getattr(...,
    default) rather than assuming every rule has every attribute.
    """

    model_config = ConfigDict(extra="allow")

    id: str
    field: str | None = None
    topic: str | None = None


class DormantRule(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str


class InfoRule(BaseModel):
    id: str
    note: str


class Rulebook(BaseModel):
    version: int
    our_entities: list[str]
    entity_designators: list[str]
    rules: list[Rule]
    not_applicable_for: dict[str, list[str]]
    dormant_commercial_rules: list[DormantRule] = []
    info_rules: list[InfoRule] = []
    injection_patterns: list[str] = []

    @model_validator(mode="after")
    def _unique_rule_ids(self) -> "Rulebook":
        ids = [r.id for r in self.rules]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate rule ids in rulebook: {sorted(dupes)}")
        return self


_CACHE: Rulebook | None = None


def get_rulebook() -> Rulebook:
    global _CACHE
    if _CACHE is None:
        with RULEBOOK_PATH.open() as f:
            raw = yaml.safe_load(f)
        _CACHE = Rulebook.model_validate(raw)
    return _CACHE


def get_rule(rule_id: str) -> Rule:
    for rule in get_rulebook().rules:
        if rule.id == rule_id:
            return rule
    raise KeyError(f"rule {rule_id!r} not found in rulebook")


def get_rules_by_topic(topic: str) -> list[Rule]:
    """Used by the Clause Analyst's get_rules(topic) tool (D-58)."""
    return [r for r in get_rulebook().rules if r.topic == topic]


def get_rules_by_field(field: str) -> list[Rule]:
    return [r for r in get_rulebook().rules if r.field == field]


def not_applicable_fields(contract_type: str) -> list[str]:
    return get_rulebook().not_applicable_for.get(contract_type, [])


def is_our_entity(name: str) -> bool:
    normalized = name.strip().lower()
    return any(normalized == e.strip().lower() for e in get_rulebook().our_entities)


def has_entity_designator(name: str) -> bool:
    normalized = name.lower()
    return any(d.lower() in normalized for d in get_rulebook().entity_designators)
