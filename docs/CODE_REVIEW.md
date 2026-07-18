# ru-normalizr — Code Review (2026-07-18)

Full repository review: every Python module was read, the test suite was executed
(250 tests + 16 subtests, **all passing**), and every reported defect below was
**reproduced by actually running the library** in a clean Python 3.12 venv unless
marked otherwise.

Reviewed at commit `3af1b85` (branch `main`, clean working tree).

---

## 1. Overall assessment

The codebase is in good shape for its size (~11k lines):

- Clear stage-based pipeline ([normalizer.py](../normalizer.py)) with per-stage toggles and
  a modular public API (`Normalizer.run_stage`).
- Strong test culture: 250 tests across API, stages, and several regression suites.
- Good contributor documentation ([AGENTS.md](../AGENTS.md)), CI on 3.10–3.12, trusted
  publishing on tags.
- Morphology-aware design (pymorphy3 + num2words) rather than dictionary-only hacks.

The main problems found are: **a handful of real correctness bugs in `safe` mode**
(the mode advertised as conservative), a **case-sensitivity bug that makes several
unit-table entries unreachable**, **sentence-boundary dots being swallowed**,
significant **per-call performance overhead** on number-dense text, and some
**dead code / repo hygiene** issues.

Severity legend: **P0** = wrong output in common real text, safe mode;
**P1** = wrong output in realistic but narrower cases, or security/perf;
**P2** = cleanup, docs, hygiene.

---

## 2. Confirmed correctness bugs

### B1 (P0) — Initials «Л. Н.» are destroyed by the «лет назад» expansion

**Verified by execution.**

```text
in  (safe): Л. Н. Толстой родился в 1828 году.
out       : лет назад. Толстой родился в тысяча восемьсот двадцать восьмом году.
```

