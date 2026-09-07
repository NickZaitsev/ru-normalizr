"""Каждое правило выбора падежа числительного проверено на живой фразе.

`get_numeral_case` — упорядоченный список правил, и порядок в нём тоже контракт:
верхнее правило заслоняет нижние. Отдельный тест на правило ловит две разные
поломки: неверный падеж (сверяется чтение всей фразы через публичный `normalize`)
и потерю правила из-за нового соседа сверху (сверяется, что решение приняло именно
оно). Второе без первого бесполезно: правило может срабатывать и читать неверно.

Фразы взяты из комментариев к самим правилам и из `test_known_gap_fixes.py`.
Таксономия файлов описана в `tests/README.md`.
"""

from __future__ import annotations

import pytest

from ru_normalizr.numerals._helpers import (
    _CASE_DECIDERS,
    CASE_RULES,
    _build_numeral_token_context,
    is_integer_token,
)
from ru_normalizr.numerals._rules import NumeralContext, resolve_case
from ru_normalizr.text_context import tokenize_with_spans

from .conftest import CheckTts


def _deciding_rules(source: str) -> set[str]:
    """Имена правил, решивших падеж хотя бы одного числа во фразе."""
    tokens, _ = tokenize_with_spans(source)
    context = _build_numeral_token_context(tokens)
    decided: set[str] = set()
    for idx, token in enumerate(tokens):
        if not is_integer_token(token):
            continue
        ctx = NumeralContext(
            tokens, idx, len(tokens), context.left_scan_starts, decisions=context.decisions
        )
        # Правило, которому нужен падеж числа слева, отвечает только по готовой
        # памятке: цепочку разрешает `resolve_case`. Без этого прогрева такое
        # правило уступило бы нижестоящему, и проба показала бы не того решателя.
        resolve_case(_CASE_DECIDERS, ctx)
        for rule in CASE_RULES:
            if rule.decide(ctx) is not None:
                decided.add(rule.name)
                break
    return decided


