"""Исполняемый список согласованных пробелов, которые пока не исправлены.

Каждый оставшийся здесь пробел снабжён комментарием, почему он не закрыт:
запись неоднозначна в самом исходнике, ожидание противоречит принятой
конвенции чтения или требует подсистемы за границами нормализации прозы.
Пробелы, которые удалось закрыть, переехали в `test_known_gap_fixes.py`
обычными проверками с закреплёнными краевыми случаями.
"""

import pytest

from .conftest import CheckTts

#: Пробелы, найденные точечными проверками, а не сплошным чтением книги.
HANDWRITTEN_GAP_CASES = (
    # НЕ РЕШАЕТСЯ: запись неоднозначна в самом исходнике. Латинское «K» после
    # числа — кельвины, но та же запись означает тысячи («300K подписчиков»),
    # а кириллическое «К» после числа — ещё и литеру корпуса или комнатность.
    # Однозначного признака в форме нет, поэтому запись оставлена названием
    # литеры до появления контекстного правила (в реестре единиц строки
    # «k»/«к» намеренно закомментированы).
    pytest.param(
        "Образец нагрели до 300 K и выдержали час.",
        "Образец нагрели до трёхсот кельвинов и выдержали час.",
        id="latin_kelvin_symbol_after_number",
        marks=pytest.mark.xfail(
            strict=True,
            reason="bare K after a number is ambiguous between kelvin and a thousands suffix",
        ),
    ),
    # НЕ РЕШАЕТСЯ в рамках нормализации прозы: химическая формула требует
    # отдельной грамматики элементов, индексов и валентных обозначений, а
    # общий обработчик буквенно-цифровых токенов будет конфликтовать с
    # моделями, кодами и обычными аббревиатурами.
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
    # НЕ РЕШАЕТСЯ в рамках нормализации прозы: математическая формула требует
    # парсера выражений, а смысл букв, операторов и степеней нельзя безопасно
    # вывести из соседних слов без риска задеть идентификаторы и единицы
    # измерения.
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
    # Голый год после «в» читается годом, если дальше идёт глагол или
    # существительное («в тысяча семьсот шестом он указал»), но наречие между
    # ними признак года снимает, и год превращается в обычное число.
    # Расхождение найдено разбором полного корпуса: до `74c0e4f` фраза читалась
    # верно, правило падежей после этого стало решать её как число.
    pytest.param(
        "Донесение 1705 года говорит неопределённо о воровстве, а в 1706 уже "
        "указывает прямо на лица.",
        "Донесение тысяча семьсот пятого года говорит неопределённо о воровстве, а "
        "в тысяча семьсот шестом уже указывает прямо на лица.",
        id="bare_year_before_an_adverb_reads_as_a_plain_number",
        marks=pytest.mark.xfail(
            strict=True,
            reason="an adverb between the year and its verb drops the year reading",
        ),
    ),
)


#: Найдено сплошным чтением книги 06 (Семёнов-Тян-Шанский).
BOOK_06_GAP_CASES = ()


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
)


#: Найдено сплошным чтением книги 02 («История русской армии и флота»).
BOOK_02_GAP_CASES = (
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
    # Диапазон римских веков распадается на дореформенной орфографии: «половинѣ»
    # не опознаётся вершиной, левая римская цифра остаётся сама по себе и
    # читается именем латинской буквы («икс»). В современной орфографии та же
    # фраза читается верно. НЕ РЕШАЕТСЯ без разбора дореформенных форм: сам
    # ожидаемый ответ конвейер тоже не воспроизводит.
    pytest.param(
        "Позднѣе въ нее вошли славяне, а къ концу X — половинѣ XI вв. дружины "
        "уже были преимущественно изъ славянъ.",
        "Позднѣе въ нее вошли славяне, а къ концу десятого — половинѣ "
        "одиннадцатого вѣковъ дружины уже были преимущественно изъ славянъ.",
        id="roman_century_range_breaks_on_pre_reform_spelling",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the roman century range needs a recognizable head noun, and "
            "pre-reform forms are outside the morphology dictionary",
        ),
    ),
)


