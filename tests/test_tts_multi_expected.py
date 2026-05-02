import re
import unittest
from dataclasses import dataclass

from ru_normalizr import NormalizeOptions, Normalizer


def _canon(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


@dataclass(frozen=True)
class TtsCase:
    name: str
    text: str
    expected_variants: tuple[str, ...]
    responsible_stage: str


CASES = (
    TtsCase(
        name="url_explicit",
        text="Сайт: https://example.com/a1?b=23.",
        expected_variants=(
            "Сайт: хтпс двоеточие слэш слэш игзэмпэл точка кам слэш э один вопрос би равно два три.",
        ),
        responsible_stage="urls",
    ),
    TtsCase(
        name="email_explicit",
        text="Пиши на test@example.com",
        expected_variants=(
            "Пиши на тэст собака игзэмпэл точка кам",
        ),
        responsible_stage="urls",
    ),
    TtsCase(
        name="phone_explicit",
        text="Позвони +7 (999) 123-45-67.",
        expected_variants=(
            "Позвони плюс семь девять девять девять один два три четыре пять шесть семь.",
        ),
        responsible_stage="urls",
    ),
    TtsCase(
        name="text_date_slash",
        text="Собрание 15/04/2024 в 08.00 утра.",
        expected_variants=(
            "Собрание пятнадцатого апреля две тысячи двадцать четвёртого года в восемь, ноль ноль утра.",
        ),
        responsible_stage="dates_time",
    ),
    TtsCase(
        name="mixed_latin_cyrillic",
        text="Купил YouTube Premium.",
        expected_variants=(
            "Купил ютуб примиэм.",
        ),
        responsible_stage="latinization",
    ),
    TtsCase(
        name="address_house_abbreviation",
        text="ул. Ленина, д. 5",
        expected_variants=(
            "улица Ленина, дом пять",
        ),
        responsible_stage="preprocess",
    ),
)


class TtsMultiExpectedRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.options = NormalizeOptions.tts()
        self.normalizer = Normalizer(self.options)
        self.stage_order = (
            "urls",
            "preprocess",
            "roman",
            "years",
            "dates_time",
            "numerals",
            "abbreviations",
            "latinization",
            "dictionary",
            "finalize",
        )

    def _first_changed_stage(self, text: str) -> str | None:
        current = text
        for stage in self.stage_order:
            updated = self.normalizer.run_stage(stage, current)
            if updated != current:
                return stage
            current = updated
        return None

    def test_tts_cases_accept_multiple_valid_outputs(self):
        for case in CASES:
            with self.subTest(case=case.name):
                actual = _canon(self.normalizer.normalize(case.text))
                allowed = {_canon(variant) for variant in case.expected_variants}
                self.assertIn(actual, allowed)

    def test_stage_triage_maps_cases_to_expected_stage(self):
        for case in CASES:
            with self.subTest(case=case.name):
                self.assertEqual(self._first_changed_stage(case.text), case.responsible_stage)


if __name__ == "__main__":
    unittest.main()
