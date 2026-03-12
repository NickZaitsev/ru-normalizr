from __future__ import annotations

import logging
import pickle
import re
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class DictionaryNormalizer:
    """Apply .dic substitution rules in filename order."""

    def __init__(
        self,
        dictionaries_path: str | Path | None = None,
        exclude_files: list[str] | None = None,
        include_only_files: list[str] | None = None,
    ) -> None:
        self.dictionaries_path = (
            Path(dictionaries_path)
            if dictionaries_path
            else Path(__file__).resolve().parent / "dictionaries"
        )
        self.exclude_files = set(exclude_files or [])
        self.include_only_files = set(include_only_files or [])
        self._file_rules: list[tuple[str, Any]] = []
        self._total_dic = 0

        if not self._try_load_from_cache():
            self._load_all_dictionaries()
            self._save_to_cache()

    def _get_cache_path(self) -> Path:
        base = "dictionaries"
        if self.include_only_files:
            import hashlib

            digest = hashlib.md5(
                ",".join(sorted(self.include_only_files)).encode()
            ).hexdigest()[:8]
            base += f"_include_{digest}"
        elif self.exclude_files:
            import hashlib

            digest = hashlib.md5(
                ",".join(sorted(self.exclude_files)).encode()
            ).hexdigest()[:8]
            base += f"_exclude_{digest}"
        return self.dictionaries_path / f"{base}.pkl"

    def _try_load_from_cache(self) -> bool:
        cache_path = self._get_cache_path()
        if not cache_path.exists():
            return False
        try:
            cache_mtime = cache_path.stat().st_mtime
            for dic_file in self.dictionaries_path.glob("*.dic"):
                if dic_file.stat().st_mtime > cache_mtime:
                    return False
            with cache_path.open("rb") as fh:
                data = pickle.load(fh)
            if set(data.get("exclude_files", [])) != self.exclude_files:
                return False
            if set(data.get("include_only_files", [])) != self.include_only_files:
                return False
            self._file_rules = data["rules"]
            self._total_dic = data["dic_count"]
            return True
        except Exception as exc:
            logger.warning("Failed to load dictionary cache %s: %s", cache_path, exc)
            return False

    def _save_to_cache(self) -> None:
        try:
            with self._get_cache_path().open("wb") as fh:
                pickle.dump(
                    {
                        "rules": self._file_rules,
                        "dic_count": self._total_dic,
                        "exclude_files": list(self.exclude_files),
                        "include_only_files": list(self.include_only_files),
                    },
                    fh,
                )
        except Exception as exc:
            logger.warning("Failed to save dictionary cache: %s", exc)

    def _load_all_dictionaries(self) -> None:
        if not self.dictionaries_path.exists():
            return
        files = sorted(self.dictionaries_path.glob("*.dic"), key=lambda item: item.name)
        for filepath in files:
            if self.include_only_files and filepath.name not in self.include_only_files:
                continue
            if filepath.name in self.exclude_files:
                continue
            try:
                chunks = self._load_dic_file(filepath)
                if chunks:
                    self._file_rules.append(("dic", chunks))
                    self._total_dic += sum(
                        len(chunk[1]) if chunk[0] != "regex_batch" else len(chunk[1][1])
                        for chunk in chunks
                    )
            except Exception as exc:
                logger.error("Error loading %s: %s", filepath.name, exc)

    def _load_dic_file(self, path: Path) -> list[tuple[str, Any]]:
        chunks: list[tuple[str, Any]] = []
        current_simple: dict[str, str] = {}
        current_regex: list[tuple[re.Pattern[str], str]] = []

        def flush() -> None:
            nonlocal current_simple, current_regex
            if current_simple:
                if len(current_simple) < 1000:
                    try:
                        keys = sorted(current_simple.keys(), key=len, reverse=True)
                        pattern = re.compile(
                            r"(?<!\w)(?:" + "|".join(map(re.escape, keys)) + r")(?!\w)",
                            re.UNICODE | re.IGNORECASE,
                        )
                        chunks.append(("regex_batch", (pattern, current_simple)))
                    except Exception:
                        chunks.append(("simple", current_simple))
                else:
                    chunks.append(("simple", current_simple))
                current_simple = {}
            if current_regex:
                chunks.append(("regex", current_regex))
                current_regex = []

        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.rstrip("\n\r")
                if not line or line.startswith("#"):
                    continue
                idx = line.find("=")
                if idx == -1:
                    continue
                source = line[:idx]
                target = line[idx + 1 :]
                if not source:
                    continue

                is_simple = not source.startswith("$") and not any(
                    char in r"*\[](){}^$.|+?" for char in source
                )
                if is_simple:
                    if current_regex:
                        flush()
                    current_simple[source.lower()] = target
                    continue

                if current_simple:
                    flush()
                try:
                    anchor_start = source.startswith("$")
                    if anchor_start:
                        source = source[1:]
                    if not source:
                        continue
                    pattern_str, replacement = self._dic_pattern_to_regex(
                        source, target, anchor_start
                    )
                    current_regex.append(
                        (
                            re.compile(pattern_str, re.UNICODE | re.IGNORECASE),
                            replacement,
                        )
                    )
                except re.error:
                    continue

        flush()
        return chunks

    def _dic_pattern_to_regex(
        self, source: str, target: str, anchor_start: bool = False
    ) -> tuple[str, str]:
        parts = source.split("*")
        regex_parts: list[str] = []
        replacement_parts = [target]
        total_groups = 0

        if parts[0] == "":
            regex_parts.append(r"(\S*)")
            total_groups += 1
            replacement_parts.insert(0, r"\g<1>")
            parts.pop(0)
        elif parts[0] and parts[0][0].isalnum():
            regex_parts.append(r"(?<!\w)")

        has_suffix_wildcard = False
        if parts and parts[-1] == "":
            has_suffix_wildcard = True
            parts.pop()

        for index, part in enumerate(parts):
            if index > 0:
                regex_parts.append(r"\S*")
            if part:
                regex_parts.append(re.escape(part))

        if has_suffix_wildcard:
            regex_parts.append(r"(\S*)")
            total_groups += 1
            replacement_parts.append(f"\\g<{total_groups}>")
        elif parts and parts[-1] and parts[-1][-1].isalnum():
            regex_parts.append(r"(?!\w)")

        pattern = "".join(regex_parts)
        if anchor_start:
            pattern = "^" + pattern
        return pattern, "".join(replacement_parts)

    def _apply_simple_chunk(self, text: str, mapping: dict[str, str]) -> str:
        tokens = re.split(r"(\s+)", text)
        modified = False
        for index in range(0, len(tokens), 2):
            token = tokens[index]
            if not token:
                continue
            replacement = mapping.get(token.lower())
            if replacement is not None:
                tokens[index] = replacement
                modified = True
        return "".join(tokens) if modified else text

    def _apply_dic_rules(self, text: str, chunks: list[tuple[str, Any]]) -> str:
        for _ in range(1):
            prev = text
            for chunk_type, chunk_data in chunks:
                if chunk_type == "simple":
                    text = self._apply_simple_chunk(text, chunk_data)
                elif chunk_type == "regex_batch":
                    pattern, mapping = chunk_data
                    text = pattern.sub(
                        lambda match: mapping.get(match.group().lower(), match.group()),
                        text,
                    )
                else:
                    for pattern, replacement in chunk_data:
                        try:
                            text = pattern.sub(replacement, text)
                        except Exception:
                            continue
            if text == prev:
                break
        return text

    def apply(self, text: str, *, strip_unmatched_latin: bool = False) -> str:
        if not self._file_rules:
            return text
        for file_type, rules in self._file_rules:
            if file_type == "dic":
                text = self._apply_dic_rules(text, rules)
        if strip_unmatched_latin:
            return re.sub(r"[A-Za-z]", "", text)
        return text

    def get_rule_count(self) -> int:
        return self._total_dic


