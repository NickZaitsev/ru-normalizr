# Changelog

All notable changes to `ru-normalizr` will be documented in this file.

The format is based on Keep a Changelog, and this project follows Semantic Versioning.

## Unreleased
### Changed
- Make numeral context lookup linear and cache rendered numeral forms, substantially improving number-dense text throughput
- Reuse the shared morphology parse cache across Roman, decimal, fraction, ordinal, year, and abbreviation stages
- Skip year, date, numeral, and literal abbreviation scans when their input contains no relevant candidates
- Avoid repeatedly detokenizing the remaining document when deciding whether a dotted unit abbreviation ends a sentence
- Make CLI `--check` an explicit stdout mode that rejects conflicting `--output`, and correct the documented `python -m ru_normalizr` module command
- Cache immutable morphology parse results in numeral and caps hot paths, cutting a 5 KB number-dense normalization benchmark from about 303 ms to 75 ms
- Cache the compiled year-pattern set, roughly halving repeated `normalize_years` call overhead on a short-year microbenchmark
- Load the small bundled dictionaries directly instead of reading or writing executable pickle caches beside installed package files
- Speed up IPA latinization on large texts with many distinct Latin tokens by batching `eng_to_ipa` lookups and batched dictionary fallback rewrites instead of resolving every token separately
### Fixed
- Stop grammatical case from leaking across `равно` onto arithmetic results, so currency results remain nominative regardless of the left operand's fraction form
- Remove copyright symbols during cleanup instead of replacing them with stray sentence-ending dots
- Inflect abbreviated chapter references such as `см. гл. 5` and `в гл. 3` before the general abbreviation stage turns their numbers into bare cardinals
- Normalize prose date ranges such as `с 5 по 10 января` with ordinal day forms appropriate to both prepositions
- Recognize case-sensitive Cyrillic units such as `°С`, `мА`, `кА`, `мкА`, and `мАч` without treating their lowercase lookalikes as units
- Preserve sentence boundaries when expanding terminal year and gram abbreviations such as `1672 г.` and `вес 5 г.`, without retaining the abbreviation dot mid-sentence
- Require numeric or quantity context before expanding `л. н.` as `лет назад`, preserve person initials such as `Л. Н. Толстой`, and add `enable_years_ago_expansion` to disable this expansion explicitly
- Stop surname-first initials expansion from hijacking role/title + initial + surname lines such as `Редактор Е. Харитонова`, so TTS output no longer inserts a stray dot before the surname
- Keep initials-first name lists inside the sentence without injecting `.,` before commas or dashes
- Expand numeric reference abbreviations such as `ст.`, `рис.`, `стр.`, and `табл.` during preprocess before numeral reading, so full-pipeline outputs no longer miss forms like `ст. 49 УК РФ` after the number has already been normalized
- Fix reported numeral normalization regressions around `человек` counting forms, long decimal denominators, glued and hyphenated ordinal suffixes (`41м`, `21ом`, `1-ую`, `3ее`, `II-я`), `г.р.`/mass `г.` disambiguation, and compound adjective readings such as `5и ступенчатая` and `1 комнатная`
- Stop year regexes from matching inside preceding words, so abbreviated mass contexts such as `вес 123 г.` and `масса 237 г.` no longer get misread as years
- Normalize integer-like Unicode numeral symbols such as `①` and `⑳` through the cardinal numeral pipeline instead of crashing on `int(...)`