`YEARS_AGO_ABBREVIATION_PATTERN` in [preprocess_utils.py:54](../preprocess_utils.py#L54)
is `(?<!\w)л\.?\s*н\.` with `re.IGNORECASE`, so it matches the extremely common
person-initials pair «Л. Н.» (Лев Николаевич, Л. Н. Гумилёв, …) and rewrites it to
«лет назад.» in **both** modes, including `safe`. Any book mentioning Л. Н. Толстой
is corrupted. `expand_years_ago_abbreviation` runs unconditionally inside
`_run_preprocess_steps`.

Fix direction: drop `IGNORECASE` (the genuine abbreviation is lowercase «л. н.»)
and additionally require a numeric/quantity left context (`\d`, «тыс», «млн»,
«миллионов» …) before treating it as "years ago".

### B2 (P0) — Sentence-final dot swallowed after year/gram abbreviations

**Verified by execution.**

```text
in  (safe): Он родился в 1672 г. Потом вырос.
out       : Он родился в тысяча шестьсот семьдесят втором году Потом вырос.

in  (safe): Вес 5 г. Далее текст.
out       : Вес пять грамм Далее текст.
```

Two independent sites:

- `replace_with_word` in [years.py:505](../years.py#L505) expands `NNNN г.` but never
  re-appends the dot when it also terminated the sentence. Sibling replacers
  (`replace_s_po` at years.py:340, `_should_keep_era_terminal_dot` at years.py:124,
  `normalize_birth_year_abbreviations` in abbreviation_context.py) already contain
  the keep-terminal-dot heuristic — `replace_with_word` (and `replace_suffix`,
  `replace_era_*` where applicable) simply lacks it.
- `normalize_mass_gram_abbreviations` in
  [abbreviation_context.py:26](../abbreviation_context.py#L26) is a blind
  `\g<num> грамм` substitution that always eats the dot.

The result merges two sentences, which then breaks downstream sentence-caps logic.

### B3 (P0) — Case-sensitive `UNITS_DATA` keys are unreachable (°С, мА, кА, мкА, мАч)

**Verified by execution.**

```text
in  (safe): Температура 25 °С сегодня.        # Cyrillic С
out       : Температура двадцать пять градусов С сегодня.   # «Цельсия» lost

in  (safe): Температура 25 °C сегодня.        # Latin C
out       : Температура двадцать пять градусов Цельсия сегодня.

in  (safe): Ток 5 мА в цепи.
out       : Ток пять мА в цепи.               # unit not expanded

in  (safe): Батарея на 3000 мАч.
out       : Батарея на трёх тысячи мАч.       # unit not expanded + broken agreement
```

All lookups into `UNITS_DATA` lowercase the token first
(`next_token_lower = noun_token.lower()...` in [numerals/cardinals.py:210](../numerals/cardinals.py#L210)),
but these keys are stored with uppercase letters in
[numerals/_constants.py](../numerals/_constants.py): `"°С"`, `"°К"` (lines ~320–321),
`"мкА"`, `"мА"`, `"кА"` (lines ~344–346), `"мАч"` (line ~594). They can never match.

Additionally, the degree-suffix combiner in
[numerals/cardinals.py:214-217](../numerals/cardinals.py#L214) only accepts ASCII
`{"c", "k", "f"}` after `°`, so Cyrillic «°С»/«°К» never form a combined unit even
if the keys were lowercase.

Note the secondary symptom «на трёх тысячи мАч»: when the unit is unknown, the
numeral falls into a generic path that produces grammatically inconsistent output
(«трёх тысячи»). Fixing the keys removes this instance, but the mixed-case
inflection in `inflect_numeral_string` is worth a defensive look too.

### B4 (P1) — «С 5 по 10 января» gets the wrong forms

**Verified by execution.**

```text
in  (safe): С 5 по 10 января будут праздники.
out       : С пяти по десятого января будут праздники.
expected  : С пятого по десятое января будут праздники.
```

`TEXT_DATE_RANGE_PATTERN` in [dates_time.py:35](../dates_time.py#L35) only matches
`day1 – day2 month` with a dash. The prose form `с D1 по D2 <month>` falls through
to the generic year/numeral machinery, which renders the first number as a
cardinal in the wrong case and the second as a mismatched ordinal.

### B5 (P1) — «См. гл. 5» → «смотри глава пять» (no inflection)

**Verified by execution.**

```text
in  (safe): См. гл. 5 и рис. 3.
out       : смотри глава пять и рисунок три.
expected  : смотри главу пятую и рисунок три.  (or at least «глава пятая»)
```

Root cause is stage ordering: `run_numerals` (which owns
`normalize_heading_numbers`, aware of «глава 5» → «глава пятая») runs **before**
`run_abbreviations` where «гл.» is expanded to «глава» by a plain string rule in
[abbreviation_rules.py:25](../abbreviation_rules.py#L25). By the time «глава»
appears, the number has already been converted to an uninflected cardinal.
Same class of problem for «стр.», «табл.» expansions that produce
`страница пять`-style output.

### B6 (P1) — `©` is replaced by a bare dot

**Verified by execution.**

```text
in  (safe): © 2024 Компания
out       : . Две тысячи двадцать четыре Компания
```

[constants.py:255](../constants.py#L255) maps `"©" → "."` in
`CLEANUP_REPLACEMENTS`, injecting stray sentence boundaries. Either remove the
symbol or read it («копирайт»).

### B7 (P1) — Case leaks through «равно» onto the arithmetic result (GitHub issue #5)

**Verified by execution** (issue reproduced on current `main`; partially already fixed).

```text
in  (safe): 9 × 11.2 = 73 ₽
out       : девять умножить на одиннадцать целых две десятых равно семидесяти трёх рублей
expected  : … равно семьдесят три рубля

in  (safe): 9 × 11.1 = 73 ₽
out       : … одну десятую равно семьдесят три рубля      # correct only by luck
```

Note: the *multiplier* half of the issue («двух десятых») no longer reproduces on
`main` — the fraction is rendered correctly («две десятых»). What still breaks is
the **result after «равно»**: `get_numeral_case` in
[numerals/_helpers.py:453](../numerals/_helpers.py#L453) scans the two tokens left
of «73», parses «десятых» as an ADJF in genitive, and returns `gent` — the word
«равно» between them is not treated as a context boundary, so the fraction's case
leaks onto the result. When the fraction ends in accusative («одну десятую»), the
leak accidentally produces the right form.

Fix direction: treat «равно» (and similar copula/comparison markers emitted by
`normalize_math_symbols`) as a barrier in the left-context loops of
`get_numeral_case`, defaulting the right-hand side to nominative.

### B8 (P2) — Broken, dead `DECIMAL_PATTERN` in `numerals/_constants.py`

[numerals/_constants.py:642](../numerals/_constants.py#L642) contains
`(?:-|\\ue001)` inside an `rf"..."` string — in a raw string `\\ue001` is a literal
backslash followed by `ue001`, **not** the U+E001 negative-number placeholder.
The pattern is currently dead code (decimals.py builds its own correct
`DECIMAL_PATTERN` with `re.escape(NEGATIVE_NUMBER_PLACEHOLDER)`), but it is an
exported trap for future callers. Delete it or fix the escape.

---

## 2a. Cross-check against GitHub issues

- **Issue #4** («Сделать expand_years_ago_abbreviation отключаемым», @Tomarchelone)
  is the same defect as **B1** above, confirmed independently by a user. Besides
  fixing the false positive, the issue asks for an off-switch: add an
  `enable_years_ago_expansion` option to `NormalizeOptions` (see TASK-1 in the
  fix plan).
- **Issue #5** («Склонение результата при арифметике», @xor2016) is **B7** above.
  On current `main` only the result-after-«равно» half still reproduces; the
  multiplier inflection has since been fixed. The issue can be closed once
  TASK-16 lands, with a note that half was already resolved.

---

## 3. Known limitations observed (document, don't necessarily fix)

- «Ей 30 л. на вид.» → «тридцать литров» — «л.» = «лет» vs «литров» ambiguity.
- Phone numbers: `+7 999 123-45-67` → «семь миллионов девятьсот …» (read as one
  huge number). A phone-pattern guard (digit-by-digit reading in tts mode) would
  be a feature, not a bugfix.
- Version numbers: «Версия 10.15» reads as a decimal fraction.
- Glued «10м провода» → «десятого провода» (`_fix_glued_numbers` classifies bare
  «м» as an ordinal hyphen suffix).
- `M&M's` → «эм энд эм ' эс» — detokenizer leaves a floating apostrophe.

---

## 4. Performance

**Measured** (Python 3.12, this machine, safe mode):

- Number-dense synthetic text: **147 000 chars in 19.3 s ≈ 8k chars/s** — far from
  the README's "274K-char book in 2 s" (plausible for prose with sparse numbers,
  but worth stating the caveat).
- `normalize()` per-call overhead is fine (~1.6 ms for a short string).

Hot spots identified by reading:

- **P1 — `normalize_years` recompiles ~12 regexes on every call**
  ([years.py:213-264](../years.py#L213)). They reference only module constants;
  hoist them to module scope (or `functools.lru_cache` a builder).
- **P1 — `morph.parse()` is called repeatedly for the same tokens** with no
  memoization (`get_numeral_case` alone can parse the same neighbour tokens many
  times, and it recurses). A small `lru_cache` wrapper around
  `get_morph().parse` (word → parses) would likely give a large speedup on
  number-dense text.
- `normalize_cardinal_numerals` re-tokenizes the full text and walks it token by
  token — fine, but each token can trigger several parses (adj/noun lookahead).

---

## 5. Security / robustness

- **P1 — Pickle cache in package directory** ([dictionary.py:74-112](../dictionary.py#L74)).
  `DictionaryNormalizer` loads `dictionaries_*.pkl` with `pickle.load` from the
  dictionaries directory and writes the cache next to the shipped `.dic` files.
  Consequences: (a) loading a pickle from a directory that may be user- or
  world-writable is an arbitrary-code-execution vector; (b) in a read-only
  site-packages install the save fails (silently, warning-level) on **every**
  process start; (c) concurrent processes can race on the file. Recommendation:
  move the cache to `platformdirs`-style user cache dir, use a non-executable
  format (JSON + compiled at load), or drop the cache (load takes ~ms for the
  bundled dictionary).
- P2 — `get_dictionary_normalizer` ([dictionary.py:335](../dictionary.py#L335))
  does a check-then-act on `_normalizers` outside the lock. Benign under CPython
  GIL, but the idiomatic fix (single `with` + inner check only) is one line.
- CLI reads files as UTF-8 only (`__main__.py:13`) — reasonable, but a friendly
  error for non-UTF-8 input would help GUI/CLI users.

---

## 6. Dead code & API nits

| Where | Issue |
| --- | --- |
| [preprocess_utils.py:234](../preprocess_utils.py#L234) | `restore_paragraph_breaks` is a no-op; `normalize_linebreaks` immediately `del`s its `keep_paragraph_placeholders` arg (line 243). The whole `PARAGRAPH_BREAK_PLACEHOLDER` machinery is write-never/read-everywhere: nothing inserts `` anymore, yet caps.py, text_context.py and numerals/_helpers.py still branch on it. Either reinstate paragraph protection or strip the vestiges. |
| [__main__.py:30](../__main__.py#L30) | `--check` flag is parsed but never used. |
| [constants.py:263](../constants.py#L263) | `("-", "-")` no-op entry in `CLEANUP_REPLACEMENTS`. |
| [roman_numerals.py:687](../roman_numerals.py#L687) | `"l": "I"` mapping is unreachable — the pattern char class `[IVXLCDMХхСсІіМм]` doesn't include ASCII `l`. |
| [abbreviations.py:47](../abbreviations.py#L47) | `_LANGUAGE_ORIGIN_ABBREVIATIONS` duplicates a subset of `ADJECTIVE_ABBREVIATION_EXPANSIONS` (abbreviation_rules.py:78). Single source of truth preferred. |
| [preprocess_utils.py:210-215](../preprocess_utils.py#L210) | In `expand_years_ago_abbreviation`, `next_char.isalnum() or next_char.isalpha()` — the second test is redundant. |
| [options.py](../options.py) | `NormalizeOptions.safe(**overrides: object)` / `.tts()` erase type info for keyword args; consider `Unpack`/`TypedDict` or explicit signatures for IDE support. |

---

## 7. Packaging, docs, repo hygiene

- **P2 — README documents an invalid command**: `python -m ru-normalizr ...`
  (README.md:73 and :297). Module names can't contain hyphens; must be
  `python -m ru_normalizr`.
- **P2 — Generated/scratch files are tracked in git**: `.coverage`, `input.txt`,
  `refactoring_plan.md` (AGENTS.md itself forbids committing generated
  artifacts). Add to `.gitignore` and `git rm --cached`.
- Packaging maps the repo root as the package (`package-dir ru_normalizr = "."`)
  — works, but means every stray root file risks shipping; the explicit
  `exclude-package-data` list confirms this is already a maintenance burden.
  A conventional `src/ru_normalizr/` layout would remove the class of problem
  (larger refactor; optional).
- CI is solid (lint + tests + build on 3.10–3.12). Consider adding a coverage
  gate since `.coverage` shows coverage is already being measured locally.

---

## 8. Test suite

- 250 tests, all green; regression-oriented naming is good.
- Gaps that let the P0 bugs above survive: no test for initials «Л. Н.» in safe
  mode, no test for «NNNN г.» at a sentence boundary, no tests for the
  uppercase-key units (°С/мА/мАч), none for «с D по D <месяц>».
  The fix plan ([BUGFIX_PLAN.md](BUGFIX_PLAN.md)) includes a regression test per fix.

---

## 9. Verification environment

```text
Windows 11, Python 3.12 (venv), pip install -e .
pytest: 250 passed, 16 subtests passed in 10.48s
All quoted in/out pairs produced by ru_normalizr.normalize() at commit 3af1b85.
```
