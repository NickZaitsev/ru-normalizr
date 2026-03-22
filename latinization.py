from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from .dictionary import DictionaryNormalizer

DEFAULT_DICTIONARIES_PATH = Path(__file__).resolve().parent / "dictionaries"
DEFAULT_LATINIZATION_DICTIONARIES_PATH = DEFAULT_DICTIONARIES_PATH / "latinization"

# Order matters.
IPA_MAP = [
    ("wɝr", "вор"),
    ("wɜːr", "вор"),
    ("wɚr", "вор"),
    ("wɝ", "вор"),
    ("wɜː", "вор"),
    ("wɜ", "вор"),
    ("wɚ", "вор"),
    ("ʧ", "ч"),
    ("ʤ", "дж"),
    ("tʃ", "ч"),
    ("dʒ", "дж"),
    ("aɪ", "ай"),
    ("eɪ", "ей"),
    ("ɔɪ", "ой"),
    ("aʊ", "ау"),
    ("oʊ", "оу"),
    ("əʊ", "оу"),
    ("ju", "ю"),
    ("jʊ", "ю"),
    ("ɪə", "иэ"),
    ("eə", "эа"),
    ("ʊə", "уэ"),
    ("ɝr", "эр"),
    ("ɝ", "эр"),
    ("ɜːr", "эр"),
    ("ɜː", "эр"),
    ("ɚ", "эр"),
    ("ɾ", "т"),
    ("ŋ", "н"),
    ("ʃ", "ш"),
    ("ʒ", "ж"),
    ("θ", "с"),
    ("ð", "з"),
    ("ə", "э"),
    ("ɜ", "э"),
    ("e", "е"),
    ("æ", "э"),
    ("ɪ", "и"),
    ("ɛ", "э"),
    ("i", "и"),
    ("ɒ", "о"),
    ("ɔ", "о"),
    ("ʊ", "у"),
    ("u", "у"),
    ("ʌ", "а"),
    ("a", "а"),
    ("ɑ", "а"),
    ("p", "п"),
    ("b", "б"),
    ("t", "т"),
    ("d", "д"),
    ("k", "к"),
    ("g", "г"),
    ("f", "ф"),
    ("v", "в"),
    ("s", "с"),
    ("z", "з"),
    ("h", "х"),
    ("m", "м"),
    ("n", "н"),
    ("l", "л"),
    ("r", "р"),
    ("j", "й"),
    ("w", "в"),
    ("ʔ", "т"),
    ("ˌ", ""),
]


@lru_cache(maxsize=16)
def _get_latin_dictionary_normalizer(
    dictionaries_path: str, filename: str
) -> DictionaryNormalizer:
    return DictionaryNormalizer(
        dictionaries_path=dictionaries_path,
        include_only_files=[filename],
    )


@lru_cache(maxsize=50000)
def _ipa_convert_cached(word: str) -> str:
    import eng_to_ipa as ipa

    return ipa.convert(word)


@lru_cache(maxsize=50000)
def _resolve_unknown_latin_fallback(
    word: str, dictionaries_path: str, filename: str
) -> str:
    current = word
    resolved_path = Path(dictionaries_path)
    for _ in range(6):
        updated = _apply_dictionary_latinization(current, resolved_path, filename)
        if updated == current:
            break
        current = updated
    return current


def handle_long_vowels(ipa: str) -> str:
    long_vowels = {
        "iː": "ii",
        "uː": "uu",
        "ɑː": "aa",
        "ɔː": "oo",
    }
    for old, new in long_vowels.items():
        ipa = ipa.replace(old, new)
    return ipa


def move_stress_marker_ru(text: str) -> str:
    vowels = set("аеёиоуыэюя")
    result: list[str] = []
    pending = False

    for char in text:
        if char == "ˈ":
            pending = True
            continue
        if pending and char in vowels:
            result.append("ˈ")
            pending = False
        result.append(char)

    return "".join(result)


def _ipa_to_russian(ipa_text: str, include_stress_markers: bool = False) -> str:
    ipa_text = ipa_text.replace("ˌ", "")
    ipa_text = handle_long_vowels(ipa_text)
    for ipa_char, ru_char in IPA_MAP:
        ipa_text = ipa_text.replace(ipa_char, ru_char)
    ipa_text = ipa_text.replace("ː", "")
    ipa_text = move_stress_marker_ru(ipa_text)
    return ipa_text.replace("ˈ", "+" if include_stress_markers else "")


def _apply_dictionary_latinization(
    text: str, dictionaries_path: Path, filename: str
) -> str:
    normalizer = _get_latin_dictionary_normalizer(str(dictionaries_path), filename)
    return normalizer.apply(text, strip_unmatched_latin=False)


def _resolve_latinization_dictionary_source(
    dictionaries_path: Path | None, filename: str
) -> tuple[Path, str]:
    if dictionaries_path is None:
        default_file = DEFAULT_LATINIZATION_DICTIONARIES_PATH / filename
        if default_file.exists():
            return DEFAULT_LATINIZATION_DICTIONARIES_PATH, filename
        return DEFAULT_LATINIZATION_DICTIONARIES_PATH, "latinization_rules.dic"

    direct_path = dictionaries_path / filename
    if direct_path.exists():
        return dictionaries_path, filename

    nested_path = dictionaries_path / "latinization"
    nested_file = nested_path / filename
    if nested_file.exists():
        return nested_path, filename

    default_file = DEFAULT_LATINIZATION_DICTIONARIES_PATH / filename
    if default_file.exists():
        return DEFAULT_LATINIZATION_DICTIONARIES_PATH, filename

    bundled_default_filename = "latinization_rules.dic"
    bundled_default_file = (
        DEFAULT_LATINIZATION_DICTIONARIES_PATH / bundled_default_filename
    )
    if bundled_default_file.exists():
        return DEFAULT_LATINIZATION_DICTIONARIES_PATH, bundled_default_filename

    return dictionaries_path, filename


def _apply_ipa_latinization(
    text: str,
    dictionaries_path: Path,
    filename: str,
    *,
    include_stress_markers: bool,
) -> str:
    try:
        import eng_to_ipa  # noqa: F401
    except ImportError:
        return text

    def replace(match: re.Match[str]) -> str:
        word = match.group(0)
        ipa_text = _ipa_convert_cached(word.lower())
        if "*" in ipa_text:
            return _resolve_unknown_latin_fallback(
                word, str(dictionaries_path), filename
            )
        return _ipa_to_russian(
            ipa_text, include_stress_markers=include_stress_markers
        )

    return re.sub(r"[A-Za-z][A-Za-z'\-]*", replace, text)


def apply_latinization(
    text: str,
    *,
    enabled: bool,
    backend: str,
    dictionaries_path: Path | None = None,
    dictionary_filename: str = "latinization_rules.dic",
    include_stress_markers: bool = False,
) -> str:
    if not enabled or not re.search(r"[A-Za-z]", text):
        return text

    dict_path, resolved_filename = _resolve_latinization_dictionary_source(
        dictionaries_path, dictionary_filename
    )
    backend_name = backend.lower()
    if backend_name == "dictionary":
        return _apply_dictionary_latinization(text, dict_path, resolved_filename)
    if backend_name == "ipa":
        return _apply_ipa_latinization(
            text,
            dict_path,
            resolved_filename,
            include_stress_markers=include_stress_markers,
        )
    return text
