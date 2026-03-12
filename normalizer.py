from __future__ import annotations

import re
from pathlib import Path

from ._morph import get_morph
from .abbreviations import expand_abbreviations
from .caps import normalize_caps_lines, normalize_first_word_caps
from .dates_time import (
    normalize_dates,
    normalize_dates_and_time,
    normalize_text_dates,
    normalize_time,
)
from .dictionary import apply_dictionary_rules
from .latinization import DEFAULT_DICTIONARIES_PATH, apply_latinization
from .numbering import convert_bracketed_numbers, convert_line_numbering
from .numerals import (
    ALL_UNITS,
    normalize_all_digits_everywhere,
    normalize_cardinal_numerals,
    normalize_decimals,
    normalize_fractions,
    normalize_greek_letters,
    normalize_hyphenated_words,
    normalize_math_symbols,
    normalize_numeric_unit_ranges,
    normalize_numerals,
    normalize_ordinals,
    normalize_remaining_post_numeral_abbreviations,
    normalize_standalone_currency,
)
from .options import NormalizeOptions
from .preprocess_utils import (
    SLASH_FIX_PATTERN,
    apply_cleanup_replacements,
    clean_numbers,
    normalize_linebreaks,
    normalize_ascii_quote_pairs,
    normalize_punctuation_spacing,
    expand_years_ago_abbreviation,
    normalize_spaced_hyphens,
    normalize_unicode_fractions,
    remove_decorative_separators,
    remove_numeric_footnotes,
    restore_paragraph_breaks,
    restore_letter_hyphens,
    protect_letter_hyphens,
    protect_negative_numbers,
)
from .roman_numerals import normalize_roman
from .years import normalize_numeric_ranges, normalize_years

PARTICLE_PATTERN = re.compile(
    r"(?<=[а-яА-ЯёЁ])\s*[–—―]\s*(?=(?:то|либо|нибудь|ка|таки|де|с)\b)",
    re.IGNORECASE,
)

GLUED_PREPOSITIONS = {
    "до",
    "по",
    "от",
    "из",
    "с",
    "со",
    "к",
    "ко",
    "в",
    "во",
    "на",
    "у",
    "о",
    "об",
    "обо",
    "при",
    "за",
    "под",
    "над",
    "без",
    "для",
    "ради",
    "через",
    "сквозь",
    "вдоль",
    "мимо",
    "кроме",
    "вместо",
    "против",
    "среди",
    "между",
    "перед",
    "пред",
    "близ",
    "около",
    "свыше",
}


