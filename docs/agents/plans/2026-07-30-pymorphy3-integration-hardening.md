# Plan: Harden the pymorphy3 integration

Status: in progress since 2026-07-30.

> Note for agents: this plan is a point-in-time snapshot — its "codebase facts" describe the code as of the date above and may be outdated. Do NOT treat it as current architecture docs; verify every fact against the actual code before relying on it.

## Context

`ru-normalizr` uses `pymorphy3` as a shared morphological analyzer for parse
selection, case and gender inference, numeral and unit agreement,
abbreviation expansion, ordinal rendering, Roman numerals, and years. The
project currently resolves `pymorphy3==2.0.6` with
`pymorphy3-dicts-ru==2.4.417150.4580142`; PyPI and the upstream repository
show that 2.0.6 is the latest release as of this plan.

The basic API usage is sound: `MorphAnalyzer` is created once, parse results
are immutable enough to cache, `parse()` results are cached as tuples, and
callers generally guard `inflect()` returning `None`. The upstream
documentation and 2.0.6 source nevertheless expose several contracts which
the project does not apply consistently:

- `parse()` sorts by a non-contextual `P(tag|word)` score. Upstream explicitly
  warns that the first parse is not reliable contextual disambiguation.
- `OpencorporaTag` exposes domain-relevant grammemes such as `ms-f` (common
  gender), `Pltm`/`GNdr` (pluralia tantum without gender), `Sgtm`,
  `Coun`, `Fixd`, `Name`, `Surn`, and `Geox`.
- `MorphAnalyzer.TagClass.fix_rare_cases()` is the authoritative conversion
  for `gen1`, `gen2`, `acc1`, `acc2`, `loc1`, `loc2`, and `voct`.
- `Parse.inflect()` retries with `fix_rare_cases()` only when the exact
  requested form does not exist. Callers which send a rare case to another
  renderer first can therefore produce the wrong case before `inflect()` is
  reached.
- In the installed dictionary, known-word inventory contains 435 `gen2`,
  211 `loc2`, and 149 `voct` forms; no `gen1`, `loc1`, or `acc2` forms were
  found. `acc1` is present in `RARE_CASES` but absent from
  `KNOWN_GRAMMEMES`, so membership-testing it against a tag raises
  `ValueError`; canonicalize sets through `fix_rare_cases()` instead.

Confirmed end-to-end defects in the current code are:

- `normalize("2-я коллега") == "второй коллега"` and the same happens for
  `сирота`: the explicit feminine suffix is discarded when the noun has
  `ms-f` and no `tag.gender`.
- `normalize("2-е сутки") == "вторых сутки"`: the first parse of `сутки` is
  plural accusative, and plural inanimate accusative is not normalized to the
  nominative form used by an ordinal.
- Unit lemmas are parsed by taking the first noun candidate. This chooses the
  male name `лир` for currency `лира`, so `1 ₺`, `2 ₺`, and `5 ₺` become
  `одна лир`, `две лира`, and `пять лиров`.
- The packaged OpenCorpora dictionary represents `шекель` only as a
  singular-only geography and `грей` only as a singular-only surname.
  Consequently `5 ₪` becomes `пять шекель` and `5 грей` becomes
  `пять грей`.
- Domain units which rank an animate/person parse first are declined as
  animate in singular accusative: `на 1 Па`, `на 1 Вб`, and `на 1 Зв`
  become `на один паскаля`, `на один вебера`, and `на один зиверта`.
- The dictionary has no domain-correct paradigms for several supported
  values. `тенге` is treated as a form of `тенг`; `фарад` as a form of the
  feminine `фарада`; and `тесла` as a form of neuter `тесло`. The unit
  metadata also assigns masculine agreement to feminine Korean `вона` and
  feminine agreement to masculine amount-of-substance `моль`.
- Unit token resolution case-folds symbols whose case changes their value.
  It conflates `mW`/`мВт` with `MW`/`МВт`, `Mb` with `MB`, and Cyrillic
  `Гр` (gray) with `гр` (gram). All-Roman-letter `MV` can reach Roman
  normalization and become `1005` instead of megavolts.
- `resolve_unit_info()` strips terminal dots before lookup, making all six
  dotted-only registered aliases unreachable: `п.п.`, `б.п.`, `в.`,
  `л.с.`, `л. с.`, and `рад.`. Unit `сутки` also lacks plural-only
  number-form policy, so `2 сут.` becomes `двое сутки` rather than
  `двое суток`.
- Rare-case normalization is duplicated and incomplete outside cardinal
  rendering. For example, `noun_parse_case()` maps only `loc2`, and a `gen2`
  noun parse makes `render_ordinal_from_noun_parse(2, parse)` render
  nominative `второй` instead of genitive `второго`.
