"""Международные телефоны и замороженные отрицательные примеры до изменения."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from ru_normalizr import NormalizeOptions, normalize
from ru_normalizr.phones import normalize_international_phone_numbers

from .conftest import CheckTts


@pytest.mark.parametrize(
    ("source", "expected"),
    (
        (
            "Позвоните по телефону +375 29 123-45-67 завтра.",
            "Позвоните по телефону плюс триста семьдесят пять, двадцать девять, "
            "сто двадцать три, сорок пять, шестьдесят семь завтра.",
        ),
        (
            "Телефон: +44 20 8366 1177.",
            "Телефон: плюс сорок четыре, двадцать, восемь тысяч триста шестьдесят шесть, "
            "одна тысяча сто семьдесят семь.",
        ),
        (
            "Телефон: +1 (650) 253-2222.",
            "Телефон: плюс один, шестьсот пятьдесят, двести пятьдесят три, "
            "две тысячи двести двадцать два.",
        ),
        (
            "Телефон: +39 02 3661 8300.",
            "Телефон: плюс тридцать девять, ноль два, три тысячи шестьсот шестьдесят один, "
            "восемь тысяч триста.",
        ),
        (
            "Телефон: +7 (495) 123-00-07.",
            "Телефон: плюс семь, четыреста девяносто пять, сто двадцать три, ноль ноль, ноль семь.",
        ),
        (
            "Телефон: +380 44 123-45-67.",
            "Телефон: плюс триста восемьдесят, сорок четыре, сто двадцать три, "
            "сорок пять, шестьдесят семь.",
        ),
    ),
)
def test_international_phone_groups(check_tts: CheckTts, source: str, expected: str) -> None:
    check_tts(source, expected)


_REGRESSIONS = json.loads(
    (Path(__file__).parent / "data" / "international_phone_regressions.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize(
    ("row", "mode"),
    [
        pytest.param(row, mode, id=f"negative-{index}-{mode}")
        for index, row in enumerate(_REGRESSIONS)
        for mode in ("safe", "tts")
    ],
)
def test_frozen_non_phone_readings(row: dict[str, str], mode: str) -> None:
    options = NormalizeOptions.safe() if mode == "safe" else NormalizeOptions.tts()
    assert normalize(row["source"], options) == row[mode], row["source"]


@pytest.mark.parametrize(
    "number",
    (
        "+375 29 123-45-67",
        "+375 (29) 123-45-67",
        "+375(29)123-45-67",
        "+37529 123-45-67",
        "+375291234567",
        "+375\u00a029\u00a0123-45-67",
        "+375\u202f29\u202f123-45-67",
        "+375\u200929\u2009123-45-67",
        "+375 29 123\u201045\u201067",
        "+375 29 123\u201145\u201167",
    ),
)
@pytest.mark.parametrize("mode", ("safe", "tts"))
def test_equivalent_phone_formats(number: str, mode: str) -> None:
    options = NormalizeOptions.safe() if mode == "safe" else NormalizeOptions.tts()
    assert normalize(f"Телефон {number} указан в анкете.", options) == (
        "Телефон плюс триста семьдесят пять, двадцать девять, сто двадцать три, "
        "сорок пять, шестьдесят семь указан в анкете."
    )


@pytest.mark.parametrize(
    ("source", "expected"),
    (
        (
            "+375291234567",
            "плюс триста семьдесят пять, двадцать девять, сто двадцать три, "
            "сорок пять, шестьдесят семь",
        ),
        (
            "Контакты: (+375 29 123-45-67).",
            "Контакты: (плюс триста семьдесят пять, двадцать девять, сто двадцать три, "
            "сорок пять, шестьдесят семь).",
        ),
        (
            "Телефон:\n+375291234567\nЗвоните завтра.",
            "Телефон: плюс триста семьдесят пять, двадцать девять, сто двадцать три, "
            "сорок пять, шестьдесят семь.\nЗвоните завтра.",
        ),
        (
            "Телефон: +375291234567, +442083661177.",
            "Телефон: плюс триста семьдесят пять, двадцать девять, сто двадцать три, "
            "сорок пять, шестьдесят семь, плюс сорок четыре, двадцать, "
            "восемь тысяч триста шестьдесят шесть, одна тысяча сто семьдесят семь.",
        ),
        (
            "Телефон +375 29 123-45-67. ИНН 7701234567.",
            "Телефон плюс триста семьдесят пять, двадцать девять, сто двадцать три, "
            "сорок пять, шестьдесят семь. ИНН семь семь ноль один два три четыре "
            "пять шесть семь.",
        ),
        (
            "Телефон: +683 7012.",
            "Телефон: плюс шестьсот восемьдесят три, семь тысяч двенадцать.",
        ),
        (
            "Телефон: +49 30 12345678901.",
            "Телефон: плюс сорок девять, тридцать, двенадцать миллиардов триста "
            "сорок пять миллионов шестьсот семьдесят восемь тысяч девятьсот один.",
        ),
    ),
)
def test_phone_boundaries(check_tts: CheckTts, source: str, expected: str) -> None:
    check_tts(source, expected)


@pytest.mark.parametrize(
    "source",
    (
        "Телефон отключён. Прибыль составила +375291234567.",
        "Телефон отключён; показатель вырос на +375291234567.",
        "Телефон +375291234567 рублей указан ошибочно.",
        "Телефон +375291234567 метров указан ошибочно.",
        "Телефон +375291234567 км/ч указан ошибочно.",
        "Телефон +375291234567 = 1 записан как формула.",
        "Телефон 2 +375291234567 указан как сумма.",
        "Телефон +375291234567 +10 указан как сумма.",
        "Телефон +375291234567/2 указан как дробь.",
        "Телефон +375291234567.5 указан ошибочно.",
        "Телефон +375291234567:2 указан ошибочно.",
        "Телефон +375291234567abc указан ошибочно.",
        "Телефон +375291234567_2 указан ошибочно.",
        "Телефон +375 ((29)) 123-45-67 указан ошибочно.",
        "Телефон +375 (29 123)-45-67 указан ошибочно.",
        "Телефон +375 29 123--45-67 указан ошибочно.",
        "Телефон +375 29 123-45-67-8 указан ошибочно.",
        "Телефон +44 (0)20 8366 1177 содержит национальный префикс.",
        "Телефон +1 200 253-2222 имеет невыделенный код региона.",
        "Телефон +375 29 123-45-67 2026 указан ошибочно.",
        "Величина +375 29 123-45-67 указана без телефонной метки.",
        "Телефон +٣٧٥٢٩١٢٣٤٥٦٧ записан другими цифрами.",
    ),
)
def test_rejected_candidates_are_unchanged(source: str) -> None:
    # Проверяем границу нового правила напрямую: дальнейшее обычное чтение
    # таких строк проверяется замороженными E2E-примерами выше.
    assert normalize_international_phone_numbers(source) == source


def test_phone_does_not_consume_digits_from_the_next_line() -> None:
    assert normalize_international_phone_numbers(
        "Телефон +375 29 123-45-67\n2026 год указан отдельно."
    ) == (
        "Телефон плюс триста семьдесят пять, двадцать девять, сто двадцать три, "
        "сорок пять, шестьдесят семь\n2026 год указан отдельно."
    )


def test_disabled_numerals_keep_the_previous_reading() -> None:
    assert (
        normalize(
            "Телефон: +375291234567.",
            NormalizeOptions.tts(enable_numeral_normalization=False),
        )
        == "Телефон: плюс 375291234567."
    )


def test_converter_failure_preserves_the_source() -> None:
    source = "Телефон: +375 29 123-45-67."
    with patch("ru_normalizr.phones.num2words", side_effect=ValueError("conversion failed")):
        assert normalize_international_phone_numbers(source) == source


def test_many_phone_numbers_keep_their_boundaries() -> None:
    source = "Телефон +375 29 123-45-67 указан в анкете.\n"
    expected = (
        "Телефон плюс триста семьдесят пять, двадцать девять, сто двадцать три, "
        "сорок пять, шестьдесят семь указан в анкете.\n"
    )
    assert normalize_international_phone_numbers(source * 1000) == expected * 1000


def test_overlong_digit_run_is_not_partially_read_as_a_phone() -> None:
    source = "Телефон +375291234567" + "0" * 10000 + " записан ошибочно."
    assert normalize_international_phone_numbers(source) == source
