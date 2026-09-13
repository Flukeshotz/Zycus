"""
Field Mapper (architecture.md §3 #9, §7.1). Bridges BusinessInputs field
names and template placeholder names in both directions:

  - is_required / placeholder_for_field: used by the orchestrator when
    building each field's FieldContext for the router (required-ness comes
    from the template, not guessed).
  - unmapped_input_fields: detects inputs with no placeholder at all
    (payment_terms, contract_value on this NDA) — cross-referenced against
    the rulebook's not_applicable_for list, this is what catches "an input
    that doesn't belong in this contract type" (context.md §5).
  - map_decisions_to_placeholders: turns the router's per-field decisions
    into the {placeholder_name: value} dict the Assembler substitutes into
    section text.
"""
from __future__ import annotations

from core.models import BusinessInputs, FieldDecision
from tools.template_store import Template


def is_required(template: Template, field_name: str) -> bool:
    for spec in template.placeholders.values():
        if spec.field == field_name:
            return spec.required
    return False  # a field with no placeholder at all is never "required" in the document sense


def placeholder_for_field(template: Template, field_name: str) -> str | None:
    for placeholder_name, spec in template.placeholders.items():
        if spec.field == field_name:
            return placeholder_name
    return None


def unmapped_input_fields(template: Template, inputs: BusinessInputs) -> list[str]:
    """BusinessInputs fields with no corresponding template placeholder
    (e.g. payment_terms, contract_value on a Mutual NDA). contract_type
    itself only selects the template and is never a placeholder."""
    mapped_fields = {spec.field for spec in template.placeholders.values()}
    return [
        name for name in type(inputs).model_fields
        if name != "contract_type" and name not in mapped_fields
    ]


def map_decisions_to_placeholders(
    template: Template, decisions: list[FieldDecision]
) -> dict[str, str | None]:
    by_field = {d.field: d for d in decisions}
    result: dict[str, str | None] = {}
    for placeholder_name, spec in template.placeholders.items():
        decision = by_field.get(spec.field)
        result[placeholder_name] = decision.value_for_document if decision else None
    return result