- Context scanners still confuse a syntactic adjective or noun with its
  highest-ranked homonym. `гос. часовой стрелки` expands to
  `государственный часовой стрелки`, and `1 пасть` uses masculine
  `один` because the first parse of `пасть` is an infinitive. Likewise,
  first-person plural `достигаем` ranks a short-adjective homonym first, so
  its genitive governance is lost (`достигаем 5 целей`).
- Implicit-year detection checks only the first normal form. A measurement
  such as `дозу в 2020 зивертов` is therefore rendered as
  `дозу в две тысячи двадцатом зивертов`.
- `normalize_fractions()` inflects a generated numerator token by token
  instead of using the project's complete numeral renderer. This leaves
  `сто` unchanged in oblique cases and produces `двух тысячи`; a separate
  stage-order collision consumes `1000/100` as an ordinal plus a slash in
  dative/prepositional contexts.

Every item above is pinned through a natural full-message
`pytest.mark.xfail(strict=True)` regression in `tests/test_known_gaps.py`.
Multi-case defects use pytest parameterization, so every message is an
independent strict xfail and a partial fix becomes an immediate XPASS
failure. When an item is fixed, move its test into the regular focused suite
rather than deleting the assertion.

There is also a backend migration opportunity. The current environment
uses pure-Python `DAWG2-Python` (`pymorphy3.dawg.EXTENSION_AVAILABLE` is
false). On this Windows/Python 3.11 environment, an isolated
`pymorphy3[fast]==2.0.6` run installed a wheel successfully and parsed the
same 10,000 distinct known words at approximately 146k words/s versus 21.5k
words/s for the pure-Python backend. The user approved making the compiled
DAWG backend the default, but only after an isolated baseline-versus-candidate
parity gate proves that public normalization output and public morphology
results do not change. Performance alone is not sufficient evidence.

## Approved decisions

1. Proceed without further product questions, as explicitly requested by the
   user, and use conservative defaults which preserve existing documented
   normalization conventions.
2. Keep `pymorphy3` as the morphology engine. Do not fork it, patch
   site-packages, compile a custom OpenCorpora dictionary, or add a second
   general-purpose morphology dependency.
3. Centralize parse selection and rare-case handling instead of adding
   phrase-specific replacements.
4. Treat explicit ordinal suffix information as stronger evidence than
   `pymorphy3`'s non-contextual first parse, especially for common-gender and
   plural-only nouns.
5. Keep ordinary byte-family counting forms from
   `docs/agents/conventions.md` (`5 байтов`, including prefixed units); do not
   switch them to OpenCorpora `Coun` forms merely because such a parse ranks
   first.
6. Represent domain lexemes which the packaged dictionary cannot inflect
   correctly through typed unit-lexicon morphology metadata, including
   expected animacy, indeclinability, and validated paradigm seeds/forms.
   Do not add one-off regex substitutions for a token or complete phrase.
7. Resolve SI and information-unit symbols in exact case whenever case
   changes the prefix, bit/byte meaning, or collides with another unit.
   Optional permissive aliases may remain only when they are unambiguous.
   Protect exact unit tokens before Roman-numeral recognition.
8. Make `pymorphy3[fast]` the default dependency on supported CPython
   platforms only after a clean-environment parity comparison against the
   current pure-Python backend passes with zero differences. The comparison
   must cover public `normalize()` output and the public parse/inflection
   fields consumed by this project. If any difference remains unexplained,
   do not switch the dependency; record the mismatch and keep the portable
   backend while the morphology fixes proceed.
9. Add a `<3` compatibility ceiling for both direct pymorphy packages while
   retaining the lockfile's exact resolved versions. Do not bump the project
   version as part of this work.

## Key codebase facts

- `src/ru_normalizr/_morph.py` owns the single cached `MorphAnalyzer`,
  the 65,536-entry `parse_word()` cache, and the local `MorphParse`
  protocol. All project morphology calls route through this module.
- `pymorphy3` 2.0.6 documents that `parse()` always returns at least an
  `UNKN` parse. The existing `first_parse()` guard is still useful as a
  compatibility boundary and should remain.
- `src/ru_normalizr/numerals/_helpers.py` already has `safe_inflect()`,
  `inflect_unit_lemma()`, `is_case_reliable_noun()`, and
  `get_target_tags_for_number()`. `safe_inflect()` is the established
  failure boundary and logs broad fallbacks at `DEBUG`.
- `src/ru_normalizr/numerals/_num2words.py::SECONDARY_CASE_TO_PRIMARY`
  duplicates upstream `MorphAnalyzer.TagClass.fix_rare_cases()`. Several
  other files separately special-case only `loc2`.
