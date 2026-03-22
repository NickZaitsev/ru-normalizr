import unittest

from ru_normalizr import normalize
from ru_normalizr.roman_numerals import normalize_roman


class RuNormalizrRegnalNameTests(unittest.TestCase):
    def test_roman_stage_turns_regnal_names_into_ordinals(self):
        self.assertEqual(
            normalize_roman("коронация Георга VI"),
            "коронация Георга шестого",
        )
        self.assertEqual(
            normalize_roman("реформы при Елизавете II"),
            "реформы при Елизавете второй",
        )
        self.assertEqual(
            normalize_roman("при Дарии I"),
            "при Дарии первом",
        )
        self.assertEqual(
            normalize_roman("к Георгу VI"),
            "к Георгу шестому",
        )
        self.assertEqual(
            normalize_roman("о Георге VI"),
            "о Георге шестом",
        )

    def test_normalize_reads_regnal_names_as_ordinals(self):
        self.assertEqual(
            normalize("Одна из центральных тем – коронация Георга VI."),
            "Одна из центральных тем — коронация Георга шестого.",
        )
        self.assertEqual(
            normalize("Армия Людовика XVI отступила."),
            "Армия Людовика шестнадцатого отступила.",
        )
        self.assertEqual(
            normalize("Реформы при Елизавете II были спорными."),
            "Реформы при Елизавете второй были спорными.",
        )
        self.assertEqual(
            normalize("При Дарии I были реформы."),
            "При Дарии первом были реформы.",
        )
        self.assertEqual(
            normalize("К Георгу VI обратились с просьбой."),
            "К Георгу шестому обратились с просьбой.",
        )
        self.assertEqual(
            normalize("О Георге VI говорили часто."),
            "О Георге шестом говорили часто.",
        )


if __name__ == "__main__":
    unittest.main()
