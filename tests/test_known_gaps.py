"""Исполняемый список согласованных пробелов, которые пока не исправлены."""

import pytest

from ru_normalizr import NormalizeOptions, normalize

E2E_KNOWN_GAP_CASES = (
    # Родительное приложение после счётной группы тоже не управляет ею.
    #
    # НЕ РЕШАЕТСЯ алгоритмически: «отправили 4 человека» и «вижу 2 человека»
    # различаются только смыслом, а не формой — в обоих случаях счётная форма
    # «человека» стоит при одушевлённом прямом объекте. Проект осознанно читает
    # такую пару как «двух человек» (paucal_accusative_case, tests/test_cardinal_stage.py),
    # поэтому «четыре человека» здесь недостижимо без обратной регрессии.
    pytest.param(
        "К ним отправили 4 человека детей боярских.",
        "К ним отправили четыре человека детей боярских.",
        id="count_group_before_genitive_apposition",
        marks=pytest.mark.xfail(
            strict=True,
            reason="animate accusative convention renders the counted group in the genitive",
        ),
    ),
    # Диапазон лет с «годов» читается родительным единственного числа для
    # каждой границы, а не множественным числом порядкового.
    #
    # НЕ ИСПРАВЛЯЕТСЯ без регрессий: множественное число границ диапазона —
    # осознанное соглашение проекта, закреплённое несколькими проходящими
    # тестами (tests/test_year_stage.py::YearRangeTests, tests/test_coverage_edges.py
    # про «из 1990-1995 годов», tests/test_era_year_abbrev_regressions.py про
    # «44-45 гг. до н. э.»). Оба чтения нормативны, поэтому смена соглашения —
    # решение пользователя, а не побочный эффект правки этого пробела.
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
    # Латинское «K» после числа — кельвины, но та же запись означает тысячи
    # («300K подписчиков»), а кириллическое «К» после числа — ещё и литеру
    # корпуса или комнатность. Однозначного признака в форме нет, поэтому
    # запись оставлена названием литеры до появления контекстного правила
    # (в реестре единиц строки «k»/«к» намеренно закомментированы).
    pytest.param(
        "Образец нагрели до 300 K и выдержали час.",
        "Образец нагрели до трёхсот кельвинов и выдержали час.",
        id="latin_kelvin_symbol_after_number",
        marks=pytest.mark.xfail(
            strict=True,
            reason="bare K after a number is ambiguous between kelvin and a thousands suffix",
        ),
    ),
    # Перенос слова по строке: дефис в конце строки склеивает части слова, а
    # не разделяет их. Сейчас дефис между буквами превращается в тире
    # (LETTER_HYPHEN_PATTERN в preprocess_utils.py) без проверки переноса
    # строки, и середина слова читается как вставная конструкция.
    pytest.param(
        "Гра-\nфическим редактором пользовались все сотрудники отдела.",
        "Графическим редактором пользовались все сотрудники отдела.",
        id="line_break_hyphen_splits_a_wrapped_word",
        marks=pytest.mark.xfail(
            strict=True,
            reason="hyphen before a line break becomes a dash instead of joining the wrapped word",
        ),
    ),
    # Односимвольная единица-омограф предлога («В» — вольт, «с» — секунда)
    # раскрывается только в конце клаузы: should_skip_unit_candidate в
    # cardinals.py снимает кандидата, если за единицей стоит любой непустой
    # токен. Это защищает «пять с половиной» и «220 в сети», но теряет единицу
    # там, где следующее слово не может быть дополнением предлога — наречие,
    # предлог, союз. Правило должно смотреть на разбор следующего слова, а не
    # на его наличие.
    pytest.param(
        "Прибор работает при напряжении 220 В постоянно и не греется.",
        "Прибор работает при напряжении двести двадцать вольт постоянно и не греется.",
        id="preposition_homograph_unit_before_an_adverb",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a single-letter unit homographic with a preposition expands only at a clause end",
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
