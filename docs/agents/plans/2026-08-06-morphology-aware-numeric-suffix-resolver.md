# Plan: Morphology-aware numeric suffix resolver

Status: plan, 2026-08-06.

> Note for agents: this plan is a point-in-time snapshot — its "codebase facts" describe the code as of the date above and may be outdated. Do NOT treat it as current architecture docs; verify every fact against the actual code before relying on it.

## Context

The numeral pipeline currently interprets Cyrillic text after a digit and a hyphen through two overlapping paths. `normalize_hyphenated_words` treats selected cardinal-looking suffixes as direct case instructions, while `normalize_ordinals` independently resolves ordinal and a smaller set of cardinal suffixes. This makes the suffix itself weaker than an implementation table: `7-ми` is forced to instrumental and becomes `семью`, even though `семью` does not end in `-ми`; the realistic sentence `В 7-ми классах ввели новую программу.` therefore produces `В семью классах...` instead of `В семи классах...`.

The required contract is morphology-aware but deterministic. A recognized suffix first constrains the output to real cardinal or ordinal readings whose final spoken word literally ends in that suffix. Local syntax then selects among compatible readings. When syntax cannot distinguish a compatible cardinal and ordinal reading, the cardinal reading wins. If no real reading has the written ending, the suffix is treated as malformed and the ordinary numeral context resolver chooses a cardinal form; without useful context it falls back to cardinal nominative. Recognized constructions must normalize rather than retain digits.

No external service, endpoint, paid API, new public option, or version bump is involved.

## Approved decisions

1. Use a closed registry of recognized Cyrillic numeric suffixes. Do not treat arbitrary letters after a numeric hyphen as a grammatical suffix.
2. For a recognized suffix, generate real cardinal and ordinal readings and keep exact candidates only when the last spoken word case-insensitively ends with the written suffix.
3. Use bounded local morphology and syntax to choose among exact candidates. The suffix is a hard compatibility constraint while at least one exact candidate exists.
4. If context still leaves compatible cardinal and ordinal candidates, choose the cardinal reading deterministically; do not preserve the digit token and do not guess by number magnitude.
5. If no exact candidate exists, do not maintain a special replacement table for malformed endings. Ignore the malformed ending semantically, resolve the ordinary cardinal case from context, and use cardinal nominative when context supplies no case.
6. Protect identifiers structurally: embedded alphanumeric forms such as `X7-ми`, `X7ми`, and `A320-й` must not be normalized as numeric suffix constructions. Standalone numeric constructions remain eligible regardless of whether the value is above 100.
7. Keep year/decade parsing, numeric ranges, decimal notation, versions, unit links, and numeric compound words in their specialized stages. The suffix resolver must neither preempt them nor partially consume their tokens.
8. Preserve existing public entry points while centralizing the decision logic so direct stage calls and the full `normalize` pipeline cannot disagree.
9. Add a broad table-driven regression and corner-case matrix, including ambiguity, malformed endings, codes, signs, values above 100, years, ranges, decimals, capitalization, punctuation, and backend failure behavior. Retain no fixed known gap merely by weakening its expected result.

## Key codebase facts

