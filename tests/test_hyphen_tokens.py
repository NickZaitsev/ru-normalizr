import unittest

from ru_normalizr import NormalizeOptions, normalize
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
        self.assertEqual(normalize("Z80A", options), "зи восемьдесят-э")

    def test_normalize_distinguishes_mixed_case_and_all_caps_latin_index_tokens(self):
        options = NormalizeOptions.tts()
        self.assertEqual(normalize("Stg-44", options), "стг-сорок четыре")
        self.assertEqual(normalize("STG-44", options), "эс ти джи-сорок четыре")


if __name__ == "__main__":
    unittest.main()
