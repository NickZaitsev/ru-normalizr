"""Branch coverage for the abbreviation stage: initials, adjectives, letter names.

The stage is exercised directly, as the README documents it as separately
usable. That also keeps the sentence-boundary decisions visible, which
`finalize` would otherwise smooth over.
"""

import unittest
from unittest.mock import patch

from ru_normalizr._morph import parse_word
from ru_normalizr.abbreviations import (
    expand_abbreviations,
    expand_letter_abbreviations,
    expand_person_initials,
)
from ru_normalizr.options import NormalizeOptions


def abbr(text: str) -> str:
    return expand_abbreviations(text, NormalizeOptions.tts())


class EtcAbbreviationTests(unittest.TestCase):
    def test_etc_forms_are_expanded(self):
        self.assertEqual(abbr("и т. д."), "и так далее.")
        self.assertEqual(abbr("и т.п."), "и тому подобное.")

    def test_terminal_dot_is_kept_before_a_capitalized_continuation(self):
        self.assertEqual(abbr("и т. д. Затем"), "и так далее. Затем")

    def test_terminal_dot_is_kept_before_a_lowercase_line_continuation(self):
        self.assertEqual(
            abbr("В отчёте перечислены цели, задачи и т. д.\nпродолжение следует."),
            "В отчёте перечислены цели, задачи и так далее.\nпродолжение следует.",
        )

    def test_terminal_dot_is_dropped_before_a_closing_quote(self):
        self.assertEqual(abbr("и т. д.»"), "и так далее»")

    def test_terminal_dot_is_kept_when_a_closing_mark_ends_the_sentence(self):
        # No space before the capital: the quotation itself ends the sentence, so
        # the abbreviation keeps the dot it would otherwise lend to the quote.
        self.assertEqual(abbr("и т. д.»Затем"), "и так далее.»Затем")
        self.assertEqual(abbr("и т. д.)Затем"), "и так далее.)Затем")


