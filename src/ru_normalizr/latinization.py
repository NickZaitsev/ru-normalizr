from __future__ import annotations

import re
import threading
import warnings
from collections import OrderedDict
from functools import lru_cache
from pathlib import Path

from .constants import LetterVowelMode, resolve_letter_name
from .dictionary import DictionaryNormalizer
from .text_scan import compile_scan

DEFAULT_DICTIONARIES_PATH = Path(__file__).resolve().parent / "dictionaries"
DEFAULT_LATINIZATION_DICTIONARIES_PATH = DEFAULT_DICTIONARIES_PATH / "latinization"
# Типографский апостроф «’» входит в слово только между буквами — иначе это
# закрывающая кавычка, и съедать её нельзя.
LATIN_TOKEN_PATTERN = compile_scan(r"[A-Za-z][A-Za-z'\-]*(?:’[A-Za-z][A-Za-z'\-]*)*")
ALPHANUMERIC_SUFFIX_LETTER_PATTERN = compile_scan(
    r"(?:(?<=\d)|(?<=[А-Яа-яЁё]-))(?P<letter>[A-Za-z])\b"
    r"|(?<![\w'’-])(?P<label>[A-Za-z])(?![\w'’-])"
)
#: Слово рядом с одиночной латинской буквой: оно решает, метка перед нами или
#: английское слово в английской фразе.
_NEIGHBOUR_WORD_PATTERN = compile_scan(r"[A-Za-zА-Яа-яЁё]+")
#: Сколько знаков просматривать в поисках соседнего слова: между буквой-меткой
#: и словом стоят пробел, скобка или кавычка, а не целое предложение.
_NEIGHBOUR_WORD_WINDOW = 48


def _reads_as_letter_label(text: str, start: int, end: int) -> bool:
    """Одиночная латинская буква в русской фразе — метка.

    Английский артикль стоит внутри английской фразы, и рядом с ним латинские
    слова; у метки соседи русские — «вариант A лучше». Латинский сосед с любой
    стороны отменяет чтение именем буквы: там буква входит в английскую фразу
    или в имя с инициалом («J. Smith»).
    """
    left = _NEIGHBOUR_WORD_PATTERN.findall(
        text[max(0, start - _NEIGHBOUR_WORD_WINDOW) : start]
    )
    right = _NEIGHBOUR_WORD_PATTERN.findall(text[end : end + _NEIGHBOUR_WORD_WINDOW])
    neighbours = left[-1:] + right[:1]
    if not neighbours:
        return False
    return not any(word[0].isascii() for word in neighbours)
IPA_BATCH_SIZE = 800
IPA_BATCH_THRESHOLD = 24
DICTIONARY_FALLBACK_BATCH_THRESHOLD = 8
LATINIZATION_WORD_CACHE_SIZE = 50000

_ipa_word_cache: OrderedDict[str, str] = OrderedDict()
_fallback_word_cache: OrderedDict[tuple[str, str, str], str] = OrderedDict()
_word_cache_lock = threading.RLock()

_ipa_backend_warning_lock = threading.Lock()
_ipa_backend_warning_emitted = False


def _warn_missing_ipa_backend() -> None:
    """Warn once that the ``eng_to_ipa`` backend is unavailable."""
    global _ipa_backend_warning_emitted
    with _ipa_backend_warning_lock:
        if _ipa_backend_warning_emitted:
            return
        _ipa_backend_warning_emitted = True
    warnings.warn(
        "The 'ipa' latinization backend requires the 'eng_to_ipa' package, "
        "which ships with ru-normalizr by default but is not importable now. "
        "Reinstall it with 'pip install eng_to_ipa'. Falling back to the "
        "dictionary latinization backend.",
        RuntimeWarning,
        stacklevel=2,
    )

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


def _ipa_convert_cached(word: str) -> str:
    return _ipa_convert_words((word,))[word]


def _read_ipa_word_cache(words: tuple[str, ...]) -> tuple[dict[str, str], tuple[str, ...]]:
    resolved: dict[str, str] = {}
    missing: list[str] = []
    with _word_cache_lock:
        for word in words:
            cached = _ipa_word_cache.get(word)
            if cached is None:
                missing.append(word)
                continue
            _ipa_word_cache.move_to_end(word)
            resolved[word] = cached
    return resolved, tuple(missing)


def _store_ipa_word_cache(results: dict[str, str]) -> None:
    with _word_cache_lock:
        for word, converted in results.items():
            _ipa_word_cache[word] = converted
            _ipa_word_cache.move_to_end(word)
        while len(_ipa_word_cache) > LATINIZATION_WORD_CACHE_SIZE:
            _ipa_word_cache.popitem(last=False)


def _ipa_convert_words(words: tuple[str, ...]) -> dict[str, str]:
    resolved, missing = _read_ipa_word_cache(words)
    if not missing:
        return resolved

    import eng_to_ipa as ipa

    if len(missing) <= IPA_BATCH_THRESHOLD:
        converted = tuple(_select_ipa_result(ipa.convert(word)) for word in missing)
    else:
        converted = _ipa_convert_batch(missing)
    fresh_results = dict(zip(missing, converted, strict=True))
    _store_ipa_word_cache(fresh_results)
    resolved.update(fresh_results)
    return resolved


def _select_ipa_result(ipa_variants: str | list[str]) -> str:
    if isinstance(ipa_variants, str):
        return ipa_variants
    return ipa_variants[-1] if ipa_variants else ""


def _ipa_convert_batch(words: tuple[str, ...]) -> tuple[str, ...]:
    import eng_to_ipa as ipa

    converted: list[str] = []
    for start in range(0, len(words), IPA_BATCH_SIZE):
        chunk = list(words[start : start + IPA_BATCH_SIZE])
        ipa_chunks = ipa.ipa_list(chunk, keep_punct=True)
        converted.extend(_select_ipa_result(ipa_variants) for ipa_variants in ipa_chunks)
    return tuple(converted)


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