## [0.2.0] - 2026-03-22
### Added
- Add an early TTS-only URL stage that rewrites explicit links such as `https://example.com/a1` into spoken separator words and digit-by-digit number readings before preprocess, while leaving plain Latin chunks for the later latinization stage
- Read `=` as `равно` in math-like expressions when at least one side contains digits, covering forms such as `t=10` and `x=(2+3)` while leaving plain non-numeric assignments such as `x = y` unchanged
- Read `~` as `примерно` before numeric expressions and treat compact lowercase `k` suffixes such as `250k` as thousands while keeping uppercase `K` for Kelvin units
- Inflect adjective-like abbreviations such as `гос.`, `междунар.`, and `полит.` from the following noun phrase so forms like `гос. контроля` normalize to `государственного контроля`
- Expand English title abbreviations `Mr.` and `Mrs.` to `мистер` and `миссис` before latinization, so mixed inputs such as `Mr. Поппер` normalize cleanly
- Normalize `&` contextually as `и` in Russian phrases and as `энд` in brand-like English letter-name contexts such as `AT&T`
- Add `ул.` and `Св.` expansions
- Normalize single chapter/section-style references such as `главу 10`, `из главы 10`, and `из раздела 3` to ordinal forms like `главу десятую`, `из главы десятой`, and `из раздела третьего`
- Read regnal name patterns such as `Георг VI`, `Людовик XVI`, `Елизавета II`, and `Дарий I` as ordinal names (`Георг шестой`, `Людовик шестнадцатый`, etc.) instead of cardinal numerals
- Preserve full Greek-script words such as `αστατος` instead of spelling them out letter-by-letter, while still reading standalone Greek symbols like `α`, and expand `от греч./лат. <foreign word>` to forms such as `от греческого αστατος` and `от латинского homo`
- Extend era handling to English historical markers such as `BC`, `BCE`, `AD`, and `CE`, and route shared-era ranges through the existing year logic for forms like `с 12500 по 9500 до н. э.`
- Normalize chapter/section/book-style Roman and Arabic headings to ordinal forms such as `Глава четвёртая` / `Глава десятая` for more consistent heading handling across the pipeline
- Normalize coordinated Roman numerals with a shared context word on the right into contextual ordinal forms, so inputs such as `V и IV тысячелетиях до н. э.` become `пятом и четвёртом ...` instead of leaving the first numeral for latinization as `ви`
- Normalize more coordinated Roman series with shared context words on either side, covering dative forms such as `к XV и XVI векам` and left-shared heading patterns such as `главы IV и V` / `в главах IV и V`
- Normalize left-shared heading ranges written with hyphens, so forms such as `главы IV-V` and `в разделах IV-V` no longer partially convert only the first Roman numeral
- Treat `вв.` consistently as plural `века` across shared series and range patterns, covering forms such as `XV и XVI вв.`, `XV-XVI вв.`, `с XVI по XVIII вв.`, and `от XVI до XVIII вв.`

### Changed
- Cache resolved IPA latinization fallback results for repeated unknown Latin words, and stop retrying dictionary fallback once the transliteration stabilizes
- Precompile runtime regexes for large simple dictionary-rule chunks once per `DictionaryNormalizer` instance instead of rebuilding them on every `apply()`
- Explicitly treat `не более`, `не менее`, `не больше`, `не меньше`, `более`, `менее`, `больше`, and `меньше` as genitive-marking quantifiers only in direct continuous use before numerals, without extending that rule through `чем`
- Move implicit year disambiguation out of year regexes into shared token/context helpers
- Route safe `число-дефис-единица` forms such as `35-мм`, `35 - мм`, and `1,5-мл` through shared numeral hyphen handling so they normalize like spaced units while leaving ordinary forms such as `20-этажный` and ambiguous single-letter suffixes alone
- Keep preprocess from eagerly converting ASCII ` - ` into `—`; only normalize explicit dash characters there, canonize numeric `число - suffix/unit` forms such as `35 - мм`, `20 - этажный`, and `5 - й` before numeral handling, and move leftover ASCII word-separator dashes to finalize so plain spaced ranges like `10 - 20` stay range-like
- Rewrite explicit Cyrillic combining stress marks such as `Фри́дрих А́вгуст` to the package's `+` stress format (`Фр+идрих +Август`) during preprocess instead of letting combining accents break token spacing
- Restrict implicit `от/с ... до/по ...` year-range normalization without explicit `год/г./гг.` to plausible years only, and expand single initials near likely surnames in TTS mode while leaving obvious non-person tokens such as `С. Петербург` untouched
- Refresh README Python examples so Roman heading outputs such as `Глава IV.` match the current ordinal normalization (`Глава четвёртая.`)

