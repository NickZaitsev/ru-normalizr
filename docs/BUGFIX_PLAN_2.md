# ru-normalizr — Review & Bugfix Plan #2 (for Claude Code / Codex agents)

Reviewed at commit `194c782` (2026-07-18, branch `main`, clean tree). Follow-up to
[BUGFIX_PLAN.md](BUGFIX_PLAN.md) / [CODE_REVIEW.md](CODE_REVIEW.md), which were executed
earlier the same day (commits `1daa7c8..194c782`).

Every repro below was reproduced by running the library at `194c782` unless marked
otherwise. Differential testing was done against baseline `3af1b85` on a real book
corpus (see "Book acceptance protocol" at the end).

---

## 0. Verification of the 2026-07-18 commit batch (done, no action needed)

- `py -3.12 scripts/dev.py check` — green (lint, 269 tests, build, twine).
- Full-book differential (1,099,288 chars) `3af1b85` vs `194c782`, both modes:
  **13 changed lines out of ~4,600**. 11 are clear improvements (correct genitives
  «из ста участников», «потери ста долларов», restored sentence dot after «года»),
  1 is the intended arithmetic-result convention change (`2267f42`, «равно сорок семь»
  in nominative), 1 flip is attributable to the pre-existing nondeterminism described
  in TASK-1 (not to any rule change).
- Performance on the book: **19.5 s → 6.7 s tts (2.9×), 18.3 s → 6.0 s safe (3.0×)**.
- Fast-path guards (`442b738`), morph caches (`2f05ba0`, `c10a7e4`), dotted-unit
  boundary (`53f2648`), linear context scan (`7fc47db`), dead-code removal (`f542bda`)
  were adversarially reviewed — sound.
- Two compat notes to be aware of (documented, not regressions):
  - `c98b6e1`: `--check --output` is now a hard CLI error (was accepted before).
  - `ec090b5`: `YEARS_AGO_ABBREVIATION_PATTERN` lost `re.IGNORECASE`, so sentence-initial
    «Тыс. л. н.» no longer expands. Marginal; revisit only if reported.

Conclusion: **the batch did not introduce rule regressions.** Three bugs initially
suspected as regressions (date ranges, `гл. N-M`, decade misreads) reproduce
identically at `3af1b85` — they are pre-existing and are now TASK-2/3/4.

---

## Ground rules for the agent (read first)

1. Read [AGENTS.md](../AGENTS.md). Key points: fix the rule, not the string; smallest
   correct fix; failing test before/with the fix; `CHANGELOG.md` under `## Unreleased`
   for any output-visible change; keep numeral scans linear
   (see [performance invariants](agents/performance-invariants.md)).
2. One task per commit, conventional-commit messages.
3. Validation after every task: `py -3.12 scripts/dev.py check` (quick loop:
   `py -3.12 scripts/dev.py test`).
4. After every P0/P1 task additionally run the **book acceptance protocol** (below).
5. Work in priority order: P0 → P1 → P2 → P3. Within a band, order as listed.

---

## P0 — determinism

### TASK-1 · fix(numerals): normalize() output depends on prior calls in the process

**Symptom.** The same input text produces different numeral case forms depending on
what was normalized earlier — across calls on the same instance, across separate
`Normalizer` instances, and even for the same sentence at different positions inside
one text. Confirmed at `194c782` **and** at baseline `3af1b85` (pre-existing).

**Repro** (two clean processes, tts mode; sentences from the book corpus):

```python
tail = ("Если функция точна, одна и та же психологическая дистанция отделяет "
        "100 тысяч долларов от 1 миллиона, а 10 миллионов — от 100 миллионов долларов.")
para = "<the full paragraph from the book that ends with this sentence>"
# (any longer text containing `tail` as its final sentence reproduces it;
#  the original is book line 2621, «Как хорошо понимал Фехнер…»)

# Process A:
Normalizer(tts).normalize(para)                 # → «…от сто миллионов долларов.»  (wrong)
# Process B:
n = Normalizer(tts); n.normalize(tail); n.normalize(para)
                                                # → «…от ста миллионов долларов.»  (correct)
```

**Evidence gathered.**
- Clearing only `numerals._helpers.inflect_numeral_string.cache_clear()` between the
  two calls in process B flips the result back — the `lru_cache` is the state carrier
  that freezes whichever value happened to be computed first.
- With the cache bypassed, the *uncached* function returned different results for
  identical args within one run: `('100', 'gent', 'masc')` → `'сто'` (early call),
  `'ста'` (later call). So the underlying computation reads hidden mutable state.
