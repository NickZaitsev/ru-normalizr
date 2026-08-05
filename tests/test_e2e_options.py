"""E2E-проверки публичных переключателей ``NormalizeOptions``."""

from pathlib import Path

from ru_normalizr import NormalizeOptions, normalize


def test_caps_normalization_toggle_is_isolated_from_numerals() -> None:
    source = "Сегодня ОЧЕНЬ ВАЖНЫЙ ДЕНЬ: осталось 2 часа."

    enabled = normalize(source, NormalizeOptions.safe(enable_caps_normalization=True))
    disabled = normalize(source, NormalizeOptions.safe(enable_caps_normalization=False))

    assert enabled == "Сегодня Очень важный день: осталось два часа."
    assert disabled == "Сегодня ОЧЕНЬ ВАЖНЫЙ ДЕНЬ: осталось два часа."


def test_first_word_decap_toggle_is_isolated_from_numerals() -> None:
    source = "ЗАГОЛОВОК содержит 2 слова."

    enabled = normalize(source, NormalizeOptions.safe(enable_first_word_decap=True))
    disabled = normalize(source, NormalizeOptions.safe(enable_first_word_decap=False))

    assert enabled == "Заголовок содержит два слова."
    assert disabled == "ЗАГОЛОВОК содержит два слова."


def test_remove_links_toggle_is_isolated_from_roman_numerals() -> None:
    source = "Факт подтверждён источником[12], см. главу IV."
    common = {"enable_numeral_normalization": False}

    enabled = normalize(source, NormalizeOptions.safe(remove_links=True, **common))
    disabled = normalize(source, NormalizeOptions.safe(remove_links=False, **common))

    assert enabled == "Факт подтверждён источником, смотри главу четвёртую."
    assert disabled == "Факт подтверждён источником(12), смотри главу четвёртую."


def test_disabled_url_normalization_preserves_explicit_urls_verbatim() -> None:
    options = NormalizeOptions.safe(
        enable_url_normalization=False,
        remove_links=False,
        enable_numeral_normalization=False,
    )
    cases = (
        (
            "Адрес https://milk.org/docs указан в главе IV.",
            "Адрес https://milk.org/docs указан в главе четвёртой.",
        ),
        (
            "Откройте www.Example.COM/path?x=1&next=a#top, затем главу IV.",
            "Откройте www.Example.COM/path?x=1&next=a#top, затем главу четвёртую.",
        ),
        (
            "Сравните http://a.test:8080/x и www.b.test/(docs).",
            "Сравните http://a.test:8080/x и www.b.test/(docs).",
        ),
        (
            "Ссылка (www.example.org/path).",
            "Ссылка (www.example.org/path).",
        ),
    )

    for source, expected in cases:
        assert normalize(source, options) == expected


def test_tts_can_preserve_explicit_url_when_url_normalization_is_disabled() -> None:
    options = NormalizeOptions.tts(
        enable_url_normalization=False,
        remove_links=False,
        enable_latinization=False,
    )

    assert normalize("Адрес www.Example.COM/a1, найден 2 раза.", options) == (
        "Адрес www.Example.COM/a1, найден два раза."
    )


def test_ignored_footnote_year_uses_year_toggle_not_numeral_toggle() -> None:
    source = "Архив[1500] содержит 2 записи[12]."
    common = {
        "remove_links": True,
        "enable_numeral_normalization": False,
    }

    years_enabled = normalize(
        source,
        NormalizeOptions.safe(enable_year_normalization=True, **common),
    )
    years_disabled = normalize(
        source,
        NormalizeOptions.safe(enable_year_normalization=False, **common),
    )

    assert years_enabled == "Архив(одна тысяча пятьсот) содержит 2 записи."
    assert years_disabled == "Архив(1500) содержит 2 записи."


def test_year_normalization_toggle_keeps_roman_stage_active() -> None:
    source = "В 2024 году опубликована глава IV."
    common = {"enable_numeral_normalization": False}

    enabled = normalize(
        source,
        NormalizeOptions.safe(enable_year_normalization=True, **common),
    )
    disabled = normalize(
        source,
        NormalizeOptions.safe(enable_year_normalization=False, **common),
    )

    assert enabled == "В две тысячи двадцать четвёртом году опубликована глава четвёртая."
    assert disabled == "В 2024 году опубликована глава четвёртая."


def test_roman_normalization_toggle_keeps_cardinal_stage_active() -> None:
    source = "В главе IV есть 3 причины."

    enabled = normalize(source, NormalizeOptions.safe(enable_roman_normalization=True))
    disabled = normalize(source, NormalizeOptions.safe(enable_roman_normalization=False))

    assert enabled == "В главе четвёртой есть три причины."
    assert disabled == "В главе IV есть три причины."


