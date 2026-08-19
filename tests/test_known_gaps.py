"""Исполняемый список согласованных пробелов, которые пока не исправлены."""

import pytest

from .conftest import CheckTts

#: Пробелы, найденные точечными проверками, а не сплошным чтением книги.
HANDWRITTEN_GAP_CASES = (
    # Косвенная вершина измерения слева склоняет и целое число, хотя при целом
    # это приложение-ярлык: «на частоте три», как «на частоте три и две десятых».
    # Правило `oblique-noun-before-bare-number` писалось под дробь и целое ловит
    # заодно; отличить дробь от целого одного взгляда на соседей не хватает —
    # нужен признак «число называет параметр, а не считает предметы».
    pytest.param(
        "На частоте 3 передатчик работает стабильно почти без помех.",
        "На частоте три передатчик работает стабильно почти без помех.",
        id="bare_integer_after_oblique_measurement_head",
        marks=pytest.mark.xfail(
            strict=True,
            reason="oblique-noun-before-bare-number also declines a bare integer label",
        ),
    ),
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
    # Диапазон при мере длины уходит в родительный падеж вместо именительного.
    pytest.param(
        "От них до реки 130—140 верст по прямой дороге.",
        "От них до реки сто тридцать — сто сорок вёрст по прямой дороге.",
        id="measure_range_read_in_the_genitive",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a range of a length measure is rendered in the genitive",
        ),
    ),
    # Число после предлога «в» в значении меры остаётся в именительном падеже.
    pytest.param(
        "Ягайло, простояв верстах в 40, повернул назад к своим границам.",
        "Ягайло, простояв верстах в сорока, повернул назад к своим границам.",
        id="number_after_preposition_v_in_the_locative",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a number after the preposition в stays in the nominative",
        ),
    ),
    # Точка как разделитель разрядов принимается за десятичную, а «кв.» —
    # за киловольты.
    pytest.param(
        "При Иоанне III Москва имела площадь около 15.000 кв. миль.",
        "При Иоанне третьем Москва имела площадь около пятнадцати тысяч квадратных миль.",
        id="dot_as_a_thousands_separator_before_a_square_unit",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a dot thousands separator is read as a decimal point and кв. as kilovolts",
        ),
    ),
    # Число после прилагательного в творительном падеже остаётся именительным.
    pytest.param(
        "Отряд начальствовал отборными 1000 чел., от которых высылались разъезды.",
        "Отряд начальствовал отборными тысячей человек, от которых высылались разъезды.",
        id="number_after_an_instrumental_adjective",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a number after an instrumental adjective stays nominative",
        ),
    ),
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
    # Слово в начале следующего предложения пропадает из вывода после числа
    # со счётной формой.
    pytest.param(
        "Всего было принято 32 000 человек. Люди поступили на укомплектование "
        "двадцати семи пехотных полков.",
        "Всего было принято тридцать две тысячи человек. Люди поступили "
        "на укомплектование двадцати семи пехотных полков.",
        id="word_dropped_after_a_sentence_boundary",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the first word of the next sentence is dropped after a counted form",
        ),
    ),
    # Дробное число перед «тысяч» ломает согласование: «тысячи» вместо «тысяч».
    pytest.param(
        "Заготовлено около 12 тысяч бомб и 11,5 тысяч ручных гранат.",
        "Заготовлено около двенадцати тысяч бомб и одиннадцати с половиной тысяч ручных гранат.",
        id="decimal_number_before_thousands",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a decimal before тысяч breaks the agreement of the counted noun",
        ),
    ),
    # Составное число в творительном падеже склоняется только по первой части.
    pytest.param(
        "Мы закончили дело 2700 пленными и полным разгромом неприятельского обоза.",
        "Мы закончили дело двумя тысячами семьюстами пленными "
        "и полным разгромом неприятельского обоза.",
        id="instrumental_of_a_four_digit_number",
        marks=pytest.mark.xfail(
            strict=True,
            reason="only the first part of a compound number takes the instrumental",
        ),
    ),
    # Число после «в составе» остаётся в именительном падеже.
    pytest.param(
        "Низовый корпус был в составе 12 400 чел. и стоял отдельно.",
        "Низовый корпус был в составе двенадцати тысяч четырёхсот человек и стоял отдельно.",
        id="number_after_v_sostave",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a number after в составе stays in the nominative",
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
    # Запятая как разделитель разрядов принимается за десятичную.
    pytest.param(
        "Выставлялись две рати, каждая около 10,000 чел., у Новосела и Мценска.",
        "Выставлялись две рати, каждая около десяти тысяч человек, у Новосела и Мценска.",
        id="comma_as_a_thousands_separator",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a comma thousands separator is read as a decimal point",
        ),
    ),
    # Дробь, набранная одним знаком и приклеенная к целому («2½»), читается как
    # отдельное двузначное число.
    pytest.param(
        "В неравной борьбе и только ценою 2½ столетий рабства они уцелели.",
        "В неравной борьбе и только ценою двух с половиной столетий рабства они уцелели.",
        id="vulgar_fraction_glued_to_an_integer",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a vulgar fraction glued to an integer is read as a two-digit number",
        ),
    ),
    # Дробь-знак в составе прилагательного («½-пудовой») не сворачивается
    # в «полупудовой».
    pytest.param(
        "Единорогъ былъ трехъ видовъ: 2-пудовой, пудовой и ½-пудовой.",
        "Единорогъ былъ трехъ видовъ: двухпудовой, пудовой и полупудовой.",
        id="vulgar_fraction_in_an_attribute",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a vulgar fraction in an attribute is not folded into полу-",
        ),
    ),
    # Творительный падеж предыдущего слова перетекает на следующее число
    # в перечислении.
    pytest.param(
        "Шведы теряютъ до трехъ тысячъ убитыми, 8 знаменъ, 4 орудія и весь обозъ.",
        "Шведы теряютъ до трехъ тысячъ убитыми, восемь знаменъ, четыре орудія и весь обозъ.",
        id="instrumental_leaks_to_the_next_count",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the instrumental of a previous word leaks to the next count",
        ),
    ),
    # Согласование числа с дореформенным прилагательным портит само слово:
    # «2 прочныя» → «двух прочныев».
    pytest.param(
        "Эта работа подготовила 2 прочныя ступени къ новому подвигу нашей рати.",
        "Эта работа подготовила двѣ прочныя ступени къ новому подвигу нашей рати.",
        id="adjective_corrupted_by_agreement",
        marks=pytest.mark.xfail(
            strict=True,
            reason="agreement with a pre-reform adjective corrupts the adjective itself",
        ),
    ),
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
    # Число перед существительным в винительном падеже остаётся количественным
    # вместо порядкового.
    pytest.param(
        "Работы были назначены на 27 неделю по церковному календарю того года.",
        "Работы были назначены на двадцать седьмую неделю по церковному календарю того года.",
        id="number_before_an_accusative_noun_stays_cardinal",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a number before an accusative noun stays cardinal instead of ordinal",
        ),
    ),
    # Число после «у меня» уходит в родительный падеж вместо именительного.
    pytest.param(
        "У меня 350 казаков, и с ними я готов идти на неприятеля.",
        "У меня триста пятьдесят казаков, и с ними я готов идти на неприятеля.",
        id="count_after_u_menya_read_in_the_genitive",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a count after у меня is put into the genitive",
        ),
    ),
    # Время «в 2 часа ночи» получает предложный падеж вместо винительного:
    # «в 2 часа» → «в двух часа».
    pytest.param(
        "Он пришёл в 2 часа ночи и сразу лёг спать до самого утра.",
        "Он пришёл в два часа ночи и сразу лёг спать до самого утра.",
        id="hour_after_v_gets_locative_case",
        marks=pytest.mark.xfail(
            strict=True,
            reason="в + N часа is read as a locative instead of accusative",
        ),
    ),
    # Разделительное «по» с числом даёт винительный вместо родительного:
    # «по 2 бургомистра» → «по двух бургомистров».
    pytest.param(
        "В каждом городе выбирали по 2 бургомистра из числа торговых людей.",
        "В каждом городе выбирали по два бургомистра из числа торговых людей.",
        id="distributive_po_with_a_count_noun",
        marks=pytest.mark.xfail(
            strict=True,
            reason="distributive по with a count noun produces the wrong case",
        ),
    ),
    # Число перед «тысяч» уходит в дательный падеж вслед за глаголом.
    pytest.param(
        "Ему предлагали 300 тысяч рейхсталеров, но он отказался от этих денег.",
        "Ему предлагали триста тысяч рейхсталеров, но он отказался от этих денег.",
        id="number_before_thousands_read_in_the_dative",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a number before тысяч takes the dative of the governing verb",
        ),
    ),
)