- Tracing `num2words.num2words` shows that for the key `('100','gent','masc')` the
  expected `case='genitive', gender='masculine'` call never reaches num2words in the
  failing run — some branch (the `except Exception` fallback in
  `inflect_numeral_string`, `numerals/_helpers.py:264`, or a caller in
  `numerals/cardinals.py`) silently degrades to the bare
  `num2words(value, lang="ru")` nominative path.
- The installed num2words is a fork with case/gender kwargs on `to_cardinal` and a
  shared singleton converter (`num2words.CONVERTER_CLASSES['ru']`).

**Fix direction.**
1. Root-cause which branch produces `'сто'` for `('100','gent','masc')`: instrument
   `inflect_numeral_string` and its callers in `cardinals.py`; find what hidden state
   (num2words singleton, exception-once path, or a caller-level heuristic that
   consults cache contents) makes it non-reproducible.
2. Make the whole pipeline a pure function of `(text, options)`: any `lru_cache`d
   helper must itself be pure. If num2words converter state is the culprit, isolate it
   (fresh converter per call is too slow — snapshot/restore its mutable attrs, or lock
   down the kwargs so the stateful path is never hit).
3. Regression test: normalize a fixture corpus twice — (a) each sentence in a fresh
   normalizer with all module caches cleared, (b) all sentences sequentially — assert
   identical per-sentence output. Add the para/tail pair above as a direct case.

**Acceptance.** Book output byte-identical across two runs with different chunk
splits (whole file vs per-line). The «имеющего ста дукатов» flip in the book diff
disappears (both orders give the same, correct form).

---

## P1 — correctness (deterministic rule bugs, all verified at `194c782`)

### TASK-2 · fix(dates): prose day range drops the year form

- `с 25 по 31 декабря 2023` → `с двадцать пятого по тридцать первое декабря две тысячи двадцать три`
- Expected: `…декабря две тысячи двадцать третьего года` (ordinal genitive + «года»).
- Cause: `TEXT_DATE_FROM_TO_PATTERN` (`dates_time.py:35`) consumes the day range but has
  no optional year group (unlike `TEXT_DATE_PATTERN`), so the bare year later falls
  through to plain cardinals (the years stage requires a год-word).
- Fix: add an optional `(?P<year>\d{4})` tail mirroring `TEXT_DATE_PATTERN`, reuse its
  year-rendering helper. `с 5 по 10 января 2024 года` (already works) must not change.

### TASK-3 · fix(numerals): abbreviated heading references break ranges

- `гл. 1-3` → `глава первая-три`; `см. гл. 10-12` → `смотри главу десятую-двенадцать`.
- Expected: range semantics preserved: `главы с первой по третью` / existing heading-range
  convention (`главы один — три` was the old form; pick the convention used by
  `normalize_heading_ranges` for full-word «глава» and match it).
- Cause: `ABBREVIATED_HEADING_PATTERN` (`numerals/ordinals.py:84`) matches `\d+\b` — the
  first number of a range, because `-` is a word boundary. The full-word path is
  protected by `normalize_heading_ranges` running first; the abbreviated path is not.
- Fix: route `гл.` (and siblings `табл.`, `разд.`, `рис.`, `стр.` where applicable)
  through the existing heading machinery instead of the parallel one-off regex, or at
  minimum add a range guard `(?!\s*[-–—]\s*\d)`. This also addresses the "hack-flag"
  on `e4ccceb`: generalize, don't special-case «гл» alone.

### TASK-4 · fix(years): comma enumerations misread as decade ranges

- `маршруты 10, 20-е отменены` → `маршруты десятые — двадцатые отменены`
- `страницы 10, 12-е издания` → `страницы десятые — двенадцатые издания`
- Cause: the decade pattern (`years.py:214`) accepts `(?:[-–—]|,)` between the two
  numbers with **no год-word and no preposition required**, so `N, M-е` enumerations
  are rewritten as ranges. Note: at `3af1b85` this pattern's source had an f-string
  bug (`{2,4}` interpolated as a tuple) — behavior is nevertheless identical at both
  commits, so treat as pre-existing.
- Fix: for the comma variant require a год-context (following `год…`/`гг.` word) or
  decade-plausible values (`10..90` step 10, e.g. `60, 70-е годы`); keep the dash
  variant as is. Add both false-positive tests above and true-positive
  `в 60, 70-е годы` coverage.

### TASK-5 · fix(numerals): preposition case leaks across verbs; governing noun ignored

- `из-за которой упустили 150 тысяч долларов.` → `…упустили ста пятидесяти тысяч…`
  («из-за» genitive is attributed to a numeral three tokens away, across the verb
  «упустили»; expected accusative `сто пятьдесят тысяч долларов`).
