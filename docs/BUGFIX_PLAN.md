# ru-normalizr — Bugfix Plan (for Claude Code / Codex agents)

Companion to [CODE_REVIEW.md](CODE_REVIEW.md). Each task below is self-contained:
repro, root cause, fix sketch, tests, acceptance criteria. Every reported symptom
was reproduced at commit `3af1b85`.

## Ground rules for the agent (read first)

1. Read [AGENTS.md](../AGENTS.md) — it is the repo's contributor contract.
   Key points: smallest correct fix, add a failing test before/with the fix,
   no drive-by refactors, update `CHANGELOG.md` under `## Unreleased` for any
   output-visible change.
2. **One task per commit/PR**, conventional-commit messages
   (e.g. `fix(preprocess): stop expanding uppercase initials as "лет назад"`).
3. Validation after every task:
   ```bash
   py -3.12 scripts/dev.py check      # clean + version + lint + tests + build
   ```
   (or `python -m pytest -q` for quick iteration). The suite must stay at
   250+ passing; new regression tests must fail before the fix and pass after.
4. The package must be installed editable (`pip install -e .`) for tests to
   import `ru_normalizr`.
5. Do each task in order within its priority band; P0 first.

---

## P0 — safe-mode correctness (do these first)

### TASK-1 · fix(preprocess): «Л. Н.» initials rewritten to «лет назад»

> Confirmed by users: **GitHub issue #4** (@Tomarchelone) reports exactly this and
> asks for an external off-switch. Reference the issue in the commit message
> (`Fixes #4`).

- **Repro**
  ```python
  from ru_normalizr import normalize
  normalize("Л. Н. Толстой родился в 1828 году.")
  # actual : 'лет назад. Толстой родился в …'
  # expected: initials preserved (safe) / expanded as letter names only in tts initials stage
  ```
