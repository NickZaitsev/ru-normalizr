from __future__ import annotations

import pytest

from ru_normalizr import NormalizeOptions, normalize
from ru_normalizr.numerals.fractions import normalize_fractions


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("без 100/100 выборки", "без ста сотых выборки"),
        ("без 101/100 выборки", "без ста одной сотой выборки"),
        ("без 2000/10000 выборки", "без двух тысяч десятитысячных выборки"),
        ("к 1000/100 от целого", "к одной тысяче сотых от целого"),
        ("о 100/100 выборки", "о ста сотых выборки"),
    ],
)
def test_fraction_stage_inflects_complete_numerator(
    source: str, expected: str
) -> None:
    assert normalize_fractions(source) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "Расчёт выполнен без 100/100 общей выборки.",
            "Расчёт выполнен без ста сотых общей выборки.",
        ),
        (
            "Расчёт выполнен без 2000/10000 общей выборки.",
            "Расчёт выполнен без двух тысяч десятитысячных общей выборки.",
        ),
        (
            "Показатель приблизился к 1000/100 от целого.",
            "Показатель приблизился к одной тысяче сотых от целого.",
        ),
    ],
)
def test_public_pipeline_leaves_fraction_ownership_to_fraction_stage(
    source: str, expected: str
) -> None:
    assert normalize(source) == expected


#: Десятичное количество всегда неодушевлённое: одушевлённый винительный
#: («двух целых трёх десятых») в нём появиться не может, даже если управляющий
#: глагол требует винительного падежа. Форму на «…1» винительный сохраняет:
#: «одну целую», «одну тысячу».
INANIMATE_ACCUSATIVE_DECIMAL_CASES = (
    (
        "Армия потеряла почти 1,3 млн. убитыми.",
        "Армия потеряла почти одну целую три десятых миллиона убитыми.",
    ),
    (
        "Компания вложила 2,3 млн. рублей.",
        "Компания вложила две целых три десятых миллиона рублей.",
    ),
    (
        "Завод выпустил 3,2 млн деталей.",
        "Завод выпустил три целых две десятых миллиона деталей.",
    ),
    (
        "Комиссия проверила 1,1 млн заявок.",
        "Комиссия проверила одну целую одну десятую миллиона заявок.",
    ),
)

#: Падежи, которых правка не касается: там винительного нет вообще.
UNCHANGED_DECIMAL_CASES = (
    ("Пробежал за 8,4 с.", "Пробежал за восемь целых четыре десятых секунды."),
    (
        "При дозе 0,5 мл эффект есть.",
        "При дозе ноль целых пять десятых миллилитра эффект есть.",
    ),
    (
        "Длина троса 1,5 м проверена мастером.",
        "Длина троса одна целая пять десятых метра проверена мастером.",
    ),
)


@pytest.mark.parametrize(
    ("source", "expected"),
    [*INANIMATE_ACCUSATIVE_DECIMAL_CASES, *UNCHANGED_DECIMAL_CASES],
)
def test_decimal_quantity_never_takes_the_animate_accusative(
    source: str, expected: str
) -> None:
    assert normalize(source, NormalizeOptions.tts()) == expected