- `src/ru_normalizr/ordinal_utils.py` contains `noun_parse_case()`,
  `choose_noun_parse()`, `render_ordinal()`, and
  `render_ordinal_from_noun_parse()`. `noun_parse_case()` currently maps only
  `loc2`, and `render_ordinal()` converts singular inanimate accusative to
  nominative but not plural inanimate accusative.
- `src/ru_normalizr/numerals/ordinals.py::normalize_ordinals()` derives useful
  evidence from the written suffix, then discards that gender/case evidence
  when `right_noun` is found and calls
  `render_ordinal_from_noun_parse()` without hints.
- `src/ru_normalizr/numerals/_constants.py::UNITS_DATA` is already the
  domain lexicon for unit token, lemma, gender, category, and optional suffix
  data. Mixed-case SI token routing has separate invariants documented in
  `docs/agents/case-sensitive-units.md`; do not weaken that resolver.
- BIPM/NIST define SI prefix symbols as case-sensitive (`m` milli, `M` mega)
  and unit symbols derived from names with their specified capital letters.
  NIST likewise distinguishes bit `b` from byte `B`. Exact token routing is
  therefore correctness, not merely preferred typography.
- `src/ru_normalizr/numerals/_helpers.py::inflect_unit_lemma()` accepts target
  tags but picks the first noun parse and has no way to receive the expected
  unit gender or domain morphology metadata.
- The current dictionary parses `лира` first as
  `NOUN,anim,masc,Name` with normal form `лир`; the correct currency parse is
  `NOUN,inan,femn` with normal form `лира`.
- The current dictionary has usable inanimate paradigms for `ньютон` and
  indeclinable `генри`, despite also returning person-name parses. Candidate
  selection must prefer good domain parses without rejecting all lexemes
  carrying `Name`/`Surn`/`Geox`.
- The current dictionary has no correct selectable normal form for `тенге`,
  `фарад`/prefixed farads, or unit `тесла`; these require validated domain
  forms rather than blind use of a predicted homonym. `шекель` and `грей`
  likewise lack productive domain paradigms.
- `Parse.is_known` checks whether the surface word occurs anywhere in the
  dictionary. It does not certify that a particular homonymous candidate is
  the domain-correct one, so it cannot be a primary selector criterion.
- `docs/agents/conventions.md` requires ordinary byte-family forms and
  aligned reference/range output. Some byte lemmas have a first `Coun` parse,
  while others do not, so first-parse behavior would make prefixed byte units
  inconsistent.
- `pymorphy3` does not ship a `py.typed` marker in 2.0.6. Keep a local
  protocol rather than importing private result types for static typing.
- `pymorphy3` exposes `Parse.make_agree_with_number()`, but it is not a
  drop-in replacement for the project's logic: the project must render the
  numeral itself, preserve documented ordinary byte forms, and support
  explicit external cases. It may be used as a reference oracle in tests,
  not as an unconditional implementation replacement.
- `MorphAnalyzer.parse()` lowercases internally. Routing cache keys through a
  lowercase-only private cache is output-equivalent and avoids duplicate
  entries for `Фёдор`/`фёдор`; do not fold `е` and `ё`, because strict
  candidate sets can differ.
- `pymorphy3==2.0.6` declares `DAWG2>=0.9.0,<1.0.0` for its `fast` extra on
  CPython and retains `dawg2-python>=0.8.0` as its portable dependency.
  `DAWG2==0.13.3` publishes CPython 3.10-3.13 wheels for Windows, macOS,
  manylinux, and musllinux, which covers the project's declared Python
  versions on its mainstream platforms as of this plan.

## Completed audit coverage

The second pass reviewed every current `parse_word()`,
`first_parse_required()`, and direct `Parse.inflect()` call. Its disposition
is part of the implementation contract:

- `_morph.py`: singleton initialization, immutable tuple caching, non-empty
  `UNKN` fallback, lowercase cache duplication, and concurrent reuse were
  checked. A 16-worker parse/inflect stress run completed without exceptions.
- `abbreviations.py`: static adjective and language lemmas are unambiguous;
  person-initial logic correctly inspects all name grammemes. Phrase-head
  selection is defective because it accepts the first noun homonym of the
  first token (`часовой`) instead of respecting adjective-plus-head structure.
- `abbreviation_context.py`: all surface forms of `вес` and `масса` were
  checked. Its noun-candidate scan is adequate for its narrow semantic test;
  no first-parse defect was reproduced there.
- `cardinals.py`: direct unit recovery is constrained by the unit lexicon,
  but the ordinary following-noun and adjective+noun branches use first
  parses. Numeric context must prefer a noun candidate, as shown by `1 пасть`.
