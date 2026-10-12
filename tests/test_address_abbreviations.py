"""Postal address abbreviations: expansion, case agreement and non-address guards.

The guard half of this file is the important one: every abbreviation in the
address registry also spells out something else in ordinary prose («стр.» is a
page, «кв. м» is a square metre), so each rejection case here pins down a way
the stage must stay quiet.
"""

from __future__ import annotations

from unittest import mock

import pytest

from ru_normalizr import NormalizeOptions, address, normalize
from ru_normalizr.address import expand_address_abbreviations
from ru_normalizr.normalizer import PipelineNormalizer

TTS = NormalizeOptions.tts()
SAFE = NormalizeOptions.safe()


ADDRESS_CHAIN_CASES = (
    pytest.param(
        "Курьер прибудет по адресу: ул. Полевая, д. 10, корп. 2, кв. 35.",
        "Курьер прибудет по адресу: улица Полевая, дом десять, корпус два, "
        "квартира тридцать пять.",
        id="full_chain",
    ),
    pytest.param(
        "Адрес такой: д. 10, кв. 35 без уточнений.",
        "Адрес такой: дом десять, квартира тридцать пять без уточнений.",
        id="chain_without_street",
    ),
    pytest.param(
        "Пришлите документы на пр-т Мира, д. 1, стр. 3.",
        "Пришлите документы на проспекте Мира, дом один, строение три.",
        id="building_wins_over_page",
    ),
    pytest.param(
        "Заявка по адресу ул. Полевая, д.10, кв.35 принята.",
        "Заявка по адресу улица Полевая, дом десять, квартира тридцать пять принята.",
        id="no_space_after_dot",
    ),
    pytest.param(
        "Адрес доставки: ул. Красных Партизан, д. 3, кв. 12.",
        "Адрес доставки: улица Красных Партизан, дом три, квартира двенадцать.",
        id="two_word_street_name",
    ),
    pytest.param(
        "Первый склад: ул. Полевая, д. 1. Второй склад: ул. Лесная, д. 2.",
        "Первый склад: улица Полевая, дом один. Второй склад: улица Лесная, дом два.",
        id="two_independent_chains",
    ),
    pytest.param(
        "Ул. Полевая, д. 10 — адрес нового пункта выдачи.",
        "Улица Полевая, дом десять — адрес нового пункта выдачи.",
        id="sentence_initial_capital_is_kept",
    ),
    pytest.param(
        "Комиссия осмотрела влд. 5, стр. 2 в промышленной зоне.",
        "Комиссия осмотрела владение пять, строение два в промышленной зоне.",
        id="possession_and_building",
    ),
    pytest.param(
        "Договор подписан на пом. 7, оф. 12 в новом здании.",
        "Договор подписан на помещении семь, офис двенадцать в новом здании.",
        id="premises_and_office",
    ),
)


