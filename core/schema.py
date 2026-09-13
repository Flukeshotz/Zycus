"""
Pydantic v2 -> Groq strict json_schema converter (D-57).

Groq strict mode requires, on every object in the schema:
  - additionalProperties: false
  - every property listed in "required" (no true optional fields — an
    optional field becomes a nullable type instead, still required)

Pydantic's default model_json_schema() does not produce this shape for
optional fields (it omits them from "required" and doesn't set
additionalProperties). This module walks the generated schema and fixes it
up recursively, including through $defs/$ref, anyOf, and arrays.

Usage:
    from core.models import NormalizedInputs
    schema = strict_schema(NormalizedInputs)
    response_format = {
        "type": "json_schema",
        "json_schema": {"name": "normalized_inputs", "strict": True, "schema": schema},
    }
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

# Keywords Groq's strict mode does not support / does not need. Pydantic can
# emit these (e.g. "title", "default", "examples"); stripping them keeps the
# schema minimal and avoids 400s from unsupported keywords.
_STRIP_KEYS = {"title", "default", "examples", "description_source"}


def strict_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Return a Groq-strict-mode-compatible JSON Schema for a Pydantic model."""
    raw = model.model_json_schema()
    defs = raw.pop("$defs", {}) or raw.pop("definitions", {})

    # Fix up every definition in place first, then the root schema, so $ref
    # targets are already strict by the time anything points at them.
    fixed_defs = {name: _fix_node(node, defs) for name, node in defs.items()}
    fixed_root = _fix_node(raw, defs)

    if fixed_defs:
        fixed_root["$defs"] = fixed_defs
    return fixed_root


def _fix_node(node: Any, defs: dict[str, Any]) -> Any:
    if isinstance(node, list):
        return [_fix_node(item, defs) for item in node]
    if not isinstance(node, dict):
        return node

    node = {k: v for k, v in node.items() if k not in _STRIP_KEYS}

    # Recurse into known nested-schema locations first.
    if "properties" in node:
        node["properties"] = {
            key: _fix_node(val, defs) for key, val in node["properties"].items()
        }
    if "items" in node:
        node["items"] = _fix_node(node["items"], defs)
    for combinator in ("anyOf", "oneOf", "allOf"):
        if combinator in node:
            node[combinator] = [_fix_node(sub, defs) for sub in node[combinator]]

    # An object (has "properties", or declares type "object"): enforce strict
    # object rules. A bare $ref is left alone here — the referenced def is
    # fixed on its own and $ref must be the only key in its schema for some
    # validators, so we don't touch it further.
    is_object = node.get("type") == "object" or "properties" in node
    if is_object and "$ref" not in node:
        properties = node.get("properties", {})
        node["properties"] = properties
        node["required"] = list(properties.keys())
        node["additionalProperties"] = False

    return node


def make_optional_nullable(field_schema: dict[str, Any]) -> dict[str, Any]:
    """
    Helper for hand-built schemas (not usually needed when using Pydantic
    `X | None` fields, which model_json_schema already renders as anyOf with
    "null" — kept here for the rare manual-schema case).
    """
    if "anyOf" in field_schema:
        return field_schema
    return {"anyOf": [field_schema, {"type": "null"}]}
