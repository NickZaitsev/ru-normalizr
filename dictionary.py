from __future__ import annotations

import logging
import re
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

def _compile_simple_mapping_patterns(
    mapping: dict[str, str],
) -> list[tuple[re.Pattern[str], str]]:
    patterns: list[tuple[re.Pattern[str], str]] = []
    for key in sorted(mapping.keys(), key=len, reverse=True):
        patterns.append(
            (
                re.compile(
                    rf"(?<!\w){re.escape(key)}(?!\w)",
                    re.UNICODE | re.IGNORECASE,
                ),
                mapping[key],
            )
        )
    return patterns


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
        self._runtime_file_rules: list[tuple[str, Any]] = []
        self._total_dic = 0

        self._load_all_dictionaries()
        self._build_runtime_rules()

    def _load_all_dictionaries(self) -> None:
        if not self.dictionaries_path.exists():
            return
        files = sorted(self.dictionaries_path.rglob("*.dic"))
        for filepath in files:
            relative_name = filepath.relative_to(self.dictionaries_path).as_posix()
            if not self.include_only_files and relative_name.startswith("latinization/"):
                continue
            if self.include_only_files and (
                filepath.name not in self.include_only_files
                and relative_name not in self.include_only_files
            ):
                continue
            if filepath.name in self.exclude_files or relative_name in self.exclude_files:
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
        current_regex: list[tuple[re.Pattern[str], str, str | None]] = []

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
                    except re.error as exc:
                        logger.debug(
                            "Falling back to simple mapping; regex batch compile failed: %s",
                            exc,
                        )
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
                    literal_hint = max(
                        (part for part in source.split("*") if part),
                        key=len,
                        default=None,
                    )
                    current_regex.append(
                        (
                            re.compile(pattern_str, re.UNICODE | re.IGNORECASE),
                            replacement,
                            literal_hint.casefold() if literal_hint else None,
                        )
                    )
                except re.error:
                    continue

        flush()
        return chunks

    def _build_runtime_rules(self) -> None:
        runtime_rules: list[tuple[str, Any]] = []
        for file_type, rules in self._file_rules:
            if file_type != "dic":
                runtime_rules.append((file_type, rules))
                continue
            runtime_chunks: list[tuple[str, Any]] = []
            for chunk_type, chunk_data in rules:
                if chunk_type == "simple":
                    runtime_chunks.append(
                        ("simple_compiled", _compile_simple_mapping_patterns(chunk_data))
                    )
                else:
                    runtime_chunks.append((chunk_type, chunk_data))
            runtime_rules.append((file_type, runtime_chunks))
        self._runtime_file_rules = runtime_rules

    def _dic_pattern_to_regex(
        self, source: str, target: str, anchor_start: bool = False
    ) -> tuple[str, str]:
        # Treat *foo* as an in-word substring replacement so regex.sub can
        # replace every occurrence across the text, not just one fragment
        # inside a whitespace token.
        if source.startswith("*") and source.endswith("*") and source.count("*") == 2:
            pattern = re.escape(source[1:-1])
            if anchor_start:
                pattern = "^" + pattern
            return pattern, target

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

    def _apply_simple_chunk(
        self, text: str, patterns: list[tuple[re.Pattern[str], str]]
    ) -> str:
        for pattern, replacement in patterns:
            text = pattern.sub(replacement, text)
        return text

    def _apply_dic_rules(self, text: str, chunks: list[tuple[str, Any]]) -> str:
        for chunk_type, chunk_data in chunks:
            if chunk_type == "simple_compiled":
                text = self._apply_simple_chunk(text, chunk_data)
            elif chunk_type == "regex_batch":
                pattern, mapping = chunk_data
                text = pattern.sub(
                    lambda match: mapping.get(match.group().lower(), match.group()),
                    text,
                )
            else:
                folded_text = text.casefold()
                for pattern, replacement, literal_hint in chunk_data:
                    if literal_hint is not None and literal_hint not in folded_text:
                        continue
                    try:
                        updated = pattern.sub(replacement, text)
                    except re.error as exc:
                        logger.debug(
                            "Skipping dictionary rule; pattern.sub failed for %r: %s",
                            replacement,
                            exc,
                        )
                        continue
                    if updated != text:
                        text = updated
                        folded_text = text.casefold()
        return text

    def apply(self, text: str, *, strip_unmatched_latin: bool = False) -> str:
        if not self._runtime_file_rules:
            return text
        for file_type, rules in self._runtime_file_rules:
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
