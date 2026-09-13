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

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, model_validator

from core.models import BusinessInputs, NormalizedField, RuleFinding

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


def display_field_name(field_name: str | None) -> str:
    """'governing_law' -> 'Governing law'. Used in generated finding/reason text."""
    if not field_name:
        return "This field"
    return field_name.replace("_", " ").capitalize()


# ---------------------------------------------------------------------------
# Rule engine (P2 task 2.4) — deterministic, code-only checks against the
# rulebook. Never reads AI output; the router (core/router.py) is the only
# consumer of what this returns, via each field's list of RuleFinding.
# ---------------------------------------------------------------------------

_NA_SIGNAL_PATTERN = re.compile(r"^\s*(n/?a\b|none\b|not\s+applicable)", re.I)


def value_is_empty_or_na(raw_value: str) -> bool:
    """True for '', whitespace-only, or a value that starts with an
    N/A-style signal ('N/A', 'None', 'Not applicable — this is an NDA...').
    Used by both the rule engine and core/router.py's gates G3/G4."""
    if not raw_value or not raw_value.strip():
        return True
    return bool(_NA_SIGNAL_PATTERN.match(raw_value.strip()))


def _months_to_human(n: int) -> str:
    if n % 12 == 0:
        years = n // 12
        return f"{years} year{'s' if years != 1 else ''}"
    return f"{n} month{'s' if n != 1 else ''}"


def _normalize_governing_law(text: str) -> str:
    t = re.sub(r"^\s*state\s+of\s+", "", text.strip(), flags=re.I)
    return t.strip().lower()


def _check_duration_range(rule: Rule, nf: NormalizedField) -> RuleFinding | None:
    """Shared by NDA-TERM-01 and NDA-SURV-01: both are '{field}: standard_months
    range, else flag; perpetual is always flagged' rules."""
    field = rule.field
    standard = getattr(rule, "standard_months", None)

    if nf.normalized_value == "perpetual":
        range_note = f" the standard range is {standard[0]}-{standard[1]} months." if standard else ""
        return RuleFinding(
            code=rule.id, field=field, severity="violation",
            message=f"{display_field_name(field)} is stated as perpetual;{range_note}".rstrip(),
        )

    months = nf.duration_months
    if months is None or not standard:
        # Unparseable and not perpetual -> ambiguous (G8/G9's job, not the
        # rule engine's) or the rule has no numeric range to check against.
        return None

    lo, hi = standard
    if months < lo or months > hi:
        return RuleFinding(
            code=rule.id, field=field, severity="violation",
            message=(
                f"{display_field_name(field)} of {_months_to_human(months)} is outside the "
                f"standard range of {lo}-{hi} months."
            ),
        )
    return None


def _check_governing_law(rule: Rule, raw_value: str) -> RuleFinding | None:
    approved = getattr(rule, "approved", None) or []
    if not raw_value.strip():
        return None  # empty is G1's concern, not a list-membership violation
    normalized_input = _normalize_governing_law(raw_value)
    normalized_approved = {_normalize_governing_law(a) for a in approved}
    if normalized_input not in normalized_approved:
        return RuleFinding(
            code=rule.id, field="governing_law", severity="violation",
            message=f"'{raw_value.strip()}' is not on the approved governing-law list.",
        )
    return None


def _check_survival_longer_than_term(
    surv_rule: Rule, normalized: dict[str, NormalizedField]
) -> RuleFinding | None:
    if not getattr(surv_rule, "info_if_longer_than_term", False):
        return None
    term_nf, surv_nf = normalized.get("term"), normalized.get("survival_period")
    if not term_nf or not surv_nf:
        return None
    if term_nf.duration_months is None or surv_nf.duration_months is None:
        return None
    if surv_nf.duration_months <= term_nf.duration_months:
        return None
    total = term_nf.duration_months + surv_nf.duration_months
    return RuleFinding(
        code=f"{surv_rule.id}-INFO", field="survival_period", severity="info",
        message=(
            f"Confidentiality obligations survive {_months_to_human(surv_nf.duration_months)} "
            f"after a {_months_to_human(term_nf.duration_months)} term, extending total "
            f"exposure to up to {_months_to_human(total)}."
        ),
    )


def _check_parties(inputs: BusinessInputs) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    disclosing = inputs.disclosing_party.strip()
    receiving = inputs.receiving_party.strip()

    if disclosing and receiving and disclosing.lower() == receiving.lower():
        for field in ("disclosing_party", "receiving_party"):
            findings.append(RuleFinding(
                code="PARTY-IDENTICAL", field=field, severity="violation",
                message="Disclosing party and receiving party are identical.",
            ))
        return findings  # supersedes the checks below for this pair

    if disclosing and receiving:
        zycus_present = is_our_entity(disclosing) or is_our_entity(receiving)
        if not zycus_present:
            for field in ("disclosing_party", "receiving_party"):
                findings.append(RuleFinding(
                    code="NEITHER-PARTY-IS-ZYCUS", field=field, severity="violation",
                    message="Neither party is a recognized Zycus entity.",
                ))

    for field, name in (("disclosing_party", disclosing), ("receiving_party", receiving)):
        if name and not has_entity_designator(name):
            findings.append(RuleFinding(
                code="NO-ENTITY-DESIGNATOR", field=field, severity="violation",
                message=(
                    f"'{name}' has no recognizable legal entity designator "
                    f"(e.g. Inc., Ltd., Pvt. Ltd., LLC)."
                ),
            ))
    return findings


def _check_injection(special_clause: str) -> list[RuleFinding]:
    if not special_clause.strip():
        return []
    for pattern in get_rulebook().injection_patterns:
        if re.search(pattern, special_clause, re.I):
            return [RuleFinding(
                code="INJECTION-PATTERN", field="special_clause", severity="info",
                message=(
                    "This request contains language resembling a prompt-injection attempt; "
                    "treated as untrusted data only and does not change the routing decision."
                ),
            )]
    return []


def evaluate(inputs: BusinessInputs, normalized: dict[str, NormalizedField]) -> list[RuleFinding]:
    """
    The deterministic rule engine (architecture §3 #5, §5.2 gate G6). Reads
    raw BusinessInputs (for text checks: party names, governing law aliasing,
    injection patterns) and the Normalizer's parsed output (for numeric
    range checks: term/survival duration_months). Never reads special_clause
    beyond the injection-pattern scan — clause risk assessment is the Clause
    Analyst's job (P3), not the rule engine's.
    """
    rb = get_rulebook()
    findings: list[RuleFinding] = []

    for rule in rb.rules:
        if rule.field in ("term", "survival_period") and rule.field in normalized:
            finding = _check_duration_range(rule, normalized[rule.field])
            if finding:
                findings.append(finding)
        elif rule.field == "governing_law":
            finding = _check_governing_law(rule, inputs.governing_law)
            if finding:
                findings.append(finding)

    surv_rule = next((r for r in rb.rules if r.id == "NDA-SURV-01"), None)
    if surv_rule:
        finding = _check_survival_longer_than_term(surv_rule, normalized)
        if finding:
            findings.append(finding)

    findings.extend(_check_parties(inputs))
    findings.extend(_check_injection(inputs.special_clause))

    for info_rule in rb.info_rules:
        findings.append(RuleFinding(
            code=info_rule.id, field=None, severity="info", message=info_rule.note,
        ))

    return findings
