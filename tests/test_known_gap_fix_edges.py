"""Корнер-кейсы для правил, закрывших известные пробелы.

Каждый случай подобран так, чтобы сломать соответствующее правило: рядом с
рабочим примером стоит похожий вход, на котором правило срабатывать не должно.
"""

import pytest

from ru_normalizr import NormalizeOptions, normalize

LETTER_SUFFIX_CASES = (
    pytest.param("Дом 7Б готов к сдаче.", "Дом семь бэ готов к сдаче.", id="glued"),
    pytest.param(
        "Дом 7-Б готов к сдаче.", "Дом семь бэ готов к сдаче.", id="hyphenated"
    ),
    # Одна буква через пробел — это следующее слово, а не литера дома.
    pytest.param(
        "Строение 2 в цехе закрыто на ремонт.",
        "Строение два в цехе закрыто на ремонт.",
        id="preposition_after_number",
    ),
    pytest.param(
        "Офис 12 и склад работают до пяти.",
        "Офис двенадцать и склад работают до пяти.",
        id="conjunction_after_number",
    ),
)

PAUCAL_MODIFIER_CASES = (
    # Количественное на 2–4 требует существительное в родительном единственного,
    # а определение — во множественном.
    pytest.param(
        "В подвале установлено 3 кубических метра бетона.",
        "В подвале установлено три кубических метра бетона.",
        id="masculine_paucal",
    ),
    pytest.param(
        "Пациент получил 2 международные единицы препарата.",
        "Пациент получил две международные единицы препарата.",
        id="feminine_paucal",
    ),
    pytest.param(
        "В смесь добавили 22 кубических метра песка.",
        "В смесь добавили двадцать два кубических метра песка.",
        id="compound_paucal",
    ),
    pytest.param(
        "В смесь добавили 5 кубических метров песка.",
        "В смесь добавили пять кубических метров песка.",
        id="genitive_plural_not_paucal",
    ),
    pytest.param(
        "В смесь добавили 1 кубический метр песка.",
        "В смесь добавили один кубический метр песка.",
        id="singular_not_paucal",
    ),
)

RANGE_AGREEMENT_CASES = (
    # Левая граница диапазона согласуется с существительным, стоящим после
    # правой границы.
    pytest.param(
        "Компания обнаружила 2-3 ошибки в отчёте.",
        "Компания обнаружила две — три ошибки в отчёте.",
        id="feminine_noun_after_range",
    ),
    pytest.param(
        "Врач осмотрел 2-3 пациентов в час.",
        "Врач осмотрел двух — трёх пациентов в час.",
        id="animate_noun_after_range",
    ),
    # "рабочих" разбирается и как существительное, но это определение, поэтому
    # диапазон остаётся неодушевлённым.
    pytest.param(
        "Доставка займёт 2-3 рабочих дня.",
        "Доставка займёт два — три рабочих дня.",
        id="substantivized_modifier_after_range",
    ),
    pytest.param(
        "В зале осталось 2-3 места у окна.",
        "В зале осталось два — три места у окна.",
        id="neuter_noun_after_range",
    ),
    # Диапазон в косвенном падеже управляется существительным после него.
    pytest.param(
        "Обмен 3-5 квартирами занял почти год.",
        "Обмен тремя — пятью квартирами занял почти год.",
        id="instrumental_noun_range",
    ),
    pytest.param(
        "В 3-5 квартирах идёт ремонт.",
        "В трёх — пяти квартирах идёт ремонт.",
        id="locative_noun_range",
    ),
)

AGE_RANGE_CASES = (
    pytest.param(
        "Программа рассчитана на детей 6-12 лет и включает 24 занятия.",
        "Программа рассчитана на детей от шести до двенадцати лет "
        "и включает двадцать четыре занятия.",
        id="children_age_range",
    ),
    # После "возраст" числа — значение признака, а не возрастной интервал.
    pytest.param(
        "Возраст 10-20 лет считается юным.",
        "Возраст десять — двадцать лет считается юным.",
        id="attribute_value_stays_range",
    ),
)

SUFFIX_COORDINATION_CASES = (
    # У соседа "2-м" нет количественной формы на -м в предложном падеже, и это
    # снимает неоднозначность "1-м".
    pytest.param(
        "В 1-м и 2-м кварталах выручка выросла на 10%.",
        "В первом и втором кварталах выручка выросла на десять процентов.",
        id="locative_ordinals",
    ),
    pytest.param(
        "Отчёт сдан к 1-му и 2-му числу месяца.",
        "Отчёт сдан к первому и второму числу месяца.",
        id="dative_ordinals",
    ),
)