- `_helpers.py`: generated cardinal tokens from 0 through 1000 plus scale
  boundaries were inventoried. Their first parse is compatible with numeral
  rendering; unit and free-text context calls are not uniformly safe.
- `fractions.py`: per-token first-parse inflection is not safe for compound
  numerators and must be replaced. `decimals.py` already delegates the
  numerator to `inflect_numeral_string()` and did not reproduce that defect.
- `ordinal_utils.py` and `ordinals.py`: noun scans inspect all noun candidates,
  but common gender, pluralia tantum, suffix evidence, and rare-case
  canonicalization are incomplete.
- `roman_numerals.py`: context nouns and person names already use constrained
  candidate sets; shared rare-case canonicalization is still required.
  Exact case-sensitive unit tokens made only of Roman letters must be
  protected before this stage.
- `years.py`: the final words generated by `num2words(..., to="ordinal")`
  were checked for 1 through 9999 and had an adjective/`Anum` first parse.
  Keep that invariant test. `years_context.py` is defective because semantic
  unit detection checks only `parsed[0].normal_form`.
- Shape analyzers and boundary values were exercised with empty strings,
  punctuation, digits, Roman and Latin text, unknown Cyrillic text,
  one- and multi-hyphen words, capitalization, and `е`/`ё`. They degrade to
  `NUMB`, `ROMN`, `LATN`, `PNCT`, or `UNKN` with `inflect() is None`; the
  existing fallback model is appropriate.
- The upstream 2.0.6 threading, inflection, numeral-agreement, tagset,
  result-wrapper, parsing, and analyzer suites were run against the installed
  dictionary: 555 passed, 23 upstream expected failures remained, and 4
  upstream non-strict expected failures passed. No base-contract failure was
  observed. Upstream still marks digit-plus-suffix parses such as `3-го`,
  `41-й`, and `8-му` as expected failures, confirming that the project's own
  ordinal token grammar cannot be replaced by pymorphy3's shape analyzers.
- Every unique unit lemma was checked at one/few/many and every lemma with
  `Sgtm`, `Pltm`, `GNdr`, `Fixd`, `Coun`, `Name`, `Surn`, `Geox`, or `ms-f`
  was inspected. This found the lira, shekel, gray, pascal/weber/sievert,
  tenge, won, farad, tesla, mole, byte-family, and exact-case symbol cases
  listed above; the remaining current unit lemmas produced their intended
  base form at one.

Public pymorphy3 functionality was also evaluated rather than omitted:

- use `TagClass.fix_rare_cases()`, `Parse.lexeme`, and ordinary parse/tag
  fields where they strengthen the shared policy;
- retain `make_agree_with_number()` only as a test oracle because it cannot
  honor the project's external case and byte-form conventions;
- do not switch runtime code to `normal_forms()` or `tag()` because current
  callers need tags plus normal forms and often inflection;
- do not use `word_is_known()` as a spell checker or parse selector (the
  upstream documentation explicitly warns against both assumptions);
- do not depend on `methods_stack`, private analyzer-unit classes,
  `result_type=None`, a disabled probability estimator, or a custom
  `MorphAnalyzer(units=...)`; those either expose private contracts or remove
  information required by the project.

## Implementation

### 0. Prove backend parity before changing the default

Add a deterministic parity harness under `scripts/` and focused tests under
`tests/` which can run in two clean environments:

- baseline: the locked `pymorphy3==2.0.6` with `DAWG2-Python` active and
  `pymorphy3.dawg.EXTENSION_AVAILABLE is False`;
- candidate: the same analyzer and dictionary versions with
  `pymorphy3[fast]` installed and
  `pymorphy3.dawg.EXTENSION_AVAILABLE is True`.

Run this gate before any parse-selection or normalization behavior changes,
so backend parity is not confused with the intentional fixes in later
sections. Emit stable UTF-8 JSON containing:

- exact public `normalize()` results for every complete input message
  collected by the test suite, including strict-xfail inputs;
- ordered public parse signatures for the bounded morphology corpus:
  surface word, `normal_form`, stringified tag, score, and `word`;
- `inflect()` results for every supported case/number/gender combination on
  unit lemmas, numeral words, ambiguous regression words, and generated
  ordinal final words;
- lexeme word/tag signatures where later domain-policy code relies on
  `Parse.lexeme`.

Build the corpus deterministically from test parameters, all `UNITS_DATA`
tokens and lemmas, generated cardinal/ordinal boundary values, rare-case
fixtures, unknown-word/shape fixtures, and `е`/`ё` plus case variants. Do not
serialize private `methods_stack`, analyzer units, DAWG internals, object
representations, or timing data. Compare the two JSON artifacts byte for byte
after stable sorting of the corpus; preserve parse and lexeme order inside
each entry because order is part of the behavior currently consumed by the
project.

