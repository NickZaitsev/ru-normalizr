"""Branch coverage for the year stage: cases, decades, ranges, eras, fallbacks.

`normalize_years` is called directly so the case and number decisions stay
visible: `finalize` later fixes capitalization and collapses the dots this stage
emits, which would hide exactly what is under test here.
"""

import unittest
from unittest.mock import patch

import num2words

from ru_normalizr.years import (
    normalize_numeric_ranges,
    normalize_years,
    year_to_ordinal_words,
)


def years(text: str) -> str:
    return normalize_years(text)


class YearOrdinalWordsTests(unittest.TestCase):
    def setUp(self) -> None:
        year_to_ordinal_words.cache_clear()
        self.addCleanup(year_to_ordinal_words.cache_clear)

    def test_each_case_renders_its_own_ordinal_form(self):
        cases = (
            ("nomn", "тысяча девятьсот восьмидесятый"),
            ("gent", "тысяча девятьсот восьмидесятого"),
            ("datv", "тысяча девятьсот восьмидесятому"),
            ("ablt", "тысяча девятьсот восьмидесятым"),
            ("loct", "тысяча девятьсот восьмидесятом"),
        )
        for case, expected in cases:
            with self.subTest(case=case):
                self.assertEqual(year_to_ordinal_words(1980, case), expected)

    def test_singular_accusative_reads_as_the_nominative(self):
        self.assertEqual(
            year_to_ordinal_words(1980, "accs"),
            year_to_ordinal_words(1980, "nomn"),
        )

    def test_plural_forms_differ_from_the_singular(self):
        self.assertEqual(
            year_to_ordinal_words(1980, "nomn", True), "тысяча девятьсот восьмидесятые"
        )
        self.assertEqual(
            year_to_ordinal_words(1980, "gent", True), "тысяча девятьсот восьмидесятых"
        )

    def test_secondary_case_renders_as_its_primary_case(self):
        for secondary, primary in (
            ("gen2", "gent"),
            ("loc2", "loct"),
            ("acc2", "accs"),
            ("voct", "nomn"),
        ):
            with self.subTest(case=secondary):
                self.assertEqual(
                    year_to_ordinal_words(1980, secondary),
                    year_to_ordinal_words(1980, primary),
                )

    def test_five_digit_year_is_split_into_thousands_and_a_tail(self):
        self.assertEqual(
            year_to_ordinal_words(12345), "двенадцать тысяч триста сорок пятый"
        )

    def test_five_digit_round_year_is_not_split(self):
        self.assertEqual(year_to_ordinal_words(10500), "десять тысяч пятисотый")

    def test_pymorphy_fallback_inflects_the_last_word(self):
        # Reached when num2words cannot render the requested case; the ordinal
        # tail is then inflected with pymorphy instead.
        real = num2words.num2words

        def without_case(number, **kwargs):
            if kwargs.get("case"):
                raise ValueError("case is not supported by this release")
            return real(number, **kwargs)

        with patch.object(num2words, "num2words", side_effect=without_case):
            self.assertEqual(
                year_to_ordinal_words(1980, "loct"), "тысяча девятьсот восьмидесятом"
            )
            self.assertEqual(
                year_to_ordinal_words(1980, "gent", True),
                "тысяча девятьсот восьмидесятых",
            )

    def test_total_backend_failure_preserves_the_digits(self):
        with patch.object(
            num2words, "num2words", side_effect=RuntimeError("backend is broken")
        ):
            self.assertEqual(year_to_ordinal_words(1980, "gent"), "1980")