_normalizers: dict[
    tuple[str, tuple[str, ...], tuple[str, ...]], DictionaryNormalizer
] = {}
_normalizers_lock = threading.Lock()


def get_dictionary_normalizer(
    dictionaries_path: str | Path | None = None,
    *,
    exclude_files: list[str] | None = None,
    include_only_files: list[str] | None = None,
) -> DictionaryNormalizer:
    key = (
        str(
            Path(dictionaries_path)
            if dictionaries_path
            else Path(__file__).resolve().parent / "dictionaries"
        ),
        tuple(sorted(exclude_files or [])),
        tuple(sorted(include_only_files or [])),
    )
    if key not in _normalizers:
        with _normalizers_lock:
            if key not in _normalizers:
                _normalizers[key] = DictionaryNormalizer(
                    dictionaries_path=key[0],
                    exclude_files=list(key[1]),
                    include_only_files=list(key[2]),
                )
    return _normalizers[key]


def apply_dictionary_rules(
    text: str,
    *,
    enabled: bool,
    dictionaries_path: str | Path | None = None,
    include_only_files: tuple[str, ...] = (),
    exclude_files: tuple[str, ...] = (),
    strip_unmatched_latin: bool = False,
) -> str:
    if not enabled:
        return text
    normalizer = get_dictionary_normalizer(
        dictionaries_path=dictionaries_path,
        include_only_files=list(include_only_files),
        exclude_files=list(exclude_files),
    )
    return normalizer.apply(text, strip_unmatched_latin=strip_unmatched_latin)