- `src/ru_normalizr/normalizer.py::PipelineNormalizer.run_numerals` currently runs numeric-unit hyphen repair, numeric compounds, versions, decimals, fractions, `normalize_hyphenated_words`, `normalize_ordinals`, and then general numeral normalization in that order. Years and dates run before the numerals stage.
- `src/ru_normalizr/normalizer.py::GLUED_NUMERIC_SUFFIXES` duplicates suffix knowledge from `ORDINAL_SUFFIXES` and a separate literal set. `_fix_glued_numbers` only recognizes an embedded alphanumeric code when the right-hand text has length one, so multi-letter suffix-looking tails such as `X7ми` are currently exposed to later normalization.
- `src/ru_normalizr/numerals/_hyphen.py` defines `ORDINAL_SUFFIXES`, `CARDINAL_CASE_SUFFIXES`, unit-vs-suffix classification, and structural handling for numeric-unit hyphens. `classify_numeric_hyphen_rhs` checks ordinal suffixes before cardinal ones and has no shared candidate model.
- `src/ru_normalizr/numerals/_constants.py` defines `HYPHENATED_WORD_PATTERN` as any integer followed by one or more Cyrillic letters and `ORDINAL_PATTERN` as an integer followed by one to four Cyrillic letters. Neither pattern captures the negative-number placeholder, decimal boundaries, or a complete alphanumeric-code boundary contract.
- `src/ru_normalizr/numerals/ordinals.py::normalize_hyphenated_words` currently accepts arbitrary Cyrillic right-hand text, maps `ти/и` directly to genitive and `ми/мя` directly to instrumental, and returns a cardinal for every member of `CARDINAL_CASE_SUFFIXES`. It intentionally skips some suffixes above 100, but the subsequent ordinal pass can still claim them in the public pipeline.
- `src/ru_normalizr/numerals/ordinals.py::normalize_ordinals` separately recognizes `ти`, `ми`, and `у` as cardinal suffixes, otherwise uses `resolve_ordinal_suffix_case`, noun agreement, and ordinal defaults. It already supports text-start capitalization through `capitalize_text_start`.
- `src/ru_normalizr/numerals/_helpers.py::inflect_numeral_string` renders cached cardinal readings after canonicalizing pymorphy grammemes. `get_numeral_case` is the existing bounded context resolver and must remain the source of fallback cardinal case rather than introducing a second preposition table.
- `src/ru_normalizr/ordinal_utils.py::render_ordinal` and `render_ordinal_from_noun_parse` provide ordinal generation and noun agreement. `resolve_ordinal_suffix_case`, `resolve_ordinal_plural`, and `normalize_ordinal_suffix_defaults` currently encode suffix decisions that the shared resolver will replace or narrow.
- `src/ru_normalizr/years.py` owns year and decade suffixes before the numeral stage. Its `YEAR_SUFFIX_TO_CASE`, `infer_suffix_case`, plausible-year guards, and decade rounding must remain specialized; representative forms include `1990-е`, `1990-х`, `90-ми годами`, and `2000-ми годами`.
- `docs/agents/performance-invariants.md` requires numeral context to be built once per tokenized document or scanned only through a bounded local window, and morphology caches to remain bounded. Candidate generation must therefore be constant-bounded per matched token and cached with a finite `maxsize`.
- `docs/agents/negative-numbers.md` requires `protect_negative_numbers` to be the only general unary-minus classifier. New suffix matching must consume `NEGATIVE_NUMBER_PLACEHOLDER` for signed inputs and must not reinterpret a bare code hyphen as minus.
- `tests/test_known_gaps.py::test_mi_suffix_agrees_with_the_preposition_case` is the strict realistic regression to graduate. Existing focused suffix coverage is primarily in `tests/test_ordinal_stage.py`; public-pipeline morphology coverage is in `tests/test_reported_regressions.py`, `tests/test_api.py`, and `tests/test_context_parse_selection.py`.

## Implementation

### 0. Lock the behavioral matrix before refactoring

- Add a focused table-driven test module such as `tests/test_numeric_suffixes.py` covering direct resolver behavior and full-sentence public-pipeline behavior.
- Record the approved selection order explicitly in tests: exact suffix compatibility, contextual selection, cardinal tie-break, then context-only cardinal fallback when there are zero exact candidates.
- Include at least these primary contracts:
  - `7-ми` → `семи`;
  - `В 7-ми классах...` → `В семи классах...`;
  - `7-ую книгу` → `седьмую книгу`;
  - a contextually unresolved `101-го участника` → `сто одного участника` under the cardinal tie-break;
  - `90-ми годами` remains ordinal because no compatible cardinal reading ends in `-ми`;
  - `с 7-мя учениками` → `с семью учениками` through context-only fallback because no exact `-мя` reading exists for seven;
  - bare malformed-but-recognized `7-мя` → nominative cardinal `семь` when no context is available.
- Audit and freeze every currently intended accepted suffix spelling. The closed registry must include the current normative ordinal inventory and explicitly approved/common cardinal spellings rather than inheriting arbitrary matches from `HYPHENATED_WORD_PATTERN`; cover at least `ти`, `и`, `ми`, `х`, `мя`, `тью`, `ух`, `ех`, `ёх`, `ум`, `ём`, and `у` where the existing pipeline accepts them.
- Add strict realistic `xfail` baselines in `tests/test_known_gaps.py` for any newly confirmed public-pipeline defect that cannot be fixed in the same implementation commit, following the repository rule. Do not add stage-only or fragmentary known-gap cases.

### 1. Introduce one closed suffix registry and candidate model

