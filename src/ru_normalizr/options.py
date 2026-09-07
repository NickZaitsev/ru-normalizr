from __future__ import annotations

import inspect
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .constants import LetterVowelMode

NormalizeMode = Literal["safe", "tts"]
LatinizationBackend = Literal["ipa", "dictionary"]
InitialsVowelMode = LetterVowelMode
InitialsPauseMode = Literal["preserve", "comma"]

# Единственный источник истины для профилей: одна строка на опцию, значения для
# safe и tts рядом. Расхождение между профилями видно глазами, и нельзя добавить
# опцию в один профиль, забыв про другой.
_MODE_DEFAULTS: dict[str, tuple[object, object]] = {
    # опция: (safe, tts)
    "cleanup_malformed_punctuation": (False, True),
    "enable_caps_normalization": (False, True),
    "enable_first_word_decap": (False, True),
    "remove_links": (False, True),
    "enable_url_normalization": (False, True),
    "enable_year_normalization": (True, True),
    "enable_roman_normalization": (True, True),
    "enable_math_normalization": (False, True),
    "enable_dates_time_normalization": (True, True),
    "enable_numeral_normalization": (True, True),
    "enable_abbreviation_expansion": (True, True),
    "enable_contextual_abbreviation_expansion": (True, True),
    "enable_years_ago_expansion": (True, True),
    "enable_initials_expansion": (False, True),
    "letter_vowel_mode": ("single", "double"),
    "initials_pause_mode": ("preserve", "comma"),
    "enable_letter_abbreviation_expansion": (False, True),
    "enable_dictionary_normalization": (True, True),
    "enable_latinization": (False, True),
    "latinization_backend": ("ipa", "ipa"),
    "enable_latinization_stress_marks": (False, False),
}

_PROFILES: dict[str, Mapping[str, object]] = {
    "safe": {name: values[0] for name, values in _MODE_DEFAULTS.items()},
    "tts": {name: values[1] for name, values in _MODE_DEFAULTS.items()},
}


def _mode_defaults(mode: NormalizeMode | None) -> Mapping[str, object]:
    """Вернуть дефолты профиля. Без режима действует safe, опечатка в режиме — ошибка."""
    if mode is None:
        return _PROFILES["safe"]
    try:
        return _PROFILES[mode]
    except KeyError:
        raise ValueError(
            f"unknown normalization mode {mode!r}; expected one of {sorted(_PROFILES)}"
        ) from None


