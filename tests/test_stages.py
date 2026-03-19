import unittest

from ru_normalizr import NormalizeOptions, Normalizer
from ru_normalizr.abbreviations import expand_abbreviations
from ru_normalizr.dates_time import normalize_dates_and_time
from ru_normalizr.numbering import convert_bracketed_numbers
from ru_normalizr.numerals import (
    normalize_decimals,
    normalize_fractions,
    normalize_hyphenated_words,
    normalize_math_symbols,
    normalize_numerals,
    normalize_ordinals,
)
from ru_normalizr.roman_numerals import normalize_roman
from ru_normalizr.years import normalize_years


class RuNormalizrStageTests(unittest.TestCase):
    def test_roman_stage(self):
        self.assertEqual(
            normalize_roman("Глава IV. Общественный строй"),
            "Глава 4. Общественный строй",
        )

    def test_roman_stage_does_not_treat_cyrillic_measurement_as_roman(self):
        self.assertEqual(
            normalize_roman("Диаметр 40 см."),
            "Диаметр 40 см.",
        )

    def test_roman_stage_keeps_title_case_see_abbreviation(self):
        self.assertEqual(
            normalize_roman("См. главу IV."),
            "См. главу 4.",
        )

    def test_roman_stage_keeps_known_abbreviation_cd(self):
        self.assertEqual(
            normalize_roman("CD-плеер и CD"),
            "CD-плеер и CD",
        )

    def test_roman_stage_keeps_configured_roman_exceptions(self):
        self.assertEqual(
            normalize_roman("DC MD CV CI DI MC CM MM"),
            "DC MD CV CI DI MC CM MM",
        )

    def test_dates_time_stage(self):
        self.assertEqual(
            normalize_dates_and_time("Встреча в 10:07."),
            "Встреча в десять, ноль семь.",
        )

    def test_dates_time_stage_normalizes_listed_days_in_text_date(self):
        self.assertEqual(
            normalize_dates_and_time("Эти объекты наблюдались 15 и 25 апреля."),
            "Эти объекты наблюдались пятнадцатого и двадцать пятого апреля.",
        )

    def test_dates_time_stage_normalizes_comma_separated_days_in_text_date(self):
        self.assertEqual(
            normalize_dates_and_time("Замеры делали 15, 25 и 27 апреля."),
            "Замеры делали пятнадцатого, двадцать пятого и двадцать седьмого апреля.",
        )

    def test_dates_time_stage_normalizes_day_range_with_preposition(self):
        self.assertEqual(
            normalize_dates_and_time("за 11–12 февраля 1905 года"),
            "за одиннадцатое — двенадцатое февраля тысяча девятьсот пятого года",
        )

    def test_dates_time_pipeline_stage_leaves_decimal_numbers_for_numerals_stage(self):
        normalizer = Normalizer()
        self.assertEqual(normalizer.run_stage("dates_time", "3,6"), "3,6")
        self.assertEqual(normalizer.run_stage("dates_time", "(3,6)"), "(3,6)")

    def test_numeral_stage(self):
        self.assertEqual(
            normalize_numerals("250$"),
            "двести пятьдесят долларов",
        )

    def test_numeral_stage_normalizes_heading_single_number_as_ordinal(self):
        self.assertEqual(
            normalize_numerals("главу 10"),
            "главу десятую",
        )
        self.assertEqual(
            normalize_numerals("в главе 10"),
            "в главе десятой",
        )

    def test_numeral_stage_normalizes_negative_measurements(self):
        self.assertEqual(
            normalize_numerals("\ue00120 °C"),
            "минус двадцать градусов Цельсия",
        )

    def test_numeral_stage_preserves_measurement_ranges(self):
        self.assertEqual(
            normalize_numerals("до 30 — 40 см в диаметре"),
            "до тридцати — сорока сантиметров в диаметре",
        )

    def test_numeral_stage_normalizes_bracketed_integer_via_pipeline_stage(self):
        normalizer = Normalizer()
        self.assertEqual(normalizer.run_stage("numerals", "(2)"), "(два)")

    def test_numeral_stage_normalizes_bracketed_decimal_via_pipeline_stage(self):
        normalizer = Normalizer()
        self.assertEqual(
            normalizer.run_stage("numerals", "(3,6)"), "(три целых шесть десятых)"
        )

    def test_numeral_stage_normalizes_other_bracketed_decimals_via_pipeline_stage(self):
        normalizer = Normalizer()
        self.assertEqual(
            normalizer.run_stage("numerals", "(2,6)"), "(две целых шесть десятых)"
        )
        self.assertEqual(
            normalizer.run_stage("numerals", "(3.4)"), "(три целых четыре десятых)"
        )

    def test_numeral_stage_normalizes_decimal_via_pipeline_stage(self):
        normalizer = Normalizer()
        self.assertEqual(normalizer.run_stage("numerals", "3,6"), "три целых шесть десятых")

    def test_numeral_stage_reads_equals_only_between_numeric_expressions(self):
        normalizer = Normalizer()
        self.assertEqual(normalizer.run_stage("numerals", "2=2"), "два равно два")
        self.assertEqual(
            normalizer.run_stage("numerals", "3,5 = 7/2"),
            "три целых пять десятых равно семь вторых",
        )
        self.assertEqual(normalizer.run_stage("numerals", "x = y"), "x = y")

    def test_numeral_helpers_cover_decimals_fractions_ordinals_and_hyphenated_words(self):
        self.assertEqual(
            normalize_decimals("1.5 кг"),
            "одна целая пять десятых килограмма",
        )
        self.assertEqual(normalize_fractions("1/4"), "одна четвёртая")
        self.assertEqual(normalize_ordinals("5-й"), "пятый ")
        self.assertEqual(
            normalize_hyphenated_words("20-этажный дом"),
            "двадцатиэтажный дом",
        )

    def test_math_symbol_stage_reads_equals_when_one_side_contains_digits(self):
        self.assertEqual(normalize_math_symbols("t=10"), "t равно 10")
        self.assertEqual(normalize_math_symbols("x=(2+3)"), "x равно (2+3)")
        self.assertEqual(normalize_math_symbols("x = y"), "x = y")
        self.assertEqual(normalize_math_symbols("======"), "======")

    def test_abbreviation_stage(self):
        self.assertEqual(
            expand_abbreviations("т. д."),
            "так далее.",
        )

    def test_abbreviation_stage_expands_see_figure(self):
        self.assertEqual(
            expand_abbreviations("(см. рис.)"),
            "(смотри рисунок)",
        )

    def test_abbreviation_stage_expands_article_only_before_digit(self):
        self.assertEqual(
            expand_abbreviations("ст. 15 УК РФ"),
            "статья 15 уголовный кодекс российской федерации",
        )

    def test_abbreviation_stage_keeps_article_abbreviation_without_digit(self):
        self.assertEqual(
            expand_abbreviations("ст. ложка"),
            "ст. ложка",
        )

    def test_abbreviation_stage_drops_terminal_dot_inside_sentence(self):
        self.assertEqual(
            expand_abbreviations("и т. д. и т. п."),
            "и так далее и тому подобное.",
        )

    def test_abbreviation_stage_keeps_terminal_dot_before_uppercase(self):
        self.assertEqual(
            expand_abbreviations("и т. п. Эти шумы"),
            "и тому подобное. Эти шумы",
        )

    def test_abbreviation_stage_keeps_terminal_dot_before_linebreak(self):
        self.assertEqual(
            expand_abbreviations("и т. д.\nСледующая строка"),
            "и так далее.\nСледующая строка",
        )

    def test_abbreviation_stage_prefers_note_specific_rules(self):
        self.assertEqual(
            expand_abbreviations("(прим. перев.)"),
            "(примечание переводчика)",
        )
        self.assertEqual(
            expand_abbreviations("прим.ред."),
            "примечание редактора",
        )

    def test_year_stage(self):
        self.assertIn(
            "году книга",
            normalize_years("В 1981 г. книга вышла."),
        )

    def test_year_stage_normalizes_clean_implicit_year_phrase(self):
        self.assertEqual(
            normalize_years("в 1990 началось обсуждение"),
            "в тысяча девятьсот девяностом началось обсуждение",
        )
        self.assertEqual(
            normalize_years("в 1990, началось обсуждение"),
            "в тысяча девятьсот девяностом, началось обсуждение",
        )

    def test_year_stage_keeps_hyphenated_decade_out_of_implicit_year_rule(self):
        self.assertEqual(
            normalize_years("а в 1990-ые годы началась новая волна обсуждений."),
            "а в тысяча девятьсот девяностые годы началась новая волна обсуждений.",
        )

    def test_year_stage_keeps_measurement_contexts_out_of_implicit_year_rules(self):
        self.assertEqual(normalize_years("в 1990 кг"), "в 1990 кг")
        self.assertEqual(normalize_years("от 1000 до 1200 кг"), "от 1000 до 1200 кг")
        self.assertEqual(normalize_years("с 1990 по 1995 кг"), "с 1990 по 1995 кг")
        self.assertEqual(normalize_years("с 1990 по 1995 руб."), "с 1990 по 1995 руб.")

    def test_year_stage_keeps_explicit_s_po_year_ranges_working(self):
        self.assertEqual(
            normalize_years("с 1990 по 1995"),
            "с тысяча девятьсот девяностого по тысяча девятьсот девяносто пятый",
        )
        self.assertEqual(
            normalize_years("с 1990 по 1995 гг."),
            "с тысяча девятьсот девяностого по тысяча девятьсот девяносто пятый годы.",
        )
        self.assertEqual(
            normalize_years("с 1920 до 1933 г."),
            "с тысяча девятьсот двадцатого до тысяча девятьсот тридцать третьего года.",
        )

    def test_bracketed_number_stage_respects_link_removal(self):
        self.assertEqual(
            convert_bracketed_numbers("Текст [1]", NormalizeOptions.tts()), "Текст "
        )

    def test_bracketed_number_stage_keeps_references_when_link_removal_is_disabled(self):
        self.assertEqual(convert_bracketed_numbers("Текст (1)"), "Текст (1)")
        self.assertEqual(convert_bracketed_numbers("Текст [12]"), "Текст [12]")

    def test_bracketed_number_stage_keeps_comma_decimals(self):
        self.assertEqual(convert_bracketed_numbers("Текст (500,5)"), "Текст (500,5)")
        self.assertEqual(convert_bracketed_numbers("Текст (2,6)"), "Текст (2,6)")
        self.assertEqual(convert_bracketed_numbers("Текст (3,14)"), "Текст (3,14)")
        self.assertEqual(convert_bracketed_numbers("Текст (3.4)"), "Текст (3.4)")
        self.assertEqual(convert_bracketed_numbers("Текст (−0,7)"), "Текст (−0,7)")

    def test_bracketed_number_stage_keeps_numbers_with_units(self):
        self.assertEqual(convert_bracketed_numbers("Текст (10,0%)"), "Текст (10,0%)")
        self.assertEqual(
            convert_bracketed_numbers("Текст (500,5 кг)"), "Текст (500,5 кг)"
        )
        self.assertEqual(
            convert_bracketed_numbers("Текст (500,5 руб.)"), "Текст (500,5 руб.)"
        )

    def test_bracketed_number_stage_removes_confident_references(self):
        options = NormalizeOptions.tts()
        self.assertEqual(convert_bracketed_numbers("Текст (1)", options), "Текст ")
        self.assertEqual(convert_bracketed_numbers("Текст (12)", options), "Текст ")
        self.assertEqual(convert_bracketed_numbers("Текст (1, 3, 5)", options), "Текст ")
        self.assertEqual(convert_bracketed_numbers("Текст (1–3)", options), "Текст ")
        self.assertEqual(convert_bracketed_numbers("Текст (2.5)", options), "Текст ")
        self.assertEqual(convert_bracketed_numbers("Текст (2.5.1)", options), "Текст ")


if __name__ == "__main__":
    unittest.main()