The migration gate passes only with zero differences and with the complete
existing test suite producing the same pass/xfail/skip outcomes in both
environments. An XPASS, changed exception, changed fallback, missing compiled
backend, or packaging/install failure is a failed gate. Keep any diagnostic
artifact outside version control; commit only the harness, fixtures, and
documented command.

After the gate passes, modify `pyproject.toml` and refresh `uv.lock`:

- replace the base analyzer requirement with
  `pymorphy3[fast]>=2.0,<3`, making compiled DAWG the normal CPython backend;
- constrain the direct Russian dictionary dependency to `>=2.0,<3`;
- lock the resolved `DAWG2` package and retain the portable dependency pulled
  by pymorphy3; do not add a second project-specific runtime switch.

Verify fresh wheel and sdist installs on the project's supported CPython
3.10-3.13 range, at minimum on Windows and Linux CI. Confirm
`EXTENSION_AVAILABLE is True` in each candidate environment. If a supported
matrix cell cannot install a published wheel and would require an
unprovisioned compiler, treat that as a failed migration gate rather than
silently accepting a slower or untested backend.

### 1. Add a single morphology-policy boundary

Modify `src/ru_normalizr/_morph.py`:

- Extend `MorphParse` only with public attributes actually needed by the new
  policy (`score: float` and `lexeme` if the validated paradigm path uses
  them). Do not expose `methods_stack` or private analyzer classes, and do
  not use surface-global `is_known` as candidate evidence.
- Split `parse_word()` into a public normalizing wrapper and a private
  lowercase-keyed LRU cache. Preserve `е` versus `ё` and the current
  65,536-entry bound.
- Add `canonicalize_grammemes(grammemes: Iterable[str]) -> frozenset[str]`
  implemented through `get_morph().TagClass.fix_rare_cases()`.
- Add `canonicalize_case(case: str | None, default: str = "nomn") -> str`
  as the scalar wrapper used by renderers.
- Add a deterministic `select_parse(...) -> MorphParse | None` helper whose
  inputs can constrain POS, normal form, required/forbidden grammemes,
  preferred grammemes, gender, number, and case. Preserve upstream score
  order only as the final tie-breaker.
- Keep selection linear in the number of parses. Do not add a scan over the
  dictionary or disable the existing word cache.

Replace the private `SECONDARY_CASE_TO_PRIMARY` mapping in
`src/ru_normalizr/numerals/_num2words.py` with the shared helper. Update
`src/ru_normalizr/abbreviations.py`,
`src/ru_normalizr/ordinal_utils.py`,
`src/ru_normalizr/roman_numerals.py`, and
`src/ru_normalizr/numerals/ordinals.py` to use the same canonical case
function instead of local `loc2` expressions.

### 2. Make ordinal disambiguation honor explicit morphology

Modify `src/ru_normalizr/ordinal_utils.py`:

- Change `render_ordinal_from_noun_parse()` to accept optional explicit
  `case_hint`, `gender_hint`, `plural_hint`, and `inanimate_hint` keyword
  arguments. A supplied hint wins over a missing or ambiguous tag; a
  contradictory fully specified noun tag remains a validation/fallback case,
  not a silent override.
- Recognize `ms-f` as unresolved common gender rather than masculine. Require
  a suffix/context hint when available; retain masculine only as the final
  compatibility fallback when no evidence exists.
- In `render_ordinal()`, map inanimate plural accusative to nominative just as
  Russian adjective agreement requires. Keep animate plural accusative
  genitive-like.
- Route all noun cases through `canonicalize_case()`.

Modify `src/ru_normalizr/numerals/ordinals.py`:

- Preserve the case, gender, plurality, and animacy evidence already derived
  from the numeric suffix and nearby tokens.
- Pass the explicit suffix gender for common-gender nouns, so both
  `2-й коллега` and `2-я коллега` retain the intended agreement.
- For `Pltm`/`GNdr` nouns, choose the parse compatible with the explicit
  suffix and inanimacy rather than accepting the first equal-score or
  highest-score case.
- Keep the existing bounded four-token noun scan and morphology performance
  invariants.

Update Roman and heading call sites only to match the new signature. Do not
broaden the set of text recognized as a Roman-numeral context.

### 3. Select domain-correct unit parses

Introduce a typed unit descriptor in
`src/ru_normalizr/numerals/_constants.py` (a frozen dataclass or
`NamedTuple`; choose the style which causes the smallest safe migration) with
the existing lemma/gender/category/suffix fields plus optional morphology
metadata:

