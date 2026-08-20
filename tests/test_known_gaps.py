"""Исполняемый список согласованных пробелов, которые пока не исправлены."""

import pytest

from .conftest import CheckTts

#: Пробелы, найденные точечными проверками, а не сплошным чтением книги.
HANDWRITTEN_GAP_CASES = (
    # Числовой суффикс перед дореформенным составным прилагательным: «фунтовыя»
    # неизвестно словарю, и резолвер суффикса оставляет «-ти» приклеенным
    # («шестнадцати-ти-фунтовыя»). В современной орфографии («фунтовые»)
    # та же запись сворачивается верно.
    pytest.param(
        "Полевая артиллерія имѣла 8-ми- и 16-ти-фунтовыя пушки.",
        "Полевая артиллерія имѣла восьми- и шестнадцатифунтовыя пушки.",
        id="numeric_suffix_before_pre_reform_compound_adjective",
        marks=pytest.mark.xfail(
            strict=True,
            reason="suffix resolver keeps «-ти» glued when the compound adjective "
            "is unknown to the morphology (pre-reform spelling)",
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


#: Найдено прогоном по книжному корпусу benchmarks/corpus.
CORPUS_SWEEP_GAP_CASES = (
    # Незнакомое сокращение с точкой принимается за конец предложения, и
    # следующее слово получает заглавную букву.
    pytest.param(
        "Отряд состоял из генер. штаба подполковника и трёх писарей.",
        "Отряд состоял из генер. штаба подполковника и трёх писарей.",
        id="sentence_caps_after_unknown_abbreviation",
        marks=pytest.mark.xfail(
            strict=True,
            reason="an unknown abbreviation with a dot capitalizes the next word",
        ),
    ),
)


#: Найдено сплошным чтением книги 06 (Семёнов-Тян-Шанский).
BOOK_06_GAP_CASES = (
    # Угловые минуты после градусов не читаются: апостроф остаётся отдельным
    # символом.
    pytest.param(
        "Пиренеи лежат между 42°30' и 43° северной широты по всей длине.",
        "Пиренеи лежат между сорока двумя градусами тридцатью минутами "
        "и сорока тремя градусами северной широты по всей длине.",
        id="arc_minutes_after_degrees",
        marks=pytest.mark.xfail(
            strict=True,
            reason="arc minutes after a degree sign are left as a bare apostrophe",
        ),
    ),
    # Сокращение единицы после смешанной дроби не раскрывается: остаётся точка
    # и заглавная буква у следующего слова.
    pytest.param(
        "За прогоны платили по 1 1/2 коп. с версты и лошади на почтовом тракте.",
        "За прогоны платили по одной целой одной второй копейки с версты "
        "и лошади на почтовом тракте.",
        id="unit_abbreviation_after_mixed_fraction",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a unit abbreviation after a mixed fraction is left unexpanded",
        ),
    ),
    # Многоточие внутри цитаты принимается за конец предложения, и следующее
    # слово получает заглавную букву.
    pytest.param(
        "Он писал так: «.... факты, разработанные лучшими учёными нашего века, скудны».",
        'Он писал так: ".... факты, разработанные лучшими учёными нашего века, скудны".',
        id="caps_after_inline_ellipsis",
        marks=pytest.mark.xfail(
            strict=True,
            reason="an ellipsis inside a quotation capitalizes the next word",
        ),
    ),
)


#: Найдено сплошным чтением книги 05 (Небольсин).
BOOK_05_GAP_CASES = (
    # Заглавная буква в начале строки после числа принимается за единицу:
    # «20 А. Тюменка» читается «двадцать ампер». Алгоритмически не решается
    # без понимания макета исходника: «А.» здесь — буквенная рубрика списка,
    # формально неотличимая от символа ампера после числа; любой запрет
    # «числу + А.» сломал бы настоящие амперы в техническом тексте.
    pytest.param(
        "20 А. Тюменка-речка течёт сто тридцать вёрст до устья.",
        "Двадцать. А. Тюменка-речка течёт сто тридцать вёрст до устья.",
        id="capital_letter_after_a_number_read_as_ampere",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a capital letter after a number is read as a unit symbol",
        ),
    ),
    # Диапазон страниц в конце ссылки теряет тире и читается перечислением.
    pytest.param(
        "Ссылка дана так: Карамзин. Т. IX. С. 381—382.",
        "Ссылка дана так: Карамзин. Том девятый. Страницы триста восемьдесят один — "
        "триста восемьдесят два.",
        id="page_range_at_the_end_of_a_reference",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a page range closing a reference is read as an enumeration",
        ),
    ),
    # Приклеенный к слову номер сноски читается вслух как число.
    pytest.param(
        "Так пинежане8 и мезенцы ходили на промысел за Камень каждое лето.",
        "Так пинежане и мезенцы ходили на промысел за Камень каждое лето.",
        id="footnote_digit_glued_to_a_word",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a footnote number glued to a word is read aloud",
        ),
    ),
    # Апостроф внутри латинского слова отбивается пробелами с обеих сторон.
    pytest.param(
        "В книге стоит фраза est fait de millet et d’orge monde на полях.",
        "В книге стоит фраза эст фейт дэ милэт эт дорж манд на полях.",
        id="apostrophe_inside_a_latin_word",
        marks=pytest.mark.xfail(
            strict=True,
            reason="an apostrophe inside a latin word is split off with spaces",
        ),
    ),
)


