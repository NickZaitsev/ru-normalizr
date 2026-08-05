# Plan: Refactor unit normalization into a validated registry and bounded expression parser

Status: plan, 2026-08-05.

> Note for agents: this plan is a point-in-time snapshot — its "codebase facts" describe the code as of the date above and may be outdated. Do NOT treat it as current architecture docs; verify every fact against the actual code before relying on it.

## Context

Unit normalization is currently driven by two large alias dictionaries in `src/ru_normalizr/numerals/_constants.py`, plus several independent token and regex consumers. The runtime inventory contains 377 aliases for 145 lemmas: 348 aliases in the case-folded table and 29 aliases in the exact-case table. The data mixes canonical unit metadata, morphology overrides, aliases, currencies, percentages, compound spellings, and spoken suffixes.

The current resolver checks the exact table and then unconditionally calls `UNITS_DATA.get(original.lower())`. This loses semantic case distinctions. Confirmed examples include `мПа` being read as megapascals, `Мг` as milligrams, `Mb/s` as megabytes per second, and `GBps` as gigabits per second. The exact and folded maps already have ten folded-key groups with conflicting meanings, including `ma`, `mv`, `mw`, `kb`, `mb`, `gb`, `tb`, `mbps`, `гр`, and `мвт`.

Case handling is only one symptom. Cardinal, decimal, range, version, hyphen, year-context, and glued-number code each perform their own partial unit recognition. `UNIT_SLASH_PATTERN` is a manually maintained whitelist separate from the alias inventory. Cardinal matching joins at most four tokens, while decimal matching has a different two-token path. Compound readings are stored as opaque aliases with static suffix strings, so `/`, `·`, and powers do not have one parsing or rendering contract.

The refactor must preserve generalizable morphology-aware behavior, remain linear in input length, avoid a version bump, add Russian changelog text for user-visible changes, and turn fixed strict `xfail` cases into focused regular tests. There are no external services, endpoints, or paid APIs.

## Approved decisions

1. Generate prefixed units from declarations, but only for explicitly prefixable base units and explicitly allowed prefixes. Do not form the unrestricted Cartesian product of every prefix and every unit.
2. Generate both standard Latin symbols and explicitly declared Cyrillic/localized symbol families. Never invent localized symbols by automatic transliteration.
3. Resolve an exact alias first. Permit case repair only when the folded alias group has exactly one semantic target; if case changes the meaning, require an exact spelling and leave unknown variants unexpanded.
4. Case repair for a single-letter symbol is disabled. In particular, bare uppercase `М` is not guessed as metre or molarity; `5 М` normalizes to `пять М`, while lowercase `5 м` remains `пять метров`.
5. Multi-letter, semantically unambiguous case damage may be repaired: `мМ` and `ММ` may resolve as millimetres, `мкМ` as micrometres, and `нМ` as nanometres once those length units exist in the generated registry.
6. Do not support shorthand molarity symbols `М`, `мМ`, `мкМ`, or `нМ`. Amount concentration is recognized only through a fully written unit-per-volume form such as `моль/л`, `ммоль/л`, `мкмоль/л`, or `нмоль/л`.
7. Latin information symbols are semantic and case-aware: `b/B` distinguish bit/byte, as do `Mb/MB`, `Mbps/MBps`, and the corresponding kilo/giga/tera families. An ambiguous malformed variant is not guessed. Folded Cyrillic word-like aliases such as `мбит` and `мбайт` remain supported.
8. Introduce one bounded unit-expression parser for division (`мг/кг`, `Mb/s`, `моль/л`), multiplication (`кВт·ч`), and powers (`м²`, `м³`). It must be registry-driven and longest-match-first, not a general mathematical parser.
9. Use the same resolver, match object, and renderer from integer, decimal, range, hyphen, version, year-disambiguation, and glued-number paths. Preserve mode behavior unless an output is explicitly changed by this plan.
10. Migrate currency and percentage entries onto the shared registry infrastructure without changing their normalization behavior. Decimal currency splitting and other currency feature work remain separate.
11. Keep declarations as typed Python data. Do not add JSON/YAML registries, a public custom-unit API, runtime plugins, value conversion, dimensional analysis, or arbitrary nested unit algebra.
12. Guard generation against degradation with import-time registry validation, differential regression coverage for all accepted existing aliases, explicit ambiguity matrices, the full test suite, and the existing performance benchmarks.