- expected normal form;
- expected animacy and whether accusative must use the inanimate form;
- explicit indeclinability when the surface form must never enter a foreign
  dictionary paradigm;
- preferred/forbidden grammemes;
- optional morphology seed for a productive paradigm which is absent from
  the packaged dictionary;
- as a last domain-data fallback, a validated six-case singular/plural
  paradigm for a whole lexeme when pymorphy3 has no usable productive parse.

Migrate `resolve_unit_info()` and direct `UNITS_DATA` consumers to the typed
descriptor without changing token-resolution precedence or mixed-case SI
rules.

Modify `src/ru_normalizr/numerals/_helpers.py::inflect_unit_lemma()`:

- Accept the unit descriptor, or at minimum the expected lemma, gender, and
  morphology metadata, instead of only a raw lemma.
- Select a noun parse matching the expected normal form, gender, and
  inanimate domain meaning before considering score. This resolves `лира`
  without a token-specific replacement.
- Avoid `Sgtm`, `Name`, `Surn`, and `Geox` parses when a productive
  domain-compatible parse exists. Allow `Fixd` when the unit is genuinely
  indeclinable (`евро`, `генри`, `песо`, `промилле`).
- Avoid `Coun` for byte-family units because the project explicitly requires
  ordinary plural forms. Encode that as unit-family morphology policy, not
  dependence on current parse order.
- When the packaged dictionary has no productive unit paradigm, parse the
  declared morphology seed and require the resulting candidate to match the
  expected lemma, gender, animacy, and requested form. If validation fails,
  use the descriptor's complete validated paradigm when present; otherwise
  log at `DEBUG` and return the established safe fallback. Do not fabricate a
  form by suffix concatenation at runtime.
- For an inanimate masculine unit whose only usable dictionary paradigm is
  animate (`паскаль`), normalize singular accusative to nominative before
  inflection. Do not blindly select the dictionary's inanimate `зивёрт`
  candidate, because it would change the supported spelling `зиверт`.
- Keep all `inflect()` calls behind `safe_inflect()` or an equivalent
  boundary. Never index an unvalidated candidate.

Provide validated morphology metadata for the currently confirmed gaps
(`лира`, `шекель`, `грей`, `тенге`, `вона`, `фарад` and its prefixes,
`тесла`, `моль`, `паскаль` and its prefixes, `вебер`, and `зиверт`) and audit
every existing unit lemma carrying `Sgtm`, `Pltm`, `GNdr`, `Fixd`, `Coun`,
`Name`, `Surn`, `Geox`, or `ms-f`. Metadata is domain-lexicon data, not a
regex replacement, and must cover a whole lexeme paradigm through the shared
mechanism.

Refactor `CASE_SENSITIVE_UNITS_DATA` and `resolve_unit_info()` at the same
time:

- enumerate exact standard forms wherever case distinguishes a value:
  milli/mega SI prefixes, `b`/`B` for bit/byte, and Cyrillic `Гр`/`гр`;
- add the missing domain descriptors needed by supported exact forms, such
  as milliwatt, megavolt, and megabit;
- keep case-insensitive lookup only for textual names and genuinely
  unambiguous aliases;
- add a shared `is_exact_unit_token()`/protection API used before Roman and
  Latin stages, so `MV` cannot be consumed as a Roman numeral;
- table-test every exact token beside its nearest case variant. Do not
  generate aliases by indiscriminate `.lower()` or `.upper()`.
- Preserve both the exact cleaned token and the original dotted token during
  lookup. Dotted-only aliases must resolve, while sentence-terminal dot
  preservation continues to use the existing boundary helpers.
- Encode `Pltm` unit agreement for `сутки`: one uses `одни сутки`, two uses
  the collective numeral plus genitive plural `двое суток`, and five uses
  `пять суток`. Keep this descriptor-driven for future plural-only units.

### 4. Tighten context parse selection without suppressing unknown words

Review every remaining direct `first_parse_required()` and `parsed[0]` use in:

- `src/ru_normalizr/abbreviations.py`
- `src/ru_normalizr/abbreviation_context.py`
- `src/ru_normalizr/ordinal_utils.py`
- `src/ru_normalizr/roman_numerals.py`
- `src/ru_normalizr/years.py`
- `src/ru_normalizr/years_context.py`
- `src/ru_normalizr/numerals/cardinals.py`
- `src/ru_normalizr/numerals/decimals.py`
- `src/ru_normalizr/numerals/fractions.py`
- `src/ru_normalizr/numerals/ordinals.py`
- `src/ru_normalizr/numerals/_helpers.py`

For each call, do one of the following and leave a short code comment where
the choice is non-obvious:

- use `select_parse()` with facts already known by the caller;
- keep first-parse behavior when the generated token is unambiguous and add a
  focused invariant test;
