from __future__ import annotations

import re
from pathlib import Path

from ._morph import get_morph
from .abbreviations import expand_abbreviations
from .caps import (
    normalize_caps_lines,
    normalize_first_word_caps,
    normalize_sentence_start_caps,
)
from .dates_time import normalize_dates_and_time
from .dictionary import apply_dictionary_rules
from .latinization import DEFAULT_DICTIONARIES_PATH, apply_latinization
from .numbering import convert_bracketed_numbers, convert_line_numbering
from .numerals import (
    ALL_UNITS,
    normalize_compound_numeric_adjectives,
    normalize_decimals,
    normalize_fractions,
    normalize_hyphenated_words,
    normalize_math_symbols,
    normalize_numerals,
    normalize_ordinals,
)
from .numerals._hyphen import (
    ORDINAL_SUFFIXES,
    normalize_numeric_unit_hyphen_links,
    normalize_spaced_numeric_hyphen_words,
)
from .options import NormalizeOptions
from .preprocess_utils import (
    SLASH_FIX_PATTERN,
    UNIT_SLASH_PLACEHOLDER,
    apply_cleanup_replacements,
    clean_numbers,
    expand_years_ago_abbreviation,
    normalize_ascii_quote_pairs,
    normalize_cyrillic_combining_stress_marks,
    normalize_explicit_dashes,
    normalize_linebreaks,
    normalize_numeric_abbreviations,
    normalize_punctuation_spacing,
    normalize_spaced_ascii_hyphens,
    normalize_unicode_fractions,
    protect_letter_hyphens,
    protect_negative_numbers,
    protect_unit_slashes,
    remove_decorative_separators,
    remove_numeric_footnotes,
    remove_zero_width_formatting,
    restore_letter_hyphens,
    restore_paragraph_breaks,
)
from .roman_numerals import normalize_roman
from .urls import normalize_urls
from .years import normalize_numeric_ranges, normalize_years

PARTICLE_PATTERN = re.compile(
    r"(?<=[а-яА-ЯёЁ])\s*[–—―]\s*(?=(?:то|либо|нибудь|ка|таки|де|с)\b)",
    re.IGNORECASE,
)
DECORATIVE_MARKER_PATTERN = re.compile(r"(?:[*=_~+#\-\xad\u2010-\u2015]\s*){5,}")
ASTERISK_SEPARATOR_PATTERN = re.compile(r"(?:\*\s*){3,}")
CURRENCY_AMOUNT_PATTERN = re.compile(r"([$€₽])\s?(\d+(?:[.,]\d+)?)")
DEGREE_SPACING_PATTERN = re.compile(r"(\d)°")
LEADING_LETTER_DIGIT_PATTERN = re.compile(r"(?<=[а-яА-ЯёЁa-zA-Z])(\d+)")
GLUED_NUMBER_WORD_PATTERN = re.compile(r"(\d+)([а-яА-ЯёЁa-zA-Z+]{1,})")

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
GLUED_NUMERIC_SUFFIXES = ORDINAL_SUFFIXES | {"ти", "ми", "х", "у"}


