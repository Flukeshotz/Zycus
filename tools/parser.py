"""
Deterministic parser (architecture.md §3 #6, D-15).

Two jobs, both intentionally conservative — returning None (i.e. "I can't
confidently parse this") is always safe, because the router treats an
unparseable value as ambiguous (G8) or a cross-check mismatch (G9), which
routes to a human. A wrong guess would be unsafe; None never is.

  parse_duration(text)  -> a whole number of months, or "perpetual"
  parse_date(text, tz)  -> "today" resolved in a fixed timezone, or an
                           explicit calendar date

Used two ways (D-46): as the Normalizer's deterministic cross-check in every
mode (G9), and as the entire "Normalizer" in FakeLLM / degraded mode, since
these are exactly the patterns simple enough not to need an LLM at all.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Durations
# ---------------------------------------------------------------------------

_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

_PERPETUAL_PATTERN = re.compile(
    r"\b(perpetual(?:ly)?|indefinite(?:ly)?|forever|no\s+expir\w*)\b", re.I
)

_NUMBER_ALTERNATION = r"\d+|" + "|".join(_WORD_NUMBERS.keys())
_DURATION_PATTERN = re.compile(
    rf"\b(?P<number>{_NUMBER_ALTERNATION})\b\s*(?P<unit>years?|yrs?|months?|mos?)\b",
    re.I,
)


@dataclass(frozen=True)
class Duration:
    months: int | None  # None when kind == "perpetual"
    kind: Literal["fixed", "perpetual"]


def parse_duration(text: str) -> Duration | None:
    """
    Parse a free-text duration into whole months. Returns None when nothing
    confidently parseable is found (caller treats this as ambiguous).
    """
    if not text or not text.strip():
        return None
    stripped = text.strip()

    if _PERPETUAL_PATTERN.search(stripped):
        return Duration(months=None, kind="perpetual")

    match = _DURATION_PATTERN.search(stripped)
    if not match:
        return None

    raw_number = match.group("number").lower()
    number = _WORD_NUMBERS.get(raw_number)
    if number is None:
        try:
            number = int(raw_number)
        except ValueError:
            return None

    unit = match.group("unit").lower()
    months = number * 12 if unit.startswith(("year", "yr")) else number
    return Duration(months=months, kind="fixed")


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------

# Straight (') and curly (’) apostrophes both accepted — live LLM output
# or a user typing in the UI may use either.
_TODAY_PATTERN = re.compile(
    r"\b(today|use\s+today[’']?s\s+date|to\s+be\s+filled.*?today|current\s+date)\b",
    re.I,
)
# "day after tomorrow" must be checked before the bare "tomorrow" pattern,
# since it contains "tomorrow" as a substring and needs a different offset.
_DAY_AFTER_TOMORROW_PATTERN = re.compile(r"\bday\s+after\s+tomorrow\b", re.I)
_TOMORROW_PATTERN = re.compile(r"\btomorrow\b", re.I)

_MONTH_NAMES = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]
_MONTH_ALTERNATION = "|".join(_MONTH_NAMES)

_ISO_DATE_PATTERN = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DAY_MONTH_YEAR_PATTERN = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_ALTERNATION})\s+(\d{{4}})\b", re.I
)
_MONTH_DAY_YEAR_PATTERN = re.compile(
    rf"\b({_MONTH_ALTERNATION})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(\d{{4}})\b", re.I
)


@dataclass(frozen=True)
class ParsedDate:
    value: date
    interpretation: Literal["derived", "clear"]


def parse_date(text: str, tz: str) -> ParsedDate | None:
    """
    Resolve a relative date reference — "today" / "use today's date",
    "tomorrow", "day after tomorrow" — to a concrete date in `tz`
    (interpretation="derived"), or parse an explicit calendar date
    (interpretation="clear"). Returns None for anything else, including an
    invalid calendar date (e.g. "31 February") or a genuinely ambiguous
    relative phrase (e.g. "next quarter") that has no safe fixed offset.
    """
    if not text or not text.strip():
        return None
    stripped = text.strip()

    if _TODAY_PATTERN.search(stripped):
        today = datetime.now(ZoneInfo(tz)).date()
        return ParsedDate(value=today, interpretation="derived")

    if _DAY_AFTER_TOMORROW_PATTERN.search(stripped):
        today = datetime.now(ZoneInfo(tz)).date()
        return ParsedDate(value=today + timedelta(days=2), interpretation="derived")

    if _TOMORROW_PATTERN.search(stripped):
        today = datetime.now(ZoneInfo(tz)).date()
        return ParsedDate(value=today + timedelta(days=1), interpretation="derived")

    if m := _ISO_DATE_PATTERN.search(stripped):
        return _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    if m := _DAY_MONTH_YEAR_PATTERN.search(stripped):
        day = int(m.group(1))
        month = _MONTH_NAMES.index(m.group(2).lower()) + 1
        year = int(m.group(3))
        return _safe_date(year, month, day)

    if m := _MONTH_DAY_YEAR_PATTERN.search(stripped):
        month = _MONTH_NAMES.index(m.group(1).lower()) + 1
        day = int(m.group(2))
        year = int(m.group(3))
        return _safe_date(year, month, day)

    return None


def _safe_date(year: int, month: int, day: int) -> ParsedDate | None:
    try:
        return ParsedDate(value=date(year, month, day), interpretation="clear")
    except ValueError:
        return None


def format_long_date(d: date) -> str:
    """`13 September 2026` — long-form, unambiguous, no platform-specific
    strftime flags like %-d (D-15)."""
    return f"{d.day} {d:%B %Y}"
