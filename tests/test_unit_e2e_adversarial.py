from unittest.mock import patch

import pytest

from ru_normalizr import normalize
from ru_normalizr.numerals import unit_expressions
from ru_normalizr.numerals.cardinals import normalize_cardinal_numerals
from ru_normalizr.numerals.unit_expressions import resolve_unit_expression


def test_generated_unit_families_use_inanimate_accusative_paradigms() -> None:
    source = (
        "Пределы: на 1 мПа, на 1 мН, на 1 мГц, на 1 Мг, на 1 мкм, "
        "на 1 мс, на 1 мл и на 1 мФ."
    )
    expected = (
        "Пределы: на один миллипаскаль, на один миллиньютон, на один миллигерц, "
        "на один мегаграмм, на один микрометр, на одну миллисекунду, "
        "на один миллилитр и на один миллифарад."
    )
    assert normalize(source) == expected


def test_generated_units_cover_one_few_many_and_decimal_boundaries() -> None:
    source = (
        "Давление: 1 МПа, 2 МПа, 5 МПа; размеры: 1 мкм, 2 мкм, "
        "5 мкм и 2,5 мкм."
    )
    expected = (
        "Давление: один мегапаскаль, два мегапаскаля, пять мегапаскалей; "
        "размеры: один микрометр, два микрометра, пять микрометров и "
        "две целых пять десятых микрометра."
    )
    assert normalize(source) == expected


def test_milli_mega_and_damaged_case_do_not_cross_semantic_targets() -> None:
    source = (
        "Лист 5 ММ, масса 5 Мг, давление 5 мПа и 5 МПа; "
        "варианты 5 mPA, 5 Mpa и 5 М оставлены как есть."
    )
    expected = (
        "Лист пять миллиметров, масса пять мегаграммов, давление пять "
        "миллипаскалей и пять мегапаскалей; варианты пять mPA, пять Mpa "
        "и пять М оставлены как есть."
    )
    assert normalize(source) == expected


def test_micrometre_does_not_capture_molar_like_mixed_case() -> None:
    result = normalize("Толщина 5 мкм, а сомнительные записи 5 мкМ и 5 М не пояснены.")
    assert result == (
        "Толщина пять микрометров, а сомнительные записи пять мкМ и пять М не пояснены."
    )
    assert "микромол" not in result


def test_bit_byte_rates_require_exact_semantic_case_end_to_end() -> None:
    source = (
        "Первый канал — 1 Mb/s; второй — 2 MB/s; третий — 5 kBps; "
        "четвёртый — 5 mBps."
    )
    expected = (
        "Первый канал — один мегабит в секунду; второй — два мегабайта в секунду; "
        "третий — пять килобайтов в секунду; четвёртый — пять mBps."
    )
    assert normalize(source) == expected


def test_registered_expressions_survive_spacing_quotes_and_punctuation() -> None:
    source = "Дозы: «2 мл / мин», (3 мг / кг); энергия — 4 кВт · ч."
    expected = (
        'Дозы: "два миллилитра в минуту", (три миллиграмма на килограмм); '
        "энергия — четыре киловатт-часа."
    )
    assert normalize(source) == expected


def test_unit_slash_protection_does_not_claim_urls_or_plain_fractions() -> None:
    source = "Откройте https://example.test/data/5Mb/s; доля равна 5/7."
    expected = "Откройте https://example.test/data/5Mb/s; доля равна пять седьмых."
    assert normalize(source) == expected


def test_squared_denominator_unit_is_a_registered_rate_expression() -> None:
    assert normalize("Ускорение достигло 2 м/с² перед остановкой установки.") == (
        "Ускорение достигло двух метров в секунду в квадрате перед остановкой установки."
    )


@pytest.mark.parametrize(
    "raw",
    [
        "мг/кг/сут",
        "foo/bar",
        "C:/tmp",
        "5/7",
        "м^4",
        "мкМ",
    ],
)
def test_bounded_parser_rejects_nested_unknown_and_molar_like_inputs(raw: str) -> None:
    assert resolve_unit_expression(raw) is None


def test_number_dense_unknown_unit_matching_stays_bounded() -> None:
    source = " ".join(f"{value} mPA" for value in range(1, 101))
    with patch.object(
        unit_expressions,
        "resolve_unit_expression",
        wraps=unit_expressions.resolve_unit_expression,
    ) as resolve_expression:
        normalize_cardinal_numerals(source)

    assert resolve_expression.call_count <= 400