#: Найдено сплошным чтением книги 04 (Костомаров, «Русская история»).
BOOK_04_GAP_CASES = (
    # Осталась только конвенция: «кн.» перед именем не раскрывается.
    #
    # Падеж и порядковость номера перед «гл.» исправлены 7 сентября: теперь
    # читается «в восьмой главе кн. Царств» вместо «в восемь глава», см.
    # LEADING_HEADING_NUMBER_CASES в test_known_gap_fixes.py. НЕ РЕШАЕТСЯ без
    # пересмотра конвенции остаток: ожидание требует раскрыть и «кн.», а
    # принятая конвенция (см. ABBREVIATED_HEADING_MARKER_CASES там же)
    # сознательно сохраняет маркер сокращённым («т. втором», «кн. пятую»).
    pytest.param(
        "Об этом сказано в 8 гл. кн. Царств, и с тем согласны все толкователи.",
        "Об этом сказано в восьмой главе книги Царств, и с тем согласны все толкователи.",
        id="chapter_abbreviation_after_a_number",
        marks=pytest.mark.xfail(
            strict=True,
            reason="кн. before a proper name keeps its abbreviated form by convention",
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
)


#: Найдено при восстановлении пробела после точки сокращения (план
#: 2026-08-22-fix-real-book-regressions): пробел вернулся, но заглавная после
#: точки осталась.
DOT_ABBREVIATION_CAPS_GAP_CASES = (
    # Стадия расстановки заглавных считает точку концом предложения, когда
    # слово перед ней не опознано как сокращение. «Fig.» после латинизации
    # превращается в «фиг.» — обычное словарное слово, а «Kfz.» — в «кфз.»,
    # которого в словаре нет вовсе. Дефект не в расклейке: у исходника с
    # пробелом («Смотри Fig. 3 внизу.») тот же результат. Для TTS пауза идёт
    # от точки, а не от регистра, поэтому исправление ждёт отдельной задачи по
    # стадии заглавных.
    pytest.param(
        "Схема этого узла приведена в Fig.3 на следующей странице.",
        "Схема этого узла приведена в фиг. три на следующей странице.",
        id="latin_abbreviation_dot_before_digit_keeps_lowercase",
        marks=pytest.mark.xfail(
            strict=True,
            reason="sentence caps treat an unrecognized abbreviation dot as a sentence end",
        ),
    ),
)


#: Латинская дата римскими цифрами через точки разобрана 7 сентября, см.
#: DOTTED_ROMAN_CASES в test_known_gap_fixes.py. Раздел оставлен пустым: он
#: описывает источник находки, а не отдельный класс дефектов.
DOTTED_ROMAN_GAP_CASES = ()


#: Найдено сплошным чтением книги 01 («История России с древнейших времён»).
BOOK_01_GAP_CASES = (
)


#: Найдено ревью 1.1.0 (3 сентября 2026) на современной прозе: договоры,
#: новости, техника, кулинария. Книжный корпус XIX века таких конструкций не
#: содержит, поэтому ни один из этих пробелов тестами не ловился. Подробный
#: разбор причин и предлагаемых правок — docs/ISSUES.md.
REVIEW_2026_09_GAP_CASES = (
    # Римский номер рубрики раскрывает сокращение «гл.», но само
    # существительное остаётся в именительном: падеж от предлога получает
    # только порядковое. У арабского номера («в гл. 5») согласуются оба слова.
    pytest.param(
        "Об этом сказано в гл. XLII, где описаны обычаи северных народов.",
        "Об этом сказано в главе сорок второй, где описаны обычаи северных народов.",
        id="roman_chapter_number_leaves_the_noun_in_the_nominative",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the roman heading pass inflects the ordinal but not the "
            "heading noun it expands from «гл.»",
        ),
    ),
    # «Гл.» перед родительным целого читается существительным «глава», но
    # литеральная подстановка даёт только именительный и только строчную
    # букву: падеж от предлога и позиция в начале предложения теряются.
    pytest.param(
        "Это сказано в гл. книги о завоевании Сибири.",
        "Это сказано в главе книги о завоевании Сибири.",
        id="chapter_noun_before_a_genitive_whole_stays_in_the_nominative",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the literal «гл.» rule substitutes one form and ignores the "
            "governing preposition",
        ),
    ),
    pytest.param(
        "Гл. книги посвящена завоеванию Сибири.",
        "Глава книги посвящена завоеванию Сибири.",
        id="chapter_noun_at_sentence_start_loses_its_capital",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the literal «гл.» rule substitutes a lowercase form "
            "regardless of the sentence boundary",
        ),
    ),
    # --- Дефекты, меняющие смысл: число теряет цифру или значение -------------
    #
    # Имя собственное с номером перед знаком конца клаузы всё ещё теряет цифру:
    # «Обдориею2.» и «Ковид19,» устроены одинаково, а положение числа —
    # единственный признак, отличающий имя с номером от маркера сноски. Здесь
    # он говорит против имени, и цифра снимается. НЕ РЕШАЕТСЯ без сведений об
    # исходной вёрстке: надёжный признак сноски — надстрочная цифра, а её
    # распознавание книги уже потеряло.
    pytest.param(
        "Ковид19, изменивший привычки миллионов, постепенно отступил.",
        "Ковид девятнадцать, изменивший привычки миллионов, постепенно отступил.",
        id="glued_digits_before_a_clause_edge_dropped_as_footnote",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a number glued to a capitalized name at a clause edge is "
            "indistinguishable from a footnote marker once superscripts are lost",
        ),
    ),
    # Голый домен ловится по реестру TLD без учёта регистра: «Sorry.It» —
    # склейка двух предложений, а не адрес. Настоящий домен пишут строчными.
    pytest.param(
        "В письме он написал: «Sorry.It was my fault».",
        'В письме он написал: "сари. Ит ваз май фолт".',
        id="glued_latin_sentence_boundary_read_as_domain",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a glued English sentence boundary is read as a bare domain; "
            "case does not separate it from Mail.Ru, see docs/ISSUES.md",
        ),
    ),
    # --- Падеж и род числительных --------------------------------------------
    #
    # Число в начале предложения теряет заглавную букву: развёртывание идёт
    # после разбора границ, и первое слово результата остаётся строчным.
    pytest.param(
        "3 участника пришли на встречу и остались до вечера.",
        "Три участника пришли на встречу и остались до вечера.",
        id="sentence_initial_number_loses_its_capital",
        marks=pytest.mark.xfail(
            strict=True,
            reason="an expanded numeral at sentence start is not capitalized",
        ),
    ),
    # Управление глагола протягивается на первый член счётной группы как
    # одушевлённый винительный: «присудили двух и три премии» вместо
    # «присудили три и пять премий».
    pytest.param(
        "Присудили 3 и 5 премий лучшим работникам завода.",
        "Присудили три и пять премий лучшим работникам завода.",
        id="verb_government_leaks_into_a_counted_group",
        marks=pytest.mark.xfail(
            strict=True,
            reason="verb government puts the first member into the animate accusative",
        ),
    ),
    # Тире вместо повторённого глагола: вершина ряда справа стоит в дательном,
    # но «свежее количество после тире» объявляет ряд именительным.
    pytest.param(
        "Премии присудили 3 и 5 участникам, а грамоты — 2 и 4 школам.",
        "Премии присудили трём и пяти участникам, а грамоты — двум и четырём школам.",
        id="series_after_a_verb_ellipsis_dash_ignores_its_head",
        marks=pytest.mark.xfail(
            strict=True,
            reason="fresh-quantity-after-dash shadows the coordinated series head",
        ),
    ),
    # --- Единицы измерения ------------------------------------------------------
    #
    # Распределительное «по» с ценой требует винительного («продавали по
    # девяносто девять рублей»), а получает дательный. Отношение единиц при
    # этом читается верно, см. MONEY_RATIO_CASES в test_known_gap_fixes.py.
    pytest.param(
        "Яблоки продавали по 99,90 ₽/кг.",
        "Яблоки продавали по девяносто девять рублей девяносто копеек за килограмм.",
        id="distributive_po_with_a_price_takes_the_dative",
        marks=pytest.mark.xfail(
            strict=True,
            reason="distributive «по» before a price is read as an ordinary dative",
        ),
    ),
)


