"""Sentence-start capitalization around abbreviation dots.

The rule has two sides that pull against each other: the dot of an unexpanded
abbreviation must not start a sentence, and a real sentence boundary after a
short word must keep its capital. Both directions are pinned here.
"""

from __future__ import annotations

import pytest

from ru_normalizr import NormalizeOptions, normalize
from ru_normalizr.caps import normalize_sentence_start_caps

TTS = NormalizeOptions.tts()


ABBREVIATION_DOT_CASES = (
    pytest.param(
        "Дело хранится в д. 5 архива областного суда.",
        "Дело хранится в д. пять архива областного суда.",
        id="dictionary_abbreviation_house",
    ),
    pytest.param(
        "Правки внесены в кор. 3 корректурного листа.",
        "Правки внесены в кор. три корректурного листа.",
        id="unknown_token_correction_sheet",
    ),
    pytest.param(
        "Требование указано в ч. 5 действующего регламента.",
        "Требование указано в ч. пять действующего регламента.",
        id="single_letter_abbreviation_part",
    ),
    pytest.param(
        "Условие описано в п. 3 подписанного договора.",
        "Условие описано в п. три подписанного договора.",
        id="single_letter_abbreviation_clause",
    ),
    pytest.param(
        # The case only guards against a capital letter after the abbreviation
        # dot. The page reference itself is read as "на странице седьмой", the
        # form the page-reference rule produces everywhere else.
        "Ссылка ведёт на стр. 7 приложения к договору.",
        "Ссылка ведёт на странице седьмой приложения к договору.",
        id="expanded_abbreviation_needs_no_guard",
    ),
)


SENTENCE_BOUNDARY_CASES = (
    pytest.param(
        "Он ушёл домой. она осталась ждать.",
        "Он ушёл домой. Она осталась ждать.",
        id="ordinary_word_ends_a_sentence",
    ),
    pytest.param(
        "Их было сто. он считал молча.",
        "Их было сто. Он считал молча.",
        id="short_real_word_ends_a_sentence",
    ),
    pytest.param(
        "Мы сделали это раз. он повторил дважды.",
        "Мы сделали это раз. Он повторил дважды.",
        id="homonym_of_an_abbreviation_ends_a_sentence",
    ),
    pytest.param(
        "Он посмотрел вверх. ад показался ближе.",
        "Он посмотрел вверх. Ад показался ближе.",
        id="two_letter_real_word_ends_a_sentence",
    ),
    pytest.param(
        "Она сказала нет. он не стал спорить.",
        "Она сказала нет. Он не стал спорить.",
        id="predicative_ends_a_sentence",
    ),
    pytest.param(
        "Это был я. он ушёл первым.",
        "Это был я. Он ушёл первым.",
        id="single_letter_pronoun_ends_a_sentence",
    ),
    pytest.param(
        "Ты идёшь? да. он тоже собирается.",
        "Ты идёшь? Да. Он тоже собирается.",
        id="question_mark_is_not_guarded",
    ),
    pytest.param(
        "Стой! он уже вышел.",
        "Стой! Он уже вышел.",
        id="exclamation_mark_is_not_guarded",
    ),
)


@pytest.mark.parametrize(("source", "expected"), ABBREVIATION_DOT_CASES)
def test_abbreviation_dot_does_not_capitalize_the_next_word(
    source: str, expected: str
) -> None:
    assert normalize(source, TTS) == expected


@pytest.mark.parametrize(("source", "expected"), SENTENCE_BOUNDARY_CASES)
def test_real_sentence_boundary_keeps_its_capital(source: str, expected: str) -> None:
    assert normalize_sentence_start_caps(source) == expected


@pytest.mark.parametrize(
    "source",
    [
        "Автор пояснил: т. е. документ содержит три раздела.",
        "Ошибка описана в п. а перечня требований.",
        "Значение указано в в. графе таблицы.",
        "Сноска стоит в с. примечании к разделу.",
    ],
    ids=["te", "letter_a", "letter_v", "letter_s"],
)
def test_single_letter_abbreviation_dot_is_not_a_boundary(source: str) -> None:
    # A one-letter word that could precede a real sentence end is always a
    # preposition or a conjunction, and neither can end a sentence.
    assert normalize_sentence_start_caps(source) == source


def test_capitalized_word_after_an_abbreviation_is_left_as_written():
    # A genuine sentence end after an abbreviation is already capitalized in the
    # source, so the guard costs nothing there.
    assert normalize_sentence_start_caps("Это стоит 5 руб. Дорого выходит.") == (
        "Это стоит 5 руб. Дорого выходит."
    )


def test_guard_does_not_reach_across_a_longer_word():
    # Only the token directly before the dot decides; a preceding abbreviation
    # further to the left must not suppress the boundary.
    assert normalize_sentence_start_caps("Смотри ул. Полевую. он живёт там.") == (
        "Смотри ул. Полевую. Он живёт там."
    )


def test_guard_ignores_a_capitalized_abbreviation():
    assert normalize_sentence_start_caps("Приехали на Ул. полевую утром.") == (
        "Приехали на Ул. Полевую утром."
    )


def test_initial_sequence_before_a_conjunction_is_not_a_sentence_boundary():
    source = "В комиссию вошли Петров В. Г. и Сидоров."
    assert normalize(source) == source


def test_disabled_option_leaves_the_text_untouched():
    source = "Он ушёл домой. она осталась ждать."
    assert normalize_sentence_start_caps(source, enabled=False) == source


@pytest.mark.parametrize(
    "source",
    [
        "Ионические колонии до р.х. не заставили переменить это имя моря.",
        "Ионические колонии (750 кораблей до р.х.) не заставили переменить имя.",
        "Персы пришли сюда до н.э. и остались здесь надолго.",
        "Он приехал в Москву, т.е. в столицу, и остался там надолго.",
        "В комиссию вошли Петров В.Г. и Сидоров, оба из уездного правления.",
    ],
    ids=["rh", "rh_in_parens", "ne", "te", "initials_without_spaces"],
)
def test_dotted_letter_chain_is_not_a_sentence_boundary(source: str) -> None:
    # «р.х.», «н.э.», «т.е.» — цепочка однобуквенных сокращений: точка перед
    # буквой прячет её от общего хвостового шаблона, и без отдельного правила
    # предложение ложно начиналось с «Не заставили».
    assert normalize_sentence_start_caps(source) == source


def test_dotted_letter_chain_keeps_a_real_boundary():
    # Настоящая граница после цепочки уже заглавная в источнике, а обычное
    # слово перед точкой цепочкой не считается.
    assert normalize_sentence_start_caps("Это было до н.э. Позже пришли греки.") == (
        "Это было до н.э. Позже пришли греки."
    )
    assert normalize_sentence_start_caps("Он закончил работу. дальше шли другие.") == (
        "Он закончил работу. Дальше шли другие."
    )
