"""Branch coverage for the ordinal stage: headings, compound adjectives, hyphens.

Each stage function is exercised directly, because the case and gender decisions
they make are invisible in the finished sentence once later stages have run. The
stage returns a trailing space after a rendered ordinal; `finalize` collapses it,
so the expectations below keep it.
"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

import num2words

from ru_normalizr.numerals import ordinals
from ru_normalizr.numerals.ordinals import (
    _heading_parse,
    normalize_compound_numeric_adjectives,
    normalize_heading_numbers,
    normalize_heading_ranges,
    normalize_hyphenated_words,
    normalize_ordinals,
)


class HeadingParseTests(unittest.TestCase):
    def test_head_that_is_not_a_noun_has_no_parse(self):
        self.assertIsNone(_heading_parse("быстро 3-5", 0, "быстро"))

    def test_unambiguous_head_resolves_to_nominative_singular(self):
        parse = _heading_parse("глава 5", 0, "глава")

        self.assertIsNotNone(parse)
        assert parse is not None
        self.assertEqual(parse.tag.case, "nomn")
        self.assertEqual(parse.tag.gender, "femn")

    def test_ambiguous_head_without_context_has_no_parse(self):
        # "главы" is genitive singular or nominative plural; with nothing on the
        # left there is no way to choose, so the caller must fall back.
        self.assertIsNone(_heading_parse("главы 3-5", 0, "главы"))

    def test_ambiguous_head_resolves_from_the_preposition_on_the_left(self):
        parse = _heading_parse("из главы 3-5", 3, "главы")

        self.assertIsNotNone(parse)
        assert parse is not None
        self.assertEqual(parse.tag.case, "gent")

    def test_ambiguous_head_with_a_context_case_it_has_no_form_for(self):
        # "к" asks for the dative, which "главы" cannot be.
        self.assertIsNone(_heading_parse("к главы 3-5", 2, "главы"))


class HeadingRangeTests(unittest.TestCase):
    def test_range_with_a_resolvable_head_agrees_in_case_and_number(self):
        self.assertEqual(
            normalize_heading_ranges("из главы 3-5"),
            "из глав с третьей по пятую",
        )
        self.assertEqual(
            normalize_heading_ranges("о части 2-4"),
            "о частях со второй по четвёртую",
        )

    def test_every_context_word_decides_the_case_of_an_ambiguous_head(self):
        # "части" is genitive singular, nominative plural and accusative plural
        # at once, so the word in front of it is the only thing that picks the
        # case — and the choice surfaces in the plural head of the rendered
        # range: "частях" (loct), "частям" (datv), "частей" (gent), "части"
        # (accs). Every entry of HEADING_CONTEXT_CASES that can occur before one
        # of the six ambiguous heads is listed here; "во", "об", "обо", "ко" and
        # "со" cannot, as none of those heads begins with a vowel or a cluster
        # that would call for the long form.
        cases = (
            (
                "Требование указано в части 3-5 регламента.",
                "Требование указано в частях с третьей по пятую регламента.",
            ),
            ("Спорят о части 3-5 договора.", "Спорят о частях с третьей по пятую договора."),
            (
                "Ссылка дана при части 3-5 отчёта.",
                "Ссылка дана при частях с третьей по пятую отчёта.",
            ),
            (
                "Перейдите к части 3-5 инструкции.",
                "Перейдите к частям с третьей по пятую инструкции.",
            ),
            (
                "Замечания распределены по части 3-5 плана.",
                "Замечания распределены по частям с третьей по пятую плана.",
            ),
            ("Начните с части 3-5 учебника.", "Начните с частей с третьей по пятую учебника."),
            (
                "Цитата взята из части 3-5 монографии.",
                "Цитата взята из частей с третьей по пятую монографии.",
            ),
            (
                "Прочитайте до части 3-5 включительно.",
                "Прочитайте до частей с третьей по пятую включительно.",
            ),
            (
                "Отсчёт идёт от части 3-5 текста.",
                "Отсчёт идёт от частей с третьей по пятую текста.",
            ),
            ("Ответа нет у части 3-5 задания.", "Ответа нет у частей с третьей по пятую задания."),
            (
                "Книга издана без части 3-5 приложения.",
                "Книга издана без частей с третьей по пятую приложения.",
            ),
            (
                "Выводы идут после части 3-5 отчёта.",
                "Выводы идут после частей с третьей по пятую отчёта.",
            ),
            (
                "Пояснения написаны для части 3-5 курса.",
                "Пояснения написаны для частей с третьей по пятую курса.",
            ),
            (
                "Правки внесены около части 3-5 рукописи.",
                "Правки внесены около частей с третьей по пятую рукописи.",
            ),
            (
                "Схема размещена возле части 3-5 чертежа.",
                "Схема размещена возле частей с третьей по пятую чертежа.",
            ),
            (
                "Комментарии собраны вокруг части 3-5 закона.",
                "Комментарии собраны вокруг частей с третьей по пятую закона.",
            ),
            (
                "Проверено всё кроме части 3-5 приложения.",
                "Проверено всё кроме частей с третьей по пятую приложения.",
            ),
            (
                "Начало части 3-5 переписано заново.",
                "Начало частей с третьей по пятую переписано заново.",
            ),
            (
                "Конец части 3-5 сокращён редактором.",
                "Конец частей с третьей по пятую сокращён редактором.",
            ),
            (
                "Середина части 3-5 утеряна при печати.",
                "Середина частей с третьей по пятую утеряна при печати.",
            ),
            (
                "Подробности см части 3-5 приложения.",
                "Подробности см части с третьей по пятую приложения.",
            ),
            (
                "Подробности смотри части 3-5 приложения.",
                "Подробности смотри части с третьей по пятую приложения.",
            ),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(normalize_heading_ranges(source), expected)

    def test_capitalized_head_stays_capitalized_after_inflection(self):
        self.assertEqual(
            normalize_heading_ranges("Из Главы 3-5"),
            "Из Глав с третьей по пятую",
        )

    def test_accusative_head_falls_back_to_a_plural_only_form(self):
        # "см." asks for the accusative, which "главы" only has in the plural,
        # so the singular-first lookup must fall through.
        self.assertEqual(
            normalize_heading_ranges("см. главы 3-5"),
            "см. главы с третьей по пятую",
        )

    def test_unresolvable_head_is_left_as_written_and_defaults_to_masculine(self):
        self.assertEqual(
            normalize_heading_ranges("главы 3-5"),
            "главы с третьего по пятый",
        )
        self.assertEqual(
            normalize_heading_ranges("к главы 3-5"),
            "к главы с третьего по пятый",
        )

    def test_head_that_cannot_be_pluralized_is_left_as_written(self):
        stub = SimpleNamespace(
            tag=SimpleNamespace(case="nomn", gender="femn"),
            inflect=lambda _tags: None,
        )
        with patch.object(ordinals, "_heading_parse", return_value=stub):
            result = normalize_heading_ranges("главы 3-5")

        self.assertEqual(result, "главы с третьей по пятую")

    def test_preposition_becomes_so_before_a_sibilant_ordinal(self):
        self.assertEqual(
            normalize_heading_ranges("тома 2-3"),
            "тома со второго по третий",
        )
        self.assertEqual(
            normalize_heading_ranges("Книги 1-2"),
            "Книги с первого по второй",
        )

    def test_abbreviated_range_expands_the_head_and_follows_context(self):
        self.assertEqual(
            normalize_heading_ranges("гл. 3-5"),
            "главы с третьей по пятую",
        )
        self.assertEqual(
            normalize_heading_ranges("в гл. 3-5"),
            "в главах с третьей по пятую",
        )

    def test_abbreviated_range_is_left_alone_when_the_head_cannot_be_parsed(self):
        with patch.object(ordinals, "parse_word", return_value=()):
            self.assertEqual(normalize_heading_ranges("гл. 3-5"), "гл. 3-5")

    def test_abbreviated_range_is_left_alone_when_the_head_cannot_be_pluralized(self):
        stub = SimpleNamespace(
            tag=SimpleNamespace(case="nomn", gender="femn"),
            inflect=lambda _tags: None,
        )
        stub.tag.__contains__ = lambda _self, _item: True
        with patch.object(ordinals, "parse_word", return_value=(_AlwaysTagged(),)):
            self.assertEqual(normalize_heading_ranges("гл. 3-5"), "гл. 3-5")


class _AlwaysTagged:
    """A parse that claims every grammeme but refuses to inflect."""

    class _Tag:
        case = "nomn"
        gender = "femn"

        def __contains__(self, _item: str) -> bool:
            return True

    tag = _Tag()

    def inflect(self, _tags):
        return None


class HeadingNumberTests(unittest.TestCase):
    def test_single_heading_agrees_with_the_head(self):
        self.assertEqual(normalize_heading_numbers("Глава 5"), "Глава пятая")
        self.assertEqual(normalize_heading_numbers("в главе 5"), "в главе пятой")
        self.assertEqual(normalize_heading_numbers("квартал 4"), "квартал четвёртый")

    def test_ambiguous_head_without_context_is_left_untouched(self):
        self.assertEqual(normalize_heading_numbers("части 3"), "части 3")

    def test_abbreviated_heading_follows_the_preposition_on_the_left(self):
        self.assertEqual(normalize_heading_numbers("гл. 5"), "глава пятая")
        self.assertEqual(normalize_heading_numbers("в гл. 5"), "в главе пятой")
        self.assertEqual(normalize_heading_numbers("см. гл. 5"), "см. главу пятую")

    def test_abbreviated_heading_is_left_alone_when_the_head_cannot_be_parsed(self):
        with patch.object(ordinals, "parse_word", return_value=()):
            self.assertEqual(normalize_heading_numbers("гл. 5"), "гл. 5")

    def test_abbreviated_heading_is_left_alone_when_the_head_cannot_be_inflected(self):
        with patch.object(ordinals, "parse_word", return_value=(_AlwaysTagged(),)):
            self.assertEqual(normalize_heading_numbers("гл. 5"), "гл. 5")


class CompoundAdjectiveTests(unittest.TestCase):
    def test_small_numerals_use_their_fixed_prefix(self):
        cases = (
            ("1 комнатная", "однокомнатная"),
            ("2 тонный", "двухтонный"),
            ("3 комнатная", "трёхкомнатная"),
            ("4 этажный", "четырёхэтажный"),
            ("5 местный", "пятиместный"),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(
                    normalize_compound_numeric_adjectives(source), expected
                )

    def test_every_stem_forms_its_compound_adjective(self):
        # One adjective per entry of COMPOUND_ADJECTIVE_STEMS, so a change to the
        # pattern cannot silently drop a stem.
        cases = (
            ("3 комнатная", "трёхкомнатная"),
            ("5 тонный", "пятитонный"),
            ("2 местная", "двухместная"),
            ("3 ступенчатый", "трёхступенчатый"),
            ("9 этажный", "девятиэтажный"),
            ("100 кратный", "стократный"),
            ("2 дневный", "двухдневный"),
            ("7 часовой", "семичасовой"),
            ("90 летний", "девяносталетний"),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(
                    normalize_compound_numeric_adjectives(source), expected
                )

    def test_counted_noun_is_not_glued_into_a_compound(self):
        # A stem must only fire on an adjective. These are plain counted nouns
        # whose forms start the same way ("лет" under "летн", "дней" under
        # "дневн"), and gluing them would destroy the sentence.
        for source in (
            "Отчёт за 7 лет.",
            "Прошло 5 дней.",
            "Осталось 3 ступени.",
            "Взял 2 места.",
            "Снял 3 комнаты.",
            "Дом в 9 этажей.",
            "Разница в 4 раза.",
        ):
            with self.subTest(source=source):
                self.assertEqual(normalize_compound_numeric_adjectives(source), source)

    def test_ninety_keeps_its_nominative_stem_inside_a_compound(self):
        # The genitive "девяноста" is wrong as a prefix; "девяносто" is the stem.
        self.assertEqual(
            normalize_compound_numeric_adjectives("90 летний"), "девяносталетний"
        )
        self.assertEqual(
            normalize_compound_numeric_adjectives("95 летний"),
            "девяностопятилетний",
        )

    def test_one_hundred_uses_the_short_stem(self):
        self.assertEqual(
            normalize_compound_numeric_adjectives("100 кратный"), "стократный"
        )

    def test_explicit_hyphen_suffix_is_absorbed(self):
        self.assertEqual(
            normalize_compound_numeric_adjectives("2-х комнатная"), "двухкомнатная"
        )
        self.assertEqual(
            normalize_compound_numeric_adjectives("3-и ступенчатый"),
            "трёхступенчатый",
        )

    def test_percent_compound_keeps_the_adjective_ending(self):
        cases = (
            ("25%-ный", "двадцатипятипроцентный"),
            ("1%-ная", "однопроцентная"),
            ("50%-ных", "пятидесятипроцентных"),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(
                    normalize_compound_numeric_adjectives(source), expected
                )


class HyphenatedWordTests(unittest.TestCase):
    def test_measurement_units_keep_their_hyphen(self):
        # "5-км" is a unit link, not an ordinal, and a later stage handles it.
        self.assertEqual(normalize_hyphenated_words("5-км"), "5-км")
        self.assertEqual(normalize_hyphenated_words("10-кг"), "10-кг")

    def test_ordinal_suffixes_are_left_to_the_ordinal_stage(self):
        self.assertEqual(normalize_hyphenated_words("5-ый"), "5-ый")
        self.assertEqual(normalize_hyphenated_words("5-й"), "5-й")

    def test_dative_suffix_u_is_left_to_the_ordinal_stage(self):
        self.assertEqual(normalize_hyphenated_words("5-у"), "5-у")

    def test_short_ordinal_suffix_above_one_hundred_is_left_untouched(self):
        # Beyond 100 a bare "-й" is far more likely a model or serial number.
        self.assertEqual(normalize_hyphenated_words("120-й"), "120-й")
        self.assertEqual(normalize_hyphenated_words("101-ого"), "101-ого")

    def test_case_suffix_above_one_hundred_is_left_untouched(self):
        # Same rule for the case suffixes that reach this guard: "120-х" reads as
        # an identifier, while "20-х" is still expanded.
        self.assertEqual(normalize_hyphenated_words("120-х"), "120-х")
        self.assertEqual(normalize_hyphenated_words("200-ми"), "200-ми")
        self.assertEqual(normalize_hyphenated_words("20-х"), "двадцати")

    def test_genitive_suffix_renders_the_genitive(self):
        self.assertEqual(normalize_hyphenated_words("5-ти лет"), "пяти лет")

    def test_instrumental_suffixes_render_the_instrumental(self):
        self.assertEqual(normalize_hyphenated_words("2-мя годами"), "двумя годами")
        self.assertEqual(normalize_hyphenated_words("7-мя"), "семью")

    def test_ambiguous_suffix_h_takes_the_case_from_context(self):
        # "-х" is genitive or locative; the surrounding words decide, and
        # anything else falls back to the genitive.
        self.assertEqual(normalize_hyphenated_words("около 5-х"), "около пяти")
        self.assertEqual(normalize_hyphenated_words("5-х"), "пяти")

    def test_adjective_right_hand_side_is_glued_into_one_word(self):
        self.assertEqual(normalize_hyphenated_words("10-кратный"), "десятикратный")
        self.assertEqual(normalize_hyphenated_words("5-дневный"), "пятидневный")

    def test_long_noun_right_hand_side_keeps_a_space(self):
        self.assertEqual(normalize_hyphenated_words("5-процентов"), "пять процентов")
        self.assertEqual(normalize_hyphenated_words("5-метров"), "пять метров")


class OrdinalCardinalSuffixTests(unittest.TestCase):
    def test_cardinal_suffix_without_a_noun_renders_a_cardinal(self):
        self.assertEqual(normalize_ordinals("5-ти"), "пять ")
        self.assertEqual(normalize_ordinals("5-ми"), "пять ")

    def test_cardinal_suffix_is_left_untouched_when_the_backend_fails(self):
        with patch.object(
            num2words, "num2words", side_effect=RuntimeError("backend is broken")
        ):
            self.assertEqual(normalize_ordinals("5-ти"), "5-ти")

    def test_suffix_u_renders_an_accusative_agreeing_with_the_noun(self):
        self.assertEqual(normalize_ordinals("5-у"), "пять ")

    def test_ordinal_before_a_month_stays_neuter_nominative(self):
        self.assertEqual(normalize_ordinals("20-е мая"), "двадцатое  мая")
        self.assertEqual(normalize_ordinals("1-ое января"), "первое  января")

    def test_ordinal_agrees_with_the_noun_on_the_right(self):
        self.assertEqual(normalize_ordinals("5-й дом"), "пятый  дом")
        self.assertEqual(normalize_ordinals("3-ее место"), "третье  место")

    def test_ordinal_agrees_with_a_name_on_the_left(self):
        self.assertEqual(normalize_ordinals("Иван 4-й"), "Иван четвёртый ")


if __name__ == "__main__":
    unittest.main()