#: Пробелы, найденные сплошной проверкой современного корпуса
#: `tests/data/modern_normalization.json` (фаза 7 плана нормализации).
MODERN_CORPUS_GAP_CASES = (
    # --- Даты -------------------------------------------------------------------
    #
    # В диапазоне «с 15 на 22 сентября» название месяца относится к обеим
    # датам, но первое число разбирается без месяца и читается количественным.
    pytest.param(
        "Заседание перенесли с 15 на 22 сентября по просьбе защиты.",
        "Заседание перенесли с пятнадцатого на двадцать второе сентября по просьбе "
        "защиты.",
        id="day_range_before_a_month_reads_the_first_day_as_a_cardinal",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the first day of a day-to-day range does not inherit the month",
        ),
    ),
    # --- Управление числом ------------------------------------------------------
    #
    # «Принять участие» — устойчивое сочетание с уже занятым винительным
    # («участие»), поэтому подлежащее при нём остаётся в именительном, а
    # числительное получает винительный от глагола.
    pytest.param(
        "В голосовании приняли участие 1 458 депутатов из 1 500.",
        "В голосовании приняли участие одна тысяча четыреста пятьдесят восемь "
        "депутатов из одной тысячи пятисот.",
        id="subject_after_prinyat_uchastie_takes_the_accusative",
        marks=pytest.mark.xfail(
            strict=True,
            reason="«принять участие» already fills its accusative slot",
        ),
    ),
    # Предлог «на» при показателе работы требует предложного («работает на ста
    # мегагерцах»), а число с единицей читается в именительном.
    pytest.param(
        "Частота процессора 3,6 ГГц, а шина работает на 100 МГц.",
        "Частота процессора три целых шесть десятых гигагерца, а шина работает на "
        "ста мегагерцах.",
        id="na_before_a_rate_unit_keeps_the_nominative",
        marks=pytest.mark.xfail(
            strict=True,
            reason="«на» before a measured rate is read as an accusative direction",
        ),
    ),
    # Однородное «и 2 цифры» продолжает группу «не менее 12 символов»:
    # числительное получает родительный, а существительное остаётся в
    # исходной форме, и согласование рвётся.
    pytest.param(
        "Пароль должен содержать не менее 12 символов и 2 цифры.",
        "Пароль должен содержать не менее двенадцати символов и двух цифр.",
        id="coordinated_quantity_after_ne_menee_breaks_noun_agreement",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the coordinated noun keeps its surface form while the numeral inflects",
        ),
    ),
    # --- Единицы измерения ------------------------------------------------------
    #
    # «20 с» перед союзом не раскрывается: символ секунды совпадает с
    # предлогом «с», и признак единицы теряется.
    pytest.param(
        "Сборка заняла 4 мин 20 с и потребовала 8 ГБ памяти.",
        "Сборка заняла четыре минуты двадцать секунд и потребовала восемь "
        "гигабайтов памяти.",
        id="second_symbol_before_a_conjunction_stays_unexpanded",
        marks=pytest.mark.xfail(
            strict=True,
            reason="bare «с» before a conjunction is not resolved as the second symbol",
        ),
    ),
    # --- Ссылочные существительные ----------------------------------------------
    #
    # Номер страницы — метка в именительном (см. conventions.md), но после
    # «на» он читается порядковым и согласуется с существительным.
    pytest.param(
        "См. табл. 4 и рис. 7 на стр. 218.",
        "Смотри таблицу четыре и рисунок семь на странице двести восемнадцать.",
        id="page_number_after_na_reads_as_an_ordinal",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a label number after «на стр.» is inflected as an ordinal",
        ),
    ),
    # «На рис. 7» требует предложного: «на рисунке семь». Ссылочное
    # существительное получает от «на» винительный.
    pytest.param(
        "Схема показана на рис. 7.",
        "Схема показана на рисунке семь.",
        id="reference_noun_after_na_takes_the_accusative",
        marks=pytest.mark.xfail(
            strict=True,
            reason="«на» before a reference noun is read as an accusative direction",
        ),
    ),
    # Второе однородное ссылочное существительное теряет управление глагола и
    # остаётся в именительном.
    pytest.param(
        "Сравните рис. 7 и табл. 4 в конце главы.",
        "Сравните рисунок семь и таблицу четыре в конце главы.",
        id="coordinated_reference_noun_loses_the_governing_case",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the second reference noun of a pair falls back to the nominative",
        ),
    ),
    # Иерархический номер после полнословной метки читается десятичной дробью,
    # хотя после сокращения («п. 4.2») он верно читается по компонентам.
    pytest.param(
        "В разделе 3.2 приведены 2 примера расчёта.",
        "В разделе три точка два приведены два примера расчёта.",
        id="hierarchical_number_after_a_full_word_label_reads_as_a_decimal",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a full-word label does not mark the following number as hierarchical",
        ),
    ),
    # --- Сокращения -------------------------------------------------------------
    #
    # «Т.» перед номером тома не раскрывается: сокращение неоднозначно
    # («том», «тонна», «товарищ»), но номер рядом задаёт рубрику.
    pytest.param(
        "Материалы дела на 128 листах хранятся в т. 2.",
        "Материалы дела на ста двадцати восьми листах хранятся в томе два.",
        id="volume_abbreviation_before_a_number_stays_unexpanded",
        marks=pytest.mark.xfail(
            strict=True,
            reason="«т.» before a rubric number is not resolved as «том»",
        ),
    ),
    # «Каб.» отсутствует в реестре ссылочных сокращений и уходит в озвучку как есть.
    pytest.param(
        "Приём заявлений идёт в каб. 305 с 9:00 до 18:00.",
        "Приём заявлений идёт в кабинете триста пять с девяти часов ноля минут до "
        "восемнадцати часов ноля минут.",
        id="room_abbreviation_before_a_number_stays_unexpanded",
        marks=pytest.mark.xfail(
            strict=True,
            reason="«каб.» is missing from the reference-noun registry",
        ),
    ),
    # «Наб.» не раскрывается, а следующее слово получает заглавную от точки
    # сокращения, как будто началось новое предложение.
    pytest.param(
        "Адрес: наб. реки Фонтанки, д. 7, кв. 41.",
        "Адрес: набережная реки Фонтанки, дом семь, квартира сорок один.",
        id="embankment_abbreviation_capitalizes_the_next_word",
        marks=pytest.mark.xfail(
            strict=True,
            reason="«наб.» is unexpanded and its dot is treated as a sentence end",
        ),
    ),
    # Раскрытие сокращения в начале предложения теряет заглавную: «См.»
    # читается как «смотри».
    pytest.param(
        "См. приложение к договору перед подписанием.",
        "Смотри приложение к договору перед подписанием.",
        id="word_abbreviation_at_sentence_start_loses_its_capital",
        marks=pytest.mark.xfail(
            strict=True,
            reason="expanded word abbreviations do not restore the sentence-initial capital",
        ),
    ),
)


#: Полный список: разбит по происхождению, потому что пробелы одной книги
#: правятся и снимаются пачкой, а плоская таблица на сотню записей
#: не даёт увидеть, что именно принесло каждое сплошное чтение.
E2E_KNOWN_GAP_CASES = (
    *HANDWRITTEN_GAP_CASES,
    *DOT_ABBREVIATION_CAPS_GAP_CASES,
    *DOTTED_ROMAN_GAP_CASES,
    *CORPUS_SWEEP_GAP_CASES,
    *BOOK_06_GAP_CASES,
    *BOOK_05_GAP_CASES,
    *BOOK_02_GAP_CASES,
    *BOOK_02B_GAP_CASES,
    *BOOK_04_GAP_CASES,
    *BOOK_03_GAP_CASES,
    *BOOK_01_GAP_CASES,
    *REVIEW_2026_09_GAP_CASES,
    *MODERN_CORPUS_GAP_CASES,
)


@pytest.mark.parametrize(("source", "expected"), E2E_KNOWN_GAP_CASES)
def test_tts_e2e_normalization_known_gaps(
    check_tts: CheckTts, source: str, expected: str
) -> None:
    check_tts(source, expected)
