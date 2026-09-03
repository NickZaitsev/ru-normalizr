"""Исполняемый список согласованных пробелов, которые пока не исправлены.

Каждый оставшийся здесь пробел снабжён комментарием, почему он не закрыт:
запись неоднозначна в самом исходнике, ожидание противоречит принятой
конвенции чтения или требует подсистемы за границами нормализации прозы.
Пробелы, которые удалось закрыть, переехали в `test_known_gap_fixes.py`
обычными проверками с закреплёнными краевыми случаями.
"""

import pytest

from .conftest import CheckTts, Tts

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
    # Суффикс «-м» в стадии годов входит в PLURAL_SUFFIXES (как в «к 1990-м
    # годам»), и творительный падеж после «с» делает год множественным, а
    # множественное округляется до десятилетия: 2023 → 2020. В творительном
    # единственного числа «с 2023-м годом» год должен остаться целым.
    pytest.param(
        "По сравнению с 2023-м годом выручка выросла вдвое.",
        "По сравнению с две тысячи двадцать третьим годом выручка выросла вдвое.",
        id="year_instrumental_suffix_rounded_to_decade",
        marks=pytest.mark.xfail(
            strict=True,
            reason="-м suffix after «с» is treated as plural and the year is rounded to a decade",
        ),
    ),
    pytest.param(
        "Урожай этого года он сравнивал с 1913-м годом.",
        "Урожай этого года он сравнивал с тысяча девятьсот тринадцатым годом.",
        id="year_instrumental_suffix_rounded_to_decade_1913",
        marks=pytest.mark.xfail(
            strict=True,
            reason="-м suffix after «с» is treated as plural and the year is rounded to a decade",
        ),
    ),
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
    # Шаблон маркера эры «н. э.» без правой границы и с IGNORECASE съедает
    # любое слово на «нэ…». Дефект живёт в двух местах: ERA_ABBREVIATION_PATTERN
    # в preprocess_utils и ERA_REGEX в years.
    pytest.param(
        "Нэнси пришла домой поздно вечером.",
        "Нэнси пришла домой поздно вечером.",
        id="era_marker_without_right_boundary_eats_name",
        marks=pytest.mark.xfail(
            strict=True,
            reason="era marker regex has no right boundary and matches the start of a word",
        ),
    ),
    pytest.param(
        "Времена нэпа давно прошли, а привычки остались.",
        "Времена нэпа давно прошли, а привычки остались.",
        id="era_marker_without_right_boundary_eats_lowercase_word",
        marks=pytest.mark.xfail(
            strict=True,
            reason="era marker regex has no right boundary and matches the start of a word",
        ),
    ),
    pytest.param(
        "В 1990 году Нэнси уехала в Париж.",
        "В тысяча девятьсот девяностом году Нэнси уехала в Париж.",
        id="era_marker_after_year_eats_following_word",
        marks=pytest.mark.xfail(
            strict=True,
            reason="years-stage era regex has no right boundary and eats the word after a year",
        ),
    ),
    # «и т. д.» ищется с IGNORECASE, поэтому инициалы «Т. Д.» перед фамилией
    # раскрываются в «так далее». Заглавные буквы и фамилия справа — инициалы.
    pytest.param(
        "На сессии выступил Т. Д. Лысенко с докладом.",
        "На сессии выступил тэ дэ Лысенко с докладом.",
        id="initials_read_as_etc_abbreviation",
        marks=pytest.mark.xfail(
            strict=True,
            reason="«Т. Д.» initials are matched by the case-insensitive «и т. д.» pattern",
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
    # protect_negative_numbers идёт раньше, чем « - » превращается в тире (это
    # делает только finalize), поэтому дефис-тире перед числом в прозе читается
    # минусом.
    pytest.param(
        "Он сказал - 5 человек ушли раньше срока.",
        "Он сказал — пять человек ушли раньше срока.",
        id="spaced_hyphen_before_number_read_as_minus",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a spaced hyphen used as a dash is protected as a unary minus",
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
    # --- Ложные срабатывания контекста -----------------------------------------
    #
    # Голое «в» без точки после латинского слова или римского числа принимается
    # за сокращение «век»: «mix в» → «тысяча девятого века», «II в переводе» →
    # «второго века переводе». Для «в»/«вв» нужна точка, как у «стол».
    pytest.param(
        "Слово mix в русском языке означает смесь.",
        "Слово микс в русском языке означает смесь.",
        id="bare_v_after_latin_word_read_as_century",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a bare «в» after a roman-looking Latin word is read as «век»",
        ),
    ),
    pytest.param(
        "Часть II в переводе Пастернака вышла позже.",
        "Часть вторая в переводе Пастернака вышла позже.",
        id="bare_v_after_roman_numeral_read_as_century",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a bare «в» after a roman numeral is read as «век»",
        ),
    ),
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
    # Неявный год после предлога: «на 1000 больше» и «за 1500 лет» читаются
    # порядковыми, хотя справа компаратив или счётное слово «лет».
    pytest.param(
        "Сегодня пришло на 1000 больше, чем вчера.",
        "Сегодня пришло на тысячу больше, чем вчера.",
        id="implicit_year_before_comparative",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a round number after «на» before a comparative is read as an implicit year",
        ),
    ),
    pytest.param(
        "За 1500 лет многое изменилось.",
        "За тысячу пятьсот лет многое изменилось.",
        id="implicit_year_before_let",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a number after «за» before «лет» is read as an implicit year",
        ),
    ),
    # TEXT_DATE_PATTERN знает только предлоги «перед» и «на»; «к 5 мая» получает
    # родительный вместо дательного.
    pytest.param(
        "Отчёт нужно сдать к 5 мая.",
        "Отчёт нужно сдать к пятому мая.",
        id="date_after_k_preposition_gets_genitive",
        marks=pytest.mark.xfail(
            strict=True,
            reason="text dates know only «перед» and «на» as case-governing prepositions",
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
    # --- Падеж и род числительных ---------------------------------------------
    #
    # «Годовой» override в _unit_case_at_site (1000 ≤ n ≤ 2100 после «в» → accs)
    # срабатывает на единицах длины и перебивает правило distance-from-landmark.
    pytest.param(
        "Лагерь стоял в 1500 м от реки.",
        "Лагерь стоял в тысяче пятистах метрах от реки.",
        id="distance_from_landmark_lost_to_year_override",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the year-range accusative override wins over distance-from-landmark",
        ),
    ),
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
    # Диапазон глав: «со» ставится перед любым в/ф/с/з/ш/ж, а род при
    # неоднозначной вершине падает в мужской.
    pytest.param(
        "Прочитайте главы 8-9 к понедельнику.",
        "Прочитайте главы с восьмой по девятую к понедельнику.",
        id="chapter_range_preposition_and_gender",
        marks=pytest.mark.xfail(
            strict=True,
            reason="range rendering uses «со» before any в/ф/с/з and defaults to masculine",
        ),
    ),
    # Знаменатель 3 даёт «трети» при любом числителе, кроме единицы.
    pytest.param(
        "Добавьте 5/3 стакана муки.",
        "Добавьте пять третьих стакана муки.",
        id="fraction_third_denominator_plural_form",
        marks=pytest.mark.xfail(
            strict=True,
            reason="denominator 3 renders as «трети» for any numerator other than one",
        ),
    ),
    # Замена «девяноста» → «девяносто» в составном прилагательном делается
    # только для 91–99.
    pytest.param(
        "На 90-летний юбилей собрались все родственники.",
        "На девяностолетний юбилей собрались все родственники.",
        id="compound_adjective_ninety_prefix",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the ninety prefix of a compound adjective keeps the genitive form",
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
    # Счёт матча: «3:2» склоняется по «со счётом» в родительный, а «4:1» вовсе
    # не читается. Оба — именительный с паузой-тире, как уже делает «2:0».
    pytest.param(
        "Матч закончился со счётом 3:2 в пользу гостей.",
        "Матч закончился со счётом три — два в пользу гостей.",
        id="score_read_in_genitive",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a match score after «со счётом» inherits the genitive",
        ),
    ),
    pytest.param(
        "Серия закончилась 4:1 в пользу хозяев.",
        "Серия закончилась четыре — один в пользу хозяев.",
        id="score_colon_not_read",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a match score without a score word keeps the colon",
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
    # Знак параграфа без точки после номера не читается.
    pytest.param(
        "§ 3 настоящих правил обязателен для всех.",
        "Параграф три настоящих правил обязателен для всех.",
        id="section_sign_without_dotted_number_not_read",
        marks=pytest.mark.xfail(
            strict=True,
            reason="«§ N» without a dotted number keeps the section sign",
        ),
    ),
    # --- Регистр, аббревиатуры и латиница ----------------------------------------
    #
    # _restore_known_abbreviations возвращает верхний регистр однобуквенным
    # токенам капс-строки: предлоги «У» и «В» остаются заглавными.
    pytest.param(
        "СТОЛ СТОЯЛ У ОКНА В КОМНАТЕ\nОн вошёл и сел.",
        "Стол стоял у окна в комнате.\nОн вошёл и сел.",
        id="caps_line_keeps_single_letter_prepositions_upper",
        marks=pytest.mark.xfail(
            strict=True,
            reason="single-letter words in a CAPS line are restored to upper case as abbreviations",
        ),
    ),
    # normalize_first_word_caps опускает любой акроним длиннее трёх букв, если
    # его нет в KNOWN_ABBREVIATIONS.
    pytest.param(
        "МГИМО объявил дополнительный набор.",
        "МГИМО объявил дополнительный набор.",
        id="unknown_acronym_decapitalized_at_sentence_start",
        marks=pytest.mark.xfail(
            strict=True,
            reason="an acronym outside KNOWN_ABBREVIATIONS is decapitalized as a CAPS word",
        ),
    ),
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
    # _resolve_explicit_year_word_case знает дательный только для «к/ко».
    pytest.param(
        "По 2020 году данных пока нет.",
        "По две тысячи двадцатому году данных пока нет.",
        id="year_after_po_preposition_gets_locative",
        marks=pytest.mark.xfail(
            strict=True,
            reason="«по» before a year is not mapped to the dative",
        ),
    ),
    # Кириллическое «ХХ» перед «веке» отбрасывается как двойник, хотя контекст
    # однозначно требует римского числа.
    pytest.param(
        "В ХХ веке наука изменила мир.",
        "В двадцатом веке наука изменила мир.",
        id="cyrillic_roman_lookalike_before_century",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a Cyrillic look-alike roman numeral is spelled out even before «веке»",
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
    # «около 3.50 долларов» читается временем: DOTTED_TIME_LEFT_CONTEXT содержит
    # «около» и не проверяет правый контекст. Через запятую та же сумма читается
    # верно.
    pytest.param(
        "Билет стоил около 3.50 долларов.",
        "Билет стоил около трёх долларов пятидесяти центов.",
        id="dotted_price_after_okolo_read_as_time",
        marks=pytest.mark.xfail(
            strict=True,
            reason="«около N.NN» is read as a dotted time even before a currency word",
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


#: Длина сочинённого ряда чисел, на которой падеж первого члена уже не
#: вычисляется: `_rule_coordinated_first_number` рекурсивно спрашивает падеж у
#: предыдущего члена без памятки, глубина рекурсии растёт с длиной ряда, а
#: время — квадратично. На 300 членах прогон ещё живёт, на 500 — падает.
LONG_COORDINATED_LIST_LENGTH = 500


@pytest.mark.xfail(
    strict=True,
    raises=RecursionError,
    reason="coordinated-number case resolution recurses once per list member",
)
def test_long_coordinated_number_list_does_not_overflow(tts: Tts) -> None:
    numbers = ", ".join(str(i) for i in range(1, LONG_COORDINATED_LIST_LENGTH + 1))
    result = tts(f"В приложении перечислены статьи {numbers} кодекса.")
    assert not any(char.isdecimal() for char in result)
