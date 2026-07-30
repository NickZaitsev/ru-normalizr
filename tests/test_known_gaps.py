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
        reason="the counted noun keeps the form written beside the digit",
    )
    def test_animate_paucal_accusative_agrees_the_counted_noun(self):
        self.assertEqual(
            normalize("Вижу 2 человека у входа."), "Вижу двух человек у входа."
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


if __name__ == "__main__":
    unittest.main()