- **Root cause**: `YEARS_AGO_ABBREVIATION_PATTERN` at
  [preprocess_utils.py:54](../preprocess_utils.py#L54) —
  `(?<!\w)л\.?\s*н\.` with `re.IGNORECASE` matches uppercase initials.
  Called unconditionally from `_run_preprocess_steps` (normalizer.py:218).
- **Fix sketch**:
  1. Remove `re.IGNORECASE`; the genuine abbreviation is lowercase «л. н.» / «л.н.».
  2. Require a quantity on the left: only expand when preceded (within a few
     tokens) by a digit or a magnitude word («тыс», «млн», «млрд», «миллионов»,
     «тысяч» …). A lookbehind is impractical for variable width — do the check in
     the `repl` callback against `text[:match.start()]`.
  3. Make sure the genuine case still works: `«Это было 5 млн л. н.»` and
     `«около 10 тыс. л. н.»`.
  4. Per issue #4: add an `enable_years_ago_expansion: bool` option to
     `NormalizeOptions` (default `True` in both mode-default dicts in
     [options.py](../options.py)), thread it through
     `PipelineNormalizer._run_preprocess_steps`, and guard the
     `expand_years_ago_abbreviation` call with it. Follow the existing pattern of
     other `enable_*` flags exactly (frozen dataclass with custom `__init__` —
     the new field must be added to the dataclass fields, the `__init__`
     signature, the `values` dict, and both `_SAFE_MODE_DEFAULTS` /
     `_TTS_MODE_DEFAULTS`).
- **Tests** (new file or `tests/test_reported_regressions.py`):
  - `Л. Н. Толстой родился в 1828 году.` (safe) → initials survive preprocess;
    full-pipeline output contains «Толстой» and does **not** contain «лет назад».
  - `Роман написал Л.Н. Толстой.` (no space variant) → no «лет назад».
  - `Это было 5 млн л. н. примерно.` → still contains «лет назад».
- **Risk**: tts-mode initials expansion happens later in
  `expand_person_initials`; verify tts output for «Л. Н. Толстой» becomes
  letter-name initials («эл эн Толстой»-style), not «лет назад».

### TASK-2 · fix(years): keep sentence-final dot when expanding «NNNN г.» / «N г.»

- **Repro**
  ```python
  normalize("Он родился в 1672 г. Потом вырос.")
  # actual : '…семьдесят втором году Потом вырос.'  (two sentences merged)
  normalize("Вес 5 г. Далее текст.")
  # actual : 'Вес пять грамм Далее текст.'
  ```
- **Root cause**:
  - `replace_with_word` in [years.py:505](../years.py#L505) drops the «г.» dot
    unconditionally. Sibling logic already exists: see `keep_terminal_dot` in
    `replace_s_po` (years.py:340-347) and `_should_keep_era_terminal_dot`
    (years.py:124).
  - `normalize_mass_gram_abbreviations` in
    [abbreviation_context.py:26](../abbreviation_context.py#L26) is a plain
    `\g<context>\g<num> грамм` sub with no tail handling.
- **Fix sketch**: factor the existing keep-terminal-dot heuristic (empty tail /
  newline / next significant char is uppercase or closing quote+uppercase) into
  a small shared helper (natural home: `abbreviation_context.py` or
  `preprocess_utils.py`), then apply it in:
  - `years.replace_with_word` (when the matched `word` ended with `.`),
  - `years.replace_suffix` (same condition),
  - `abbreviation_context.normalize_mass_gram_abbreviations` (switch to a
    callback repl).
  Follow the exact convention used by `_should_keep_era_terminal_dot`.
- **Tests**:
  - `Он родился в 1672 г. Потом вырос.` → output contains `году. Потом`.
  - `Это случилось в 1990 г. в Москве.` → still **no** dot (`году в Москве`).
  - `Он родился в 1672 г.` (end of text) → ends with `году.` (check current
    expectation: today it ends without a dot — decide with tests; the era logic
    keeps the dot at end-of-text, be consistent with it).
  - `Вес 5 г. Далее текст.` → `грамм. Далее`.
- **Risk**: several existing tests assert year outputs; run the full suite and
  reconcile — do not weaken existing expectations without noting it in the
  changelog.

### TASK-3 · fix(numerals): unreachable mixed-case unit keys (°С, °К, мА, кА, мкА, мАч)

- **Repro**
  ```python
  normalize("Температура 25 °С сегодня.")   # Cyrillic С → 'градусов С' (suffix lost)
  normalize("Ток 5 мА в цепи.")             # 'пять мА' (unit not expanded)
  normalize("Батарея на 3000 мАч.")         # 'на трёх тысячи мАч' (broken agreement)
  ```
- **Root cause**: `UNITS_DATA` in
  [numerals/_constants.py](../numerals/_constants.py) stores keys `"°С"`, `"°К"`
  (~lines 320-321), `"мкА"`, `"мА"`, `"кА"` (~344-346), `"мАч"` (~594), but every
  lookup lowercases the token first (`cardinals.py:210`, `decimals.py`,
  `_hyphen.py`). Also `cardinals.py:214-217` combines `°` + suffix only for
  ASCII `{"c","k","f"}`, never Cyrillic `с`/`к`.
- **Fix sketch**:
  1. Lowercase those keys in `UNITS_DATA` (`"°с"`, `"°к"`, `"мка"`, `"ма"`,
     `"ка"`, `"мач"`). ⚠ `"ма"`/`"ка"` become ambiguous with real words —
     check `get_morph()` collisions; if «ма»/«ка» misfire on prose (e.g. «5 ка»),
     it may be safer to keep only the unambiguous ones (`мка`, `мач`, `°с`, `°к`)
     and route bare «мА»→ deliberate decision documented in the test.
  2. Add `"с"`, `"к"`, `"ф"` (Cyrillic) to the degree-suffix set in
     `cardinals.py` so `25 ° С` tokenized forms combine.
  3. Add a module-level sanity assertion (or a unit test) that **every**
     `UNITS_DATA` key equals `key.lower()` so the class of bug can't return.
- **Tests**:
  - `Температура 25 °С сегодня.` (Cyrillic) → contains `градусов Цельсия`.
  - `Батарея на 3000 мАч.` → contains `миллиампер-час` in a grammatical phrase.
  - `test_units_data_keys_are_lowercase` — iterate `UNITS_DATA`.
- **Risk**: watch for new false positives from short Cyrillic keys; run full suite.

---

## P1 — realistic wrong output, security, performance

### TASK-4 · fix(dates): «с D1 по D2 <месяц>» range without dash

- **Repro**: `С 5 по 10 января будут праздники.` →
  `С пяти по десятого января…`; expected `С пятого по десятое января…`.
- **Root cause**: `TEXT_DATE_RANGE_PATTERN`
  ([dates_time.py:35](../dates_time.py#L35)) requires a dash between days; the
  prose form falls through to generic numeral handling.
- **Fix sketch**: add a dedicated pattern
  `\b(?P<p1>с|со)\s+(?P<day1>\d{1,2})\s+(?P<p2>по|до)\s+(?P<day2>\d{1,2})\s+(?P<month>января|…)`
  handled before `TEXT_DATE_RANGE_PATTERN`; render `day1` as genitive ordinal
  neuter («пятого»), `day2` as accusative («по десятое») or genitive for «до».
  Reuse `_day_to_ordinal`.
- **Tests**: the repro; plus `со 2 по 8 марта`, `с 1 до 15 июня`, and a
  non-date guard like `с 5 по 10 человек` (must not become a date).

### TASK-5 · fix(pipeline): «гл. 5» expands after numeral stage → «глава пять»

- **Repro**: `См. гл. 5 и рис. 3.` → `смотри глава пять…`; expected
  `смотри главу пятую…` (or consistent inflected form).
- **Root cause**: stage ordering — `run_numerals` (owns
  `normalize_heading_numbers`) runs before `run_abbreviations` where «гл.» is a
  plain string rule ([abbreviation_rules.py:25](../abbreviation_rules.py#L25)).
- **Fix sketch** (choose the least invasive; do NOT reorder whole stages):
  teach `normalize_heading_numbers` / `HEADING_SINGLE_PATTERN`
  ([numerals/ordinals.py:78](../numerals/ordinals.py#L78)) to also accept the
  abbreviated heads («гл.», «разд.», «ч.» is too ambiguous — skip it) and expand
  them via the same noun-parse machinery (mirroring how roman_numerals handles
  `_ROMAN_ABBREVIATION_TO_CONTEXT`). Then delete/keep the plain «гл.» string rule
  as a fallback for non-numeric contexts.
- **Tests**: repro above; `в гл. 3 говорится` → `в главе третьей говорится`;
  make sure standalone «гл.» (no number) still expands to «глава».

### TASK-6 · fix(preprocess): «©» must not become a bare dot

- **Repro**: `© 2024 Компания` → `. Две тысячи двадцать четыре Компания`.
- **Root cause**: `("©", ".")` in `CLEANUP_REPLACEMENTS`
  ([constants.py:255](../constants.py#L255)).
- **Fix sketch**: replace with `("©", "")` (mirroring `®`/`™`) — or «копирайт »
  if reading it aloud is desired; check tests for the intended behavior first.
- **Tests**: `© 2024 Компания` (safe) → no leading `.`; `Текст © автора` stays sane.

### TASK-7 · fix(dictionary): move pickle cache out of package dir / make it safe

- **Symptom**: `DictionaryNormalizer` writes `dictionaries_*.pkl` into the
  installed package's `dictionaries/` dir and `pickle.load`s it on startup
  ([dictionary.py:74-112](../dictionary.py#L74)). Read-only installs warn on
  every run; a writable shared dir is an arbitrary-code-execution vector;
  concurrent processes race.
- **Fix sketch** (pick one, document in changelog):
  - (a) Simplest: drop the cache entirely — measure first; the bundled
    latinization dictionary is small and `_load_dic_file` is fast.
  - (b) Keep a cache but store under a user cache dir
    (`%LOCALAPPDATA%`/`XDG_CACHE_HOME`, no new deps: build the path manually)
    keyed by dictionaries-path hash + mtimes, and write atomically
    (`tempfile` + `os.replace`).
  - Never unpickle from a directory the package doesn't control.
- **Tests**: construct `DictionaryNormalizer` against a temp dictionaries dir
  twice; assert no `.pkl` appears inside the dictionaries dir (option b) or at
  all (option a), and rules still apply.

### TASK-8 · perf(years): hoist per-call regex compilation

- **Symptom**: `normalize_years` compiles ~12 `re.compile(...)` patterns on
  **every call** ([years.py:213-264](../years.py#L213)); they depend only on
  module constants.
- **Fix sketch**: move the compiles to module level (they're pure constants) or
  wrap in a module-level `@functools.lru_cache` builder returning a namedtuple
  of patterns. Keep the inner closures reading `text` via arguments as they do.
- **Acceptance**: `python -m pytest -q` green; a quick micro-benchmark
  (`timeit` on `normalize_years("В 1995 году")`) shows reduced per-call time.

### TASK-9 · perf(morph): memoize morph.parse for hot paths

- **Symptom**: number-dense text runs at ~8k chars/s; `get_numeral_case`
  ([numerals/_helpers.py:344](../numerals/_helpers.py#L344)) and the cardinal
  walker parse the same tokens repeatedly.
- **Fix sketch**: add
  ```python
  @functools.lru_cache(maxsize=65536)
  def parse_word(word: str): return get_morph().parse(word)
  ```
  in `_morph.py` and route the hottest call sites through it
  (`_helpers.get_numeral_case`, `cardinals.normalize_cardinal_numerals`,
  `caps._restore_known_abbreviations`). Parses are immutable; sharing is safe.
  Do NOT change behavior — result lists must be used read-only.
- **Acceptance**: full suite green; measurable speedup on a ~100KB number-dense
  sample (script it under `scripts/` or a scratch benchmark; do not commit
  benchmark artifacts).

### TASK-16 · fix(numerals): case leaks through «равно» onto arithmetic result (GitHub issue #5)

> Reference the issue in the commit message (`Fixes #5`). Note in the issue that
> the multiplier half («двух десятых») no longer reproduces on `main`; only the
> result case remains broken.

- **Repro**
  ```python
  normalize("9 × 11.2 = 73 ₽")
  # actual : 'девять умножить на одиннадцать целых две десятых равно семидесяти трёх рублей'
  # expected: '… равно семьдесят три рубля'
  normalize("9 × 11.1 = 73 ₽")   # correct today, only by luck («десятую» is accusative)
  ```
- **Root cause**: `get_numeral_case` in
  [numerals/_helpers.py:453-458](../numerals/_helpers.py#L453) — when resolving
  the case for «73», the loop over the two tokens to its left parses «десятых»
  (from the just-rendered fraction) as an ADJF in genitive and returns `gent`.
  «равно» sitting between them is not treated as a context boundary, so the
  left operand's case contaminates the right operand. The same leak affects the
  verb-case loop (lines ~460-465).
- **Fix sketch**: introduce a small set of barrier tokens
  (`{"равно", "="}` — consider also «есть», «это», «приблизительно») in
  `numerals/_helpers.py`; in `get_numeral_case`, stop the left-context scans
  (the ADJF/PRTF hint loop, `blocked_by_noun` scan, and the VERB_CASE loop) when
  a barrier token is encountered, so a number right of «равно» defaults to the
  usual right-context/nominative logic. Alternative (more surgical): have
  `_normalize_contextual_equals` in [numerals/symbols.py](../numerals/symbols.py)
  emit a marker the case resolver respects — but the plain barrier set is
  simpler and testable.
- **Tests** (parameterized over the issue's six inputs):
  - `9 × 11 = 73 ₽`, `9 × 11.01 = 73 ₽`, `9 × 11.1 = 73 ₽`, `9 × 11.0 = 73 ₽`,
    `9 × 11.2 = 73 ₽`, `9 × 11.02 = 73 ₽` — all must end with
    `равно семьдесят три рубля`.
  - Guard: a genuine genitive context still works, e.g.
    `не более 73 рублей` unchanged in behavior.
- **Risk**: `get_numeral_case` is shared by many stages — run the full suite;
  expect no changes outside «равно»-adjacent contexts.

---

## P2 — cleanup, docs, hygiene (batchable)

### TASK-10 · docs(readme): `python -m ru-normalizr` is not runnable

`python -m` takes a **module** name: change both occurrences (README.md ~line 73
and ~line 297) to `python -m ru_normalizr`. Verify:
`py -3.12 -m ru_normalizr "Глава IV." --mode tts` runs after `pip install -e .`.

### TASK-11 · chore(cli): remove or implement the dead `--check` flag

[__main__.py:30](../__main__.py#L30) parses `--check` and ignores it. Remove the
argument (help text says it just prints — which is the default behavior anyway).

### TASK-12 · chore(repo): untrack generated/scratch files

`.coverage`, `input.txt`, `refactoring_plan.md` are tracked.
`git rm --cached .coverage input.txt refactoring_plan.md`, add `.coverage` and
`input.txt` to `.gitignore` (decide whether `refactoring_plan.md` is still
wanted; it looks like a finished scratch plan — likely delete).

### TASK-13 · chore(numerals): delete broken dead `DECIMAL_PATTERN`

Remove `DECIMAL_PATTERN` from
[numerals/_constants.py:642](../numerals/_constants.py#L642) (contains
`(?:-|\\ue001)` — a literal-backslash bug; superseded by the correct pattern in
`numerals/decimals.py`). Grep for imports first (`rg "from ._constants import"` /
`rg DECIMAL_PATTERN`) — today only decimals.py defines/uses its own.

### TASK-14 · chore(preprocess): strip paragraph-placeholder vestiges (or reinstate)

`PARAGRAPH_BREAK_PLACEHOLDER` is never inserted anywhere;
`restore_paragraph_breaks` ([preprocess_utils.py:234](../preprocess_utils.py#L234))
is a no-op; `normalize_linebreaks` `del`s its `keep_paragraph_placeholders`
parameter. Decide: (a) remove the placeholder branches in caps.py,
text_context.py, numerals/_helpers.py and the dead params, or (b) reinstate the
paragraph-protection feature. (a) is the smaller change; keep public
`preprocess_text` signature stable.

### TASK-15 · chore: misc dead entries

- `("-", "-")` no-op in `CLEANUP_REPLACEMENTS` ([constants.py:263](../constants.py#L263)).
- Unreachable `"l": "I"` mapping in `normalize_cyrillic_roman`
  ([roman_numerals.py:687](../roman_numerals.py#L687)) — either add `l` to the
  pattern class deliberately (risky) or drop the mapping.
- Redundant `next_char.isalnum() or next_char.isalpha()` in
  `expand_years_ago_abbreviation` (obsolete once TASK-1 lands).
- Deduplicate `_LANGUAGE_ORIGIN_ABBREVIATIONS`
  ([abbreviations.py:47](../abbreviations.py#L47)) against
  `ADJECTIVE_ABBREVIATION_EXPANSIONS` — import the subset from one place.
- Idiomatic locking in `get_dictionary_normalizer`
  ([dictionary.py:335](../dictionary.py#L335)): take the lock before the first
  membership check.

---

## Suggested execution order & batching

| Batch | Tasks | Note |
| --- | --- | --- |
| 1 | TASK-1, TASK-2, TASK-3 | separate commits; each ships with regression tests + CHANGELOG entries |
| 2 | TASK-4, TASK-5, TASK-6, TASK-16 | output-visible; tests + CHANGELOG; TASK-1 closes issue #4, TASK-16 closes issue #5 |
| 3 | TASK-7, TASK-8, TASK-9 | perf/security; benchmark before/after for 8–9 |
| 4 | TASK-10 … TASK-15 | may be combined into 1–2 chore commits; no CHANGELOG needed except CLI flag removal (TASK-11) and README fix (TASK-10) |

## Definition of done (per task)

- New regression test(s) that fail on `main` and pass with the fix.
- `py -3.12 scripts/dev.py check` fully green.
- `CHANGELOG.md` updated under `## Unreleased` for any output-visible change.
- No version bump (per AGENTS.md, releases are separate tasks).