class PipelineNormalizer:
    """Fixed-order Russian normalization pipeline with toggleable stages."""

    def __init__(self, options: NormalizeOptions | None = None) -> None:
        self.options = options or NormalizeOptions()

    @property
    def dictionaries_path(self) -> Path:
        return self.options.dictionaries_path or DEFAULT_DICTIONARIES_PATH

    def run_stage(self, stage: str, text: str) -> str:
        handlers = {
            "urls": self.run_urls,
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
        text = self.run_urls(text)
        text = self._run_preprocess_steps(
            text,
            keep_paragraph_placeholders=True,
            apply_caps_normalization=False,
        )
        text = self.run_roman(text)
        text = self._run_caps_normalization(text)
        if self.options.remove_links:
            text = remove_numeric_footnotes(
                text,
                keep_paragraph_placeholders=True,
                ignore_interval=self.options.remove_links_ignore_interval,
            )
        else:
            text = normalize_linebreaks(text, keep_paragraph_placeholders=True).strip()
        text = self.run_years(text)
        text = self.run_dates_time(text)
        text = self.run_numerals(text)
        text = self.run_abbreviations(text)
        text = self.run_latinization(text)
        text = self.run_dictionary(text)
        return self.run_finalize(text)

    def run_preprocess(
        self, text: str, keep_paragraph_placeholders: bool = False
    ) -> str:
        text = self._run_preprocess_steps(
            text,
            keep_paragraph_placeholders=keep_paragraph_placeholders,
            apply_caps_normalization=True,
        )
        if self.options.remove_links:
            text = remove_numeric_footnotes(
                text,
                keep_paragraph_placeholders=keep_paragraph_placeholders,
                ignore_interval=self.options.remove_links_ignore_interval,
            )
        else:
            text = normalize_linebreaks(
                text, keep_paragraph_placeholders=keep_paragraph_placeholders
            ).strip()
        return text

    def run_urls(self, text: str) -> str:
        return normalize_urls(text, enabled=self.options.enable_url_normalization)

    def _run_preprocess_steps(
        self,
        text: str,
        *,
        keep_paragraph_placeholders: bool,
        apply_caps_normalization: bool,
    ) -> str:
        if text.strip().startswith("+"):
            text = " " + text.lstrip()

        text = normalize_linebreaks(
            text, keep_paragraph_placeholders=keep_paragraph_placeholders
        )
        text = remove_zero_width_formatting(text)
        text = normalize_cyrillic_combining_stress_marks(text)
        text = protect_letter_hyphens(text)
        text = text.replace("◦", " ")
        text = remove_decorative_separators(text)
        text = DECORATIVE_MARKER_PATTERN.sub(" ", text)
        text = ASTERISK_SEPARATOR_PATTERN.sub(" ", text)
        text = text.replace("[", "(").replace("]", ")")
        text = protect_unit_slashes(text)
        text = SLASH_FIX_PATTERN.sub(" ", text)
        text = text.replace(UNIT_SLASH_PLACEHOLDER, "/")
        text = normalize_ascii_quote_pairs(text)
        text = normalize_punctuation_spacing(text)
        text = expand_years_ago_abbreviation(text)
        text = normalize_numeric_abbreviations(text)
        text = protect_negative_numbers(text)
        text = normalize_explicit_dashes(text)
        text = convert_bracketed_numbers(text, self.options)
        text = convert_line_numbering(text)
        if apply_caps_normalization:
            text = self._run_caps_normalization(text)
        text = PARTICLE_PATTERN.sub("-", text)
        text = apply_cleanup_replacements(text)
        text = normalize_unicode_fractions(text)
        text = text.translate(
            str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉", "01234567890123456789")
        )
        text = CURRENCY_AMOUNT_PATTERN.sub(r"\2\1", text)
        text = DEGREE_SPACING_PATTERN.sub(r"\1 °", text)
        text = clean_numbers(text)
        text = self._fix_glued_numbers(text)
        text = restore_letter_hyphens(text)
        return text

    def _run_caps_normalization(self, text: str) -> str:
        text = normalize_caps_lines(text, enabled=self.options.enable_caps_normalization)
        return normalize_first_word_caps(
            text, enabled=self.options.enable_first_word_decap
        )

    def run_roman(self, text: str) -> str:
        return normalize_roman(text, self.options)

    def run_years(self, text: str) -> str:
        text = normalize_years(text, self.options)
        return normalize_numeric_ranges(text)

    def run_dates_time(self, text: str) -> str:
        if not self.options.enable_dates_time_normalization:
            return text
        return normalize_dates_and_time(text, self.options)

    def run_numerals(self, text: str) -> str:
        if not self.options.enable_numeral_normalization:
            return text
        text = normalize_math_symbols(text)
        text = normalize_spaced_numeric_hyphen_words(text)
        text = normalize_numeric_unit_hyphen_links(text)
        text = normalize_compound_numeric_adjectives(text)
        text = normalize_decimals(text)
        text = normalize_fractions(text)
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
            include_stress_markers=self.options.enable_latinization_stress_marks,
        )

    def run_finalize(self, text: str) -> str:
        text = normalize_ascii_quote_pairs(text)
        text = normalize_spaced_ascii_hyphens(text)
        text = normalize_punctuation_spacing(text)
        text = normalize_linebreaks(text, keep_paragraph_placeholders=True)
        text = normalize_sentence_start_caps(text)
        return restore_paragraph_breaks(text)

    def _classify_glued_numeric_rhs(self, word: str) -> str:
        word_lower = word.lower()
        if word == "k":
            return "thousand_suffix"
        if word_lower in GLUED_NUMERIC_SUFFIXES or word_lower in {"о", "а"}:
            return "hyphen"
        if word_lower in ALL_UNITS or word_lower in GLUED_PREPOSITIONS:
            return "space"

        parsed = get_morph().parse(word_lower)[0]
        if "ADJF" in parsed.tag:
            return "hyphen"
        if "NOUN" in parsed.tag:
            return "space"
        return "hyphen"

    def _fix_glued_numbers(self, text: str) -> str:
        def fix_glued(match: re.Match[str]) -> str:
            num, word = match.group(1), match.group(2)
            rhs_kind = self._classify_glued_numeric_rhs(word)
            if rhs_kind == "thousand_suffix":
                return f"{num} тыс"
            if rhs_kind == "hyphen":
                return f"{num}-{word}"
            if rhs_kind == "space":
                return f"{num} {word}"
            return f"{num}-{word}"

        text = LEADING_LETTER_DIGIT_PATTERN.sub(r" \1", text)
        previous = None
        iteration = 0
        while previous != text and iteration < 5:
            previous = text
            text = GLUED_NUMBER_WORD_PATTERN.sub(fix_glued, text)
            iteration += 1
        return text


def preprocess_text(text: str, options: NormalizeOptions | None = None) -> str:
    return PipelineNormalizer(options).run_preprocess(text)
