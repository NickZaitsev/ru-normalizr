import re
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from ru_normalizr import NormalizeOptions
from ru_normalizr.abbreviation_context import (
    allows_short_abbreviated_year,
    has_mass_measurement_context,
    should_keep_terminal_abbreviation_dot,
)
from ru_normalizr.dates_time import (
    _day_to_ordinal,
    _day_to_ordinal_genitive,
    normalize_dates,
    normalize_time,
)
from ru_normalizr.numbering import (
    convert_bracketed_numbers,
    convert_numeric_sequence,
    num_to_word,
    roman_to_word,
)
from ru_normalizr.numerals import _helpers
from ru_normalizr.numerals._helpers import (
    apply_genitive_plural_heuristic,
    inflect_numeral_string,
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
from ru_normalizr.urls import normalize_urls
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


class AbbreviationContextBranchTests(unittest.TestCase):
    def test_terminal_abbreviation_dot_uses_following_text_context(self):
        cases = (
            ("Отчёт 5 г.", True),
            ("Отчёт 5 г. Далее", True),
            ("Отчёт 5 г. далее", False),
            ("Отчёт 5 г.\nДалее", True),
            ("Отчёт 5 г.!", True),
            ('Отчёт 5 г. "Далее', True),
            ('Отчёт 5 г. "далее', False),
            ('Отчёт 5 г. "', True),
        )
        marker = " 5 г."
        for source, expected in cases:
            with self.subTest(source=source):
                match_end = source.index(marker) + len(marker)
                self.assertEqual(
                    should_keep_terminal_abbreviation_dot(source, match_end), expected
                )

    def test_short_year_abbreviation_requires_a_birth_context_without_preposition(self):
        cases = (
            ("55 г.", None, False),
            ("55 г. рождения", None, True),
            ("55 г. назад", None, False),
            ("55 г. 2020", None, False),
            ("в 55 г.", "в", True),
        )
        for source, prep, expected in cases:
            with self.subTest(source=source, prep=prep):
                self.assertEqual(
                    allows_short_abbreviated_year(
                        source, source.index("г.") + len("г."), prep
                    ),
                    expected,
                )

    def test_mass_abbreviation_requires_a_recent_weight_noun(self):
        cases = (
            ("Вес 123 г.", True),
            ("Масса образца 237 г.", True),
            ("Скорость 123 г.", False),
            ("Взвешивание образца 123 г.", False),
            ("Показатель @@@ 123 г.", False),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                number_start = source.rindex("123") if "123" in source else source.rindex("237")
                self.assertEqual(
                    has_mass_measurement_context(source, number_start), expected
                )


class NumberingBranchTests(unittest.TestCase):
    def test_numbering_fallbacks_preserve_input_when_backends_cannot_render(self):
        with patch(
            "ru_normalizr.numbering.num2words.num2words",
            side_effect=RuntimeError("backend unavailable"),
        ):
            self.assertEqual(num_to_word(7), "7")
        self.assertEqual(roman_to_word("IIII"), "IIII")

    def test_numeric_sequence_keeps_non_numeric_segments_in_order(self):
        self.assertEqual(
            convert_numeric_sequence("12.abc"), "двенадцать точка abc"
        )
        self.assertEqual(convert_numeric_sequence("I.2"), "I точка два")

    def test_bracketed_reference_removal_respects_inclusive_ignore_interval(self):
        options = NormalizeOptions.tts(remove_links_ignore_interval=(10, 20))
        self.assertEqual(
            convert_bracketed_numbers("Текст [1] [10] [20] [21].", options),
            "Текст  [10] [20] .",
        )
        self.assertEqual(convert_bracketed_numbers("Текст [IV].", options), "Текст .")
        self.assertEqual(convert_bracketed_numbers("Текст [²].", options), "Текст .")
        self.assertEqual(
            convert_bracketed_numbers("Текст (1] {2}.", options), "Текст (1] ."
        )


class UrlBranchTests(unittest.TestCase):
    def test_url_stage_keeps_unbalanced_closers_with_trailing_punctuation(self):
        self.assertEqual(
            normalize_urls("Смотри https://example.org/path).", enabled=True),
            "Смотри https двоеточие слэш слэш example точка org слэш path).",
        )

    def test_url_stage_keeps_balanced_closers_inside_the_url(self):
        self.assertEqual(
            normalize_urls("Смотри https://example.org/(path).", enabled=True),
            "Смотри https двоеточие слэш слэш example точка org слэш ( path ).",
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


class NumeralInflectionCaseTests(unittest.TestCase):
    """Case handling in ``inflect_numeral_string``.

    pymorphy reports secondary cases for the nouns that have them (partitive
    "чаю", locative "в лесу", vocative "Пап!") and call sites pass that case
    straight through. Numerals have no such forms, so each secondary case must
    be read as its primary one before rendering.
    """

    def setUp(self) -> None:
        inflect_numeral_string.cache_clear()
        self.addCleanup(inflect_numeral_string.cache_clear)

    def test_non_numeric_input_is_returned_unchanged(self):
        self.assertEqual(inflect_numeral_string("не число", "gent"), "не число")

    def test_secondary_case_renders_as_its_primary_case(self):
        numbers = ("21", "1000", "2000", "5000", "2000000")
        equivalences = (
            ("gen1", "gent"),
            ("gen2", "gent"),
            ("loc1", "loct"),
            ("loc2", "loct"),
            ("acc2", "accs"),
            ("voct", "nomn"),
        )
        for secondary, primary in equivalences:
            for number in numbers:
                with self.subTest(case=secondary, number=number):
                    self.assertEqual(
                        inflect_numeral_string(number, secondary),
                        inflect_numeral_string(number, primary),
                    )

    def test_vocative_keeps_the_nominative_wording(self):
        # Regression: asking pymorphy for {voct} made it answer with an
        # arbitrary matching form, so "пять тысяч" came back as "пять тысячи".
        self.assertEqual(inflect_numeral_string("5000", "voct"), "пять тысяч")
        self.assertEqual(inflect_numeral_string("2000000", "voct"), "два миллиона")


class NumeralInflectionFallbackTests(unittest.TestCase):
    """The pymorphy fallback inside ``inflect_numeral_string``.

    ``num2words`` renders every case directly. The fallback below it only runs
    when num2words raises — a real risk, since the dependency has no upper
    version bound. It is the last line of defence against a crash on arbitrary
    text, so its output is pinned here rather than left to chance.
    """

    def setUp(self) -> None:
        inflect_numeral_string.cache_clear()
        self.addCleanup(inflect_numeral_string.cache_clear)

    def _without_case_support(self):
        """Patch num2words so only the plain nominative call succeeds."""
        real_num2words = _helpers.num2words.num2words

        def only_positional(value, **kwargs):
            if kwargs.get("case"):
                raise ValueError("case is not supported by this release")
            return real_num2words(value, lang="ru")

        return patch.object(
            _helpers.num2words, "num2words", side_effect=only_positional
        )

    def test_fallback_inflects_the_unit_word(self):
        with self._without_case_support():
            self.assertEqual(inflect_numeral_string("21", "gent"), "двадцати одного")

    def test_fallback_agrees_the_unit_word_with_the_magnitude_gender(self):
        # "тысяча" is feminine and "миллион" masculine, so the unit word takes
        # the magnitude's gender rather than the requested one.
        cases = (
            ("1000", "одной тысячи"),
            ("1000000", "одного миллиона"),
            ("1000000000", "одного миллиарда"),
            ("1000000000000", "одного триллиона"),
        )
        with self._without_case_support():
            for number, expected in cases:
                with self.subTest(number=number):
                    self.assertEqual(inflect_numeral_string(number, "gent"), expected)

    def test_fallback_puts_the_magnitude_in_the_plural_when_its_group_requires_it(self):
        # In an oblique case the whole phrase inflects, so the magnitude noun
        # follows its own group: 1000 stays singular, 2000 goes plural, and
        # 21000 is singular again because its group ends in one. Without this
        # the noun kept the singular and produced "двух тысячи".
        cases = (
            ("1000", "gent", "одной тысячи"),
            ("2000", "gent", "двух тысяч"),
            ("5000", "gent", "пяти тысяч"),
            ("21000", "gent", "двадцати одной тысячи"),
            ("2000", "loct", "двух тысячах"),
            ("2000", "datv", "двум тысячам"),
            ("2000", "ablt", "двумя тысячами"),
            ("2000000", "gent", "двух миллионов"),
            ("2000000000000", "gent", "двух триллионов"),
            ("2500", "gent", "двух тысяч пятисот"),
        )
        with self._without_case_support():
            for number, case, expected in cases:
                with self.subTest(number=number, case=case):
                    self.assertEqual(inflect_numeral_string(number, case), expected)

    def test_total_num2words_failure_preserves_the_digits(self):
        with patch.object(
            _helpers.num2words,
            "num2words",
            side_effect=RuntimeError("backend is broken"),
        ):
            self.assertEqual(inflect_numeral_string("2500", "gent"), "2500")


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