VERB_GOVERNMENT_CASES = (
    # "встречу" разбирается и как переходный глагол, но существительное
    # многократно вероятнее, поэтому падеж числительного им не управляется.
    pytest.param(
        "На встречу пришли 3 сотрудницы отдела.",
        "На встречу пришли три сотрудницы отдела.",
        id="noun_homonym_does_not_govern",
    ),
    # "пришли" — это и "прийти", и повелительное от "прислать"; при равной
    # вероятности непереходное чтение снимает винительный падеж.
    pytest.param(
        "На встречу пришли 2-3 сотрудницы отдела.",
        "На встречу пришли две — три сотрудницы отдела.",
        id="ambiguous_transitivity_keeps_nominative",
    ),
    pytest.param(
        "Компания заплатила 21 тысячу рублей подрядчику.",
        "Компания заплатила двадцать одну тысячу рублей подрядчику.",
        id="transitive_verb_still_governs",
    ),
)

NUMBER_SIGN_CASES = (
    # Вокализованные "со"/"ко" стоят только перед скоплением согласных, а знак
    # раскрывается в "номером"/"номеру".
    pytest.param(
        "Со № 5 началась новая нумерация документов.",
        "С номером пять началась новая нумерация документов.",
        id="vocalized_with_sentence_start",
    ),
    pytest.param(
        "Обратитесь ко № 12 в общем списке.",
        "Обратитесь к номеру двенадцать в общем списке.",
        id="vocalized_dative",
    ),
    pytest.param(
        "Дело под № 7 закрыто.", "Дело под номером семь закрыто.", id="plain_preposition"
    ),
)


@pytest.mark.parametrize(
    ("source", "expected"),
    (
        *LETTER_SUFFIX_CASES,
        *PAUCAL_MODIFIER_CASES,
        *RANGE_AGREEMENT_CASES,
        *AGE_RANGE_CASES,
        *SUFFIX_COORDINATION_CASES,
        *VERB_GOVERNMENT_CASES,
        *NUMBER_SIGN_CASES,
    ),
)
def test_gap_fix_edge_cases(source: str, expected: str) -> None:
    assert normalize(source) == expected


ABBREVIATION_DOT_CASES = (
    # Точка сокращения не начинает предложение и не съедает запятую.
    pytest.param(
        "Ссылка дана на примеч. 257 в конце главы.",
        "Ссылка дана на примеч. двести пятьдесят семь в конце главы.",
        id="truncated_abbreviation_keeps_lowercase",
    ),
    pytest.param(
        "Дом стоял в Мыльников пер., рядом была типография.",
        "Дом стоял в Мыльников пер., рядом была типография.",
        id="abbreviation_dot_keeps_comma",
    ),
    # Незнакомое словарю целое слово — не сокращение: продолжений в словаре у
    # него нет, поэтому граница предложения сохраняется.
    pytest.param(
        "Мы завершили деплой. 12 сервисов работают штатно.",
        "Мы завершили деплой. Двенадцать сервисов работают штатно.",
        id="unknown_whole_word_keeps_sentence_break",
    ),
    # Обычное слово перед точкой — граница предложения, а точка перед запятой
    # у него лишняя.
    pytest.param(
        "Работа закончена. 15 листов сданы в архив.",
        "Работа закончена. Пятнадцать листов сданы в архив.",
        id="plain_word_keeps_sentence_break",
    ),
    pytest.param(
        "Фраза., затем 2 слова.",
        "Фраза. затем два слова.",
        id="plain_word_drops_stray_dot",
    ),
    # Короткое настоящее слово в конце предложения не считается сокращением.
    pytest.param(
        "Их было сто. 40 человек ушли раньше.",
        "Их было сто. Сорок человек ушли раньше.",
        id="short_real_word_keeps_sentence_break",
    ),
    # Длинное слово (больше десяти букв) не может быть усечением: проверять
    # его как сокращение нельзя, иначе граница предложения теряется.
    pytest.param(
        "Работа была завершена. 7 томов ушли в переплёт.",
        "Работа была завершена. Семь томов ушли в переплёт.",
        id="long_word_keeps_sentence_break",
    ),
)


@pytest.mark.parametrize(("source", "expected"), ABBREVIATION_DOT_CASES)
def test_abbreviation_dot_edges(source: str, expected: str) -> None:
    assert normalize(source, NormalizeOptions.tts()) == expected


