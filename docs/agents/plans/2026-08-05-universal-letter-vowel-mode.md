# Plan: Universal letter vowel mode

Status: plan, 2026-08-05.

> Note for agents: this plan is a point-in-time snapshot — its "codebase facts" describe the code as of the date above and may be outdated. Do NOT treat it as current architecture docs; verify every fact against the actual code before relying on it.

## Context

`NormalizeOptions.initials_vowel_mode` currently controls doubled Cyrillic vowels only in person initials, while other independently pronounced letters use unrelated hard-coded behavior. Latin `E` and `U` are always stored as `ии` and `юю`; generated Cyrillic abbreviations use single vowel names; and several `KNOWN_ABBREVIATIONS` readings embed doubled vowel tokens. The result is inconsistent and the `flight_number` known-gap expectation conflicts with the current TTS-oriented English table.

The change must make vowel length a single mode applied to every independently pronounced letter, without rewriting ordinary lexical pronunciation rules such as `read=риид` in the bundled latinization dictionary.

## Approved decisions

1. Generalize the setting from initials to all independently pronounced Cyrillic and Latin letters.
2. Keep `single` as the safe/default preset and `double` as the TTS preset.
3. Introduce the public name `letter_vowel_mode` and retain `initials_vowel_mode` as a backwards-compatible constructor and attribute alias.
4. Apply the mode to person initials, generated letter-by-letter abbreviations, mode-aware custom abbreviation readings, and Latin alphanumeric suffix letters.
5. Under TTS/double mode, `SU` is correctly rendered as `эс юю`; the existing `flight_number` xfail expectation must be corrected and promoted to a regular E2E regression.
6. Add focused tests and public-pipeline E2E tests for both modes and both scripts.

## Key codebase facts

- `src/ru_normalizr/constants.py` defines `RU_LETTER_NAMES`, `RU_DOUBLED_VOWEL_INITIAL_NAMES`, `EN_LETTER_NAMES`, and `KNOWN_ABBREVIATIONS`.
- `KNOWN_ABBREVIATIONS` contains embedded doubled vowel tokens in readings for `США`, `ЕЭС`, `НБА`, `ВТО`, `ОАО`, `ЗАО`, `ООО`, and `ОРЗ`; other repeated vowels in `src/ru_normalizr/dictionaries/latinization/latinization_rules.dic` are lexical pronunciation data and are out of scope.
- `src/ru_normalizr/abbreviations.py::expand_person_initials` is the only current consumer of `RU_DOUBLED_VOWEL_INITIAL_NAMES`.
- `src/ru_normalizr/abbreviations.py::expand_letter_abbreviations` reads generated Cyrillic and Latin abbreviations and returns `KNOWN_ABBREVIATIONS` values before generic heuristics.
- `src/ru_normalizr/latinization.py::apply_latinization` uses `EN_LETTER_NAMES` directly for Latin suffix letters matched by `ALPHANUMERIC_SUFFIX_LETTER_PATTERN`.
- `src/ru_normalizr/options.py` exposes the frozen, slotted `NormalizeOptions` public configuration. The safe preset currently sets `initials_vowel_mode="single"`; TTS sets `"double"`.
- `README.md` documents the option in both Russian and English sections.
- `tests/test_known_gaps.py` contains the `flight_number` xfail; fixed known gaps must move to a focused regular suite in the same commit.

## Implementation

0. Centralize letter-name resolution

   - Update `src/ru_normalizr/constants.py` so base Cyrillic and Latin maps contain single forms.
   - Rename/generalize the doubled-vowel table and add a resolver such as `resolve_letter_name(letter: str, vowel_mode: LetterVowelMode) -> str | None`.
   - Add a helper that adjusts only standalone vowel-name tokens inside custom abbreviation readings. Do not perform unrestricted substring replacement.
   - Ensure the ampersand classifier recognizes both single and doubled English letter-name outputs.

1. Generalize the public option compatibly

   - Update `src/ru_normalizr/options.py` with `LetterVowelMode` and `NormalizeOptions.letter_vowel_mode`.
   - Continue accepting `initials_vowel_mode`; mirror the effective value on the legacy attribute.
   - If both constructor names are supplied with different values, raise `ValueError` rather than silently choosing one.
   - Preserve safe/default `single` and TTS `double` behavior.

2. Route every independent-letter rendering through the mode

   - Update `src/ru_normalizr/abbreviations.py::expand_person_initials` and `expand_letter_abbreviations` to use the shared resolver.
   - Pass `NormalizeOptions.letter_vowel_mode` from `expand_abbreviations`.
   - Apply the same mode to vowel tokens in `KNOWN_ABBREVIATIONS` readings while leaving lexical readings intact.
   - Update `src/ru_normalizr/latinization.py::apply_latinization` to accept the mode and use the resolver for alphanumeric suffix letters.
   - Pass the configured mode from `src/ru_normalizr/normalizer.py::run_latinization`.

3. Update user-visible documentation and known-gap inventory

   - Document `letter_vowel_mode` and the compatibility alias in both language sections of `README.md`.
   - Add the behavior change under `CHANGELOG.md` `Unreleased`.
   - Remove `flight_number` from `tests/test_known_gaps.py` and add its corrected TTS expectation to a focused regular E2E suite.

## Testing & verification

- Add table-driven resolver tests for all Cyrillic doubled vowels and Latin `E`/`U`, plus unchanged consonants and unknown characters.
- Extend `tests/test_abbreviation_stage.py` to cover single/double Cyrillic and Latin generated abbreviations and mode-aware known readings such as `США`, `ООО`, and `USB`.
- Extend `tests/test_e2e_options.py` to prove that `letter_vowel_mode` changes initials, Cyrillic abbreviations, Latin abbreviations, and alphanumeric suffixes through `normalize`, while unrelated lexical latinization is unchanged.
- Add compatibility tests for the legacy option name, matching aliases, conflicting aliases, and preset attributes.
- Promote the flight-number scenario to a regular E2E regression with `эс юю` in TTS mode.
- Run `uv run ruff check .`, `uv run pyright`, and the full `uv run pytest` suite before the implementation commit.

## Out of scope

- Do not alter lexical vowel sequences in the latinization `.dic` rules.
- Do not fix dotted-acronym preprocessing; that remains a separate known gap.
- Do not revise consonant letter-name conventions or unrelated custom abbreviation pronunciations.
- Do not remove the legacy `initials_vowel_mode` API in this change.

---
**Maintenance note (for the implementing agent):** when this plan is implemented, update the `Status:` line above, e.g. `Status: implemented YYYY-MM-DD in branch `feat/<name>``. If the plan changes during implementation, update the affected sections too — the plan must not lie about what was built.
