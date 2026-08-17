"""Исполняемый список согласованных пробелов, которые пока не исправлены."""

import pytest

from ru_normalizr import NormalizeOptions, normalize

E2E_KNOWN_GAP_CASES = (
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
