import unittest

from ru_normalizr import NormalizeOptions, normalize
from ru_normalizr.latinization import apply_latinization
from ru_normalizr.numerals import get_numeral_case, simple_tokenize


class RuNormalizrRegressionTests(unittest.TestCase):
    def test_thousands_abbreviation_does_not_force_prepositional_case_after_na(self):
        tokens = simple_tokenize("выписал чек на сумму 100 тыс. долл.")
        self.assertEqual(get_numeral_case(tokens, tokens.index("100")), "accs")

    def test_normalize_amount_with_thousands_abbreviation_after_na_summu(self):
        self.assertEqual(
            normalize(
                "Энди Бехтольшайм, заинтересовавшийся этим проектом, сразу же выписал чек на сумму 100 тыс. долл."
            ),
            "Энди Бехтольшайм, заинтересовавшийся этим проектом, сразу же выписал чек на сумму сто тысяч долларов",
        )

    def test_dictionary_latinization_regressions_keep_current_duplicate_rule_behavior(self):
        options = NormalizeOptions(enable_latinization=True, latinization_backend="dictionary")

        self.assertEqual(
            apply_latinization("engineering", enabled=True, backend="dictionary"),
            "энджинИаинг",
        )
        self.assertEqual(
            apply_latinization("school", enabled=True, backend="dictionary"),
            "скул",
        )
        self.assertEqual(
            apply_latinization("server", enabled=True, backend="dictionary"),
            "сеарвэ",
        )
        self.assertEqual(normalize("engineering", options), "энджинИаинг")


if __name__ == "__main__":
    unittest.main()
