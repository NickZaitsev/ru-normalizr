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


class RuNormalizrKnownGapTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
