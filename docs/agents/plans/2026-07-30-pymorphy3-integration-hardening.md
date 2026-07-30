# Plan: Harden the pymorphy3 integration

Status: plan, 2026-07-30.

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
- Rare-case normalization is duplicated and incomplete outside cardinal
  rendering. For example, `noun_parse_case()` maps only `loc2`, and a `gen2`
  noun parse makes `render_ordinal_from_noun_parse(2, parse)` render
  nominative `второй` instead of genitive `второго`.

There is also an optional performance opportunity. The current environment
uses pure-Python `DAWG2-Python` (`pymorphy3.dawg.EXTENSION_AVAILABLE` is
false). On this Windows/Python 3.11 environment, an isolated
`pymorphy3[fast]==2.0.6` run installed a wheel successfully and parsed the
same 10,000 distinct known words at approximately 146k words/s versus 21.5k
words/s for the pure-Python backend. This is not a correctness requirement,
and the compiled backend must remain optional.

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
   correctly through typed unit-lexicon morphology metadata. Do not add
   one-off regex substitutions for `лира`, `шекель`, `грей`, or any complete
   phrase.
7. Offer the compiled DAWG backend as an optional package extra and document
   the trade-off. Keep the portable pure-Python backend as the default.
8. Add a `<3` compatibility ceiling for both direct pymorphy packages while
   retaining the lockfile's exact resolved versions. Do not bump the project
   version as part of this work.

## Key codebase facts

- `src/ru_normalizr/_morph.py` owns the single cached `MorphAnalyzer`,
  the 65,536-entry `parse_word()` cache, and the local `MorphParse`
  protocol. All project morphology calls route through this module.
- `pymorphy3` 2.0.6 documents that `parse()` always returns at least an
  `UNKN` parse. The existing `first_parse()` guard is still useful as a
  compatibility boundary and should remain.
- `src/ru_normalizr/numerals/_helpers.py` already has
  `SECONDARY_CASE_TO_PRIMARY`, `safe_inflect()`,
  `inflect_unit_lemma()`, `is_case_reliable_noun()`, and
  `get_target_tags_for_number()`. `safe_inflect()` is the established
  failure boundary and logs broad fallbacks at `DEBUG`.
- `SECONDARY_CASE_TO_PRIMARY` duplicates upstream
  `MorphAnalyzer.TagClass.fix_rare_cases()`. Several other files separately
  special-case only `loc2`.
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
- The working tree had pre-existing user changes in
  `src/ru_normalizr/dictionary.py` and `tests/test_dictionary_rules.py` when
  this plan was created. An implementing agent must preserve them unless
  they have since been committed or removed by the user.

## Implementation

### 0. Add a single morphology-policy boundary

Modify `src/ru_normalizr/_morph.py`:

- Extend `MorphParse` only with public attributes actually needed by the new
  policy (`score: float` and `is_known: bool` if used). Do not expose
  `methods_stack` or private analyzer classes.
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
`src/ru_normalizr/numerals/_helpers.py` with the shared helper. Update
`src/ru_normalizr/abbreviations.py`,
`src/ru_normalizr/ordinal_utils.py`,
`src/ru_normalizr/roman_numerals.py`, and
`src/ru_normalizr/numerals/ordinals.py` to use the same canonical case
function instead of local `loc2` expressions.

### 1. Make ordinal disambiguation honor explicit morphology

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

### 2. Select domain-correct unit parses

Introduce a typed unit descriptor in
`src/ru_normalizr/numerals/_constants.py` (a frozen dataclass or
`NamedTuple`; choose the style which causes the smallest safe migration) with
the existing lemma/gender/category/suffix fields plus optional morphology
metadata:

- expected normal form;
- preferred/forbidden grammemes;
- optional morphology seed for a productive paradigm which is absent from
  the packaged dictionary.

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
  log at `DEBUG` and return the established safe fallback.
- Keep all `inflect()` calls behind `safe_inflect()` or an equivalent
  boundary. Never index an unvalidated candidate.

Provide validated morphology metadata for the currently confirmed gaps
(`шекель` and `грей`) and audit every existing unit lemma carrying `Sgtm`,
`Pltm`, `GNdr`, `Fixd`, `Coun`, `Name`, `Surn`, `Geox`, or `ms-f`.
Metadata is domain-lexicon data, not a regex replacement, and must cover a
whole lexeme paradigm through the shared mechanism.

### 3. Tighten context parse selection without suppressing unknown words

Review every remaining direct `first_parse_required()` and `parsed[0]` use in:

- `src/ru_normalizr/abbreviations.py`
- `src/ru_normalizr/abbreviation_context.py`
- `src/ru_normalizr/caps.py`
- `src/ru_normalizr/normalizer.py`
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
- use `is_known`/`score` only as confidence signals, not hard global filters.