- inspect all candidates when the decision is semantic (`NOUN`, `ADJF`,
  person name, unit, or case);
- use `score` only as a final confidence/tie-break signal, not a hard global
  filter; keep `is_known` out of per-candidate selection.

Do not globally reject predicted parses: unknown Russian words and names are
valid TTS input. Treat `LATN`, `NUMB`, `ROMN`, `PNCT`, and `UNKN` as barriers
where a caller is specifically scanning for Russian syntactic context.

Apply the concrete outcomes of the completed review:

- In `abbreviations.py`, parse the bounded phrase as adjective/participle
  modifiers followed by the rightmost compatible noun head. Do not accept a
  noun homonym for a token when an adjective parse is compatible with a
  later noun (`часовой стрелки`). Keep the existing three-word bound.
- In `cardinals.py`, when a numeric token is followed by a Russian word,
  select a noun candidate before giving up on gender/animacy. For the
  adjective+noun branch, constrain each token by its syntactic role instead
  of checking only its first parse. Preserve all current unit-resolution
  precedence.
- In `_helpers.py::get_numeral_case()`, inspect compatible verb/infinitive
  candidates when matching `VERB_CASE`; do not let a top `ADJS` homonym hide
  `достигаем`. Keep participles as attributive barriers and preserve the
  bounded left scan.
- In `years_context.py`, accept a following token as a known unit only when
  an exact unit token or a semantically compatible noun normal form matches
  the lexicon. Inspect all noun candidates, but do not let an arbitrary
  low-score homonym suppress a genuine year; require expected unit
  lemma/descriptor compatibility.
- Keep first-parse behavior for the last word emitted by
  `num2words(..., to="ordinal")`, but add the bounded generated-output
  invariant which justified that choice.
- Leave `abbreviation_context.py` person/name scans and Roman name selection
  on their existing all-candidate logic, changing only their shared
  canonical-case calls.

### 5. Render fractions through the complete numeral path

Modify `src/ru_normalizr/numerals/fractions.py`:

- replace per-token `first_parse_required(part).inflect({case})` with
  `inflect_numeral_string()` so hundreds and magnitude groups retain their
  internal agreement in every case;
- keep the final feminine adjustment for numerators ending in one/two, but
  perform it on a semantically selected `NUMR`/`Anum` parse;
- reuse the shared case canonicalizer and safe inflection boundary;
- ensure the ordinal/year stages do not match a number immediately followed
  by `/` when that slash begins `FRACTION_PATTERN`, including numerators of
  four or more digits;
- add stage-level tests as well as public `normalize()` tests so ownership of
  `1000/100` cannot regress.

### 6. Document the default compiled backend

Update the Russian installation/development documentation in `README.md`:

- explain that supported CPython installations use the compiled backend by
  default after the parity gate;
- state the supported interpreter/platform wheel matrix and that callers can
  verify the active backend through
  `pymorphy3.dawg.EXTENSION_AVAILABLE`;
- document that a false flag on a supported CPython installation is an
  installation/configuration problem, not a silently supported production
  mode;
- report benchmark methodology, not a universal performance promise.

Do not rely on the fast backend for correctness and do not create separate
code paths based on its availability.

### 7. Record the durable integration constraints

Create `docs/agents/pymorphy3-integration.md` in English and list it in
`docs/agents/README.md` with a two-sentence Russian description. Document:

- non-contextual parse ordering;
- typed grammeme comparison and cache canonicalization;
- authoritative rare-case conversion;
- domain parse selection rules;
- dictionary age and semantic homonym limitations;
- unit morphology seed validation;
- the parity gate and default compiled versus portable fallback DAWG
  backends;
- the reason `make_agree_with_number()` is not used globally.

Update `CHANGELOG.md` under `## Unreleased` in Russian for all user-visible
normalization corrections and the default compiled backend migration. Do not
bump the package version.

Do not add an `AGENTS.md` gotcha unless implementation reveals a new critical
fact which meets the repository's stated criteria; propose its exact wording
to the user first if that happens.

## Testing & verification

Start each bug fix with a failing regression test. User-facing regressions
must use natural complete messages through public `normalize()`, not isolated
two-word fragments. Use additional table-driven helper/stage tests for
grammeme families and unit paradigms.

Add or update tests covering:

- move each fixed full-message regression from `tests/test_known_gaps.py`
  into the closest regular test module; remove `xfail` only in the same
  commit which makes that exact assertion pass;
- common gender with explicit masculine and feminine suffixes:
  `2-й коллега`, `2-я коллега`, `2-й сирота`, `2-я сирота`;
- `Pltm`/`GNdr` nominative and accusative ambiguity:
  `2-е сутки`, `2-е ножницы`, and `2-е дрова`;
