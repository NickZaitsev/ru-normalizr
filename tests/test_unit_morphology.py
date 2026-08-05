from __future__ import annotations

import logging

import pytest

from ru_normalizr import normalize
from ru_normalizr._morph import select_parse
from ru_normalizr.numerals._constants import (
    CASE_SENSITIVE_UNITS_DATA,
    UNITS_DATA,
    UnitDescriptor,
    UnitMorphology,
    is_exact_unit_token,
    resolve_unit_info,
)
from ru_normalizr.numerals._helpers import inflect_unit_lemma


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Билет стоит 1 ₺.", "Билет стоит одну лиру."),
        ("Два билета стоят 2 ₺.", "Два билета стоят две лиры."),
        ("Пять билетов стоят 5 ₺.", "Пять билетов стоят пять лир."),
        ("Покупка стоит 1 тенге.", "Покупка стоит один тенге."),
        ("Покупка стоит 5 ₸.", "Покупка стоит пять тенге."),
        ("Цена билета — 1 ₩.", "Цена билета — одна вона."),
        ("Цена билетов — 5 ₩.", "Цена билетов — пять вон."),
        ("Ёмкость составляет 1 Ф.", "Ёмкость составляет один фарад."),
        ("Ёмкость составляет 2 мФ.", "Ёмкость составляет два миллифарада."),
        ("Индукция составляет 5 Тл.", "Индукция составляет пять тесл."),
        ("В образце содержится 2 mol.", "В образце содержится два моля."),
        ("Доза составляет 5 ₪.", "Доза составляет пять шекелей."),
        ("Доза составляет 5 Гр.", "Доза составляет пять греев."),
        ("Давление увеличили на 1 Па.", "Давление увеличили на один паскаль."),
        ("Поток увеличили на 1 Вб.", "Поток увеличили на один вебер."),
        ("Дозу увеличили на 1 Зв.", "Дозу увеличили на один зиверт."),
    ],
)
def test_domain_units_use_validated_morphology(source: str, expected: str) -> None:
    assert normalize(source) == expected


@pytest.mark.parametrize(
    "lemma",
    [
        "шекель",
        "грей",
        "фарад",
        "миллифарад",
        "микрофарад",
        "нанофарад",
        "пикофарад",
        "тесла",
        "паскаль",
        "килопаскаль",
        "мегапаскаль",
        "зиверт",
    ],
)
def test_validated_unit_paradigms_cover_all_primary_cases_and_numbers(
    lemma: str,
) -> None:
    descriptor = next(
        descriptor
        for descriptor in UNITS_DATA.values()
        if descriptor.lemma == lemma
    )
    forms = descriptor.morphology.paradigm
    assert len(forms) == 12
    for case, number, expected in forms:
        assert inflect_unit_lemma(descriptor, {case, number}) == expected


def test_string_unit_lemma_uses_the_same_validated_inflection_path() -> None:
    assert inflect_unit_lemma("метр", {"gent", "plur"}) == "метров"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Экспедиция длилась 1 сут.", "Экспедиция длилась одни сутки."),
        ("Экспедиция длилась 2 сут.", "Экспедиция длилась двое суток."),
        ("Экспедиция длилась 5 сут.", "Экспедиция длилась пять суток."),
    ],
)
def test_plural_only_day_unit_uses_collective_agreement(
    source: str, expected: str
) -> None:
    assert normalize(source) == expected


@pytest.mark.parametrize(
    ("token", "lemma"),
    [
        ("mW", "милливатт"),
        ("MW", "мегаватт"),
        ("мВт", "милливатт"),
        ("МВт", "мегаватт"),
        ("mV", "милливольт"),
        ("MV", "мегавольт"),
        ("mA", "миллиампер"),
        ("MA", "мегаампер"),
        ("b", "бит"),
        ("B", "байт"),
        ("Mb", "мегабит"),
        ("MB", "мегабайт"),
        ("Mbps", "мегабит"),
        ("MBps", "мегабайт"),
        ("Гр", "грей"),
        ("гр", "грамм"),
    ],
)
def test_exact_case_unit_resolution(token: str, lemma: str) -> None:
    descriptor = resolve_unit_info(token)
    assert descriptor is not None
    assert descriptor.lemma == lemma
    assert is_exact_unit_token(token)


