"""Тесты защиты от цифровых простыней.

Число длиннее 4300 цифр роняло весь прогон: `int()` на такой строке кидает
`ValueError` (лимит интерпретатора против квадратичного разбора), а голых
`int()` в правилах — десятки. При этом озвучить такое число нечем и без
лимита: `num2words` для русского заканчивается на 10**34 - 1.
"""

from __future__ import annotations

import pytest

from ru_normalizr import NormalizeOptions, normalize
from ru_normalizr.normalizer import PipelineNormalizer
from ru_normalizr.overlong_numbers import MAX_SPOKEN_DIGITS, protect_overlong_numbers

_OVERLONG = "7" * 4400


@pytest.fixture(scope="module")
def tts_options() -> NormalizeOptions:
    return NormalizeOptions.tts()


@pytest.mark.parametrize(
    "text",
    [
        f"Число {_OVERLONG} конец.",
        f"В {_OVERLONG}-м году.",
        f"Ровно {_OVERLONG},5 рубля.",
        f"Дробь {_OVERLONG}/3 конец.",
        f"С {_OVERLONG} по {_OVERLONG} год.",
        f"Стоит {_OVERLONG} руб.",
        f"Рост {_OVERLONG}% за год.",
        f"{_OVERLONG}.01.2020 год.",
    ],
)
def test_overlong_number_does_not_crash_the_run(text: str, tts_options: NormalizeOptions) -> None:
    result = normalize(text, tts_options)

    assert _OVERLONG in result


def test_overlong_number_leaves_the_rest_of_the_sentence_normalized(
    tts_options: NormalizeOptions,
) -> None:
    result = normalize(f"Было {_OVERLONG} рублей и ещё 25 копеек.", tts_options)

    assert _OVERLONG in result
    assert "двадцать пять копеек" in result


def test_numbers_up_to_the_ceiling_are_still_spoken(tts_options: NormalizeOptions) -> None:
    spoken = normalize("Число " + "9" * MAX_SPOKEN_DIGITS + " конец.", tts_options)

    assert not any(char.isdigit() for char in spoken)


def test_number_above_the_ceiling_stays_in_digits(tts_options: NormalizeOptions) -> None:
    above = "9" * (MAX_SPOKEN_DIGITS + 1)

    assert above in normalize(f"Число {above} конец.", tts_options)


def test_protection_keeps_short_numbers_visible_to_the_rules() -> None:
    protected = protect_overlong_numbers("В 1917 году было 12345 рублей.")

    assert protected.text == "В 1917 году было 12345 рублей."
    assert protected.restore(protected.text) == "В 1917 году было 12345 рублей."


def test_protection_hides_only_the_digit_run() -> None:
    protected = protect_overlong_numbers(f"Код {_OVERLONG} конец.")

    assert _OVERLONG not in protected.text
    assert protected.text.startswith("Код ")
    assert protected.text.endswith(" конец.")
    assert protected.restore(protected.text) == f"Код {_OVERLONG} конец."


def test_foreign_digits_run_does_not_crash_the_run(tts_options: NormalizeOptions) -> None:
    """Цифры чужой письменности правила приводят к ASCII перед `int()`."""
    arabic_indic = "٥" * 4400

    assert arabic_indic in normalize(f"Код {arabic_indic} конец.", tts_options)


@pytest.mark.parametrize("stage", ["numerals", "years", "dates_time"])
def test_single_stage_survives_overlong_number(stage: str, tts_options: NormalizeOptions) -> None:
    normalizer = PipelineNormalizer(tts_options)

    assert _OVERLONG in normalizer.run_stage(stage, f"Код {_OVERLONG} конец.")
