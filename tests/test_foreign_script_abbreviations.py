import unittest

from ru_normalizr import normalize


class RuNormalizrForeignScriptTests(unittest.TestCase):
    def test_normalize_preserves_full_greek_words(self):
        self.assertEqual(
            normalize("Элемент назвали от греч. αστατος – неустойчивый."),
            "Элемент назвали от греческого αστατος — неустойчивый.",
        )

    def test_normalize_expands_language_origin_before_ascii_words(self):
        self.assertEqual(
            normalize("Слово происходит от лат. homo."),
            "Слово происходит от латинского homo.",
        )

    def test_normalize_keeps_standalone_greek_symbols_readable(self):
        self.assertEqual(
            normalize("Угол α и слово αστατος."),
            "Угол альфа и слово αστατος.",
        )


if __name__ == "__main__":
    unittest.main()