## Key codebase facts

- `src/ru_normalizr/numerals/_constants.py:272` defines `UnitMorphology`; `UnitDescriptor` follows at line 295. `_UNIT_MORPHOLOGY` stores manual pymorphy overrides and validated paradigms.
- `_upgrade_units` at `src/ru_normalizr/numerals/_constants.py:491` creates a separate descriptor for every alias. `UNITS_DATA` begins at line 509 and `CASE_SENSITIVE_UNITS_DATA` at line 867.
- `resolve_unit_info` at `src/ru_normalizr/numerals/_constants.py:909` performs exact lookup followed by unconditional lowercase fallback. `resolve_unit_form` at line 921 performs morphological fallback after lowercasing the surface.
- `ENTITY_KEYWORDS` and `ALL_UNITS` at lines 949 and 955 flatten exact aliases back to lowercase. They are consumed by numeral case inference, year disambiguation, and glued-number classification.
- `UNIT_TOKEN_FRAGMENT` at `src/ru_normalizr/numerals/_constants.py:964` is a generic token-shape regex, not an alias-derived matcher. Many registered punctuation and currency aliases cannot full-match it.
- `normalize_cardinal_numerals` at `src/ru_normalizr/numerals/cardinals.py:102` owns a nested `extract_unit_candidate` at line 139. It concatenates up to four tokens and calls `resolve_unit_info` repeatedly.
- `normalize_numeric_unit_ranges` at `src/ru_normalizr/numerals/cardinals.py:399` has a separate unit path and its own multiword morphology fallback.
- `DECIMAL_PATTERN` and `normalize_decimals` at `src/ru_normalizr/numerals/decimals.py:29` and line 36 implement another unit capture path. Decimal rendering currently forces a recognized unit to genitive singular and independently handles a possible second token and abbreviation dot.
- `UNIT_SLASH_PATTERN` and `protect_unit_slashes` at `src/ru_normalizr/preprocess_utils.py:15` and line 56 whitelist selected compounds before the general slash cleanup runs.
- `PipelineNormalizer._classify_glued_numeric_rhs` at `src/ru_normalizr/normalizer.py:320` tests `word_lower in ALL_UNITS`; this bypasses exact-case semantics.
- `src/ru_normalizr/numerals/_hyphen.py`, `versions.py`, `src/ru_normalizr/years_context.py`, and `src/ru_normalizr/roman_numerals.py` each query a different subset of the current unit API.
- `inflect_unit_lemma` is in `src/ru_normalizr/numerals/_helpers.py:212`. It consumes `UnitDescriptor` and already supports validated paradigms, indeclinable units, bit counting forms, and byte-family restrictions.
- Existing unit-focused coverage lives primarily in `tests/test_unit_morphology.py`, `tests/test_cardinal_stage.py`, `tests/test_stages.py`, `tests/test_reported_regressions.py`, and `tests/test_known_gaps.py`. `tests/test_e2e_benchmark.py` contains the performance gate.
- `docs/agents/case-sensitive-units.md` records the current collision audit. `docs/agents/conventions.md` defines accepted byte-family output forms.
- Current project gates are `uv run ruff check .`, `uv run pyright`, and `uv run pytest`. User-visible fixes require a Russian entry under `CHANGELOG.md` → `Unreleased`; this is not a release and must not change versions.

## Implementation

### 0. Lock the migration baseline

Modify `tests/test_unit_morphology.py`, `tests/test_reported_regressions.py`, and `tests/test_known_gaps.py` before changing the resolver.

1. Keep the explicit policy test that shorthand `М` forms never receive a molar descriptor and that `ммоль/л` remains an explicit amount-concentration alias.
2. Keep a strict full-sentence `xfail` for bare uppercase `М`, whose target output preserves the letter while normalizing the number.
3. Add table-driven baseline cases for every currently correct alias family: ordinary Russian unit names, dotted abbreviations, currencies, percent units, temperatures, time, bytes/bits, exact electrical symbols, ranges, decimals, glued quantities, and hyphen-linked quantities.
4. Record all intentional output changes in a small explicit expected-change table in the tests; do not bless unrelated differential changes.
5. Add inventory assertions for the current canonical semantic targets, not for the legacy dictionary layout, so the tests survive the structural migration.

