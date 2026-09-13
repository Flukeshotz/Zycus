"""
Pydantic v2 data contracts (architecture.md §6).

Two categories of model live here, and the distinction matters for D-57:

  1. LLM OUTPUT MODELS — NormalizedField, NormalizedInputs, ClauseAssessment,
     SafeguardCheck, VerificationResult. These are converted to Groq strict
     json_schema via core/schema.py::strict_schema(). Strict mode requires
     every property to be listed in "required" with no defaults, so these
     models declare no field defaults; optional values are typed `X | None`
     (a required-but-nullable field, never an omittable one).

  2. EVERYTHING ELSE — deterministic / API / infra models (BusinessInputs,
     RuleFinding, FieldDecision, QAReport, TraceStep, RunResult, RunEnvelope,
     RenderRequest, ReviewerAction). These are never passed through
     strict_schema(), so ordinary Pydantic defaults are used freely.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Shared enums
# ---------------------------------------------------------------------------


class Interpretation(str, Enum):
    """How the Normalizer read a raw input value (architecture §6)."""

    CLEAR = "clear"
    DERIVED = "derived"
    AMBIGUOUS = "ambiguous"
    NOT_APPLICABLE = "not_applicable"
    MISSING = "missing"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FieldStatus(str, Enum):
    """The five field-level outcomes of the Confidence Router (architecture §5.1)."""

    AUTO_FILLED = "AUTO_FILLED"
    AUTO_FILLED_WITH_ASSUMPTION = "AUTO_FILLED_WITH_ASSUMPTION"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    BLOCKED_MISSING = "BLOCKED_MISSING"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class Readiness(str, Enum):
    """Document-level readiness, derived from all FieldDecisions (architecture §5.1)."""

    READY_FOR_SIGNATURE_REVIEW = "READY_FOR_SIGNATURE_REVIEW"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    BLOCKED = "BLOCKED"


class ReviewerActionType(str, Enum):
    """
    The four HITL actions available on a NEEDS_REVIEW special clause
    (architecture §5.4). Values match the action, not the UI button label:
      ACCEPT_PROPOSED  -> "Accept proposed"   -> audit record "accepted_fallback"
      USE_AS_REQUESTED -> "Use as requested"  -> audit record "accepted_nonstandard"
      REMOVE           -> "Remove clause"     -> audit record "removed"
      EDIT             -> "Edit text"         -> audit record "edited"
    """

    ACCEPT_PROPOSED = "accept_proposed"
    USE_AS_REQUESTED = "use_as_requested"
    REMOVE = "remove"
    EDIT = "edit"


class TraceStepKind(str, Enum):
    TOOL = "tool"
    AGENT = "agent"
    RULE = "rule"
    RENDER = "render"
    QA = "qa"


# ---------------------------------------------------------------------------
# Input contract
# ---------------------------------------------------------------------------


class BusinessInputs(BaseModel):
    """
    The raw form submitted by a reviewer (context.md §2.2). Length caps are a
    Groq free-tier token-budget guard, not a legal constraint (D-60).
    """

    contract_type: str = Field(default="mutual_nda", max_length=100)
    disclosing_party: str = Field(..., max_length=1000)
    receiving_party: str = Field(..., max_length=1000)
    effective_date: str = Field(..., max_length=1000)
    term: str = Field(..., max_length=1000)
    governing_law: str = Field(..., max_length=1000)
    survival_period: str = Field(..., max_length=1000)
    purpose: str = Field(..., max_length=1000)
    special_clause: str = Field(default="", max_length=2000)
    payment_terms: str = Field(default="", max_length=1000)
    contract_value: str = Field(default="", max_length=1000)


# ---------------------------------------------------------------------------
# LLM output models — strict-schema friendly (no defaults; see module docstring)
# ---------------------------------------------------------------------------


class NormalizedField(BaseModel):
    """One business-input field as interpreted by the Normalizer agent."""

    field: str
    raw_value: str
    normalized_value: str | None
    duration_months: int | None
    interpretation: Interpretation
    confidence: Confidence
    reason: str


class NormalizedInputs(BaseModel):
    fields: list[NormalizedField]


class ClauseAssessment(BaseModel):
    """Phase B (decision) output of the two-phase Clause Analyst (D-58)."""

    request_summary: str
    library_match: str | None
    deviation: Literal["standard", "non_standard", "unacceptable"]
    risks: list[str]
    conflicting_sections: list[int]
    rule_ids_cited: list[str]  # must appear in the evidence pack (checked in code)
    proposed_text: str | None
    proposed_text_source: Literal["library", "ai_drafted", "none"]
    confidence: Confidence


class SafeguardCheck(BaseModel):
    safeguard_id: str
    present: bool
    evidence_quote: str | None  # must literally appear in proposed_text (checked in code)


class VerificationResult(BaseModel):
    checks: list[SafeguardCheck]


# ---------------------------------------------------------------------------
# Deterministic / rule-engine models
# ---------------------------------------------------------------------------


class RuleFinding(BaseModel):
    """
    One output of the deterministic rule engine (tools/rulebook.py). `code`
    is either a rulebook rule id (e.g. "NDA-TERM-01") or a structural check
    sentinel not tied to a single YAML rule (e.g. "PARTY-IDENTICAL",
    "NO-ENTITY-DESIGNATOR", "WRONG-TEMPLATE-SIGNAL", "INJECTION-PATTERN").
    """

    code: str
    field: str | None = None
    severity: Literal["violation", "info"]
    message: str


class FieldDecision(BaseModel):
    """One field's outcome from the Confidence Router (architecture §5.2)."""

    field: str
    status: FieldStatus
    gate: str  # e.g. "G5_risk_shifting"
    value_for_document: str | None
    reason: str
    info_notes: list[str] = Field(default_factory=list)
    reviewer_action: ReviewerActionType | None = None


