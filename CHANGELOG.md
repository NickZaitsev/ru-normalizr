# Changelog

All notable changes to `ru-normalizr` will be documented in this file.

The format is based on Keep a Changelog, and this project follows Semantic Versioning.

## Unreleased


## [0.1.4] - 2026-03-15
- Update repo name to `ru-normalizr`.


## [0.1.3] - 2026-03-15
### Changed
- Changed release helper scripts.
- Moved decimal and fraction normalization from the `dates_time` stage to `numerals`.
- `enable_numeral_normalization=False` now keeps decimal numbers unchanged instead of normalizing them through `dates_time`
### Fixed.
- Bracketed numeric references are no longer expanded during preprocess when `remove_links=False`; they now stay unchanged unless link removal is enabled.


## [0.1.2] - 2026-03-14
### Changed
- Updated README.md.
- Fixed incorrect repository/homepage links in PyPI metadata.
- Cleaned up lint issues and added release helper scripts.
- Added GitHub Actions CI and tag-based PyPI release automation.

## [0.1.1] - 2026-03-13

### Changed
- Fixed quote space normalization.
- Updated Readme and project description.

## [0.1.0] - 2026-03-11

### Added
- Initial standalone `ru_normalizr` package extracted from private TTS workflow.
- Public Python API: `normalize`, `Normalizer`, `normalize_batch`, `run_stage`, and `preprocess_text`.
- Standalone CLI via `python -m ru_normalizr` and `ru-normalizr`.
- Fixed-order normalization pipeline for:
  - preprocess cleanup
  - Roman numerals
  - years, dates, and time
  - cardinal numerals, ordinals, decimals, fractions, and hyphenated numeric words
  - abbreviations, initials, and letter-by-letter expansions
  - optional dictionary normalization
  - optional Latin transliteration
- Native dictionary loader for `.dic` files.
- Library test suite moved into `ru_normalizr/tests`.
- Package metadata, typing marker, and wheel build support.
- PEP8 formatted.
- `NormalizeOptions.safe()` and `NormalizeOptions.tts()` presets.
- Granular abbreviation toggles for contextual abbreviations, initials, and letter-by-letter expansions.
- Optional IPA stress marker output controlled by `enable_latinization_stress_marks`.
- CLI support for `--mode safe|tts` and `--with-latin-stress`.


### Changed
- Consolidated morphology loading through a shared cached helper.
- Expanded parity coverage against legacy normalization behavior.
- `NormalizeOptions()` now defaults to the conservative `safe` preset.
- TTS-oriented behavior is now explicit through `NormalizeOptions.tts()` or `--mode tts`.
- Latinization rules were moved to `ru_normalizr/dictionaries/latinization/latinization_rules.dic`.
- General dictionary normalization no longer implicitly loads the latinization dictionary subtree unless it is explicitly requested.

### Notes
- TTS-specific pause hacks, pronunciation logic, accentization, and audio/model integration remain intentionally out of scope. ru-normalizr is only handling book normalization.
