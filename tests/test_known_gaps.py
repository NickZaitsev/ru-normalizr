"""Исполняемый список согласованных пробелов, которые пока не исправлены."""

import pytest

from ru_normalizr import NormalizeOptions, normalize

E2E_KNOWN_GAP_CASES = (
    # Родительное приложение после счётной группы тоже не управляет ею.
    pytest.param(
        "К ним отправили 4 человека детей боярских.",
        "К ним отправили четыре человека детей боярских.",
        id="count_group_before_genitive_apposition",
        marks=pytest.mark.xfail(
            strict=True,
            reason="following genitive apposition leaks its case into the counted group",
        ),
    ),
    # Диапазон лет с «годов» читается родительным единственного числа для
    # каждой границы, а не множественным числом порядкового.
    pytest.param(
        "Летопись сообщает о событиях 1475—1481 годов подробно.",
        "Летопись сообщает о событиях тысяча четыреста семьдесят пятого — "
        "тысяча четыреста восемьдесят первого годов подробно.",
        id="year_range_before_plural_years",
        marks=pytest.mark.xfail(
            strict=True,
            reason="year range before plural годов renders plural ordinals instead of genitive singular",
        ),
    ),
    # Римская цифра при сокращении тома — порядковое числительное, как и в
    # «том II»; после точки сокращения регистр тоже не меняется.
    pytest.param(
        "Собрание грамот. Т. II, № 45 хранится в архиве.",
        "Собрание грамот. Т. второй, номер сорок пять хранится в архиве.",
        id="roman_volume_after_volume_abbreviation",
        marks=pytest.mark.xfail(
            strict=True,
            reason="roman numeral after an abbreviated volume marker renders as a cardinal",
        ),
    ),
    # Двойная датировка «7092 (1582) года»: слово «года» стоит в источнике
    # один раз и не должно дублироваться перед скобкой.
    pytest.param(
        "Грамота царя от 16 ноября 7092 (1582) года была опальной.",
        "Грамота царя от шестнадцатого ноября семь тысяч девяносто второго "
        "(одна тысяча пятьсот восемьдесят два) года была опальной.",
        id="dual_dating_duplicates_year_head",
        marks=pytest.mark.xfail(
            strict=True,
            reason="year stage inserts a second года before the bracketed equivalent",
        ),
    ),
    # Химическая формула требует отдельной грамматики элементов, индексов и
    # валентных обозначений; общий обработчик буквенно-цифровых токенов будет
    # конфликтовать с моделями, кодами и обычными аббревиатурами.
    pytest.param(
        "Раствор H₂SO₄ концентрацией 5% хранили при 20 °C.",
        "Раствор аш два эс о четыре концентрацией пять процентов хранили при двадцати "
        "градусах Цельсия.",
        id="chemical_formula",
        marks=pytest.mark.xfail(
            strict=True,
            reason="structured chemical formula grammar is outside generic token normalization",
        ),
    ),
    # Математическая формула требует парсера выражений: смысл букв, операторов
    # и степеней нельзя безопасно вывести из соседних слов без риска задеть
    # идентификаторы и единицы измерения.
    pytest.param(
        "В учебнике формула E = mc² приведена в главе III.",
        "В учебнике формула е равно эм цэ в квадрате приведена в главе третьей.",
        id="physics_formula",
        marks=pytest.mark.xfail(
            strict=True,
            reason="structured mathematical expression grammar is not generic prose normalization",
        ),
    ),
)


@pytest.mark.parametrize(("source", "expected"), E2E_KNOWN_GAP_CASES)
def test_tts_e2e_normalization_known_gaps(source: str, expected: str) -> None:
    assert normalize(source, NormalizeOptions.tts()) == expected
