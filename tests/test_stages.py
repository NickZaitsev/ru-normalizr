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
from ru_normalizr.urls import normalize_urls
from ru_normalizr.years import normalize_years
from ru_normalizr.years_context import is_plausible_year


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
        self.assertEqual(
            normalize_roman("Фотокамера 35-ММ."),
            "Фотокамера 35-ММ.",
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
        self.assertEqual(
            normalize_numerals("из главы 10"),
            "из главы десятой",
        )
        self.assertEqual(
            normalize_numerals("до главы 10"),
            "до главы десятой",
        )
        self.assertEqual(
            normalize_numerals("из раздела 3"),
            "из раздела третьего",
        )
        self.assertEqual(
            normalize_numerals("из книги 2"),
            "из книги второй",
        )
        self.assertEqual(
            normalize_numerals("в части 2"),
            "в части второй",
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

    def test_numeral_stage_supports_safe_hyphenated_units(self):
        normalizer = Normalizer()
        self.assertEqual(
            normalizer.run_stage("numerals", "35-мм и 1,5-мл"),
            "тридцать пять миллиметров и одна целая пять десятых миллилитра",
        )
        self.assertEqual(
            normalizer.run_stage("numerals", "20 - этажный дом и 5 - й этаж"),
            "двадцатиэтажный дом и пятый этаж",
        )
        self.assertEqual(
            normalizer.run_stage("numerals", "20-этажный дом"),
            "двадцатиэтажный дом",
        )

    def test_math_symbol_stage_reads_equals_when_one_side_contains_digits(self):
        self.assertEqual(normalize_math_symbols("t=10"), "t равно 10")
        self.assertEqual(normalize_math_symbols("x=(2+3)"), "x равно (2+3)")
        self.assertEqual(normalize_math_symbols("x = y"), "x = y")
        self.assertEqual(normalize_math_symbols("======"), "======")

    def test_finalize_stage_converts_ascii_spaced_hyphen_to_dash(self):
        normalizer = Normalizer()
        self.assertEqual(normalizer.run_stage("finalize", "слово - слово"), "слово — слово")
        self.assertEqual(normalizer.run_stage("finalize", "слово — слово"), "слово — слово")

    def test_url_stage_rewrites_explicit_url_structure_before_preprocess(self):
        normalizer = Normalizer(NormalizeOptions.tts())
        self.assertEqual(
            normalizer.run_stage("urls", "https://milk.org/a1?b=23."),
            "https двоеточие слэш слэш milk точка org слэш a один вопрос b равно два три.",
        )

    def test_url_stage_is_disabled_outside_tts_by_default(self):
        self.assertEqual(
            normalize_urls("https://milk.org/a1?b=23.", enabled=False),
            "https://milk.org/a1?b=23.",
        )

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

    def test_abbreviation_stage_expands_english_titles(self):
        self.assertEqual(
            expand_abbreviations("Mr. Поппер"),
            "мистер Поппер",
        )
        self.assertEqual(
            expand_abbreviations("Mrs. Поппер"),
            "миссис Поппер",
        )

    def test_abbreviation_stage_expands_single_initials_in_tts_only_for_name_like_tokens(self):
        self.assertEqual(
            expand_abbreviations("Ч. Рихтер", NormalizeOptions.tts()),
            "чэ Рихтер.",
        )
        self.assertEqual(
            expand_abbreviations("Рихтер Ч.", NormalizeOptions.tts()),
            "Рихтер чэ.",
        )
        self.assertEqual(
            expand_abbreviations("С. Петербург", NormalizeOptions.tts()),
            "С. Петербург",
        )
        self.assertEqual(
            expand_abbreviations("Ч. Рихтер", NormalizeOptions.safe()),
            "Ч. Рихтер",
        )

    def test_abbreviation_stage_expands_article_only_before_digit(self):
        self.assertEqual(
            expand_abbreviations("ст. 15 УК РФ"),
            "статья 15 уголовный кодекс российской федерации",
        )

    def test_abbreviation_stage_normalizes_ampersand_contextually(self):
        self.assertEqual(
            expand_abbreviations("нефть & газ"),
            "нефть и газ",
        )
        self.assertEqual(
            expand_abbreviations("эй ти & ти"),
            "эй ти энд ти",
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

    def test_abbreviation_stage_inflects_contextual_adjective_abbreviations(self):
        self.assertEqual(
            expand_abbreviations("гос. контроля"),
            "государственного контроля",
        )
        self.assertEqual(
            expand_abbreviations("гос. имущество"),
            "государственное имущество",
        )
        self.assertEqual(
            expand_abbreviations("гос. институты"),
            "государственные институты",
        )
        self.assertEqual(
            expand_abbreviations("междунар. контроля"),
            "международного контроля",
        )
        self.assertEqual(
            expand_abbreviations("полит. системы"),
            "политической системы",
        )
        self.assertEqual(
            expand_abbreviations("нем. слово"),
            "немецкое слово",
        )

    def test_abbreviation_stage_keeps_pronoun_sentence_boundary_for_language_like_tokens(self):
        self.assertEqual(
            expand_abbreviations("в нем. Когда мы вспоминали об этом"),
            "в нем. Когда мы вспоминали об этом",
        )
        self.assertEqual(
            expand_abbreviations("о нем. Потом заговорили снова"),
            "о нем. Потом заговорили снова",
        )
        self.assertEqual(
            expand_abbreviations("от нем. Beobachtung"),
            "от немецкого Beobachtung",
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
        self.assertEqual(normalize_years("от 1 до 9"), "от 1 до 9")
        self.assertEqual(normalize_years("от 90 до 99"), "от 90 до 99")
        self.assertEqual(normalize_years("в 1990 кг"), "в 1990 кг")
        self.assertEqual(normalize_years("в 1990 % случаев"), "в 1990 % случаев")
        self.assertEqual(normalize_years("в 1990 ¢"), "в 1990 ¢")
        self.assertEqual(normalize_years("в 1990 руб."), "в 1990 руб.")
        self.assertEqual(normalize_years("в 1990 usd"), "в 1990 usd")
        self.assertEqual(normalize_years("от 1000 до 1200 кг"), "от 1000 до 1200 кг")
        self.assertEqual(normalize_years("от 1200 до 10000 ¢"), "от 1200 до 10000 ¢")
        self.assertEqual(normalize_years("от 1200 до 10000 ₽"), "от 1200 до 10000 ₽")
        self.assertEqual(normalize_years("от 1200 до 10000 МПа"), "от 1200 до 10000 МПа")
        self.assertEqual(
            normalize_years("от 1200 до 10 000 ¢"), "от 1200 до 10 000 ¢"
        )
        self.assertEqual(
            normalize_years("от 1200 до 10 000 ₽"), "от 1200 до 10 000 ₽"
        )
        self.assertEqual(
            normalize_years("от 1200 до 10 000 МПа"), "от 1200 до 10 000 МПа"
        )
        self.assertEqual(normalize_years("с 1990 по 1995 кг"), "с 1990 по 1995 кг")
        self.assertEqual(normalize_years("с 1990 по 1995 руб."), "с 1990 по 1995 руб.")
        self.assertEqual(normalize_years("с 1990 по 1995 usd"), "с 1990 по 1995 usd")

    def test_year_context_plausible_year_bounds(self):
        self.assertFalse(is_plausible_year(999))
        self.assertTrue(is_plausible_year(1000))
        self.assertTrue(is_plausible_year(1990))
        self.assertTrue(is_plausible_year(2100))
        self.assertFalse(is_plausible_year(2101))

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
