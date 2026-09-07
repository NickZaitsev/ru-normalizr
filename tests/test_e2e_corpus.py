"""Passing E2E-корпус плотных реалистичных фраз для TTS-нормализации.

Кроме таблицы `E2E_CASES`, написанной прямо в коде, здесь прогоняется
современный корпус из `tests/data/modern_normalization.json`: короткие абзацы
делового, новостного, бытового и технического языка, у которых ожидание
вычитано вручную и снабжено объяснением.
"""

import json
from pathlib import Path

import pytest

from ru_normalizr import NormalizeOptions, Normalizer, normalize

from .conftest import CheckTts

#: Профили нормализации, допустимые в JSON-корпусе.
MODERN_CORPUS_PROFILES = {
    "tts": NormalizeOptions.tts,
    "safe": NormalizeOptions.safe,
}
MODERN_CORPUS_PATH = Path(__file__).parent / "data" / "modern_normalization.json"


def _modern_corpus_data() -> list[dict[str, str]]:
    """Кейсы современного корпуса как они записаны в JSON."""
    data = json.loads(MODERN_CORPUS_PATH.read_text(encoding="utf-8"))
    return list(data["cases"])


MODERN_CORPUS_DATA = _modern_corpus_data()
#: Случаи современного корпуса: идентификатор, профиль, вход, ожидание.
MODERN_CORPUS_CASES = tuple(
    (case["id"], case["profile"], case["source"], case["expected"])
    for case in MODERN_CORPUS_DATA
)
#: Репрезентативная выборка того же корпуса с ожиданием профиля safe.
MODERN_CORPUS_SAFE_CASES = tuple(
    (case["id"], "safe", case["source"], case["expected_safe"])
    for case in MODERN_CORPUS_DATA
    if "expected_safe" in case
)

E2E_CASES = (
    (
        "discount_and_money",
        "Скидка 17,5% снизила цену с 8 000 до 6 600 руб.",
        "Скидка семнадцать целых пять десятых процента снизила цену с восьми тысяч "
        "до шести тысяч шестисот рублей.",
    ),
    (
        "train_and_platform",
        "Поезд № 742 отправится с 3-й платформы в 06:05.",
        "Поезд номер семьсот сорок два отправится с третьей платформы в шесть, ноль пять.",
    ),
    (
        "chapter_range",
        "В главах IV–VI и приложении № 2 описаны 3 основных сценария.",
        "В четвёртой — шестой главах и приложении номер два описаны три основных сценария.",
    ),
    (
        "year_range",
        "С 1999 по 2001 г. население выросло на 12%.",
        "С тысяча девятьсот девяносто девятого по две тысячи первый год население "
        "выросло на двенадцать процентов.",
    ),
    (
        "data_transfer",
        "Файл объёмом 2,5 ГБ загрузился на 87% со скоростью 100 МБ/с.",
        "Файл объёмом две целых пять десятых гигабайта загрузился на восемьдесят семь "
        "процентов со скоростью сто мегабайтов в секунду.",
    ),
    (
        "medicine_dosage",
        "Принимайте по 1/2 таблетки 3 раза в день в течение 7 суток.",
        "Принимайте по одной второй таблетки три раза в день в течение семи суток.",
    ),
    (
        "child_age",
        "Ребёнку исполнилось 1,5 года, а его брату — 3 года.",
        "Ребёнку исполнилось одна целая пять десятых года, а его брату — три года.",
    ),
    (
        "mixed_length_units",
        "Рост ребёнка — 1 м 24 см, а длина шага — 48 см.",
        "Рост ребёнка — один метр двадцать четыре сантиметра, а длина шага — сорок "
        "восемь сантиметров.",
    ),
    (
        "mixed_weight_units",
        "Посылка весит 2 кг 350 г, упаковка добавляет ещё 75 г.",
        "Посылка весит два килограмма триста пятьдесят грамм, упаковка добавляет ещё "
        "семьдесят пять грамм.",
    ),
    (
        "network_bandwidth",
        "Канал 1 Гбит/с передал 12,5 ГБ за 100 с.",
        "Канал один гигабит в секунду передал двенадцать целых пять десятых гигабайта за "
        "сто секунд.",
    ),
    (
        "software_version",
        "Обновите приложение с версии 2.10.3 до версии 2.11.0, сборка 451.",
        "Обновите приложение с версии два точка десять точка три до версии два точка "
        "одиннадцать точка ноль, сборка четыреста пятьдесят один.",
    ),
    (
        "decade_abbreviation",
        "В 1990-е гг. предприятие выпускало до 25 тыс. машин в год.",
        "В тысяча девятьсот девяностые годы предприятие выпускало до двадцати пяти тысяч "
        "машин в год.",
    ),
    (
        "time_with_seconds",
        "Система зафиксировала событие в 14:03:07 и повторила проверку в 14:05:00.",
        "Система зафиксировала событие в четырнадцать часов три минуты семь секунд и "
        "повторила проверку в четырнадцать часов пять минут ноль секунд.",
    ),
    (
        "audio_parameters",
        "Запись сохранена с частотой 44,1 кГц и битрейтом 320 кбит/с.",
        "Запись сохранена с частотой сорок четыре целых одна десятая килогерца и "
        "битрейтом триста двадцать килобит в секунду.",
    ),
    (
        "large_approximate_quantity",
        "В 2025 г. аудитория сервиса достигла 2,3 млрд пользователей в 190 странах.",
        "В две тысячи двадцать пятом году аудитория сервиса достигла двух целых трёх "
        "десятых миллиарда пользователей в ста девяноста странах.",
    ),
    (
        "flight_number",
        "Рейс SU 213 вылетает из терминала B в 23:40.",
        "Рейс эс юю двести тринадцать вылетает из терминала би в двадцать три, сорок.",
    ),
    (
        "numeric_suffixes_dense",
        "В 7-ми классах выбрали 7-ую книгу из 2-ух вариантов для 101-го участника.",
        "В семи классах выбрали седьмую книгу из двух вариантов для сто первого участника.",
    ),
    (
        "numeric_suffix_codes_dense",
        "Коды X7ми, X7-ми и A320-й сверили с версиями 2.1-я и 1,5-й.",
        "Коды экс7ми, экс7-ми и э320-й сверили с версиями 2.1-я и 1,5-й.",
    ),
)