class AdjectiveAbbreviationTests(unittest.TestCase):
    def test_adjective_agrees_with_the_head_noun(self):
        cases = (
            ("гос. учреждение", "государственное учреждение"),
            ("в гос. учреждении", "в государственном учреждении"),
            ("междунар. организации", "международной организации"),
            ("полит. вопросы", "политические вопросы"),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(abbr(source), expected)

    def test_adjective_agrees_with_the_head_noun_inside_a_sentence(self):
        # The head noun is picked from the three words after the abbreviation, so
        # the words around it are what makes gender, number and case decidable.
        cases = (
            (
                "Приняли новый гос. стандарт качества.",
                "Приняли новый государственный стандарт качества.",
            ),
            ("Собрали междунар. группу учёных.", "Собрали международную группу учёных."),
            (
                "Издали офиц. письмо руководителя ведомства.",
                "Издали официальное письмо руководителя ведомства.",
            ),
            ("Изучаем юридич. последствия сделки.", "Изучаем юридические последствия сделки."),
            (
                "Отметили полит. волю руководства страны.",
                "Отметили политическую волю руководства страны.",
            ),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(abbr(source), expected)

    def test_animate_head_noun_takes_the_animate_accusative(self):
        # "защитника" and "наблюдателей" are accusative but animate, so the
        # adjective must not fall back to the nominative-looking inanimate form.
        self.assertEqual(
            abbr("Назначили гос. защитника обвиняемому."),
            "Назначили государственного защитника обвиняемому.",
        )
        self.assertEqual(
            abbr("Пригласили междунар. наблюдателей на выборы."),
            "Пригласили международных наблюдателей на выборы.",
        )

    def test_inanimate_head_noun_takes_the_inanimate_accusative(self):
        cases = (
            (
                "Подписали гос. контракт на поставку.",
                "Подписали государственный контракт на поставку.",
            ),
            (
                "Приняли гос. меры поддержки бизнеса.",
                "Приняли государственные меры поддержки бизнеса.",
            ),
            (
                "Отправили офиц. запросы всем участникам.",
                "Отправили официальные запросы всем участникам.",
            ),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(abbr(source), expected)

    def test_substantivized_adjective_can_be_the_head(self):
        cases = (
            (
                "Наградили гос. служащего медалью.",
                "Наградили государственного служащего медалью.",
            ),
            (
                "Опросили полит. заключённых колонии.",
                "Опросили политических заключённых колонии.",
            ),
            (
                "Помогли гос. служащему оформить документы.",
                "Помогли государственному служащему оформить документы.",
            ),
            (
                "Довольны гос. служащими отдела.",
                "Довольны государственными служащими отдела.",
            ),
            (
                "Гос. служащий подал заявление.",
                "Государственный служащий подал заявление.",
            ),
            (
                "Допросили полит. обвиняемого по делу.",
                "Допросили политического обвиняемого по делу.",
            ),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(abbr(source), expected)

    def test_substantivized_head_is_not_confused_with_its_modifiers(self):
        cases = (
            (
                "Наградили гос. бывшего служащего.",
                "Наградили государственного бывшего служащего.",
            ),
            (
                "Обсудили гос. новый проект.",
                "Обсудили государственный новый проект.",
            ),
            (
                "Проверили гос. официально зарегистрированную в реестре организацию.",
                "Проверили государственную официально зарегистрированную "
                "в реестре организацию.",
            ),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(abbr(source), expected)

    def test_contextual_abbreviation_parses_each_phrase_word_once(self):
        with patch("ru_normalizr.abbreviations.parse_word", wraps=parse_word) as mocked:
            abbr("Наградили гос. бывшего служащего медалью.")

        parsed_words = [call.args[0] for call in mocked.call_args_list]
        for word in ("бывшего", "служащего", "медалью"):
            with self.subTest(word=word):
                self.assertEqual(parsed_words.count(word), 1)

    def test_head_noun_is_found_past_an_intervening_adverb(self):
        # "очень" is neither an adjective nor a noun, so the scan has to walk
        # over it to reach "задачей" as the head.
        self.assertEqual(
            abbr("Работаем над гос. очень важной задачей."),
            "Работаем над государственной очень важной задачей.",
        )

    def test_capitalized_abbreviation_keeps_its_capital(self):
        self.assertEqual(abbr("Гос. учреждение"), "Государственное учреждение")

    def test_language_abbreviation_before_a_capitalized_word_is_left_alone(self):
        # "англ. Hello" introduces a source-language spelling, not an adjective
        # agreeing with a noun.
        for source in ("англ. Hello", "лат. Homo", "нем. Wort"):
            with self.subTest(source=source):
                self.assertEqual(abbr(source), source)

    def test_language_abbreviation_before_a_lowercase_noun_is_an_adjective(self):
        self.assertEqual(abbr("англ. слово"), "английское слово")

    def test_language_origin_after_a_preposition_becomes_a_noun_phrase(self):
        self.assertEqual(abbr("от англ. Hello"), "от английского Hello")
        self.assertEqual(abbr("с англ. Word"), "с английского Word")

    def test_language_origin_needs_a_non_cyrillic_word_after_it(self):
        # "от англ. слова" is an ordinary adjective phrase, not a source-language
        # note, so the adjective agrees with the noun instead.
        self.assertEqual(abbr("от англ. слова"), "от английского слова")

    def test_cyrillic_plural_after_language_abbreviation_keeps_adjective_agreement(self):
        self.assertEqual(
            abbr("Взяли примеры из англ. книг."),
            "Взяли примеры из английских книг.",
        )

    def test_head_without_a_case_leaves_the_adjective_in_its_lemma(self):
        # "и" has a noun reading (the letter name) but no case, so there is
        # nothing to agree with and the dictionary form is used as is.
        self.assertEqual(abbr("гос. и"), "государственный и")


class InitialsTests(unittest.TestCase):
    def test_surname_with_two_initials_at_the_end_of_a_sentence(self):
        self.assertEqual(abbr("Иванов А. Б."), "Иванов аа бэ.")

    def test_surname_with_two_initials_before_a_capitalized_continuation(self):
        self.assertEqual(abbr("Иванов А. Б. Затем"), "Иванов аа бэ. Затем")

    def test_existing_sentence_punctuation_is_not_doubled(self):
        self.assertEqual(abbr("Иванов А. Б.!"), "Иванов аа бэ!")

    def test_closing_bracket_does_not_make_the_name_non_final(self):
        self.assertEqual(abbr("Иванов А. Б.)"), "Иванов аа бэ.)")

    def test_closing_quote_does_not_make_the_name_non_final(self):
        # "»" is a closing mark; treating it as an opening one gave the
        # comma-separated non-final form instead.
        self.assertEqual(abbr("Иванов А. Б.»"), "Иванов аа бэ.»")

    def test_opening_quote_makes_the_name_non_final(self):
        self.assertEqual(abbr("Иванов А. Б. «текст»"), "Иванов, аа, бэ, «текст»")

    def test_lowercase_continuation_makes_the_name_non_final(self):
        self.assertEqual(abbr("Иванов А. Б. и Петров"), "Иванов, аа, бэ, и Петров")

    def test_initials_before_the_surname(self):
        self.assertEqual(abbr("А. Б. Иванов"), "аа бэ Иванов.")
        self.assertEqual(abbr("А. Б. Иванов пришёл"), "аа бэ Иванов пришёл")

    def test_single_initial_forms(self):
        self.assertEqual(abbr("Иванов А."), "Иванов аа.")
        self.assertEqual(abbr("А. Иванов"), "аа Иванов.")

    def test_single_initial_before_surname_preserves_terminal_marks(self):
        for mark in (".", "!", "?", "…"):
            with self.subTest(mark=mark):
                self.assertEqual(
                    abbr(f"Отчёт подготовил А. Иванов{mark}"),
                    f"Отчёт подготовил аа Иванов{mark}",
                )

    def test_existing_terminal_mark_is_never_doubled(self):
        # Each of the three name shapes decides the trailing dot on its own, so
        # every shape has to be checked against every sentence-final mark.
        for mark, expected_tail in ((".", "."), ("!", "!"), ("?", "?"), ("…", "…")):
            for template, expected in (
                ("Отчёт подготовил Иванов А. Б.{}", "Отчёт подготовил Иванов аа бэ{}"),
                ("Доклад читал А. Б. Иванов{}", "Доклад читал аа бэ Иванов{}"),
                ("Приказ подписал Иванов А.{}", "Приказ подписал Иванов аа{}"),
            ):
                text = template.format(mark)
                with self.subTest(text=text):
                    self.assertEqual(abbr(text), expected.format(expected_tail))

    def test_several_closing_marks_are_stripped_before_the_decision(self):
        # Both "»" and ")" have to be skipped to reach the lowercase "и", which
        # is what makes the name non-final here.
        self.assertEqual(
            abbr("Цитата: «Иванов А. Б.») и далее"),
            "Цитата: «Иванов, аа, бэ,») и далее",
        )

    def test_quotation_ending_the_sentence_keeps_the_dot(self):
        self.assertEqual(
            abbr("В книге: «Отчёт сдал Иванов А. Б.»"),
            "В книге: «Отчёт сдал Иванов аа бэ.»",
        )

    def test_closing_marks_are_stripped_one_at_a_time(self):
        # No space before the capital, so the character right after the closing
        # marks is what decides. Skipping the marks in the wrong steps would
        # read the "Д" as consumed and see a lowercase tail instead.
        self.assertEqual(
            abbr("В книге: «Отчёт сдал Иванов А. Б.»Далее следует вывод."),
            "В книге: «Отчёт сдал Иванов аа бэ.»Далее следует вывод.",
        )
        self.assertEqual(
            abbr("Цитата: «Иванов А. Б.»)Далее по тексту."),
            "Цитата: «Иванов аа бэ.»)Далее по тексту.",
        )

    def test_opening_bracket_makes_the_name_non_final(self):
        self.assertEqual(
            abbr("Автор — Иванов А. Б. (директор)"),
            "Автор — Иванов, аа, бэ, (директор)",
        )


class InitialsReadingModeTests(unittest.TestCase):
    """The stage function's own defaults, without the TTS profile on top.

    `NormalizeOptions.tts()` turns on both the doubled vowel names and the pause
    commas, so a bare call has to be asserted separately or the defaults are only
    ever exercised through the profile that overrides them.
    """

    SENTENCE = "Иванов А. Б. подписал акт."

    def test_defaults_read_single_vowels_without_pauses(self):
        self.assertEqual(
            expand_person_initials(self.SENTENCE), "Иванов а бэ подписал акт."
        )

    def test_double_vowel_mode_lengthens_the_vowel_letter_name(self):
        self.assertEqual(
            expand_person_initials(self.SENTENCE, vowel_mode="double"),
            "Иванов аа бэ подписал акт.",
        )

    def test_comma_pause_mode_separates_the_initials(self):
        self.assertEqual(
            expand_person_initials(self.SENTENCE, pause_mode="comma"),
            "Иванов, а, бэ, подписал акт.",
        )

    def test_both_modes_combine(self):
        self.assertEqual(
            expand_person_initials(
                self.SENTENCE, vowel_mode="double", pause_mode="comma"
            ),
            "Иванов, аа, бэ, подписал акт.",
        )


class LetterAbbreviationTests(unittest.TestCase):
    def test_letter_by_letter_reading_for_russian_acronyms(self):
        cases = (
            ("ЭВМ", "э вэ эм"),
            ("СССР", "эс эс эс эр"),
            ("РФ", "эр эф"),
            ("ФБР", "эф бэ эр"),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(expand_letter_abbreviations(source), expected)

    def test_letter_by_letter_reading_for_latin_acronyms(self):
        self.assertEqual(expand_letter_abbreviations("ABC"), "эй би си")
        self.assertEqual(expand_letter_abbreviations("FBI"), "эф би ай")

    def test_vowel_mode_applies_to_generated_cyrillic_and_latin_readings(self):
        cases = (
            (
                "А.Е.Ё.И.О.У.Ы.Э.Ю.Я.",
                "а е ё и о у ы э ю я.",
                "аа ее ё ии оо уу ыы ээ юю яя.",
            ),
            ("EU", "и ю", "ии юю"),
            ("BUD", "би ю ди", "би юю ди"),
        )
        for source, single, double in cases:
            with self.subTest(source=source):
                self.assertEqual(
                    expand_letter_abbreviations(source, vowel_mode="single"), single
                )
                self.assertEqual(
                    expand_letter_abbreviations(source, vowel_mode="double"), double
                )

    def test_vowel_mode_applies_to_standalone_letters_in_known_readings(self):
        cases = (
            ("США", "сэ шэ а", "сэ шэ аа"),
            ("ООН", "о он", "оо он"),
            ("ГРУ", "гэ рэ у", "гэ рэ уу"),
            ("УССР", "у эс эс эр", "уу эс эс эр"),
            ("ЕЭС", "е э эс", "ее ээ эс"),
            ("ЕС", "е эс", "ее эс"),
            ("НБА", "эн бэ а", "эн бэ аа"),
            ("ВТО", "вэ тэ о", "вэ тэ оо"),
            ("АЗС", "а зэ эс", "аа зэ эс"),
            ("ОАО", "о а о", "оо аа оо"),
            ("ЗАО", "зз а о", "зз аа оо"),
            ("ООО", "о о о", "оо оо оо"),
            ("ИП", "и пэ", "ии пэ"),
            ("ГБУ", "гэ бэ у", "гэ бэ уу"),
            ("МБУ", "эм бэ у", "эм бэ уу"),
            ("ФГБУ", "эф гэ бэ у", "эф гэ бэ уу"),
            ("НИИ", "ни и", "ни ии"),
            ("ПТУ", "пэ тэ у", "пэ тэ уу"),
            ("ГТО", "гэ тэ о", "гэ тэ оо"),
            ("USB", "ю эс би", "юю эс би"),
            ("ОРЗ", "о эр зэ", "оо эр зэ"),
        )
        for source, single, double in cases:
            with self.subTest(source=source):
                self.assertEqual(
                    expand_letter_abbreviations(source, vowel_mode="single"), single
                )
                self.assertEqual(
                    expand_letter_abbreviations(source, vowel_mode="double"), double
                )

    def test_known_acronym_uses_its_dictionary_reading(self):
        cases = (("ВУЗ", "вуз"), ("НАТО", "нато"), ("АЭС", "аэс"))
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(expand_letter_abbreviations(source), expected)

    def test_dotted_known_acronym_keeps_its_terminal_dot(self):
        # The dotted spelling carries the sentence dot in its own last position,
        # so the dictionary reading has to give it back.
        cases = (
            ("Флаг подняли в С.Ш.А.", "Флаг подняли в сэ шэ а."),
            ("Договор подписан в С.С.С.Р.", "Договор подписан в эс эс эс эр."),
            ("Он вступил в Н.А.Т.О.", "Он вступил в нато."),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(expand_letter_abbreviations(source), expected)

    def test_dotless_known_acronym_gains_no_dot(self):
        self.assertEqual(
            expand_letter_abbreviations("Он вступил в НАТО"), "Он вступил в нато"
        )

    def test_trailing_dot_is_preserved(self):
        self.assertEqual(expand_letter_abbreviations("ЭВМ."), "э вэ эм.")

    def test_single_letter_is_too_short_to_be_an_acronym(self):
        self.assertEqual(expand_letter_abbreviations("А"), "А")

    def test_all_caps_real_word_is_not_read_letter_by_letter(self):
        # Emphasis in caps is common in prose, so a token that is a real word
        # must survive it.
        for source in ("КОТ", "ДОМ", "МИР"):
            with self.subTest(source=source):
                self.assertEqual(expand_letter_abbreviations(source), source)

    def test_overlong_latin_run_is_left_untouched(self):
        self.assertEqual(expand_letter_abbreviations("ABCDEFG"), "ABCDEFG")

    def test_overlong_cyrillic_run_is_left_untouched(self):
        # Note this run never reaches the length limit: pymorphy reads "ждкфпч"
        # as an ordinary noun without the Abbr grammeme, so the real-word guard
        # rejects it first. The length limit itself is pinned from the reachable
        # side by test_run_at_the_cyrillic_length_limit_is_still_spelled_out.
        self.assertEqual(expand_letter_abbreviations("ЖДКФПЧ"), "ЖДКФПЧ")

    def test_dictionary_reading_wins_before_any_heuristic(self):
        # A known abbreviation is answered from the table, ahead of the real-word,
        # length and vowel guards. ABBREV_MAX_LEN_RU is in practice unreachable
        # for real five-letter acronyms for exactly this reason: they are either
        # in the table or rejected by the guards before the limit is consulted.
        self.assertEqual(expand_letter_abbreviations("ВЛКСМ"), "вэ эл ка эс эм")
        self.assertEqual(expand_letter_abbreviations("ГИБДД"), "ги бэ дэ дэ")

    def test_vowel_heavy_cyrillic_run_is_left_untouched(self):
        # More than one vowel means it is probably pronounceable as a word.
        self.assertEqual(expand_letter_abbreviations("АЕИ"), "АЕИ")
        self.assertEqual(expand_letter_abbreviations("ОАЭ"), "ОАЭ")

    def test_exactly_two_vowels_already_look_like_a_word(self):
        # The boundary of the vowel rule: two is already "more than one", so a
        # run like this stays as written and gets read naturally.
        self.assertEqual(expand_letter_abbreviations("ЮАР"), "ЮАР")

    def test_run_at_the_latin_length_limit_is_still_spelled_out(self):
        self.assertEqual(expand_letter_abbreviations("HTTPS"), "эйч ти ти пи эс")

    def test_latin_run_one_letter_past_the_limit_is_left_untouched(self):
        self.assertEqual(expand_letter_abbreviations("GITHUB"), "GITHUB")

    def test_dotted_form_bypasses_the_length_and_vowel_limits(self):
        # The dots themselves say it is an abbreviation, so the heuristics that
        # protect vowel-heavy ordinary words are not applied.
        self.assertEqual(expand_letter_abbreviations("А.Е.И."), "а е и.")

    def test_lowercase_dotted_form_is_not_an_acronym(self):
        self.assertEqual(expand_letter_abbreviations("и.о."), "и.о.")

    def test_mixed_script_token_is_left_untouched(self):
        self.assertEqual(expand_letter_abbreviations("АBC"), "АBC")


class AmpersandTests(unittest.TestCase):
    """"X & Y" reads as "энд" for brands and as "и" for Russian text.

    The whole decision rests on which script each side is written in, so the
    boundary letters of both alphabets are asserted here as well.
    """

    LATINIZING = NormalizeOptions(enable_latinization=True)

    def test_two_latin_words_read_the_ampersand_as_end(self):
        self.assertEqual(
            expand_abbreviations("Rockwell & Co открыли филиал", self.LATINIZING),
            "Rockwell энд Co открыли филиал",
        )

    def test_ampersand_between_latin_words_is_kept_without_latinization(self):
        # Nothing will read the Latin out, so spelling the ampersand in Russian
        # would leave a half-translated phrase.
        self.assertEqual(
            expand_abbreviations("Rockwell & Co открыли филиал", NormalizeOptions()),
            "Rockwell & Co открыли филиал",
        )

    def test_cyrillic_neighbours_read_the_ampersand_as_the_russian_conjunction(self):
        self.assertEqual(
            expand_abbreviations("Маша & Петя пришли", self.LATINIZING),
            "Маша и Петя пришли",
        )

    def test_one_cyrillic_side_is_enough_for_the_russian_conjunction(self):
        self.assertEqual(
            expand_abbreviations("Маша & Co подписали договор", self.LATINIZING),
            "Маша и Co подписали договор",
        )

    def test_boundary_latin_letters_still_count_as_latin(self):
        # The check is a pair of range comparisons, so the first and last letter
        # of each case must fall inside it.
        for text, expected in (
            ("A & B поставили подписи", "A энд B поставили подписи"),
            ("Z & Q остались в списке", "Z энд Q остались в списке"),
            ("a & q в сноске", "a энд q в сноске"),
            ("z & y в примечании", "z энд y в примечании"),
        ):
            with self.subTest(text=text):
                self.assertEqual(expand_abbreviations(text, self.LATINIZING), expected)

    def test_boundary_cyrillic_letters_still_count_as_cyrillic(self):
        # "Ё" and "ё" sit outside the А-я range and need their own check.
        for text, expected in (
            ("Пункты Ё & Я согласованы", "Пункты Ё и Я согласованы"),
            ("Схемы А & я в приложении", "Схемы А и я в приложении"),
            ("Отделы ё & Ю закрыты", "Отделы ё и Ю закрыты"),
        ):
            with self.subTest(text=text):
                self.assertEqual(expand_abbreviations(text, self.LATINIZING), expected)

    def test_english_letter_name_pulls_in_the_end_reading(self):
        # An already-transliterated letter name counts as English, so the pair
        # keeps reading as a brand rather than switching to "и".
        for text, expected in (
            ("би & си в таблице", "би энд си в таблице"),
            ("би & Rockwell в списке", "би энд Rockwell в списке"),
        ):
            with self.subTest(text=text):
                self.assertEqual(expand_abbreviations(text, self.LATINIZING), expected)


if __name__ == "__main__":
    unittest.main()