- Add `src/ru_normalizr/numerals/numeric_suffixes.py` (or an equivalently focused module) and move the authoritative recognized-suffix registry there.
- Define an immutable candidate record containing at least the rendered reading, `cardinal`/`ordinal` kind, case, gender where applicable, plurality, and whether it exactly matches the written suffix.
- Provide a bounded cached generator such as `generate_numeric_suffix_candidates(number: int, suffix: str) -> tuple[NumericSuffixCandidate, ...]`.
- Generate cardinal candidates through `inflect_numeral_string` for the supported primary cases and required gender/animacy variants, and ordinal candidates through `render_ordinal` for singular genders and plural forms. Deduplicate identical readings while retaining all compatible grammatical analyses.
- Compare the casefolded suffix only against the final lexical word of a multiword reading. Do not let a coincidental ending elsewhere in `двадцать один` qualify a candidate.
- Keep the cache finite and add tests proving candidate generation is reused without making output depend on cache state.

### 2. Resolve candidates through existing bounded context

- Add a resolver such as `resolve_numeric_suffix(number_text: str, suffix: str, *, tokens_left: list[str], tokens_right: list[str]) -> str | None`.
- First retain exact-ending candidates. Score them against `get_numeral_case`, the nearest compatible noun parse, ordinal gender/number agreement, animacy where observable, and existing bounded barriers. Do not scan the remaining document or add an unbounded regex callback slice.
- When exactly one rendered reading remains, return it. When multiple readings remain but all render identically, return the shared reading.
- When context cannot distinguish different exact cardinal and ordinal readings, return the cardinal reading as the approved deterministic tie-break. Keep this tie-break explicit and unit-tested rather than relying on pymorphy or set iteration order.
- If there are zero exact-ending candidates, discard suffix semantics and render an ordinary cardinal using `get_numeral_case`; use nominative only when the resolver finds no governing context. Do not add per-suffix malformed-ending replacements.
- On morphology or `num2words` failure, handle the failure at the resolver boundary, log a safe `DEBUG` diagnostic without source secrets, and use the established cardinal fallback where possible. Never crash normalization for arbitrary input.

### 3. Give the shared resolver one pipeline owner

- Replace the overlapping suffix branches in `src/ru_normalizr/numerals/ordinals.py` with a single normalization pass, e.g. `normalize_numeric_suffixes(text: str, *, capitalize_text_start: bool = False) -> str`.
- Narrow `normalize_hyphenated_words` to non-suffix numeric compounds and genuine right-hand words. A recognized suffix must be delegated to the shared resolver; an unknown short Cyrillic tail must not be silently discarded as if it were a grammatical ending.
- Keep `normalize_ordinals` and `normalize_hyphenated_words` as compatibility entry points for existing imports, but route their suffix behavior through the same resolver. Ensure `PipelineNormalizer.run_numerals` invokes the shared suffix pass only once and still preserves text-start capitalization.
- Remove or reduce `resolve_ordinal_suffix_case`, `resolve_ordinal_plural`, `normalize_ordinal_suffix_defaults`, and `_render_cardinal_suffix_number` only after a repository-wide caller search proves the shared resolver owns their former suffix responsibilities. Retain unrelated ordinal noun-agreement helpers.
- Update `src/ru_normalizr/numerals/__init__.py` exports only as needed; do not introduce a new promised public API unless an existing export requires compatibility.

### 4. Harden token ownership and code boundaries

- Replace `HYPHENATED_WORD_PATTERN`/`ORDINAL_PATTERN` suffix ownership with a boundary-aware matcher that accepts registered suffixes longest-first, supports the protected negative placeholder, rejects decimal/version fragments, and cannot start inside an alphanumeric identifier.
- Update `src/ru_normalizr/normalizer.py::GLUED_NUMERIC_SUFFIXES` and `_fix_glued_numbers` to consume the shared registry. Protect `X7ми` and `X7-ми` structurally regardless of suffix length; do not add brand/model keyword lists.
- Keep `normalize_numeric_unit_hyphen_links` authoritative for registered units and preserve ambiguous single-letter-unit safeguards in `_hyphen.py`.
- Verify unknown suffix-like tails, ordinary numeric compounds (`10-кратный`, `5-дневный`), full-word quantities (`5-метров`), and identifiers take separate explicit paths.
- Preserve the unary-minus invariant: a full-pipeline signed suffix construction may use only `NEGATIVE_NUMBER_PLACEHOLDER`; direct-stage support for bare minus must use the guarded boundary documented in `docs/agents/negative-numbers.md`.

### 5. Preserve specialized stages and graduate the known gap

