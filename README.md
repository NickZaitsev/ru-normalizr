# ru-normalizr

Normalization-only Russian text preprocessing extracted into a standalone package.

`ru-normalizr` focuses on deterministic Russian text normalization:
- years, dates, time, decimals, fractions, ordinals, and cardinal numerals
- abbreviations, initials, Roman numerals, cleanup rules, and glued OCR-like text
- optional Latin transliteration via dictionary or `eng_to_ipa`

Out of scope by design:
- accentization and stress dictionaries
- pronunciation and post-phoneme fixes
- TTS pause hacks and chunking
- audio, model, or engine integration

## Installation

Core install:

```bash
pip install ru-normalizr
```

With IPA-based Latin handling:

```bash
pip install "ru-normalizr[ipa]"
```

## API

```python
from ru_normalizr import NormalizeOptions, Normalizer, normalize, preprocess_text

text = normalize("Глава IV. Встреча в 10:07.")
prepared = preprocess_text("10кг")

normalizer = Normalizer(
    NormalizeOptions(
        enable_latinization=False,
        enable_first_word_decap=True,
    )
)
batch = normalizer.normalize_batch(["Глава IV.", "В 1980-е годы было 25 млн."])
roman_only = normalizer.run_stage("roman", "Глава IV")
```

### Example outputs

```python
from ru_normalizr import normalize

print(normalize("Глава IV. Встреча в 10:07."))
# Глава четыре. Встреча в десять, ноль семь.

print(normalize("В 1980-е годы было 25 млн. $"))
# В тысяча девятьсот восьмидесятые годы было двадцать пять миллионов долларов

print(normalize("Добавьте 1/4 стакана воды."))
# Добавьте одну четвертую стакана воды.

print(normalize("И. О. Фамилия приехал."))
# и о фамилия приехал.
```

### Configuring options

```python
from ru_normalizr import NormalizeOptions, normalize

options = NormalizeOptions(
    enable_latinization=False,
    enable_dictionary_normalization=False,
    enable_first_word_decap=True,
)

print(normalize("YouTube в 2024 г.", options))
```

### Example dictionaries

Runtime dictionary assets shipped in the package live under `ru_normalizr/dictionaries/`.
The editable example override file lives in `examples/your_rules.dic` in the source tree and is not included in published wheels.

### Batch usage

```python
from ru_normalizr import Normalizer

normalizer = Normalizer()
texts = ["Глава IV.", "12.03.2025", "Цена 1.5 кг сахара."]
print(normalizer.normalize_batch(texts))
```

Available stage names for expert use:
- `preprocess`
- `roman`
- `years`
- `dates_time`
- `numerals`
- `abbreviations`
- `dictionary`
- `latinization`
- `finalize`

Stage order is fixed in the main pipeline. Stage-level calls are for debugging, testing, and focused use, not for arbitrary reordering.

## CLI

```bash
python -m ru_normalizr "Глава IV. Встреча в 10:07."
echo "В 1980-е годы было 25 млн." | python -m ru_normalizr
ru-normalizr --file ./sample.txt
ru-normalizr --file ./sample.txt --output ./sample.normalized.txt
ru-normalizr --no-latinization "YouTube в 2024 г."
```

## Development

```bash
py -3.12 -m pip install -r ./ru_normalizr/requirements-dev.txt
py -3.12 ./ru_normalizr/scripts/dev.py test
py -3.12 ./ru_normalizr/scripts/dev.py lint
py -3.12 ./ru_normalizr/scripts/dev.py build
```

## Release Notes

- Changelog: `CHANGELOG.md`
- Versioning policy: `VERSIONING.md`
- Publish checklist: `PYPI_RELEASE_CHECKLIST.md`

## Packaging

The package is self-contained inside `ru_normalizr/` and builds as a standalone wheel from that directory:

```bash
python -m pip wheel --no-deps ./ru_normalizr
```

For repeatable local workflows, use the helper script:

```bash
py -3.12 ./ru_normalizr/scripts/dev.py clean
py -3.12 ./ru_normalizr/scripts/dev.py test
py -3.12 ./ru_normalizr/scripts/dev.py lint
py -3.12 ./ru_normalizr/scripts/dev.py build
```

The supported public Python imports are from the package root, for example:

```python
from ru_normalizr import NormalizeOptions, Normalizer, normalize, preprocess_text
```
