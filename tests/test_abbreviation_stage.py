"""Branch coverage for the abbreviation stage: initials, adjectives, letter names.

The stage is exercised directly, as the README documents it as separately
usable. That also keeps the sentence-boundary decisions visible, which
`finalize` would otherwise smooth over.
"""

import unittest

from ru_normalizr.abbreviations import expand_abbreviations, expand_letter_abbreviations
from ru_normalizr.options import NormalizeOptions


def abbr(text: str) -> str:
    return expand_abbreviations(text, NormalizeOptions.tts())


class EtcAbbreviationTests(unittest.TestCase):
    def test_etc_forms_are_expanded(self):
        self.assertEqual(abbr("и т. д."), "и так далее.")
        self.assertEqual(abbr("и т.п."), "и тому подобное.")

    def test_terminal_dot_is_kept_before_a_capitalized_continuation(self):
        self.assertEqual(abbr("и т. д. Затем"), "и так далее. Затем")

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

    def test_known_acronym_uses_its_dictionary_reading(self):
        cases = (("ВУЗ", "вуз"), ("НАТО", "нато"), ("АЭС", "аэс"))
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(expand_letter_abbreviations(source), expected)

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