class PipelineNormalizer:
    """Fixed-order Russian normalization pipeline with toggleable stages."""

    def __init__(self, options: NormalizeOptions | None = None) -> None:
        self.options = options or NormalizeOptions()

    @property
    def dictionaries_path(self) -> Path:
        return self.options.dictionaries_path or DEFAULT_DICTIONARIES_PATH

    def run_stage(self, stage: str, text: str) -> str:
        handlers = {
            "preprocess": self.run_preprocess,
            "roman": self.run_roman,
            "years": self.run_years,
            "dates_time": self.run_dates_time,
            "numerals": self.run_numerals,
            "abbreviations": self.run_abbreviations,
            "dictionary": self.run_dictionary,
            "latinization": self.run_latinization,
            "finalize": self.run_finalize,
        }
        try:
            handler = handlers[stage]
        except KeyError as exc:
            available = ", ".join(sorted(handlers))
            raise ValueError(
                f"Unknown stage '{stage}'. Available stages: {available}"
            ) from exc
        return handler(text)

    def normalize_text(self, text: str) -> str:
        if text.strip().startswith("+"):
            text = " " + text.lstrip()

        text = normalize_linebreaks(text, keep_paragraph_placeholders=True)
        text = protect_letter_hyphens(text)
        text = text.replace("◦", " ")
        text = remove_decorative_separators(text)
        text = re.sub(r"(?:[*=_~+#\-\xad\u2010-\u2015]\s*){5,}", " ", text)
        text = re.sub(r"(?:\*\s*){3,}", " ", text)
        text = text.replace("[", "(").replace("]", ")")
        text = SLASH_FIX_PATTERN.sub(" ", text)
        text = normalize_ascii_quote_pairs(text)
        text = expand_years_ago_abbreviation(text)
        text = protect_negative_numbers(text)
        text = normalize_spaced_hyphens(text)
        text = convert_bracketed_numbers(text, self.options)
        text = convert_line_numbering(text)
        text = normalize_roman(text, self.options)
        text = normalize_caps_lines(
            text, enabled=self.options.enable_caps_normalization
        )
        text = normalize_first_word_caps(
            text, enabled=self.options.enable_first_word_decap
        )
        text = PARTICLE_PATTERN.sub("-", text)
        text = apply_cleanup_replacements(text)
        text = normalize_unicode_fractions(text)
        text = text.translate(
            str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉", "01234567890123456789")
        )
        text = re.sub(r"([$€₽])\s?(\d+(?:[.,]\d+)?)", r"\2\1", text)
        text = re.sub(r"(\d)°", r"\1 °", text)
        text = clean_numbers(text)
        text = self._fix_glued_numbers(text)
        text = restore_letter_hyphens(text)

        if self.options.enable_year_normalization:
            text = normalize_years(text, self.options)
        text = normalize_numeric_ranges(text)

        if self.options.enable_dates_time_normalization:
            text = normalize_text_dates(text)
            text = normalize_dates(text)
            text = normalize_time(text)

        text = normalize_decimals(text)
        text = normalize_fractions(text)

        if self.options.enable_numeral_normalization:
            text = normalize_hyphenated_words(text)
            text = normalize_ordinals(text)
            text = normalize_numeric_unit_ranges(text)
            text = normalize_cardinal_numerals(text)
            text = normalize_remaining_post_numeral_abbreviations(text)
            text = normalize_greek_letters(text)
            text = normalize_math_symbols(text)
            text = normalize_standalone_currency(text)

        text = remove_numeric_footnotes(text, keep_paragraph_placeholders=True)
        text = normalize_all_digits_everywhere(text)
        text = expand_abbreviations(text, self.options)
        text = self.run_latinization(text)
        text = self.run_dictionary(text)
        return self.run_finalize(text)

    def run_preprocess(
        self, text: str, keep_paragraph_placeholders: bool = False
    ) -> str:
        if text.strip().startswith("+"):
            text = " " + text.lstrip()

        text = normalize_linebreaks(
            text, keep_paragraph_placeholders=keep_paragraph_placeholders
        )
        text = protect_letter_hyphens(text)
        text = text.replace("◦", " ")
        text = remove_decorative_separators(text)
        text = re.sub(r"(?:[*=_~+#\-\xad\u2010-\u2015]\s*){5,}", " ", text)
        text = re.sub(r"(?:\*\s*){3,}", " ", text)
        text = text.replace("[", "(").replace("]", ")")
        text = SLASH_FIX_PATTERN.sub(" ", text)
        text = normalize_ascii_quote_pairs(text)
        text = normalize_punctuation_spacing(text)
        text = expand_years_ago_abbreviation(text)
        text = protect_negative_numbers(text)
        text = normalize_spaced_hyphens(text)
        text = convert_bracketed_numbers(text, self.options)
        text = convert_line_numbering(text)
        text = normalize_caps_lines(
            text, enabled=self.options.enable_caps_normalization
        )
        text = normalize_first_word_caps(
            text, enabled=self.options.enable_first_word_decap
        )
        text = PARTICLE_PATTERN.sub("-", text)
        text = apply_cleanup_replacements(text)
        text = normalize_unicode_fractions(text)
        text = text.translate(
            str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉", "01234567890123456789")
        )
        text = re.sub(r"([$€₽])\s?(\d+(?:[.,]\d+)?)", r"\2\1", text)
        text = re.sub(r"(\d)°", r"\1 °", text)
        text = clean_numbers(text)
        text = self._fix_glued_numbers(text)
        text = restore_letter_hyphens(text)
        return remove_numeric_footnotes(
            text, keep_paragraph_placeholders=keep_paragraph_placeholders
        )

    def run_roman(self, text: str) -> str:
        return normalize_roman(text, self.options)

    def run_years(self, text: str) -> str:
        text = normalize_years(text, self.options)
        return normalize_numeric_ranges(text)

    def run_dates_time(self, text: str) -> str:
        if not self.options.enable_dates_time_normalization:
            return text
        text = normalize_dates_and_time(text, self.options)
        text = normalize_decimals(text)
        return normalize_fractions(text)

    def run_numerals(self, text: str) -> str:
        if not self.options.enable_numeral_normalization:
            return text
        text = normalize_hyphenated_words(text)
        text = normalize_ordinals(text)
        return normalize_numerals(text, self.options)

    def run_abbreviations(self, text: str) -> str:
        return expand_abbreviations(text, self.options)

    def run_dictionary(self, text: str) -> str:
        return apply_dictionary_rules(
            text,
            enabled=self.options.enable_dictionary_normalization,
            dictionaries_path=self.dictionaries_path,
            include_only_files=self.options.dictionary_include_files,
            exclude_files=self.options.dictionary_exclude_files,
        )

    def run_latinization(self, text: str) -> str:
        return apply_latinization(
            text,
            enabled=self.options.enable_latinization,
            backend=self.options.latinization_backend,
            dictionaries_path=self.dictionaries_path,
            dictionary_filename=self.options.latin_dictionary_filename,
        )

    def run_finalize(self, text: str) -> str:
        text = normalize_ascii_quote_pairs(text)
        text = normalize_punctuation_spacing(text)
        text = normalize_linebreaks(text, keep_paragraph_placeholders=True)
        return restore_paragraph_breaks(text)

    def _fix_glued_numbers(self, text: str) -> str:
        def fix_glued(match: re.Match[str]) -> str:
            num, word = match.group(1), match.group(2)
            word_lower = word.lower()
            if word_lower in {
                "ти",
                "ми",
                "го",
                "му",
                "м",
                "х",
                "я",
                "е",
                "й",
                "о",
                "а",
            }:
                return f"{num}-{word}"
            if word_lower in ALL_UNITS or word_lower in GLUED_PREPOSITIONS:
                return f"{num} {word}"

            parsed = get_morph().parse(word_lower)[0]
            if "ADJF" in parsed.tag:
                return f"{num}-{word}"
            if "NOUN" in parsed.tag:
                return f"{num} {word}"
            return f"{num}-{word}"

        text = re.sub(r"(?<=[а-яА-ЯёЁa-zA-Z])(\d+)", r" \1", text)
        previous = None
        iteration = 0
        while previous != text and iteration < 5:
            previous = text
            text = re.sub(r"(\d+)([а-яА-ЯёЁa-zA-Z+]{1,})", fix_glued, text)
            iteration += 1
        return text


def preprocess_text(text: str, options: NormalizeOptions | None = None) -> str:
    return PipelineNormalizer(options).run_preprocess(text)
