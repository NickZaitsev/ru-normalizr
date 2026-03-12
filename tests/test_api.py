import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from ru_normalizr import NormalizeOptions, Normalizer, normalize, preprocess_text


class RuNormalizrApiTests(unittest.TestCase):
    def test_normalize_function_handles_roman_and_time_pipeline(self):
        self.assertEqual(
            normalize("Глава IV. Встреча в 10:07."),
            "Глава четыре. Встреча в десять, ноль семь.",
        )

    def test_normalize_runs_roman_before_caps_normalization(self):
        self.assertEqual(
            normalize("ГЛАВА IV."),
            "Глава четыре.",
        )

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

    def test_preprocess_text_is_exported(self):
        self.assertIn("10 кг", preprocess_text("10кг"))

    def test_preprocess_text_inserts_legacy_dot_before_uppercase_line(self):
        self.assertEqual(
            preprocess_text(
                "Часть два.\nПалеозой: утро\n\nКембрий пятьсот сорок один,"
            ),
            "Часть два.\nПалеозой: утро.\nКембрий пятьсот сорок один,",
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
            "Первая строка.\nВторая строка",
        )

    def test_preprocess_text_inserts_legacy_dot_before_uppercase_paragraph(self):
        self.assertEqual(
            preprocess_text("Metaspriggina walcotti\n\nЧего пока не хватало"),
            "Metaspriggina walcotti.\nЧего пока не хватало",
        )

    def test_preprocess_text_collapses_many_linebreaks_to_one(self):
        self.assertEqual(
            preprocess_text("Первая строка\n\n\n\n\n\nВторая строка"),
            "Первая строка.\nВторая строка",
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
            ),
            'Автомобиль джип ("виллис"), легкий полноприводной вездеход.',
        )

    def test_preprocess_text_normalizes_caps_heading_with_short_preposition(self):
        self.assertEqual(
            preprocess_text(
                "АВТОМОБИЛЬ С КОМПЬЮТЕРНЫМ УПРАВЛЕНИЕМ ТРАНСМИССИЕЙ, выпустила на рынок японская компания."
            ),
            "Автомобиль С Компьютерным управлением трансмиссией, выпустила на рынок японская компания.",
        )

    def test_preprocess_text_normalizes_caps_heading_with_multiple_words(self):
        self.assertEqual(
            preprocess_text(
                "АВТОРУЧКА С КЕРАМИЧЕСКИМ ПЕРОМ, выпустила на рынок японская компания."
            ),
            "Авторучка С Керамическим пером, выпустила на рынок японская компания.",
        )

    def test_preprocess_text_normalizes_caps_heading_without_parentheses(self):
        self.assertEqual(
            preprocess_text(
                "БАТАРЕЙКА ЭЛЕКТРИЧЕСКАЯ ПЛАСТМАССОВАЯ, сконструирована американскими учеными."
            ),
            "Батарейка электрическая пластмассовая, сконструирована американскими учеными.",
        )

    def test_preprocess_text_cleans_quote_ellipsis_and_sentence_spacing(self):
        self.assertEqual(
            preprocess_text(
                'Основное правило: любое объяснение лучше его отсутствия … Итак. Ницше, " Сумерки богов "'
            ),
            'Основное правило: любое объяснение лучше его отсутствия… Итак. Ницше, "Сумерки богов"',
        )

    def test_preprocess_text_inserts_legacy_dot_before_digit_line_and_expands_years_ago(
        self,
    ):
        self.assertEqual(
            preprocess_text("МЕЖДУНАРОДНАЯ ШКАЛА\n541 млн л. н."),
            "Международная шкала.\n541 млн лет назад.",
        )

    def test_normalize_preserves_letter_hyphens_inside_words(self):
        self.assertEqual(
            normalize("Планета-печка и Великая Революция"),
            "Планета-печка и Великая Революция",
        )

    def test_normalize_expands_years_ago_before_unit_normalization(self):
        self.assertEqual(
            normalize("МЕЖДУНАРОДНАЯ ШКАЛА\n541 млн л. н."),
            "Международная шкала. пятьсот сорок один миллион лет назад.",
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
            "Глава четыре.\nВстреча в десять, ноль семь.",
        )

    def test_normalize_keeps_sentence_boundary_after_etc_abbreviation(self):
        self.assertEqual(
            normalize("миротворцы и т. д. Эти шумы остались."),
            "миротворцы и так далее. Эти шумы остались.",
        )

    def test_normalize_removes_decorative_separator_without_extra_punctuation(self):
        self.assertEqual(
            normalize(
                "первый шаг в сторону обретения челюстей.\n\n"
                "Metaspriggina walcotti\n\n\n"
                "* * *\n\n\n"
                "Чего пока не хватало кембрийским хордовым, так это чешуи и зубов. "
            ),
            "первый шаг в сторону обретения челюстей.\n"
            "мэтэспаригджинэ вэлсоттай.\n\n"
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

    def test_preprocess_text_keeps_bracketed_comma_decimals(self):
        self.assertEqual(preprocess_text("(500,5)"), "(500,5)")
        self.assertEqual(preprocess_text("(1 234,56)"), "(1234,56)")
        self.assertEqual(preprocess_text("(10,0%)"), "(10,0%)")
        self.assertEqual(preprocess_text("(500,5 кг)"), "(500,5 кг)")

    def test_preprocess_text_removes_confident_bracketed_references(self):
        self.assertEqual(preprocess_text("(1)"), "")
        self.assertEqual(preprocess_text("(1, 3, 5)"), "")
        self.assertEqual(preprocess_text("(1–3)"), "")
        self.assertEqual(preprocess_text("(2.5)"), "")
        self.assertEqual(preprocess_text("(2.5.1)"), "")

    def test_normalize_keeps_cyrillic_measurements_out_of_roman_stage(self):
        self.assertEqual(
            normalize(
                "характерны гигантские медузоиды до 30 – 40 см в диаметре и перистовидные колонии"
            ),
            "характерны гигантские медузоиды до тридцати — сорока сантиметров в диаметре и перистовидные колонии",
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

    def test_normalize_syncs_legacy_gibdd_abbreviation_reading(self):
        self.assertEqual(
            normalize("ГИБДД"),
            "ги бэ дэ дэ",
        )

    def test_run_stage_supports_targeted_stage_access(self):
        normalizer = Normalizer()

        self.assertEqual(normalizer.run_stage("roman", "Глава IV."), "Глава 4.")

    def test_package_metadata_files_exist(self):
        package_dir = Path(__import__("ru_normalizr").__file__).resolve().parent

        self.assertTrue((package_dir / "py.typed").exists())
        self.assertTrue((package_dir / "dictionaries" / "65_ЛАТИНИЦА@.dic").exists())

    def test_stage_module_import_does_not_pull_speakerpy(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import ru_normalizr.roman_numerals; "
                "print(any(name.startswith('speakerpy') for name in sys.modules))",
            ],
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertEqual(completed.stdout.strip(), "False")

    def test_package_builds_as_wheel_from_package_directory(self):
        repo_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as dist_dir:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "wheel",
                    "--no-deps",
                    str(repo_root / "ru_normalizr"),
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
            self.assertTrue(
                any(path.suffix == ".whl" for path in Path(dist_dir).iterdir())
            )

    def test_latinization_module_import_does_not_pull_speakerpy(self):
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import sys; import ru_normalizr.latinization; "
                "print(any(name.startswith('speakerpy') for name in sys.modules))",
            ],
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertEqual(completed.stdout.strip(), "False")

    def test_dictionary_rules_can_be_toggled(self):
        options = NormalizeOptions(
            enable_latinization=False,
            enable_dictionary_normalization=True,
            dictionary_include_files=("65_ЛАТИНИЦА@.dic",),
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


if __name__ == "__main__":
    unittest.main()
