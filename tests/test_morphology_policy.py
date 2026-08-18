from __future__ import annotations

import concurrent.futures
import re

import num2words
import pytest

from ru_normalizr import normalize
from ru_normalizr._morph import (
    _parse_word_lower,
    canonicalize_case,
    canonicalize_grammemes,
    parse_word,
    select_parse,
)


@pytest.mark.parametrize(
    ("rare", "primary"),
    [
        ("gen1", "gent"),
        ("gen2", "gent"),
        ("acc1", "accs"),
        ("acc2", "accs"),
        ("loc1", "loct"),
        ("loc2", "loct"),
        ("voct", "nomn"),
    ],
)
def test_all_upstream_rare_cases_are_canonicalized(rare: str, primary: str) -> None:
    assert canonicalize_case(rare) == primary
    assert canonicalize_grammemes({rare, "plur"}) == frozenset({primary, "plur"})


def test_parse_cache_uses_lowercase_key_without_folding_yo() -> None:
    _parse_word_lower.cache_clear()
    assert parse_word("Фёдор") == parse_word("фёдор")
    assert _parse_word_lower.cache_info().currsize == 1
    assert parse_word("Федор") != parse_word("Фёдор")
    assert _parse_word_lower.cache_info().currsize == 2


def test_selector_prefers_domain_compatible_lira_parse() -> None:
    selected = select_parse(
        "лира",
        pos="NOUN",
        normal_forms={"лира"},
        gender="femn",
        required_grammemes={"inan"},
        forbidden_grammemes={"Name", "Surn", "Geox"},
    )
    assert selected is not None
    assert selected.normal_form == "лира"
    assert selected.tag.gender == "femn"
    assert "inan" in selected.tag


def test_selector_respects_score_order_only_after_preferences() -> None:
    selected = select_parse(
        "часовой",
        pos={"ADJF", "NOUN"},
        preferred_grammemes={"ADJF"},
    )
    assert selected is not None
    assert selected.tag.POS == "ADJF"


def test_selector_returns_none_for_shape_barrier() -> None:
    assert select_parse("hello", pos="NOUN") is None


def test_shared_analyzer_is_safe_under_concurrent_parse_and_normalize() -> None:
    inputs = ["Фёдор", "лира", "сутки", "достигаем"] * 8

    def exercise(word: str) -> tuple[int, str]:
        return len(parse_word(word)), normalize(f"В сообщении есть 2 слова: {word}.")

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(exercise, inputs))
    assert all(parse_count > 0 and normalized for parse_count, normalized in results)


def test_generated_ordinal_final_words_keep_adjective_first_parse_invariant() -> None:
    for value in range(1, 10_000):
        final_word = num2words.num2words(value, lang="ru", to="ordinal").split()[-1]
        first = parse_word(final_word)[0]
        assert first.tag.POS == "ADJF" or "Anum" in first.tag, (value, final_word, first.tag)


#: Measurement in a parameter phrase is an apposition naming the parameter's
#: value, so it stays nominative whatever case the parameter itself carries.
PARAMETER_HEAD_CASES = [
    (
        "Сплав плавится при температуре 660 °C ровно.",
        "Сплав плавится при температуре шестьсот шестьдесят градусов Цельсия ровно.",
    ),
    (
        "Прибор работает при давлении 2 атм постоянно.",
        "Прибор работает при давлении две атмосферы постоянно.",
    ),
    (
        "Машина шла со скоростью 60 км/ч по трассе.",
        "Машина шла со скоростью шестьдесят километров в час по трассе.",
    ),
    (
        "Самолёт летел на высоте 5000 м над морем.",
        "Самолёт летел на высоте пять тысяч метров над морем.",
    ),
    (
        "Отчёт о температуре 25 °C подготовлен.",
        "Отчёт о температуре двадцать пять градусов Цельсия подготовлен.",
    ),
    (
        "Груз массой 3 т перевезли по железной дороге.",
        "Груз массой три тонны перевезли по железной дороге.",
    ),
    (
        "На площади 5 га растёт молодой лес.",
        "На площади пять гектаров растёт молодой лес.",
    ),
    # A decimal names the value just as an integer does.
    (
        "Работаем на частоте 3,2 ГГц.",
        "Работаем на частоте три целых две десятых гигагерца.",
    ),
    # «В» is a volt and must not be read as the preposition that would let the
    # parameter govern the measurement.
    (
        "Прибор работает при напряжении 220 В постоянно.",
        "Прибор работает при напряжении двести двадцать В постоянно.",
    ),
]

