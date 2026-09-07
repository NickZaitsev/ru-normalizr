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
CORPUS_SWEEP_GAP_CASES = ()


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


#: Найдено при вводе реестра доменов верхнего уровня (план
#: 2026-08-22-fix-real-book-regressions): запись перестала читаться адресом и
#: обнажила пробел в разборе латинских точечных сокращений.
DOTTED_ROMAN_GAP_CASES = (
    # Латинская дата римскими цифрами через точки не опознаётся как число:
    # «M.DC.LXXX» — это 1680. Раньше запись случайно читалась доменом («эм
    # точка ди си точка восемьдесят»), теперь точки остаются как в исходнике, и
    # стадия заглавных поднимает регистр после каждой. Правильное чтение
    # требует разбора римского числа с точечными разделителями.
    pytest.param(
        "Рукопись подписана: анно M.DC.LXXX, и переписчик её не назвал.",
        "Рукопись подписана: анно тысяча шестьсот восемьдесят, и переписчик её не назвал.",
        id="dotted_latin_roman_year",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a dot-separated roman numeral is not recognized as a number",
        ),
    ),
)


#: Найдено сплошным чтением книги 01 («История России с древнейших времён»).
BOOK_01_GAP_CASES = (
)


#: Найдено ревью 1.1.0 (3 сентября 2026) на современной прозе: договоры,
#: новости, техника, кулинария. Книжный корпус XIX века таких конструкций не
#: содержит, поэтому ни один из этих пробелов тестами не ловился. Подробный
#: разбор причин и предлагаемых правок — docs/ISSUES.md.
REVIEW_2026_09_GAP_CASES = (
    # --- Дефекты, меняющие смысл: число теряет цифру или значение -------------
    #
    # Эвристика сноски в fix_glued_numbers считает цифру, приклеенную к слову,
    # номером примечания и удаляет её: «Формула1» и «Ковид19» теряют число.
    # Имя собственное с заглавной буквы сноской быть не должно.
    pytest.param(
        "Формула1 стартовала в Сочи в октябре.",
        "Формула один стартовала в Сочи в октябре.",
        id="glued_digit_after_proper_name_dropped_as_footnote",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a digit glued to a capitalized word is dropped as a footnote marker",
        ),
    ),
    pytest.param(
        "Ковид19 изменил привычки миллионов людей.",
        "Ковид девятнадцать изменил привычки миллионов людей.",
        id="glued_digits_after_proper_name_dropped_as_footnote",
        marks=pytest.mark.xfail(
            strict=True,
            reason="digits glued to a capitalized word are dropped as a footnote marker",
        ),
    ),
    # LINE_NUMBERING_PATTERN принимает год в начале строки за номер пункта и
    # читает его количественным. Четырёхзначное число в диапазоне лет с точкой
    # и предложением справа — хронологическая запись, год-порядковое.
    pytest.param(
        "1941. Началась война, и город опустел.",
        "Тысяча девятьсот сорок первый. Началась война, и город опустел.",
        id="year_at_line_start_read_as_list_number",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a year at line start is read as a cardinal list number",
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
    # Идентификаторы читаются как числа: ИНН — как «семь миллиардов…», код
    # ГОСТа — как десятичная дробь, номер ISO — с двоеточием внутри. Слово-
    # метка слева (ИНН, ОГРН, ГОСТ, ISO) должно переключать чтение на цифры
    # или группы; способ группировки — конвенция, которую фиксирует правка.
    pytest.param(
        "ИНН 7701234567 указан в договоре.",
        "ИНН семь семь ноль один два три четыре пять шесть семь указан в договоре.",
        id="tax_id_read_as_cardinal",
        marks=pytest.mark.xfail(
            strict=True,
            reason="an identifier after ИНН is read as a ten-digit cardinal",
        ),
    ),
    pytest.param(
        "ГОСТ 2.105-95 устанавливает общие требования к текстовым документам.",
        "гост два точка сто пять девяносто пять устанавливает общие требования к текстовым документам.",
        id="standard_code_read_as_decimal",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a dotted standard code after ГОСТ is read as a decimal fraction",
        ),
    ),
    pytest.param(
        "Компания сертифицирована по ISO 9001:2015.",
        "Компания сертифицирована по ай эс о девять тысяч один, две тысячи пятнадцать.",
        id="standard_code_with_colon_not_split",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the colon inside an ISO code survives into the output",
        ),
    ),
    # Буква внутри буквенно-цифрового кода резолвится как единица измерения:
    # «H» в «24H2» читается «генри».
    pytest.param(
        "Обновление Windows 11 24H2 вышло осенью.",
        "Обновление виндоуз одиннадцать двадцать четыре эйч два вышло осенью.",
        id="alphanumeric_code_letter_read_as_unit",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a letter inside an alphanumeric code is resolved as an SI unit",
        ),
    ),
    # Ветка thousand_suffix срабатывает только после знака препинания; после
    # слова «100k» уходит в правило «код вида А 1Б» и читается «сто-кей».
    pytest.param(
        "Заработал 100k за месяц и уволился.",
        "Заработал сто тысяч за месяц и уволился.",
        id="thousands_suffix_after_word_read_as_code",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the k thousands suffix is recognized only after punctuation",
        ),
    ),
    # --- Ложные срабатывания контекста ---------------------------------------
    #
    # Граммы принимаются за годы: allows_short_abbreviated_year разрешает «г»
    # после любого предлога, а проверка на вещество в родительном справа есть
    # только для «под».
    pytest.param(
        "Добавьте в 250 г муки щепотку соли.",
        "Добавьте в двести пятьдесят граммов муки щепотку соли.",
        id="grams_after_preposition_read_as_year",
        marks=pytest.mark.xfail(
            strict=True,
            reason="«г» after a preposition is read as a year abbreviation before a mass noun",
        ),
    ),
    # NUMERIC_DATE_PATTERN принимает год из двух цифр без «г.» и не смотрит на
    # «п.» слева: номер пункта договора читается датой. «п.» при этом не
    # раскрывается.
    pytest.param(
        "Согласно п. 1.2.34 договора аванс не возвращается.",
        "Согласно пункту один точка два точка тридцать четыре договора аванс не возвращается.",
        id="dotted_clause_number_read_as_date",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a dotted clause number after «п.» is read as a numeric date",
        ),
    ),
    # Литеральные правила сокращений раскрывают только в именительном и без
    # оглядки на соседа: «Гл. редактор» — «главный», «в табл.» — «в таблице»,
    # «ст. 5» после «согласно» — «статье», «в обл.» — «в области».
    pytest.param(
        "Гл. редактор ушёл в отставку.",
        "Главный редактор ушёл в отставку.",
        id="gl_abbreviation_before_noun_read_as_chapter",
        marks=pytest.mark.xfail(
            strict=True,
            reason="«гл.» is always expanded to «глава» regardless of the word after it",
        ),
    ),
    pytest.param(
        "Данные приведены в табл. 3 и в прил. 2.",
        "Данные приведены в таблице три и в приложении два.",
        id="literal_abbreviation_expansion_ignores_case",
        marks=pytest.mark.xfail(
            strict=True,
            reason="literal abbreviation rules expand to the nominative only",
        ),
    ),
    pytest.param(
        "Согласно ст. 5 п. 2 закона штраф удвоен.",
        "Согласно статье пять пункту два закона штраф удвоен.",
        id="article_abbreviation_ignores_case_and_point_stays",
        marks=pytest.mark.xfail(
            strict=True,
            reason="«ст.» expands to the nominative and «п.» is not expanded at all",
        ),
    ),
    pytest.param(
        "Он жил в Московской обл. до войны.",
        "Он жил в Московской области до войны.",
        id="oblast_abbreviation_ignores_case",
        marks=pytest.mark.xfail(
            strict=True,
            reason="«обл.» expands to the nominative after a locative adjective",
        ),
    ),
    # --- Падеж и род числительных --------------------------------------------
    #
    # distance-from-landmark не видит диапазон: единица и «от» стоят после
    # правой границы, а правило смотрит только на соседей левой.
    pytest.param(
        "Деревня лежит в 10-20 км от города.",
        "Деревня лежит в десяти — двадцати километрах от города.",
        id="distance_range_from_landmark_not_inflected",
        marks=pytest.mark.xfail(
            strict=True,
            reason="distance-from-landmark does not look past a range to the unit",
        ),
    ),
    # Падеж каждого члена сочинённого ряда должен идти от существительного
    # справа: «3, 5 и 7 участникам» — дательный.
    pytest.param(
        "Премии присудили 3, 5 и 7 участникам.",
        "Премии присудили трём, пяти и семи участникам.",
        id="coordinated_numbers_ignore_head_case",
        marks=pytest.mark.xfail(
            strict=True,
            reason="coordinated numbers before a dative head stay nominative",
        ),
    ),
    # --- Единицы измерения ------------------------------------------------------
    #
    # Отношения единиц с точкой сокращения («руб./долл.», «уд./мин») и знак
    # валюты перед «/кг» не разбираются: остаётся мусор «рублей./долларов»,
    # а число слева получает чужой падеж.
    pytest.param(
        "Курс составил 70 руб./долл.",
        "Курс составил семьдесят рублей за доллар.",
        id="dotted_unit_ratio_keeps_dot_and_slash",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a unit ratio with abbreviation dots is not parsed",
        ),
    ),
    pytest.param(
        "Пульс 72 уд./мин считается нормой.",
        "Пульс семьдесят два удара в минуту считается нормой.",
        id="dotted_unit_ratio_leaves_number_in_genitive",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a unit ratio with an abbreviation dot is not parsed and the number gets the genitive",
        ),
    ),
    pytest.param(
        "Яблоки продавали по 99,90 ₽/кг.",
        "Яблоки продавали по девяносто девять рублей девяносто копеек за килограмм.",
        id="currency_symbol_per_unit_not_parsed",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a currency symbol followed by /unit is left as is and the amount is read as a decimal",
        ),
    ),
    # После «тыс.» единица «км» не раскрывается.
    pytest.param(
        "Расстояние до цели — 3—4 тыс. км.",
        "Расстояние до цели — три — четыре тысячи километров.",
        id="unit_after_thousands_abbreviation_not_expanded",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the unit after «тыс.» is not expanded",
        ),
    ),
    # Диапазон после «лет» и диапазон десятичных читаются через запятую, тогда
    # как остальные диапазоны — через тире.
    pytest.param(
        "Ему было лет 25–30, не больше.",
        "Ему было лет двадцать пять — тридцать, не больше.",
        id="range_after_let_read_as_comma",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a range after «лет» is rendered with a comma instead of a dash",
        ),
    ),
    pytest.param(
        "Мощность станции 1,2—1,5 ГВт.",
        "Мощность станции одна целая две десятых — одна целая пять десятых гигаватта.",
        id="decimal_range_read_as_comma",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a decimal range is rendered with a comma instead of a dash",
        ),
    ),
    # --- Регистр, аббревиатуры и латиница ------------------------------------
    #
    # Одиночная латинская буква идёт через IPA как безударный артикль «э», а не
    # по имени буквы «эй».
    pytest.param(
        "Вариант A лучше варианта B.",
        "Вариант эй лучше варианта би.",
        id="single_latin_letter_read_as_article",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a standalone Latin letter goes through IPA as the article «a»",
        ),
    ),
    # «руб.» раскрывается в родительный множественного без числа слева.
    pytest.param(
        "Цена в руб. указана без НДС.",
        "Цена в рублях указана без эн дэ эс.",
        id="rub_abbreviation_without_number",
        marks=pytest.mark.xfail(
            strict=True,
            reason="«руб.» without a number is expanded as if counted",
        ),
    ),
    # «г.» перед названием с заглавной буквы — город, а не год.
    pytest.param(
        "Он переехал в г. Казань в 2010 году.",
        "Он переехал в город Казань в две тысячи десятом году.",
        id="city_abbreviation_before_name_not_expanded",
        marks=pytest.mark.xfail(
            strict=True,
            reason="«г.» before a capitalized place name is not expanded to «город»",
        ),
    ),
    # «Св.» перед именем в родительном не раскрывается.
    pytest.param(
        "Церковь Св. Анны стоит на холме.",
        "Церковь Святой Анны стоит на холме.",
        id="saint_abbreviation_before_genitive_name",
        marks=pytest.mark.xfail(
            strict=True,
            reason="«Св.» before a name in the genitive is left as is",
        ),
    ),
    # --- Найдено пробами corner cases при закрытии дефектов «-м» (3 сентября) --
    #
    # Дата «8-м марта» получает творительный вместо винительного: предлог «на»
    # с датой требует «на восьмое марта».
    pytest.param(
        "На 8-м марта подарили цветы.",
        "На восьмое марта подарили цветы.",
        id="dated_ordinal_after_na_gets_instrumental",
        marks=pytest.mark.xfail(
            strict=True,
            reason="«на 8-м марта» keeps the instrumental instead of the accusative date",
        ),
    ),
    # --- Найдено пробами при закрытии правок ревью (4 сентября) --------------
    #
    # Голое «в» после римского числа перестало читаться веком только там, где
    # слева стоит неодушевлённая вершина заголовка. «Глава» разбирается и как
    # одушевлённое («глава города»), проверка на неодушевлённость не проходит,
    # и предлог снова съедается: «Глава четвёртый век этом издании».
    pytest.param(
        "Глава IV в этом издании отсутствует.",
        "Глава четвёртая в этом издании отсутствует.",
        id="bare_v_after_animate_ambiguous_heading_head_read_as_century",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the heading head «глава» also parses as animate, so the "
            "inanimate check fails and the bare «в» is eaten as «век»",
        ),
    ),
    # Заглавная аббревиатура в начале предложения сохраняет регистр только если
    # морфология знает её как `Abbr`. «НАСА» и «ЮНЕСКО» словарю неизвестны и
    # опускаются в строчные, хотя «МГИМО» уже читается верно.
    pytest.param(
        "НАСА объявило дополнительный набор.",
        "НАСА объявило дополнительный набор.",
        id="acronym_outside_the_dictionary_decapitalized_at_sentence_start",
        marks=pytest.mark.xfail(
            strict=True,
            reason="an acronym that morphology does not know as Abbr is still "
            "decapitalized as a CAPS word at sentence start",
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
)


@pytest.mark.parametrize(("source", "expected"), E2E_KNOWN_GAP_CASES)
def test_tts_e2e_normalization_known_gaps(
    check_tts: CheckTts, source: str, expected: str
) -> None:
    check_tts(source, expected)
