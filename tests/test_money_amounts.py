"""Decimal money amounts read as major plus minor units.

"89,40 ₽" is spoken "восемьдесят девять рублей сорок копеек", never
"восемьдесят девять целых сорок сотых рубля". The rule is driven by the
currency table, so these tests pin both halves of it: which currencies split,
and — just as important — which decimals must keep the plain fraction reading.

The carrier sentences are chosen so the governing case is unambiguous.
"Комиссия … списана банком" is a plain nominative; a transitive verb is avoided
on purpose, because the numeral case after one is a separate known gap
(tests/test_known_gaps.py).
"""

from __future__ import annotations

import pytest

from ru_normalizr import NormalizeOptions, normalize


def tts(text: str) -> str:
    return normalize(text, NormalizeOptions.tts())


# --------------------------------------------------------------------------
# The amount itself
# --------------------------------------------------------------------------

SPLIT_CASES = (
    # Each half agrees with its own noun, so the same "21" is masculine before
    # "рубль" and feminine before "копейка" inside one amount.
    ("Комиссия 21,21 ₽ списана банком.", "Комиссия двадцать один рубль двадцать одна копейка списана банком."),
    ("Комиссия 1,01 ₽ списана банком.", "Комиссия один рубль одна копейка списана банком."),
    ("Комиссия 2,02 ₽ списана банком.", "Комиссия два рубля две копейки списана банком."),
    ("Комиссия 5,11 ₽ списана банком.", "Комиссия пять рублей одиннадцать копеек списана банком."),
    ("Комиссия 11,11 ₽ списана банком.", "Комиссия одиннадцать рублей одиннадцать копеек списана банком."),
    ("Комиссия 12,30 ₽ списана банком.", "Комиссия двенадцать рублей тридцать копеек списана банком."),
    # A whole amount voices no subunit at all: nobody says "ноль копеек".
    ("Комиссия 100,00 ₽ списана банком.", "Комиссия сто рублей списана банком."),
    ("Комиссия 1,00 ₽ списана банком.", "Комиссия один рубль списана банком."),
    # A zero major part is still voiced, because the digit is written.
    ("Комиссия 0,99 ₽ списана банком.", "Комиссия ноль рублей девяносто девять копеек списана банком."),
    ("Комиссия 0,01 ₽ списана банком.", "Комиссия ноль рублей одна копейка списана банком."),
)


@pytest.mark.parametrize(("source", "expected"), SPLIT_CASES)
def test_decimal_money_splits_into_major_and_minor_units(source: str, expected: str) -> None:
    assert tts(source) == expected


FRACTION_DIGIT_CASES = (
    # The fractional part is positional, not a literal count: ",5" is fifty
    # kopecks, not five.
    ("Комиссия 100,5 ₽ списана банком.", "Комиссия сто рублей пятьдесят копеек списана банком."),
    ("Комиссия 100,05 ₽ списана банком.", "Комиссия сто рублей пять копеек списана банком."),
    # Past two digits the tail can no longer be a subunit, so the amount keeps
    # the fraction reading instead of being silently rounded.
    ("Комиссия 100,005 ₽ списана банком.", "Комиссия сто целых пять тысячных рубля списана банком."),
    ("Комиссия 100,0001 ₽ списана банком.", "Комиссия сто целых одна десятитысячная рубля списана банком."),
)


@pytest.mark.parametrize(("source", "expected"), FRACTION_DIGIT_CASES)
def test_fraction_length_decides_whether_the_tail_is_a_subunit(
    source: str, expected: str
) -> None:
    assert tts(source) == expected


# --------------------------------------------------------------------------
# Agreement with the governing context
# --------------------------------------------------------------------------

GOVERNED_CASE_CASES = (
    ("Комиссия 12,30 ₽ списана банком.", "Комиссия двенадцать рублей тридцать копеек списана банком."),
    ("Курс вырос с 89,40 ₽ за сутки.", "Курс вырос с восьмидесяти девяти рублей сорока копеек за сутки."),
    ("Скидка достигла 12,30 ₽ вчера.", "Скидка достигла двенадцати рублей тридцати копеек вчера."),
    ("Цена подошла к 89,40 ₽ вплотную.", "Цена подошла к восьмидесяти девяти рублям сорока копейкам вплотную."),
    ("Перевод на 12,30 ₽ ушёл вчера.", "Перевод на двенадцать рублей тридцать копеек ушёл вчера."),
    ("Речь о 12,30 ₽ шла долго.", "Речь о двенадцати рублях тридцати копейках шла долго."),
    # The accusative has to survive into the thousands group: "одну тысячу",
    # not "одна тысяча".
    ("Счёт выставили на 1250,50 ₽ вчера.", "Счёт выставили на одну тысячу двести пятьдесят рублей пятьдесят копеек вчера."),
    # Both endpoints of an explicit "от … до" range carry their own currency.
    ("Штраф от 12,30 ₽ до 50,00 ₽ назначает суд.", "Штраф от двенадцати рублей тридцати копеек до пятидесяти рублей назначает суд."),
)