### 1. Introduce canonical unit models and a validated registry

Create `src/ru_normalizr/numerals/unit_registry.py` and `src/ru_normalizr/numerals/unit_data.py`.

1. Move `UnitMorphology` and `UnitDescriptor` into `unit_registry.py` without changing their rendering contract. Keep temporary re-exports from `_constants.py` while internal imports migrate.
2. Add immutable declarations along these lines:
   - `UnitAlias(text: str, kind: Literal["word", "symbol"], allow_case_repair: bool = True)`;
   - `UnitDefinition(id: str, lemma: str, gender: str, category: str, aliases: tuple[UnitAlias, ...], morphology: UnitMorphology, suffix: str | None = None, prefixable: bool = False, allowed_prefixes: frozenset[str] = frozenset())`;
   - `PrefixDefinition(id: str, spoken: str, exponent: int, latin: str | None, cyrillic: tuple[str, ...])`;
   - `UnitMatch(descriptor: UnitDescriptor, source: str, alias: str, consumed_tokens: int, expression: UnitExpression | None = None)`.
3. Build immutable exact and folded-group indexes once at import. Semantic identity must include the canonical definition id and spoken suffix, not merely the lemma.
4. Implement `UnitRegistry.resolve(token: str) -> UnitDescriptor | None` with this order:
   - trim only explicitly supported boundary punctuation;
   - exact lookup;
   - reject case repair for single-letter symbols;
   - casefold lookup only when the folded group has one semantic target and every participating alias permits repair;
   - otherwise return `None`.
5. Implement explicit query methods instead of exposing lowercase bags: `is_unit_token(token: str)`, `is_exact_symbol(token: str)`, `is_non_year_unit(token: str)`, and `entity_category(token: str)`. Callers must not lowercase before invoking them.
6. Validate at construction and raise a descriptive `ValueError` for duplicate exact aliases with different targets, an alias assigned to incompatible categories, a generated alias colliding with a manual alias, missing canonical definitions, invalid morphology metadata, and unreachable aliases.
7. Keep exceptions proportional: registry construction is deterministic local data validation, so fail immediately rather than logging and continuing with a corrupt inventory.

### 2. Replace hand-written prefix duplication with bounded generation

Populate `unit_data.py` with canonical definitions, aliases, prefix declarations, and morphology overrides migrated from `_constants.py`.

1. Define only prefixes currently needed by supported units, then expand deliberately as tests require. Include correct exponent and exact Latin/localized symbols; uppercase/lowercase is data, not normalization logic.
2. Each base unit declares its permitted prefixes. Examples include gram, metre, second, pascal, newton, hertz, volt, ampere, watt, farad, litre, mole, bit, and byte, but the implementing agent must audit existing support before finalizing the allowlists.
3. Treat kilogram as the historical mass exception: prefixes attach to gram, never recursively to kilogram.
4. Generate canonical spoken lemmas from prefix spoken form plus base lemma, with explicit overrides where Russian spelling or pymorphy requires one. Reuse `_UNIT_MORPHOLOGY` paradigms until each generated lemma passes the morphology route test.
5. Generate Latin and Cyrillic symbols only from explicit base-symbol declarations. Do not transliterate arbitrary source text.
6. Exclude molarity shorthand from generation. Keep `моль/л`, `ммоль/л`, `мкмоль/л`, and `нмоль/л` as explicit or structurally composed amount-per-volume expressions.
7. Model bit and byte as different canonical definitions. Generate only approved prefix families and exact `b/B`-sensitive symbols; retain Cyrillic word-like compatibility aliases separately.
8. Migrate currencies and percentages as non-prefixable definitions. Preserve their aliases and existing morphology exactly.

### 3. Add a single bounded unit-expression matcher

Create `src/ru_normalizr/numerals/unit_expressions.py`.

1. Define a bounded `UnitExpression` model for:
   - one atomic registered unit;
   - an atomic unit with exponent 2 or 3;
   - one numerator and one denominator separated by `/`;
   - one product separated by `·`, `.`, or a registered hyphen spelling where unambiguous.
