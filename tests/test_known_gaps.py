"""Known defects that are pinned rather than fixed.

Every test here asserts the output we *want* and is marked
``pytest.mark.xfail(strict=True)``. Strict matters: when the underlying defect
is fixed the test starts passing, pytest reports XPASS and the run **fails**,
which is the reminder to drop the marker and move the test into the regular
suite. A prose note in ``docs/`` cannot do that — it goes stale silently.

Only put a defect here when the correct output is agreed. An open design
question ("should `10-5` read as subtraction?") has nothing to assert and
belongs in a GitHub issue instead.
"""

import unittest

import pytest

from ru_normalizr import NormalizeOptions, normalize


@pytest.mark.xfail(
    strict=True,
    reason="common-gender nouns discard an explicit feminine ordinal suffix",
)
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "На конференции выступила 2-я коллега из Казани.",
            "На конференции выступила вторая коллега из Казани.",
        ),
        (
            "После аварии 2-я сирота осталась без опекуна.",
            "После аварии вторая сирота осталась без опекуна.",
        ),
    ],
)
def test_feminine_ordinal_suffix_wins_for_common_gender_nouns(source, expected):
    assert normalize(source) == expected


@pytest.mark.xfail(
    strict=True,
    reason="the currency unit picks the masculine personal-name parse of лира",
)
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "Билет на автобус стоит 1 ₺ за поездку.",
            "Билет на автобус стоит одну лиру за поездку.",
        ),
        (
            "Два билета стоят 2 ₺ за поездку.",
            "Два билета стоят две лиры за поездку.",
        ),
        (
            "Пять билетов стоят 5 ₺ за поездку.",
            "Пять билетов стоят пять лир за поездку.",
        ),
    ],
)
def test_turkish_lira_uses_the_inanimate_feminine_lemma(source, expected):
    assert normalize(source) == expected


@pytest.mark.xfail(
    strict=True,
    reason="domain units inherit animate person-name parses in singular accusative",
)
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Давление увеличили на 1 Па.", "Давление увеличили на один паскаль."),
        (
            "Магнитный поток увеличили на 1 Вб.",
            "Магнитный поток увеличили на один вебер.",
        ),
        (
            "Эквивалентную дозу увеличили на 1 Зв.",
            "Эквивалентную дозу увеличили на один зиверт.",
        ),
    ],
)
def test_measurement_units_remain_inanimate_in_the_accusative(source, expected):
    assert normalize(source) == expected


@pytest.mark.xfail(
    strict=True,
    reason="case-folding conflates milli- and mega-prefixed SI symbols",
)
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "Датчик в режиме ожидания потребляет 5 mW.",
            "Датчик в режиме ожидания потребляет пять милливатт.",
        ),
        (
            "Лазер развивает мощность 5 мВт.",
            "Лазер развивает мощность пять милливатт.",
        ),
        (
            "Источник выдаёт напряжение 5 MV.",
            "Источник выдаёт напряжение пять мегавольт.",
        ),
    ],
)
def test_si_prefix_case_does_not_change_the_measurement_scale(source, expected):
    assert normalize(source) == expected


@pytest.mark.xfail(
    strict=True,
    reason="the unit metadata assigns the amount-of-substance моль a feminine gender",
)
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "Количество вещества в образце — 1 mol.",
            "Количество вещества в образце — один моль.",
        ),
        (
            "В растворе содержится 2 mol вещества.",
            "В растворе содержится два моля вещества.",
        ),
    ],
)
def test_mole_unit_uses_the_masculine_measurement_lexeme(source, expected):
    assert normalize(source) == expected


@pytest.mark.xfail(
    strict=True,
    reason="the packaged dictionary analyzes тесла only as a form of тесло",
)
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "Измеренная магнитная индукция — 1 Тл.",
            "Измеренная магнитная индукция — одна тесла.",
        ),
        (
            "Измеренная магнитная индукция — 2 Тл.",
            "Измеренная магнитная индукция — две теслы.",
        ),
        (
            "Измеренная магнитная индукция — 5 Тл.",
            "Измеренная магнитная индукция — пять тесл.",
        ),
    ],
)
def test_tesla_uses_the_magnetic_induction_unit_lexeme(source, expected):
    assert normalize(source) == expected


@pytest.mark.xfail(
    strict=True,
    reason="the Korean won metadata uses masculine agreement for a feminine currency",
)
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Цена билета в Сеуле — 1 ₩.", "Цена билета в Сеуле — одна вона."),
        (
            "Цена двух билетов в Сеуле — 2 ₩.",
            "Цена двух билетов в Сеуле — две воны.",
        ),
    ],
)
def test_korean_won_uses_feminine_numeral_agreement(source, expected):
    assert normalize(source) == expected


