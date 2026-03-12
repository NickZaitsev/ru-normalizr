import unittest

from ru_normalizr import NormalizeOptions, normalize
from ru_normalizr.latinization import apply_latinization
from ru_normalizr.numerals import get_numeral_case, simple_tokenize


class RuNormalizrRegressionTests(unittest.TestCase):
    def test_dictionary_latinization_expected_output_for_long_english_text(self):
        text = (
            "Windows Server updates improve browser security, download archives, "
            "and home page access for mobile devices."
        )

        self.assertEqual(
            apply_latinization(text, enabled=True, backend="dictionary"),
            "виндаус сервэр апдэйтс импров браусэр секюрити, даунлооад "
            "аркхивэс, энд хоум пэйдж эксесс фор мобил дэвисес.",
        )

    def test_dictionary_latinization_rewrites_all_ascii_letters_in_long_english_text(self):
        text = (
            "Windows Server updates improve browser security, download archives, "
            "and home page access for mobile devices. Creative teams write code, "
            "share knowledge, monitor metrics, and support online services for "
            "global users."
        )

        result = apply_latinization(text, enabled=True, backend="dictionary")

        self.assertNotEqual(result, text)
        self.assertNotRegex(result, r"[A-Za-z]")

    def test_thousands_abbreviation_does_not_force_prepositional_case_after_na(self):
        tokens = simple_tokenize("выписал чек на сумму 100 тыс. долл.")
        self.assertEqual(get_numeral_case(tokens, tokens.index("100")), "accs")

    def test_money_amount_after_za_uses_accusative_case(self):
        tokens = simple_tokenize("продал корову за 1000 долл.")
        self.assertEqual(get_numeral_case(tokens, tokens.index("1000")), "accs")

    def test_normalize_amount_with_thousands_abbreviation_after_na_summu(self):
        self.assertEqual(
            normalize(
                "Энди Бехтольшайм, заинтересовавшийся этим проектом, сразу же выписал чек на сумму 100 тыс. долл."
            ),
            "Энди Бехтольшайм, заинтересовавшийся этим проектом, сразу же выписал чек на сумму сто тысяч долларов",
        )

    def test_normalize_amount_with_dollar_abbreviation_before_comma(self):
        self.assertEqual(
            normalize("Например, я продал корову за 1000 долл., а потом ушёл."),
            "Например, я продал корову за одну тысячу долларов, а потом ушёл.",
        )

    def test_normalize_amount_after_imet_uses_accusative_case(self):
        self.assertEqual(
            normalize("Мне лучше иметь 1000 долл., чем корову."),
            "Мне лучше иметь одну тысячу долларов, чем корову.",
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
            "сервэр",
        )
        self.assertEqual(normalize("engineering", options), "энджинИаинг")

    def test_normalize_with_dictionary_backend_removes_ascii_letters_from_long_english_text(self):
        options = NormalizeOptions(
            enable_latinization=True,
            latinization_backend="dictionary",
        )
        text = (
            "Browser updates improve network security and home storage systems, "
            "while engineering teams download source archives, review server logs, "
            "and write stable code for remote support platforms."
        )

        result = normalize(text, options)

        self.assertNotEqual(result, text)
        self.assertNotRegex(result, r"[A-Za-z]")

    def test_dictionary_latinization_handles_mixed_russian_and_english_text(self):
        text = (
            "Сегодня Windows Server обновил browser security, а support team "
            "review logs и пишет stable code для remote platform."
        )

        result = apply_latinization(text, enabled=True, backend="dictionary")

        self.assertEqual(
            result,
            "Сегодня виндаус сервэр обновил браусэр секюрити, а саппот тим "
            "рэвью логс и пишет стэбл кодэ для рэмоут плэтфом.",
        )
        self.assertNotRegex(result, r"[A-Za-z]")
        self.assertIn("Сегодня", result)
        self.assertIn("обновил", result)
        self.assertIn("для", result)


if __name__ == "__main__":
    unittest.main()