2. Do not accept nested expressions, arbitrary arithmetic, arbitrary exponents, or unknown atoms. Registered compound aliases may override generic composition when they have a lexicalized reading such as `киловатт-час`.
3. Implement `match_unit_tokens(tokens: Sequence[str], start: int) -> UnitMatch | None` and `resolve_unit_expression(raw: str) -> UnitMatch | None`. Both must use the same registry and return the longest valid match plus the exact consumed span.
4. Build first-token indexes or a small trie at registry construction. Runtime matching must be bounded by the maximum registered alias/expression length and must never loop through all aliases for every input token.
5. Centralize abbreviation-dot ownership and punctuation preservation in the match object. Remove caller-specific guesses about whether a dot belongs to a unit or the sentence.
6. Replace `UNIT_SLASH_PATTERN` with registry-aware protection. A slash is protected only when both sides form a supported unit expression; unrelated paths, fractions, dates, and prose slashes keep their current pipeline behavior.

### 4. Centralize unit rendering

Create `src/ru_normalizr/numerals/unit_rendering.py` or move the cohesive unit-specific pieces out of `_helpers.py` if that avoids circular imports.

1. Preserve `inflect_unit_lemma(unit: UnitDescriptor | str, target_tags: set[str]) -> str` as the canonical atomic inflector, including validated manual paradigms and logging behavior.
2. Add `render_unit_expression(match: UnitMatch, *, value: int | None, case: str, number_kind: Literal["integer", "decimal", "range"]) -> str`.
3. Render squared/cubic units through registered adjective+noun lemmas so both words inflect together. Do not derive Russian output by appending a generic word after rendering.
4. Render denominator expressions with the approved spoken relation (`на` or `в`) stored in the canonical compound definition, not by copying a static suffix between unrelated aliases.
5. Render lexicalized products such as energy units through their canonical compound definition. Keep multiplication notation in mathematical expressions separate from physical-unit products.
6. Preserve existing cardinal, paucal, plural-only, decimal, and governed-case behavior unless a focused regression test explicitly changes it. Do not use this refactor to silently rewrite general numeral morphology.

### 5. Migrate every consumer to the shared API

Modify the following files in small, testable steps:

1. `src/ru_normalizr/numerals/cardinals.py`: replace nested `extract_unit_candidate`, `_resolve_range_unit_info`, and direct map access with `match_unit_tokens` and the shared renderer for cardinal quantities and ranges.
2. `src/ru_normalizr/numerals/decimals.py`: keep decimal-number rendering separate, but replace both unit captures, combined-candidate construction, suffix handling, and dot handling with a returned `UnitMatch`.
3. `src/ru_normalizr/preprocess_utils.py`: replace the slash whitelist with registry-aware unit-expression protection without changing fraction/date behavior.
4. `src/ru_normalizr/normalizer.py`: make `_classify_glued_numeric_rhs` query the registry with the original spelling. An ambiguous or rejected symbol must not become a unit merely because its lowercase form exists.
5. `src/ru_normalizr/years_context.py`: replace `ALL_UNITS`/`ENTITY_KEYWORDS` membership and morphological re-resolution with the registry query methods while preserving bounded context scans.
6. `src/ru_normalizr/roman_numerals.py`: protect exact Roman-shaped unit symbols through `is_exact_symbol`, including generated symbols such as `MV`, without protecting rejected case variants.
7. `src/ru_normalizr/numerals/_hyphen.py` and `versions.py`: use the shared resolver and match policy; keep the existing ambiguity guard for single-letter hyphen suffixes.
8. `src/ru_normalizr/numerals/_constants.py` and `numerals/__init__.py`: remove migrated unit data and lowercase derived indexes after all callers move. Keep compatibility re-exports only if a repository-wide import search shows a required internal transition; do not promise new public API.

### 6. Fix and graduate the scoped known gaps

Use the new registry/parser to address unit defects, but move an `xfail` only when its entire realistic expected sentence passes.