NAMED_ELEMENT_CASE_AGREEMENT_CASES = (
    pytest.param(
        "Офис компании находится по ул. Лесной.",
        "Офис компании находится по улице Лесной.",
        id="dative_after_po",
    ),
    pytest.param(
        "Водитель свернул на ул. Лесную и остановился у ворот.",
        "Водитель свернул на улицу Лесную и остановился у ворот.",
        id="accusative_after_na",
    ),
    pytest.param(
        "Магазин расположен на пл. Победы рядом с фонтаном.",
        "Магазин расположен на площади Победы рядом с фонтаном.",
        id="locative_after_na",
    ),
    pytest.param(
        "Мы дошли до пер. Кривого и свернули во двор.",
        "Мы дошли до переулка Кривого и свернули во двор.",
        id="genitive_after_do",
    ),
    pytest.param(
        "Встретимся у б-р Гоголевский ближе к вечеру.",
        "Встретимся у бульвара Гоголевский ближе к вечеру.",
        id="genitive_after_u",
    ),
    pytest.param(
        "Новый дом сдан в мкр. Северный этой весной.",
        "Новый дом сдан в микрорайоне Северный этой весной.",
        id="apposition_keeps_prepositional_case",
    ),
    pytest.param(
        "Он приехал на ул. Полевая ранним утром.",
        "Он приехал на улице Полевая ранним утром.",
        id="undeclined_name_follows_the_preposition",
    ),
    pytest.param(
        "Прогулка по наб. Фонтанки заняла целый час.",
        "Прогулка по набережной Фонтанки заняла целый час.",
        id="substantivized_adjective_lemma",
    ),
    pytest.param(
        "Автобус едет по ш. Энтузиастов до конечной остановки.",
        "Автобус едет по шоссе Энтузиастов до конечной остановки.",
        id="indeclinable_lemma_stays_intact",
    ),
    pytest.param(
        "Памятник поставили на просп. Мира прошлым летом.",
        "Памятник поставили на проспекте Мира прошлым летом.",
        id="avenue_locative",
    ),
    pytest.param(
        "Колонна прошла по пр-кт Ленина до самой площади.",
        "Колонна прошла по проспекту Ленина до самой площади.",
        id="hyphenated_avenue_abbreviation",
    ),
    pytest.param(
        "Школу построили в дер. Ивановка два года назад.",
        "Школу построили в деревне Ивановка два года назад.",
        id="village_locative",
    ),
    pytest.param(
        "Стройка идёт в кв-л Северный уже третий месяц.",
        "Стройка идёт в квартале Северный уже третий месяц.",
        id="quarter_locative",
    ),
    pytest.param(
        "Кафе открылось в туп. Малый напротив аптеки.",
        "Кафе открылось в тупике Малый напротив аптеки.",
        id="dead_end_locative",
    ),
    pytest.param(
        "Адрес такой: ул. Полевая, встречаемся у подъезда.",
        "Адрес такой: улица Полевая, встречаемся у подъезда.",
        id="colon_gives_no_governing_preposition",
    ),
)


NON_ADDRESS_GUARD_CASES = (
    pytest.param(
        "Таблица приведена на стр. 12 отчёта за прошлый квартал.",
        "страниц",
        id="lone_page_abbreviation_stays_a_page",
    ),
    pytest.param(
        "Площадь участка составляет 5 кв. м без учёта построек.",
        "квадратных метров",
        id="square_metre_is_not_an_apartment",
    ),
    pytest.param(
        "Объём резервуара равен 3 куб. м по проектной документации.",
        "кубических метра",
        id="cubic_metre_is_untouched",
    ),
    pytest.param(
        "Документ офиц. подтверждён.",
        "официальный",
        id="official_abbreviation_is_not_an_office",
    ),
    pytest.param(
        "Поездку отменили, т. к. дорогу закрыли на ремонт.",
        "так как",
        id="because_abbreviation_is_not_a_building",
    ),
    pytest.param(
        "Возьмите тетрадь, ручку и т. д. на завтрашнее занятие.",
        "так далее",
        id="etc_abbreviation_is_not_a_house",
    ),
    pytest.param(
        "Прим. пер. приведено в конце главы.",
        "переводчика",
        id="translator_note_is_not_a_lane",
    ),
)


NON_ADDRESS_UNCHANGED_CASES = (
    pytest.param(
        "Точка имеет координаты 55 градусов с. ш. и 37 градусов в. д.",
        ("с. ш.", "в. д."),
        id="geographic_direction_abbreviations",
    ),
    pytest.param(
        "Дело хранится в д. 5 архива областного суда.",
        ("д.",),
        id="lone_house_abbreviation_is_ambiguous",
    ),
    pytest.param(
        "Ответ разобран в к. 5 методического пособия.",
        ("к.",),
        id="lone_k_abbreviation_is_ambiguous",
    ),
    pytest.param(
        "Образец описан в лит. 4 сопроводительной ведомости.",
        ("лит.",),
        id="lone_letter_abbreviation_is_ambiguous",
    ),
    pytest.param(
        "Правки внесены в кор. 3 корректурного листа.",
        ("кор.",),
        id="lone_kor_abbreviation_is_ambiguous",
    ),
)


