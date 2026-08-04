"""Executable inventory of agreed defects not fixed yet.

Every entry is a natural full-message regression marked
``pytest.mark.xfail(strict=True)``. When a defect is fixed, its assertion moves
to the closest focused regular suite in the same commit.
"""

import unittest

import pytest

from ru_normalizr import NormalizeOptions, normalize


class RuNormalizrKnownGapTests(unittest.TestCase):
    @pytest.mark.xfail(
        strict=True,
        reason="the plural year abbreviation leaves its dot before a shared era marker",
    )
    def test_plural_year_abbreviation_does_not_split_shared_era_marker(self):
        self.assertEqual(
            normalize("44-45 гг. до н. э."),
            "сорок четвёртые — сорок пятые годы до нашей эры.",
        )

    @pytest.mark.xfail(
        strict=True,
        reason="the abbreviated year dot remains before a shared era marker",
    )
    def test_singular_year_abbreviation_does_not_split_shared_era_marker(self):
        self.assertEqual(
            normalize("В 300-200 г. до н. э."),
            "В трёхсотых — двухсотых годах до нашей эры.",
        )

    @pytest.mark.xfail(
        strict=True,
        reason="the month alternation has no right-hand word boundary",
    )
    def test_month_name_is_not_matched_inside_a_longer_word(self):
        self.assertEqual(normalize("15 маяк"), "пятнадцать маяк")
        self.assertEqual(normalize("20 маяков"), "двадцать маяков")

    @pytest.mark.xfail(
        strict=True,
        reason="CamelCase tokens are never split, so the acronym never reaches "
        "the abbreviation stage",
    )
    def test_acronym_inside_a_camel_case_token_is_read_letter_by_letter(self):
        tts = NormalizeOptions.tts()
        self.assertIn("эс кью эл", normalize("PostgreSQL", tts))
        self.assertIn("кью эл", normalize("GraphQL", tts))
        self.assertIn("ви пи эн", normalize("OpenVPN", tts))

    @pytest.mark.xfail(
        strict=True,
        reason="the -х suffix is read as a cardinal before an ordinally numbered noun",
    )
    def test_ordinal_suffix_wins_before_an_ordinally_numbered_noun(self):
        self.assertEqual(
            normalize("В 5-х классах ввели новый предмет."),
            "В пятых классах ввели новый предмет.",
        )
        self.assertEqual(
            normalize("Учитель работает в 9-х классах второй год."),
            "Учитель работает в девятых классах второй год.",
        )

    @pytest.mark.xfail(
        strict=True,
        reason="the -ми suffix forces the instrumental case after a locative preposition",
    )
    def test_mi_suffix_agrees_with_the_preposition_case(self):
        self.assertEqual(
            normalize("В 7-ми классах ввели новую программу."),
            "В семи классах ввели новую программу.",
        )

    @pytest.mark.xfail(
        strict=True,
        reason="the counted noun keeps the form written beside the digit",
    )
    def test_animate_paucal_accusative_agrees_the_counted_noun(self):
        self.assertEqual(normalize("Вижу 2 человека у входа."), "Вижу двух человек у входа.")

    @pytest.mark.xfail(
        strict=True,
        reason="finalize mistakes the last initial before a conjunction for a sentence end",
    )
    def test_initial_before_a_conjunction_does_not_create_a_sentence_boundary(self):
        text = "В комиссию вошли Петров В. Г. и Сидоров."
        self.assertEqual(normalize(text), text)

    @pytest.mark.xfail(
        strict=True,
        reason="the pause comma after initials is emitted even when punctuation "
        'already follows, giving ",;", ",:" and ", —"',
    )
    def test_pause_comma_after_initials_is_dropped_before_other_punctuation(self):
        tts = NormalizeOptions.tts()
        for text, expected in (
            (
                "Отчёт сдал Иванов А. Б.; проверил Петров.",
                "Отчёт сдал Иванов, аа, бэ; проверил Петров.",
            ),
            (
                "Акт подписал Иванов А. Б.: копия у Петрова.",
                "Акт подписал Иванов, аа, бэ: копия у Петрова.",
            ),
            (
                "Список: Иванов А. Б. — далее по тексту.",
                "Список: Иванов, аа, бэ — далее по тексту.",
            ),
        ):
            self.assertEqual(normalize(text, tts), expected)

    @pytest.mark.xfail(
        strict=True,
        reason="the dot of an expanded unit abbreviation is left before the comma",
    )
    def test_expanded_unit_abbreviation_drops_its_dot_and_keeps_the_comma(self):
        # The other half of the same cleanup: here the dot is a leftover from
        # "кг." spelled out as a word, so it is the dot that has to go and the
        # comma that has to stay — the opposite of the initials case above.
        self.assertEqual(
            normalize("Цена 5,5 кг., доставка бесплатно."),
            "Цена пяти целых пяти десятых килограмма, доставка бесплатно.",
        )
        self.assertEqual(
            normalize("Итого 3,5 млн руб., без НДС."),
            "Итого три целых пять десятых миллиона рублей, без НДС.",
        )

    @pytest.mark.xfail(
        strict=True,
        reason="the adjective abbreviation is inflected without the head noun's "
        "animacy, so an inanimate accusative gets the animate form",
    )
    def test_adjective_abbreviation_takes_the_inanimate_accusative(self):
        # pymorphy resolves a bare accusative to the animate variant, so the
        # target tags have to carry the noun's "inan" over.
        self.assertEqual(
            normalize("Подписали гос. контракт на поставку."),
            "Подписали государственный контракт на поставку.",
        )
        self.assertEqual(
            normalize("Приняли гос. меры поддержки бизнеса."),
            "Приняли государственные меры поддержки бизнеса.",
        )
        self.assertEqual(
            normalize("Отправили офиц. запросы всем участникам."),
            "Отправили официальные запросы всем участникам.",
        )

    @pytest.mark.xfail(
        strict=True,
        reason="a substantivized adjective is never a head noun candidate, so "
        "the abbreviation agrees with a later word instead",
    )
    def test_substantivized_adjective_is_a_head_noun_for_the_abbreviation(self):
        self.assertEqual(
            normalize("Наградили гос. служащего медалью."),
            "Наградили государственного служащего медалью.",
        )
        self.assertEqual(
            normalize("Опросили полит. заключённых колонии."),
            "Опросили политических заключённых колонии.",
        )

    @pytest.mark.xfail(
        strict=True,
        reason="with no modifier to agree with, every head noun parse scores the "
        "same and pymorphy's parse order decides the case",
    )
    def test_head_noun_case_is_not_decided_by_the_parse_order(self):
        self.assertEqual(
            normalize("Восстановили гос. пути сообщения."),
            "Восстановили государственные пути сообщения.",
        )

    @pytest.mark.xfail(
        strict=True,
        reason="the numerals stage tokenizes a hyphen between two dotted "
        "abbreviations and detokenize cannot glue it back",
    )
    def test_hyphen_joined_dotted_abbreviation_survives_the_numerals_stage(self):
        self.assertEqual(
            normalize("Построили ж.-д. вокзал нового типа."),
            "Построили железнодорожный вокзал нового типа.",
        )
        self.assertEqual(
            normalize("Развиваем с.-х. производство региона."),
            "Развиваем сельскохозяйственное производство региона.",
        )

    @pytest.mark.xfail(
        strict=True,
        reason="preprocess rewrites the stress mark to a plus before the year "
        "stage runs, so the year word is matched only up to the plus and its "
        "tail is left over next to the inflected form",
    )
    def test_stressed_year_word_is_inflected_as_one_word(self):
        # "года́ми" becomes "год+ами" in preprocess; the year stage then matches
        # the bare "год", inflects it, and the orphaned "+ами" survives beside
        # the result.
        self.assertEqual(
            normalize("Между 1999 и 2000 года́ми разница велика."),
            "Между тысяча девятьсот девяносто девятым и двухтысячным годами разница велика.",
        )
        self.assertEqual(
            normalize("Период между 2020 и 2025 года́ми оказался насыщенным."),
            "Период между две тысячи двадцатым и две тысячи двадцать пятым "
            "годами оказался насыщенным.",
        )

    @pytest.mark.xfail(
        strict=True,
        reason="preprocess spaces out the dots of an acronym, so the dotted "
        "abbreviation pattern never matches in the full pipeline",
    )
    def test_dotted_acronym_is_read_as_one_abbreviation(self):
        # ABBREV_DOTTED_PATTERN needs the dots glued to the letters, so the whole
        # is_dotted branch is unreachable through normalize: the leftover dots
        # then turn one sentence into three.
        tts = NormalizeOptions.tts()
        self.assertEqual(
            normalize("Флаг С.Ш.А. висел над входом.", tts),
            "Флаг сэ шэ аа висел над входом.",
        )
        self.assertEqual(
            normalize("Он вступил в Н.А.Т.О. в мае.", tts),
            "Он вступил в нато в мае.",
        )

    @pytest.mark.xfail(
        strict=True,
        reason="numerals joined by 'и' inherit nominative instead of the "
        "governing instrumental case",
    )
    def test_conjoined_numerals_keep_the_governing_case(self):
        self.assertEqual(
            normalize("Управление 3 и 5 заводами продолжается."),
            "Управление тремя и пятью заводами продолжается.",
        )

    @pytest.mark.xfail(
        strict=True,
        reason="a numeric range inflects its endpoints inconsistently instead "
        "of using the case of the governing noun",
    )
    def test_numeric_range_inflects_both_endpoints_in_the_same_case(self):
        self.assertEqual(
            normalize("Обмен 3-5 квартирами прошёл успешно."),
            "Обмен тремя — пятью квартирами прошёл успешно.",
        )