#: Правило — фраза — её чтение. Одна фраза может закрывать два правила: числа в
#: ней разные, и каждое решает своё.
RULE_CASES = (
    pytest.param(
        "operand-after-arithmetic-verb",
        "Нужно 9 умножить на 11 и записать результат в тетрадь.",
        "Нужно девять умножить на одиннадцать и записать результат в тетрадь.",
        id="operand_after_arithmetic_verb",
    ),
    pytest.param(
        "operand-before-multiplication",
        "Нужно 9 умножить на 11 и записать результат в тетрадь.",
        "Нужно девять умножить на одиннадцать и записать результат в тетрадь.",
        id="operand_before_multiplication",
    ),
    pytest.param(
        "ratio-left-operand",
        "Карта составлена в масштабе 1 к 50000 для всего района.",
        "Карта составлена в масштабе один к пятидесяти тысячам для всего района.",
        id="ratio_left_operand",
    ),
    pytest.param(
        "dimension-first-coordinate",
        "Габаритами 120 на 80 сантиметров стол не прошёл в дверь.",
        "Габаритами сто двадцать на восемьдесят сантиметров стол не прошёл в дверь.",
        id="dimension_first_coordinate",
    ),
    pytest.param(
        "temperature-equality",
        "По условию задачи это равно 177 °C, и печь придётся нагреть сильнее.",
        "По условию задачи это равно ста семидесяти семи градусам Цельсия, "
        "и печь придётся нагреть сильнее.",
        id="temperature_equality",
    ),
    pytest.param(
        "comparison-or-equal",
        "Значение показателя должно быть больше или равно 5 по школьной шкале.",
        "Значение показателя должно быть больше или равно пяти по школьной шкале.",
        id="comparison_or_equal",
    ),
    pytest.param(
        "equality-before-degree-unit",
        "Наклон рампы равен 30 ° по утверждённому проекту.",
        "Наклон рампы равен тридцати градусам по утверждённому проекту.",
        id="equality_before_degree_unit",
    ),
    pytest.param(
        "power-exponent",
        "Число 2 в степени 10 равно 1024, это знает любой программист.",
        "Число два в степени десять равно одна тысяча двадцать четыре, "
        "это знает любой программист.",
        id="power_exponent",
    ),
    pytest.param(
        # То же предложение: «2» здесь ярлык при слове-сущности «число».
        "entity-keyword-default",
        "Число 2 в степени 10 равно 1024, это знает любой программист.",
        "Число два в степени десять равно одна тысяча двадцать четыре, "
        "это знает любой программист.",
        id="entity_keyword_default",
    ),
    pytest.param(
        "distance-from-landmark",
        "Деревня стоит в 200 м от реки, поэтому вода всегда рядом.",
        "Деревня стоит в двухстах метрах от реки, поэтому вода всегда рядом.",
        id="distance_from_landmark",
    ),
    pytest.param(
        "measurement-continuation",
        "Между 2 ч 30 мин и 3 ч поезд стоял на станции.",
        "Между двумя часами тридцатью минутами и тремя часами поезд стоял "
        "на станции.",
        id="measurement_continuation",
    ),
    pytest.param(
        "coordinated-first-number",
        "Он пришёл на занятие с 5 и 7 книгами в рюкзаке.",
        "Он пришёл на занятие с пятью и семью книгами в рюкзаке.",
        id="coordinated_first_number",
    ),
    pytest.param(
        # То же предложение: «5» управляется существительным справа от «и».
        "coordinated-second-noun",
        "Он пришёл на занятие с 5 и 7 книгами в рюкзаке.",
        "Он пришёл на занятие с пятью и семью книгами в рюкзаке.",
        id="coordinated_second_noun",
    ),
    pytest.param(
        "range-right-boundary",
        "Задача решается за 5-7 минут, если не отвлекаться на телефон.",
        "Задача решается за пять — семь минут, если не отвлекаться на телефон.",
        id="range_right_boundary",
    ),
    pytest.param(
        "fresh-quantity-after-dash",
        "Первый канал — 2 Мбит/с, а второй заметно быстрее.",
        "Первый канал — два мегабита в секунду, а второй заметно быстрее.",
        id="fresh_quantity_after_dash",
    ),
    pytest.param(
        "range-start-governed-by-left",
        "Спортсмены выиграли 3-1 в первом же матче сезона.",
        "Спортсмены выиграли три — один в первом же матче сезона.",
        id="range_start_governed_by_left",
    ),
    pytest.param(
        "label-prefix",
        "Снимок сделан на ISO 100 при вечернем свете у окна.",
        "Снимок сделан на ай эс о сто при вечернем свете у окна.",
        id="label_prefix",
    ),
    pytest.param(
        "numbering-head",
        "Смотрите том 5 на верхней полке, там же лежит указатель.",
        "Смотрите том пять на верхней полке, там же лежит указатель.",
        id="numbering_head",
    ),
    pytest.param(
        "label-noun-head",
        "Мы живём в доме 5 на этой улице уже двенадцать лет.",
        "Мы живём в доме пять на этой улице уже двенадцать лет.",
        id="label_noun_head",
    ),
    pytest.param(
        "genitive-quantity-governor",
        "Итоговая сумма 4500 рублей устроила обе стороны сделки.",
        "Итоговая сумма четырёх тысяч пятисот рублей устроила обе стороны сделки.",
        id="genitive_quantity_governor",
    ),
    pytest.param(
        "locative-quantity-head",
        "Он ушёл на пенсию в возрасте 25 лет и занялся садом.",
        "Он ушёл на пенсию в возрасте двадцати пяти лет и занялся садом.",
        id="locative_quantity_head",
    ),
    pytest.param(
        "measure-parameter-head",
        "Металл плавится при температуре 660 градусов Цельсия, это знают литейщики.",
        "Металл плавится при температуре шестьсот шестьдесят градусов Цельсия, "
        "это знают литейщики.",
        id="measure_parameter_head",
    ),
    pytest.param(
        "preposition-before-number",
        "Он родился в 1995 году в Москве и вырос в Тушине.",
        "Он родился в тысяча девятьсот девяносто пятом году в Москве и вырос в Тушине.",
        id="preposition_before_number",
    ),
    pytest.param(
        "passive-participle-predicate",
        "В отчёте перечислены 3 причины отказа, и все они устранимы.",
        "В отчёте перечислены три причины отказа, и все они устранимы.",
        id="passive_participle_predicate",
    ),
    pytest.param(
        "adjective-agreement",
        "Свободных 7 хватило всем опоздавшим на вечерний сеанс.",
        "Свободных семи хватило всем опоздавшим на вечерний сеанс.",
        id="adjective_agreement",
    ),
    pytest.param(
        "verb-government",
        "Компания заплатила 1 миллион рублей налога и закрыла квартал.",
        "Компания заплатила один миллион рублей налога и закрыла квартал.",
        id="verb_government",
    ),
    pytest.param(
        "oblique-noun-on-the-right",
        "Угол при основании равен 45 градусам, поэтому треугольник равнобедренный.",
        "Угол при основании равен сорока пяти градусам, поэтому треугольник равнобедренный.",
        id="oblique_noun_on_the_right",
    ),
)