1. Fix `case_sensitive_si_prefixes`, `case_sensitive_bit_byte_rates`, `wavelength_and_thickness`, and `ambiguous_uppercase_single_letter_unit`.
2. Exercise generated milli/mega pairs in both directions, including `мПа/МПа`, `мН/МН`, `мГц/МГц`, `мг/Мг`, `мм/Мм`, `мс/Мс`, `мл/Мл`, and `мФ/МФ` where the corresponding generated unit is approved.
3. Fix registry/parser portions of compound-unit gaps such as `мг/кг`, `мл/мин`, `кВт·ч`, square/cubic units, and fully written amount concentration. If a case also depends on unrelated decimal morphology, formula parsing, currency logic, or mathematical layout, keep it strict `xfail` and add a narrower focused regular test for the unit sub-behavior.
4. Remove no `xfail` by weakening its expected output or by marking only part of an assertion.

### 7. Documentation and changelog

1. Update `docs/agents/case-sensitive-units.md` in Russian with the final registry algorithm, ambiguity-group rule, single-letter exception, generated-prefix policy, and the deliberate rejection of shorthand molarity.
2. Update `docs/agents/conventions.md` in Russian with exact bit/byte rate readings and compound-unit output conventions.
3. Update the Russian README unit examples only if documented behavior changes or new supported notation is user-facing.
4. Add Russian `CHANGELOG.md` entries under `Unreleased` describing corrected case-sensitive units, safe case repair, generated prefixes, and supported compound notation.
5. Do not change `pyproject.toml` or package versions.

## Testing & verification

1. Add focused registry tests in a new `tests/test_unit_registry.py`:
   - exact resolution for every alias;
   - unique folded-group repair, including `КГ`;
   - rejection of ambiguous folded groups;
   - rejection of uppercase single-letter repair (`М`);
   - duplicate/collision validation failures;
   - generated prefix allowlists and historical kilogram behavior;
   - no shorthand molarity target;
   - canonical full amount-concentration expressions.
2. Expand `tests/test_unit_morphology.py` with table-driven `1/2/5`, six-case, decimal, and range coverage for representative generated lemmas. Keep the all-descriptors morphology-route invariant.
3. Add expression tests covering spaces around separators, `µ/μ/мк` micro spellings when explicitly supported, `/`, `·`, `.`, `²/³`, punctuation boundaries, sentence-final dots, and longest-match behavior.
4. Add negative/boundary cases for dates, fractions, URLs, paths, formulas, model numbers, ordinal suffixes, ordinary words after numbers, unsupported nested expressions, malformed case, and lone symbols.
5. Add a bit/byte matrix for `b/B`, `kb/kB`, `Mb/MB`, `Gb/GB`, `Tb/TB`, `bps/Bps`, slash forms, and Cyrillic word aliases. Every expected distinction must be asserted end-to-end.
6. Add a case-degradation matrix for each supported symbol family. For a unique semantic fold group, representative damaged variants resolve identically; for an ambiguous fold group, only registered exact aliases resolve; single-letter case repair always fails.
7. Keep old accepted-output cases while migrating each caller. Run focused tests after each integration step so a cardinal fix cannot hide a decimal, year, version, or hyphen regression.
8. Run `uv run ruff check .`, `uv run pyright`, and `uv run pytest` before every commit and after the final integration.
9. Run the existing `tests/test_e2e_benchmark.py` gate and a number-dense corpus containing many unit candidates. Verify matching remains linear and that adding aliases does not increase per-token work proportionally to registry size.
10. Verify all strict `xfail` cases: fixed cases must become passing focused tests; all remaining gaps must still fail for their documented reason, with no unexpected `XPASS`.
11. Inspect the built wheel if modules are added or packaging changes: `uv run python -m build`, install the wheel into a clean temporary environment, and normalize representative units through both the Python API and CLI.

## Out of scope

- Numeric value conversion between units.
- General dimensional analysis or validation of physically compatible expressions.
- Arbitrary nested expressions, arbitrary powers, equations, scientific notation, or chemical formula parsing.
- Shorthand molarity symbols `М`, `мМ`, `мкМ`, and `нМ`.
- A public API, config file, plugin, or dictionary syntax for custom units.
- A functional redesign of currency and percentage normalization, including major/minor currency splitting.
- Fixing unrelated numeral-case, decimal morphology, formula, display-resolution, or mathematical-expression gaps merely because their examples contain a unit.
- A package version bump or release work.

---
**Maintenance note (for the implementing agent):** when this plan is implemented, update the `Status:` line above, e.g. `Status: implemented YYYY-MM-DD in branch <branch>.` If the plan changes during implementation, update the affected sections too — the plan must not lie about what was built.
