import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from ru_normalizr import NormalizeOptions, Normalizer, normalize, preprocess_text


def _find_source_root() -> Path | None:
    current = Path(__file__).resolve()
    for candidate in [current.parent, *current.parents]:
        if (candidate / "pyproject.toml").exists():
            return candidate
    return None


def _clean_build_artifacts(root: Path) -> None:
    for relative in ("build", "dist", ".tmp_dist", "ru_normalizr.egg-info"):
        target = root / relative
        if target.exists():
            shutil.rmtree(target)


class RuNormalizrApiTests(unittest.TestCase):
    def test_package_init_supports_direct_file_import(self):
        package_dir = Path(__import__("ru_normalizr").__file__).resolve().parent
        init_path = package_dir / "__init__.py"
        spec = importlib.util.spec_from_file_location("__init__", init_path)

        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        self.assertIs(module.NormalizeOptions, NormalizeOptions)
        self.assertIs(module.Normalizer, Normalizer)
        self.assertIs(module.normalize, normalize)
        self.assertIs(module.preprocess_text, preprocess_text)

    def test_normalize_function_handles_roman_and_time_pipeline(self):
        self.assertEqual(
            normalize("Глава IV. Встреча в 10:07."),
            "Глава четыре. Встреча в десять, ноль семь.",
        )

    def test_normalize_keeps_see_chapter_reference_semantics(self):
        text = "(См. главу 10.)"
        expected = "(смотри главу десятую.)"

        self.assertEqual(normalize(text), expected)
        self.assertEqual(normalize(text, NormalizeOptions.tts()), expected)

    def test_normalize_distinguishes_chapter_heading_and_inline_references(self):
        self.assertEqual(
            normalize("Глава 10. Последние слова генерала."),
            "Глава десять. Последние слова генерала.",
        )
        self.assertEqual(
            normalize("См. главу 10, где описан конфликт."),
            "смотри главу десятую, где описан конфликт.",
        )
        self.assertEqual(
            normalize("В главе 10 автор объясняет принципы эффективного плавания."),
            "В главе десятой автор объясняет принципы эффективного плавания.",
        )
        self.assertEqual(
            normalize("См. главу IV."),
            "смотри главу четвёртую.",
        )

    def test_normalize_runs_roman_before_caps_normalization(self):
        self.assertEqual(
            normalize("ГЛАВА IV.", NormalizeOptions.tts()),
            "Глава четыре.",
        )

    def test_package_root_normalizer_re_exports_pipeline_class(self):
        from ru_normalizr.pipeline import Normalizer as PipelineNormalizer

        self.assertIs(Normalizer, PipelineNormalizer)
        self.assertIsInstance(Normalizer(), PipelineNormalizer)

    def test_normalize_batch_reuses_normalizer(self):
        normalizer = Normalizer()

        self.assertEqual(
            normalizer.normalize_batch(["Глава IV.", "Встреча в 10:07."]),
            ["Глава четыре.", "Встреча в десять, ноль семь."],
        )

    def test_options_can_disable_first_word_decap(self):
        options = NormalizeOptions(
            enable_caps_normalization=False, enable_first_word_decap=False
        )

        self.assertEqual(normalize("ПРИВЕТ мир", options), "ПРИВЕТ мир")

    def test_tts_does_not_decap_single_all_caps_token(self):
        self.assertEqual(preprocess_text("СВСН", NormalizeOptions.tts()), "СВСН")

    def test_tts_does_not_spell_real_words_inside_caps_heading(self):
        self.assertEqual(
            normalize("ЛИБЕРТАРИАНСТВО ЗА ОДИН УРОК", NormalizeOptions.tts()),
            "Либертарианство за один урок",
        )

    def test_preprocess_text_is_exported(self):
        self.assertIn("10 кг", preprocess_text("10кг"))

    def test_preprocess_text_inserts_legacy_dot_before_uppercase_line(self):
        self.assertEqual(
            preprocess_text(
                "Часть два.\nПалеозой: утро\n\nКембрий пятьсот сорок один,"
            ),
            "Часть два.\nПалеозой: утро.\n\nКембрий пятьсот сорок один,",
        )

    def test_preprocess_text_does_not_insert_legacy_dot_at_start_of_text(self):
        self.assertEqual(
            preprocess_text("\nПалеозой: утро"),
            "Палеозой: утро",
        )

    def test_preprocess_text_removes_linebreak_before_lowercase_line(self):
        self.assertEqual(
            preprocess_text("Палеозой: утро\nкембрий был дальше"),
            "Палеозой: утро кембрий был дальше",
        )

    def test_preprocess_text_preserves_paragraphs_but_limits_linebreaks(self):
        self.assertEqual(
            preprocess_text("Первая строка\n\n\n\nВторая строка"),
            "Первая строка.\n\nВторая строка",
        )

    def test_preprocess_text_inserts_legacy_dot_before_uppercase_paragraph(self):
        self.assertEqual(
            preprocess_text("Metaspriggina walcotti\n\nЧего пока не хватало"),
            "Metaspriggina walcotti.\n\nЧего пока не хватало",
        )

    def test_preprocess_text_collapses_many_linebreaks_to_one(self):
        self.assertEqual(
            preprocess_text("Первая строка\n\n\n\n\n\nВторая строка"),
            "Первая строка.\n\nВторая строка",
        )

    def test_preprocess_text_preserves_paragraph_break_before_quoted_uppercase_text(self):
        self.assertEqual(
            preprocess_text(
                "Часть три.\nВишну-хранитель\n\n\n"
                "«Вишну, Хранитель мироздания, поддерживает все существующее."
            ),
            'Часть три.\nВишну-хранитель.\n\n"Вишну, Хранитель мироздания, поддерживает все существующее.',
        )

    def test_preprocess_text_preserves_letter_hyphens_inside_words(self):
        self.assertEqual(
            preprocess_text("Планета-печка и Великая Революция"),
            "Планета-печка и Великая Революция",
        )

    def test_preprocess_text_normalizes_leading_caps_heading_phrase(self):
        self.assertEqual(
            preprocess_text(
                "АВТОМОБИЛЬ ДЖИП («ВИЛЛИС»), легкий полноприводной вездеход."
            , NormalizeOptions.tts()),
            'Автомобиль джип ("виллис"), легкий полноприводной вездеход.',
        )

    def test_preprocess_text_normalizes_caps_heading_with_short_preposition(self):
        self.assertEqual(
            preprocess_text(
                "АВТОМОБИЛЬ С КОМПЬЮТЕРНЫМ УПРАВЛЕНИЕМ ТРАНСМИССИЕЙ, выпустила на рынок японская компания."
            , NormalizeOptions.tts()),
            "Автомобиль С Компьютерным управлением трансмиссией, выпустила на рынок японская компания.",
        )

    def test_preprocess_text_normalizes_caps_heading_with_multiple_words(self):
        self.assertEqual(
            preprocess_text(
                "АВТОРУЧКА С КЕРАМИЧЕСКИМ ПЕРОМ, выпустила на рынок японская компания."
            , NormalizeOptions.tts()),
            "Авторучка С Керамическим пером, выпустила на рынок японская компания.",
        )

    def test_preprocess_text_normalizes_caps_heading_without_parentheses(self):
        self.assertEqual(
            preprocess_text(
                "БАТАРЕЙКА ЭЛЕКТРИЧЕСКАЯ ПЛАСТМАССОВАЯ, сконструирована американскими учеными."
            , NormalizeOptions.tts()),
            "Батарейка электрическая пластмассовая, сконструирована американскими учеными.",
        )

    def test_preprocess_text_cleans_quote_ellipsis_and_sentence_spacing(self):
        self.assertEqual(
            preprocess_text(
                'Основное правило: любое объяснение лучше его отсутствия … Итак. Ницше, " Сумерки богов "'
            ),
            'Основное правило: любое объяснение лучше его отсутствия… Итак. Ницше, "Сумерки богов"',
        )

    def test_preprocess_text_inserts_space_after_closing_quote_before_word(self):
        self.assertEqual(
            preprocess_text('просто не могли не «подобрать» одну из самых древних'),
            'просто не могли не "подобрать" одну из самых древних',
        )

    def test_preprocess_text_keeps_separate_quote_pairs_around_sentences(self):
        self.assertEqual(
            preprocess_text(
                'Когда настал назначенный день, многие провожали его к берегу реки, войдя в которую, он сказал: '
                '«Смерть, где твое жало?» И когда он погрузился глубже, то продолжал: '
                '«Ад, где твоя победа?» (I Коринф. 15: 55).'
            ),
            'Когда настал назначенный день, многие провожали его к берегу реки, войдя в которую, он сказал: '
            '"Смерть, где твое жало?" И когда он погрузился глубже, то продолжал: '
            '"Ад, где твоя победа?" (I Коринф. 15: 55).',
        )

    def test_normalize_matches_preprocess_when_later_stages_are_disabled(self):
        options = NormalizeOptions(
            enable_year_normalization=False,
            enable_dates_time_normalization=False,
            enable_numeral_normalization=False,
            enable_abbreviation_expansion=False,
            enable_dictionary_normalization=False,
            enable_latinization=False,
        )
        text = (
            'Основное правило: любое объяснение лучше его отсутствия … Итак. Ницше, " Сумерки богов "'
        )

        self.assertEqual(normalize(text, options), preprocess_text(text, options))

    def test_decimal_normalization_now_respects_enable_numeral_normalization(self):
        options = NormalizeOptions(enable_numeral_normalization=False)
        self.assertEqual(normalize("3,6", options), "3,6")
        self.assertEqual(normalize("(3,6)", options), "(3,6)")

    def test_all_disabled_options_keep_bracketed_integer_unchanged(self):
        options = NormalizeOptions(
            enable_year_normalization=False,
            enable_dates_time_normalization=False,
            enable_numeral_normalization=False,
            enable_abbreviation_expansion=False,
            enable_dictionary_normalization=False,
            enable_latinization=False,
        )
        self.assertEqual(normalize("(2)", options), "(2)")
        self.assertEqual(preprocess_text("(2)", options), "(2)")

    def test_preprocess_text_inserts_legacy_dot_before_digit_line_and_expands_years_ago(
        self,
    ):
        self.assertEqual(
            preprocess_text("МЕЖДУНАРОДНАЯ ШКАЛА\n541 млн л. н.", NormalizeOptions.tts()),
            "Международная шкала.\n541 млн лет назад.",
        )

    def test_normalize_preserves_letter_hyphens_inside_words(self):
        self.assertEqual(
            normalize("Планета-печка и Великая Революция"),
            "Планета-печка и Великая Революция",
        )

    def test_normalize_expands_years_ago_before_unit_normalization(self):
        self.assertEqual(
            normalize("МЕЖДУНАРОДНАЯ ШКАЛА\n541 млн л. н.", NormalizeOptions.tts()),
            "Международная шкала. Пятьсот сорок один миллион лет назад.",
        )

    def test_normalize_expands_years_ago_before_following_sentence(self):
        self.assertEqual(
            normalize(
                "Катийский век и катийская гляциоэпоха начались как минимум из трех "
                "оледенений 453 млн л. н. Ледники покрыли Центральную Африку и Бразилию."
            ),
            "Катийский век и катийская гляциоэпоха начались как минимум из трех "
            "оледенений четыреста пятьдесят три миллиона лет назад. "
            "Ледники покрыли Центральную Африку и Бразилию.",
        )

    def test_normalize_expands_years_ago_with_surrounding_dashes(self):
        self.assertEqual(
            normalize("Из лохковского века Шотландии – 410 – 414 млн л. н. –"),
            "Из лохковского века Шотландии — четыреста десять — четыреста четырнадцать миллионов лет назад —",
        )

    def test_normalize_preserves_paragraph_breaks_during_full_pipeline(self):
        self.assertEqual(
            normalize("Глава IV.\n\nВстреча в 10:07."),
            "Глава четыре.\n\nВстреча в десять, ноль семь.",
        )

    def test_normalize_preserves_paragraph_break_before_quoted_uppercase_text(self):
        self.assertEqual(
            normalize(
                "Часть три.\nВишну-хранитель\n\n\n"
                "«Вишну, Хранитель мироздания, поддерживает все существующее."
            ),
            'Часть три.\nВишну-хранитель.\n\n"Вишну, Хранитель мироздания, поддерживает все существующее.',
        )

    def test_normalize_keeps_sentence_boundary_after_etc_abbreviation(self):
        self.assertEqual(
            normalize("миротворцы и т. д. Эти шумы остались."),
            "миротворцы и так далее. Эти шумы остались.",
        )

    def test_normalize_capitalizes_sentence_start_after_numeric_expansion(self):
        self.assertEqual(
            normalize(
                ". 90 серий этих суперрусских правдюков дают материал для 180 увлекательнейших статей."
            ),
            ". Девяносто серий этих суперрусских правдюков дают материал для сто восьмидесяти увлекательнейших статей.",
        )

    def test_normalize_removes_decorative_separator_without_extra_punctuation(self):
        self.assertEqual(
            normalize(
                "первый шаг в сторону обретения челюстей.\n\n"
                "Metaspriggina walcotti\n\n\n"
                "* * *\n\n\n"
                "Чего пока не хватало кембрийским хордовым, так это чешуи и зубов. "
            ),
            "первый шаг в сторону обретения челюстей.\n\n"
            "Metaspriggina walcotti.\n\n"
            "Чего пока не хватало кембрийским хордовым, так это чешуи и зубов.",
        )

    def test_normalize_expands_years_ago_inside_ranges_and_parentheses(self):
        self.assertEqual(
            normalize(
                "Всего на несколько миллионов лет моложе, но формально уже среднекембрийского "
                "возраста одно из самых знаменитых мест – сланцы Бёрджес в Канаде с датировкой "
                "510 – 505 млн л. н. (в среднем 508 млн л.н.)."
            ),
            "Всего на несколько миллионов лет моложе, но формально уже среднекембрийского "
            "возраста одно из самых знаменитых мест — сланцы Бёрджес в Канаде с датировкой "
            "пятисот десяти — пятисот пяти миллионов лет назад (в среднем пятьсот восемь миллионов лет назад).",
        )

    def test_preprocess_tts_keeps_bracketed_years_within_ignore_interval(self):
        self.assertEqual(
            preprocess_text("Пекин (2008)", NormalizeOptions.tts()),
            "Пекин (2008)",
        )

    def test_preprocess_tts_respects_bracketed_year_ignore_interval_boundaries(self):
        options = NormalizeOptions.tts()
        self.assertEqual(preprocess_text("Рим (2200)", options), "Рим (2200)")
        self.assertEqual(preprocess_text("Рим (2201)", options), "Рим")
        self.assertEqual(preprocess_text("ссылка (12)", options), "ссылка")
        self.assertEqual(preprocess_text("диапазон (1–3)", options), "диапазон")

    def test_preprocess_text_keeps_bracketed_comma_decimals(self):
        self.assertEqual(preprocess_text("(500,5)"), "(500,5)")
        self.assertEqual(preprocess_text("(1 234,56)"), "(1234,56)")
        self.assertEqual(preprocess_text("(10,0%)"), "(10,0%)")
        self.assertEqual(preprocess_text("(500,5 кг)"), "(500,5 кг)")

    def test_preprocess_text_removes_confident_bracketed_references(self):
        options = NormalizeOptions.tts()
        self.assertEqual(preprocess_text("(1)", options), "")
        self.assertEqual(preprocess_text("(1, 3, 5)", options), "")
        self.assertEqual(preprocess_text("(1–3)", options), "")
        self.assertEqual(preprocess_text("(2.5)", options), "")
        self.assertEqual(preprocess_text("(2.5.1)", options), "")

    def test_normalize_keeps_cyrillic_measurements_out_of_roman_stage(self):
        self.assertEqual(
            normalize(
                "характерны гигантские медузоиды до 30 – 40 см в диаметре и перистовидные колонии"
            ),
            "характерны гигантские медузоиды до тридцати — сорока сантиметров в диаметре и перистовидные колонии",
        )

    def test_normalize_expands_century_abbreviation_after_roman_numeral(self):
        self.assertEqual(
            normalize("от её начала до середины XIX в. у нас был ещё один институт"),
            "от её начала до середины девятнадцатого века у нас был ещё один институт",
        )
        self.assertEqual(
            normalize("от её начала до середины XIX в у нас был ещё один институт"),
            "от её начала до середины девятнадцатого века у нас был ещё один институт",
        )

    def test_normalize_inflects_plural_year_abbreviation_in_decade_phrase(self):
        self.assertEqual(
            normalize("В начале 1960-х гг. стечение обстоятельств посеяло семена."),
            "В начале тысяча девятьсот шестидесятых годов стечение обстоятельств посеяло семена.",
        )

    def test_normalize_expands_plural_year_abbreviation_to_gody_in_nominative(self):
        self.assertEqual(
            normalize("1960-е гг. были переломными."),
            "тысяча девятьсот шестидесятые годы были переломными.",
        )

    def test_normalize_inflects_short_decade_abbreviation_with_preposition(self):
        self.assertEqual(
            normalize("В 60-х гг. многие молодые люди были не согласны."),
            "В шестидесятых годах многие молодые люди были не согласны.",
        )

    def test_normalize_treats_unary_minus_as_spoken_minus(self):
        self.assertEqual(
            normalize("при -20°C и -1 %"),
            "при минус двадцати градусах Цельсия и минус один процент",
        )

    def test_normalize_keeps_percent_subject_after_genitive_noun_phrase(self):
        self.assertEqual(
            normalize(
                'Но гокленовская статистика показала, что среди всех европейских спортивных чемпионов 22 % действительно родилось в периоды "благоприятных" положений Марса.'
            ),
            'Но гокленовская статистика показала, что среди всех европейских спортивных чемпионов двадцать два процента действительно родилось в периоды "благоприятных" положений Марса.',
        )

    def test_normalize_deduplicates_percent_word_after_percent_sign(self):
        self.assertEqual(
            normalize("90 % процентов всей информации"),
            "девяносто процентов всей информации",
        )

    def test_normalize_preserves_dash_between_words(self):
        self.assertEqual(
            normalize("слово - слово"),
            "слово — слово",
        )

    def test_normalize_preserves_numeric_range_as_non_minus(self):
        self.assertEqual(
            normalize("10 - 20"),
            "десять, двадцать",
        )

    def test_normalize_handles_negative_decimal_from_start_of_text(self):
        self.assertEqual(
            normalize("-36.6"),
            "минус тридцать шесть целых шесть десятых",
        )

    def test_normalize_does_not_keep_abbreviation_dot_after_thousands_unit(self):
        self.assertEqual(
            normalize("В результате погибли от 60 до 80 тыс. жителей города."),
            "В результате погибли от шестидесяти до восьмидесяти тысяч жителей города.",
        )

    def test_normalize_keeps_sentence_boundary_after_terminal_thousands_unit(self):
        self.assertEqual(
            normalize("В результате потери в долларах составили от 60 до 80 тыс."),
            "В результате потери в долларах составили от шестидесяти до восьмидесяти тысяч.",
        )

    def test_normalize_syncs_legacy_time_and_storage_units(self):
        self.assertEqual(
            normalize("длительность 74,33 мин. и емкость — 650 МБ."),
            "длительность семьдесят четыре целых тридцать три сотых минуты и емкость — шестьсот пятьдесят мегабайтов.",
        )

    def test_normalize_supports_ascii_square_and_cubic_units(self):
        self.assertEqual(
            normalize("площадь 10 м2, объем 3 м^3 и участок 2 км2"),
            "площадь десять квадратных метров, объем три кубических метра и участок два квадратных километра",
        )
        self.assertEqual(normalize("1 м^3"), "один кубический метр")
        self.assertEqual(normalize("2 м^3"), "два кубических метра")
        self.assertEqual(normalize("5 м^3"), "пять кубических метров")
        self.assertEqual(normalize("1 км2"), "один квадратный километр")
        self.assertEqual(normalize("2 км2"), "два квадратных километра")
        self.assertEqual(normalize("5 км2"), "пять квадратных километров")

    def test_normalize_supports_slash_units_for_speed_and_rpm(self):
        self.assertEqual(
            normalize("скорость 90 км/ч, вал крутится 3000 об/мин"),
            "скорость девяносто километров в час, вал крутится три тысячи оборотов в минуту",
        )

    def test_normalize_supports_slash_units_for_transfer_and_lab_values(self):
        self.assertEqual(
            normalize("канал 10 MB/s и 20 кбит/с"),
            "канал десять мегабайтов в секунду и двадцать килобитов в секунду",
        )
        self.assertEqual(
            normalize("раствор 5 мг/мл, 3 ммоль/л"),
            "раствор пять миллиграммов на миллилитр, три миллимоля на литр",
        )

    def test_normalize_supports_dotted_time_abbreviations(self):
        self.assertEqual(
            normalize("длительность 2 ч. 15 мин. 7 сек. А длина — 5 мин."),
            "длительность два часа пятнадцать минут семь секунд. А длина — пять минут.",
        )

    def test_normalize_supports_more_area_volume_and_duration_variants(self):
        self.assertEqual(
            normalize("10 см2 и 5 куб.м"),
            "десять квадратных сантиметров и пять кубических метров",
        )
        self.assertEqual(
            normalize("2 куб.м и 4 км2"),
            "два кубических метра и четыре квадратных километра",
        )
        self.assertEqual(
            normalize("7 сут. и 2 нед."),
            "семь суток и две недели.",
        )

    def test_normalize_supports_more_tech_and_lab_units(self):
        self.assertEqual(
            normalize("12 rpm"),
            "двенадцать оборотов в минуту",
        )
        self.assertEqual(
            normalize("220 V, 10 mA, 5 kWh"),
            "двести двадцать вольт, десять миллиампер, пять киловатт-часов",
        )
        self.assertEqual(
            normalize("5 IU и 3 мкг/мл"),
            "пять международных единиц и три микрограмма на миллилитр",
        )
        self.assertEqual(normalize("1 IU"), "одна международная единица")
        self.assertEqual(
            normalize("2 IU и 3 IU"),
            "две международные единицы и три международные единицы",
        )
        self.assertEqual(normalize("5 IU"), "пять международных единиц")
        self.assertEqual(
            normalize("8 байт/с"),
            "восемь байт в секунду",
        )

    def test_normalize_reads_tilde_before_decimal_measurement_as_approximation(self):
        self.assertEqual(
            normalize("~2.7 GB"),
            "примерно две целых семь десятых гигабайта",
        )

    def test_normalize_reads_compact_k_suffix_after_tilde_as_thousands(self):
        self.assertEqual(
            normalize("~250k запросов"),
            "примерно двести пятьдесят тысяч запросов",
        )

    def test_normalize_supports_requested_common_abbreviations(self):
        self.assertEqual(normalize("ул. Абрамова"), "улица Абрамова")
        self.assertEqual(normalize("Св. Георгия"), "Святого Георгия")
        self.assertEqual(normalize("и т.д. и т.п."), "и так далее и тому подобное.")

    def test_normalize_supports_full_decade_suffix_spelling(self):
        self.assertEqual(
            normalize("1990-ые годы."),
            "тысяча девятьсот девяностые годы.",
        )
        self.assertEqual(
            normalize("УЖЕ 1990-ые годы.", NormalizeOptions.tts()),
            "УЖЕ тысяча девятьсот девяностые годы.",
        )

    def test_normalize_keeps_hyphenated_decade_phrases_out_of_implicit_year_rule(self):
        self.assertEqual(
            normalize("а в 1990-ые годы началась новая волна обсуждений."),
            "а в тысяча девятьсот девяностые годы началась новая волна обсуждений.",
        )

    def test_normalize_keeps_parallel_percent_phrases_in_same_case(self):
        self.assertEqual(
            normalize("(Например, 20 % личного и 20 % экономического)"),
            "(Например, двадцать процентов личного и двадцать процентов экономического)",
        )

    def test_normalize_inflects_generic_numeric_ranges_from_context(self):
        self.assertEqual(
            normalize("Правительство и политика последних 20-30 лет."),
            "Правительство и политика последних двадцати — тридцати лет.",
        )
        self.assertEqual(
            normalize(
                "В главах 1–3 рассматриваются общие проблемы, которые стоят перед всеми без исключения пловцами."
            ),
            "В главах с первой по третью рассматриваются общие проблемы, которые стоят перед всеми без исключения пловцами.",
        )
        self.assertEqual(
            normalize(
                "В главах 4–10 объясняются принципы эффективного плавания, взаимодействия тела человека и воды."
            ),
            "В главах с четвёртой по десятую объясняются принципы эффективного плавания, взаимодействия тела человека и воды.",
        )
        self.assertEqual(
            normalize("Правительство и политика последних 20-30 лет и продолжение курса."),
            "Правительство и политика последних двадцати — тридцати лет и продолжение курса.",
        )

    def test_normalize_supports_heading_like_numeric_ranges(self):
        self.assertEqual(
            normalize("В главах 1–3 рассматриваются общие проблемы."),
            "В главах с первой по третью рассматриваются общие проблемы.",
        )
        self.assertEqual(
            normalize("В главах 4–10 объясняются принципы."),
            "В главах с четвёртой по десятую объясняются принципы.",
        )
        self.assertEqual(
            normalize("В частях 2–4 говорится об этом."),
            "В частях со второй по четвёртую говорится об этом.",
        )
        self.assertEqual(
            normalize("В разделах 5–7 приведены примеры."),
            "В разделах с пятого по седьмой приведены примеры.",
        )
        self.assertEqual(
            normalize("В томах 2–3 опубликованы материалы."),
            "В томах со второго по третий опубликованы материалы.",
        )
        self.assertEqual(
            normalize("В книгах 1–2 рассказано об эпохе."),
            "В книгах с первой по вторую рассказано об эпохе.",
        )
        self.assertEqual(
            normalize("В кварталах 1–2 наблюдался рост."),
            "В кварталах с первого по второй наблюдался рост.",
        )

    def test_normalize_keeps_ordinary_numeric_ranges_working(self):
        self.assertEqual(
            normalize("до 30 – 40 см в диаметре"),
            "до тридцати — сорока сантиметров в диаметре",
        )
        self.assertEqual(
            normalize("1990–2000 гг. компания выпустила 15 моделей."),
            "тысяча девятьсот девяностые — двухтысячные годы. Компания выпустила пятнадцать моделей.",
        )
        self.assertEqual(
            normalize("В начале 1960-х гг. стечение обстоятельств посеяло семена."),
            "В начале тысяча девятьсот шестидесятых годов стечение обстоятельств посеяло семена.",
        )
        self.assertEqual(
            normalize("Из лохковского века Шотландии – 410 – 414 млн л. н. –"),
            "Из лохковского века Шотландии — четыреста десять — четыреста четырнадцать миллионов лет назад —",
        )
        self.assertEqual(
            normalize("В результате погибли от 60 до 80 тыс. жителей города."),
            "В результате погибли от шестидесяти до восьмидесяти тысяч жителей города.",
        )

    def test_normalize_supports_shared_year_abbreviation_after_multiple_years(self):
        self.assertEqual(
            normalize("в 1943 и 1951 гг. — два тома"),
            "в тысяча девятьсот сорок третьем и тысяча девятьсот пятьдесят первом годах — два тома",
        )

    def test_normalize_keeps_do_year_ranges_with_trailing_single_year_abbreviation(self):
        self.assertEqual(
            normalize(
                "С 1920 до 1933 г. конституционная поправка запрещала производство."
            ),
            "С тысяча девятьсот двадцатого до тысяча девятьсот тридцать третьего года конституционная поправка запрещала производство.",
        )

    def test_normalize_keeps_bracketed_years_in_todo_visa_case(self):
        result = normalize(
            'Данила Изотов, член "Команды Visa", серебряный призер Олимпийских игр в Пекине (2008) '
            "в эстафете 4×200 метров вольным стилем, мировой рекордсмен в эстафете 4×100 метров "
            "смешанным стилем в коротких бассейнах, бронзовый призер Чемпионата мира в Риме (2009) "
            "на дистанции 200 м вольным стилем.",
            NormalizeOptions.tts(),
        )
        self.assertIn("(две тысячи восемь)", result)
        self.assertIn("(две тысячи девять)", result)

    def test_normalize_supports_years_with_era_markers_below_thousand(self):
        self.assertEqual(
            normalize("(206 год до н. э. – 220 год н. э.)"),
            "(двести шестой год до нашей эры — двести двадцатый год нашей эры)",
        )

    def test_normalize_keeps_age_phrases_in_nominative(self):
        self.assertEqual(
            normalize("когда ей было 16 лет,"),
            "когда ей было шестнадцать лет,",
        )
        self.assertEqual(
            normalize("у неё было 16 лет опыта."),
            "у неё было шестнадцать лет опыта.",
        )
        self.assertEqual(
            normalize("мне исполнилось 16 лет."),
            "мне исполнилось шестнадцать лет.",
        )

    def test_normalize_keeps_explicit_case_cues_after_case_heuristic_softening(self):
        self.assertEqual(
            normalize("к 16 годам он вырос."),
            "к шестнадцати годам он вырос.",
        )
        self.assertEqual(
            normalize("после 16 лет службы."),
            "после шестнадцати лет службы.",
        )
        self.assertEqual(
            normalize("между 5 и 7 годами прошёл срок."),
            "между пятью и семью годами прошёл срок.",
        )

    def test_normalize_supports_single_letter_cyrillic_units_when_boundary_is_clear(self):
        self.assertEqual(
            normalize("длина 5 м, температура 300 °C. Ждали 5 С."),
            "длина пять метров, температура триста градусов Цельсия. Ждали пять секунд.",
        )

    def test_normalize_keeps_ambiguous_single_letter_units_as_prepositions_in_running_text(self):
        self.assertEqual(
            normalize("Соотношение 3 к 1. Соотношение 3,5 к 1. Ждали 5 с половиной минут."),
            "Соотношение три к одному. Соотношение три целых пять десятых к одному. Ждали пять с половиной минут.",
        )

    def test_normalize_reads_equals_only_between_numeric_expressions(self):
        self.assertEqual(normalize("2=2"), "два равно два")
        self.assertEqual(
            normalize("3,5 = 7/2"),
            "три целых пять десятых равно семь вторых",
        )
        self.assertEqual(normalize("t=10"), "t равно десять")
        self.assertEqual(normalize("x=(2)"), "x равно (два)")
        self.assertEqual(normalize("x = y"), "x = y")

    def test_normalize_supports_spaced_compound_units_and_compact_rate_aliases(self):
        self.assertEqual(
            normalize("90 км ч и 5 квт ч"),
            "девяносто километров в час и пять киловатт-часов",
        )
        self.assertEqual(
            normalize("12 fps, 60 mph и 20 kbps"),
            "двенадцать кадров в секунду, шестьдесят миль в час и двадцать килобитов в секунду",
        )

    def test_normalize_supports_decimal_spaced_compound_units(self):
        self.assertEqual(
            normalize("1,5 км ч и 1,5 квт ч"),
            "одна целая пять десятых километра в час и одна целая пять десятых киловатт-часа",
        )

    def test_normalize_supports_safe_compact_units_without_slash(self):
        self.assertEqual(
            normalize("12 об мин и 3 ммоль л"),
            "двенадцать оборотов в минуту и три миллимоля на литр",
        )

    def test_normalize_compound_units_do_not_overconsume_following_token(self):
        self.assertEqual(
            normalize("500 квт ч Кл и 90 км ч Кл"),
            "пятьсот киловатт-часов Кл и девяносто километров в час Кл",
        )
        self.assertEqual(
            normalize("1,5 квт ч Кл и 1,5 км ч Кл"),
            "одна целая пять десятых киловатт-часа Кл и одна целая пять десятых километра в час Кл",
        )

    def test_normalize_compound_units_do_not_capture_following_prepositions(self):
        self.assertEqual(
            normalize("12 fps к цели, 60 mph в городе и 20 kbps к серверу"),
            "двенадцать кадров в секунду к цели, шестьдесят миль в час в городе и двадцать килобитов в секунду к серверу",
        )
        self.assertEqual(
            normalize("12 об мин к концу цикла и 3 ммоль л в крови"),
            "двенадцать оборотов в минуту к концу цикла и три миллимоля на литр в крови",
        )

    def test_normalize_compound_units_keep_boundaries_near_punctuation(self):
        self.assertEqual(
            normalize("500 квт ч, Кл. 90 км ч. Кл."),
            "пятьсот киловатт-часов, Кл. Девяносто километров в час. Кл.",
        )
        self.assertEqual(
            normalize("(1,5 квт ч) Кл и 1,5 fps в сцене"),
            "(одна целая пять десятых киловатт-часа) Кл и одна целая пять десятых кадра в секунду в сцене",
        )

    def test_normalize_syncs_legacy_gibdd_abbreviation_reading(self):
        self.assertEqual(
            normalize("ГИБДД", NormalizeOptions.tts()),
            "ги бэ дэ дэ",
        )

    def test_tts_expands_unknown_cyrillic_letter_abbreviations(self):
        self.assertEqual(normalize("ЦРУ", NormalizeOptions.tts()), "цэ эр уу")
        self.assertEqual(normalize("ФБР", NormalizeOptions.tts()), "эф бэ эр")

    def test_safe_mode_keeps_caps_and_letter_abbreviations_conservative(self):
        self.assertEqual(normalize("ГЛАВА IV.", NormalizeOptions.safe()), "ГЛАВА четыре.")
        self.assertEqual(normalize("ГИБДД", NormalizeOptions.safe()), "ГИБДД")

    def test_mode_helpers_apply_expected_defaults(self):
        safe = NormalizeOptions.safe()
        tts = NormalizeOptions.tts()

        self.assertFalse(safe.enable_caps_normalization)
        self.assertFalse(safe.enable_initials_expansion)
        self.assertFalse(safe.enable_letter_abbreviation_expansion)
        self.assertFalse(safe.enable_latinization)
        self.assertFalse(safe.remove_links)

        self.assertTrue(tts.enable_caps_normalization)
        self.assertTrue(tts.enable_initials_expansion)
        self.assertTrue(tts.enable_letter_abbreviation_expansion)
        self.assertTrue(tts.enable_latinization)
        self.assertTrue(tts.remove_links)

    def test_default_options_match_safe_preset_except_mode_marker(self):
        default = NormalizeOptions()
        safe = NormalizeOptions.safe()

        self.assertEqual(default.enable_caps_normalization, safe.enable_caps_normalization)
        self.assertEqual(default.enable_first_word_decap, safe.enable_first_word_decap)
        self.assertEqual(default.remove_links, safe.remove_links)
        self.assertEqual(default.remove_links_ignore_interval, safe.remove_links_ignore_interval)
        self.assertEqual(default.enable_year_normalization, safe.enable_year_normalization)
        self.assertEqual(default.enable_roman_normalization, safe.enable_roman_normalization)
        self.assertEqual(
            default.enable_dates_time_normalization, safe.enable_dates_time_normalization
        )
        self.assertEqual(default.enable_numeral_normalization, safe.enable_numeral_normalization)
        self.assertEqual(default.enable_abbreviation_expansion, safe.enable_abbreviation_expansion)
        self.assertEqual(
            default.enable_contextual_abbreviation_expansion,
            safe.enable_contextual_abbreviation_expansion,
        )
        self.assertEqual(default.enable_initials_expansion, safe.enable_initials_expansion)
        self.assertEqual(
            default.enable_letter_abbreviation_expansion,
            safe.enable_letter_abbreviation_expansion,
        )
        self.assertEqual(
            default.enable_dictionary_normalization, safe.enable_dictionary_normalization
        )
        self.assertEqual(default.enable_latinization, safe.enable_latinization)
        self.assertEqual(default.latinization_backend, safe.latinization_backend)
        self.assertEqual(
            default.enable_latinization_stress_marks,
            safe.enable_latinization_stress_marks,
        )
        self.assertEqual(default.latin_dictionary_filename, safe.latin_dictionary_filename)
        self.assertEqual(default.dictionary_include_files, safe.dictionary_include_files)
        self.assertEqual(default.dictionary_exclude_files, safe.dictionary_exclude_files)
        self.assertEqual(default.dictionaries_path, safe.dictionaries_path)
        self.assertIsNone(default.mode)
        self.assertEqual(safe.mode, "safe")

    def test_default_and_safe_have_same_observable_behavior(self):
        text = "ГЛАВА IV. ГИБДД (1)"

        self.assertEqual(normalize(text), normalize(text, NormalizeOptions.safe()))
        self.assertEqual(
            preprocess_text("(1)", NormalizeOptions()),
            preprocess_text("(1)", NormalizeOptions.safe()),
        )

    def test_tts_differs_from_default_on_key_behavior(self):
        self.assertEqual(normalize("ГИБДД"), "ГИБДД")
        self.assertEqual(normalize("ГИБДД", NormalizeOptions.safe()), "ГИБДД")
        self.assertEqual(normalize("ГИБДД", NormalizeOptions.tts()), "ги бэ дэ дэ")

        self.assertEqual(preprocess_text("(1)", NormalizeOptions()), "(1)")
        self.assertEqual(preprocess_text("(1)", NormalizeOptions.safe()), "(1)")
        self.assertEqual(preprocess_text("(1)", NormalizeOptions.tts()), "")

    def test_preprocess_keeps_bracketed_references_when_link_removal_is_disabled(self):
        self.assertEqual(preprocess_text("(2)", NormalizeOptions()), "(2)")
        self.assertEqual(preprocess_text("(2)", NormalizeOptions.safe()), "(2)")

    def test_tts_mode_can_enable_ipa_stress_markers_explicitly(self):
        self.assertEqual(
            normalize(
                "engineering",
                NormalizeOptions.tts(
                    latinization_backend="ipa",
                    enable_latinization_stress_marks=False,
                ),
            ),
            "энджэнирин",
        )
        self.assertEqual(
            normalize(
                "engineering",
                NormalizeOptions.tts(
                    latinization_backend="ipa",
                    enable_latinization_stress_marks=True,
                ),
            ),
            "+энджэн+ирин",
        )

    def test_run_stage_supports_targeted_stage_access(self):
        normalizer = Normalizer()

        self.assertEqual(normalizer.run_stage("roman", "Глава IV."), "Глава 4.")

    def test_package_metadata_files_exist(self):
        package_dir = Path(__import__("ru_normalizr").__file__).resolve().parent

        self.assertTrue((package_dir / "py.typed").exists())
        self.assertTrue(
            (package_dir / "dictionaries" / "latinization" / "latinization_rules.dic").exists()
        )
        self.assertTrue((package_dir / "numerals" / "__init__.py").exists())
        self.assertFalse((package_dir / "dictionaries" / "your_dictionary.dic").exists())

    def test_package_builds_as_wheel_from_package_directory(self):
        repo_root = _find_source_root()
        if repo_root is None:
            self.skipTest("source checkout not available for wheel build test")
        _clean_build_artifacts(repo_root)
        with tempfile.TemporaryDirectory() as dist_dir:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "wheel",
                    "--no-deps",
                    str(repo_root),
                    "-w",
                    dist_dir,
                ],
                text=True,
                capture_output=True,
                check=True,
            )

            self.assertIn(
                "Successfully built ru-normalizr", completed.stdout + completed.stderr
            )
            wheel_path = next(path for path in Path(dist_dir).iterdir() if path.suffix == ".whl")
            with zipfile.ZipFile(wheel_path) as wheel_file:
                wheel_names = set(wheel_file.namelist())

            self.assertIn("ru_normalizr/py.typed", wheel_names)
            self.assertIn(
                "ru_normalizr/dictionaries/latinization/latinization_rules.dic",
                wheel_names,
            )
            self.assertIn("ru_normalizr/numerals/__init__.py", wheel_names)
            self.assertNotIn("ru_normalizr/preprocess.py", wheel_names)
            self.assertNotIn("ru_normalizr/dictionaries/your_dictionary.dic", wheel_names)
            self.assertFalse(any(name.startswith("ru_normalizr/tests/") for name in wheel_names))
            self.assertFalse(any(name.startswith("ru_normalizr/scripts/") for name in wheel_names))
            self.assertFalse(any(name.startswith("ru_normalizr/examples/") for name in wheel_names))
            self.assertFalse(any(name.startswith("build/") for name in wheel_names))
            self.assertFalse(any(name.startswith("dist/") for name in wheel_names))
            self.assertFalse(any(name.startswith(".pytest_cache/") for name in wheel_names))

    def test_dictionary_rules_can_be_toggled(self):
        options = NormalizeOptions(
            enable_latinization=False,
            enable_dictionary_normalization=True,
            dictionary_include_files=("latinization/latinization_rules.dic",),
        )

        result = normalize("YouTube", options)

        self.assertNotEqual(result, "YouTube")
        self.assertNotRegex(result, r"[A-Za-z]")


class RuNormalizrCliTests(unittest.TestCase):
    def test_cli_normalizes_stdin_in_check_mode(self):
        completed = subprocess.run(
            [sys.executable, "-m", "ru_normalizr", "--check"],
            input="Глава IV.",
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertIn("Глава четыре.", completed.stdout)

    def test_cli_can_write_output_to_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "normalized.txt"
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ru_normalizr",
                    "Глава IV.",
                    "--output",
                    str(output_path),
                ],
                text=True,
                capture_output=True,
                check=True,
            )

            self.assertEqual(completed.stdout, "")
            self.assertEqual(output_path.read_text(encoding="utf-8"), "Глава четыре.\n")

    def test_cli_tts_mode_enables_letter_abbreviation_expansion(self):
        completed = subprocess.run(
            [sys.executable, "-m", "ru_normalizr", "--mode", "tts", "ГИБДД"],
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertIn("ги бэ дэ дэ", completed.stdout)


if __name__ == "__main__":
    unittest.main()