@pytest.mark.xfail(
    strict=True,
    reason="disabling URL normalization lets generic cleanup corrupt URL punctuation and casing",
)
def test_disabled_url_normalization_preserves_url_verbatim():
    options = NormalizeOptions.safe(
        enable_url_normalization=False,
        remove_links=False,
        enable_numeral_normalization=False,
    )

    assert normalize("Адрес https://milk.org/docs указан в главе IV.", options) == (
        "Адрес https://milk.org/docs указан в главе четвёртой."
    )


@pytest.mark.xfail(
    strict=True,
    reason="the predicate context incorrectly puts a nominative counted numeral in genitive",
)
def test_predicate_keeps_counted_numeral_nominative_after_roman_reference():
    assert normalize("В главе IV перечислены 3 причины.", NormalizeOptions.safe()) == (
        "В главе четвёртой перечислены три причины."
    )


@pytest.mark.xfail(
    strict=True,
    reason="an abbreviation expanded at sentence start is not capitalized",
)
def test_expanded_abbreviation_at_sentence_start_is_capitalized():
    assert normalize("Т. е. документ содержит 3 раздела.", NormalizeOptions.safe()) == (
        "То есть документ содержит три раздела."
    )


E2E_KNOWN_GAP_CASES = (
    pytest.param(
        "Встреча назначена на 12.05.2025 в 09:07, кабинет 315.",
        "Встреча назначена на двенадцатое мая две тысячи двадцать пятого года "
        "в девять, ноль семь, кабинет триста пятнадцать.",
        id="datetime_and_room",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a calendar date after 'назначена на' is rendered in genitive, not accusative",
        ),
    ),
    pytest.param(
        "За 3,5 кг яблок заплатили 1 249,90 руб.",
        "За три целых пять десятых килограмма яблок заплатили одну тысячу двести "
        "сорок девять рублей девяносто копеек.",
        id="weight_and_price",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a decimal quantity inherits the wrong case and decimal currency is not split into rubles and kopecks",
        ),
    ),
    pytest.param(
        "Ночью температура изменится от −12 °C до +3 °C.",
        "Ночью температура изменится от минус двенадцати градусов Цельсия до плюс "
        "трёх градусов Цельсия.",
        id="signed_temperature_range",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a unary plus before a temperature is left as a raw symbol",
        ),
    ),
    pytest.param(
        "Участок размером 12,5 × 8 м имеет площадь 100 м².",
        "Участок размером двенадцать целых пять десятых на восемь метров имеет площадь "
        "сто квадратных метров.",
        id="dimensions_and_area",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the multiplication sign in physical dimensions is read as an arithmetic operation",
        ),
    ),
    pytest.param(
        "Позвоните по номеру +7 (495) 123-45-67 после 18:30.",
        "Позвоните по номеру плюс семь, четыреста девяносто пять, сто двадцать три, "
        "сорок пять, шестьдесят семь после восемнадцати часов тридцати минут.",
        id="phone_number",
        marks=pytest.mark.xfail(
            strict=True,
            reason="phone syntax loses the parenthesized area code and leaves plus and grouping unnormalized",
        ),
    ),
    pytest.param(
        "Отчёт доступен на example.ru/docs, вопросы отправляйте на help@example.ru.",
        "Отчёт доступен на игзэмпэл точка ру слэш докс, вопросы отправляйте на хэлп "
        "собака игзэмпэл точка ру.",
        id="web_and_email",
        marks=pytest.mark.xfail(
            strict=True,
            reason="bare web and email addresses reach latinization before their separators are verbalized",
        ),
    ),
    pytest.param(
        "21-й участник поднялся на 14-й этаж за 2 мин 35 сек.",
        "Двадцать первый участник поднялся на четырнадцатый этаж за две минуты "
        "тридцать пять секунд.",
        id="ordinal_and_floor",
        marks=pytest.mark.xfail(
            strict=True,
            reason="an ordinal expanded at the start of a sentence is not capitalized",
        ),
    ),
    pytest.param(
        "Команда выиграла 3:2, забив 2 из 5 пенальти в 1/4 финала.",
        "Команда выиграла три — два, забив два из пяти пенальти в одну четвёртую финала.",
        id="score_and_fraction",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a sports score keeps punctuation and the counted masculine penalty gives the numeral feminine gender",
        ),
    ),
    pytest.param(
        "Курс вырос с 89,40 ₽ до 91,05 ₽ за 1 USD.",
        "Курс вырос с восьмидесяти девяти рублей сорока копеек до девяноста одного рубля "
        "пяти копеек за один доллар.",
        id="currency_exchange",
        marks=pytest.mark.xfail(
            strict=True,
            reason="decimal currency amounts are read as abstract fractions instead of major and minor units",
        ),
    ),
    pytest.param(
        "Отпуск запланирован с 28.02.2024 по 03.03.2024.",
        "Отпуск запланирован с двадцать восьмого февраля две тысячи двадцать четвёртого "
        "года по третье марта две тысячи двадцать четвёртого года.",
        id="date_range",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the upper date after 'по' is rendered in genitive instead of accusative",
        ),
    ),
    pytest.param(
        "Приём ведётся с 08:45 до 17:15 без перерыва.",
        "Приём ведётся с восьми часов сорока пяти минут до семнадцати часов пятнадцати "
        "минут без перерыва.",
        id="time_range",
        marks=pytest.mark.xfail(
            strict=True,
            reason="times in a governed range stay nominative and omit hour and minute units",
        ),
    ),
    pytest.param(
        "Добавьте 2/3 стакана молока и 1/4 ч. л. соли.",
        "Добавьте две трети стакана молока и одну четвёртую чайной ложки соли.",
        id="recipe_fraction",
        marks=pytest.mark.xfail(
            strict=True,
            reason="recipe fractions use wrong forms and the teaspoon abbreviation is not expanded",
        ),
    ),
    pytest.param(
        "Автомобиль разогнался со 100 до 120 км/ч за 8,4 с.",
        "Автомобиль разогнался со ста до ста двадцати километров в час за восемь целых "
        "четыре десятых секунды.",
        id="speed_and_duration",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the fractional part of a decimal duration incorrectly inherits genitive case",
        ),
    ),
    pytest.param(
        "Давление поднялось с 120/80 до 140/90 мм рт. ст.",
        "Давление поднялось со ста двадцати на восемьдесят до ста сорока на девяносто "
        "миллиметров ртутного столба.",
        id="blood_pressure",
        marks=pytest.mark.xfail(
            strict=True,
            reason="blood-pressure pairs are parsed as fractions and their unit stays abbreviated",
        ),
    ),
    pytest.param(
        "В бак объёмом 1,5 м³ залили 750 л воды.",
        "В бак объёмом одна целая пять десятых кубического метра залили семьсот пятьдесят "
        "литров воды.",
        id="volume_and_litres",
        marks=pytest.mark.xfail(
            strict=True,
            reason="superscript cubic units and the standalone litre symbol are not expanded",
        ),
    ),
    pytest.param(
        "Лампа мощностью 9 Вт потребляет 0,075 кВт·ч за 8 ч.",
        "Лампа мощностью девять ватт потребляет ноль целых семьдесят пять тысячных "
        "киловатт-часа за восемь часов.",
        id="electricity_units",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the middle-dot kilowatt-hour symbol is split and left partly unexpanded",
        ),
    ),
    pytest.param(
        "Согласно п. 2 ст. 15 ФЗ № 123 заявление рассматривают 30 дней.",
        "Согласно пункту второму статьи пятнадцатой федерального закона номер сто двадцать "
        "три заявление рассматривают тридцать дней.",
        id="legal_references",
        marks=pytest.mark.xfail(
            strict=True,
            reason="legal references are split into sentences and lose case-aware abbreviation expansion",
        ),
    ),
    pytest.param(
        "Таблица приведена на стр. 12–15, а схема — на стр. 21.",
        "Таблица приведена на страницах с двенадцатой по пятнадцатую, а схема — на "
        "странице двадцать первой.",
        id="page_range",
        marks=pytest.mark.xfail(
            strict=True,
            reason="page abbreviations and their ordinal range do not agree with the preposition",
        ),
    ),
    pytest.param(
        "Офис находится на 2-м этаже дома № 7Б по ул. Лесной.",
        "Офис находится на втором этаже дома номер семь бэ по улице Лесной.",
        id="postal_address",
        marks=pytest.mark.xfail(
            strict=True,
            reason="an alphanumeric house suffix is lost and the street abbreviation gets wrong case",
        ),
    ),
    pytest.param(
        "Концентрат смешивают с водой в пропорции 1:4.",
        "Концентрат смешивают с водой в пропорции один к четырём.",
        id="mixing_ratio",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a mixing ratio is treated as punctuation instead of an 'X к Y' construction",
        ),
    ),
    pytest.param(
        "Доходность изменилась с +2,5% до −1,75% за месяц.",
        "Доходность изменилась с плюс двух целых пяти десятых процента до минус одной "
        "целой семидесяти пяти сотых процента за месяц.",
        id="signed_percentages",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a unary plus before a percentage remains a raw symbol",
        ),
    ),
    pytest.param(
        "В 1-м и 2-м кварталах продажи выросли на 7%, а в 3-м снизились на 2%.",
        "В первом и втором кварталах продажи выросли на семь процентов, а в третьем "
        "снизились на два процента.",
        id="quarter_ordinals",
        marks=pytest.mark.xfail(
            strict=True,
            reason="coordinated suffixed ordinals disagree in number and case with quarters",
        ),
    ),
    pytest.param(
        "В конце XIX — начале XX вв. город насчитывал около 50 тыс. жителей.",
        "В конце девятнадцатого — начале двадцатого веков город насчитывал около "
        "пятидесяти тысяч жителей.",
        id="century_range",
        marks=pytest.mark.xfail(
            strict=True,
            reason="Roman century endpoints receive inconsistent and incorrect morphology",
        ),
    ),
    pytest.param(
        "Точка имеет координаты 55°45′ с. ш. и 37°37′ в. д.",
        "Точка имеет координаты пятьдесят пять градусов сорок пять минут северной широты "
        "и тридцать семь градусов тридцать семь минут восточной долготы.",
        id="geographic_coordinates",
        marks=pytest.mark.xfail(
            strict=True,
            reason="coordinate minutes and dotted direction abbreviations remain unexpanded",
        ),
    ),
    pytest.param(
        "Аккумулятор ёмкостью 5 000 мА·ч заряжается током 2 А за 2,5 ч.",
        "Аккумулятор ёмкостью пять тысяч миллиампер-часов заряжается током два ампера за "
        "две целых пять десятых часа.",
        id="battery_capacity",
        marks=pytest.mark.xfail(
            strict=True,
            reason="battery and current units stay partial and decimal duration gets the wrong case",
        ),
    ),
    pytest.param(
        "Введите 0,25 мл раствора со скоростью 2 мл/мин.",
        "Введите ноль целых двадцать пять сотых миллилитра раствора со скоростью двух "
        "миллилитров в минуту.",
        id="injection_dosage",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the per-minute denominator in a dosage rate remains abbreviated",
        ),
    ),
    pytest.param(
        "Концентрация вещества составляет 1 × 10⁻³ моль/л.",
        "Концентрация вещества составляет один умножить на десять в минус третьей степени "
        "моль на литр.",
        id="scientific_concentration",
        marks=pytest.mark.xfail(
            strict=True,
            reason="superscript negative powers and molar concentration units stay as symbols",
        ),
    ),
    pytest.param(
        "Билет стоил 49,99 €, включая сбор 2,50 €.",
        "Билет стоил сорок девять евро девяносто девять центов, включая сбор два евро "
        "пятьдесят центов.",
        id="euro_and_cents",
        marks=pytest.mark.xfail(
            strict=True,
            reason="decimal euro amounts are read as abstract fractions instead of euros and cents",
        ),
    ),
    pytest.param(
        "Счёт выставили на 1 250,50 $, а аванс составил 300 $.",
        "Счёт выставили на одну тысячу двести пятьдесят долларов пятьдесят центов, а "
        "аванс составил триста долларов.",
        id="dollars_and_cents",
        marks=pytest.mark.xfail(
            strict=True,
            reason="a grouped decimal dollar amount is misparsed and never split into cents",
        ),
    ),
    pytest.param(
        "Процессор работает на частоте 3,2 ГГц при напряжении 1,15 В.",
        "Процессор работает на частоте трёх целых двух десятых гигагерца при напряжении "
        "одной целой пятнадцати сотых вольта.",
        id="processor_frequency",
        marks=pytest.mark.xfail(
            strict=True,
            reason="decimal fraction parts disagree in case and the volt symbol stays unexpanded",
        ),
    ),
    pytest.param(
        "Монитор 27″ имеет разрешение 2560 × 1440 пикселей и частоту 144 Гц.",
        "Монитор двадцать семь дюймов имеет разрешение две тысячи пятьсот шестьдесят на "
        "одну тысячу четыреста сорок пикселей и частоту сто сорок четыре герца.",
        id="display_resolution",
        marks=pytest.mark.xfail(
            strict=True,
            reason="inch marks stay raw and screen dimensions are treated as multiplication with wrong cases",
        ),
    ),
    pytest.param(
        "Препарат назначают по 5 мг/кг массы тела 2 раза в сутки.",
        "Препарат назначают по пять миллиграммов на килограмм массы тела два раза в сутки.",
        id="weight_based_dosage",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the denominator of a weight-based dosage loses the spoken 'на килограмм'",
        ),
    ),
    pytest.param(
        "Раствор H₂SO₄ концентрацией 5% хранили при 20 °C.",
        "Раствор аш два эс о четыре концентрацией пять процентов хранили при двадцати "
        "градусах Цельсия.",
        id="chemical_formula",
        marks=pytest.mark.xfail(
            strict=True,
            reason="chemical formula letters use English pronunciation and subscripts corrupt morphology",
        ),
    ),
    pytest.param(
        "В учебнике формула E = mc² приведена в главе III.",
        "В учебнике формула е равно эм цэ в квадрате приведена в главе третьей.",
        id="physics_formula",
        marks=pytest.mark.xfail(
            strict=True,
            reason="formula symbols are merged and a squared term is read as a cardinal two",
        ),
    ),
    pytest.param(
        "Сервис доступен по адресу 192.168.1.10:8080 в локальной сети.",
        "Сервис доступен по адресу сто девяносто два точка сто шестьдесят восемь точка "
        "один точка десять двоеточие восемь тысяч восемьдесят в локальной сети.",
        id="ip_address_and_port",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the colon before a network port remains a raw punctuation symbol",
        ),
    ),
    pytest.param(
        "Рейс SU 213 вылетает из терминала B в 23:40.",
        "Рейс эс ю двести тринадцать вылетает из терминала би в двадцать три, сорок.",
        id="flight_number",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the final letter of the Latin airline code is duplicated",
        ),
    ),
    pytest.param(
        "Пассажиру назначено место 12А, выход № 7C.",
        "Пассажиру назначено место двенадцать а, выход номер семь си.",
        id="seat_and_gate",
        marks=pytest.mark.xfail(
            strict=True,
            reason="seat suffixes are lost and a Latin gate suffix is mistaken for a physical unit",
        ),
    ),
    pytest.param(
        "Срок действия сертификата истекает 2025-12-31.",
        "Срок действия сертификата истекает тридцать первого декабря две тысячи двадцать "
        "пятого года.",
        id="iso_date",
        marks=pytest.mark.xfail(
            strict=True,
            reason="an ISO calendar date is rendered as three cardinal numbers",
        ),
    ),
    pytest.param(
        "Трансляция начнётся в 14:00 UTC+3 и закончится в 16:30.",
        "Трансляция начнётся в четырнадцать, ноль ноль ю ти си плюс три и закончится в "
        "шестнадцать, тридцать.",
        id="utc_offset",
        marks=pytest.mark.xfail(
            strict=True,
            reason="UTC duplicates a letter and its positive offset keeps a raw plus symbol",
        ),
    ),
    pytest.param(
        "Программа рассчитана на детей 6–12 лет и включает 24 занятия.",
        "Программа рассчитана на детей от шести до двенадцати лет и включает двадцать "
        "четыре занятия.",
        id="children_age_range",
        marks=pytest.mark.xfail(
            strict=True,
            reason="an exact age interval is read as two nominatives instead of an 'от/до' range",
        ),
    ),
    pytest.param(
        "Подробные требования приведены в § 4.2 и § 4.3 документа.",
        "Подробные требования приведены в параграфах четыре точка два и четыре точка три "
        "документа.",
        id="section_reference",
        marks=pytest.mark.xfail(
            strict=True,
            reason="section signs stay raw and hierarchical numbers are treated as decimal fractions",
        ),
    ),
    pytest.param(
        "Ставка выросла на 0,25 п. п. до 16% годовых.",
        "Ставка выросла на ноль целых двадцать пять сотых процентного пункта до шестнадцати "
        "процентов годовых.",
        id="percentage_points",
        marks=pytest.mark.xfail(
            strict=True,
            reason="the dotted percentage-point abbreviation is stripped to two bare letters",
        ),
    ),
    pytest.param(
        "Отчёт подписан 5 янв. 2026 г. и зарегистрирован под № 18.",
        "Отчёт подписан пятого января две тысячи двадцать шестого года и зарегистрирован под номером восемнадцать.",
        id="abbreviated_calendar_date",
        marks=pytest.mark.xfail(
            strict=True, reason="an abbreviated month is not recognized as part of a date"
        ),
    ),
    pytest.param(
        "Приём заявок закончится 05.09 в 23:59.",
        "Приём заявок закончится пятого сентября в двадцать три, пятьдесят девять.",
        id="date_without_year",
        marks=pytest.mark.xfail(
            strict=True, reason="a day-month date without a year is treated as a decimal"
        ),
    ),
    pytest.param(
        "Победитель преодолел дистанцию за 01:42:35, опередив соперника на 12,4 с.",
        "Победитель преодолел дистанцию за один час сорок две минуты тридцать пять секунд, опередив соперника на двенадцать целых четыре десятых секунды.",
        id="record_duration",
        marks=pytest.mark.xfail(
            strict=True, reason="duration components and decimal seconds receive wrong morphology"
        ),
    ),
    pytest.param(
        "Концентрация препарата составляет 25 мкг/мл при дозе 0,5 мл.",
        "Концентрация препарата составляет двадцать пять микрограммов на миллилитр при дозе ноль целых пять десятых миллилитра.",
        id="microgram_concentration",
        marks=pytest.mark.xfail(
            strict=True, reason="microgram and decimal dosage forms use incorrect morphology"
        ),
    ),
    pytest.param(
        "Лазер работает на длине волны 532 нм, толщина покрытия — 2,5 мкм.",
        "Лазер работает на длине волны пятьсот тридцать два нанометра, толщина покрытия — две целых пять десятых микрометра.",
        id="wavelength_and_thickness",
        marks=pytest.mark.xfail(strict=True, reason="the micrometre symbol is left unexpanded"),
    ),
    pytest.param(
        "План напечатан в масштабе 1:50 000 и охватывает площадь 12 км².",
        "План напечатан в масштабе один к пятидесяти тысячам и охватывает площадь двенадцать квадратных километров.",
        id="map_scale",
        marks=pytest.mark.xfail(
            strict=True, reason="a map scale is treated as punctuation instead of an X-to-Y ratio"
        ),
    ),
    pytest.param(
        "Условие выполняется при x ≥ 5 и x < 10.",
        "Условие выполняется при икс больше или равно пяти и икс меньше десяти.",
        id="mathematical_inequality",
        marks=pytest.mark.xfail(
            strict=True,
            reason="variables, comparison signs, and governed bounds are not normalized consistently",
        ),
    ),
    pytest.param(
        "Угол поворота равен 45°30′15″, допустимое отклонение — ±5″.",
        "Угол поворота равен сорока пяти градусам тридцати минутам пятнадцати секундам, допустимое отклонение — плюс-минус пять секунд.",
        id="angle_degrees_minutes_seconds",
        marks=pytest.mark.xfail(
            strict=True,
            reason="angular minutes and seconds remain symbols and the angle ignores instrumental case",
        ),
    ),
    pytest.param(
        "Кадр снят при ISO 100, f/1.8 и выдержке 1/250 с.",
        "Кадр снят при ай эс о сто, эф один и восемь и выдержке одна двухсот пятидесятая секунды.",
        id="camera_settings",
        marks=pytest.mark.xfail(
            strict=True,
            reason="camera aperture and shutter-speed notation is parsed as generic fractions",
        ),
    ),
    pytest.param(
        "Курьер прибудет по адресу: ул. Полевая, д. 10, корп. 2, кв. 35.",
        "Курьер прибудет по адресу: улица Полевая, дом десять, корпус два, квартира тридцать пять.",
        id="apartment_address",
        marks=pytest.mark.xfail(
            strict=True, reason="common postal address abbreviations remain unexpanded"
        ),
    ),
    pytest.param(
        "Ответственность предусмотрена ч. 1 ст. 20.1 КоАП РФ.",
        "Ответственность предусмотрена частью первой статьи двадцать точка один Кодекса Российской Федерации об административных правонарушениях.",
        id="administrative_law_reference",
        marks=pytest.mark.xfail(
            strict=True, reason="administrative-law references are split and treated as decimals"
        ),
    ),
    pytest.param(
        "Книга выпущена под ISBN 978-5-17-123456-7 тиражом 3 000 экз.",
        "Книга выпущена под ай эс би эн девятьсот семьдесят восемь — пять — семнадцать — сто двадцать три тысячи четыреста пятьдесят шесть — семь тиражом три тысячи экземпляров.",
        id="isbn_identifier",
        marks=pytest.mark.xfail(
            strict=True, reason="the copies abbreviation remains unexpanded after an ISBN"
        ),
    ),
    pytest.param(
        "Автомобиль с номером В123МС 77 проехал 250 км.",
        "Автомобиль с номером вэ сто двадцать три эм эс семьдесят семь проехал двести пятьдесят километров.",
        id="vehicle_registration_plate",
        marks=pytest.mark.xfail(
            strict=True,
            reason="Cyrillic letters in a vehicle registration plate are not consistently verbalized",
        ),
    ),
    pytest.param(
        "Напишите пользователю @support_team и укажите номер заявки № 42.",
        "Напишите пользователю собака саппорт подчёркивание тим и укажите номер заявки номер сорок два.",
        id="social_media_handle",
        marks=pytest.mark.xfail(
            strict=True, reason="at-sign and underscore in a social handle remain unspoken"
        ),
    ),
    pytest.param(
        "Публикация с тегом #Наука2025 набрала 1,2 млн просмотров.",
        "Публикация с тегом решётка наука две тысячи двадцать пять набрала одну целую две десятых миллиона просмотров.",
        id="hashtag_and_views",
        marks=pytest.mark.xfail(
            strict=True, reason="hashtag marker remains raw and the view count gets wrong case"
        ),
    ),
    pytest.param(
        "Духовку разогрели до 350 °F, что примерно равно 177 °C.",
        "Духовку разогрели до трёхсот пятидесяти градусов Фаренгейта, что примерно равно ста семидесяти семи градусам Цельсия.",
        id="fahrenheit_temperature",
        marks=pytest.mark.xfail(
            strict=True, reason="the comparison predicate does not govern the Celsius quantity"
        ),
    ),
    pytest.param(
        "Заказ стоил 19,95 £, а доставка — 4 £.",
        "Заказ стоил девятнадцать фунтов девяносто пять пенсов, а доставка — четыре фунта.",
        id="pounds_and_pence",
        marks=pytest.mark.xfail(
            strict=True, reason="decimal sterling is not split into pounds and pence"
        ),
    ),
)


@pytest.mark.parametrize(("source", "expected"), E2E_KNOWN_GAP_CASES)
def test_tts_e2e_normalization_known_gaps(source: str, expected: str) -> None:
    assert normalize(source, NormalizeOptions.tts()) == expected


if __name__ == "__main__":
    unittest.main()
