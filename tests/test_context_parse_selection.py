from __future__ import annotations

import pytest

from ru_normalizr import normalize


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "Порядок гос. часовой службы определён уставом.",
            "Порядок государственной часовой службы определён уставом.",
        ),
        (
            "На циферблате отметили положение офиц. часовой стрелки.",
            "На циферблате отметили положение официальной часовой стрелки.",
        ),
        (
            "Порядок гос. службы определён уставом.",
            "Порядок государственной службы определён уставом.",
        ),
    ],
)
def test_abbreviation_uses_rightmost_compatible_noun_head(
    source: str, expected: str
) -> None:
    assert normalize(source) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        # Distributive "по" takes the dative only when the numeral ends in a
        # single "one": ...1 but not ...11. Everything else stays accusative.
        ("Выдали по 1 рублю каждому.", "Выдали по одному рублю каждому."),
        ("Выдали по 21 рублю каждому.", "Выдали по двадцати одному рублю каждому."),
        ("Выдали по 31 рублю каждому.", "Выдали по тридцати одному рублю каждому."),
        ("Раздали по 41 карандашу детям.", "Раздали по сорока одному карандашу детям."),
        ("Выдали по 101 рублю каждому.", "Выдали по ста одному рублю каждому."),
        ("Выдали по 11 рублей каждому.", "Выдали по одиннадцать рублей каждому."),
        ("Выдали по 111 рублей каждому.", "Выдали по сто одиннадцать рублей каждому."),
        ("Выдали по 2 рубля каждому.", "Выдали по два рубля каждому."),
        ("Выдали по 5 рублей каждому.", "Выдали по пять рублей каждому."),
        ("Заплатили по 1000 рублей каждому.", "Заплатили по одну тысячу рублей каждому."),
    ],
)
def test_distributive_po_takes_the_dative_only_for_a_final_one(
    source: str, expected: str
) -> None:
    assert normalize(source) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        # With no preposition and no governing verb, an unambiguous instrumental
        # or dative noun right after the number is what sets the numeral's case.
        # The head has to be a noun ("управление"), not a verb: "владеть" and
        # "управлять" govern the instrumental themselves and would decide first.
        ("Управление 5 заводами затруднено.", "Управление пятью заводами затруднено."),
        ("Обмен 3 квартирами состоялся.", "Обмен тремя квартирами состоялся."),
        ("Замена 8 деталями решена.", "Замена восемью деталями решена."),
        ("Он рад 5 гостям.", "Он рад пяти гостям."),
        ("Доступ 4 сотрудникам открыт.", "Доступ четырём сотрудникам открыт."),
    ],
)
def test_following_noun_without_a_preposition_sets_the_numeral_case(
    source: str, expected: str
) -> None:
    assert normalize(source) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Мне уже 40.", "Мне уже сорок."),
        ("Мне теперь 40.", "Мне теперь сорок."),
        ("Ей 25.", "Ей двадцать пять."),
        ("Ему 33.", "Ему тридцать три."),
        ("Директору 45.", "Директору сорок пять."),
    ],
)
def test_age_after_a_dative_stays_nominative(source: str, expected: str) -> None:
    # A bare number closing the clause is a predicate, so the dative on the left
    # must not pull the numeral with it.
    assert normalize(source) == expected


def test_number_licenses_noun_parse_of_infinitive_homonym() -> None:
    assert normalize("В музее представлена 1 пасть древнего животного.") == (
        "В музее представлена одна пасть древнего животного."
    )


def test_verb_candidate_governs_case_below_short_adjective_homonym() -> None:
    assert normalize("К концу квартала мы достигаем 5 целей программы.") == (
        "К концу квартала мы достигаем пяти целей программы."
    )


def test_inflected_unit_in_year_range_is_measurement_not_implicit_year() -> None:
    assert normalize("Прибор рассчитан на дозу в 2020 зивертов.") == (
        "Прибор рассчитан на дозу в две тысячи двадцать зивертов."
    )
    assert normalize("Документ подписали в 2020 году.") == (
        "Документ подписали в две тысячи двадцатом году."
    )
