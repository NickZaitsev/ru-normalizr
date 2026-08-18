"""Исполняемый список согласованных пробелов, которые пока не исправлены."""

import pytest

from ru_normalizr import NormalizeOptions, normalize

E2E_KNOWN_GAP_CASES = (
    # Счётная группа «N человек» — приложение к перечислению, а не дополнение
    # предлога: далёкое «в Киеве» не должно ни склонять числительное, ни
    # менять лемму счётного слова.
    pytest.param(
        "Конных и пеших людей всего в Киеве 3177 человек.",
        "Конных и пеших людей всего в Киеве три тысячи сто семьдесят семь человек.",
        id="count_group_after_distant_locative",
        marks=pytest.mark.xfail(
            strict=True,
            reason="distant locative place name leaks its case into the counted group",
        ),
    ),
    # Родительные определения перед счётной группой описывают предмет счёта,
    # а не управляют им.
    pytest.param(
        "Послано татар казанских и свияжских 100 человек.",
        "Послано татар казанских и свияжских сто человек.",
        id="count_group_after_genitive_attributes",
        marks=pytest.mark.xfail(
            strict=True,
            reason="preceding genitive attributes leak their case into the counted group",
        ),
    ),
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
    # Знак градуса перед «с. ш.» остаётся в тексте: сокращение широты
    # перекрывает разбор единицы, хотя «в. д.» разбирается верно.
    pytest.param(
        "Хребет лежит на 42° с. ш. и 74° в. д.",
        "Хребет лежит на сорок два градуса северной широты и семьдесят четыре "
        "градуса восточной долготы.",
        id="degree_sign_before_latitude_abbreviation",
        marks=pytest.mark.xfail(
            strict=True,
            reason="latitude abbreviation blocks the degree unit and leaves ° in the output",
        ),
    ),
    # Сокращение «Ц.» в конце предложения должно раскрываться в «Цельсия»
    # и сохранять точку как границу предложения.
    pytest.param(
        "Температура была +12,5° Ц. Здесь мы остановились.",
        "Температура была плюс двенадцать целых пять десятых градуса Цельсия. "
        "Здесь мы остановились.",
        id="celsius_abbreviation_at_sentence_end",
        marks=pytest.mark.xfail(
            strict=True,
            reason="Ц. is spelled as a letter name and swallows the sentence boundary",
        ),
    ),
    # Запятая после точки сокращения — часть структуры фразы; вычищать её
    # нельзя, иначе TTS теряет паузу и склеивает части предложения.
    pytest.param(
        "Дом стоял в Мыльников пер., рядом была типография.",
        "Дом стоял в Мыльников пер., рядом была типография.",
        id="comma_after_abbreviation_dot",
        marks=pytest.mark.xfail(
            strict=True,
            reason="cleanup_malformed_punctuation collapses abbreviation dot plus comma to a dot",
        ),
    ),
    # Точка неизвестного сокращения не начинает предложение, поэтому
    # следующее числительное остаётся строчным.
    pytest.param(
        "Ссылка дана на примеч. 257 в конце главы.",
        "Ссылка дана на примеч. двести пятьдесят семь в конце главы.",
        id="capitalization_after_unknown_abbreviation",
        marks=pytest.mark.xfail(
            strict=True,
            reason="dot of an out-of-dictionary abbreviation is treated as a sentence end",
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
    # Латинская буква-омоглиф внутри кириллического слова — дефект набора,
    # а не латинизируемый токен.
    pytest.param(
        "Bсе рисунки исполнены графическим институтом.",
        "Все рисунки исполнены графическим институтом.",
        id="latin_homoglyph_inside_cyrillic_word",
        marks=pytest.mark.xfail(
            strict=True,
            reason="latin homoglyph starting a Cyrillic word is latinized as a letter name",
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