#: Правила, до которых поток целых чисел не доходит: их спрашивают из своей
#: стадии, со своим потоком токенов. Проверяются только по чтению — имя правила
#: на обычном потоке не наблюдается.
INDIRECT_RULE_CASES = (
    pytest.param(
        "oblique-noun-before-bare-number",
        "Передатчик работает на частоте 3,2 и не сбивается даже ночью.",
        "Передатчик работает на частоте трёх целых двух десятых и не сбивается даже ночью.",
        id="oblique_noun_before_bare_number",
    ),
)


@pytest.mark.parametrize(("rule", "source", "expected"), RULE_CASES)
def test_case_rule_reads_the_sentence_and_decides_it(
    check_tts: CheckTts, rule: str, source: str, expected: str
) -> None:
    check_tts(source, expected)
    decided = _deciding_rules(source)
    assert rule in decided, (
        f"падеж во фразе решило не правило {rule!r}, а {sorted(decided)}: "
        "правило заслонено соседом сверху либо перестало срабатывать"
    )


@pytest.mark.parametrize(("rule", "source", "expected"), INDIRECT_RULE_CASES)
def test_case_rule_reads_the_sentence(
    check_tts: CheckTts, rule: str, source: str, expected: str
) -> None:
    check_tts(source, expected)


def test_bare_number_falls_back_to_nominative(check_tts: CheckTts) -> None:
    """Ни одно правило не сработало — число остаётся именительным."""
    source = "Мне уже 40, и я не жалуюсь на здоровье."
    check_tts(source, "Мне уже сорок, и я не жалуюсь на здоровье.")
    assert not _deciding_rules(source), "фраза должна доходить до именительного по умолчанию"


def test_every_case_rule_has_a_sentence() -> None:
    """Новое правило без фразы — правило, о приоритете которого никто не знает."""
    covered = {case.values[0] for case in RULE_CASES + INDIRECT_RULE_CASES}
    missing = [rule.name for rule in CASE_RULES if rule.name not in covered]
    assert not missing, f"правила без проверочной фразы: {missing}"


def test_case_rule_names_are_unique_kebab_case() -> None:
    """Имя правила попадает в сообщения тестов, поэтому оно уникально и читаемо."""
    names = [rule.name for rule in CASE_RULES]
    assert len(names) == len(set(names)), "имена правил повторяются"
    assert all(name == name.lower() and " " not in name and "_" not in name for name in names), (
        f"имена не в кебаб-кейсе: {names}"
    )