#: Найдено сплошным чтением книги 03 (Карамзин, «История государства Российского»).
BOOK_03_GAP_CASES = (
    # Греческое слово транслитерируется частично: отдельные буквы заменяются
    # русскими названиями, остальные остаются как есть.
    pytest.param(
        "Греки называли это море Μαῦρο θάλασσα, а турки давали ему своё имя.",
        "Греки называли это море Μαῦρο θάλασσα, а турки давали ему своё имя.",
        id="greek_word_transliterated_letter_by_letter",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a greek word is partially replaced with russian letter names",
        ),
    ),
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
    # Служебный символ из приватной области Unicode попадает в результат, если
    # дефис-тире стоит внутри цитаты.
    pytest.param(
        "Он писал так: «Я выехал из Москвы, - пишет он, - 13 апреля и прибыл к вечеру».",
        'Он писал так: "Я выехал из Москвы, — пишет он, — тринадцатого апреля и прибыл к вечеру".',
        id="private_use_sentinel_leaks_into_the_output",
        marks=pytest.mark.xfail(
            strict=True,
            reason="an internal private-use sentinel character leaks into the output",
        ),
    ),
)


#: Найдено сплошным чтением книги 01 («История России с древнейших времён»).
BOOK_01_GAP_CASES = (
    # Предлог «с» после дроби принимается за сокращение секунды.
    pytest.param(
        "Если считать по этому расчёту, то придётся на рубль положить по 10 коп. 1/8 с дробями.",
        "Если считать по этому расчёту, то придётся на рубль положить "
        "по десять копеек одна восьмая с дробями.",
        id="preposition_s_read_as_seconds_after_a_fraction",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the preposition s after a fraction is read as the seconds symbol",
        ),
    ),
    # Косая черта в архивном шифре при «№» читается как дробь.
    pytest.param(
        "Следственные дела хранятся в Архиве министерства юстиции под № 72/288.",
        "Следственные дела хранятся в Архиве министерства юстиции "
        "под номером семьдесят два дробь двести восемьдесят восемь.",
        id="archive_reference_slash_read_as_a_fraction",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the slash in an archive reference number is read as a fraction",
        ),
    ),
    # Порядковое окончание последнего числа не распространяется на перечисление.
    pytest.param(
        "Синод сослался на 494, 495 и 496-й статьи большого наказа и отложил решение.",
        "Синод сослался на четыреста девяносто четвёртую, четыреста девяносто пятую "
        "и четыреста девяносто шестую статьи большого наказа и отложил решение.",
        id="ordinal_suffix_not_spread_over_an_enumeration",
        marks=pytest.mark.xfail(
            strict=True,
            reason="only the last number of the enumeration becomes an ordinal",
        ),
    ),
    # Падеж от предлога «до» получает только первое число перечисления.
    pytest.param(
        "Соль продается неравными ценами от 3 копеек до 20, 30 и 40 копеек за пуд.",
        "Соль продается неравными ценами от трёх копеек до двадцати, тридцати "
        "и сорока копеек за пуд.",
        id="case_not_spread_over_an_enumerated_range",
        marks=pytest.mark.xfail(
            strict=True,
            reason="only the first number after the preposition takes its case",
        ),
    ),
    # Число в винительном падеже при инфинитиве уходит в предложный.
    pytest.param(
        "Он думает сим способом 100000 рублей достать, а после уехать за границу.",
        "Он думает сим способом сто тысяч рублей достать, а после уехать за границу.",
        id="accusative_object_read_in_the_prepositional",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the accusative object of the infinitive is read in the prepositional",
        ),
    ),
    # Номер часа после предлога «в» остаётся количественным.
    pytest.param(
        "Пополуночи в 9 часу неприятель показался на левом фланге.",
        "Пополуночи в девятом часу неприятель показался на левом фланге.",
        id="hour_after_v_stays_cardinal",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the hour number after v is not made ordinal",
        ),
    ),
    # Счёт в позиции подлежащего уходит в косвенный падеж.
    pytest.param(
        "В Козлове 103 церкви, 7596 дворов и более двадцати пяти тысяч жителей.",
        "В Козлове сто три церкви, семь тысяч пятьсот девяносто шесть дворов "
        "и более двадцати пяти тысяч жителей.",
        id="subject_count_read_in_an_oblique_case",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a count in subject position is put into an oblique case",
        ),
    ),
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