@dataclass(frozen=True, slots=True, init=False)
class NormalizeOptions:
    """Public configuration for ru_normalizr."""

    cleanup_malformed_punctuation: bool
    enable_caps_normalization: bool
    enable_first_word_decap: bool
    remove_links: bool
    enable_url_normalization: bool
    remove_links_ignore_interval: tuple[int, int]
    enable_year_normalization: bool
    enable_roman_normalization: bool
    enable_math_normalization: bool
    enable_dates_time_normalization: bool
    enable_numeral_normalization: bool
    enable_abbreviation_expansion: bool
    enable_contextual_abbreviation_expansion: bool
    enable_years_ago_expansion: bool
    enable_initials_expansion: bool
    letter_vowel_mode: LetterVowelMode
    initials_vowel_mode: InitialsVowelMode
    initials_pause_mode: InitialsPauseMode
    enable_letter_abbreviation_expansion: bool
    enable_dictionary_normalization: bool
    enable_latinization: bool
    latinization_backend: LatinizationBackend
    enable_latinization_stress_marks: bool
    latin_dictionary_filename: str
    dictionary_include_files: tuple[str, ...]
    dictionary_exclude_files: tuple[str, ...]
    dictionaries_path: Path | None
    mode: NormalizeMode | None

    def __init__(
        self,
        *,
        cleanup_malformed_punctuation: bool | None = None,
        enable_caps_normalization: bool | None = None,
        enable_first_word_decap: bool | None = None,
        remove_links: bool | None = None,
        enable_url_normalization: bool | None = None,
        remove_links_ignore_interval: tuple[int, int] = (1000, 2200),
        enable_year_normalization: bool | None = None,
        enable_roman_normalization: bool | None = None,
        enable_math_normalization: bool | None = None,
        enable_dates_time_normalization: bool | None = None,
        enable_numeral_normalization: bool | None = None,
        enable_abbreviation_expansion: bool | None = None,
        enable_contextual_abbreviation_expansion: bool | None = None,
        enable_years_ago_expansion: bool | None = None,
        enable_initials_expansion: bool | None = None,
        letter_vowel_mode: LetterVowelMode | None = None,
        initials_vowel_mode: InitialsVowelMode | None = None,
        initials_pause_mode: InitialsPauseMode | None = None,
        enable_letter_abbreviation_expansion: bool | None = None,
        enable_dictionary_normalization: bool | None = None,
        enable_latinization: bool | None = None,
        latinization_backend: LatinizationBackend | None = None,
        enable_latinization_stress_marks: bool | None = None,
        latin_dictionary_filename: str = "latinization_rules.dic",
        dictionary_include_files: tuple[str, ...] = (),
        dictionary_exclude_files: tuple[str, ...] = (),
        dictionaries_path: Path | None = None,
        mode: NormalizeMode | None = None,
    ) -> None:
        defaults = _mode_defaults(mode)

        if (
            letter_vowel_mode is not None
            and initials_vowel_mode is not None
            and letter_vowel_mode != initials_vowel_mode
        ):
            raise ValueError(
                "letter_vowel_mode and initials_vowel_mode must match when both are provided"
            )
        effective_letter_vowel_mode = (
            letter_vowel_mode if letter_vowel_mode is not None else initials_vowel_mode
        )

        values = {
            "cleanup_malformed_punctuation": cleanup_malformed_punctuation,
            "enable_caps_normalization": enable_caps_normalization,
            "enable_first_word_decap": enable_first_word_decap,
            "remove_links": remove_links,
            "enable_url_normalization": enable_url_normalization,
            "enable_year_normalization": enable_year_normalization,
            "enable_roman_normalization": enable_roman_normalization,
            "enable_math_normalization": enable_math_normalization,
            "enable_dates_time_normalization": enable_dates_time_normalization,
            "enable_numeral_normalization": enable_numeral_normalization,
            "enable_abbreviation_expansion": enable_abbreviation_expansion,
            "enable_contextual_abbreviation_expansion": enable_contextual_abbreviation_expansion,
            "enable_years_ago_expansion": enable_years_ago_expansion,
            "enable_initials_expansion": enable_initials_expansion,
            "letter_vowel_mode": effective_letter_vowel_mode,
            "initials_pause_mode": initials_pause_mode,
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

        object.__setattr__(self, "initials_vowel_mode", self.letter_vowel_mode)

        object.__setattr__(self, "remove_links_ignore_interval", remove_links_ignore_interval)
        object.__setattr__(self, "latin_dictionary_filename", latin_dictionary_filename)
        object.__setattr__(self, "dictionary_include_files", dictionary_include_files)
        object.__setattr__(self, "dictionary_exclude_files", dictionary_exclude_files)
        object.__setattr__(self, "dictionaries_path", dictionaries_path)
        object.__setattr__(self, "mode", mode)

    @classmethod
    def safe(cls, **overrides: Any) -> NormalizeOptions:
        _check_override_names("safe", overrides)
        return cls(mode="safe", **overrides)

    @classmethod
    def tts(cls, **overrides: Any) -> NormalizeOptions:
        _check_override_names("tts", overrides)
        return cls(mode="tts", **overrides)


# Имена опций выводятся из подписи __init__, чтобы не держать ещё один список
# опций, который придётся руками синхронизировать при добавлении новой.
OPTION_NAMES: frozenset[str] = frozenset(
    name for name in inspect.signature(NormalizeOptions.__init__).parameters if name != "self"
)


def _check_override_names(profile: str, overrides: Mapping[str, Any]) -> None:
    """Отклонить опечатки в именах опций: иначе они молча теряются в **overrides."""
    unknown = sorted(set(overrides) - OPTION_NAMES)
    if unknown:
        raise TypeError(
            f"NormalizeOptions.{profile}() got unexpected keyword argument(s): "
            f"{', '.join(repr(name) for name in unknown)}"
        )
