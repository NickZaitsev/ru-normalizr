from __future__ import annotations

import pytest

from ru_normalizr import NormalizeOptions, normalize
from ru_normalizr.numerals.numeric_suffixes import (
    NUMERIC_SUFFIXES,
    generate_numeric_suffix_candidates,
    is_numeric_suffix,
)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("7-ми", "семи"),
        ("В 7-ми классах ввели новую программу.", "В семи классах ввели новую программу."),
        ("7-ую книгу положили на стол.", "седьмую книгу положили на стол."),
        ("101-го участника пригласили в зал.", "сто одного участника пригласили в зал."),
        ("С 7-мя учениками провели занятие.", "С семью учениками провели занятие."),
        ("Около 7-мя человек остались снаружи.", "Около семи человек остались снаружи."),
        ("Получилось 7-мя.", "Получилось семь."),
        ("В 5-х классах ввели новый предмет.", "В пятых классах ввели новый предмет."),
        ("Учитель работает в 9-х классах второй год.", "Учитель работает в девятых классах второй год."),
    ],
)
def test_numeric_suffix_contract(source: str, expected: str) -> None:
    assert normalize(source, NormalizeOptions.safe()) == expected


def test_copular_predicate_selects_instrumental_ordinal_after_a_preposition_homonym() -> None:
    assert normalize("Он был 2-м после лидера.", NormalizeOptions.safe()) == (
        "Он был вторым после лидера."
    )


@pytest.mark.parametrize(
    "source",
    [
        "Код X7ми указан на коробке.",
        "Код X7-ми указан на коробке.",
        "Модель A320-й поступила в музей.",
        "Версия 2.1-я остаётся тестовой.",
        "Объём равен 1,5-й условной единицы.",
    ],
)
def test_suffix_resolver_does_not_partially_consume_structured_tokens(source: str) -> None:
    assert normalize(source, NormalizeOptions.safe()) == source


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Из 2-ух вариантов выбрали один.", "Из двух вариантов выбрали один."),
        ("Из 3-ех вариантов выбрали один.", "Из трёх вариантов выбрали один."),
        ("Из 4-ёх вариантов выбрали один.", "Из четырёх вариантов выбрали один."),
        ("С 5-тью способами разобрались.", "С пятью способами разобрались."),
        ("К 2-ум людям подошли позже.", "К двум людям подошли позже."),
        ("К 3-ём людям подошли позже.", "К трём людям подошли позже."),
    ],
)
def test_supported_nonstandard_suffix_spellings(source: str, expected: str) -> None:
    assert normalize(source, NormalizeOptions.safe()) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("В 1990-е годы всё изменилось.", "В тысяча девятьсот девяностые годы всё изменилось."),
        ("В 1990-х годах всё изменилось.", "В тысяча девятьсот девяностых годах всё изменилось."),
        ("Работали между 1990-ми и 2000-ми годами.", "Работали между тысяча девятьсот девяностыми и двухтысячными годами."),
        ("Это случилось 90-ми годами ранее.", "Это случилось девяностыми годами ранее."),
    ],
)
def test_year_stage_keeps_suffix_ownership(source: str, expected: str) -> None:
    assert normalize(source, NormalizeOptions.safe()) == expected


@pytest.mark.parametrize(
    ("number", "suffix"),
    [
        (1, "й"),
        (2, "мя"),
        (3, "х"),
        (4, "ёх"),
        (5, "тью"),
        (7, "ми"),
        (8, "ми"),
        (11, "ти"),
        (20, "ти"),
        (21, "го"),
        (90, "ми"),
        (100, "ми"),
        (101, "го"),
        (1001, "го"),
    ],
)
def test_candidate_generator_matches_only_the_final_spoken_word(
    number: int, suffix: str
) -> None:
    exact = [
        candidate
        for candidate in generate_numeric_suffix_candidates(number, suffix)
        if candidate.exact
    ]
    assert exact
    assert all(candidate.reading.casefold().split()[-1].endswith(suffix) for candidate in exact)


