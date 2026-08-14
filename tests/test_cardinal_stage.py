"""Branch coverage for the cardinal stage: units, ranges, accusative agreement.

The stage decides case, gender and animacy from the noun it counts, and those
decisions are what the tests below pin. Unit lemmas come from `UNITS_DATA`, so a
unit that is not in the table must leave the text alone rather than guess.
"""

import unittest
from unittest.mock import patch

import num2words

from ru_normalizr.numerals._helpers import paucal_accusative_case
from ru_normalizr.numerals.cardinals import (
    normalize_all_digits_everywhere,
    normalize_cardinal_numerals,
    normalize_numeric_unit_ranges,
    normalize_remaining_post_numeral_abbreviations,
)


class PaucalAccusativeCaseTests(unittest.TestCase):
    def test_non_accusative_cases_pass_through(self):
        for case in ("nomn", "gent", "datv", "ablt", "loct"):
            with self.subTest(case=case):
                self.assertEqual(
                    paucal_accusative_case(22, case, animate=True), case
                )

    def test_numerals_outside_the_paucal_group_stay_accusative(self):
        for value in (1, 5, 11, 12, 13, 14, 25, 100):
            with self.subTest(value=value):
                self.assertEqual(
                    paucal_accusative_case(value, "accs", animate=False), "accs"
                )

    def test_bare_paucal_numeral_takes_the_genitive_only_when_animate(self):
        for value in (2, 3, 4):
            with self.subTest(value=value):
                self.assertEqual(
                    paucal_accusative_case(value, "accs", animate=True), "gent"
                )
                self.assertEqual(
                    paucal_accusative_case(value, "accs", animate=False), "nomn"
                )

    def test_compound_paucal_numeral_never_takes_the_genitive(self):
        # Regression: a compound numeral was inflected as if it were bare, so
        # "вижу 22 человека" read as "двадцати двух человека".
        for value in (22, 33, 44, 102, 1002):
            with self.subTest(value=value):
                self.assertEqual(
                    paucal_accusative_case(value, "accs", animate=True), "nomn"
                )