COUNTING_GROUP_CASES = (
    # Счётная группа — синтаксический остров: соседнее существительное или
    # прилагательное её не склоняет.
    pytest.param(
        "Мы живём в городе 12 лет.",
        "Мы живём в городе двенадцать лет.",
        id="locative_place_before_duration",
    ),
    pytest.param(
        "На глубине 200 м вода холодная.",
        "На глубине двести метров вода холодная.",
        id="locative_measure_head_before_unit",
    ),
    pytest.param(
        "Послано татар казанских и свияжских 100 человек.",
        "Послано татар казанских и свияжских сто человек.",
        id="genitive_attributes_before_count",
    ),
    # А вот согласованная косвенная группа остаётся косвенной: считанное слово
    # стоит не в счётной форме, а согласовано с числительным.
    pytest.param(
        "В 12 городах открыли пункты выдачи.",
        "В двенадцати городах открыли пункты выдачи.",
        id="agreeing_locative_plural_stays_oblique",
    ),
    pytest.param(
        "Он приехал с 200 метрами кабеля.",
        "Он приехал с двумястами метрами кабеля.",
        id="agreeing_instrumental_stays_oblique",
    ),
    # Предлог и глагол по-прежнему управляют счётной группой.
    pytest.param(
        "Он заплатил за 3 книги наличными.",
        "Он заплатил за три книги наличными.",
        id="preposition_still_governs_count",
    ),
    pytest.param(
        "Работы шли в течение 12 лет без перерыва.",
        "Работы шли в течение двенадцати лет без перерыва.",
        id="compound_preposition_still_governs_count",
    ),
    pytest.param(
        "Сумма 5 рублей указана в квитанции.",
        "Сумма пяти рублей указана в квитанции.",
        id="quantity_governor_still_assigns_genitive",
    ),
)


@pytest.mark.parametrize(("source", "expected"), COUNTING_GROUP_CASES)
def test_counting_group_edges(source: str, expected: str) -> None:
    assert normalize(source, NormalizeOptions.tts()) == expected


DISTANCE_FROM_LANDMARK_CASES = (
    pytest.param(
        "В 200 м от дома есть парк.",
        "В двухстах метрах от дома есть парк.",
        id="distance_from_landmark_is_locative",
    ),
    pytest.param(
        "В 5 км от города открыли завод.",
        "В пяти километрах от города открыли завод.",
        id="distance_with_prefixed_unit",
    ),
    # Без ориентира «в» сохраняет винительное чтение: это не расстояние.
    pytest.param(
        "Он вложил в 3 км дороги много сил.",
        "Он вложил в три километра дороги много сил.",
        id="accusative_quantity_without_landmark",
    ),
)


@pytest.mark.parametrize(("source", "expected"), DISTANCE_FROM_LANDMARK_CASES)
def test_distance_from_landmark_edges(source: str, expected: str) -> None:
    assert normalize(source, NormalizeOptions.tts()) == expected


DEGREE_SUFFIX_CASES = (
    # Буква шкалы присоединяется к знаку градуса только как зарегистрированное
    # обозначение.
    pytest.param(
        "Хребет лежит на 42° с. ш. и 74° в. д.",
        "Хребет лежит на сорок два градуса северной широты и семьдесят четыре "
        "градуса восточной долготы.",
        id="hemisphere_marker_keeps_plain_degree",
    ),
    pytest.param(
        "Точка 42° ю. ш. и 74° з. д. отмечена на карте.",
        "Точка сорок два градуса южной широты и семьдесят четыре градуса "
        "западной долготы отмечена на карте.",
        id="southern_and_western_markers",
    ),
    pytest.param(
        "Замер дал 30° с уклоном на север.",
        "Замер дал тридцать градусов с уклоном на север.",
        id="preposition_after_degree_is_not_a_scale",
    ),
    pytest.param(
        "Угол 30° к горизонту выдержан точно.",
        "Угол тридцать градусов к горизонту выдержан точно.",
        id="dative_preposition_after_degree",
    ),
    # Зарегистрированные обозначения шкал по-прежнему читаются целиком.
    pytest.param(
        "Температура была 20 °C утром.",
        "Температура была двадцать градусов Цельсия утром.",
        id="celsius_symbol_still_merges",
    ),
    pytest.param(
        "Духовку разогрели до 350 °F за час.",
        "Духовку разогрели до трёхсот пятидесяти градусов Фаренгейта за час.",
        id="fahrenheit_symbol_still_merges",
    ),
)


@pytest.mark.parametrize(("source", "expected"), DEGREE_SUFFIX_CASES)
def test_degree_suffix_edges(source: str, expected: str) -> None:
    assert normalize(source, NormalizeOptions.tts()) == expected


TRADITIONAL_TEMPERATURE_SCALE_CASES = (
    pytest.param(
        "Температура была +12,5° Ц. Здесь мы остановились.",
        "Температура была плюс двенадцать целых пять десятых градуса Цельсия. "
        "Здесь мы остановились.",
        id="celsius_abbreviation_at_sentence_end",
    ),
    pytest.param(
        "Температура была 20° Ц. и держалась весь день.",
        "Температура была двадцать градусов Цельсия и держалась весь день.",
        id="celsius_abbreviation_inside_sentence",
    ),
    pytest.param(
        "Жара достигла 100° Ф. в тени.",
        "Жара достигла ста градусов Фаренгейта в тени.",
        id="fahrenheit_traditional_abbreviation",
    ),
)


@pytest.mark.parametrize(("source", "expected"), TRADITIONAL_TEMPERATURE_SCALE_CASES)
def test_traditional_temperature_scale_edges(source: str, expected: str) -> None:
    assert normalize(source, NormalizeOptions.tts()) == expected