def _resolve_unknown_latin_fallbacks(
    words: tuple[str, ...], dictionaries_path: str, filename: str
) -> dict[str, str]:
    unique_words = tuple(dict.fromkeys(words))
    if not unique_words:
        return {}

    resolved: dict[str, str] = {}
    missing: list[str] = []
    with _word_cache_lock:
        for word in unique_words:
            key = (word, dictionaries_path, filename)
            cached = _fallback_word_cache.get(key)
            if cached is None:
                missing.append(word)
                continue
            _fallback_word_cache.move_to_end(key)
            resolved[word] = cached

    if not missing:
        return resolved
    if len(missing) <= DICTIONARY_FALLBACK_BATCH_THRESHOLD:
        fresh_results = {
            word: _resolve_unknown_latin_fallback(word, dictionaries_path, filename)
            for word in missing
        }
    else:
        current = "\n".join(missing)
        resolved_path = Path(dictionaries_path)
        for _ in range(6):
            updated = _apply_dictionary_latinization(current, resolved_path, filename)
            if updated == current:
                break
            current = updated

        resolved_words = current.split("\n")
        if len(resolved_words) != len(missing):
            fresh_results = {
                word: _resolve_unknown_latin_fallback(word, dictionaries_path, filename)
                for word in missing
            }
        else:
            fresh_results = dict(zip(missing, resolved_words, strict=True))

    with _word_cache_lock:
        for word, converted in fresh_results.items():
            key = (word, dictionaries_path, filename)
            _fallback_word_cache[key] = converted
            _fallback_word_cache.move_to_end(key)
        while len(_fallback_word_cache) > LATINIZATION_WORD_CACHE_SIZE:
            _fallback_word_cache.popitem(last=False)
    resolved.update(fresh_results)
    return resolved


def _clear_latinization_word_caches() -> None:
    with _word_cache_lock:
        _ipa_word_cache.clear()
        _fallback_word_cache.clear()
    _resolve_unknown_latin_fallback.cache_clear()


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
    if not include_stress_markers:
        return ipa_text.replace("ˈ", "")
    # Один знак на слово. IPA составных названий несёт по главному ударению на
    # каждую часть («microsoft» → м+айкроус+офт), а синтез читает второй знак как
    # отдельное ударение и ломает слово.
    return _single_stress_per_word(ipa_text)


_WORD_WITH_STRESS_RE = re.compile(r"[^\W\d_]+(?:[ˈ][^\W\d_]+)*", re.UNICODE)


def _single_stress_per_word(text: str) -> str:
    """Заменить ``ˈ`` на ``+``, оставив в каждом слове только первый знак."""

    def one_word(match: re.Match[str]) -> str:
        word = match.group(0)
        head, marker, tail = word.partition("ˈ")
        if not marker:
            return word
        return head + "+" + tail.replace("ˈ", "")

    return _WORD_WITH_STRESS_RE.sub(one_word, text).replace("ˈ", "+")


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
        _warn_missing_ipa_backend()
        return _apply_dictionary_latinization(text, dictionaries_path, filename)

    matches = list(LATIN_TOKEN_PATTERN.finditer(text))
    if not matches:
        return text

    unique_words = tuple(
        dict.fromkeys(match.group(0).lower().replace("’", "'") for match in matches)
    )
    ipa_results = _ipa_convert_words(unique_words)

    replacements: dict[str, str] = {}
    unknown_words: list[str] = []
    for word, ipa_text in ipa_results.items():
        if "*" in ipa_text:
            unknown_words.append(word)
            continue
        replacements[word] = _ipa_to_russian(
            ipa_text, include_stress_markers=include_stress_markers
        )

    if unknown_words:
        # Апостроф в неизвестном слове — элизия («d'orge»): читаем слитно.
        fused = {word: word.replace("'", "") for word in unknown_words}
        retry_targets = tuple(
            dict.fromkeys(fused[word] for word in unknown_words if "'" in word)
        )
        retried = _ipa_convert_words(retry_targets) if retry_targets else {}
        dictionary_words: list[str] = []
        for word in unknown_words:
            ipa_text = retried.get(fused[word], "*")
            if "*" in ipa_text:
                dictionary_words.append(word)
                continue
            replacements[word] = _ipa_to_russian(
                ipa_text, include_stress_markers=include_stress_markers
            )
        if dictionary_words:
            resolved = _resolve_unknown_latin_fallbacks(
                tuple(dict.fromkeys(fused[word] for word in dictionary_words)),
                str(dictionaries_path),
                filename,
            )
            for word in dictionary_words:
                replacements[word] = resolved[fused[word]]

    def replace(match: re.Match[str]) -> str:
        word = match.group(0).lower().replace("’", "'")
        return replacements.get(word, match.group(0))

    return LATIN_TOKEN_PATTERN.sub(replace, text)


def apply_latinization(
    text: str,
    *,
    backend: str,
    dictionaries_path: Path | None = None,
    dictionary_filename: str = "latinization_rules.dic",
    include_stress_markers: bool = False,
    letter_vowel_mode: LetterVowelMode = "single",
) -> str:
    if not re.search(r"[A-Za-z]", text):
        return text

    def letter_name_repl(match: re.Match[str]) -> str:
        letter = match.group("letter")
        if letter is None:
            letter = match.group("label")
            if not _reads_as_letter_label(text, match.start(), match.end()):
                return letter
        return resolve_letter_name(letter, letter_vowel_mode) or letter

    text = ALPHANUMERIC_SUFFIX_LETTER_PATTERN.sub(letter_name_repl, text)

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