@pytest.mark.parametrize(("source", "expected"), GOVERNED_CASE_CASES)
def test_money_split_agrees_with_the_governing_case(source: str, expected: str) -> None:
    assert tts(source) == expected


# --------------------------------------------------------------------------
# Which currencies split, and which do not
# --------------------------------------------------------------------------

CURRENCY_WITH_SUBUNIT_CASES = (
    ("Комиссия 5,25 ₽ списана банком.", "Комиссия пять рублей двадцать пять копеек списана банком."),
    ("Комиссия 5,25 руб. списана банком.", "Комиссия пять рублей двадцать пять копеек списана банком."),
    ("Комиссия 5,25 р. списана банком.", "Комиссия пять рублей двадцать пять копеек списана банком."),
    ("Комиссия 5,25 ₴ списана банком.", "Комиссия пять гривен двадцать пять копеек списана банком."),
    ("Комиссия 5,25 $ списана банком.", "Комиссия пять долларов двадцать пять центов списана банком."),
    ("Комиссия 5,25 usd списана банком.", "Комиссия пять долларов двадцать пять центов списана банком."),
    ("Комиссия 5,25 долл. списана банком.", "Комиссия пять долларов двадцать пять центов списана банком."),
    ("Комиссия 5,25 € списана банком.", "Комиссия пять евро двадцать пять центов списана банком."),
    ("Комиссия 5,25 eur списана банком.", "Комиссия пять евро двадцать пять центов списана банком."),
    # The pound symbol only reaches the currency table once it is part of the
    # unit fragment; before that it was left raw in the output.
    ("Комиссия 5,25 £ списана банком.", "Комиссия пять фунтов двадцать пять пенсов списана банком."),
)


@pytest.mark.parametrize(("source", "expected"), CURRENCY_WITH_SUBUNIT_CASES)
def test_currency_with_a_spoken_subunit_splits(source: str, expected: str) -> None:
    assert tts(source) == expected


CURRENCY_WITHOUT_SUBUNIT_CASES = (
    # Тиын, куруш, пайса and чон are not pronounced by Russian speakers, so
    # these currencies deliberately keep the fraction reading rather than voice
    # a subunit nobody says.
    ("Комиссия 5,25 ¥ списана банком.", "Комиссия пять целых двадцать пять сотых иены списана банком."),
    ("Комиссия 5,25 ₸ списана банком.", "Комиссия пять целых двадцать пять сотых тенге списана банком."),
    ("Комиссия 5,25 ₺ списана банком.", "Комиссия пять целых двадцать пять сотых лиры списана банком."),
    ("Комиссия 5,25 ₹ списана банком.", "Комиссия пять целых двадцать пять сотых рупии списана банком."),
    ("Комиссия 5,25 ₩ списана банком.", "Комиссия пять целых двадцать пять сотых воны списана банком."),
)


@pytest.mark.parametrize(("source", "expected"), CURRENCY_WITHOUT_SUBUNIT_CASES)
def test_currency_without_a_spoken_subunit_keeps_the_fraction(
    source: str, expected: str
) -> None:
    assert tts(source) == expected


# --------------------------------------------------------------------------
# Everything that must NOT be split
# --------------------------------------------------------------------------

NON_SPLIT_CASES = (
    # A multiplier owns the fraction: "1,5 млн" is one and a half millions, not
    # one rouble fifty kopecks.
    ("Компания привлекла 1,5 млн рублей инвестиций.", "Компания привлекла одна целая пять десятых миллиона рублей инвестиций."),
    ("Выручка 1,5 млн ₽ за квартал.", "Выручка одна целая пять десятых миллиона рублей за квартал."),
    ("Проект стоил 2,3 млрд рублей суммарно.", "Проект стоил двух целых трёх десятых миллиарда рублей суммарно."),
    ("Долг 2,5 трлн ₽ копился годами.", "Долг две целых пять десятых триллиона рублей копился годами."),
    ("Бюджет 12,5 тыс. рублей утверждён вчера.", "Бюджет двенадцать целых пять десятых тысячи рублей утверждён вчера."),
    # Physical units and percentages share the decimal code path and must stay
    # untouched by the money rule.
    ("Длина троса 1,5 м проверена мастером.", "Длина троса одна целая пять десятых метра проверена мастером."),
    ("Заседание длилось 2,5 ч без перерыва.", "Заседание длилось две целых пять десятых часа без перерыва."),
    ("Масса груза 2,15 кг подтверждена весами.", "Масса груза две целых пятнадцать сотых килограмма подтверждена весами."),
    ("Налито 1,5 л воды в бутыль.", "Налито одна целая пять десятых литра воды в бутыль."),
    ("Доля составила 12,5% от выручки.", "Доля составила двенадцать целых пять десятых процента от выручки."),
    ("Ставка выросла на 0,25 п. п. за месяц.", "Ставка выросла на ноль целых двадцать пять сотых процентных пункта за месяц."),
)


@pytest.mark.parametrize(("source", "expected"), NON_SPLIT_CASES)
def test_non_currency_decimals_keep_the_fraction_reading(
    source: str, expected: str
) -> None:
    assert tts(source) == expected


# --------------------------------------------------------------------------
# Number shape around the amount
# --------------------------------------------------------------------------