def test_candidate_cache_is_bounded_and_reused() -> None:
    generate_numeric_suffix_candidates.cache_clear()
    first = generate_numeric_suffix_candidates(101, "го")
    second = generate_numeric_suffix_candidates(101, "го")
    cache_info = generate_numeric_suffix_candidates.cache_info()
    assert first == second
    assert cache_info.hits == 1
    assert cache_info.maxsize == 16384


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("7-ю", "семью"),
        ("7-ю книгу", "седьмую книгу"),
        ("3-х участников", "трёх участников"),
        ("2-е сутки", "вторые сутки"),
        ("-7-ми", "минус семи"),
        ("«7-ми»,", '"семи",'),
        ("7-аб", "семь аб"),
    ],
)
def test_ambiguity_boundaries_and_unknown_tails(source: str, expected: str) -> None:
    assert normalize(source, NormalizeOptions.safe()) == expected


def test_suffix_registry_is_closed() -> None:
    assert "ми" in NUMERIC_SUFFIXES
    assert not is_numeric_suffix("аб")


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        # Порядковое согласуется с существительным справа, когда падеж числа
        # ничем не задан и по умолчанию считается именительным.
        ("штаб 4-й армии", "штаб четвёртой армии"),
        ("солдаты 295-й дивизии", "солдаты двести девяносто пятой дивизии"),
        ("командир 4-й роты", "командир четвёртой роты"),
        ("знамя 4-й армии", "знамя четвёртой армии"),
        ("части 4-й армии", "части четвёртой армии"),
        # Явный сигнал (управление, предлог) главнее согласования справа.
        ("командующий 4-й армией", "командующий четвёртой армией"),
        ("из 4-й армии", "из четвёртой армии"),
        ("2-я танковая дивизия", "вторая танковая дивизия"),
        ("глава 1-я", "глава первая"),
        ("он был 2-м после лидера", "он был вторым после лидера"),
    ],
)
def test_ordinal_agrees_with_the_head_noun_without_a_preposition(
    source: str, expected: str
) -> None:
    assert normalize(source, NormalizeOptions.safe()) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        # Суффиксы «й», «го», «м» бывают только у порядковых, поэтому ничья
        # между «одной» и «первой» решается в пользу порядкового.
        ("в 1-й главе", "в первой главе"),
        ("из 1-й Ударной армии", "из первой Ударной армии"),
        ("из 1-го батальона", "из первого батальона"),
        ("он живёт на 1-м этаже", "он живёт на первом этаже"),
        ("из 21-й армии", "из двадцать первой армии"),
        ("он был 1-м в списке", "он был первым в списке"),
        ("1-й раз он пришёл", "первый раз он пришёл"),
        # Суффиксы из количественного реестра сохраняют количественное чтение.
        ("в течение 2-х часов", "в течение двух часов"),
        ("7-ми поездами", "седьмыми поездами"),
        ("1-го октября", "первого октября"),
    ],
)
def test_ordinal_only_suffix_prefers_the_ordinal_reading(source: str, expected: str) -> None:
    assert normalize(source, NormalizeOptions.safe()) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        # Союз, имя и деепричастный оборот справа — не вершина числовой группы:
        # у каждого есть именной разбор, который навязывал числу чужие род и
        # число.
        (
            "Полки продвинулись между 1-й и 2-й линиями.",
            "Полки продвинулись между первой и второй линиями.",
        ),
        (
            "В ночь с 27-го на 28-е Святослав ожидал нападения.",
            "В ночь с двадцать седьмого на двадцать восьмое Святослав ожидал нападения.",
        ),
        (
            "В ночь на 28-е Святослав, ожидая нападения, приказал вырыть ров.",
            "В ночь на двадцать восьмое Святослав, ожидая нападения, приказал вырыть ров.",
        ),
        # Без вершины справа порядковое единственного: множественному не с чем
        # согласовываться. Множественное определение слева правило снимает.
        ("Наконец, 4-е, обиженное боярство выдвинуло орудие.", "Наконец, четвёртое, обиженное боярство выдвинуло орудие."),
        ("в лихие 90-е.", "в лихие девяностые."),
    ],
)
def test_head_noun_search_ignores_words_that_cannot_govern(source: str, expected: str) -> None:
    assert normalize(source, NormalizeOptions.safe()) == expected
