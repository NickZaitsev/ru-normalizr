[![Windows GUI](https://img.shields.io/badge/Windows-GUI%20Download-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://github.com/NickZaitsev/ru-normalizr/releases/latest)
[![Open in Colab](https://img.shields.io/badge/Open%20in-Colab-F9AB00?style=for-the-badge&logo=googlecolab)](https://colab.research.google.com/drive/1Vyjncl8pteDBOpiDUFk_U5Mn4J968sgS)
[![PyPI](https://img.shields.io/pypi/v/ru-normalizr?style=for-the-badge)](https://pypi.org/project/ru-normalizr/)

# ru-normalizr — лучший open-source нормализатор русского текста

Приводит числа, даты, время, сокращения, римские цифры, символы и латиницу в русские буквы для использования в TTS и NLP:
```text
"В 1980-е годы денег было 25 млн." → "В тысяча девятьсот восьмидесятые годы денег было двадцать пять миллионов."
```  
 
**Ставит слова в правильную грамматическую форму, а не просто делает замены по словарю.**
- Очень высокая скорость
- Покрывает больше реальных кейсов, чем dictionary-only решения
- Стабильнее и качественнее, чем LLM-based нормализаторы
- Малое потребление ресурсов. Не требует GPU

[**Скачать программу *ru-normalizr GUI* для Windows**](https://github.com/NickZaitsev/ru-normalizr/releases/latest) \
[*Смотри сравнение с другими нормализаторами здесь*](#сравнение-с-другими-нормализаторами) \
[*English version of README*](#main-features)

## Основные возможности и режимы

По умолчанию используется режим `safe`:
- приводит к словам числа, даты, время и годы
- обрабатывает римские цифры
- раскрывает самые типичные сокращения, где преобразование обычно однозначно
- нормализует единицы измерения и некоторые символы
- исправляет пробелы, пунктуацию, переносы строк и часть склеек в тексте

Режим `tts` нормализует ближе к "как это надо читать вслух" — рекомендуется для TTS. Кроме всего перечисленного выше, этот режим:
- включает нормализацию CAPS (`ГЛАВА` → `Глава`)
- раскрывает инициалы и аббревиатуры в звуки (`ГИБДД` → `ги бэ дэ дэ`)
- включает перевод латиницы в кириллицу (`iPhone` → `айфоун`)
- может убирать сноски в скобках, например, `[1]`

`ru-normalizr` умеет ставить верные ударения ТОЛЬКО при переводе латиницы в кириллицу.
Чтоб включить эту функцию, используйте флаг CLI-флаг `--with-latin-stress` или настройку `enable_latinization_stress_marks=True`.

Пакет не ставит ударения в русских словах. Для TTS-пайплайна постановку ударений лучше добавлять отдельным этапом, например, через пакет `Silero Stress`.

## Установка

```bash
pip install ru-normalizr
```

Для Windows также доступен GUI: [Скачать ru-normalizr GUI для Windows](https://github.com/NickZaitsev/ru-normalizr/releases/latest)

## Запуск из cmd или bash (CLI)

Нормализовать строку (по умолчанию в режиме `safe`):

```bash
ru-normalizr "Глава IV. Встреча в 10:07."
```

Использовать TTS-режим (рекомендуется):

```bash
ru-normalizr "Глава IV. Встреча в 10:07." --mode tts
```

Прочитать текст из файла и сохранить результат в файл:

```bash
ru-normalizr --mode tts --file ./sample.txt --output ./sample.normalized.txt
```

Если команда `ru_normalizr` не работает, добавьте перед ней `python -m`, например:
```bash
python -m ru-normalizr "Глава IV. Встреча в 10:07." --mode tts
```

Полезные флаги:

- `--mode safe|tts`
- `--with-latin-stress` — по возможности ставить верное удар+ение при кириллизации латиницы
- `--keep-links` — не удалять [1], (2.5) и прочие сноски

## Использование в Python

Cамый простой способ — `normalize()`:

```python
from ru_normalizr import normalize

# по умолчанию режим safe
print(normalize("Глава IV. Встреча в 10:07."))
# Глава четыре. Встреча в десять, ноль семь.
```

Если вы обрабатываете много текстов с одними и теми же настройками, удобнее создать `Normalizer`:
```python
from ru_normalizr import NormalizeOptions, Normalizer

# в режиме tts:
normalizer = Normalizer(NormalizeOptions.tts())

print(normalizer.normalize("ГИБДД"))
# ги бэ дэ дэ

print(normalizer.normalize_batch(["Глава IV.", "В 1980-е годы было 25 млн."]))
# "Глава четыре.", "В тысяча девятьсот восьмидесятые годы было двадцать пять миллионов."
```

Для более точной настройки используйте `NormalizeOptions`:
```python
from ru_normalizr import NormalizeOptions, normalize

options = NormalizeOptions.tts(
    latinization_backend="ipa",
    enable_latinization_stress_marks=True,
)

print(normalize("YouTube в 2024 г.", options))
# +ютуб в две тысячи двадцать четвёртом году
```

## Модульность

`ru-normalizr` можно использовать не только как один большой black box, но и как модульный пайплайн.

Доступны отдельные стадии:

- `preprocess` — предварительная очистка текста: пробелы, переносы строк, пунктуация, часть OCR-подобных склеек, базовая подготовка перед остальной нормализацией
- `roman` — обработка римских цифр
- `years` — нормализация годов, десятилетий и диапазонов лет
- `dates_time` — нормализация дат и времени
- `numerals` — нормализация числительных, порядковых форм, дробей, десятичных и других числовых выражений
- `abbreviations` — раскрытие сокращений, инициалов и буквенных аббревиатур в зависимости от выбранного режима
- `dictionary` — применение словарных правил и пользовательских словарей
- `latinization` — перевод латиницы в кириллицу через словарь или IPA-бэкенд
- `finalize` — финальная чистка текста после всех преобразований: нормализация пунктуации, регистра и восстановление абзацев

Это удобно для отладки, тестирования и встраивания только нужных частей пайплайна в собственную систему.

## Сравнение с другими нормализаторами

Сравнение проводилось на одном компьютере на одних и тех же текстах. Качество можете оценить сами по примерам ниже.

| Нормализатор           | Скорость       | Качество  | Время на книгу       |
| -------------------- | ----------- | -------- | -------- |
| ru-normalizr         | ⚡ очень быстро | ✅ высокое     | ⚡ 2 секунды |
| RuNorm               | 🐢 очень медленно     | ❌ с артефактами | 140-700 секунд |
| Demagog |  быстро      | низкое   | 35 секунд |

Также было произведено сравнение с многообещающим `russian_text_normalizer`. Он показал себя гораздо лучше, чем RuNorm, но он тоже допускает ошибки в нормализации числительных (например, `получил приблизительно 2500 голосов.`→`получил приблизительно двести пятьдесят тысяч голосов.`), нормализирует не всё и съедает слова из оригинального текста.

### Входной текст (пример)
```text
Глава 1
      ПОСЛЕДНИЕ СЛОВА ГЕНЕРАЛА

В 1990–2000 гг компания выпустила 15 моделей iPhone XII и продала 1 234 567 устройств в странах СНГ и ЕС.

АВТОМОБИЛЕСТРОЕНИЕ КОНВЕЙЕРНОЕ организовал американский промышленник Р. Э. Олдс – основатель компании «Олдс Мотор Уоркс» (Olds Motor Works) в городе Детройте.

Компания ABC Ltd. протестировала систему на 3.5 TB данных со скоростью 100 Mb/s.
Размер модели: 2.7 GB, точность: 99.5%.
```

### Результат обработки с ru-normalizr (режим tts)

```text
Глава один.
Последние слова генерала.

В тысяча девятьсот девяностых — двухтысячных годах компания выпустила пятнадцать моделей айфоун двенадцать и продала один миллион двести тридцать четыре тысячи пятьсот шестьдесят семь устройств в странах эс эн гэ и е эс.

Автомобилестроение конвейерное организовал американский промышленник эр ээ Олдс. — основатель компании "Олдс Мотор Уоркс" (оулдз моутэр вэркс) в городе Детройте.

Компания эй би си элтиди. Протестировала систему на трёх целых пять десятых терабайта данных со скоростью ста мегабайтов в секунду.
Размер модели: две целых семь десятых гигабайта, точность: девяносто девять целых пять десятых процента.
```
На нормализацию примера ушло 0.24 секунды. Аббревиатуры и инициалы раскрываются в буквы намерено. Это можно отключить.

Реальную книгу (здесь и далее — Дэвид Бергланд, «ЛИБЕРТАРИАНСТВО ЗА ОДИН УРОК» с flibusta — небольшая книга в 274K символов) ru-normalizer обработал за 2 секунды.

### Результат обработки с RuNorm Big 

```text
Глава первая пэ о эс эл е дэ эн и е эс эл о вэ а гэ е эн е эр а эл а в тысяча девятьсот девяносто первом – две тысячи втором годах компания выпустила пятнадцать моделей айфон двенадцать и продала один миллион двести двадцать четыре тысячи пятьсот семьдесят семь устройств в странах эс эн гэ и е эс. А вэ тэ о эм о бэ и эл е эс тэ эр о е эн и е ка о эн вэ е ий е эр эн о е, на промышленной основе, организовал американский промышленник р. э. олдс – основатель компании «олдс мотор уоркс » ( олдс мотор уоркс ) в городе детройте. Компания эй би си литд. протестировала систему на три целых и пять десятых терабайта данных со скоростью сто мегабайт /секунд. Размер модели : два целых семь десятых гигабайта, точность : девяносто девять целых и пять десятыхпроцент.
```
На нормализацию примера ушло 15.76 секунды.

Реальную книгу (274K символов) RuNorm Small обработал за 143 секунды, RuNorm Big — за 723 секунды.

RuNorm значительно медленнее и использует значительно больше ресурсов.
Качество нормализации у RuNorm низкое и нестабильное. Ломает форматирование.

### Результат обработки словарями Demagog
```text
Глава первая
ПОСЛЕДНИЕ СЛОВА ГЕНЕРАЛА

В одна тысяча девятьсот девяносто–две тысячи компания выпустила пятнадцать моделей ифон двенадцать и продала один двести тридцать четыре пятьсот шестьдесят семь устройств в странах СНГ и ЕС.

АВТОМОБИЛЕСТРОЕНИЕ КОНВЕЙЕРНОЕ организовал американский промышленник Р. Э. Олдс – основатель компании «Олдс Мотор Уоркс» (олдс мото Оркс) в городе Детройте.

Компания эбс лимитэд. протестировала систему на три с половиной тб данных со скоростью сто мегабайтов /с.
Размер модели: два,семь гигабайтов , точность: девяносто девять с половиной%.
```
Применены популярные Демагог словари `10_REX_числа(chisla).rex`, `65_ЛАТИНИЦА@.dic`.

На нормализацию примера ушло менее секунды.

Реальную книгу (274K символов) Демагог обработал за 35 секунд.

Качество нормализации хуже, чем у ru-normalizr, особенно в не покрываемых словарём случаях. Функционал ниже.

# ru-normalizr — the best open-source Russian text normalizer

## Main features

`ru-normalizr` converts numbers, dates, time, abbreviations, Roman numerals, symbols, and Latin text into Russian words for use in TTS and NLP.

**It inflects words into the correct grammatical form instead of relying on simple dictionary replacements.**

- Very fast
- Covers more real-world cases than dictionary-only solutions
- More stable and higher quality than LLM-based normalizers
- Lightweight and resource-efficient. No GPU required

[*See the comparison with other normalizers here*](#comparison-with-other-normalizers)

## Why ru-normalizr?

Russian text normalization is difficult because:

- numbers must be inflected
- abbreviations are ambiguous
- Latin words appear in modern text
- dictionary-only solutions fail on unseen cases

ru-normalizr solves this with a rule-based pipeline that
produces grammatically correct forms instead of simple replacements.

## Modes

By default, `safe` mode is used:
- converts numbers, dates, time, and years into words
- handles Roman numerals
- expands the most common abbreviations where the transformation is usually unambiguous
- normalizes measurement units and some symbols
- fixes spacing, punctuation, line breaks, and some tokenization / merged-text issues

`tts` mode normalizes text closer to “how it should be read aloud” and is recommended for TTS:
- includes CAPS normalization (`ГЛАВА` → `Глава`)
- expands initials and abbreviations into letter names / sounds (`ГИБДД` → `ги бэ дэ дэ`)
- includes Latin-to-Cyrillic transliteration (`iPhone` → `айфоун`)
- can remove bracketed references such as `[1]`

`ru-normalizr` can add correct stress marks ONLY when converting Latin text to Cyrillic.  
To enable this feature, use the CLI flag `--with-latin-stress` or the setting `enable_latinization_stress_marks=True`.

The package does not add stress marks to Russian words. For a TTS pipeline, it is better to add stress marks as a separate stage, for example with the `Silero Stress` package.

## Installation

```bash
pip install ru-normalizr
````

## Running from cmd or bash (CLI)

Normalize a string (uses `safe` mode by default):

```bash
ru-normalizr "Глава IV. Встреча в 10:07."
```

Use TTS mode (recommended):

```bash
ru-normalizr "Глава IV. Встреча в 10:07." --mode tts
```

Read text from a file and save the result to another file:

```bash
ru-normalizr --mode tts --file ./sample.txt --output ./sample.normalized.txt
```

If the `ru_normalizr` command does not work, prepend it with `python -m`, for example:

```bash
python -m ru-normalizr "Глава IV. Встреча в 10:07." --mode tts
```

Useful flags:

* `--mode safe|tts`
* `--with-latin-stress` — add correct stress marks when possible during Latin-to-Cyrillic conversion
* `--keep-links` — do not remove references such as `[1]`, `(2.5)`, etc.

## Usage in Python

The simplest way is to use `normalize()`:

```python
from ru_normalizr import normalize

# safe mode by default
print(normalize("Глава IV. Встреча в 10:07."))
# Глава четыре. Встреча в десять, ноль семь.
```

If you process many texts with the same settings, it is more convenient to create a `Normalizer`:

```python
from ru_normalizr import NormalizeOptions, Normalizer

# tts mode:
normalizer = Normalizer(NormalizeOptions.tts())

print(normalizer.normalize("ГИБДД"))
# ги бэ дэ дэ

print(normalizer.normalize_batch(["Глава IV.", "В 1980-е годы было 25 млн."]))
# "Глава четыре.", "В тысяча девятьсот восьмидесятые годы было двадцать пять миллионов."
```

For finer control, use `NormalizeOptions`:

```python
from ru_normalizr import NormalizeOptions, normalize

options = NormalizeOptions.tts(
    latinization_backend="ipa",
    enable_latinization_stress_marks=True,
)

print(normalize("YouTube в 2024 г.", options))
# +ютуб в две тысячи двадцать четвёртом году
```

## Modularity

`ru-normalizr` can be used not only as one big black box, but also as a modular pipeline.

Individual stages are available:

- `preprocess` — preliminary text cleanup: spaces, line breaks, punctuation, some OCR-like glued text, and other preparation before the main normalization stages
- `roman` — Roman numeral handling
- `years` — normalization of years, decades, and year ranges
- `dates_time` — normalization of dates and time expressions
- `numerals` — normalization of cardinal numbers, ordinal forms, fractions, decimals, and other numeric expressions
- `abbreviations` — expansion of abbreviations, initials, and letter-by-letter abbreviations depending on the selected mode
- `dictionary` — application of built-in and custom dictionary rules
- `latinization` — conversion of Latin words into Cyrillic using either dictionary rules or the IPA backend
- `finalize` — final cleanup after all transformations: punctuation normalization, casing fixes, and paragraph restoration

## Comparison with other normalizers

The comparison was run on the same machine and the same texts.

| Normalizer           | Speed       | Quality  |
| -------------------- | ----------- | -------- |
| ru-normalizr         | ⚡ very fast | ✅ high     |
| RuNorm               | 🐢 slow     | ❌ unstable |
| Demagog | ⚡ fast      | ❌ limited  |

A comparison was also made with the promising `russian_text_normalizer`. It performed much better than RuNorm, but it also makes errors in normalizing numerals (for example, `получил приблизительно 2500 голосов.`→`получил приблизительно двести пятьдесят тысяч голосов.`), does not normalize everything, and omits words from the original text.

### Input text (example)

```text
Глава 1
      ПОСЛЕДНИЕ СЛОВА ГЕНЕРАЛА

В 1990–2000 гг компания выпустила 15 моделей iPhone XII и продала 1 234 567 устройств в странах СНГ и ЕС.

АВТОМОБИЛЕСТРОЕНИЕ КОНВЕЙЕРНОЕ организовал американский промышленник Р. Э. Олдс – основатель компании «Олдс Мотор Уоркс» (Olds Motor Works) в городе Детройте.

Компания ABC Ltd. протестировала систему на 3.5 TB данных со скоростью 100 Mb/s.
Размер модели: 2.7 GB, точность: 99.5%.
```

### Output produced by ru-normalizr (`tts` mode)

```text
Глава один.
Последние слова генерала.

В тысяча девятьсот девяностых — двухтысячных годах компания выпустила пятнадцать моделей айфоун двенадцать и продала один миллион двести тридцать четыре тысячи пятьсот шестьдесят семь устройств в странах эс эн гэ и е эс.

Автомобилестроение конвейерное организовал американский промышленник эр ээ Олдс. — основатель компании "Олдс Мотор Уоркс" (оулдз моутэр вэркс) в городе Детройте.

Компания эй би си элтиди. Протестировала систему на трёх целых пять десятых терабайта данных со скоростью ста мегабайтов в секунду.
Размер модели: две целых семь десятых гигабайта, точность: девяносто девять целых пять десятых процента.
```

Normalizing this example took 0.24 seconds. Abbreviations and initials are intentionally expanded into letter names. This can be disabled.

A real book (here and below: David Bergland, *Libertarianism in One Lesson* from Flibusta — 274K characters) was processed by `ru-normalizr` in 2 seconds.

### Output produced by RuNorm Big

```text
Глава первая пэ о эс эл е дэ эн и е эс эл о вэ а гэ е эн е эр а эл а в тысяча девятьсот девяносто первом – две тысячи втором годах компания выпустила пятнадцать моделей айфон двенадцать и продала один миллион двести двадцать четыре тысячи пятьсот семьдесят семь устройств в странах эс эн гэ и е эс. А вэ тэ о эм о бэ и эл е эс тэ эр о е эн и е ка о эн вэ е ий е эр эн о е, на промышленной основе, организовал американский промышленник р. э. олдс – основатель компании «олдс мотор уоркс » ( олдс мотор уоркс ) в городе детройте. Компания эй би си литд. протестировала систему на три целых и пять десятых терабайта данных со скоростью сто мегабайт /секунд. Размер модели : два целых семь десятых гигабайта, точность : девяносто девять целых и пять десятыхпроцент.
```

Normalizing this example took 15.76 seconds.

A real book (274K characters) was processed in 143 seconds by RuNorm Small and in 723 seconds by RuNorm Big.

RuNorm is significantly slower and uses significantly more resources.
Its normalization quality is low and unstable. It also breaks formatting.

### Output produced with Demagog dictionaries

```text
Глава первая
ПОСЛЕДНИЕ СЛОВА ГЕНЕРАЛА

В одна тысяча девятьсот девяносто–две тысячи компания выпустила пятнадцать моделей ифон двенадцать и продала один двести тридцать четыре пятьсот шестьдесят семь устройств в странах СНГ и ЕС.

АВТОМОБИЛЕСТРОЕНИЕ КОНВЕЙЕРНОЕ организовал американский промышленник Р. Э. Олдс – основатель компании «Олдс Мотор Уоркс» (олдс мото Оркс) в городе Детройте.

Компания эбс лимитэд. протестировала систему на три с половиной тб данных со скоростью сто мегабайтов /с.
Размер модели: два,семь гигабайтов , точность: девяносто девять с половиной%.
```

Popular Demagog dictionaries `10_REX_числа(chisla).rex` and `65_ЛАТИНИЦА@.dic` were used.

Normalizing this example took less than one second.

A real book (274K characters) was processed by Demagog in 35 seconds.

Normalization quality is worse than `ru-normalizr`, especially in cases not covered by the dictionary. Functionality is also more limited.