- `радость от выигрыша не перевесит огорчения от потери 100 долларов` →
  `…от потери сто долларов` (expected `ста долларов`: genitive governed by «потери»).
- Cause: `_get_preposition_before_number` (`numerals/_helpers.py`) scans back up to 3
  tokens with barriers only from `NUMERAL_CONTEXT_BARRIERS`; verbs are not barriers.
  Meanwhile a governing genitive noun directly before the numeral («потеря/потери,
  выигрыш, стоимость, цена…») is not used as a case source at all.
- Fix (rule-level, morphology-aware): during the back-scan, treat tokens whose primary
  pymorphy parse is VERB/INFN/GRND as barriers; add a "governing noun requires
  genitive" check for the immediate left neighbor when it is a case-reliable noun in
  genitive/nominative that governs quantity. Keep the scan linear (see performance
  invariants).

### TASK-6 · fix(numerals): `%-ная`/`N-ный` compound adjectives are dismembered

- `30%-ная надбавка` → `тридцать процентов — ная надбавка`
- Expected: `тридцатипроцентная надбавка`.
- Fix: detect `<number>%-<adj-suffix>` (and `<number>-<suffix>` compounds like
  `50-летний`, check existing handling first) before the percent symbol expansion;
  build the compound adjective via the ordinal-stem machinery (`тридцати` +
  `процентн` + inflected suffix). This is a rule for the whole class, not for «30».

### TASK-7 · fix(abbreviations): bibliographic «Т.» and «Vol.» misexpanded

- `в журнале (1984. Т. 34)` → `…(одна тысяча девятьсот восемьдесят четыре тонны тридцать четыре)`
  — «Т.» read as «тонны»; expected «том тридцать четыре» (bibliographic volume).
- `Vol. 34` → `вол. Тридцать четыре` — «Vol.» latinized to «вол»; expected «том»
  (or at least a non-animal transliteration).
- Fix: unit abbreviation «т» (tonne) must require a preceding number in a measure
  context; «Т.» followed by a number in citation context (inside parens after a year,
  or capitalized standalone) is «том». Add `Vol.`/`No.`/`P.`/`С.` bibliographic
  handling to the abbreviation dictionary as a class (dictionary-driven, not inline).

### TASK-8 · fix(caps): sentence-start capitalization fires after a quoted question

- `вопрос "сколько?" заставляет думать` → `вопрос "сколько?" Заставляет думать`
- Cause: sentence-boundary detection in `caps.py` treats `?"` as end of sentence and
  capitalizes the next word, even when the quote is an embedded phrase followed by a
  lowercase continuation.
- Fix: when `?`/`!` is followed by a closing quote and the next word was originally
  lowercase, do not capitalize (writer's lowercase is the signal the sentence
  continues). Related locked-in snapshots to revisit while here:
  `tests/test_api.py:222-244` («Автомобиль С Компьютерным…» random Title-Case).

### TASK-9 · fix(numerals/ordinals): agreement bugs (gender, instrumental, о/об)

All verified at HEAD, each needs a failing test first:

| Input | Actual | Expected |
|---|---|---|
| `3-я глава` | `третий глава` | `третья глава` |
| `с 5 книгами` | `с пяти книгами` | `с пятью книгами` |
| `и теперь мне уже 35, а` | `мне уже тридцати пяти` | `мне уже тридцать пять` |
| `стих об 1-ой женщине` | `об первой женщине` | `о первой женщине` |
| `перед 8 марта` | `перед восьмого марта` | `перед восьмым марта` |

Notes: the `3-я` bug is gender agreement from the suffix (`-я` → feminine) being
overridden by the noun's parse; `с N <noun-instr>` must map to instrumental numeral;
the `об`→`о` allomorph must be re-evaluated after substitution (rule: «о» before
consonant-initial word, «об» before vowel); `перед` governs instrumental for dates.
Fix in the shared case/gender resolution helpers, not per-input.

### TASK-10 · fix(dates/time): standalone numeric dates and HH:MM:SS

- `12.05.2025` (standalone/start of line) → `Двенадцать точка пять.Две тысячи двадцать пять`
  (mid-sentence it works correctly: «двенадцатого мая две тысячи двадцать пятого года»).
- `в 10:07:30` → `в десять, ноль семь: тридцать` (raw colon survives).
- Fix: allow the DD.MM.YYYY pattern to match at string/line start (currently it seems
  to require a preceding context token); extend the time pattern with optional
  `:SS` («десять часов семь минут тридцать секунд» in tts, per existing time
  convention).

---

## P2 — test-suite repair (tests that lock in wrong Russian)