# ---------------------------------------------------------------------------
# Document generation & QA
# ---------------------------------------------------------------------------


class QACheckResult(BaseModel):
    check_id: str  # "Q1".."Q8"
    name: str
    passed: bool
    detail: str = ""


class QAReport(BaseModel):
    passed: bool
    checks: list[QACheckResult] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Trace
# ---------------------------------------------------------------------------


class ToolCallRecord(BaseModel):
    name: str
    arguments_summary: str
    output_summary: str
    is_error: bool = False


class TraceStep(BaseModel):
    name: str
    kind: TraceStepKind
    status: Literal["ok", "error"]
    started_at: str  # ISO timestamp
    duration_ms: float
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    remaining_rate_limit_tokens: str | None = None
    served_by: str | None = None  # e.g. "gemini-fallback" (D-69)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    input_summary: str | None = None
    output_summary: str | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Run result, envelope, and reviewer-action request
# ---------------------------------------------------------------------------


class RunResult(BaseModel):
    run_id: str
    created_at: str  # ISO, in APP_TIMEZONE
    inputs: BusinessInputs
    readiness: Readiness
    decisions: list[FieldDecision] = Field(default_factory=list)
    clause: ClauseAssessment | None = None
    verification: VerificationResult | None = None
    qa: QAReport
    trace: list[TraceStep] = Field(default_factory=list)
    # Static, document-level observations not tied to one input field (the
    # "(document)" row in architecture §4, e.g. mutual/one-way labels,
    # missing standard protections, signature block). Never block; INFO only.
    document_notes: list[str] = Field(default_factory=list)


class RunEnvelope(BaseModel):
    """Returned by POST /api/run and POST /api/render (D-63)."""

    run_result: RunResult
    signature: str
    preview_html: str
    docx_base64: str | None = None  # None when QA failed


class ReviewerAction(BaseModel):
    field: str
    action: ReviewerActionType
    edited_text: str | None = None


class RenderRequest(BaseModel):
    """Sent to POST /api/render. Never triggers an LLM call (D-12, D-63)."""

    run_result: RunResult
    signature: str
    reviewer_actions: list[ReviewerAction] = Field(default_factory=list)