- Keep `src/ru_normalizr/years.py` as the owner of years, decades, and their ranges. Do not replace `YEAR_SUFFIX_TO_CASE` with the general resolver in this change; add differential tests showing the earlier year stage consumes its valid forms before general suffix handling.
- Preserve version, decimal, fraction, numeric-range, heading-range, and unit behavior. If a specialized parser does not support a suffix-bearing decimal or range, preserve the entire structured token for that parser/known-gap policy rather than partially normalizing only one side.
- Move `test_mi_suffix_agrees_with_the_preposition_case` from `tests/test_known_gaps.py` to the closest regular suffix/E2E suite only when its complete realistic sentence passes.
- Remove the corresponding `docs/issues.md` entry and add a Russian `CHANGELOG.md` entry under `Unreleased`. Do not change package versions.

### 6. Document the maintained policy

- Add `docs/agents/numeric-suffix-resolution.md` in Russian describing the closed registry, exact-ending constraint, context scoring, cardinal tie-break, zero-candidate cardinal fallback, code boundaries, and specialized-stage ownership.
- Add the new note to `docs/agents/README.md` with a two-sentence description.
- Do not add an `AGENTS.md` gotcha without separate explicit user approval. If implementation reveals a critical non-obvious invariant, propose exact wording to the user instead.

## Testing & verification

- Add table-driven candidate tests across representative number families: `1`, `2`, `3`, `4`, `5`, `7`, `8`, `11`, `20`, `21`, `90`, `100`, `101`, and a multiword value above 1000. Cover every registered suffix and both matching and zero-candidate paths.
- Cover cardinal/ordinal collisions explicitly: `7-ми` (`семи`/`седьмыми`), `3-х` (`трёх`/`третьих`), `7-ю` (`семью`/`седьмую`), `7-м` (dative/instrumental/locative ordinal variants), and `101-го` (`сто одного`/`сто первого`). Assert context-selected and context-unresolved outcomes separately.
- Cover grammatical context: prepositions, a following noun with an unambiguous case, noun gender/number, animate accusative, a left name anchor, sentence start, quoted text, punctuation, conjunctions, and bounded context barriers.
- Cover malformed recognized endings without special mappings: `с 7-мя учениками`, `около 7-мя человек`, and bare `7-мя`; verify context-only cardinal fallback and nominative default.
- Cover currently accepted nonstandard spellings such as `из 2-ух`, `из 3-ех`, `из 4-ёх`, `с 5-тью`, `к 2-ум`, and `к 3-ём`, preventing accidental loss when the open-ended regex is replaced by the closed registry.
- Cover structural exclusions and stage ownership: `X7ми`, `X7-ми`, `A320-й`, negative numbers, `1,5-й`, `2.1-я`, numeric units, `10-кратный`, `5-метров`, `1990-е`, `1990-х`, `90-ми годами`, `2000-ми годами`, heading ranges, `с 1-го по 3-й`, and shared-suffix lists. No test may bless partial token corruption or a leaked private placeholder.
- Add backend-failure tests proving normalization does not crash and does not silently switch cardinal/ordinal meaning because one candidate renderer failed.
- Add a differential corpus of existing ordinal, year, unit, range, version, compound-adjective, and reported-regression cases. Review every changed output; accept only changes listed in the approved contract.
- Extend `tests/test_e2e_benchmark.py` with a suffix-dense text and a code-dense adversarial text. Verify runtime remains linear in input length, local context scans stay bounded, and candidate-cache growth is bounded independently of document size.
- During implementation, run focused suffix/ordinal/year tests after each integration step. Before every commit run `uv run ruff check .`, `uv run pyright`, and the relevant pytest scope; before completion run the full `uv run pytest` suite and the benchmark gate.

## Out of scope

- Do not add a user-facing strictness mode or configuration flag for suffix preference.
- Do not normalize arbitrary unknown Cyrillic tails as suffixes or introduce fuzzy/edit-distance matching.
- Do not add brand, model, ГОСТ, ТУ, or document-type keyword dictionaries for identifier protection.
- Do not rewrite year/decade morphology into the general resolver; only preserve and test its stage boundary.
- Do not redesign numeric ranges, decimal ordinals, versions, or compound numeric adjectives beyond preventing the new resolver from partially consuming them. Any independent semantic defect remains a separate task and, if confirmed during implementation, receives the required strict realistic known-gap test.
- Do not change numeral pronunciation conventions unrelated to suffix-bearing numeric tokens.

---
**Maintenance note (for the implementing agent):** when this plan is implemented, update the `Status:` line above, e.g. `Status: implemented YYYY-MM-DD in branch `feat/<name>``. If the plan changes during implementation, update the affected sections too — the plan must not lie about what was built.