LABEL_NUMBER_CASES = (
    pytest.param(
        "Ключи от квартиры 35 потеряны ещё вчера.",
        "Ключи от квартиры тридцать пять потеряны ещё вчера.",
        id="apartment_label_after_genitive",
    ),
    pytest.param(
        "Ключи от пом. 7 забрал охранник на проходной.",
        "Ключи от помещения семь забрал охранник на проходной.",
        id="expanded_premises_label_after_genitive",
    ),
    pytest.param(
        "Поднимитесь на эт. 3 и поверните направо.",
        "Поднимитесь на этаже три и поверните направо.",
        id="expanded_floor_label",
    ),
    pytest.param(
        "Совещание идёт в кабинете 315 весь день.",
        "Совещание идёт в кабинете триста пятнадцать весь день.",
        id="office_room_label",
    ),
    pytest.param(
        "Цитата взята из тома 5 академического издания.",
        "Цитата взята из тома пять академического издания.",
        id="volume_label_is_lemma_matched",
    ),
    pytest.param(
        "Заявление зарегистрировано под номером 18 в канцелярии.",
        "Заявление зарегистрировано под номером восемнадцать в канцелярии.",
        id="number_label_is_lemma_matched",
    ),
)


@pytest.mark.parametrize(("source", "expected"), ADDRESS_CHAIN_CASES)
def test_address_chain_is_expanded(source: str, expected: str) -> None:
    assert normalize(source, TTS) == expected


@pytest.mark.parametrize(("source", "expected"), NAMED_ELEMENT_CASE_AGREEMENT_CASES)
def test_named_address_element_agrees_with_its_preposition(
    source: str, expected: str
) -> None:
    assert normalize(source, TTS) == expected


@pytest.mark.parametrize(("source", "expected_fragment"), NON_ADDRESS_GUARD_CASES)
def test_non_address_abbreviation_keeps_its_own_expansion(
    source: str, expected_fragment: str
) -> None:
    assert expected_fragment in normalize(source, TTS)


@pytest.mark.parametrize(("source", "kept_fragments"), NON_ADDRESS_UNCHANGED_CASES)
def test_ambiguous_abbreviation_outside_a_chain_is_left_alone(
    source: str, kept_fragments: tuple[str, ...]
) -> None:
    result = expand_address_abbreviations(source)
    assert result == source
    for fragment in kept_fragments:
        assert fragment in result


@pytest.mark.parametrize(("source", "expected"), LABEL_NUMBER_CASES)
def test_label_number_after_a_noun_stays_nominative(source: str, expected: str) -> None:
    assert normalize(source, TTS) == expected


def test_address_chain_does_not_start_a_new_sentence():
    # The dot of «д.» used to read as a sentence end, so the numerals stage
    # capitalized the house number in the middle of the address.
    result = normalize("Курьер прибудет по адресу: ул. Полевая, д. 10, кв. 35.", TTS)
    assert "Десять" not in result
    assert "Тридцать" not in result
    assert result.count(".") == 1


def test_address_chain_expands_the_same_way_in_safe_mode():
    assert normalize("Курьер прибудет по адресу: ул. Полевая, д. 10, кв. 35.", SAFE) == (
        "Курьер прибудет по адресу: улица Полевая, дом десять, квартира тридцать пять."
    )


def test_conjunction_breaks_the_address_chain():
    # «и» is not an address separator, so the ambiguous «д.» loses its only
    # unambiguous neighbour and must stay abbreviated.
    result = expand_address_abbreviations("Он живёт в д. 10 и в кв. 5.")
    assert result == "Он живёт в д. 10 и в квартире 5."


def test_lowercase_street_name_is_not_treated_as_an_address():
    assert expand_address_abbreviations("Сверните на ул. лесной дорогой.") == (
        "Сверните на ул. лесной дорогой."
    )


def test_named_abbreviation_without_a_name_is_not_expanded():
    assert expand_address_abbreviations("Значение ул. равно нулю.") == (
        "Значение ул. равно нулю."
    )


def test_numbered_abbreviation_without_a_number_is_not_expanded():
    assert expand_address_abbreviations("Значение кв. велико.") == (
        "Значение кв. велико."
    )


