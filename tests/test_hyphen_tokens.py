import unittest

from ru_normalizr import NormalizeOptions, normalize
from ru_normalizr.latinization import apply_latinization
from ru_normalizr.numerals import simple_tokenize


class RuNormalizrHyphenTokenTests(unittest.TestCase):
    def test_tokenizer_keeps_letter_digit_hyphenated_tokens_whole(self):
        self.assertEqual(simple_tokenize("COVID-19"), ["COVID-19"])
        self.assertEqual(simple_tokenize("Т-34"), ["Т-34"])
        self.assertEqual(simple_tokenize("52-G"), ["52-G"])
        self.assertEqual(simple_tokenize("80-A"), ["80-A"])

    def test_tokenizer_still_splits_numeric_suffix_forms(self):
        self.assertEqual(simple_tokenize("1980-е"), ["1980", "-", "е"])
        self.assertEqual(simple_tokenize("5-й"), ["5", "-", "й"])

    def test_normalize_preserves_hyphen_in_letter_digit_compounds(self):
        options = NormalizeOptions.tts()
        self.assertEqual(normalize("COVID-19", options), "ковид-девятнадцать")
        self.assertEqual(normalize("Т-34", options), "Т-тридцать четыре")
        self.assertEqual(normalize("B52G", options), "би пятьдесят два-джи")
        self.assertEqual(normalize("Z80A", options), "зи восемьдесят-эй")

    def test_latinization_reads_alphanumeric_suffixes_as_letter_names(self):
        self.assertEqual(
            apply_latinization(
                "модель-восемьдесят-A",
                backend="dictionary",
            ),
            "модель-восемьдесят-эй",
        )

    def test_latinization_applies_vowel_mode_to_alphanumeric_suffixes(self):
        cases = (("single", "модель-восемьдесят-ю"), ("double", "модель-восемьдесят-юю"))
        for vowel_mode, expected in cases:
            with self.subTest(vowel_mode=vowel_mode):
                self.assertEqual(
                    apply_latinization(
                        "модель-восемьдесят-U",
                        backend="dictionary",
                        letter_vowel_mode=vowel_mode,
                    ),
                    expected,
                )

    def test_normalize_distinguishes_mixed_case_and_all_caps_latin_index_tokens(self):
        options = NormalizeOptions.tts()
        self.assertEqual(normalize("Stg-44", options), "стг-сорок четыре")
        self.assertEqual(normalize("STG-44", options), "эс ти джи-сорок четыре")

    def test_number_glued_to_an_unknown_tail_is_separated_by_a_space(self):
        """Дефис — утверждение о связи; для неизвестного хвоста его нет.

        Латинские буквы читаются по названиям, поэтому дефис доходил до вывода
        («сто-писиз»). Разбор цифры, подменившей букву при наборе, дефис
        сохраняет: «3аклятые» лучше прочесть одним словом.
        """
        options = NormalizeOptions.tts()
        cases = (
            ("Купил 100pcs товара.", "Купил сто писиз товара."),
            ("Версия 3beta вышла вчера.", "Версия три бейтэ вышла вчера."),
            ("Осталось 5кркр штук.", "Осталось пять кркр штук."),
            ("Он взял 3аклятые письма.", "Он взял трёхаклятые письма."),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                self.assertEqual(normalize(source, options), expected)


if __name__ == "__main__":
    unittest.main()
