"""
Template Store (architecture.md §3 #4, §7.1).

Loads and validates data/templates/<contract_type>.yaml. Fails fast on a
malformed template (P1) and raises UnsupportedContractType for a contract
type with no registered template (used by the UI to say "not supported"
rather than guess, per context.md §9 out-of-scope note).
"""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, model_validator

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "templates"


class UnsupportedContractType(Exception):
    """Raised when contract_type has no data/templates/<contract_type>.yaml."""


class PlaceholderSpec(BaseModel):
    field: str
    required: bool
    sections: list[str]


class Template(BaseModel):
    id: str
    title: str
    placeholders: dict[str, PlaceholderSpec]
    sections: list[str]
    section_text: dict[str, str]

    @model_validator(mode="after")
    def _every_section_has_text(self) -> "Template":
        missing = [s for s in self.sections if s not in self.section_text]
        if missing:
            raise ValueError(f"section_text missing entries for sections: {missing}")
        return self

    @model_validator(mode="after")
    def _every_placeholder_section_is_declared(self) -> "Template":
        for name, spec in self.placeholders.items():
            unknown = [s for s in spec.sections if s not in self.sections]
            if unknown:
                raise ValueError(
                    f"placeholder {name!r} references undeclared section(s): {unknown}"
                )
        return self


_CACHE: dict[str, Template] = {}


def get_template(contract_type: str) -> Template:
    if contract_type in _CACHE:
        return _CACHE[contract_type]

    path = DATA_DIR / f"{contract_type}.yaml"
    if not path.exists():
        raise UnsupportedContractType(contract_type)

    with path.open() as f:
        raw = yaml.safe_load(f)
    template = Template.model_validate(raw)
    _CACHE[contract_type] = template
    return template


def get_section(contract_type: str, section: str) -> str:
    """Return the verbatim text of one section (used by the get_template_section tool, D-58)."""
    template = get_template(contract_type)
    if section not in template.section_text:
        raise KeyError(f"section {section!r} not found in template {contract_type!r}")
    return template.section_text[section]


def list_supported_contract_types() -> list[str]:
    return sorted(p.stem for p in DATA_DIR.glob("*.yaml"))
