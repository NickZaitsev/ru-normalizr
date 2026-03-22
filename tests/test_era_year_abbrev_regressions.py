from ru_normalizr import normalize


def test_normalize_handles_era_year_abbreviation_without_preposition():
    assert normalize("50 г. до н. э.") == "пятидесятый год до нашей эры."
    assert normalize("50 г. н. э.") == "пятидесятый год нашей эры."