def test_exact_roman_shaped_unit_is_protected_before_roman_stage() -> None:
    assert normalize("Источник выдаёт напряжение 5 MV.") == (
        "Источник выдаёт напряжение пять мегавольт."
    )


def test_molar_concentration_requires_fully_written_unit() -> None:
    # Short forms ending in uppercase "М" overlap length notation and are
    # common artefacts of damaged source formatting. Never assign them a molar
    # meaning; only an explicit amount-per-volume alias may represent it.
    molar_lemmas = {"моль", "миллимоль", "микромоль", "наномоль"}
    for token in ("М", "мМ", "ММ", "мкМ", "нМ"):
        descriptor = resolve_unit_info(token)
        assert descriptor is None or not (
            descriptor.lemma in molar_lemmas and descriptor.suffix == "на литр"
        )

    explicit_concentration = resolve_unit_info("ммоль/л")
    assert explicit_concentration is not None
    assert explicit_concentration.lemma == "миллимоль"
    assert explicit_concentration.suffix == "на литр"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Ставка выросла на 5 п.п. за месяц.", "Ставка выросла на пять процентных пунктов за месяц."),
        ("Доходность выросла на 5 б.п. за день.", "Доходность выросла на пять базисных пунктов за день."),
        ("Крепость строили 2 в. подряд.", "Крепость строили два века подряд."),
        ("Угол составляет 2 рад. сегодня.", "Угол составляет два радиана сегодня."),
        ("Мощность составляет 5 л. с. сейчас.", "Мощность составляет пять лошадиных сил сейчас."),
        ("Угол составляет 2 рад.", "Угол составляет два радиана."),
    ],
)
def test_dotted_only_aliases_preserve_sentence_boundary(
    source: str, expected: str
) -> None:
    assert normalize(source) == expected


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("байт", "пять байтов"),
        ("кб", "пять килобайтов"),
        ("MB", "пять мегабайтов"),
        ("GB", "пять гигабайтов"),
        ("TB", "пять терабайтов"),
        ("Mb", "пять мегабит"),
    ],
)
def test_byte_family_uses_ordinary_forms_but_bits_may_use_counting_forms(
    token: str, expected: str
) -> None:
    assert normalize(f"Файл занимает 5 {token}.") == f"Файл занимает {expected}."


def test_invalid_morphology_seed_logs_and_falls_back(
    caplog: pytest.LogCaptureFixture,
) -> None:
    descriptor = UnitDescriptor(
        lemma="несуществующаяединица",
        gender="masc",
        category="measure",
        morphology=UnitMorphology(
            expected_normal_form="другаяединица",
            morphology_seed="тожеошибка",
        ),
    )
    with caplog.at_level(logging.DEBUG):
        assert inflect_unit_lemma(descriptor, {"gent", "plur"}) == descriptor.lemma
    assert "No validated morphology form" in caplog.text


def test_unit_inventory_has_a_validated_morphology_route() -> None:
    descriptors = {*UNITS_DATA.values(), *CASE_SENSITIVE_UNITS_DATA.values()}
    for descriptor in descriptors:
        morphology = descriptor.morphology
        if (
            " " in descriptor.lemma
            or "-" in descriptor.lemma
            or morphology.indeclinable
            or morphology.paradigm
        ):
            continue
        selected = select_parse(
            descriptor.lemma,
            pos="NOUN",
            normal_forms={morphology.expected_normal_form or descriptor.lemma},
            required_grammemes=(
                {morphology.animacy} if morphology.animacy is not None else set()
            ),
            forbidden_grammemes=morphology.forbidden_grammemes,
            gender=(
                descriptor.gender
                if descriptor.gender in {"masc", "femn", "neut"}
                else None
            ),
        )
        assert selected is not None, descriptor.lemma
        if morphology.byte_family:
            assert "Coun" not in selected.tag