NUMBER_SHAPE_CASES = (
    ("Комиссия -3,50 ₽ списана банком.", "Комиссия минус три рубля пятьдесят копеек списана банком."),
    # A dot is as valid a decimal separator here as a comma.
    ("Комиссия 3.50 руб. списана банком.", "Комиссия три рубля пятьдесят копеек списана банком."),
    ("Комиссия 1 250,50 ₽ списана банком.", "Комиссия одна тысяча двести пятьдесят рублей пятьдесят копеек списана банком."),
    ("Комиссия 12 345,67 ₽ списана банком.", "Комиссия двенадцать тысяч триста сорок пять рублей шестьдесят семь копеек списана банком."),
    ("Комиссия 1 234 567,89 ₽ списана банком.", "Комиссия один миллион двести тридцать четыре тысячи пятьсот шестьдесят семь рублей восемьдесят девять копеек списана банком."),
)


@pytest.mark.parametrize(("source", "expected"), NUMBER_SHAPE_CASES)
def test_money_split_survives_sign_and_thousand_separators(
    source: str, expected: str
) -> None:
    assert tts(source) == expected


# --------------------------------------------------------------------------
# Collision with the year rule
# --------------------------------------------------------------------------

YEAR_COLLISION_CASES = (
    # A four-digit major part after a preposition used to be claimed by the
    # year rule, which stranded the fractional part: "на 1250,50 ₽" came out as
    # "на тысяча двести пятидесятый, пятьдесят рублей".
    ("Счёт на 1250,50 ₽ пришёл вчера.", "Счёт на одну тысячу двести пятьдесят рублей пятьдесят копеек пришёл вчера."),
    ("Счёт на 1999,99 ₽ пришёл вчера.", "Счёт на одну тысячу девятьсот девяносто девять рублей девяносто девять копеек пришёл вчера."),
    ("Счёт на 2024,50 ₽ пришёл вчера.", "Счёт на две тысячи двадцать четыре рубля пятьдесят копеек пришёл вчера."),
)


@pytest.mark.parametrize(("source", "expected"), YEAR_COLLISION_CASES)
def test_year_rule_does_not_claim_the_integer_part_of_an_amount(
    source: str, expected: str
) -> None:
    assert tts(source) == expected


REAL_YEAR_CASES = (
    ("Дом построили в 1250 году.", "Дом построили в тысяча двести пятидесятом году."),
    ("Встреча назначена на 2024 год.", "Встреча назначена на две тысячи двадцать четвёртый год."),
    ("В 1941 началась война.", "В тысяча девятьсот сорок первом началась война."),
)


@pytest.mark.parametrize(("source", "expected"), REAL_YEAR_CASES)
def test_year_rule_still_claims_a_real_year(source: str, expected: str) -> None:
    assert tts(source) == expected


# --------------------------------------------------------------------------
# Punctuation around an abbreviated currency
# --------------------------------------------------------------------------


def test_abbreviated_currency_keeps_the_sentence_boundary() -> None:
    assert tts("Цена 3,50 руб. Доставка бесплатна.") == (
        "Цена трёх рублей пятидесяти копеек. Доставка бесплатна."
    )


def test_abbreviated_unit_keeps_the_sentence_boundary() -> None:
    # The same stranded-dot path, reached without any currency involved.
    assert tts("Масса 3,50 кг. Доставка бесплатна.") == (
        "Масса три целых пятьдесят сотых килограмма. Доставка бесплатна."
    )


def test_abbreviated_currency_before_a_comma_drops_its_dot() -> None:
    assert tts("Он отдал 3,50 руб., получив сдачу.") == (
        "Он отдал три рубля пятьдесят копеек, получив сдачу."
    )


# --------------------------------------------------------------------------
# End-to-end sentences that used to be known gaps
# --------------------------------------------------------------------------

E2E_CASES = (
    pytest.param(
        "Курс вырос с 89,40 ₽ до 91,05 ₽ за 1 USD.",
        "Курс вырос с восьмидесяти девяти рублей сорока копеек до девяноста одного рубля "
        "пяти копеек за один доллар.",
        id="currency_exchange",
    ),
    pytest.param(
        "Билет стоил 49,99 €, включая сбор 2,50 €.",
        "Билет стоил сорок девять евро девяносто девять центов, включая сбор два евро "
        "пятьдесят центов.",
        id="euro_and_cents",
    ),
    pytest.param(
        "Счёт выставили на 1 250,50 $, а аванс составил 300 $.",
        "Счёт выставили на одну тысячу двести пятьдесят долларов пятьдесят центов, а "
        "аванс составил триста долларов.",
        id="dollars_and_cents",
    ),
    pytest.param(
        "Заказ стоил 19,95 £, а доставка — 4 £.",
        "Заказ стоил девятнадцать фунтов девяносто пять пенсов, а доставка — четыре фунта.",
        id="pounds_and_pence",
    ),
)


@pytest.mark.parametrize(("source", "expected"), E2E_CASES)
def test_tts_e2e_money_amounts(source: str, expected: str) -> None:
    assert tts(source) == expected
