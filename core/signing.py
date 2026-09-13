"""
HMAC-SHA256 signing for stateless HITL (D-63). Signs and verifies the
canonical JSON of a RunResult, so the frontend can send it back to
POST /api/render without the server needing server-side storage.

Canonical form:  json.dumps(run_result.model_dump(mode="json"),
                            sort_keys=True, separators=(",", ":"))
— deterministic byte-for-byte, no matter what dict ordering Python uses.

The signing secret comes from RUN_SIGNING_SECRET (≥32 bytes, hex) in env.
"""
from __future__ import annotations

import hashlib
import hmac
import json

from core.config import get_settings
from core.models import RunResult


def _canonical_json(run_result: RunResult) -> str:
    return json.dumps(
        run_result.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )


def sign(run_result: RunResult, secret: str | None = None) -> str:
    """Produce an HMAC-SHA256 hex signature over the canonical JSON."""
    if secret is None:
        secret = get_settings().run_signing_secret
    return hmac.new(
        secret.encode(), _canonical_json(run_result).encode(), hashlib.sha256
    ).hexdigest()


def verify(run_result: RunResult, signature: str, secret: str | None = None) -> bool:
    """Constant-time comparison of the provided signature vs. the expected one."""
    expected = sign(run_result, secret)
    return hmac.compare_digest(expected, signature)
