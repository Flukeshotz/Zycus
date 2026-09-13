"""
Parser tests (implementation.md P2 task 2.2), written before tools/parser.py.

Required cases from the Claude Code prompt in implementation.md:
"2 years from effective date"=24, "24 months", "two yrs", "perpetual";
"use today's date" -> derived, "1 October 2026" -> clear, "next quarter" -> None.
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from tools.parser import Duration, ParsedDate, format_long_date, parse_date, parse_duration


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


class TestFormatLongDate:
    def test_format(self):
        assert format_long_date(date(2026, 9, 13)) == "13 September 2026"

    def test_no_leading_zero_padding(self):
        assert format_long_date(date(2026, 1, 5)) == "5 January 2026"
