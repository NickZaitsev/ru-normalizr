import re
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from ru_normalizr.dates_time import (
    _day_to_ordinal,
    _day_to_ordinal_genitive,
    normalize_dates,
    normalize_time,
)
from ru_normalizr.numerals._helpers import (
    apply_genitive_plural_heuristic,
    safe_inflect,
    should_consume_abbreviation_dot,
    should_keep_decimal_unit_dot,
    should_keep_tokenized_decimal_unit_dot,
)
from ru_normalizr.numerals.fractions import normalize_fractions
from ru_normalizr.ordinal_utils import (
    normalize_ordinal_suffix_defaults,
    render_ordinal,
)
from ru_normalizr.years import (
    _normalize_era_marker,
    normalize_numeric_ranges,
    normalize_years,
    year_to_ordinal_words,
)
from ru_normalizr.years_context import (
    _consume_following_number,
    _is_non_year_following_token,
    should_treat_as_implicit_year,
)


class FractionBranchTests(unittest.TestCase):
    def test_fraction_cases_and_numerator_boundaries(self):
        cases = (
            ("с 1/4", "с одной четвёртой"),
            ("к 2/3", "к двум третьим"),
            ("в 3/5", "в три пятых"),
            ("о 5/8", "о пяти восьмых"),
            ("11/2", "одиннадцать вторых"),
            ("12/7", "двенадцать седьмых"),
            ("21/100", "двадцать одна сотая"),
            ("22/100", "двадцать две сотых"),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(normalize_fractions(source), expected)

    def test_fraction_preserves_source_when_numerator_rendering_fails(self):
        with patch(
            "ru_normalizr.numerals.fractions.num2words.num2words",
            side_effect=RuntimeError("backend unavailable"),
        ):
            self.assertEqual(normalize_fractions("3/5"), "3/5")

    def test_fraction_preserves_source_when_denominator_rendering_fails(self):
        real_num2words = __import__("num2words").num2words

        def fail_for_ordinal(number, **kwargs):
            if kwargs.get("to") == "ordinal":
                raise RuntimeError("ordinal backend unavailable")
            return real_num2words(number, **kwargs)

        with patch(
            "ru_normalizr.numerals.fractions.num2words.num2words",
            side_effect=fail_for_ordinal,
        ):
            self.assertEqual(normalize_fractions("3/5"), "3/5")


class NumeralHelperBranchTests(unittest.TestCase):
    def test_genitive_plural_heuristic_covers_supported_adjective_endings(self):
        cases = (
            ("слово", "NOUN", "слово"),
            ("новые", "ADJF", "новых"),
            ("синие", "ADJF", "синих"),
            ("новый", "ADJF", "нового"),
            ("синий", "ADJF", "синего"),
            ("новая", "ADJF", "новой"),
            ("синяя", "ADJF", "синей"),
            ("краткое", "ADJF", "краткое"),
        )
        for word, pos, expected in cases:
            with self.subTest(word=word):
                self.assertEqual(
                    apply_genitive_plural_heuristic(word, pos),
                    expected,
                )

    def test_safe_inflect_uses_result_heuristic_and_fallback(self):
        class FakeParse:
            def __init__(self, word, pos, result=None, error=None):
                self.word = word
                self.tag = SimpleNamespace(POS=pos)
                self.result = result
                self.error = error

            def inflect(self, _target_tags):
                if self.error is not None:
                    raise self.error
                return (
                    SimpleNamespace(word=self.result)
                    if self.result is not None
                    else None
                )

        self.assertEqual(
            safe_inflect(FakeParse("новые", "ADJF", result="готовых"), {"gent"}),
            "готовых",
        )
        self.assertEqual(
            safe_inflect(FakeParse("новые", "ADJF"), {"gent", "plur"}),
            "новых",
        )
        self.assertEqual(
            safe_inflect(
                FakeParse("новые", "ADJF", error=RuntimeError("cannot inflect")),
                {"gent", "plur"},
            ),
            "новых",
        )
        self.assertEqual(
            safe_inflect(
                FakeParse("дом", "NOUN"),
                {"gent", "plur"},
                fallback_word="резерв",
            ),
            "резерв",
        )

    def test_abbreviation_and_decimal_dot_boundaries(self):
        consume_cases = (
            (["кг"], 0, False),
            (["кг", "."], 1, False),
            (["кг", ".", "\n"], 1, False),
            (["кг", ".", ","], 1, True),
            (["кг", ".", ""], 1, False),
            (["кг", ".", "слово"], 1, True),
            (["кг", ".", "2"], 1, True),
            (["кг", ".", "Слово"], 1, False),
        )
        for tokens, index, expected in consume_cases:
            with self.subTest(tokens=tokens):
                self.assertEqual(
                    should_consume_abbreviation_dot(tokens, index),
                    expected,
                )

        decimal_cases = (
            ("", True),
            (" \nслово", True),
            (" ! слово", True),
            (" слово", False),
            (" 2", False),
            (" Слово", True),
        )
        for rest, expected in decimal_cases:
            with self.subTest(rest=rest):
                self.assertEqual(should_keep_decimal_unit_dot(rest), expected)

        tokenized_cases = (
            (["", "\n"], True),
            (["!"], True),
            (["слово"], False),
            (["2"], False),
            (["Слово"], True),
            ([], True),
        )
        for tokens, expected in tokenized_cases:
            with self.subTest(tokens=tokens):
                self.assertEqual(
                    should_keep_tokenized_decimal_unit_dot(tokens, 0),
                    expected,
                )


class DateTimeBranchTests(unittest.TestCase):
    def test_day_ordinal_bounds_and_backend_failures(self):
        self.assertIsNone(_day_to_ordinal(0))
        self.assertIsNone(_day_to_ordinal_genitive(32))

        with patch(
            "ru_normalizr.dates_time.num2words.num2words",
            side_effect=RuntimeError("backend unavailable"),
        ):
            self.assertIsNone(_day_to_ordinal(5))
            self.assertIsNone(_day_to_ordinal_genitive(5))

    def test_numeric_date_guards_and_two_digit_year_boundaries(self):
        self.assertEqual(normalize_dates("32.13.2020"), "32.13.2020")
        self.assertEqual(
            normalize_dates("01.02.49"),
            "первого февраля две тысячи сорок девятого года",
        )
        self.assertEqual(
            normalize_dates("01.02.50"),
            "первого февраля тысяча девятьсот пятидесятого года",
        )

    def test_time_fallbacks_preserve_information(self):
        with patch(
            "ru_normalizr.dates_time.num2words.num2words",
            side_effect=RuntimeError("backend unavailable"),
        ):
            self.assertEqual(normalize_time("10:07"), "10, ноль 7")
            self.assertEqual(normalize_time("10:17"), "10, 17")
            self.assertEqual(normalize_time("10:07:30"), "10:07:30")


class OrdinalUtilityBranchTests(unittest.TestCase):
    def test_suffix_defaults_cover_gender_case_and_plural_forms(self):
        cases = (
            ("я", ("nomn", "femn", False)),
            ("ое", ("nomn", "neut", False)),
            ("ые", ("nomn", None, True)),
            ("го", ("gent", "masc", False)),
            ("му", ("datv", "masc", False)),
            ("м", ("loct", "masc", False)),
            ("ую", ("accs", "femn", False)),
            ("ей", ("loct", "femn", False)),
            ("ым", ("ablt", "masc", False)),
            ("й", ("nomn", "masc", False)),
        )
        for suffix, expected in cases:
            with self.subTest(suffix=suffix):
                self.assertEqual(
                    normalize_ordinal_suffix_defaults("nomn", suffix),
                    expected,
                )

    def test_ordinal_fallback_inflects_untyped_backend_result(self):
        real_num2words = __import__("num2words").num2words

        def fail_case_aware_call(number, **kwargs):
            if "case" in kwargs:
                raise RuntimeError("case-aware call failed")
            return real_num2words(number, **kwargs)

        with patch(
            "ru_normalizr.ordinal_utils.num2words.num2words",
            side_effect=fail_case_aware_call,
        ):
            self.assertEqual(render_ordinal(5, gender=None), "пятый")

    def test_ordinal_fallback_handles_backend_and_parse_failures(self):
        with patch(
            "ru_normalizr.ordinal_utils.num2words.num2words",
            side_effect=RuntimeError("backend unavailable"),
        ):
            self.assertEqual(render_ordinal(5, gender=None), "5")

        with (
            patch(
                "ru_normalizr.ordinal_utils.num2words.num2words",
                side_effect=[RuntimeError("case-aware call failed"), ""],
            ),
            patch("ru_normalizr.ordinal_utils.parse_word", return_value=()),
        ):
            self.assertEqual(render_ordinal(5, gender=None), "")


class YearContextBranchTests(unittest.TestCase):
    explicit_year_word = re.compile(r"\s+г(?:од)?")
    year_suffix = re.compile(r"-х")

    def test_following_number_consumes_grouped_thousands(self):
        self.assertEqual(_consume_following_number([], 0), (None, 0))
        self.assertEqual(
            _consume_following_number(["10", "000", "000", "кг"], 0),
            ("10000000", 3),
        )

    def test_implicit_year_context_boundaries(self):
        cases = (
            ("-х", False),
            (" год", False),
            ("", True),
            (" до 1995", False),
            (" до 10000", False),
            (" до 9 кг", False),
            (" до девяти", True),
            (" кг", False),
            (" событие", True),
        )
        for tail, expected in cases:
            with self.subTest(tail=tail):
                self.assertEqual(
                    should_treat_as_implicit_year(
                        tail,
                        0,
                        explicit_year_word_pattern=self.explicit_year_word,
                        year_suffix_tail_pattern=self.year_suffix,
                    ),
                    expected,
                )

    def test_unknown_unparsed_token_is_not_a_non_year_marker(self):
        with patch("ru_normalizr.years_context.parse_word", return_value=()):
            self.assertFalse(_is_non_year_following_token("неизвестно"))


class YearBranchTests(unittest.TestCase):
    def test_era_markers_are_normalized_only_for_supported_spellings(self):
        cases = (
            ("BC", "до нашей эры"),
            ("B.C.E.", "до нашей эры"),
            ("AD", "нашей эры"),
            ("C.E.", "нашей эры"),
            ("до н. э.", "до нашей эры"),
            ("н. э.", "нашей эры"),
            ("до нашей эры", "до нашей эры"),
            ("нашей эры", "нашей эры"),
            ("неизвестная эра", None),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(_normalize_era_marker(source), expected)

    def test_year_patterns_cover_eras_suffixes_lists_and_parentheses(self):
        cases = (
            ("без чисел", "без чисел"),
            ("44 года", "44 года"),
            ("в 44 году", "в сорок четвёртом году"),
            (
                "в 1999, 2000 и 2001 годах",
                "в тысяча девятьсот девяносто девятом, двухтысячном и две тысячи первом годах",
            ),
            ("44 г. до н. э.", "сорок четвёртый год до нашей эры."),
            ("44 до н. э.", "сорок четвёртый год до нашей эры."),
            (
                "с 44 по 45 до н. э.",
                "с сорок четвёртого по сорок пятый год до нашей эры.",
            ),
            (
                "44-45 до н. э.",
                "сорок четвёртый — сорок пятый год до нашей эры.",
            ),
            ("44 BCE.", "сорок четвёртый год до нашей эры."),
            (
                "44 BCE. Затем",
                "сорок четвёртый год до нашей эры. Затем",
            ),
            (
                "44 BCE. дальше",
                "сорок четвёртый год до нашей эры дальше",
            ),
            (
                "44 BCE.\nДальше",
                "сорок четвёртый год до нашей эры.\nДальше",
            ),
            ("44 AD.", "сорок четвёртый год нашей эры."),
            (
                "события (1990)",
                "события (одна тысяча девятьсот девяносто)",
            ),
            (
                "под номером (1990)",
                "под номером (тысяча девятьсот девяностый)",
            ),
            ("при дворе [2001]", "при дворе [две тысячи первый]"),
            ("(999)", "(999)"),
            ("в 1980-х", "в тысяча девятьсот восьмидесятых"),
            ("с 1980-х", "с тысяча девятьсот восьмидесятых"),
            ("к 1980-м", "к тысяча девятьсот восьмидесятым"),
            ("6301-х", "6301-х"),
            ("80-х", "80-х"),
            ("80-х годах", "восьмидесятых годах"),
            ("1980-го года", "тысяча девятьсот восьмидесятого года"),
            ("в 1980-м году", "в тысяча девятьсот восьмидесятом году"),
            (
                "1990-1995 годы",
                "тысяча девятьсот девяностые — тысяча девятьсот девяносто пятые годы",
            ),
            (
                "1990-1995 гг.",
                "с тысяча девятьсот девяностого по тысяча девятьсот девяносто пятый год.",
            ),
            (
                "из 1990-1995 годов",
                "из тысяча девятьсот девяностых — тысяча девятьсот девяносто пятых годов",
            ),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(normalize_years(source), expected)

    def test_large_year_uses_cardinal_high_part_and_ordinal_tail(self):
        self.assertEqual(
            year_to_ordinal_words(12345, "gent"),
            "двенадцати тысяч триста сорок пятого",
        )

    def test_year_rendering_falls_back_to_digits_when_backend_fails(self):
        year_to_ordinal_words.cache_clear()
        with patch(
            "ru_normalizr.years.num2words.num2words",
            side_effect=RuntimeError("backend unavailable"),
        ):
            self.assertEqual(year_to_ordinal_words(12345, "gent"), "12345")
        year_to_ordinal_words.cache_clear()

    def test_numeric_range_guard_skips_measurements(self):
        self.assertEqual(
            normalize_numeric_ranges("10—20; 30–40 кг"),
            "10, 20; 30–40 кг",
        )


if __name__ == "__main__":
    unittest.main()