#: Найдено сплошным чтением книги 02 («История русской армии и флота»).
BOOK_02_GAP_CASES = (
    # Номер пункта перечисления «1)» читается количественным «один».
    pytest.param(
        "Служили сначала иноземцы, а потом: 1) «гулящие некрепостные люди», "
        "2) дворяне и дети боярские.",
        'Служили сначала иноземцы, а потом: первое) "гулящие некрепостные люди", '
        "второе) дворяне и дети боярские.",
        id="numbered_list_marker_read_as_cardinal",
        marks=pytest.mark.xfail(
            strict=True,
            reason="an enumeration marker 1) is read as the cardinal один",
        ),
    ),
    # «ч.» в значении «человек» читается как «часов». Алгоритмически не
    # решается надёжно: «(42 000 ч.)» и «(42 000 ч. боя)» различаются только
    # военно-историческим смыслом; надёжного морфологического признака,
    # отделяющего людей от часов при «ч.» без соседних слов, нет.
    pytest.param(
        "Румянцев с 115 орудиями (42 000 ч.) разбил наголову отряд турок.",
        "Румянцев с ста пятнадцатью орудиями (сорок две тысячи человек) "
        "разбил наголову отряд турок.",
        id="ch_abbreviation_read_as_hours",
        marks=pytest.mark.xfail(
            strict=True,
            reason="ч. meaning человек is read as hours",
        ),
    ),
)


#: Найдено сплошным чтением книги 02b (та же книга, дореформенная орфография).
BOOK_02B_GAP_CASES = (
    # «л.» в значении «лет» читается как «литров». Алгоритмически не решается
    # нормально: нужен смысловой разбор «Только 24 л. <фамилия>» (возраст в
    # родительном падеже), а ожидание к тому же в дореформенной орфографии
    # («лѣтъ», «четырёхъ»), которую конвейер не воспроизводит.
    pytest.param(
        "Только 24 л. Суворовъ, пройдя всѣ нижнія званія, получилъ первый чинъ.",
        "Только двадцати четырёхъ лѣтъ Суворовъ, пройдя всѣ нижнія званія, получилъ первый чинъ.",
        id="l_abbreviation_read_as_litres",
        marks=pytest.mark.xfail(
            strict=True,
            reason="л. meaning years is read as litres",
        ),
    ),
)


#: Найдено сплошным чтением книги 04 (Костомаров, «Русская история»).
BOOK_04_GAP_CASES = (
    # Сокращение «гл.» после числа раскрывается в именительном, а само число
    # остаётся количественным.
    #
    # НЕ РЕШАЕТСЯ без пересмотра конвенции: ожидание требует полного раскрытия
    # маркеров «гл.»/«кн.» с падежом, а принятая конвенция (см.
    # ABBREVIATED_HEADING_MARKER_CASES в test_known_gap_fixes.py) сознательно
    # сохраняет маркер сокращённым («т. втором», «кн. пятую»). Отдельный дефект
    # «в восемь глава» — падеж арабского номера перед «гл.» — решается в рамках
    # кластера падежного согласования числительных.
    pytest.param(
        "Об этом сказано в 8 гл. кн. Царств, и с тем согласны все толкователи.",
        "Об этом сказано в восьмой главе книги Царств, и с тем согласны все толкователи.",
        id="chapter_abbreviation_after_a_number",
        marks=pytest.mark.xfail(
            strict=True,
            reason="гл. after a number is expanded in the nominative and the number stays cardinal",
        ),
    ),
)


#: Найдено сплошным чтением книги 03 (Карамзин, «История государства Российского»).
BOOK_03_GAP_CASES = (
    # Сокращение «кн.» перед римским номером не раскрывается, а номер получает
    # женский род по самому сокращению.
    #
    # НЕ РЕШАЕТСЯ без пересмотра конвенции: номер уже читается правильно
    # («в кн. четвёртой»), а раскрытие маркера «кн.» в «книге» противоречит
    # принятой конвенции сокращённых маркеров рубрикации (см.
    # ABBREVIATED_HEADING_MARKER_CASES в test_known_gap_fixes.py).
    pytest.param(
        "Геродот пишет об этом в кн. IV, где описаны обычаи скифов и соседних народов.",
        "Геродот пишет об этом в книге четвёртой, где описаны обычаи скифов и соседних народов.",
        id="book_abbreviation_before_a_roman_numeral",
        marks=pytest.mark.xfail(
            strict=True,
            reason="кн. before a roman numeral is not expanded and the numeral agrees with it",
        ),
    ),
    # Восклицательный знак перед закрывающей кавычкой не считается концом
    # предложения, и следующее слово остаётся строчным.
    pytest.param(
        "Он воскликнул: «Спасёт вас Господь от тирана!» 15 июня царь выехал из Новагорода.",
        'Он воскликнул: "Спасёт вас Господь от тирана!" Пятнадцатого июня '
        "царь выехал из Новагорода.",
        id="no_caps_after_an_exclamation_inside_quotes",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a sentence-ending exclamation before a closing quote does not capitalise",
        ),
    ),
)


#: Найдено сплошным чтением книги 01 («История России с древнейших времён»).
BOOK_01_GAP_CASES = (
)


#: Полный список: разбит по происхождению, потому что пробелы одной книги
#: правятся и снимаются пачкой, а плоская таблица на сотню записей
#: не даёт увидеть, что именно принесло каждое сплошное чтение.
E2E_KNOWN_GAP_CASES = (
    *HANDWRITTEN_GAP_CASES,
    *CORPUS_SWEEP_GAP_CASES,
    *BOOK_06_GAP_CASES,
    *BOOK_05_GAP_CASES,
    *BOOK_02_GAP_CASES,
    *BOOK_02B_GAP_CASES,
    *BOOK_04_GAP_CASES,
    *BOOK_03_GAP_CASES,
    *BOOK_01_GAP_CASES,
)


@pytest.mark.parametrize(("source", "expected"), E2E_KNOWN_GAP_CASES)
def test_tts_e2e_normalization_known_gaps(
    check_tts: CheckTts, source: str, expected: str
) -> None:
    check_tts(source, expected)