Full audit (2026-07-18) found the suite green but freezing incorrect output in
places. **Process for every item: decide the correct Russian first, write it in the
test, then fix the rule until it passes.** Never adjust the expectation to match code.

### TASK-11 · Wrong-logic expectations to correct (with rule fixes)

- `tests/test_reported_regressions.py:504` — expects `мне уже тридцати пяти` (see TASK-9).
- `tests/test_reported_regressions.py:154-162` — expects `диаметром двух — шести футов`;
  correct is nominative `диаметром два — шесть футов` (same file line 368 already
  expects nominative for «высотой пятнадцать метров» — the suite contradicts itself).
- `tests/test_api.py:371` — expects `для сто восьмидесяти…`; correct genitive of 180 is
  `ста восьмидесяти` (compound must inflect all words).
- `tests/test_api.py:467` — expects `при -20°C и -1 %` → `…и минус один процент`;
  correct: `минус одном проценте` (coordination under «при»).
- `tests/test_api.py:612` / `tests/test_stages.py:546` — `ст. 49 УК РФ`: no case/ordinal
  agreement («статья сорок девять уголовный кодекс…»); decide convention (at minimum
  genitive «уголовного кодекса Российской Федерации»), fix rule and tests.
- `tests/test_api.py:761` — `1990–2000 гг.` read as decades («девяностые — двухтысячные»)
  plus a spurious sentence break; correct: year range «с … по двухтысячный год».
- `tests/test_stages.py:137/707`, `tests/test_reported_regressions.py:319` —
  `по … вв.`/`гг.` should end singular («по восемнадцатый век», «по … год»);
  lines 141-144 «до восемнадцатого веков» → «века».
- `tests/test_hyphen_tokens.py:23` — `Z80A` → «зи восемьдесят-э»; English A is «эй».

### TASK-12 · Latinization: replace wrong-output snapshots with ground truth

`tests/test_regressions.py:90-99, 241-256, 274-290` freeze admittedly wrong
transliterations («энджинИаинг» with a capital И mid-word, «даунлооад», «аркхивэс»,
«саппот», «плэтфом»). Options (pick one, document in the test file):
(a) fix the fallback transliteration rules and update expectations to correct forms;
(b) keep as `xfail`/`# known-wrong` markers so they stop reading as specification.
Add a small ground-truth table test (10–20 common words: support, platform, download,
device, code, improve…) for the non-IPA fallback path.

### TASK-13 · Resolve internal convention conflicts (document in `docs/agents/conventions.md`)

1. Measure-noun + numeral case: «диаметром/высотой/объемом N» → nominative (pick one).
2. `с … по …` + век/год: singular.
3. Byte-family plurals: `МБ` → «мегабайтов» vs `байт` → «байт» — unify counting forms.
4. `см./смотри` + reference: accusative («смотри рисунок два, таблицу три, страницу четыре»).
5. Initials: comma-injection rules («Рихтер, чэ,» vs no-commas test) — one rule.
6. Letter names: fix «э» → «эй» for A; decide vowel-doubling convention for Cyrillic
   initials — «Е.» → «ее» collides with the pronoun (S8 in audit); consider «е точка»
   or name-expansion off by default.

### TASK-14 · Coverage gaps (new tests, then fix what fails)

- Instrumental prepositions: `с 5 книгами`, `с 3 друзьями`, `перед 8 марта` (TASK-9).
- Feminine hyphen-ordinals: `3-я глава`, `2-я мировая война` (TASK-9).
- Standalone `12.05.2025`, `10:07:30` (TASK-10).
- `2,5 млн человек` → must keep «человек» (currently «людей» — wrong lexeme).
- Math symbols: `×`, `+`, binary `−`, `÷`, `^` (book shows raw `^` surviving: «) ^ два»).
- Ellipsis preservation: `…` must survive normalization as a prosodic break
  (book/test audit shows inner ellipses deleted when numbers are adjacent).

---

## P3 — performance (next round; target ≈2× on the book, keep linearity)

Profile at `194c782`, 300k chars of the book, tts: total 1.94 s. Breakdown:
`re.Pattern.sub` 1.14 s cumulative across **46.5k calls** (58%); numerals 0.65 s;
preprocess 0.32 s (quote pairs 111 ms, linebreaks 72 ms); caps 0.24 s (1,367 per-line
calls, 42.6k `_is_caps_token`); abbreviations 0.18 s; years 0.16 s; roman 0.10 s;
pymorphy 996 parses / 0.18 s (cache works). ~44k of the sub calls go through
module-level `re.sub` — i.e. per-token/per-line loops, not big-text passes.

