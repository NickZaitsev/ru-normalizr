from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Optional

NormalizeMode = Literal["safe", "tts"]
LatinizationBackend = Literal["ipa", "dictionary"]

_SAFE_MODE_DEFAULTS = {
    "enable_caps_normalization": False,
    "enable_first_word_decap": False,
    "remove_links": False,
    "enable_url_normalization": False,
    "enable_year_normalization": True,
    "enable_roman_normalization": True,
    "enable_dates_time_normalization": True,
    "enable_numeral_normalization": True,
    "enable_abbreviation_expansion": True,
    "enable_contextual_abbreviation_expansion": True,
    "enable_initials_expansion": False,
    "enable_letter_abbreviation_expansion": False,
    "enable_dictionary_normalization": True,
    "enable_latinization": False,
    "latinization_backend": "ipa",
    "enable_latinization_stress_marks": False,
}

_TTS_MODE_DEFAULTS = {
    "enable_caps_normalization": True,
    "enable_first_word_decap": True,
    "remove_links": True,
    "enable_url_normalization": True,
    "enable_year_normalization": True,
    "enable_roman_normalization": True,
    "enable_dates_time_normalization": True,
    "enable_numeral_normalization": True,
    "enable_abbreviation_expansion": True,
    "enable_contextual_abbreviation_expansion": True,
    "enable_initials_expansion": True,
    "enable_letter_abbreviation_expansion": True,
    "enable_dictionary_normalization": True,
    "enable_latinization": True,
    "latinization_backend": "ipa",
    "enable_latinization_stress_marks": False,
}


def _mode_defaults(mode: NormalizeMode | None) -> dict[str, object]:
    if mode == "tts":
        return dict(_TTS_MODE_DEFAULTS)
    return dict(_SAFE_MODE_DEFAULTS)


@dataclass(frozen=True, slots=True, init=False)
class NormalizeOptions:
    """Public configuration for ru_normalizr."""

    enable_caps_normalization: bool
    enable_first_word_decap: bool
    remove_links: bool
    enable_url_normalization: bool
    remove_links_ignore_interval: tuple[int, int]
    enable_year_normalization: bool
    enable_roman_normalization: bool
    enable_dates_time_normalization: bool
    enable_numeral_normalization: bool
    enable_abbreviation_expansion: bool
    enable_contextual_abbreviation_expansion: bool
    enable_initials_expansion: bool
    enable_letter_abbreviation_expansion: bool
    enable_dictionary_normalization: bool
    enable_latinization: bool
    latinization_backend: LatinizationBackend
    enable_latinization_stress_marks: bool
    latin_dictionary_filename: str
    dictionary_include_files: tuple[str, ...]
    dictionary_exclude_files: tuple[str, ...]
    dictionaries_path: Optional[Path]
    mode: NormalizeMode | None

    def __init__(
        self,
        *,
        enable_caps_normalization: bool | None = None,
        enable_first_word_decap: bool | None = None,
        remove_links: bool | None = None,
        enable_url_normalization: bool | None = None,
        remove_links_ignore_interval: tuple[int, int] = (1000, 2200),
        enable_year_normalization: bool | None = None,
        enable_roman_normalization: bool | None = None,
        enable_dates_time_normalization: bool | None = None,
        enable_numeral_normalization: bool | None = None,
        enable_abbreviation_expansion: bool | None = None,
        enable_contextual_abbreviation_expansion: bool | None = None,
        enable_initials_expansion: bool | None = None,
        enable_letter_abbreviation_expansion: bool | None = None,
        enable_dictionary_normalization: bool | None = None,
        enable_latinization: bool | None = None,
        latinization_backend: LatinizationBackend | None = None,
        enable_latinization_stress_marks: bool | None = None,
        latin_dictionary_filename: str = "latinization_rules.dic",
        dictionary_include_files: tuple[str, ...] = (),
        dictionary_exclude_files: tuple[str, ...] = (),
        dictionaries_path: Optional[Path] = None,
        mode: NormalizeMode | None = None,
    ) -> None:
        defaults = _mode_defaults(mode)

        values = {
            "enable_caps_normalization": enable_caps_normalization,
            "enable_first_word_decap": enable_first_word_decap,
            "remove_links": remove_links,
            "enable_url_normalization": enable_url_normalization,
            "enable_year_normalization": enable_year_normalization,
            "enable_roman_normalization": enable_roman_normalization,
            "enable_dates_time_normalization": enable_dates_time_normalization,
            "enable_numeral_normalization": enable_numeral_normalization,
            "enable_abbreviation_expansion": enable_abbreviation_expansion,
            "enable_contextual_abbreviation_expansion": enable_contextual_abbreviation_expansion,
            "enable_initials_expansion": enable_initials_expansion,
            "enable_letter_abbreviation_expansion": enable_letter_abbreviation_expansion,
            "enable_dictionary_normalization": enable_dictionary_normalization,
            "enable_latinization": enable_latinization,
            "latinization_backend": latinization_backend,
            "enable_latinization_stress_marks": enable_latinization_stress_marks,
        }

        for field_name, explicit_value in values.items():
            object.__setattr__(
                self,
                field_name,
                defaults[field_name] if explicit_value is None else explicit_value,
            )

        object.__setattr__(self, "remove_links_ignore_interval", remove_links_ignore_interval)
        object.__setattr__(self, "latin_dictionary_filename", latin_dictionary_filename)
        object.__setattr__(self, "dictionary_include_files", dictionary_include_files)
        object.__setattr__(self, "dictionary_exclude_files", dictionary_exclude_files)
        object.__setattr__(self, "dictionaries_path", dictionaries_path)
        object.__setattr__(self, "mode", mode)

    @classmethod
    def safe(cls, **overrides: object) -> "NormalizeOptions":
        return cls(mode="safe", **overrides)

    @classmethod
    def tts(cls, **overrides: object) -> "NormalizeOptions":
        return cls(mode="tts", **overrides)
