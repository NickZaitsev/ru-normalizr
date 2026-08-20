"""Юнит-тесты ``NormalizeOptions``: снимок профилей и валидация входа.

Снимок ниже — литеральный, а не вычисленный из ``_MODE_DEFAULTS``: иначе тест
повторял бы реализацию и молча ехал бы вместе с ней. Любое изменение профиля
safe или tts видно для пользователя, поэтому ломать этот тест можно только
осознанно и с записью в ``CHANGELOG.md``.
"""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path
from typing import Any

import pytest

from ru_normalizr import NormalizeOptions

SAFE_PROFILE: dict[str, Any] = {
    "cleanup_malformed_punctuation": False,
    "enable_caps_normalization": False,
    "enable_first_word_decap": False,
    "remove_links": False,
    "enable_url_normalization": False,
    "remove_links_ignore_interval": (1000, 2200),
    "enable_year_normalization": True,
    "enable_roman_normalization": True,
    "enable_dates_time_normalization": True,
    "enable_numeral_normalization": True,
    "enable_abbreviation_expansion": True,
    "enable_contextual_abbreviation_expansion": True,
    "enable_years_ago_expansion": True,
    "enable_initials_expansion": False,
    "letter_vowel_mode": "single",
    "initials_vowel_mode": "single",
    "initials_pause_mode": "preserve",
    "enable_letter_abbreviation_expansion": False,
    "enable_dictionary_normalization": True,
    "enable_latinization": False,
    "latinization_backend": "ipa",
    "enable_latinization_stress_marks": False,
    "latin_dictionary_filename": "latinization_rules.dic",
    "dictionary_include_files": (),
    "dictionary_exclude_files": (),
    "dictionaries_path": None,
    "mode": "safe",
}

TTS_PROFILE: dict[str, Any] = {
    **SAFE_PROFILE,
    "cleanup_malformed_punctuation": True,
    "enable_caps_normalization": True,
    "enable_first_word_decap": True,
    "remove_links": True,
    "enable_url_normalization": True,
    "enable_initials_expansion": True,
    "letter_vowel_mode": "double",
    "initials_vowel_mode": "double",
    "initials_pause_mode": "comma",
    "enable_letter_abbreviation_expansion": True,
    "enable_latinization": True,
    "mode": "tts",
}


def _profile_items(profile: dict[str, Any]) -> list[tuple[str, Any]]:
    return sorted(profile.items())


@pytest.mark.parametrize(
    ("factory", "expected"),
    [("safe", SAFE_PROFILE), ("tts", TTS_PROFILE)],
    ids=["safe", "tts"],
)
@pytest.mark.parametrize("field_name", sorted(SAFE_PROFILE))
def test_profile_field_matches_snapshot(factory: str, expected: dict[str, Any], field_name: str) -> None:
    options = getattr(NormalizeOptions, factory)()

    assert getattr(options, field_name) == expected[field_name]


def test_snapshot_covers_every_declared_field() -> None:
    """Новая опция обязана попасть в снимок, иначе тест выше её не проверит."""
    declared = {field.name for field in fields(NormalizeOptions)}

    assert declared == set(SAFE_PROFILE)
    assert declared == set(TTS_PROFILE)


def test_default_construction_matches_safe_profile() -> None:
    """Без ``mode`` действует safe — только поле ``mode`` остаётся пустым."""
    options = NormalizeOptions()

    assert options.mode is None
    for name, value in _profile_items(SAFE_PROFILE):
        if name == "mode":
            continue
        assert getattr(options, name) == value, name


@pytest.mark.parametrize("factory", ["safe", "tts"])
def test_unknown_override_name_raises_type_error(factory: str) -> None:
    """Опечатка в имени опции раньше молча терялась в ``**overrides``."""
    with pytest.raises(TypeError, match="enable_caps_normalizatoin"):
        getattr(NormalizeOptions, factory)(enable_caps_normalizatoin=True)


def test_unknown_override_lists_every_bad_name() -> None:
    with pytest.raises(TypeError) as excinfo:
        NormalizeOptions.tts(nope=True, also_nope=False)

    message = str(excinfo.value)
    assert "'also_nope'" in message
    assert "'nope'" in message


@pytest.mark.parametrize("mode", ["", "TTS", "ttts", "default", "Safe"])
def test_unknown_mode_raises_value_error(mode: str) -> None:
    """Опечатка в режиме раньше молча давала профиль safe."""
    with pytest.raises(ValueError, match="unknown normalization mode"):
        NormalizeOptions(mode=mode)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("override", "expected"),
    [
        ({"enable_latinization": False}, ("enable_latinization", False)),
        ({"letter_vowel_mode": "single"}, ("letter_vowel_mode", "single")),
        ({"dictionary_include_files": ("a.dic",)}, ("dictionary_include_files", ("a.dic",))),
        ({"dictionaries_path": Path("dicts")}, ("dictionaries_path", Path("dicts"))),
        ({"remove_links_ignore_interval": (0, 1)}, ("remove_links_ignore_interval", (0, 1))),
    ],
)
def test_valid_overrides_still_apply(override: dict[str, Any], expected: tuple[str, Any]) -> None:
    """Проверка имён не должна отсекать легальные не-bool опции."""
    options = NormalizeOptions.tts(**override)

    name, value = expected
    assert getattr(options, name) == value


def test_letter_vowel_mode_override_syncs_initials_alias() -> None:
    options = NormalizeOptions.safe(letter_vowel_mode="double")

    assert options.initials_vowel_mode == "double"


def test_conflicting_vowel_modes_still_raise() -> None:
    with pytest.raises(ValueError, match="must match"):
        NormalizeOptions.tts(letter_vowel_mode="single", initials_vowel_mode="double")