Rules of engagement: after each perf task, book output must be **byte-identical**
(compare sha256 from the benchmark); `scripts/benchmark.py` synthetic cases must not
regress; scans stay linear (`docs/agents/performance-invariants.md`).

- **TASK-15 · perf(caps):** batch the per-line work — cheap predicate per line
  (`any(c.isupper())`-style or one compiled scan) before `_normalize_inline_caps`;
  fold `normalize_sentence_start_caps`'s 1,363 subs into one pass.
- **TASK-16 · perf(dictionary):** `_apply_dic_rules` fires 722 subs per run; add
  literal-hint prefiltering (as `abbreviations.py` does since `442b738`): skip a rule
  unless its required literal substring occurs in the (casefolded) text; group rules
  by first character or combine into alternations where replacements allow.
- **TASK-17 · perf(preprocess):** merge the multiple full-text passes
  (`normalize_ascii_quote_pairs` ×3, `normalize_linebreaks` ×3) into single-scan
  implementations guarded by `'"' in text` / `'\n' in text` checks.
- **TASK-18 · perf(numerals):** stop re-tokenizing between sub-stages — `simple_tokenize`
  /`detokenize` round-trips and 50k `parse_integer_token` calls; tokenize once per
  numerals stage-group and pass the token list through.
- **TASK-19 · perf(pipeline):** hunt the remaining ~44k module-level `re.sub` calls
  (profile callers of `re/__init__.py:179`); convert hot per-token loops to
  precompiled patterns applied to the whole text, or add candidate guards.

---

## Book acceptance protocol (run after every P0/P1 task and before any release)

Corpus: Kahneman, «Думай медленно… решай быстро» —
`C:\Users\softmg\Downloads\Kaneman_Dumay-medlenno-reshay-bystro.tbsahw.385321.fb2\`
(a **folder**; contains the source `.fb2` and extracted `text.txt`, 1,099,288 chars).
The benchmark accepts the folder directly. **Never commit the book text (copyright).**

```bash
py -3.12 scripts/benchmark.py --book "C:\Users\softmg\Downloads\Kaneman_Dumay-medlenno-reshay-bystro.tbsahw.385321.fb2" --mode both
```

Reference at `194c782` (single run, machine-dependent — compare sha exactly, timing ±5%):

| case | mode | median | throughput | out chars | sha256 |
|---|---|---|---|---|---|
| book | safe | 5.50 s | 199,851 c/s | 1,156,050 | `b924c75f3b968f79` |
| book | tts  | 6.08 s | 180,729 c/s | 1,151,916 | `fdc955ac1ac19701` |

Procedure per task:
1. Before the change: run the benchmark, save both mode outputs
   (`normalizer.normalize(book_text)` dumped to files in a scratch dir outside the repo).
2. After the change: rerun, `diff` old vs new output. **Every changed line must be
   explained by the task's intent**; unexplained diffs are regressions — investigate
   before committing.
3. Timing: no >5% throughput regression for correctness tasks; perf tasks must show
   their claimed improvement here, not only on synthetic cases.
4. For TASK-1 specifically: whole-file run vs per-paragraph run must produce
   identical output (this is the determinism acceptance).

Differential-vs-any-commit recipe (used for this review):

```bash
git worktree add <scratch>/base/ru_normalizr <commit> --detach
python - <<'EOF'
import sys, time
sys.path.insert(0, r"<scratch>/base")   # parent dir; folder is named ru_normalizr
import ru_normalizr
text = open(r"<...>/text.txt", encoding="utf-8").read()
n = ru_normalizr.Normalizer(ru_normalizr.NormalizeOptions.tts())
t0 = time.perf_counter(); out = n.normalize(text); dt = time.perf_counter() - t0
open(r"<scratch>/out_base.txt", "w", encoding="utf-8").write(out)
print(f"{dt:.2f}s, {len(text)/dt:,.0f} chars/s")
EOF
# same for HEAD, then: diff out_base.txt out_head.txt
git worktree remove <scratch>/base/ru_normalizr
```

---

## Suggested sequencing

| Order | Tasks | Why |
|---|---|---|
| 1 | TASK-1 | Everything else is diffed against book output; it must be stable first |
| 2 | TASK-2..4 | User-visible misreads of dates/headings/enumerations |
| 3 | TASK-5, 9 | Shared case-resolution machinery — do together, heavy test overlap |
| 4 | TASK-6..8, 10 | Independent rule fixes |
| 5 | TASK-13 → 11 → 12 → 14 | Conventions first, then fix tests+rules against them |
| 6 | TASK-15..19 | Perf, each gated by byte-identical book output |