def test_dates_time_normalization_toggle_keeps_roman_stage_active() -> None:
    source = "Встреча 12.05.2025 в 09:30 описана в главе IV."
    common = {"enable_numeral_normalization": False, "enable_year_normalization": False}

    enabled = normalize(
        source,
        NormalizeOptions.safe(enable_dates_time_normalization=True, **common),
    )
    disabled = normalize(
        source,
        NormalizeOptions.safe(enable_dates_time_normalization=False, **common),
    )

    assert enabled == "Встреча двенадцатого мая две тысячи двадцать пятого года в девять, тридцать описана в главе четвёртой."
    assert disabled == "Встреча 12.05.2025 в 09:30 описана в главе четвёртой."


def test_numeral_normalization_toggle_keeps_roman_stage_active() -> None:
    source = "Глава IV содержит 3 пункта и значение 2,5."

    enabled = normalize(source, NormalizeOptions.safe(enable_numeral_normalization=True))
    disabled = normalize(source, NormalizeOptions.safe(enable_numeral_normalization=False))

    assert enabled == "Глава четвёртая содержит три пункта и значение две целых пять десятых."
    assert disabled == "Глава четвёртая содержит 3 пункта и значение 2,5."


def test_malformed_punctuation_cleanup_toggle_runs_after_numerals() -> None:
    source = "Фраза., затем 2 слова."

    enabled = normalize(
        source,
        NormalizeOptions.safe(cleanup_malformed_punctuation=True),
    )
    disabled = normalize(
        source,
        NormalizeOptions.safe(cleanup_malformed_punctuation=False),
    )

    assert enabled == "Фраза. затем два слова."
    assert disabled == "Фраза., затем два слова."

    tts_source = "Шум., затем."
    assert normalize(tts_source, NormalizeOptions.tts()) == "Шум. затем."
    assert normalize(
        tts_source,
        NormalizeOptions.tts(cleanup_malformed_punctuation=False),
    ) == "Шум., затем."


def test_safe_punctuation_cleanup_preserves_clause_commas_after_initials() -> None:
    options = NormalizeOptions.safe(cleanup_malformed_punctuation=False)

    listed = normalize(
        "В комиссию вошли Иванов А. Б., Петров В. Г. и Сидоров.", options
    )
    clause = "Работу приняли Иванов А. Б., затем подписал Петров."

    assert "Иванов А. Б., Петров" in listed
    assert normalize(clause, options) == clause


def test_abbreviation_expansion_toggle_keeps_numeral_stage_active() -> None:
    source = "Автор пояснил: т. е. документ содержит 3 раздела."

    enabled = normalize(source, NormalizeOptions.safe(enable_abbreviation_expansion=True))
    disabled = normalize(source, NormalizeOptions.safe(enable_abbreviation_expansion=False))

    assert enabled == "Автор пояснил: то есть документ содержит три раздела."
    assert disabled == "Автор пояснил: т. Е. Документ содержит три раздела."


def test_contextual_abbreviation_toggle_keeps_numeral_stage_active() -> None:
    source = "В гос. школе открыли 3 кабинета."

    enabled = normalize(
        source,
        NormalizeOptions.safe(enable_contextual_abbreviation_expansion=True),
    )
    disabled = normalize(
        source,
        NormalizeOptions.safe(enable_contextual_abbreviation_expansion=False),
    )

    assert enabled == "В государственной школе открыли три кабинета."
    assert disabled == "В гос. Школе открыли три кабинета."


def test_years_ago_toggle_keeps_roman_stage_active() -> None:
    source = "Это произошло 5 млн л. н., см. главу IV."
    common = {
        "enable_numeral_normalization": False,
        "enable_abbreviation_expansion": False,
    }

    enabled = normalize(
        source,
        NormalizeOptions.safe(enable_years_ago_expansion=True, **common),
    )
    disabled = normalize(
        source,
        NormalizeOptions.safe(enable_years_ago_expansion=False, **common),
    )

    assert enabled == "Это произошло 5 млн лет назад, см. Главу четвёртую."
    assert disabled == "Это произошло 5 млн л. Н., см. Главу четвёртую."


def test_initials_expansion_toggle_keeps_numeral_stage_active() -> None:
    source = "Редактор Е. Харитонова подготовила 2 версии."
    common = {"initials_vowel_mode": "double", "initials_pause_mode": "comma"}

    enabled = normalize(
        source,
        NormalizeOptions.safe(enable_initials_expansion=True, **common),
    )
    disabled = normalize(
        source,
        NormalizeOptions.safe(enable_initials_expansion=False, **common),
    )

    assert enabled == "Редактор ее Харитонова подготовила две версии."
    assert disabled == "Редактор Е. Харитонова подготовила две версии."


