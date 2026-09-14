"""
Parser tests (implementation.md P2 task 2.2), written before tools/parser.py.

Required cases from the Claude Code prompt in implementation.md:
"2 years from effective date"=24, "24 months", "two yrs", "perpetual";
"use today's date" -> derived, "1 October 2026" -> clear, "next quarter" -> None.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from tools.parser import Duration, ParsedDate, _add_months, format_long_date, parse_date, parse_duration


class TestParseDuration:
    def test_years_from_effective_date(self):
        assert parse_duration("2 years from effective date") == Duration(months=24, kind="fixed")

    def test_bare_months(self):
        assert parse_duration("24 months") == Duration(months=24, kind="fixed")

    def test_word_number_years(self):
        assert parse_duration("two yrs") == Duration(months=24, kind="fixed")

    def test_perpetual(self):
        assert parse_duration("perpetual") == Duration(months=None, kind="perpetual")

    def test_indefinite_synonym(self):
        assert parse_duration("indefinite") == Duration(months=None, kind="perpetual")

    def test_ten_years_out_of_range_but_parseable(self):
        assert parse_duration("10 years") == Duration(months=120, kind="fixed")

    def test_after_termination_phrasing(self):
        assert parse_duration("3 years after termination") == Duration(months=36, kind="fixed")

    def test_ambiguous_condition_returns_none(self):
        assert parse_duration("until the project is completed") is None

    def test_empty_returns_none(self):
        assert parse_duration("") is None
        assert parse_duration("   ") is None

    def test_word_numbers_one_through_ten(self):
        words = ["one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]
        for i, w in enumerate(words, start=1):
            assert parse_duration(f"{w} years") == Duration(months=i * 12, kind="fixed"), w

    def test_singular_year_and_month(self):
        assert parse_duration("1 year") == Duration(months=12, kind="fixed")
        assert parse_duration("1 month") == Duration(months=1, kind="fixed")

    def test_abbreviation_mos(self):
        assert parse_duration("6 mos") == Duration(months=6, kind="fixed")


class TestParseDate:
    def test_today_derived(self):
        result = parse_date("use today's date", "Asia/Kolkata")
        assert result is not None
        assert result.interpretation == "derived"
        # Deliberately re-derive "today" via the same timezone the parser was
        # told to use, not the test machine's local date (D-15) — this is
        # exactly the class of bug the timezone fix guards against.
        expected = datetime.now(ZoneInfo("Asia/Kolkata")).date()
        assert result.value == expected

    def test_today_derived_curly_apostrophe(self):
        result = parse_date("use today’s date", "Asia/Kolkata")
        assert result is not None
        assert result.interpretation == "derived"

    def test_sample_phrasing(self):
        result = parse_date("To be filled — use today's date", "Asia/Kolkata")
        assert result is not None
        assert result.interpretation == "derived"

    def test_bare_today(self):
        result = parse_date("today", "Asia/Kolkata")
        assert result is not None
        assert result.interpretation == "derived"

    def test_tomorrow_derived(self):
        # D-73: "tomorrow" is just as unambiguous as "today" — resolve it,
        # don't leave it for a human to guess.
        result = parse_date("tomorrow", "Asia/Kolkata")
        assert result is not None
        assert result.interpretation == "derived"
        expected = datetime.now(ZoneInfo("Asia/Kolkata")).date() + timedelta(days=1)
        assert result.value == expected

    def test_day_after_tomorrow_derived(self):
        result = parse_date("day after tomorrow", "Asia/Kolkata")
        assert result is not None
        assert result.interpretation == "derived"
        expected = datetime.now(ZoneInfo("Asia/Kolkata")).date() + timedelta(days=2)
        assert result.value == expected

    def test_day_after_tomorrow_not_mistaken_for_tomorrow(self):
        # "day after tomorrow" contains "tomorrow" as a substring — must not
        # be caught by the bare-"tomorrow" pattern with the wrong offset.
        tomorrow = parse_date("tomorrow", "Asia/Kolkata")
        day_after = parse_date("day after tomorrow", "Asia/Kolkata")
        assert day_after.value == tomorrow.value + timedelta(days=1)

    def test_n_days_after_today_not_mistaken_for_bare_today(self):
        # D-74, found live: "three days after today" contains the bare word
        # "today" as a substring — it was matching _TODAY_PATTERN and
        # silently resolving to *today's* date, discarding "three days
        # after" entirely. Must honor the numeric offset.
        result = parse_date("three days after today", "Asia/Kolkata")
        assert result is not None
        assert result.interpretation == "derived"
        today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
        assert result.value == today + timedelta(days=3)

    def test_n_days_after_today_digit_form(self):
        result = parse_date("5 days after today", "Asia/Kolkata")
        today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
        assert result.value == today + timedelta(days=5)

    def test_n_days_before_today(self):
        result = parse_date("2 days before today", "Asia/Kolkata")
        today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
        assert result.value == today - timedelta(days=2)

    def test_n_days_from_today(self):
        result = parse_date("four days from today", "Asia/Kolkata")
        today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
        assert result.value == today + timedelta(days=4)

    def test_in_n_days(self):
        result = parse_date("in ten days", "Asia/Kolkata")
        today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
        assert result.value == today + timedelta(days=10)

    def test_explicit_day_month_year(self):
        result = parse_date("1 October 2026", "Asia/Kolkata")
        assert result == ParsedDate(value=date(2026, 10, 1), interpretation="clear")

    def test_explicit_month_day_year(self):
        result = parse_date("October 1, 2026", "Asia/Kolkata")
        assert result == ParsedDate(value=date(2026, 10, 1), interpretation="clear")

    def test_iso_format(self):
        result = parse_date("2026-10-01", "Asia/Kolkata")
        assert result == ParsedDate(value=date(2026, 10, 1), interpretation="clear")

    def test_ordinal_day(self):
        result = parse_date("21st October 2026", "Asia/Kolkata")
        assert result == ParsedDate(value=date(2026, 10, 21), interpretation="clear")

    def test_ambiguous_returns_none(self):
        assert parse_date("next quarter", "Asia/Kolkata") is None

    def test_empty_returns_none(self):
        assert parse_date("", "Asia/Kolkata") is None

    def test_invalid_calendar_date_returns_none(self):
        assert parse_date("31 February 2026", "Asia/Kolkata") is None


class TestRelativeDateGrammar:
    """D-76: the compositional grammar (Anchor + Offset) that replaced
    per-phrase pattern matching after tomorrow/day-after-tomorrow/N-days
    each broke in a new way when tested live. These tests cover the class
    of phrase, not just the one that happened to be tried."""

    TZ = "Asia/Kolkata"

    def _today(self):
        return datetime.now(ZoneInfo(self.TZ)).date()

    # -- the exact regression that prompted this rewrite --------------

    def test_n_months_from_tomorrow_composes_correctly(self):
        # "2 months from tomorrow" was resolving to just "tomorrow" — the
        # bare _TOMORROW_PATTERN matched the substring and silently
        # dropped "2 months from" entirely.
        result = parse_date("2 months from tomorrow", self.TZ)
        assert result is not None
        assert result.interpretation == "derived"
        expected = _add_months(self._today() + timedelta(days=1), 2)
        assert result.value == expected
        assert result.value != self._today() + timedelta(days=1)

    # -- weeks --------------------------------------------------------

    def test_n_weeks_after_today(self):
        result = parse_date("2 weeks after today", self.TZ)
        assert result.value == self._today() + timedelta(weeks=2)

    def test_n_weeks_from_tomorrow(self):
        result = parse_date("3 weeks from tomorrow", self.TZ)
        assert result.value == self._today() + timedelta(days=1) + timedelta(weeks=3)

    def test_in_n_weeks(self):
        result = parse_date("in two weeks", self.TZ)
        assert result.value == self._today() + timedelta(weeks=2)

    def test_n_weeks_ago(self):
        result = parse_date("2 weeks ago", self.TZ)
        assert result.value == self._today() - timedelta(weeks=2)

    # -- months ---------------------------------------------------------

    def test_n_months_after_today(self):
        result = parse_date("3 months after today", self.TZ)
        assert result.value == _add_months(self._today(), 3)

    def test_in_n_months(self):
        result = parse_date("in 2 months", self.TZ)
        assert result is not None
        assert result.interpretation == "derived"
        assert result.value == _add_months(self._today(), 2)

    def test_n_months_ago(self):
        result = parse_date("6 months ago", self.TZ)
        assert result.value == _add_months(self._today(), -6)

    def test_word_number_months(self):
        result = parse_date("three months from today", self.TZ)
        assert result.value == _add_months(self._today(), 3)

    # -- years ----------------------------------------------------------

    def test_n_years_after_today(self):
        result = parse_date("1 year after today", self.TZ)
        assert result.value == _add_months(self._today(), 12)

    def test_in_n_years(self):
        result = parse_date("in 2 years", self.TZ)
        assert result.value == _add_months(self._today(), 24)

    # -- composability across all four anchors ---------------------------

    def test_days_before_day_after_tomorrow(self):
        result = parse_date("1 day before day after tomorrow", self.TZ)
        # day after tomorrow, minus 1 day, == tomorrow
        assert result.value == self._today() + timedelta(days=1)

    def test_yesterday_anchor(self):
        result = parse_date("yesterday", self.TZ)
        assert result is not None
        assert result.interpretation == "derived"
        assert result.value == self._today() - timedelta(days=1)

    def test_n_days_after_yesterday(self):
        result = parse_date("2 days after yesterday", self.TZ)
        # yesterday + 2 days == tomorrow
        assert result.value == self._today() + timedelta(days=1)

    # -- month-end calendar arithmetic (direct, not date-dependent) ------

    def test_add_months_clamps_to_shorter_month(self):
        assert _add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)  # 2026 not a leap year

    def test_add_months_leap_year(self):
        assert _add_months(date(2024, 1, 31), 1) == date(2024, 2, 29)

    def test_add_months_crosses_year_boundary(self):
        assert _add_months(date(2026, 11, 15), 2) == date(2027, 1, 15)

    def test_add_months_negative_crosses_year_boundary(self):
        assert _add_months(date(2026, 1, 15), -2) == date(2025, 11, 15)

    # -- genuinely ambiguous phrases must still return None --------------

    def test_next_week_is_still_ambiguous(self):
        # "next week" has no single fixed date (which day of next week?) —
        # must stay a human-review case, not a guess.
        assert parse_date("next week", self.TZ) is None

    def test_next_business_day_is_still_ambiguous(self):
        assert parse_date("next business day", self.TZ) is None

    def test_bare_unit_without_number_is_ambiguous(self):
        assert parse_date("next month", self.TZ) is None


class TestFormatLongDate:
    def test_format(self):
        assert format_long_date(date(2026, 9, 13)) == "13 September 2026"

    def test_no_leading_zero_padding(self):
        assert format_long_date(date(2026, 1, 5)) == "5 January 2026"