@pytest.mark.xfail(
    strict=True,
    reason="the dictionary treats indeclinable тенге as a form of тенг",
)
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Стоимость услуги — 1 ₸.", "Стоимость услуги — один тенге."),
        ("Стоимость двух услуг — 2 ₸.", "Стоимость двух услуг — два тенге."),
        ("Стоимость пяти услуг — 5 ₸.", "Стоимость пяти услуг — пять тенге."),
        ("Стоимость услуги — 1 тенге.", "Стоимость услуги — один тенге."),
    ],
)
def test_tenge_remains_indeclinable_for_symbol_and_written_unit(source, expected):
    assert normalize(source) == expected


@pytest.mark.xfail(
    strict=True,
    reason="the dictionary resolves фарад as the genitive plural of фарада",
)
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Номинальная ёмкость — 1 Ф.", "Номинальная ёмкость — один фарад."),
        ("Номинальная ёмкость — 2 Ф.", "Номинальная ёмкость — два фарада."),
        ("Номинальная ёмкость — 1 мФ.", "Номинальная ёмкость — один миллифарад."),
    ],
)
def test_farad_uses_the_capacitance_unit_lexeme(source, expected):
    assert normalize(source) == expected


@pytest.mark.xfail(
    strict=True,
    reason="stripping the dot makes dotted-only unit aliases unreachable",
)
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("Измеренный угол составляет 2 рад.", "Измеренный угол составляет два радиана."),
        (
            "Строительство крепости продолжалось 2 в.",
            "Строительство крепости продолжалось два века.",
        ),
        (
            "Ставка выросла на 5 п.п. за месяц.",
            "Ставка выросла на пять процентных пунктов за месяц.",
        ),
        (
            "Доходность выросла на 5 б.п. за день.",
            "Доходность выросла на пять базисных пунктов за день.",
        ),
        (
            "Мощность двигателя составляет 5 л. с.",
            "Мощность двигателя составляет пять лошадиных сил.",
        ),
    ],
)
def test_dotted_only_unit_aliases_are_expanded(source, expected):
    assert normalize(source) == expected


@pytest.mark.xfail(
    strict=True,
    reason="an adjective-noun homonym is mistaken for the phrase head",
)
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "Порядок гос. часовой службы определён уставом.",
            "Порядок государственной часовой службы определён уставом.",
        ),
        (
            "На циферблате отметили положение офиц. часовой стрелки.",
            "На циферблате отметили положение официальной часовой стрелки.",
        ),
    ],
)
def test_abbreviation_agrees_with_the_head_of_an_ambiguous_noun_phrase(
    source, expected
):
    assert normalize(source) == expected


@pytest.mark.xfail(
    strict=True,
    reason="fraction numerators are inflected token by token using ambiguous first parses",
)
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            "Расчёт выполнен без 100/100 общей выборки.",
            "Расчёт выполнен без ста сотых общей выборки.",
        ),
        (
            "Расчёт выполнен без 2000/10000 общей выборки.",
            "Расчёт выполнен без двух тысяч десятитысячных общей выборки.",
        ),
    ],
)
def test_large_fraction_numerators_inflect_as_complete_numerals(source, expected):
    assert normalize(source) == expected