#: A relational quantity noun in the «в …» frame takes a genitive complement.
RELATIONAL_QUANTITY_CASES = [
    (
        "Пациент был в возрасте 25 лет на момент операции.",
        "Пациент был в возрасте двадцати пяти лет на момент операции.",
    ),
    (
        "Товар поставлен в количестве 5 штук по накладной.",
        "Товар поставлен в количестве пяти штук по накладной.",
    ),
    (
        "Штраф назначен в размере 500 рублей судом.",
        "Штраф назначен в размере пятисот рублей судом.",
    ),
    (
        "Он получил премию в сумме 1000 рублей вчера.",
        "Он получил премию в сумме одной тысячи рублей вчера.",
    ),
]

#: Quantities that really are governed from the outside and must stay oblique.
GOVERNED_QUANTITY_CASES = [
    # A distance measured off a landmark: «в» governs the number itself.
    ("Дом стоит в 200 м от реки.", "Дом стоит в двухстах метрах от реки."),
    # No parameter head at all — an ordinary oblique quantity.
    (
        "Склад разместили в 12 городах страны.",
        "Склад разместили в двенадцати городах страны.",
    ),
    # An explicit «в» before the measurement asks for the genitive reading.
    (
        "Сплав плавится при температуре в 660 градусов ровно.",
        "Сплав плавится при температуре в шестьсот шестьдесят градусов ровно.",
    ),
]


@pytest.mark.parametrize(("source", "expected"), PARAMETER_HEAD_CASES)
def test_parameter_head_keeps_its_measurement_nominative(
    source: str, expected: str
) -> None:
    assert normalize(source) == expected


@pytest.mark.parametrize(("source", "expected"), RELATIONAL_QUANTITY_CASES)
def test_relational_quantity_head_takes_a_genitive_complement(
    source: str, expected: str
) -> None:
    assert normalize(source) == expected


@pytest.mark.parametrize(("source", "expected"), GOVERNED_QUANTITY_CASES)
def test_genuinely_governed_quantity_stays_oblique(source: str, expected: str) -> None:
    assert normalize(source) == expected


#: Unit lemmas to watch in the invariant below.
_MEASUREMENT_UNIT_LEMMAS = frozenset(
    {
        "атмосфера",
        "вольт",
        "гектар",
        "герц",
        "гигагерц",
        "градус",
        "километр",
        "метр",
        "тонна",
    }
)


@pytest.mark.parametrize(
    "source",
    [source for source, _ in PARAMETER_HEAD_CASES + RELATIONAL_QUANTITY_CASES],
)
def test_unit_of_a_counted_measurement_is_never_oblique(source: str) -> None:
    """No Russian construction puts a counted unit into an oblique case.

    «двухстах метрах», «двух атмосферах», «пяти километрах в час» are all
    ungrammatical, so the case a parameter noun carries must never reach the
    unit — whichever case the resolver picks for the numeral itself.
    """
    for word in re.findall(r"[А-Яа-яЁё]+", normalize(source)):
        parse = select_parse(parse_word(word), pos="NOUN")
        if parse is None or parse.normal_form not in _MEASUREMENT_UNIT_LEMMAS:
            continue
        assert canonicalize_case(parse.tag.case) in {"nomn", "gent", "accs"}, (
            word,
            parse.tag,
        )
