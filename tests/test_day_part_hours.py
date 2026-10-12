"""Час при части суток и падеж числа под управлением слева.

«в 10 утра» читалось «в десятого утра»: «утра» — родительный единственного,
и правило «12 числа» принимало часть суток за число месяца. «локоны волос
94 женщин» читались именительным, хотя падеж числу задаёт слово слева.
"""

from __future__ import annotations

import pytest

from ru_normalizr import NormalizeOptions, normalize


@pytest.fixture(scope="module")
def tts_options() -> NormalizeOptions:
    return NormalizeOptions.tts()


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Это было в 10 утра.", "Это было в десять утра."),
        ("Пришёл в 8 утра.", "Пришёл в восемь утра."),
        ("Ушёл в 10 вечера.", "Ушёл в десять вечера."),
        ("В 5 утра два констебля вышли.", "В пять утра два констебля вышли."),
        ("Обед в 12 дня.", "Обед в двенадцать дня."),
        ("Около 11 вечера погас свет.", "Около одиннадцати вечера погас свет."),
    ],
)
def test_hour_before_day_part_is_cardinal(
    source: str, expected: str, tts_options: NormalizeOptions
) -> None:
    assert normalize(source, tts_options) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("До 5 дня болезни он держался.", "До пятого дня болезни он держался."),
        ("На 3 день пути стало легче.", "На три день пути стало легче."),
        ("Приняли на 27 неделю.", "Приняли на двадцать седьмую неделю."),
        ("Это было в 9 часу.", "Это было в девятом часу."),
    ],
)
def test_ordinal_reading_for_dates_is_kept(
    source: str, expected: str, tts_options: NormalizeOptions
) -> None:
    assert normalize(source, tts_options) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "Полиция обнаружила локоны волос 94 женщин.",
            "Полиция обнаружила локоны волос девяноста четырёх женщин.",
        ),
        ("Он нашёл локоны 94 женщин.", "Он нашёл локоны девяноста четырёх женщин."),
        ("Список 33 участников готов.", "Список тридцати трёх участников готов."),
    ],
)
def test_genitive_from_the_governor_on_the_left(
    source: str, expected: str, tts_options: NormalizeOptions
) -> None:
    assert normalize(source, tts_options) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Прошло 22 суток.", "Прошло двадцать двое суток."),
        ("Купил 24 книги.", "Купил двадцать четыре книги."),
        ("Тут 94 женщины.", "Тут девяносто четыре женщины."),
        ("В зале 24 человека.", "В зале двадцать четыре человека."),
    ],
)
def test_counted_group_without_a_governor_stays_nominative(
    source: str, expected: str, tts_options: NormalizeOptions
) -> None:
    assert normalize(source, tts_options) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "Бронепоезд № 73 войск НКВД охранял дороги.",
            "Бронепоезд номер семьдесят три войск эн ка вэ дэ охранял дороги.",
        ),
        (
            "Бронепоезд номер 73 войск НКВД охранял дороги.",
            "Бронепоезд номер семьдесят три войск эн ка вэ дэ охранял дороги.",
        ),
        ("Пункт 22 правил нарушен.", "Пункт двадцать два правил нарушен."),
    ],
)
def test_number_after_a_label_word_is_a_name_not_a_counted_group(
    source: str, expected: str, tts_options: NormalizeOptions
) -> None:
    assert normalize(source, tts_options) == expected