class AccusativeAgreementTests(unittest.TestCase):
    def test_compound_paucal_numeral_stays_nominative_before_an_animate_noun(self):
        cases = (
            ("Вижу 22 человека", "Вижу двадцать два человека"),
            ("Вижу 102 человека", "Вижу сто два человека"),
            ("Пригласил 22 гостя", "Пригласил двадцать два гостя"),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(normalize_cardinal_numerals(source), expected)

    def test_bare_paucal_numeral_is_genitive_before_an_animate_noun(self):
        self.assertEqual(
            normalize_cardinal_numerals("Вижу 2 человека"), "Вижу двух человека"
        )

    def test_inanimate_noun_keeps_the_nominative_numeral(self):
        self.assertEqual(
            normalize_cardinal_numerals("Вижу 22 дома"), "Вижу двадцать два дома"
        )
        self.assertEqual(
            normalize_cardinal_numerals("через 22 года"), "через двадцать два года"
        )

    def test_numeral_ending_in_one_keeps_the_accusative(self):
        self.assertEqual(
            normalize_cardinal_numerals("Вижу 21 человека"),
            "Вижу двадцать одного человека",
        )

    def test_teens_are_not_paucal(self):
        self.assertEqual(
            normalize_cardinal_numerals("Вижу 12 домов"), "Вижу двенадцать домов"
        )

    def test_adjective_before_the_noun_still_drives_agreement(self):
        self.assertEqual(
            normalize_cardinal_numerals("Вижу 22 новых дома"),
            "Вижу двадцать два новых дома",
        )


class UnitTests(unittest.TestCase):
    def test_unit_is_expanded_and_agrees_with_the_numeral(self):
        cases = (
            ("5 кг", "пять килограмм"),
            ("1 кг", "один килограмм"),
            ("0 кг", "ноль килограмм"),
            ("20 °C", "двадцать градусов Цельсия"),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(normalize_cardinal_numerals(source), expected)

    def test_trailing_abbreviation_dot_is_kept_at_a_sentence_end(self):
        self.assertEqual(normalize_cardinal_numerals("5 кг."), "пять килограмм.")

    def test_multiplier_pulls_the_following_unit_into_the_genitive_plural(self):
        cases = (
            ("5 млн тонн", "пять миллионов тонн"),
            ("5 млн т", "пять миллионов тонн"),
            ("5 миллионов тонн", "пять миллионов тонн"),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(normalize_cardinal_numerals(source), expected)

    def test_bare_multiplier_is_expanded_on_its_own(self):
        self.assertEqual(normalize_cardinal_numerals("5 млн"), "пять миллионов")

    def test_currency_symbol_before_a_multiplier_is_reordered(self):
        # "2 $ миллиарда" names billions of dollars, so the multiplier comes
        # first and the currency follows in the genitive plural.
        self.assertEqual(
            normalize_cardinal_numerals("2 $ миллиарда"), "два миллиарда долларов"
        )
        self.assertEqual(
            normalize_cardinal_numerals("5 $ миллионов"), "пять миллионов долларов"
        )

    def test_currency_symbol_without_a_multiplier_reads_as_the_currency(self):
        self.assertEqual(normalize_cardinal_numerals("5 $"), "пять долларов")

    def test_unit_is_not_taken_across_a_line_break(self):
        self.assertEqual(
            normalize_cardinal_numerals("5\nкг"), "пять\nкг"
        )


class UnitRangeTests(unittest.TestCase):
    def test_range_inherits_the_case_from_a_preceding_prepositional_noun(self):
        self.assertEqual(
            normalize_cardinal_numerals("В комнатах 5-7 окон."),
            "В комнатах пяти — семи окон.",
        )

    def test_s_po_range_uses_genitive_for_the_first_endpoint(self):
        self.assertEqual(
            normalize_cardinal_numerals("С 5 по 10 страниц."),
            "С пяти по десять страниц.",
        )

    def test_range_with_a_single_word_unit(self):
        self.assertEqual(
            normalize_numeric_unit_ranges("5-7 кг"), "пять — семь килограмм"
        )

    def test_range_with_a_two_word_unit(self):
        self.assertEqual(
            normalize_numeric_unit_ranges("5-7 квадратных метров"),
            "пять — семь квадратных метров",
        )
        self.assertEqual(
            normalize_numeric_unit_ranges("5-7 кубических метров"),
            "пять — семь кубических метров",
        )

    def test_range_with_an_unknown_unit_is_left_untouched(self):
        # Not in the unit table: guessing a lemma would invent a reading.
        for source in ("5-7 непонятных штук", "5-7 лошадиных сил", "5-7 метров"):
            with self.subTest(source=source):
                self.assertEqual(normalize_numeric_unit_ranges(source), source)

    def test_range_in_the_accusative_keeps_the_paucal_numeral_nominative(self):
        self.assertEqual(
            normalize_numeric_unit_ranges("Вижу 2-3 кг"), "Вижу два — три килограмма"
        )
        self.assertEqual(
            normalize_numeric_unit_ranges("Вижу 22-23 кг"),
            "Вижу двадцать два — двадцать три килограмма",
        )


class PostNumeralAbbreviationTests(unittest.TestCase):
    def test_abbreviation_dot_is_kept_at_the_end_of_the_text(self):
        result = normalize_remaining_post_numeral_abbreviations("вес 5 кг.")

        self.assertTrue(result.endswith("."), result)

    def test_abbreviation_dot_is_kept_before_a_sentence_boundary(self):
        for tail in (".", "!", "?", "\n"):
            with self.subTest(tail=tail):
                result = normalize_remaining_post_numeral_abbreviations(
                    f"вес 5 кг{tail}"
                )
                self.assertIn("кг", result)

    def test_abbreviations_are_expanded_case_insensitively_with_mixed_spacing(self):
        result = normalize_remaining_post_numeral_abbreviations(
            "5 ТЫС. 6 Млн. 7 МЛРД. 8 ТРЛН. 9 РУБ. 10 ДОЛЛ. 11 ДОЛ. 12 и\tДР."
        )

        self.assertEqual(
            result,
            "5 тысяч 6 миллионов 7 миллиардов 8 триллионов 9 рублей "
            "10 долларов 11 долларов 12 и другие.",
        )


class AllDigitsTests(unittest.TestCase):
    def test_every_remaining_digit_group_is_read_out(self):
        self.assertEqual(
            normalize_all_digits_everywhere("дом 5 и 42"), "дом пять и сорок два"
        )

    def test_digits_are_preserved_when_the_backend_fails(self):
        with patch.object(
            num2words, "num2words", side_effect=RuntimeError("backend is broken")
        ):
            self.assertEqual(normalize_all_digits_everywhere("дом 5"), "дом 5")


if __name__ == "__main__":
    unittest.main()
