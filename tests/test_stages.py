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
            "Глава четвёртая. Общественный строй",
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

    def test_roman_stage_keeps_cyrillic_caps_interjection_out_of_roman(self):
        self.assertEqual(
            normalize_roman("— ММММ, — простонала она."),
            "— ММММ, — простонала она.",
        )

    def test_roman_stage_keeps_title_case_see_abbreviation(self):
        self.assertEqual(
            normalize_roman("См. главу IV."),
            "См. главу четвёртую.",
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

    def test_roman_stage_reads_shared_millennium_series_as_ordinals(self):
        self.assertEqual(
            normalize_roman("В V и IV тысячелетиях до н. э."),
            "В пятом и четвёртом тысячелетиях до н. э.",
        )

    def test_roman_stage_reads_shared_century_series_with_commas(self):
        self.assertEqual(
            normalize_roman("В V, IV и III веках такие случаи были редки."),
            "В пятом, четвёртом и третьем веках такие случаи были редки.",
        )
        self.assertEqual(
            normalize_roman("В XVI и XVII веках религиозные войны опустошали Европу."),
            "В шестнадцатом и семнадцатом веках религиозные войны опустошали Европу.",
        )
        self.assertEqual(
            normalize_roman(
                "Страшную память оставили по себе религиозные войны между католиками и протестантами, опустошавшие Европу в XVI и XVII веках."
            ),
            "Страшную память оставили по себе религиозные войны между католиками и протестантами, опустошавшие Европу в шестнадцатом и семнадцатом веках.",
        )

    def test_roman_stage_reads_shared_century_series_in_accusative_context(self):
        self.assertEqual(
            normalize_roman("За XV и XVI века европейцы успели проплыть вокруг Африки."),
            "За пятнадцатый и шестнадцатый века европейцы успели проплыть вокруг Африки.",
        )

    def test_roman_stage_reads_shared_century_series_in_dative_context(self):
        self.assertEqual(
            normalize_roman("К XV и XVI векам сложились новые маршруты."),
            "К пятнадцатому и шестнадцатому векам сложились новые маршруты.",
        )
        self.assertEqual(
            normalize_roman("Моряки XV и XVI веков хорошо знали маршруты."),
            "Моряки пятнадцатого и шестнадцатого веков хорошо знали маршруты.",
        )

    def test_roman_stage_reads_century_abbreviation_in_context(self):
        self.assertEqual(
            normalize_roman("В XV в. начались перемены."),
            "В пятнадцатом веке начались перемены.",
        )
        self.assertEqual(
            normalize_roman("За XV в. многое изменилось."),
            "За пятнадцатый век многое изменилось.",
        )
        self.assertEqual(
            normalize_roman("О XV в. часто спорят историки."),
            "О пятнадцатом веке часто спорят историки.",
        )
        self.assertEqual(
            normalize_roman("К XV в. сложились новые маршруты."),
            "К пятнадцатому веку сложились новые маршруты.",
        )
        self.assertEqual(
            normalize_roman("Наследие XXI века ощущается до сих пор."),
            "Наследие двадцать первого века ощущается до сих пор.",
        )
        self.assertEqual(
            normalize_roman("От XVI до XVIII в. менялись маршруты."),
            "От шестнадцатого до восемнадцатого века менялись маршруты.",
        )
        self.assertEqual(
            normalize_roman("В XV-XVI вв. менялись маршруты."),
            "В пятнадцатом — шестнадцатом веках менялись маршруты.",
        )
        self.assertEqual(
            normalize_roman("XV и XVI вв."),
            "пятнадцатый и шестнадцатый века",
        )
        self.assertEqual(
            normalize_roman("XV-XVI вв."),
            "пятнадцатый — шестнадцатый века",
        )
        self.assertEqual(
            normalize_roman("С XVI по XVIII вв. менялись маршруты."),
            "С шестнадцатого по восемнадцатый века менялись маршруты.",
        )
        self.assertEqual(
            normalize_roman("От XVI до XVIII вв. менялись маршруты."),
            "От шестнадцатого до восемнадцатого веков менялись маршруты.",
        )

    def test_roman_stage_reads_quarter_abbreviations_in_context(self):
        self.assertEqual(
            normalize_roman("IV кв."),
            "четвёртый квартал",
        )
        self.assertEqual(
            normalize_roman("В IV кв. выросла выручка."),
            "В четвёртом квартале выросла выручка.",
        )
        self.assertEqual(
            normalize_roman("О IV кв. говорили долго."),
            "О четвёртом квартале говорили долго.",
        )
        self.assertEqual(
            normalize_roman("К IV кв. подготовят отчет."),
            "К четвёртому кварталу подготовят отчет.",
        )

    def test_roman_stage_reads_hyphenated_roman_ranges_in_context(self):
        self.assertEqual(
            normalize_roman("В III-IV веках н.э. манихейство распространялось."),
            "В третьем — четвёртом веках н.э. манихейство распространялось.",
        )
        self.assertEqual(
            normalize_roman("В III-IV тысячелетиях до н. э. распространялись ранние культуры."),
            "В третьем — четвёртом тысячелетиях до н. э. распространялись ранние культуры.",
        )
        self.assertEqual(
            normalize_roman("Моряки XV-XVI веков хорошо знали маршруты."),
            "Моряки пятнадцатого — шестнадцатого веков хорошо знали маршруты.",
        )
        self.assertEqual(
            normalize_roman("IV-V кварталах"),
            "четвёртом — пятом кварталах",
        )

    def test_roman_stage_reads_left_shared_heading_series(self):
        self.assertEqual(
            normalize_roman("Главы IV и V были переработаны."),
            "Четвёртая и пятая главы были переработаны.",
        )
        self.assertEqual(
            normalize_roman("В главах IV и V описаны реформы."),
            "В четвёртой и пятой главах описаны реформы.",
        )
        self.assertEqual(
            normalize_roman("Из глав IV и V убрали примечания."),
            "Из четвёртой и пятой глав убрали примечания.",
        )
        self.assertEqual(
            normalize_roman("Разделы IV и V содержат примеры."),
            "Четвёртый и пятый разделы содержат примеры.",
        )
        self.assertEqual(
            normalize_roman("В разделах IV и V приведены примеры."),
            "В четвёртом и пятом разделах приведены примеры.",
        )
        self.assertEqual(
            normalize_roman("Из разделов IV и V убрали повторы."),
            "Из четвёртого и пятого разделов убрали повторы.",
        )
        self.assertEqual(
            normalize_roman("Главы IV-V были переработаны."),
            "Четвёртая — пятая главы были переработаны.",
        )
        self.assertEqual(
            normalize_roman("В главах IV-V описаны реформы."),
            "В четвёртой — пятой главах описаны реформы.",
        )
        self.assertEqual(
            normalize_roman("Из разделов IV-V убрали повторы."),
            "Из четвёртого — пятого разделов убрали повторы.",
        )
        self.assertEqual(
            normalize_roman("Главы IV, V и VI были переработаны."),
            "Четвёртая, пятая и шестая главы были переработаны.",
        )

    def test_roman_stage_keeps_plain_single_letter_and_normalizes_heading_context(self):
        self.assertEqual(
            normalize_roman("Буква V и глава IV."),
            "Буква V и глава четвёртая.",
        )

    def test_roman_stage_falls_back_cleanly_for_plain_and_unsupported_roman_tokens(self):
        self.assertEqual(normalize_roman("XVI"), "16")
        self.assertEqual(normalize_roman("MMXXIV"), "2024")
        self.assertEqual(normalize_roman("xiv"), "xiv")
        self.assertEqual(normalize_roman("XvI"), "XvI")
        self.assertEqual(normalize_roman("ХVI век"), "шестнадцатый век")
        self.assertEqual(normalize_roman("Дом XV и XVI"), "Дом 15 и 16")
        self.assertEqual(normalize_roman("Дом XV-XVI"), "Дом 15-16")
        self.assertEqual(normalize_roman("Глава XvI"), "Глава XvI")
        self.assertEqual(normalize_roman("IIII"), "IIII")
        self.assertEqual(normalize_roman("IIII-IV век"), "IIII-IV век")

    def test_roman_stage_respects_disabled_option(self):
        options = NormalizeOptions(enable_roman_normalization=False)
        self.assertEqual(normalize_roman("Глава IV.", options), "Глава IV.")

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
            normalize_numerals("глава 10"),
            "глава десятая",
        )
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
            normalize_numerals("раздел 3"),
            "раздел третий",
        )
        self.assertEqual(
            normalize_numerals("из раздела 3"),
            "из раздела третьего",
        )
        self.assertEqual(
            normalize_numerals("книга 2"),
            "книга вторая",
        )
        self.assertEqual(
            normalize_numerals("из книги 2"),
            "из книги второй",
        )
        self.assertEqual(
            normalize_numerals("часть 2"),
            "часть вторая",
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

    def test_preprocess_stage_expands_numeric_reference_abbreviations(self):
        normalizer = Normalizer()
        self.assertEqual(
            normalizer.run_stage(
                "preprocess",
                "ст. 15, рис. 2, табл. 3, с. 4, p. 5, стр. 6",
            ),
            "статья 15, рисунок 2, таблица 3, страница 4, страница 5, страница 6",
        )

    def test_preprocess_stage_expands_birth_year_and_mass_gram_abbreviations(self):
        normalizer = Normalizer()
        self.assertEqual(
            normalizer.run_stage("preprocess", "55 г.р. 55 г. р."),
            "55 г. рождения. 55 г. рождения.",
        )
        self.assertEqual(
            normalizer.run_stage("preprocess", "вес 123 г. масса 237г."),
            "вес 123 грамм масса 237 грамм",
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

    def test_abbreviation_stage_does_not_split_role_title_and_initial_from_surname(self):
        self.assertEqual(
            expand_abbreviations("Редактор Е. Харитонова", NormalizeOptions.tts()),
            "Редактор ее Харитонова.",
        )
        self.assertEqual(
            expand_abbreviations("Автор Ч. Рихтер", NormalizeOptions.tts()),
            "Автор чэ Рихтер.",
        )

    def test_abbreviation_stage_keeps_single_initial_lists_inside_sentence(self):
        self.assertEqual(
            expand_abbreviations(
                "Б. Кагарлицкий, П. Кудюкин, А. Фадин, Ю. Хавкин, В. Чернецкий, А. Шилков, а позже — М. Ривкин.",
                NormalizeOptions.tts(),
            ),
            "бэ Кагарлицкий, пэ Кудюкин, аа Фадин, юю Хавкин, вэ Чернецкий, аа Шилков, а позже — эм Ривкин.",
        )

    def test_abbreviation_stage_expands_generic_reference_and_legal_abbreviations(self):
        self.assertEqual(
            expand_abbreviations("табл."),
            "таблица",
        )
        self.assertEqual(
            expand_abbreviations("УК РФ"),
            "уголовный кодекс российской федерации",
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

    def test_year_stage_keeps_abbreviated_mass_contexts_out_of_year_rules(self):
        self.assertEqual(normalize_years("вес 123 г."), "вес 123 г.")
        self.assertEqual(normalize_years("масса 237 г."), "масса 237 г.")
        self.assertEqual(
            normalize_years("55 г. рождения."),
            "пятьдесят пятого года рождения.",
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