@pytest.mark.parametrize(
    ("_name", "source", "expected"), E2E_CASES, ids=[case[0] for case in E2E_CASES]
)
def test_tts_e2e_normalization_corpus(
    check_tts: CheckTts, _name: str, source: str, expected: str
) -> None:
    check_tts(source, expected)


def _fail_modern_corpus(source: str, expected: str, actual: str) -> None:
    """Расхождение современного корпуса — вместе с входом и обоими чтениями."""
    pytest.fail(
        "Чтение современного корпуса разошлось с ожиданием.\n"
        f"  вход:      {source}\n"
        f"  ожидалось: {expected}\n"
        f"  получено:  {actual}",
        pytrace=False,
    )


@pytest.mark.parametrize(
    ("_case_id", "profile", "source", "expected"),
    MODERN_CORPUS_CASES,
    ids=[case[0] for case in MODERN_CORPUS_CASES],
)
def test_tts_modern_corpus(
    _case_id: str, profile: str, source: str, expected: str
) -> None:
    actual = normalize(source, MODERN_CORPUS_PROFILES[profile]())
    if actual != expected:
        _fail_modern_corpus(source, expected, actual)


@pytest.mark.parametrize(
    ("_case_id", "profile", "source", "expected"),
    MODERN_CORPUS_SAFE_CASES,
    ids=[case[0] for case in MODERN_CORPUS_SAFE_CASES],
)
def test_safe_modern_corpus(
    _case_id: str, profile: str, source: str, expected: str
) -> None:
    actual = normalize(source, MODERN_CORPUS_PROFILES[profile]())
    if actual != expected:
        _fail_modern_corpus(source, expected, actual)


def test_modern_corpus_does_not_depend_on_call_order() -> None:
    """Один Normalizer на весь корпус: кеши не должны зависеть от порядка входов.

    Кеши числительных и единиц живут в экземпляре, поэтому неверный ключ
    проявляется только при повторных вызовах — и именно на второй перестановке
    входов, а не на отдельной фразе.
    """
    for profile, options in MODERN_CORPUS_PROFILES.items():
        cases = [
            (case_id, source, expected)
            for case_id, case_profile, source, expected in (
                *MODERN_CORPUS_CASES,
                *MODERN_CORPUS_SAFE_CASES,
            )
            if case_profile == profile
        ]
        normalizer = Normalizer(options())
        for order in (cases, list(reversed(cases)), cases):
            for case_id, source, expected in order:
                actual = normalizer.normalize(source)
                assert actual == expected, (
                    f"{case_id}: чтение изменилось при повторном вызове\n"
                    f"  ожидалось: {expected}\n"
                    f"  получено:  {actual}"
                )