Do not globally reject predicted parses: unknown Russian words and names are
valid TTS input. Treat `LATN`, `NUMB`, `ROMN`, `PNCT`, and `UNKN` as barriers
where a caller is specifically scanning for Russian syntactic context.

### 4. Package compatibility and optional fast backend

Modify `pyproject.toml` and refresh `uv.lock`:

- constrain `pymorphy3` to `>=2.0,<3`;
- constrain the direct Russian dictionary dependency to `>=2.0,<3`;
- add a `fast` optional dependency which installs a compatible
  `pymorphy3[fast]` backend without making compiled DAWG mandatory.

Update the Russian installation/development documentation in `README.md`:

- explain that the default remains portable pure Python;
- show how to install the project with the fast extra;
- state that wheel availability depends on interpreter/platform and that
  callers can verify the active backend through
  `pymorphy3.dawg.EXTENSION_AVAILABLE`;
- report benchmark methodology, not a universal performance promise.

Do not rely on the fast backend for correctness and do not create separate
code paths based on its availability.

### 5. Record the durable integration constraints

Create `docs/agents/pymorphy3-integration.md` in English and list it in
`docs/agents/README.md` with a two-sentence Russian description. Document:

- non-contextual parse ordering;
- typed grammeme comparison and cache canonicalization;
- authoritative rare-case conversion;
- domain parse selection rules;
- dictionary age and semantic homonym limitations;
- unit morphology seed validation;
- default versus optional DAWG backend;
- the reason `make_agree_with_number()` is not used globally.

Update `CHANGELOG.md` under `## Unreleased` in Russian for all user-visible
normalization corrections and the optional installation extra. Do not bump
the package version.

Do not add an `AGENTS.md` gotcha unless implementation reveals a new critical
fact which meets the repository's stated criteria; propose its exact wording
to the user first if that happens.

## Testing & verification

Start each bug fix with a failing regression test. Use table-driven tests for
grammeme families and unit paradigms.

Add or update tests covering:

- common gender with explicit masculine and feminine suffixes:
  `2-й коллега`, `2-я коллега`, `2-й сирота`, `2-я сирота`;
- `Pltm`/`GNdr` nominative and accusative ambiguity:
  `2-е сутки`, `2-е ножницы`, and `2-е дрова`;
- inanimate versus animate plural accusative ordinal rendering;
- every rare-case mapping from upstream `TagClass.RARE_CASES`, including
  `gen1`, `gen2`, `acc1` when recognized by the tag class, `acc2`, `loc1`,
  `loc2`, and `voct`;
- domain homonyms and missing paradigms across one/few/many and all six
  primary cases: Turkish lira, shekel, gray, pascal, newton, and henry;
- ordinary byte-family forms for byte, kilobyte, megabyte, gigabyte, and
  terabyte, including 1, 2, 5, 11, 21, 22, and 25;
- indeclinable units (`евро`, `тенге`, `песо`, `генри`, `промилле`);
- a morphology-seed validation failure returning the documented fallback and
  emitting a `DEBUG` diagnostic without crashing;
- parse selection for unknown Cyrillic words, shape tokens, and ambiguous
  known words;
- cache determinism with typed grammemes and the new selector;
- one concurrent parse/normalize stress test using the shared analyzer;
- parity of output under pure-Python and compiled DAWG backends when the fast
  backend is available.

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
backends when the compiled wheel is available. Record the command,
interpreter, backend flag, and result in
`docs/agents/pymorphy3-integration.md`; performance variance is not a test
failure unless a changed selector violates an existing linearity assertion.

Verify end-to-end through the public `normalize()` API, not only helper
functions. Build both sdist and wheel after dependency metadata changes and
inspect their metadata to confirm the default installation remains portable
and the `fast` extra is advertised.

## Out of scope

- Replacing `pymorphy3` with Natasha, spaCy, an LLM, or another analyzer.
- Training a contextual POS tagger or performing full syntactic parsing.
- Forking or modifying `pymorphy3` or the packaged OpenCorpora dictionary.
- Building and distributing a custom compiled morphology dictionary.
- Changing documented reference, range, byte-unit, or letter-name
  conventions.
- Making a compiler toolchain or native DAWG extension mandatory.
- Adding stress placement or pronunciation dictionaries unrelated to parse
  selection and inflection.
- Bumping the `ru-normalizr` version or performing a release.

---
**Maintenance note (for the implementing agent):** when this plan is implemented, update the `Status:` line above, e.g. `Status: implemented YYYY-MM-DD in branch `feat/<name>``. If the plan changes during implementation, update the affected sections too — the plan must not lie about what was built.
