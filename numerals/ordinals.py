from __future__ import annotations

import re

import num2words

from .._morph import get_morph
from ._constants import HYPHENATED_WORD_PATTERN, ORDINAL_PATTERN
from ._helpers import get_numeral_case, inflect_numeral_string, simple_tokenize


def normalize_hyphenated_words(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        morph = get_morph()
        num_str = match.group(1)
        word = match.group(2)
        word_lower = word.lower()
        ordinal_suffixes = {"й", "я", "е", "го", "му", "м", "ю", "ее", "ий", "ая", "ое"}
        cardinal_case_suffixes = {"ти", "ми", "х", "мя", "и"}
        if word_lower in ordinal_suffixes:
            return match.group(0)
        if (
            word_lower
            in {
                "ый",
                "ой",
                "й",
                "ого",
                "го",
                "ому",
                "ым",
                "ом",
                "му",
                "е",
                "х",
                "м",
                "ми",
            }
            and int(num_str) > 100
        ):
            return match.group(0)
        try:
            int(num_str)
        except Exception:
            return match.group(0)
        case_from_suffix = None
        if word_lower == "х":
            case_from_suffix = None
        elif word_lower in ("ти", "и"):
            case_from_suffix = "gent"
        elif word_lower in ("ми", "мя"):
            case_from_suffix = "ablt"
        ctx_left = text[max(0, match.start() - 60) : match.start()]
        ctx_right = text[match.end() : match.end() + 60]
        tokens_left = simple_tokenize(ctx_left)
        tokens_right = simple_tokenize(ctx_right)
        context_case = get_numeral_case(
            tokens_left + [num_str] + tokens_right, len(tokens_left)
        )
        if case_from_suffix:
            case = case_from_suffix
        elif word_lower == "х":
            case = context_case if context_case in ("gent", "loct") else "gent"
        else:
            case = context_case
        p_word = morph.parse(word_lower)[0]
        is_adj_like = "ADJF" in p_word.tag or word_lower.endswith(
            (
                "дневный",
                "часовой",
                "минутный",
                "летний",
                "этажный",
                "тонный",
                "процентный",
                "кратный",
                "кратного",
                "кратном",
                "кратных",
            )
        )
        target_case = "gent" if is_adj_like and case == "nomn" else case
        num_words = inflect_numeral_string(num_str, target_case)
        if word_lower in cardinal_case_suffixes:
            return num_words
        return (
            f"{num_words}{word}"
            if is_adj_like
            else (f"{num_words}" if len(word) <= 3 else f"{num_words} {word}")
        )

    return HYPHENATED_WORD_PATTERN.sub(repl, text)


def normalize_ordinals(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        morph = get_morph()
        num_str = match.group(1)
        suffix = match.group(2).lower()
        try:
            num = int(num_str)
        except ValueError:
            return match.group(0)
        gender = "masc"
        is_cardinal_suffix = suffix in ("ти", "ми")
        ctx_left = text[max(0, match.start() - 60) : match.start()]
        ctx_right = text[match.end() : match.end() + 60]
        tokens_left = simple_tokenize(ctx_left)
        tokens_right = simple_tokenize(ctx_right)
        case = get_numeral_case(
            tokens_left + [num_str] + tokens_right, len(tokens_left)
        )
        if suffix in ("я", "яя"):
            gender = "femn"
        elif suffix in ("е", "ее"):
            gender = "neut"
        elif suffix == "й" and tokens_right:
            p_next = morph.parse(tokens_right[0].strip(".,!?;:"))[0]
            if "femn" in p_next.tag:
                gender = "femn"
                if case == "nomn":
                    case = "gent"
        case_from_suffix = None
        if suffix == "го":
            case_from_suffix = "gent"
        elif suffix == "му":
            case_from_suffix = "datv"
        elif suffix == "й" and case == "nomn" and tokens_right:
            p_next = morph.parse(tokens_right[0].strip(".,!?;:"))[0]
            if "femn" in p_next.tag:
                gender = "femn"
                case_from_suffix = "gent"
        if suffix == "м":
            if tokens_right:
                p_next = morph.parse(tokens_right[0].strip(".,!?;:"))[0]
                case_from_suffix = "loct" if "sing" in p_next.tag else "datv"
            else:
                case_from_suffix = "loct"
        case = case_from_suffix or case
        plural = suffix in ("х", "ми", "е", "м") and not (
            suffix == "м" and case == "loct"
        )
        cases_map = {
            "nomn": "nominative",
            "gent": "genitive",
            "datv": "dative",
            "accs": "accusative",
            "ablt": "instrumental",
            "loct": "prepositional",
        }
        gender_map = {"masc": "m", "femn": "f", "neut": "n"}
        if case in cases_map:
            try:
                kwargs = {"case": cases_map[case]}
                if not is_cardinal_suffix:
                    kwargs["to"] = "ordinal"
                if plural:
                    kwargs["plural"] = True
                elif gender in gender_map and not is_cardinal_suffix:
                    kwargs["gender"] = gender_map[gender]
                return num2words.num2words(num, lang="ru", **kwargs) + " "
            except Exception:
                pass
        try:
            ordinal = num2words.num2words(
                num, lang="ru", to="cardinal" if is_cardinal_suffix else "ordinal"
            )
        except Exception:
            return match.group(0)
        words = ordinal.split()
        if not words:
            return ordinal
        parsed = morph.parse(words[-1])
        if parsed:
            p = parsed[0]
            target_tags = {case}
            if plural:
                target_tags.add("plur")
            elif gender:
                target_tags.add(gender)
            inflected = p.inflect(target_tags)
            if inflected:
                words[-1] = inflected.word
        return " ".join(words) + " "

    return ORDINAL_PATTERN.sub(repl, text)
