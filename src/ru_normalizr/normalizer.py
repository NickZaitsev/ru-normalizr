from __future__ import annotations

import re
from pathlib import Path

from ._morph import first_parse_required
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
    _contains_numeral_candidates,
    normalize_compound_numeric_adjectives,
    normalize_decimals,
    normalize_fractions,
    normalize_hyphenated_words,
    normalize_math_symbols,
    normalize_numerals,
    normalize_numeric_suffixes,
    normalize_versions,
)
from .numerals._constants import is_unit_token
from .numerals._hyphen import (
    normalize_numeric_unit_hyphen_links,
    normalize_spaced_numeric_hyphen_words,
)
from .numerals.numeric_suffixes import NUMERIC_SUFFIXES
from .options import NormalizeOptions
from .preprocess_utils import (
    SLASH_FIX_PATTERN,
    UNIT_SLASH_PLACEHOLDER,
    apply_cleanup_replacements,
    clean_numbers,
    cleanup_malformed_punctuation,
    expand_years_ago_abbreviation,
    normalize_ascii_quote_pairs,
    normalize_cyrillic_combining_stress_marks,
    normalize_explicit_dashes,
    normalize_linebreaks,
    normalize_numeric_abbreviations,
    normalize_punctuation_spacing,
    normalize_spaced_ascii_hyphens,
    normalize_unary_plus_numbers,
    normalize_unicode_fractions,
    protect_binary_math_operators,
    protect_letter_hyphens,
    protect_negative_numbers,
    protect_unit_slashes,
    remove_decorative_separators,
    remove_numeric_footnotes,
    remove_zero_width_formatting,
    restore_binary_math_operators,
    restore_letter_hyphens,
)
from .roman_numerals import normalize_roman
from .urls import ProtectedUrls, normalize_urls, protect_urls
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
GLUED_NUMERIC_SUFFIXES = NUMERIC_SUFFIXES
_GLUED_SUFFIX_ALTERNATION = "|".join(
    re.escape(suffix)
    for suffix in sorted(NUMERIC_SUFFIXES, key=lambda value: (-len(value), value))
)
EMBEDDED_NUMERIC_SUFFIX_CODE_PATTERN = re.compile(
    rf"(?<=[а-яА-ЯёЁa-zA-Z])\d+-?(?:{_GLUED_SUFFIX_ALTERNATION})(?!\w)",
    re.IGNORECASE | re.UNICODE,
)
STRUCTURED_NUMERIC_SUFFIX_PATTERN = re.compile(
    rf"(?:"
    rf"(?<!\w)[а-яА-ЯёЁa-zA-Z][а-яА-ЯёЁa-zA-Z\d_]*\d+"
    rf"-?(?:{_GLUED_SUFFIX_ALTERNATION})(?!\w)"
    rf"|(?<![\w.,-])\d+[.,]\d+-(?:{_GLUED_SUFFIX_ALTERNATION})(?!\w)"
    rf")",
    re.IGNORECASE | re.UNICODE,
)


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
        protected_urls = ProtectedUrls(text)
        if not self.options.enable_url_normalization:
            protected_urls = protect_urls(text)
            text = protected_urls.text
        text = self.run_urls(text)
        text = self._run_preprocess_steps(
            text,
            apply_caps_normalization=False,
        )
        text = self.run_roman(text)
        text = self._run_caps_normalization(text)
        if self.options.remove_links:
            text = remove_numeric_footnotes(
                text,
                ignore_interval=self.options.remove_links_ignore_interval,
            )
        else:
            text = normalize_linebreaks(text).strip()
        # A full date is the specific case and a bare year the general one, so
        # dates_time must claim "15.03.2021 года" before the years stage takes
        # the "2021 года" out of it and strands the "15.03." for the numerals
        # stage to misread as a decimal fraction.
        text = self.run_dates_time(text)
        text = self.run_years(text)
        text = self.run_numerals(text)
        text = self.run_abbreviations(text)
        # A dictionary rule is an explicit instruction and latinization is a
        # guess, so the dictionary goes first. Running it second left it unable
        # to match any Latin token in TTS mode, because latinization had already
        # rewritten the token into Cyrillic.
        text = self.run_dictionary(text)
        text = self.run_latinization(text)
        return protected_urls.restore(self.run_finalize(text))

    def run_preprocess(
        self, text: str, keep_paragraph_placeholders: bool = False
    ) -> str:
        # Retained for compatibility with the established public method signature.
        del keep_paragraph_placeholders
        text = self._run_preprocess_steps(
            text,
            apply_caps_normalization=True,
        )
        if self.options.remove_links:
            text = remove_numeric_footnotes(
                text,
                ignore_interval=self.options.remove_links_ignore_interval,
            )
        else:
            text = normalize_linebreaks(text).strip()
        return text

    def run_urls(self, text: str) -> str:
        return normalize_urls(text, enabled=self.options.enable_url_normalization)

    def _run_preprocess_steps(
        self,
        text: str,
        *,
        apply_caps_normalization: bool,
    ) -> str:
        if text.strip().startswith("+"):
            text = " " + text.lstrip()

        text = normalize_linebreaks(text)
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
        if self.options.enable_years_ago_expansion:
            text = expand_years_ago_abbreviation(text)
        text = normalize_numeric_abbreviations(text)
        text = normalize_unary_plus_numbers(text)
        text = protect_negative_numbers(text)
        text = normalize_explicit_dashes(text)
        text = convert_bracketed_numbers(text, self.options)
        text = convert_line_numbering(text)
        if apply_caps_normalization:
            text = self._run_caps_normalization(text)
        text = PARTICLE_PATTERN.sub("-", text)
        text = protect_binary_math_operators(text)
        text = apply_cleanup_replacements(text)
        text = normalize_unicode_fractions(text)
        text = text.translate(
            str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹₀₁₂₃₄₅₆₇₈₉", "01234567890123456789")
        )
        text = CURRENCY_AMOUNT_PATTERN.sub(r"\2\1", text)
        text = DEGREE_SPACING_PATTERN.sub(r"\1 °", text)
        text = clean_numbers(text)
        text = self._fix_glued_numbers(text)
        text = restore_binary_math_operators(text)
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
        if not any(char.isdecimal() for char in text):
            return text
        text = normalize_years(text, self.options)
        return normalize_numeric_ranges(text)

    def run_dates_time(self, text: str) -> str:
        if not self.options.enable_dates_time_normalization:
            return text
        return normalize_dates_and_time(text, self.options)

    def run_numerals(self, text: str) -> str:
        if not self.options.enable_numeral_normalization:
            return text
        if not _contains_numeral_candidates(text):
            return normalize_numerals(text, self.options)
        protected_tokens: list[str] = []
        token_placeholders: list[str] = []

        def protect_structured_token(match: re.Match[str]) -> str:
            if len(protected_tokens) >= 0x20000:
                return match.group(0)
            protected_tokens.append(match.group(0))
            placeholder = chr(0xF0000 + len(protected_tokens) - 1)
            token_placeholders.append(placeholder)
            return placeholder

        text = STRUCTURED_NUMERIC_SUFFIX_PATTERN.sub(protect_structured_token, text)
        text = normalize_math_symbols(text)
        text = normalize_spaced_numeric_hyphen_words(text)
        text = normalize_numeric_unit_hyphen_links(text)
        text = normalize_compound_numeric_adjectives(text)
        text = normalize_versions(text)
        text = normalize_decimals(text)
        text = normalize_fractions(text)
        text = normalize_numeric_suffixes(
            text,
            capitalize_text_start=self.options.enable_caps_normalization,
        )
        text = normalize_hyphenated_words(text, include_numeric_suffixes=False)
        text = normalize_numerals(text, self.options)
        for placeholder, token in zip(token_placeholders, protected_tokens, strict=True):
            text = text.replace(placeholder, token)
        return text

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
            letter_vowel_mode=self.options.letter_vowel_mode,
        )

    def run_finalize(self, text: str) -> str:
        text = normalize_ascii_quote_pairs(text)
        text = normalize_spaced_ascii_hyphens(text)
        text = normalize_punctuation_spacing(text)
        text = normalize_linebreaks(text)
        text = normalize_sentence_start_caps(text)
        if self.options.cleanup_malformed_punctuation:
            text = cleanup_malformed_punctuation(text)
        return text

    def _classify_glued_numeric_rhs(self, word: str) -> str:
        word_lower = word.lower()
        if word == "k":
            return "thousand_suffix"
        if word_lower in GLUED_NUMERIC_SUFFIXES or word_lower in {"о", "а"}:
            return "hyphen"
        if is_unit_token(word) or word_lower in GLUED_PREPOSITIONS:
            return "space"

        parsed = first_parse_required(word_lower)
        if "ADJF" in parsed.tag:
            return "hyphen"
        if "NOUN" in parsed.tag:
            return "space"
        return "hyphen"

    def _fix_glued_numbers(self, text: str) -> str:
        protected_codes: list[str] = []

        def protect_code(match: re.Match[str]) -> str:
            protected_codes.append(match.group(0))
            return f"\ue010{len(protected_codes) - 1:x}\ue011"

        def fix_glued(match: re.Match[str]) -> str:
            num, word = match.group(1), match.group(2)
            start = match.start()
            previous_is_letter = start > 0 and text[start - 1].isalpha()
            previous_is_spaced_letter = (
                start > 1 and text[start - 1].isspace() and text[start - 2].isalpha()
            )
            embedded_in_alphanumeric_code = (
                (previous_is_letter or previous_is_spaced_letter)
                and len(word) == 1
            )
            rhs_kind = (
                "hyphen"
                if embedded_in_alphanumeric_code
                else self._classify_glued_numeric_rhs(word)
            )
            if rhs_kind == "thousand_suffix":
                return f"{num} тыс"
            if rhs_kind == "hyphen":
                return f"{num}-{word}"
            if rhs_kind == "space":
                return f"{num} {word}"
            return f"{num}-{word}"

        text = EMBEDDED_NUMERIC_SUFFIX_CODE_PATTERN.sub(protect_code, text)
        text = LEADING_LETTER_DIGIT_PATTERN.sub(r" \1", text)
        previous = None
        iteration = 0
        while previous != text and iteration < 5:
            previous = text
            text = GLUED_NUMBER_WORD_PATTERN.sub(fix_glued, text)
            iteration += 1
        for index, code in enumerate(protected_codes):
            text = text.replace(f"\ue010{index:x}\ue011", code)
        return text


def preprocess_text(text: str, options: NormalizeOptions | None = None) -> str:
    return PipelineNormalizer(options).run_preprocess(text)