- inanimate versus animate plural accusative ordinal rendering;
- every rare-case mapping from upstream `TagClass.RARE_CASES`, including
  `gen1`, `gen2`, `acc1` when recognized by the tag class, `acc2`, `loc1`,
  `loc2`, and `voct`;
- domain homonyms and missing paradigms across one/few/many and all six
  primary cases: Turkish lira, shekel, gray, pascal, weber, sievert, newton,
  henry, tenge, Korean won, farad and prefixed farads, tesla, and mole;
- inanimate singular accusative for pascal/weber/sievert and a control
  animate lexeme (`человек`);
- ordinary byte-family forms for byte, kilobyte, megabyte, gigabyte, and
  terabyte, including 1, 2, 5, 11, 21, 22, and 25;
- indeclinable units (`евро`, `тенге`, `песо`, `генри`, `промилле`);
- plural-only unit agreement for `1/2/5 сут.` and controls for ordinary
  plural nouns;
- every dotted-only alias (`п.п.`, `б.п.`, `в.`, `л.с.`, `л. с.`, and
  `рад.`) in sentence-medial and sentence-final positions, including
  preservation of the actual sentence boundary;
- exact-case tables for `mW`/`MW`, `мВт`/`МВт`, `mV`/`MV`, `mA`/`MA`,
  `b`/`B` data-unit families and rates, and `Гр`/`гр`; assert both the
  expanded value and that Roman normalization never sees protected units;
- abbreviation agreement with an adjective/noun homonym followed by the
  actual head (`гос. часовой стрелки`) and ordinary control phrases;
- following-noun selection where the top parse is a verb/infinitive but a
  noun parse is licensed by the number (`1 пасть`);
- verb-governed case where an `ADJS` homonym ranks above the actual verb
  (`достигаем 5 целей`) plus participle controls;
- implicit-year exclusion for inflected unit forms in the year range
  (`дозу в 2020 зивертов`) plus genuine-year controls;
- fractions with numerators 100, 101, 2000, and a magnitude boundary in all
  supported prepositional cases, including `1000/100` after `к` and `о`;
- a morphology-seed validation failure returning the documented fallback and
  emitting a `DEBUG` diagnostic without crashing;
- parse selection for unknown Cyrillic words, shape tokens, and ambiguous
  known words;
- cache determinism with typed grammemes and the new selector;
- one concurrent parse/normalize stress test using the shared analyzer;
- exact baseline-versus-candidate parity under pure-Python and compiled DAWG
  backends, including the public normalization corpus, ordered public parse
  signatures, inflection/lexeme signatures, exceptions, and pytest outcome
  counts;
- fresh-install checks which assert the compiled backend is active for every
  supported CPython/platform matrix cell included in CI.

Add a bounded inventory test over all `UNITS_DATA` descriptors which asserts:

- the lemma has a selectable noun parse or validated morphology seed;
- expected gender/animacy policy is satisfiable;
- requested one/few/many forms do not silently return a semantically
  forbidden `Name`/`Surn`/`Geox`/`Sgtm` parse;
- byte-family units never select a `Coun` result.

Run before the implementation commit:

```text
uv run ruff check .
uv run pyright
uv run pytest
```

Also run a short benchmark with 10,000 distinct known words under both
backends after correctness parity passes. Record the command,
interpreter, backend flag, and result in
`docs/agents/pymorphy3-integration.md`; performance variance is not a test
failure unless a changed selector violates an existing linearity assertion.

Verify end-to-end through the public `normalize()` API, not only helper
functions. Build both sdist and wheel after dependency metadata changes and
inspect their metadata to confirm the default requirement includes
`pymorphy3[fast]>=2.0,<3` and a clean supported CPython installation resolves
and activates `DAWG2`.

## Out of scope

- Replacing `pymorphy3` with Natasha, spaCy, an LLM, or another analyzer.
- Training a contextual POS tagger or performing full syntactic parsing.
- Forking or modifying `pymorphy3` or the packaged OpenCorpora dictionary.
- Building and distributing a custom compiled morphology dictionary.
- Changing documented reference, range, byte-unit, or letter-name
  conventions.
- Supporting a default compiled-backend migration on interpreter/platform
  combinations outside the project's declared and verified wheel matrix.
- Adding stress placement or pronunciation dictionaries unrelated to parse
  selection and inflection.
- Bumping the `ru-normalizr` version or performing a release.

---
**Maintenance note (for the implementing agent):** when this plan is implemented, update the `Status:` line above, e.g. `Status: implemented YYYY-MM-DD in branch `feat/<name>``. If the plan changes during implementation, update the affected sections too — the plan must not lie about what was built.