class RuNormalizrKnownGapTests(unittest.TestCase):
    @pytest.mark.xfail(
        strict=True,
        reason="plural inanimate accusative is not normalized for an ordinal",
    )
    def test_ordinal_agrees_with_a_pluralia_tantum_noun(self):
        self.assertEqual(
            normalize("Экспедиция продолжалась уже 2-е сутки без остановки."),
            "Экспедиция продолжалась уже вторые сутки без остановки.",
        )

    @pytest.mark.xfail(
        strict=True,
        reason="the packaged dictionary marks шекель as a singular-only geography",
    )
    def test_shekel_uses_a_productive_measurement_lexeme(self):
        self.assertEqual(
            normalize("Обследование обойдётся пациенту в 5 ₪."),
            "Обследование обойдётся пациенту в пять шекелей.",
        )

    @pytest.mark.xfail(
        strict=True,
        reason="the packaged dictionary marks грей as a singular-only surname",
    )
    def test_gray_unit_uses_a_productive_measurement_lexeme(self):
        self.assertEqual(
            normalize("За процедуру пациент получил дозу 5 грей."),
            "За процедуру пациент получил дозу пять греев.",
        )

    @pytest.mark.xfail(
        strict=True,
        reason="the case-insensitive resolver mistakes the Cyrillic gray symbol for grams",
    )
    def test_exact_case_cyrillic_gray_symbol_is_not_read_as_grams(self):
        self.assertEqual(
            normalize("За процедуру пациент получил дозу 5 Гр."),
            "За процедуру пациент получил дозу пять греев.",
        )

    @pytest.mark.xfail(
        strict=True,
        reason="case-folding conflates bit and byte abbreviations",
    )
    def test_information_unit_symbol_case_distinguishes_bits_from_bytes(self):
        self.assertEqual(
            normalize("За один такт канал передаёт 5 Mb данных."),
            "За один такт канал передаёт пять мегабит данных.",
        )

    @pytest.mark.xfail(
        strict=True,
        reason="the plural-only сутки paradigm does not receive its genitive plural form",
    )
    def test_two_days_uses_collective_numeral_and_genitive_plural_noun(self):
        self.assertEqual(
            normalize("Экспедиция длилась 2 сут. без остановки."),
            "Экспедиция длилась двое суток без остановки.",
        )

    @pytest.mark.xfail(
        strict=True,
        reason="gen2 is not canonicalized before rendering the ordinal",
    )
    def test_ordinal_preserves_the_partitive_noun_context(self):
        self.assertEqual(
            normalize("Для 2-го чаю не хватило кипятка."),
            "Для второго чаю не хватило кипятка.",
        )

    @pytest.mark.xfail(
        strict=True,
        reason="the first parse of пасть is an infinitive despite the numeric noun context",
    )
    def test_cardinal_uses_a_noun_parse_after_a_number(self):
        self.assertEqual(
            normalize("В музее представлена 1 пасть древнего животного."),
            "В музее представлена одна пасть древнего животного.",
        )

    @pytest.mark.xfail(
        strict=True,
        reason="the first parse of достигаем is a short adjective, hiding verb governance",
    )
    def test_homonymous_verb_form_still_governs_the_numeral_case(self):
        self.assertEqual(
            normalize("К концу квартала мы достигаем 5 целей программы."),
            "К концу квартала мы достигаем пяти целей программы.",
        )

    @pytest.mark.xfail(
        strict=True,
        reason="the ordinal stage consumes a large fraction numerator in dative context",
    )
    def test_large_fraction_is_not_split_by_ordinal_normalization(self):
        self.assertEqual(
            normalize("Показатель приблизился к 1000/100 от целого."),
            "Показатель приблизился к одной тысяче сотых от целого.",
        )

    @pytest.mark.xfail(
        strict=True,
        reason="implicit-year detection checks only the first homonymous unit parse",
    )
    def test_measurement_amount_in_year_range_is_not_read_as_a_year(self):
        self.assertEqual(
            normalize("Прибор рассчитан на дозу в 2020 зивертов."),
            "Прибор рассчитан на дозу в две тысячи двадцать зивертов.",
        )

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
        reason="the month alternation has no right-hand word boundary",
    )
    def test_month_name_is_not_matched_inside_a_longer_word(self):
        # TEXT_DATE_PATTERN matches "мая" inside "маяк", so a number followed by
        # any word that merely starts with a month name is read as a date.
        self.assertEqual(normalize("15 маяк"), "пятнадцать маяк")
        self.assertEqual(normalize("20 маяков"), "двадцать маяков")

    @pytest.mark.xfail(
        strict=True,
        reason="CamelCase tokens are never split, so the acronym never reaches "
        "the abbreviation stage",
    )
    def test_acronym_inside_a_camel_case_token_is_read_letter_by_letter(self):
        # Standalone the acronyms are read correctly ("SQL" -> "эс кью эл"), but
        # ABBREV_SOLID_PATTERN requires the whole token to be upper case, so a
        # CamelCase token goes to latinization as one word and the acronym is
        # guessed at from its spelling instead ("PostgreSQL" -> "постгрэскл").
        tts = NormalizeOptions.tts()
        self.assertIn("эс кью эл", normalize("PostgreSQL", tts))
        self.assertIn("кью эл", normalize("GraphQL", tts))
        self.assertIn("ви пи эн", normalize("OpenVPN", tts))

    @pytest.mark.xfail(
        strict=True,
        reason="the -х suffix is read as a cardinal before an ordinally numbered noun",
    )
    def test_ordinal_suffix_wins_before_an_ordinally_numbered_noun(self):
        # "-х" is ambiguous: a cardinal in "в течение 2-х лет" (двух лет) and a
        # plural ordinal in "в 5-х классах" (пятых классах). Morphology cannot
        # separate them — "в 2-х шагах" and "в 5-х классах" are both locative
        # plural yet read differently — so the decision needs a class of nouns
        # that take ordinal numbering (класс, ряд, курс, разряд, тур, раунд),
        # alongside the year words the year stage already special-cases.
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
        reason="the counted noun keeps the form written beside the digit",
    )
    def test_animate_paucal_accusative_agrees_the_counted_noun(self):
        # The stage inflects the numeral into the genitive that an animate
        # accusative requires ("двух"), but leaves the noun in the form the
        # author wrote next to the digit ("человека"), so the phrase disagrees
        # with itself. Agreeing it means rewriting the following noun into the
        # genitive plural, which the stage does today only for known units.
        self.assertEqual(
            normalize("Вижу 2 человека у входа."), "Вижу двух человек у входа."
        )


if __name__ == "__main__":
    unittest.main()