def test_house_number_with_a_letter_suffix_is_preserved():
    assert expand_address_abbreviations("Адрес: ул. Полевая, д. 7Б, кв. 3.") == (
        "Адрес: улица Полевая, дом 7Б, квартира 3."
    )


def test_house_number_with_a_slash_is_preserved():
    assert expand_address_abbreviations("Адрес: ул. Полевая, д. 10/2, кв. 3.") == (
        "Адрес: улица Полевая, дом 10/2, квартира 3."
    )


@pytest.mark.parametrize(
    "disabled",
    [
        {"enable_abbreviation_expansion": False},
        {"enable_contextual_abbreviation_expansion": False},
    ],
    ids=["abbreviation_expansion_off", "contextual_expansion_off"],
)
def test_disabled_abbreviation_options_skip_the_address_stage(
    disabled: dict[str, bool],
) -> None:
    # Флаги стадий проверяет пайплайн, а не сама стадия, поэтому выключенность
    # видна через `run_stage`.
    source = "Адрес: ул. Полевая, д. 10, кв. 35."
    normalizer = PipelineNormalizer(NormalizeOptions.tts(**disabled))
    assert normalizer.run_stage("address", source) == source


def test_address_stage_is_reachable_by_name():
    normalizer = PipelineNormalizer(TTS)
    assert normalizer.run_stage("address", "Адрес: ул. Полевая, д. 10.") == (
        "Адрес: улица Полевая, дом 10."
    )


def test_address_expansion_is_idempotent():
    source = "Курьер прибудет по адресу: ул. Полевая, д. 10, корп. 2, кв. 35."
    once = expand_address_abbreviations(source)
    assert expand_address_abbreviations(once) == once


@pytest.mark.parametrize(
    "source",
    ["", "Обычный текст без адресов.", "д.", "ул.", "кв. м", "3,5 д."],
    ids=["empty", "plain", "bare_house", "bare_street", "square_unit", "decimal_before"],
)
def test_degenerate_input_is_returned_unchanged(source: str) -> None:
    assert expand_address_abbreviations(source) == source


def test_preceding_word_lookback_is_bounded() -> None:
    """Падеж задаёт слово вплотную слева, а не весь текст до него.

    Шаблон предлога прибит к концу диапазона, поэтому поиск от нуля перечитывал
    книгу целиком на каждую адресную цепочку: 578 цепочек Слёзкина стоили 1,2
    млрд просканированных символов. Здесь фиксируется само окно — замер времени
    на CI ненадёжен, а верхняя граница диапазона проверяется точно.
    """
    spans: list[int] = []
    real = address._PRECEDING_WORD_PATTERN

    class Recorder:
        def search(self, text: str, pos: int, endpos: int):
            spans.append(endpos - pos)
            return real.search(text, pos, endpos)

    prefix = "Обычная проза без адресов. " * 4000
    source = f"{prefix}Дом стоит по адресу ул. Полевая, д. 10."
    with mock.patch.object(address, "_PRECEDING_WORD_PATTERN", Recorder()):
        expanded = expand_address_abbreviations(source)

    assert spans, "стадия не спросила слово слева"
    assert max(spans) <= address._PRECEDING_WORD_MAX_LOOKBACK
    assert len(prefix) > address._PRECEDING_WORD_MAX_LOOKBACK * 10
    assert "улица Полевая, дом 10." in expanded


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        pytest.param(
            "Свидание у ул. Полевая, д. 10.",
            "Свидание у улицы Полевая, дом десять.",
            id="preposition_next_to_chain",
        ),
        pytest.param(
            # Слово длиннее окна предлогом быть не может, и хвост «…до» не имеет
            # права сойти за предлог «до»: падеж берётся только у целого слова.
            "Птичьегнездогнездогнездогнездогнездо ул. Полевая, д. 10.",
            "Птичьегнездогнездогнездогнездогнездо улица Полевая, дом десять.",
            id="overlong_word_is_not_a_preposition",
        ),
    ],
)
def test_case_comes_from_the_whole_word_on_the_left(source: str, expected: str) -> None:
    assert normalize(source, TTS) == expected