class ExplicitYearWordTests(unittest.TestCase):
    def test_year_word_and_preposition_decide_the_case(self):
        cases = (
            ("в 1980 году", "в тысяча девятьсот восьмидесятом году"),
            ("к 1980 году", "к тысяча девятьсот восьмидесятому году"),
            ("до 1980 года", "до тысяча девятьсот восьмидесятого года"),
            ("по 1980 год", "по тысяча девятьсот восьмидесятый год"),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(years(source), expected)

    def test_every_preposition_of_the_map_sets_the_case(self):
        # PREPOSITIONS_TO_CASE is what decides the case whenever the year word
        # itself is ambiguous, so each entry needs its own sentence. The long
        # forms ("во", "об", "ко", "со") are reproduced verbatim — only the case
        # of the year is under test here.
        cases = (
            ("В 2020 году открыли завод.", "В две тысячи двадцатом году открыли завод."),
            ("Речь идёт о 2020 годе.", "Речь идёт о две тысячи двадцатом годе."),
            ("К 2020 году план выполнили.", "К две тысячи двадцатому году план выполнили."),
            ("С 2020 года действует запрет.", "С две тысячи двадцатого года действует запрет."),
            ("До 2020 года завода не было.", "До две тысячи двадцатого года завода не было."),
            (
                "От 2020 года остались документы.",
                "От две тысячи двадцатого года остались документы.",
            ),
            ("За 2020 год отчитались вовремя.", "За две тысячи двадцатый год отчитались вовремя."),
            (
                "На 2020 год запланировали ремонт.",
                "На две тысячи двадцатый год запланировали ремонт.",
            ),
            (
                "По 2020 год включительно действует льгота.",
                "По две тысячи двадцатый год включительно действует льгота.",
            ),
            (
                "Около 2020 года началась стройка.",
                "Около две тысячи двадцатого года началась стройка.",
            ),
            ("Об 2020 годе спорят историки.", "Об две тысячи двадцатом годе спорят историки."),
            ("Во 2020 году построили мост.", "Во две тысячи двадцатом году построили мост."),
            ("Ко 2020 году подготовили отчёт.", "Ко две тысячи двадцатому году подготовили отчёт."),
            ("Со 2020 года ввели надбавку.", "Со две тысячи двадцатого года ввели надбавку."),
            (
                "Между 2020 и 2021 годами разница велика.",
                "Между две тысячи двадцатым и две тысячи двадцать первым годами разница велика.",
            ),
            # A written-out year word carries its own case, so it hides the
            # preposition. With the abbreviation the map is the only source:
            # "гг." and "г." on their own read as the nominative.
            (
                "Между 1990 и 2000 гг. разница велика.",
                "Между тысяча девятьсот девяностым и двухтысячным годами разница велика.",
            ),
            (
                "Около 2020 г. началась стройка.",
                "Около две тысячи двадцатого года началась стройка.",
            ),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(years(source), expected)

    def test_abbreviated_year_uses_the_preposition_case(self):
        cases = (
            (
                "В 2020 г. открыли завод.",
                "В две тысячи двадцатом году открыли завод.",
            ),
            (
                "Во 2020 г. построили мост.",
                "Во две тысячи двадцатом году построили мост.",
            ),
            (
                "О 2020 г. спорят историки.",
                "О две тысячи двадцатом году спорят историки.",
            ),
            (
                "Об 2020 г. спорят историки.",
                "Об две тысячи двадцатом году спорят историки.",
            ),
            (
                "К 2020 г. подготовили отчёт.",
                "К две тысячи двадцатому году подготовили отчёт.",
            ),
            (
                "Ко 2020 г. подготовили отчёт.",
                "Ко две тысячи двадцатому году подготовили отчёт.",
            ),
            (
                "С 2020 г. действует запрет.",
                "С две тысячи двадцатого года действует запрет.",
            ),
            (
                "Со 2020 г. действует запрет.",
                "Со две тысячи двадцатого года действует запрет.",
            ),
            (
                "До 2020 г. завода не было.",
                "До две тысячи двадцатого года завода не было.",
            ),
            (
                "От 2020 г. остались документы.",
                "От две тысячи двадцатого года остались документы.",
            ),
            (
                "За 2020 г. отчитались вовремя.",
                "За две тысячи двадцатый год отчитались вовремя.",
            ),
            (
                "На 2020 г. запланировали ремонт.",
                "На две тысячи двадцатый год запланировали ремонт.",
            ),
            (
                "По 2020 г. включительно действует льгота.",
                "По две тысячи двадцатый год включительно действует льгота.",
            ),
            (
                "Около 2020 г. началась стройка.",
                "Около две тысячи двадцатого года началась стройка.",
            ),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(years(source), expected)

    def test_every_written_year_word_sets_the_case_and_number(self):
        cases = (
            ("Наступил 2020 год.", "Наступил две тысячи двадцатый год."),
            ("Это дело 2020 года.", "Это дело две тысячи двадцатого года."),
            ("Договор датирован 2020 годом.", "Договор датирован две тысячи двадцатым годом."),
            ("Речь о 2020 годе.", "Речь о две тысячи двадцатом годе."),
            ("Пришли 1990 годы.", "Пришли тысяча девятьсот девяностые годы."),
            ("Данных за 1990 годов нет.", "Данных за тысяча девятьсот девяностых годов нет."),
            (
                "По 2020 годам собрали статистику.",
                "По две тысячи двадцатым годам собрали статистику.",
            ),
            (
                "В 2020 годах статистика неполна.",
                "В две тысячи двадцатых годах статистика неполна.",
            ),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(years(source), expected)

    def test_internal_stress_marker_does_not_split_a_year_word(self):
        cases = (
            (
                "В 2020 году.",
                "В две тысячи двадцатом году.",
            ),
            (
                "В 2020 г+оду.",
                "В две тысячи двадцатом году.",
            ),
            (
                "Между 1999 и 2000 год+ами разница велика.",
                "Между тысяча девятьсот девяносто девятым и двухтысячным годами разница велика.",
            ),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(years(source), expected)

    def test_every_written_suffix_sets_the_case_and_number(self):
        # YEAR_SUFFIX_REGEX is sorted longest first, so the shared tails ("го"
        # inside "ого", "м" inside "ом") only resolve correctly while that order
        # holds; both spellings of each case are listed.
        cases = (
            ("Наступил 2020-й год.", "Наступил две тысячи двадцатый год."),
            ("Ждали 2020-ый год.", "Ждали две тысячи двадцатый год."),
            ("Это было 2020-ой год.", "Это было две тысячи двадцатый год."),
            ("Это дело 2020-го года.", "Это дело две тысячи двадцатого года."),
            ("Из 2020-ого года пришла привычка.", "Из две тысячи двадцатого года пришла привычка."),
            ("К 2020-му году всё изменилось.", "К две тысячи двадцатому году всё изменилось."),
            ("Ко 2020-ому году план был готов.", "Ко две тысячи двадцатому году план был готов."),
            ("В 2020-м году подписали договор.", "В две тысячи двадцатом году подписали договор."),
            ("В 2020-ом году открыли завод.", "В две тысячи двадцатом году открыли завод."),
            (
                "Между 2020-ым и 2021-ым годами.",
                "Между две тысячи двадцатым и две тысячи двадцать первым годами.",
            ),
            ("В 1990-х годах страна менялась.", "В тысяча девятьсот девяностых годах страна менялась."),
            ("Из 1990-ых годов пришла мода.", "Из тысяча девятьсот девяностых годов пришла мода."),
            ("Пришли 1990-е годы.", "Пришли тысяча девятьсот девяностые годы."),
            ("Наступили 1990-ые годы.", "Наступили тысяча девятьсот девяностые годы."),
            (
                "Между 1990-ми и 2000-ми годами.",
                "Между тысяча девятьсот девяностыми и двухтысячными годами.",
            ),
            (
                "Между 1990-ыми и 2000-ыми годами.",
                "Между тысяча девятьсот девяностыми и двухтысячными годами.",
            ),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(years(source), expected)

    def test_abbreviated_year_word_is_expanded_and_inflected(self):
        self.assertEqual(years("в 1980 г."), "в тысяча девятьсот восьмидесятом году.")
        self.assertEqual(years("1980 г."), "тысяча девятьсот восьмидесятого года.")
        self.assertEqual(years("1980 гг."), "тысяча девятьсот восьмидесятых годов.")

    def test_several_years_share_one_year_word(self):
        self.assertEqual(
            years("1980, 1985 и 1990 годы"),
            "тысяча девятьсот восьмидесятый, тысяча девятьсот восемьдесят пятый "
            "и тысяча девятьсот девяностый годы",
        )
        self.assertEqual(
            years("в 1980 и 1985 годах"),
            "в тысяча девятьсот восьмидесятом и тысяча девятьсот восемьдесят пятом годах",
        )

    def test_several_years_with_an_abbreviated_word_take_the_preposition_case(self):
        self.assertEqual(
            years("1980 и 1985 гг."),
            "тысяча девятьсот восьмидесятый и тысяча девятьсот восемьдесят пятый годы",
        )


class DecadeTests(unittest.TestCase):
    def test_decade_suffix_renders_the_plural_ordinal(self):
        cases = (
            ("1980-е", "тысяча девятьсот восьмидесятые"),
            ("1980-м", "тысяча девятьсот восьмидесятым"),
            ("в 1980-м", "в тысяча девятьсот восьмидесятом"),
            ("к 1980-м", "к тысяча девятьсот восьмидесятым"),
            ("о 1980-х", "о тысяча девятьсот восьмидесятых"),
            ("в 1980-х годах", "в тысяча девятьсот восьмидесятых годах"),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(years(source), expected)

    def test_ambiguous_suffix_takes_its_case_from_the_preposition(self):
        # "-х" and "-м" are ambiguous on their own; the preposition decides.
        self.assertEqual(years("с 1980-х"), "с тысяча девятьсот восьмидесятых")
        self.assertEqual(years("в 1980-х"), "в тысяча девятьсот восьмидесятых")
        self.assertEqual(years("к 1980-м годам"), "к тысяча девятьсот восьмидесятым годам")
        self.assertEqual(years("по 1980-м"), "по тысяча девятьсот восьмидесятым")

    def test_bare_decade_suffix_uses_the_genitive(self):
        self.assertEqual(
            years("Наследие 1980-х повлияло на дизайн."),
            "Наследие тысяча девятьсот восьмидесятых повлияло на дизайн.",
        )

    def test_decade_is_rounded_down_to_the_tens(self):
        self.assertEqual(years("в 25-х годах"), "в двадцатых годах")

    def test_single_digit_is_read_as_an_ordinal_not_a_decade(self):
        # Regression: (5 // 10) * 10 turned "5-х годах" into "нулевых годах".
        # A single digit has no tens to round to, but "-х" is still a plural
        # ordinal, so it is rendered as one.
        cases = (
            ("в 5-х годах", "в пятых годах"),
            ("5-х годах", "пятых годах"),
            ("в 3-х годах", "в третьих годах"),
            ("в 7-х годах", "в седьмых годах"),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(years(source), expected)

    def test_short_bare_decade_without_a_year_word_is_left_untouched(self):
        self.assertEqual(years("20-х"), "20-х")

    def test_identifier_like_number_without_a_year_word_is_left_untouched(self):
        self.assertEqual(years("6301-Х"), "6301-Х")


class YearRangeTests(unittest.TestCase):
    def test_range_with_an_explicit_year_word_agrees_in_case(self):
        self.assertEqual(
            years("1941-1945 годы"),
            "тысяча девятьсот сорок первые — тысяча девятьсот сорок пятые годы",
        )
        self.assertEqual(
            years("в 1941-1945 гг."),
            "в тысяча девятьсот сорок первых — тысяча девятьсот сорок пятых годах.",
        )

    def test_bare_plural_abbreviation_range_is_rewritten_as_s_po(self):
        self.assertEqual(
            years("1941-1945 гг."),
            "с тысяча девятьсот сорок первого по тысяча девятьсот сорок пятый год.",
        )

    def test_s_po_rewrite_keeps_the_era_marker(self):
        # Regression: this branch returned before the era was appended, so
        # "до н. э." was dropped from the output entirely.
        self.assertEqual(
            years("1941-1945 гг. до н. э."),
            "с тысяча девятьсот сорок первого по тысяча девятьсот сорок пятый "
            "год до нашей эры.",
        )
        self.assertEqual(
            years("1941-1945 гг. н. э."),
            "с тысяча девятьсот сорок первого по тысяча девятьсот сорок пятый "
            "год нашей эры.",
        )

    def test_explicit_s_po_range_agrees_in_case(self):
        self.assertEqual(
            years("с 1980 по 1985 год"),
            "с тысяча девятьсот восьмидесятого по тысяча девятьсот восемьдесят пятый год",
        )

    def test_ot_do_range_agrees_in_case(self):
        self.assertEqual(
            years("от 1980 до 1985"),
            "от тысяча девятьсот восьмидесятого до тысяча девятьсот восемьдесят пятого",
        )
        self.assertEqual(
            years("от 1980 до 1985 года"),
            "от тысяча девятьсот восьмидесятого до тысяча девятьсот "
            "восемьдесят пятого года",
        )

    def test_decade_range_renders_both_ends_in_the_plural(self):
        self.assertEqual(
            years("1980-1990-е годы"),
            "тысяча девятьсот восьмидесятые — тысяча девятьсот девяностые годы",
        )

    def test_comma_separated_pair_without_a_year_word_is_left_untouched(self):
        self.assertEqual(years("1980,1985"), "1980,1985")


class EraMarkerTests(unittest.TestCase):
    def test_supported_era_spellings_are_expanded(self):
        cases = (
            ("300 г. до н. э.", "трёхсотый год до нашей эры."),
            ("300 г. до н.э.", "трёхсотый год до нашей эры."),
            ("300 год до нашей эры", "трёхсотый год до нашей эры"),
            ("в 300 г. н. э.", "в трёхсотом году нашей эры."),
            (
                "В 1980-м н. э. началась реформа.",
                "В тысяча девятьсот восьмидесятом году нашей эры началась реформа.",
            ),
            (
                "История началась в 300 г. B.C.",
                "История началась в трёхсотом году до нашей эры.",
            ),
            (
                "Учёные спорят о 300 г. BCE.",
                "Учёные спорят о трёхсотом году до нашей эры.",
            ),
            (
                "Реформа началась в 300 г. C.E.",
                "Реформа началась в трёхсотом году нашей эры.",
            ),
            (
                "Запись относится к 300 г. A.D.",
                "Запись относится к трёхсотому году нашей эры.",
            ),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(years(source), expected)

    def test_unsupported_era_spelling_leaves_the_match_untouched(self):
        self.assertEqual(years("300 г. до н. з."), "300 г. до н. з.")

    def test_shared_era_marker_covers_a_range(self):
        self.assertEqual(
            years("300-200 гг. до н. э."),
            "трёхсотые — двухсотые годы до нашей эры.",
        )

    def test_era_terminal_dot_is_kept_before_a_sentence_boundary(self):
        self.assertEqual(
            years("300 г. до н. э. Затем"), "трёхсотый год до нашей эры. Затем"
        )
        self.assertEqual(
            years("300 г. до н. э.\nДалее"), "трёхсотый год до нашей эры.\nДалее"
        )
        self.assertEqual(years("300 г. до н. э.»"), "трёхсотый год до нашей эры.»")
        self.assertEqual(
            years("300 г. до н. э.» Затем"), "трёхсотый год до нашей эры.» Затем"
        )

    def test_era_terminal_dot_is_dropped_mid_sentence(self):
        self.assertEqual(
            years("1980 г. н. э. (текст)"),
            "тысяча девятьсот восьмидесятый год нашей эры (текст)",
        )

    def test_marker_written_without_a_dot_never_gains_one(self):
        self.assertEqual(
            years("300 год до нашей эры и далее"),
            "трёхсотый год до нашей эры и далее",
        )


class ImplicitYearTests(unittest.TestCase):
    """A bare number after a preposition, with no year word to confirm it."""

    def test_preposition_alone_can_establish_a_year_and_its_case(self):
        cases = (
            ("родился в 1980", "родился в тысяча девятьсот восьмидесятом"),
            ("к 1980", "к тысяча девятьсот восьмидесятому"),
            ("на 1980", "на тысяча девятьсот восьмидесятый"),
            ("за 1980", "за тысяча девятьсот восьмидесятый"),
            ("под 1980", "под тысяча девятьсот восьмидесятый"),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(years(source), expected)

    def test_prepositions_that_need_an_explicit_year_word_are_left_alone(self):
        # "с 1980" is just as likely a quantity as a year, so without a year
        # word the number stays a number.
        for source in ("с 1980", "до 1980", "по 1980", "около 1980"):
            with self.subTest(source=source):
                self.assertEqual(years(source), source)

    def test_implicit_range_takes_the_case_from_the_middle_word(self):
        self.assertEqual(
            years("с 1980 по 1985"),
            "с тысяча девятьсот восьмидесятого по тысяча девятьсот восемьдесят пятый",
        )
        self.assertEqual(
            years("от 1980 до 1985"),
            "от тысяча девятьсот восьмидесятого до тысяча девятьсот восемьдесят пятого",
        )

    def test_implausible_implicit_range_is_left_untouched(self):
        self.assertEqual(years("с 300 по 200"), "с 300 по 200")

    def test_decade_suffix_followed_by_an_abbreviated_year_word(self):
        self.assertEqual(years("1980-х г."), "тысяча девятьсот восьмидесятых года.")
        self.assertEqual(years("в 1980-х г."), "в тысяча девятьсот восьмидесятых году.")


class SharedEraRangeTests(unittest.TestCase):
    def test_range_without_a_year_word_gets_one_from_the_era(self):
        self.assertEqual(
            years("300-200 до н. э."), "трёхсотый — двухсотый год до нашей эры."
        )

    def test_range_with_an_explicit_year_word_keeps_it(self):
        self.assertEqual(
            years("300-200 годы до нашей эры"),
            "трёхсотые — двухсотые годы до нашей эры",
        )


class ParenthesizedYearTests(unittest.TestCase):
    def test_plausible_year_in_parentheses_is_read_as_a_cardinal(self):
        self.assertEqual(years("(1980)"), "(одна тысяча девятьсот восемьдесят)")

    def test_implausible_year_in_parentheses_is_left_untouched(self):
        self.assertEqual(years("(300)"), "(300)")
        self.assertEqual(years("(12345)"), "(12345)")

    def test_parenthesized_year_preserves_the_digits_when_the_backend_fails(self):
        with patch.object(
            num2words, "num2words", side_effect=RuntimeError("backend is broken")
        ):
            self.assertEqual(years("(1980)"), "(1980)")


class NumericRangeTests(unittest.TestCase):
    def test_dash_separated_pair_becomes_an_enumeration(self):
        self.assertEqual(normalize_numeric_ranges("выпуск 5—7."), "выпуск 5, 7.")
        self.assertEqual(normalize_numeric_ranges("(5–7)"), "(5, 7)")

    def test_ascii_hyphen_is_not_a_range(self):
        # An ASCII hyphen carries too many other meanings; only a typographic
        # dash is read as an enumeration here.
        self.assertEqual(normalize_numeric_ranges("5-7 человек"), "5-7 человек")

    def test_measurement_range_is_left_untouched(self):
        # A unit or word on the right makes it a measurement, not an enumeration.
        self.assertEqual(normalize_numeric_ranges("5—7 кг"), "5—7 кг")
        self.assertEqual(normalize_numeric_ranges("5—7 человек"), "5—7 человек")
        self.assertEqual(normalize_numeric_ranges("5—7%"), "5—7%")


if __name__ == "__main__":
    unittest.main()
