"""Executable inventory of agreed defects not fixed yet.

Every entry is a natural full-message regression marked
``pytest.mark.xfail(strict=True)``. When a defect is fixed, its assertion moves
to the closest focused regular suite in the same commit.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

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
        reason="the -ми suffix forces the instrumental case after a locative "
        "preposition",
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
        self.assertEqual(
            normalize("Вижу 2 человека у входа."), "Вижу двух человек у входа."
        )

    @pytest.mark.xfail(
        strict=True,
        reason="the numerals stage deletes a comma that follows any dot, so an "
        "abbreviation dot swallows the list separator after it",
    )
    def test_comma_after_an_abbreviation_dot_survives_the_numerals_stage(self):
        # Nothing here needs normalizing, so the sentence must come back intact.
        # Today the comma after "Б." is dropped, and finalize then reads the dot
        # as a sentence end and capitalises the "и".
        text = "В комиссию вошли Иванов А. Б., Петров В. Г. и Сидоров."
        self.assertEqual(normalize(text), text)

    @pytest.mark.xfail(
        strict=True,
        reason="the pause comma after initials is emitted even when punctuation "
        "already follows, giving \",;\", \",:\" and \", —\"",
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
        reason="the numerals stage deletes a comma that follows any dot, so a "
        "clause boundary after initials turns into a sentence boundary",
    )
    def test_clause_after_initials_does_not_become_a_new_sentence(self):
        self.assertEqual(
            normalize("Работу приняли Иванов А. Б., затем подписал Петров."),
            "Работу приняли Иванов А. Б., затем подписал Петров.",
        )

    @pytest.mark.xfail(
        strict=True,
        reason="the dot of an expanded unit abbreviation is left in place and "
        "then eats the comma after it",
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
        reason="the compound-adjective stems \"часов\" and \"тонн\" coincide with "
        "genitive plural nouns, and the pattern allows an empty adjective "
        "ending, so a counted noun is glued onto the numeral",
    )
    def test_counted_hours_and_tonnes_are_not_glued_onto_the_numeral(self):
        # COMPOUND_ADJECTIVE_PATTERN ends in "[а-яё]*", so "часов" and "тонн"
        # match with nothing after them — exactly the noun forms. Every other
        # stem ends in a cluster no noun form starts with, which is why only
        # these two break.
        self.assertEqual(normalize("Он ждал 7 часов."), "Он ждал семь часов.")
        self.assertEqual(normalize("Груз весит 5 тонн."), "Груз весит пять тонн.")
        self.assertEqual(
            normalize("Смена в 8 часов начинается."), "Смена в восемь часов начинается."
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
            "Между тысяча девятьсот девяносто девятым и двухтысячным годами "
            "разница велика.",
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
        reason="above 1000 simple rules each key gets its own pass, so rules "
        "cascade into each other instead of applying once",
    )
    def test_dictionary_rules_apply_once_regardless_of_dictionary_size(self):
        # Up to 1000 simple rules one alternation replaces every key in a single
        # pass. Past that threshold each key runs as its own substitution, so a
        # rule can rewrite what an earlier rule just produced — the same two
        # rules then give a different answer purely because the file grew.
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            filler = "".join(f"наполнитель{index}=пусто{index}\n" for index in range(1200))
            (root / "brands.dic").write_text(
                filler + "youtube=ютуб\nютуб=видеосервис\n", encoding="utf-8"
            )
            options = NormalizeOptions(
                dictionaries_path=root, enable_latinization=False
            )

            self.assertEqual(
                normalize("Смотри youtube и ютуб каждый вечер.", options),
                "Смотри ютуб и видеосервис каждый вечер.",
            )

    @pytest.mark.xfail(
        strict=True,
        reason="exactly 1000 simple rules already switch to the cascading path",
    )
    def test_dictionary_threshold_is_not_semantic_at_exactly_one_thousand_rules(self):
        filler = "".join(
            f"наполнитель{index}=пусто{index}\n" for index in range(998)
        )
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "brands.dic").write_text(
                filler + "youtube=ютуб\nютуб=видеосервис\n", encoding="utf-8"
            )
            options = NormalizeOptions(
                dictionaries_path=root, enable_latinization=False
            )

            self.assertEqual(
                normalize("Смотри youtube и ютуб каждый вечер.", options),
                "Смотри ютуб и видеосервис каждый вечер.",
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
)


@pytest.mark.parametrize(("source", "expected"), E2E_KNOWN_GAP_CASES)
def test_tts_e2e_normalization_known_gaps(source: str, expected: str) -> None:
    assert normalize(source, NormalizeOptions.tts()) == expected


if __name__ == "__main__":
    unittest.main()
