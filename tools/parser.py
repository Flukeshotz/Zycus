"""
Deterministic parser (architecture.md §3 #6, D-15).

Two jobs, both intentionally conservative — returning None (i.e. "I can't
confidently parse this") is always safe, because the router treats an
unparseable value as ambiguous (G8) or a cross-check mismatch (G9), which
routes to a human. A wrong guess would be unsafe; None never is.

  parse_duration(text)  -> a whole number of months, or "perpetual"
  parse_date(text, tz)  -> a relative date reference, resolved by a small
                           compositional grammar (see the "Dates" section
                           below) in a fixed timezone, or an explicit
                           calendar date

Used two ways (D-46): as the Normalizer's deterministic cross-check in every
mode (G9), and as the entire "Normalizer" in FakeLLM / degraded mode, since
these are exactly the patterns simple enough not to need an LLM at all.
"""
from __future__ import annotations

import calendar
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
#
# Relative dates are handled by one compositional grammar, not a growing
# list of hand-matched phrases (D-73 → D-76: each new phrase tested live —
# "tomorrow", then "N days after today", then "in 2 months", then "2 months
# from tomorrow" — broke the previous fix's pattern-matching in a new way).
#
#   Anchor := today | tomorrow | day after tomorrow | yesterday
#   Offset := <number> (days|weeks|months|years) (before|after|from) Anchor
#           | in <number> (days|weeks|months|years)        [anchor = today]
#           | <number> (days|weeks|months|years) ago        [anchor = today,
#                                                              direction = before]
#
# Every phrase in this grammar has exactly one correct date — that is the
# line D-15 draws: resolve anything with a single unambiguous answer, defer
# anything without one ("next week", "next quarter", "once signed" — which
# day? which quarter?) to a human via G8_ambiguity. This is not "parse all
# of English" (unbounded, and therefore unsafe to guess on) — it is the
# complete, bounded set of expressions that are safe to auto-resolve.

_UNIT_ALTERNATION = r"days?|weeks?|months?|years?"

# Longest/most-specific anchor first: "day after tomorrow" must win over
# "tomorrow" wherever both could start matching.
_ANCHOR_ALTERNATION = r"day\s+after\s+tomorrow|tomorrow|yesterday|today"
_ANCHOR_OFFSET_DAYS = {"day after tomorrow": 2, "tomorrow": 1, "yesterday": -1, "today": 0}

# Composable: "N <unit> before/after/from <anchor>", e.g. "2 months from
# tomorrow". Checked before every bare-anchor pattern below — "tomorrow"
# alone is a substring of this phrase and would otherwise silently swallow
# the numeric offset (the exact class of bug D-74/D-75 fixed for the
# today-only case; this generalizes the fix instead of patching each new
# phrase found live).
_OFFSET_FROM_ANCHOR_PATTERN = re.compile(
    rf"\b(?P<num>{_NUMBER_ALTERNATION})\s+(?P<unit>{_UNIT_ALTERNATION})\s+"
    rf"(?P<dir>before|after|from)\s+(?P<anchor>{_ANCHOR_ALTERNATION})\b",
    re.I,
)
_UNITS_AGO_PATTERN = re.compile(
    rf"\b(?P<num>{_NUMBER_ALTERNATION})\s+(?P<unit>{_UNIT_ALTERNATION})\s+ago\b", re.I
)
_IN_N_UNITS_PATTERN = re.compile(
    rf"\bin\s+(?P<num>{_NUMBER_ALTERNATION})\s+(?P<unit>{_UNIT_ALTERNATION})\b", re.I
)
# Bare anchor — least specific, checked last. Straight (') and curly (’)
# apostrophes both accepted — live LLM output or UI typing may use either.
_BARE_ANCHOR_PATTERN = re.compile(
    rf"\b({_ANCHOR_ALTERNATION}|use\s+today[’']?s\s+date|to\s+be\s+filled.*?today|current\s+date)\b",
    re.I,
)


def _to_int(raw: str) -> int | None:
    raw = raw.lower()
    if raw in _WORD_NUMBERS:
        return _WORD_NUMBERS[raw]
    try:
        return int(raw)
    except ValueError:
        return None


def _add_months(base: date, months: int) -> date:
    """Calendar-correct month arithmetic, clamping to the target month's
    last valid day (e.g. 31 Jan + 1 month -> 28/29 Feb, never a ValueError)."""
    month_index = base.month - 1 + months
    year = base.year + month_index // 12
    month = month_index % 12 + 1
    day = min(base.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _apply_offset(base: date, n: int, unit: str, sign: int) -> date:
    unit = unit.lower()
    if unit.startswith("day"):
        return base + timedelta(days=sign * n)
    if unit.startswith("week"):
        return base + timedelta(weeks=sign * n)
    if unit.startswith("month"):
        return _add_months(base, sign * n)
    return _add_months(base, sign * n * 12)  # year


def _anchor_date(anchor_text: str, today: date) -> date:
    normalized = re.sub(r"\s+", " ", anchor_text.strip().lower())
    if normalized in _ANCHOR_OFFSET_DAYS:
        return today + timedelta(days=_ANCHOR_OFFSET_DAYS[normalized])
    # Only reachable from _BARE_ANCHOR_PATTERN's extra "today" synonyms
    # ("use today's date", "to be filled ... today", "current date"), which
    # aren't in _ANCHOR_OFFSET_DAYS because they never appear as an anchor
    # inside _OFFSET_FROM_ANCHOR_PATTERN — only as a standalone phrase.
    return today


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
    Resolve a relative date reference to a concrete date in `tz`
    (interpretation="derived") via the compositional grammar documented
    above the pattern definitions, or parse an explicit calendar date
    (interpretation="clear"). Returns None for anything else, including an
    invalid calendar date (e.g. "31 February") or a genuinely ambiguous
    relative phrase (e.g. "next quarter", "next week") that has no single
    safe fixed offset.
    """
    if not text or not text.strip():
        return None
    stripped = text.strip()
    today = datetime.now(ZoneInfo(tz)).date()

    # Most specific patterns first — each of these contains a bare anchor
    # word ("today"/"tomorrow"/...) as a substring and must not fall into
    # the bare-anchor pattern below, which would silently discard the
    # numeric offset (D-74/D-75: found live, twice, before this grammar
    # replaced per-phrase matching).
    if m := _OFFSET_FROM_ANCHOR_PATTERN.search(stripped):
        n = _to_int(m.group("num"))
        if n is not None:
            sign = -1 if m.group("dir").lower() == "before" else 1
            base = _anchor_date(m.group("anchor"), today)
            return ParsedDate(
                value=_apply_offset(base, n, m.group("unit"), sign), interpretation="derived"
            )

    if m := _UNITS_AGO_PATTERN.search(stripped):
        n = _to_int(m.group("num"))
        if n is not None:
            return ParsedDate(
                value=_apply_offset(today, n, m.group("unit"), -1), interpretation="derived"
            )

    if m := _IN_N_UNITS_PATTERN.search(stripped):
        n = _to_int(m.group("num"))
        if n is not None:
            return ParsedDate(
                value=_apply_offset(today, n, m.group("unit"), 1), interpretation="derived"
            )

    if m := _BARE_ANCHOR_PATTERN.search(stripped):
        return ParsedDate(value=_anchor_date(m.group(1), today), interpretation="derived")

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
