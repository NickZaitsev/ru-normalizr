from __future__ import annotations

import pytest

from ru_normalizr import normalize
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
