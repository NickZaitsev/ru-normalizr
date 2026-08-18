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
    # --- Найдено прогоном по книжному корпусу benchmarks/corpus ---
    # Римская цифра перед предлогом «в» съедает сам предлог: правило вековой
    # аббревиатуры «в.» срабатывает и на предлоге без точки.
    pytest.param(
        "Въезд Петра I в Москву состоялся после Полтавской битвы.",
        "Въезд Петра первого в Москву состоялся после Полтавской битвы.",
        id="roman_regnal_number_before_preposition_v",
        marks=pytest.mark.xfail(
            strict=True,
            reason="bare preposition в after a roman numeral is consumed as the century abbreviation",
        ),
    ),
    # Век после «в начале»/«в половине» остаётся именительным, если следом идёт
    # наречие или предлог: падеж берётся от следующего слова, а не от предлога.
    pytest.param(
        "Однако в начале IX в. сквозь хозар прорвались с востока печенеги.",
        "Однако в начале девятого века сквозь хозар прорвались с востока печенеги.",
        id="century_abbreviation_before_adverbial_word",
        marks=pytest.mark.xfail(
            strict=True,
            reason="century abbreviation stays nominative when an adverb follows",
        ),
    ),
    # «г.» после года в летописной датировке читается как граммы: единица
    # выигрывает у годового контекста.
    pytest.param(
        "В летописи под 964 г. записано, что князь вырос и возмужал.",
        "В летописи под девятьсот шестьдесят четвёртым годом записано, что князь вырос и возмужал.",
        id="year_abbreviation_read_as_gram",
        marks=pytest.mark.xfail(
            strict=True,
            reason="г. after a year is resolved to grams instead of the year noun",
        ),
    ),
    # «тыс.» после диапазона не раскрывается: точка остаётся и запускает
    # заглавную букву у следующего слова.
    pytest.param(
        "Наёмных венгров и печенегов было 40—50 тыс. человек в этом походе.",
        "Наёмных венгров и печенегов было сорок — пятьдесят тысяч человек в этом походе.",
        id="thousands_abbreviation_after_a_range",
        marks=pytest.mark.xfail(
            strict=True,
            reason="тыс. after a range keeps its dot and triggers sentence capitalization",
        ),
    ),
    # Диапазон между числами с пробельными разрядами не распознаётся: тире
    # превращается в перечисление через запятую.
    pytest.param(
        "Войско его не превосходило 50 000—60 000, обыкновенно же было гораздо меньше.",
        "Войско его не превосходило пятьдесят тысяч — шестьдесят тысяч, "
        "обыкновенно же было гораздо меньше.",
        id="range_between_space_grouped_thousands",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a range between space-grouped numbers is rendered as a comma enumeration",
        ),
    ),
    # Диапазон лет перед «г.» даёт множественные порядковые, лишнюю точку внутри
    # скобки и заглавную букву у следующего слова.
    pytest.param(
        "Игорь (912—945 г.) предпринимал два похода в Византию.",
        "Игорь (девятьсот двенадцатый — девятьсот сорок пятый годы) "
        "предпринимал два похода в Византию.",
        id="year_range_before_singular_year_abbreviation",
        marks=pytest.mark.xfail(
            strict=True,
            reason="year range before singular г. leaves a stray dot and capitalizes the next word",
        ),
    ),
    # Итоговое число в перечислении получает родительный падеж, хотя стоит в
    # именительной позиции («а всего 30 000»).
    pytest.param(
        "Он имел сзади пятнадцать тысяч пехоты, а всего 30 000, и прошёл клиссуры.",
        "Он имел сзади пятнадцать тысяч пехоты, а всего тридцать тысяч, и прошёл клиссуры.",
        id="total_after_enumeration_gets_genitive",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a total after an enumeration is rendered in the genitive",
        ),
    ),
    # Счётная форма «человек» после тысяч подменяется супплетивным «людей».
    pytest.param(
        "Конные латники числом до 2000 человек шли впереди обоза.",
        "Конные латники числом до двух тысяч человек шли впереди обоза.",
        id="counted_form_chelovek_after_thousands",
        marks=pytest.mark.xfail(
            strict=True,
            reason="counted человек is replaced by the suppletive людей",
        ),
    ),
    # Тире перед односимвольным предлогом склеивается с предыдущим словом в
    # дефисное сочетание («домой-с»).
    pytest.param(
        "Он вернулся домой — с добычей и славой.",
        "Он вернулся домой — с добычей и славой.",
        id="em_dash_before_single_letter_preposition",
        marks=pytest.mark.xfail(
            strict=True,
            reason="an em dash before a single-letter preposition is glued into a hyphen compound",
        ),
    ),
    # Многоточие после восклицательного знака теряет точку.
    pytest.param(
        "Он больше не нашёл себе продолжателей!..",
        "Он больше не нашёл себе продолжателей!..",
        id="ellipsis_after_exclamation_mark",
        marks=pytest.mark.xfail(
            strict=True,
            reason="an ellipsis after ! or ? loses one dot",
        ),
    ),
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
    # Дефис после точки сокращения в составном слове («ген.-майор»,
    # «С.-Петербург») превращается в тире с пробелами.
    pytest.param(
        "В отряде служил ген.-майор Дружинин и два адъютанта.",
        "В отряде служил ген.-майор Дружинин и два адъютанта.",
        id="hyphen_after_abbreviation_dot_becomes_dash",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a hyphen after an abbreviation dot becomes a spaced dash",
        ),
    ),
    # Порядковый номер монарха согласуется с омонимичным женским разбором имени
    # («Карла» → «карла»), поэтому выходит «двенадцатая».
    pytest.param(
        "Движение Карла XII началось от Полоцка к Гродно.",
        "Движение Карла двенадцатого началось от Полоцка к Гродно.",
        id="regnal_number_after_name_homographic_with_feminine_noun",
        marks=pytest.mark.xfail(
            strict=True,
            reason="regnal number agrees with a feminine homograph parse of the name",
        ),
    ),
    # Первая римская цифра в сочинительной паре («конец XVI и начало XVII
    # веков») читается количественным, потому что «веков» стоит только у второй.
    pytest.param(
        "Смутное время охватывает конец XVI и начало XVII веков.",
        "Смутное время охватывает конец шестнадцатого и начало семнадцатого веков.",
        id="roman_century_before_a_conjunction",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the first roman numeral of a coordinated pair is read as a cardinal",
        ),
    ),
    # Левая граница диапазона «с … до …» без своего «века» читается
    # количественным в родительном падеже.
    pytest.param(
        "Собор строили с половины XIV до половины XV века.",
        "Собор строили с половины четырнадцатого до половины пятнадцатого века.",
        id="roman_century_range_with_do",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the left bound of a с … до … century range is read as a cardinal",
        ),
    ),
    # Дата вида «12 числа» требует порядкового, как и «12-го числа».
    pytest.param(
        "Напоследок 12 числа всё было в готовности к походу.",
        "Напоследок двенадцатого числа всё было в готовности к походу.",
        id="ordinal_before_chisla",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a bare day number before числа is read as a cardinal",
        ),
    ),
    # Перечисление страниц после «стр.» ставит первую страницу в родительный
    # падеж («страница пяти»).
    pytest.param(
        "Нестор говорит выше (стр. 5, 6) о разделении языков после столпотворения.",
        "Нестор говорит выше (страница пять, шесть) о разделении языков после столпотворения.",
        id="page_list_after_page_abbreviation",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the first page of a list after стр. is rendered in the genitive",
        ),
    ),
    # Диапазон страниц после «на страницах» получает средний род у первой
    # границы («девяносто одно»).
    pytest.param(
        "Летописец пишет об этом на страницах 91—92 своего сочинения.",
        "Летописец пишет об этом на страницах девяносто один — девяносто два своего сочинения.",
        id="page_range_gender_after_stranicah",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the left bound of a page range takes neuter gender",
        ),
    ),
    # Год при творительном «годом» читается количественным в творительном
    # падеже вместо порядкового.
    pytest.param(
        "Под следующим 859 годом летописец помещает известие о дани.",
        "Под следующим восемьсот пятьдесят девятым годом летописец помещает известие о дани.",
        id="year_before_instrumental_godom",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a year before instrumental годом is read as an instrumental cardinal",
        ),
    ),
    # Дата с числом после месяца («Октября 24») требует порядкового, как и
    # обратный порядок «24 октября».
    pytest.param(
        "Октября 24 на придворном театре представлена была комедия.",
        "Октября двадцать четвёртого на придворном театре представлена была комедия.",
        id="month_first_date",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a day number after the month name is read as a cardinal",
        ),
    ),
    # Смешанная дробь теряет «целую»: «1 1/3» читается как «одну одну треть».
    pytest.param(
        "За окровавление человека посредством дерева платили 1 1/3 гривны серебром.",
        "За окровавление человека посредством дерева платили одну целую одну треть гривны серебром.",
        id="mixed_fraction_with_integer_part",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the integer part of a mixed fraction loses целую",
        ),
    ),
    # Число после двух дат подхватывается годовым контекстом и становится
    # порядковым годом («семитысячного года человек»).
    pytest.param(
        "В городе умерло от 14 ноября до 1 февраля 7000 человек.",
        "В городе умерло от четырнадцатого ноября до первого февраля семь тысяч человек.",
        id="cardinal_after_a_date_read_as_year",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a cardinal following a date pair is absorbed by the year context",
        ),
    ),
    # --- Найдено сплошным чтением книги 06 (Семёнов-Тян-Шанский) ---
    # «гг.» после диапазона лет не раскрывается: точка остаётся и следующее
    # слово получает заглавную букву.
    pytest.param(
        "Путешествие в Тянь-Шань в 1856—1857 гг. осталось единственным его исследованием.",
        "Путешествие в Тянь-Шань в тысяча восемьсот пятьдесят шестом — "
        "тысяча восемьсот пятьдесят седьмом годах осталось единственным его исследованием.",
        id="year_range_before_gg_abbreviation",
        marks=pytest.mark.xfail(
            strict=True,
            reason="гг. after a year range keeps its dot and capitalizes the next word",
        ),
    ),
    # «г.» после года перед словом с заглавной буквы принимается за конец
    # предложения: в тексте с именами это рвёт фразу на каждом датированном месте.
    pytest.param(
        "В 1867 г. Семёнов поместил в записках общества описание своей поездки.",
        "В тысяча восемьсот шестьдесят седьмом году Семёнов поместил "
        "в записках общества описание своей поездки.",
        id="sentence_break_after_year_abbreviation_before_a_name",
        marks=pytest.mark.xfail(
            strict=True,
            reason="г. before a capitalized word is treated as a sentence end",
        ),
    ),
    # Век после «к середине» получает падеж от предлога «к», а не родительный
    # от управляющего существительного.
    pytest.param(
        "Наука подошла к середине XIX в., хорошо изучив побережья материка.",
        "Наука подошла к середине девятнадцатого века, хорошо изучив побережья материка.",
        id="century_takes_case_from_the_preposition",
        marks=pytest.mark.xfail(
            strict=True,
            reason="century after к середине is rendered in the dative instead of the genitive",
        ),
    ),
    # Диапазон веков «IV—VII вв.» читается именительным единственного числа
    # вместо родительного множественного.
    pytest.param(
        "Сведения шли от миссионеров буддизма IV—VII вв. и от чиновников новейших времён.",
        "Сведения шли от миссионеров буддизма четвёртого — седьмого веков "
        "и от чиновников новейших времён.",
        id="century_range_abbreviation",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a century range before вв. stays nominative singular",
        ),
    ),
    # Висячий дефис первой части сложного слова («в оро- и гидрографическом»)
    # превращается в тире, разрывая слово.
    pytest.param(
        "Работа интересна в оро- и гидрографическом отношениях для всей страны.",
        "Работа интересна в оро- и гидрографическом отношениях для всей страны.",
        id="dangling_hyphen_in_coordinated_compound",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a dangling hyphen of a coordinated compound becomes a dash",
        ),
    ),
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
    # Сокращённая запись пары лет «1856/57 гг.» не распознаётся как диапазон.
    pytest.param(
        "Мне пришлось провести зиму 1856/57 гг. в Барнауле за разбором коллекций.",
        "Мне пришлось провести зиму тысяча восемьсот пятьдесят шестого — "
        "пятьдесят седьмого годов в Барнауле за разбором коллекций.",
        id="split_year_notation",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the 1856/57 year notation is not read as a range",
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
    # Минус перед температурой набран тире и остаётся тире, теряя «минус».
    pytest.param(
        "Ночь была холодная, и к утру было —2° Ц в палатке.",
        "Ночь была холодная, и к утру было минус два градуса Цельсия в палатке.",
        id="dash_as_minus_before_temperature",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a dash used as a minus before a temperature stays a dash",
        ),
    ),
    # Инициалы перед фамилией принимаются за сокращение: «В. Д.» читается как
    # «восточной долготы», «Г. Г.» — как «годы».
    pytest.param(
        "Он спорил с князем В. Д. Горчаковым о судьбе отряда.",
        "Он спорил с князем вэ дэ Горчаковым о судьбе отряда.",
        id="initials_read_as_an_abbreviation",
        marks=pytest.mark.xfail(
            strict=True,
            reason="initials before a surname are expanded as a domain abbreviation",
        ),
    ),
    # Разрядка подчёркиваниями («в_н_е в_с_я_к_о_г_о») превращается в
    # последовательность отдельных букв вместо слова.
    pytest.param(
        "Найденные окаменелости определили, в_н_е в_с_я_к_о_г_о с_о_м_н_е_н_и_я, эпоху пластов.",
        "Найденные окаменелости определили, вне всякого сомнения, эпоху пластов.",
        id="letterspaced_emphasis_with_underscores",
        marks=pytest.mark.xfail(
            strict=True,
            reason="underscore letter-spacing is read as separate letters",
        ),
    ),
    # Односимвольные римские цифры в перечислении читаются названиями латинских
    # букв, хотя соседние двухсимвольные раскрываются правильно.
    pytest.param(
        "Статьи вышли в выпусках I, II, IV, V этого издания за один год.",
        "Статьи вышли в выпусках первом, втором, четвёртом, пятом этого издания за один год.",
        id="single_letter_roman_numerals_in_a_list",
        marks=pytest.mark.xfail(
            strict=True,
            reason="single-letter roman numerals in a list are read as latin letter names",
        ),
    ),
    # Сокращение раскрывается в именительном падеже независимо от управления:
    # «оз.» → «озеро», «ред.» → «Редактор», «сост.» → «Составитель».
    pytest.param(
        "Отряд дошёл до западной оконечности оз. Иссык-Куль в июне того года.",
        "Отряд дошёл до западной оконечности озера Иссык-Куль в июне того года.",
        id="abbreviation_expanded_in_the_nominative",
        marks=pytest.mark.xfail(
            strict=True,
            reason="an expanded abbreviation ignores the government of the phrase",
        ),
    ),
    # Год в библиографической ссылке читается количественным («одна тысяча
    # восемьсот пятьдесят»), хотя тот же год после «за» читается порядковым.
    pytest.param(
        "Книга напечатана в типографии, СПБ, 1850.",
        "Книга напечатана в типографии, эс пэ бэ, тысяча восемьсот пятидесятый.",
        id="bibliographic_year_read_as_cardinal",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a year in a bibliographic reference is read as a bare cardinal",
        ),
    ),
    # Во втором члене сочинённой пары номер остаётся количественным: «гл. 8 и 9»
    # → «глава восьмая и девять».
    pytest.param(
        "Об этом сказано в гл. 8 и 9 второго тома издания.",
        "Об этом сказано в главах восьмой и девятой второго тома издания.",
        id="second_number_of_a_coordinated_pair",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the second number of a coordinated pair stays a cardinal",
        ),
    ),
    # --- Найдено сплошным чтением книги 05 (Небольсин) ---
    # «См.» с заглавной буквы после числа принимается за единицу «см»:
    # «13 См.: с. 22» читается «тринадцать сантиметров».
    pytest.param(
        "В примечании 13 См.: с. 22 указана ссылка на грамоту.",
        "В примечании тринадцать смотри: страница двадцать два указана ссылка на грамоту.",
        id="see_abbreviation_after_a_number_read_as_centimetres",
        marks=pytest.mark.xfail(
            strict=True,
            reason="capitalized См. after a number is read as the centimetre unit",
        ),
    ),
    # Заглавная буква в начале строки после числа принимается за единицу:
    # «20 А. Тюменка» читается «двадцать ампер».
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
    # Римские номера страниц после «с.» читаются в родительном падеже и теряют
    # диапазон.
    pytest.param(
        "Край Югорский описан подробно (с. CVIII—CXIII) в предисловии издателя.",
        "Край Югорский описан подробно (страницы сто восемь — сто тринадцать) "
        "в предисловии издателя.",
        id="roman_page_range_after_page_abbreviation",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a roman page range after с. is left in the genitive without a range",
        ),
    ),
    # Номер страницы в скобках читается в родительном падеже вместо
    # именительного.
    pytest.param(
        "Миллер, осматривавший это место, говорит (с. 179): что касается до перекопи.",
        "Миллер, осматривавший это место, говорит (страница сто семьдесят девять): "
        "что касается до перекопи.",
        id="page_number_in_parentheses_read_in_genitive",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a parenthesized page number is rendered in the genitive",
        ),
    ),
    # Одиночная римская цифра с точкой после сокращения тома читается названием
    # латинской буквы: «Т. I.» → «Т. ай.».
    pytest.param(
        "Ссылка выглядит так: Шафарик. Т. I. С. 315.",
        "Ссылка выглядит так: Шафарик. Том первый. Страница триста пятнадцать.",
        id="roman_one_with_a_dot_after_a_volume_abbreviation",
        marks=pytest.mark.xfail(
            strict=True,
            reason="roman I followed by a dot after Т. is read as a latin letter name",
        ),
    ),
    # Существительное перед римским диапазоном переставляется за него:
    # «глав XXXVII—XL» → «тридцать седьмую — сороковую глав».
    pytest.param(
        "Эти сведения составляют содержание маленьких глав XXXVII—XL летописи.",
        "Эти сведения составляют содержание маленьких глав тридцать седьмой — сороковой летописи.",
        id="noun_moved_after_a_roman_chapter_range",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the noun before a roman range is moved after it",
        ),
    ),
    # Порядковое числительное после «Изд.» читается количественным во
    # множественном числе: «Изд. 2-е.» → «Изд. Две.».
    pytest.param(
        "Второе издание вышло позже: Изд. 2-е. Москва, тысяча восемьсот сорок девятый год.",
        "Второе издание вышло позже: издание второе. Москва, тысяча восемьсот сорок девятый год.",
        id="edition_ordinal_after_izd_abbreviation",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the ordinal after Изд. is read as a plural cardinal",
        ),
    ),
    # Год после «лета» в старой датировке читается количественным вместо
    # порядкового.
    pytest.param(
        "Грамота писана лета 7078 марта в двадцатый день на Москве.",
        "Грамота писана лета семь тысяч семьдесят восьмого марта в двадцатый день на Москве.",
        id="year_after_leta_read_as_cardinal",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the year after лета is read as a cardinal instead of an ordinal",
        ),
    ),
    # В двойной датировке год в скобках читается количественным, хотя это тот же
    # год, что и перед скобками.
    pytest.param(
        "Летом 7096 (1588) года воеводы поставили город на Оби.",
        "Летом семь тысяч девяносто шестого (тысяча пятьсот восемьдесят восьмого) года "
        "воеводы поставили город на Оби.",
        id="parenthesized_year_of_a_double_date",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the parenthesized year of a double date is read as a cardinal",
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
    # Тире перед частицей «то» превращается в дефис и приклеивается к
    # предыдущему слову.
    pytest.param(
        "И неправды, что над тобой сталось — то сам ведаешь и помнишь.",
        "И неправды, что над тобой сталось — то сам ведаешь и помнишь.",
        id="dash_before_the_particle_to",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a dash before the particle то becomes a hyphen glued to the word",
        ),
    ),
    # Скобка внутри слова отделяется пробелом и разрывает слово.
    pytest.param(
        "А ты по той м(оей) граммате ничего не учинил и посольского дьяка не слушал.",
        "А ты по той м(оей) граммате ничего не учинил и посольского дьяка не слушал.",
        id="parentheses_inside_a_word",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a parenthesis inside a word is separated by spaces",
        ),
    ),
    # Закрывающая кавычка перед открывающей скобкой съедает пробел:
    # «пуст» (Строгановская» → «пуст "(Строгановская».
    pytest.param(
        "А град Сибирь оставиша пуст» (Строгановская летопись 1821 года).",
        'А град Сибирь оставиша пуст" (Строгановская летопись '
        "тысяча восемьсот двадцать первого года).",
        id="space_lost_after_a_closing_quote",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the space after a closing quote before a parenthesis is dropped",
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


@pytest.mark.parametrize(("source", "expected"), E2E_KNOWN_GAP_CASES)
def test_tts_e2e_normalization_known_gaps(source: str, expected: str) -> None:
    assert normalize(source, NormalizeOptions.tts()) == expected