### Fixed
- Stop treating pure Cyrillic all-caps lookalike tokens such as `ММММ` as Roman numerals, so interjections and dialogue fragments no longer normalize to values like `четыре тысячи` while mixed-script OCR-like forms such as `ХVI` still work
- Fall back to the bundled latinization dictionary when a requested latinization dictionary filename is missing, so IPA fallback still rewrites unknown Latin words instead of leaving them unchanged
- Fix some 'к → Кельвин' and 'м в → милливольт' misnormalization errors. Add regression coverage for ambiguous single-letter units and compound unit boundaries such as `км ч`, `квт ч`, `fps`, `mph`, `kbps`, `об мин`, and `ммоль л`
- Preserve bracketed year-like values during TTS link removal
- Improve range/year case handling for forms such as `1990-ые`, `1943 и 1951 гг.`, and `206 год до н. э.`
- Keep hyphenated decade forms such as `в 1990-ые годы` out of the implicit preposition-plus-year rule so they stay decade phrases instead of becoming `девяностом-ые`
- Keep `с 1990 по 1995 кг`-style measurement ranges from being misread as year ranges
- Keep implicit year heuristics from misreading measurement and currency ranges such as `от 1200 до 10000 МПа`, `от 1200 до 10000 ₽`, and spaced-thousands forms like `от 1200 до 10 000 МПа`, while reusing shared unit/currency lexicons from `numerals._constants`
- Restore `с/со/от ... до|по ... г.` year-range normalization so explicit trailing year abbreviations keep both range endpoints in year morphology
- Fix agreement for compound adjective+noun measurement units after numerals, so outputs such as `3 м^3`, `2 км2`, and `2 IU` normalize to `три кубических метра`, `два квадратных километра`, and `две международные единицы`
- Stop misreading title-case `См.` as a Cyrillic Roman numeral token
- Stop initials expansion from crashing on some `pymorphy3` tag objects while checking name-like tokens, preserving cases such as `С. Петербург` in TTS mode
- Tighten dotted `8.00` time normalization so explicit clock contexts still normalize while ordinary decimals like `3.50 руб.` and `2.15 кг` remain decimal numbers; also preserve BCE/CE terminal punctuation and handle century ranges written as `С XVI по XVIII в.`
- Fix reported historical/BCE normalization regressions around `ок.`, `до н. э./н. э.`, parenthesized years, Roman century ranges, dotted clock times, page references like `с.22-25`, zero-width formatting garbage in Cyrillic text, and numeric/unit ranges such as `2-6 футов`
- Normalize smart single quotation marks such as `‘...’` to ASCII quote pairs when they act as surrounding quotes, while keeping intra-word apostrophes like `rock’n’roll` unchanged
- Stop unconditional language-abbreviation replacements such as `нем.` and `лат.` from misreading sentence-final pronoun forms like `в нем. Когда...`, while keeping contextual expansions such as `нем. слово` and `от лат. homo`
- Normalize measurement ranges with spelled-out multiword units such as `1200-1400 кубических сантиметров`, so dimensional contexts like `объемом ...` no longer fall back to an incorrect instrumental numeral form
- Keep inanimate accusative ordinals such as `XX век` and `3-й фильм` in the nominative-looking form (`двадцатый век`, `третий фильм`) instead of the animate accusative/genitive form (`двадцатого`, `третьего`)
- Normalize shared-era ancient year ranges such as `12500-9500 до н. э.` as year ranges instead of plain numbers, and avoid malformed large ordinals like `двенадцатый тысяч ...` for years above 9999
- Keep explicit BCE/CE year nouns such as `в 1776 год до н. э.` aligned with the written `год` form, so the ordinal no longer incorrectly switches to a prepositional shape like `шестом год`
- Fix a crash in era-year normalization for abbreviated forms such as `50 г. до н. э.` when no leading preposition is present
- Infer case for coordinated Roman-century series from sentence context, so forms such as `за XV и XVI века` normalize to `за пятнадцатый и шестнадцатый века` instead of an incorrect genitive reading
- Route single Roman numerals with contextual abbreviations such as `XV в.` through the same lemma-based context logic as full noun forms, preserving correct case in forms like `в XV в.`, `за XV в.`, `о XV в.`, and `к XV в.`
- Keep coordinated Roman-series normalization working at sentence boundaries and normalize hyphenated Roman ranges such as `III-IV веках` / `III-IV тысячелетиях` into contextual ordinal ranges instead of falling through to plain numeral handling
- Keep standalone `Roman + century noun` forms such as `XXI века` aligned with the explicit noun morphology, so genitive forms no longer fall back to nominative readings like `двадцать первый века`
- Respect explicit oblique noun forms like `веков` in coordinated and hyphenated Roman series, so outputs such as `XV-XVI веков` and `XV и XVI веков` stay in genitive (`пятнадцатого ... веков`) instead of falling back to nominative ordinals
- Improve abbreviated Roman context handling for `кв.` and `вв.`, and keep `от ... до ... в.` ranges in the expected genitive form on the right endpoint
- Keep malformed Roman hyphen ranges from partially converting only their right-hand side, so inputs such as `IIII-IV век` stay untouched instead of turning into mixed forms like `IIII-четвёртый век`

## [0.1.4] - 2026-03-15
### Changed
- Update repo name to `ru-normalizr`.
- Fix CI/CD
- Add GUI link to README.md

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