def test_initials_vowel_mode_changes_only_vowel_letter_name() -> None:
    source = "Редактор Е. Харитонова подготовила 2 версии."
    common = {"enable_initials_expansion": True, "initials_pause_mode": "preserve"}

    single = normalize(
        source,
        NormalizeOptions.safe(initials_vowel_mode="single", **common),
    )
    double = normalize(
        source,
        NormalizeOptions.safe(initials_vowel_mode="double", **common),
    )

    assert single == "Редактор е Харитонова подготовила две версии."
    assert double == "Редактор ее Харитонова подготовила две версии."


def test_letter_vowel_mode_applies_across_public_letter_reading_paths() -> None:
    source = "Редактор Е. Харитонова сравнила США, SU, support и модель-восемьдесят-U."
    common = {
        "enable_initials_expansion": True,
        "enable_letter_abbreviation_expansion": True,
        "enable_latinization": True,
        "latinization_backend": "dictionary",
        "initials_pause_mode": "preserve",
    }

    single = normalize(source, NormalizeOptions.safe(letter_vowel_mode="single", **common))
    double = normalize(source, NormalizeOptions.safe(letter_vowel_mode="double", **common))

    assert single == (
        "Редактор е Харитонова сравнила сэ шэ а, эс ю, сапорт и модель-восемьдесят-ю."
    )
    assert double == (
        "Редактор ее Харитонова сравнила сэ шэ аа, эс юю, сапорт и модель-восемьдесят-юю."
    )


def test_initials_pause_mode_changes_only_surname_first_pauses() -> None:
    source = "Доклад подготовил Иванов А. Б. вчера за 2 часа."
    common = {"enable_initials_expansion": True, "initials_vowel_mode": "double"}

    preserved = normalize(
        source,
        NormalizeOptions.safe(initials_pause_mode="preserve", **common),
    )
    comma = normalize(
        source,
        NormalizeOptions.safe(initials_pause_mode="comma", **common),
    )

    assert preserved == "Доклад подготовил Иванов аа бэ вчера за два часа."
    assert comma == "Доклад подготовил Иванов, аа, бэ, вчера за два часа."


def test_letter_abbreviation_toggle_keeps_numeral_stage_active() -> None:
    source = "ГИБДД проверила 2 машины."
    common = {"enable_latinization": False}

    enabled = normalize(
        source,
        NormalizeOptions.tts(enable_letter_abbreviation_expansion=True, **common),
    )
    disabled = normalize(
        source,
        NormalizeOptions.tts(enable_letter_abbreviation_expansion=False, **common),
    )

    assert enabled == "ги бэ дэ дэ проверила две машины."
    assert disabled == "ГИБДД проверила две машины."


def test_dictionary_normalization_toggle_keeps_numeral_stage_active(tmp_path: Path) -> None:
    (tmp_path / "brands.dic").write_text("YouTube=ютуб\n", encoding="utf-8")
    source = "YouTube выпустил 2 ролика."
    common = {
        "dictionaries_path": tmp_path,
        "dictionary_include_files": ("brands.dic",),
        "enable_latinization": False,
    }

    enabled = normalize(
        source,
        NormalizeOptions.safe(enable_dictionary_normalization=True, **common),
    )
    disabled = normalize(
        source,
        NormalizeOptions.safe(enable_dictionary_normalization=False, **common),
    )

    assert enabled == "ютуб выпустил два ролика."
    assert disabled == "YouTube выпустил два ролика."


def test_latinization_toggle_keeps_numeral_stage_active() -> None:
    source = "YouTube выпустил 2 ролика."
    common = {"latinization_backend": "dictionary"}

    enabled = normalize(
        source,
        NormalizeOptions.safe(enable_latinization=True, **common),
    )
    disabled = normalize(
        source,
        NormalizeOptions.safe(enable_latinization=False, **common),
    )

    assert enabled == "иаутюбэ выпустил два ролика."
    assert disabled == "YouTube выпустил два ролика."


def test_latinization_stress_marks_toggle_keeps_surrounding_numerals_stable() -> None:
    source = "engineering включает 2 раздела."
    common = {"enable_latinization": True, "latinization_backend": "ipa"}

    disabled = normalize(
        source,
        NormalizeOptions.safe(enable_latinization_stress_marks=False, **common),
    )
    enabled = normalize(
        source,
        NormalizeOptions.safe(enable_latinization_stress_marks=True, **common),
    )

    assert disabled == "энджэнирин включает два раздела."
    assert enabled == "+энджэн+ирин включает два раздела."
