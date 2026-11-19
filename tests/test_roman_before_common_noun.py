"""Римское число перед обычным существительным читается порядковым.

«XX съезд», «IV конференция»: римскими цифрами в русском тексте пишут номер,
а не количество, поэтому число согласуется с существительным справа в роде,
числе и падеже. Раньше это работало только для закрытого списка слов (век,
глава, том…), а остальные получали арабскую цифру и количественное чтение:
«Решения XX съезда» звучало как «двадцать съезда».
"""

from __future__ import annotations

import pytest

from ru_normalizr import normalize


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            "XX съезд прошёл в феврале.",
            "двадцатый съезд прошёл в феврале.",
            id="nominative",
        ),
        pytest.param(
            "Решения XX съезда были опубликованы.",
            "Решения двадцатого съезда были опубликованы.",
            id="genitive_without_preposition",
        ),
        pytest.param(
            "Решения XX съезда КПСС были опубликованы.",
            "Решения двадцатого съезда КПСС были опубликованы.",
            id="genitive_before_abbreviation",
        ),
        pytest.param(
            "Доклад XX съезду готовили долго.",
            "Доклад двадцатому съезду готовили долго.",
            id="dative",
        ),
        pytest.param(
            "Делегаты восхищались XX съездом.",
            "Делегаты восхищались двадцатым съездом.",
            id="instrumental",
        ),
        pytest.param(
            "На XX съезде выступил Хрущёв.",
            "На двадцатом съезде выступил Хрущёв.",
            id="locative",
        ),
        pytest.param(
            "Он готовился к IV конференции.",
            "Он готовился к четвёртой конференции.",
            id="feminine_case_from_preposition",
        ),
        pytest.param(
            "Открылась XII олимпиада.",
            "Открылась двенадцатая олимпиада.",
            id="feminine_nominative",
        ),
        pytest.param(
            "V съезд РСДРП прошёл в Лондоне.",
            "пятый съезд РСДРП прошёл в Лондоне.",
            id="single_letter_v",
        ),
    ],
)
def test_roman_before_common_noun_is_an_agreeing_ordinal(source: str, expected: str) -> None:
    assert normalize(source) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        # Счётная форма: родительный множественного требует количественного.
        pytest.param(
            "Прошло XX лет.",
            "Прошло двадцать лет.",
            id="counted_plural_stays_cardinal",
        ),
        # Монарх слева: номер принадлежит имени, а не следующему слову.
        pytest.param(
            "Людовик XIV король Франции.",
            "Людовик четырнадцатый король Франции.",
            id="regnal_name_keeps_its_number",
        ),
        # Заглавное слово справа — начало названия, а не определяемое
        # существительное.
        pytest.param(
            "Глава XX Смерть героя.",
            "Глава двадцатая Смерть героя.",
            id="heading_title_is_not_agreed",
        ),
        # Слово-рубрика слева: номер принадлежит ему, а не слову справа.
        pytest.param(
            "Часть XX съезд делегатов",
            "Часть двадцатая съезд делегатов",
            id="heading_noun_on_the_left_owns_the_number",
        ),
        # Однобуквенные C, L, D, M перед словом — латинские буквы, а не числа.
        pytest.param(
            "Отсек C закрыт наглухо.",
            "Отсек C закрыт наглухо.",
            id="single_letter_c_is_not_roman",
        ),
        # Дореформенный глагол на «ъ» морфология угадывает существительным;
        # правило берёт только словарные слова.
        pytest.param(
            "Карлъ XII обнаружилъ любовь къ военному дѣлу.",
            "Карлъ двенадцатый обнаружилъ любовь къ военному дѣлу.",
            id="pre_reform_verb_is_not_a_noun",
        ),
        # Короткое слово с точкой — сокращение, согласовывать не с чем.
        pytest.param(
            "Число стрельцов к концу XVI ст. выросло.",
            "Число стрельцов к концу шестнадцати ст. выросло.",
            id="dotted_abbreviation_is_not_agreed",
        ),
        # После римского числа глагол, а не существительное.
        pytest.param(
            "Император Пётр I правил долго.",
            "Император Пётр первый правил долго.",
            id="verb_after_regnal_number",
        ),
    ],
)
def test_roman_before_common_noun_guards(source: str, expected: str) -> None:
    assert normalize(source) == expected
