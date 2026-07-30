# Plan: Production readiness — layout, tooling strictness, docs cleanup, coverage

Status: implemented 2026-07-30 in branch `main`. The CI workflow was not
pushed or run; its wheel-install smoke sequence passed locally in a fresh
Python 3.12 environment.

> Note for agents: this plan is a point-in-time snapshot — its "codebase facts" describe the code as of the date above and may be outdated. Do NOT treat it as current architecture docs; verify every fact against the actual code before relying on it.

## Context

A full production-readiness review (2026-07-30) of this PyPI library found: the package is laid out flat at the repo root (`package-dir ru_normalizr = "."`), which forces an import-fallback hack in `__init__.py`, breaks pyright package resolution, and makes packaging fragile; lint/typecheck are far weaker than the org template (`C:\00_projects\template\docs\typecheckers\python`); several docs are stale or dangling; branch coverage is 82% overall with the CLI at 0%; dev dependencies are unpinned so CI is nondeterministic. Tests are green (314 passed, 2 xfailed, 232 subtests), gitleaks is clean on history and working tree, and the release flow (tag → GitHub Actions → PyPI trusted publishing) is sound.

This plan makes the library production-ready without changing normalization behavior. Every phase must end with a green `pytest` run and an atomic conventional commit.

## Approved decisions

1. **Migrate to src-layout** (`src/ru_normalizr/`). Approved 2026-07-30.
2. **Historical docs** (`docs/BUGFIX_PLAN.md`, `docs/BUGFIX_PLAN_2.md`, `docs/CODE_REVIEW.md`): relocate the still-referenced TASK-1 rationale into `docs/agents/`, retarget the AGENTS.md gotcha, then delete all three (history stays in git).
3. **Migrate dev tooling to uv + committed `uv.lock`**; delete `requirements-dev.txt`; CI uses `uv sync --frozen`.
4. **Pyright: adopt `standard` mode now (in CI), move to `strict` for the package as a separate later task.** Do not project-wide disable `reportOptionalMemberAccess` — Optional flow is meaningful in this library; type the `_morph` facade instead.
5. `eng_to_ipa` stays a hard default dependency — deliberate decision, commit `3665c65` reverted the `[ipa]` extra. Only fix the stale "Optional" wording in the release checklist.
6. Keep `ignore = ["E501"]` in ruff (98 violations, almost all long Cyrillic linguistic tables / regex comments — churn without value). Documented deviation from the template.

## Key codebase facts

- Flat layout wiring: `pyproject.toml` `[tool.setuptools]` `packages = ["ru_normalizr", "ru_normalizr.numerals"]`, `[tool.setuptools.package-dir] ru_normalizr = "."`, plus `exclude-package-data` listing root files (LICENSE, CHANGELOG.md, VERSIONING.md, …) that would otherwise leak into the wheel.
- `__init__.py:3-8` — try/except ImportError fallback (`from .options import …` / `from ru_normalizr.options import …`) that exists only because of the flat layout. `tests/test_api.py:32` `test_package_init_supports_direct_file_import` pins this hack and becomes obsolete with src-layout.
- All package modules use **relative imports** (`from ._morph import first_parse`); tests and `scripts/benchmark.py` use absolute `ru_normalizr` imports against the editable install → the src move is mechanical for code, but **packaging tests reference the repo layout**: `tests/test_api.py:24` `_clean_build_artifacts`, `:1132` `test_package_metadata_files_exist`, `:1142` `test_package_builds_as_wheel_from_package_directory`, `:1200` `test_wheel_includes_every_tracked_dic_file` — these must be updated in the same commit.
- `scripts/dev.py`: `package_version()` reads `ROOT / "__init__.py"` (line 73); `CLEAN_PATHS`/`PUBLISH_IGNORED_PREFIXES` mention `ru_normalizr.egg-info` at root. `publish` flow (clean tree → push main → tag `vX.Y.Z` → push) is good; keep it.
- `MANIFEST.in` prunes `tests`, `scripts`, and the no-longer-existing `examples`; `recursive-include dictionaries *.dic` and `recursive-include numerals *.py` are root-relative and must change with the layout.
- CI (`.github/workflows/ci.yml`): matrix ubuntu 3.10–3.13 + windows 3.12, weekly cron (guards unpinned `num2words` against exact-output tests — keep the cron and its comment). Steps: `pip install -r requirements-dev.txt`, `pip install -e .`, ruff, pytest, build. No pyright, no coverage. `release.yml`: `scripts/dev.py check` + `check-release-tag` + `pypa/gh-action-pypi-publish` (trusted publishing, `id-token: write` — no secrets; verified good).
- Ruff today: `select = ["E","F","I"]`, `ignore = ["E501"]`. Template ruleset (`E,F,I,UP,B,SIM,RUF` minus `RUF001-003`) yields **24 findings, 8 autofixable**. `B023` at `dictionary.py:236` is benign (lambda consumed within the same loop iteration) — fix via `mapping=mapping` default-arg binding. Three `B905` `zip(strict=)` sites: `abbreviations.py:470`, `latinization.py:167`, `latinization.py:174` (verify list with ruff at implementation time).
- Pyright measured with template-style config: **strict = 322 errors** (dominated by unknown types from unstubbed pymorphy3/num2words/eng_to_ipa), **standard = 117 errors**: ~58 `reportOptionalMemberAccess` (`.tag`/`.normal_form`/`.inflect` on `first_parse(...)` results typed `Any | None` — see `_morph.py:20-33`), 54 `reportArgumentType`, and singletons worth checking as real defects: `numerals/_helpers.py:319` (`kwargs` possibly unbound in the `except` logger call — bind before `try`), `numerals/_helpers.py:163` (`fallback_word: str | None` returned where `-> str` declared), `latinization.py:169` (`dict.update` overload mismatch), 4 `reportUnusedFunction`, 1 `reportUnusedImport`, 2 `reportMissingImports` (the `__init__.py` fallback branch — disappears with src-layout).
- Coverage (branch, tests+scripts omitted): TOTAL **82%**; `__main__.py` **0%** (CLI fully untested); `years_context.py` 65%, `numerals/fractions.py` 67%, `years.py` 70%, `dates_time.py` 75%, `ordinal_utils.py` 75%, `numerals/_helpers.py` 76%. Strong modules: options/pipeline/constants 100%, normalizer 95%, preprocess_utils 95%.
- Docs audit results (verified 2026-07-30): README.md has two dead links to deleted `examples/your_dictionary.dic` (lines 171, 481; commit `2ab5d7d` removed the file); everything else in README (CLI flags, API examples, 24-option table, stage list) matches the code exactly; README is Russian-first with English mirror — compliant. CHANGELOG.md embeds the whole versioning policy at lines 1–32 before `# Changelog`, and its Release rules cite non-existent paths `ru_normalizr/__init__.py`. `VERSIONING.md` does not exist but is referenced from `AGENTS.md:14` and `pyproject.toml:56`. `PYPI_RELEASE_CHECKLIST.md:87` falsely calls `eng_to_ipa` "Optional"; line 85 checks the removed `examples/` file. The three historical docs in `docs/` are fully executed (verified 1:1 against commits); `AGENTS.md:73` gotcha links to "TASK-1 in docs/BUGFIX_PLAN_2.md" (grammeme canonicalization, implemented at `numerals/_helpers.py:282-293`). All seven `docs/agents/*.md` topics are accurate, but the required `docs/agents/README.md` index is missing and `stage-ordering.md` / `version-numbers.md` are referenced from nowhere.
- No `.gitattributes` in the repo. `dictionaries/latinization/latinization_rules.dic` is stored LF; `dictionary.py:106` reads text-mode UTF-8 (universal newlines), so CRLF checkouts work — the risk is phantom diffs, not breakage.
- `.agents/skills/` and `.claude/skills/` are byte-identical duplicates (intentional: two agent-tool conventions). Leave as is.

## Implementation

Each phase is one atomic commit (or a small series); run `ruff check .` + `pytest -q` before every commit (plus `pyright` once phase 4 lands). Suggested order minimizes rebase noise: docs first, then layout, then tooling on top of the new layout.

### 1. Docs cleanup and consolidation

Files: `CHANGELOG.md`, `VERSIONING.md` (new), `AGENTS.md`, `docs/agents/numeral-cache-grammemes.md` (new), `docs/agents/README.md` (new), `docs/RELEASING.md` (moved), `README.md`, `MANIFEST.in`, `pyproject.toml`, delete `docs/BUGFIX_PLAN.md`, `docs/BUGFIX_PLAN_2.md`, `docs/CODE_REVIEW.md`, `PYPI_RELEASE_CHECKLIST.md`.

1. Extract CHANGELOG.md lines 1–32 (versioning policy) into a new root `VERSIONING.md`; leave CHANGELOG starting at `# Changelog`. Fix the policy's Release-rules paths to the post-migration truth (`src/ru_normalizr/__init__.py`, root `pyproject.toml`) — write them layout-agnostically ("the package `__init__.py`") to avoid a second edit after phase 2. This heals the dangling refs at `AGENTS.md:14` and `pyproject.toml:56` instead of removing them.
2. Create `docs/agents/numeral-cache-grammemes.md` with the TASK-1 rationale from `docs/BUGFIX_PLAN_2.md` (why cached numeral rendering must canonicalize pymorphy grammemes before lookup; point at `numerals/_helpers.py` `_inflect_numeral_string_cached` and the canonicalization at lines ~282-293). Retarget the `AGENTS.md` gotcha bullet to this file. Then delete the three historical docs.
3. Create `docs/agents/README.md` indexing every topic doc (the existing seven + the new one + `plans/`), two-sentence description each, in Russian.
4. `git mv PYPI_RELEASE_CHECKLIST.md docs/RELEASING.md`; while editing: fix line 87 ("Optional eng_to_ipa" → state it is a default dependency whose IPA backend degrades gracefully if the import breaks), drop the vacuous `examples/` item (line 85), mention `scripts/dev.py check-release-tag`, and switch commands to `uv run …` (phase 3 lands before release anyway). Grep the repo for `PYPI_RELEASE_CHECKLIST` and update inbound references (AGENTS.md/README if any).
5. README.md: remove/inline the two dead `examples/your_dictionary.dic` links at lines 171 and 481 (the `.dic` format snippet already sits next to each — reference the snippet instead). Both the Russian and English halves.
6. MANIFEST.in: drop `prune examples`.

Commit: `docs: консолидировать документацию — VERSIONING.md, индекс docs/agents, удалить выполненные планы`.

### 2. src-layout migration

Files: everything package-related moves; `pyproject.toml`, `MANIFEST.in`, `scripts/dev.py`, `tests/test_api.py`, `.gitignore`, `AGENTS.md` gotcha paths if any mention root modules.

1. `git mv` all package modules and data into `src/ru_normalizr/`: the ~25 root `*.py` package files (`__init__.py`, `__main__.py`, `_morph.py`, `abbreviation_*.py`, `abbreviations.py`, `caps.py`, `constants.py`, `dates_time.py`, `dictionary.py`, `latinization.py`, `normalizer.py`, `numbering.py`, `options.py`, `ordinal_utils.py`, `pipeline.py`, `preprocess_utils.py`, `roman_numerals.py`, `text_context.py`, `urls.py`, `years.py`, `years_context.py`), the `numerals/` package, `dictionaries/`, and `py.typed`. `tests/` and `scripts/` stay at root.
2. `pyproject.toml`:
   - `[tool.setuptools] package-dir = {"" = "src"}`, `packages = ["ru_normalizr", "ru_normalizr.numerals"]` (or `[tool.setuptools.packages.find] where = ["src"]`).
   - Delete the whole `[tool.setuptools.exclude-package-data]` section — with src-layout nothing leaks.
   - Keep `[tool.setuptools.package-data] ru_normalizr = ["py.typed", "dictionaries/**/*.dic"]`.
3. `src/ru_normalizr/__init__.py`: remove the try/except ImportError fallback — plain relative imports only. Delete `tests/test_api.py` `test_package_init_supports_direct_file_import` (pins the removed hack).
4. `MANIFEST.in`: rewrite for src paths (`recursive-include src/ru_normalizr/dictionaries *.dic`; the `recursive-include numerals *.py` line becomes unnecessary — packages are picked up by setuptools; keep `prune tests`, `prune scripts`).
5. `scripts/dev.py`: `package_version()` path → `ROOT / "src" / "ru_normalizr" / "__init__.py"`; `CLEAN_PATHS`/`PUBLISH_IGNORED_PREFIXES`: egg-info now appears under `src/` (`src/ru_normalizr.egg-info`) — cover both old and new locations in clean.
6. Update the packaging tests in `tests/test_api.py` (`_clean_build_artifacts`, `test_package_metadata_files_exist`, `test_package_builds_as_wheel_from_package_directory`, `test_wheel_includes_every_tracked_dic_file`) to the new paths; the wheel-content assertions themselves stay (they are the regression net for this migration).
7. `.gitignore`: ensure `src/*.egg-info/` is covered (`*.egg-info/` already matches — verify).
8. Reinstall editable (`pip install -e .` into `.venv` / later `uv sync`), full test run, then `python scripts/dev.py check` (clean → version sync → lint → test → build → twine check) must pass end-to-end.

Commit: `refactor(packaging)!: перейти на src-layout` (behavior-neutral for library users; `!` only if you consider import-path guarantees part of the contract — installed import paths do NOT change, so a plain `refactor(packaging):` is acceptable; CHANGELOG Unreleased entry either way).

### 3. uv migration (dev tooling + CI)

Files: `pyproject.toml`, `uv.lock` (new), delete `requirements-dev.txt`, `.github/workflows/ci.yml`, `.github/workflows/release.yml`, `docs/RELEASING.md`, `README.md` (contributor section, if it references pip dev flow), `AGENTS.md` (no change needed — its defaults already say `uv run …`).

1. `pyproject.toml`: add `[dependency-groups] dev = ["build>=1.0", "pytest>=7.0", "pytest-cov>=5.0", "ruff>=0.4", "pyright>=1.1", "twine>=5.0"]`. Run `uv lock` and commit `uv.lock`. Delete `requirements-dev.txt`.
2. `ci.yml`: replace pip steps with `astral-sh/setup-uv` (pin action major, enable cache) + `uv sync --frozen` + `uv run ruff check .` / `uv run pyright` (added in phase 4) / `uv run pytest -q`; build via `uv build` or keep `uv run python -m build .`. Keep the matrix and the weekly cron comment intact. Note: the cron exists to catch new `num2words` releases — `uv.lock` would freeze it; therefore the scheduled run must refresh the lock for the test job (`uv lock --upgrade-package num2words && uv sync` or simply `uv sync --upgrade` on `schedule` events only) so upstream releases are still caught. Gate on `github.event_name == 'schedule'`.
3. `release.yml`: same setup; `uv run python scripts/dev.py check` and `check-release-tag`.
4. `scripts/dev.py` `lint`/`test` subcommands run `sys.executable -m …` — they keep working inside `uv run`; no change required, but verify.

Commit: `build: перевести dev-окружение на uv с uv.lock`.

### 4. Ruff and pyright per template

Files: `pyproject.toml`, ~15 source files with mechanical fixes, `.github/workflows/ci.yml`, `AGENTS.md` (commit-check bullet already matches `uv run ruff check . && uv run pyright`).

1. Ruff: `select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]`, `ignore = ["E501", "RUF001", "RUF002", "RUF003"]` with a one-line comment for each ignore (E501: long Cyrillic linguistic tables; RUF00x: false positives on Cyrillic text per template). Fix all 24 findings: `ruff check --fix` for the 8 safe ones; `B905` → explicit `strict=False` where iterables legitimately differ or `strict=True` where they must match (check `ABBREVIATION_PATTERNS`/`ABBREVIATION_LITERAL_HINTS` are same-length — if yes, `strict=True` is a free invariant); `B023` at `dictionary.py:236` → bind via lambda default arg.
2. Pyright: add `[tool.pyright]` to `pyproject.toml` (NOT `pyrightconfig.json` — one config home, per template gotcha):
   `pythonVersion = "3.10"`, `typeCheckingMode = "standard"`, `include = ["src", "scripts"]`, `exclude = ["tests", "**/__pycache__", ".venv", "build", "dist"]`, `venvPath = "."`, `venv = ".venv"`, plus `reportUnnecessaryTypeIgnoreComment = "error"`. (Tests excluded per template default; `strict = ["src"]` and the other three error-promotions are the follow-up task, not this plan.)
3. Fix the real diagnostics behind standard mode:
   - `numerals/_helpers.py:319`: move `kwargs` initialization before the `try` so the `except` logger call is always bound.
   - `numerals/_helpers.py:163` (`inflect_word`-family): honest signature — `fallback_word` is `str | None`? Verify the caller contract; either narrow the parameter to `str` or widen the return annotation, whichever matches all call sites.
   - `latinization.py:169` `dict.update` overload — fix the argument shape.
   - Review the 4 `reportUnusedFunction` + 1 `reportUnusedImport`: delete if genuinely dead (check git history first), otherwise they are public-ish helpers — export or annotate.
   - The ~58 pymorphy Optional accesses: type the `_morph.py` facade. Introduce a `MorphParse` `Protocol` (attributes `word: str`, `normal_form: str`, `tag: Any`, method `inflect(grammemes: frozenset[str]) -> MorphParse | None`) in `_morph.py`; `parse_word` → `tuple[MorphParse, ...]`, `first_parse` → `MorphParse | None`. Then at call sites: where the code already guards (`if not parsed`), pyright narrows for free; where it dereferences unconditionally (the "pymorphy always returns ≥1 parse" invariant), add a small `first_parse_required(word) -> MorphParse` helper in `_morph.py` that asserts non-None at the single chokepoint, and switch those sites to it. No behavior change (assert documents the existing invariant; `first_parse` already exists as the guard chokepoint).
   - Remaining `reportArgumentType` (54): triage — many will collapse once the facade is typed; suppress only with per-line `# pyright: ignore[rule]` + reason where a third-party stub is at fault.
4. CI: add `uv run pyright` step after ruff (ubuntu cells are enough; keep the Windows cell running pytest only if pyright there is slow — decide by runtime).

Commit series: `style: расширить набор правил ruff до шаблонного` / `fix(types): устранить реальные дефекты типов, найденные pyright` / `ci: добавить pyright в обязательные проверки`.

### 5. Coverage: CLI tests and weakest modules

Files: `tests/test_cli.py` (new), `tests/test_years*.py` / `tests/test_fractions*.py` additions (or extend existing suites), `.github/workflows/ci.yml`.

1. `tests/test_cli.py` — call `ru_normalizr.__main__.main(argv)` directly (no subprocess for logic; one subprocess smoke via `python -m ru_normalizr` already exists in `tests/test_api.py` locale tests — verify, don't duplicate). Cover: inline text arg; `--file` (UTF-8, incl. Cyrillic); `--output` (adds trailing newline, UTF-8); `--check` exit codes 0/1; `--check` + `--output` → parser error (SystemExit 2); `--version`; stdin path (monkeypatch `sys.stdin`); `--mode tts` and each `--no-*`/`--keep-links`/`--latinization-backend`/`--with-latin-stress` flag mapping into `NormalizeOptions` (assert via a captured `normalize` call or by observable output). Target: `__main__.py` from 0% to ≥95% branch — it is thin glue over `NormalizeOptions`, so this is cheap.
2. Raise the weakest critical modules toward the tier bar (≥95% branch is the ideal for parser logic; pragmatic target for this pass: no module below 80%): `years_context.py` (65%), `numerals/fractions.py` (67%), `years.py` (70%). Read `--cov-report=term-missing` output and write table-driven tests for the uncovered *branches* (era suffixes, range edges, fraction denominators, boundary guards) — not filler line-hits. Any branch found unreachable is a candidate for deletion instead of a test.
3. CI: add a coverage step on one cell (ubuntu, py3.12): `uv run pytest -q --cov=src/ru_normalizr --cov-branch --cov-report=term-missing`. **No `--cov-fail-under` gate** — the number is a release diagnostic, not a commit gate (per review policy). Add `.coverage` to `.gitignore` (already there — verify).

Commit: `test(cli): покрыть CLI и слабые модули branch-тестами`.

### 6. Repo hygiene tail

Files: `.gitattributes` (new), `.github/workflows/ci.yml`.

1. `.gitattributes`: `* text=auto`, plus explicit `*.py text eol=lf`, `*.md text eol=lf`, `*.yml text eol=lf`, `*.toml text eol=lf`, `*.dic text eol=lf`. Run `git add --renormalize .` and inspect the diff before committing (should be empty or line-ending-only).
2. CI: add a wheel-install smoke job (section 2 of the review checklist — "verify in a clean production image"): build the wheel, create a fresh venv **without** the dev group, `pip install dist/*.whl`, then `ru-normalizr --version` and `ru-normalizr "тест 123"` must succeed. This is the manifest test that catches a missing runtime dependency or a data file dropped from the wheel.
3. CI: add `concurrency: { group: ci-${{ github.ref }}, cancel-in-progress: true }` (minor cost saving).

Commit: `ci: smoke-тест установки колеса и .gitattributes`.

## Testing & verification

- After every phase: `uv run ruff check .` (pip equivalents before phase 3), `uv run pytest -q` — 314+ passed, 2 xfailed, zero new failures. After phase 4 also `uv run pyright` → 0 errors.
- After phase 2 (the risky one): `python scripts/dev.py check` end-to-end (clean → version sync → lint → test → build → twine check); additionally unzip the built wheel and diff its file list against the pre-migration wheel — must be identical module-for-module (`ru_normalizr/*.py`, `ru_normalizr/numerals/*.py`, `ru_normalizr/dictionaries/**/*.dic`, `py.typed`, metadata).
- After phase 6: the wheel-install smoke sequence passed locally in a fresh Python 3.12 environment. The workflow itself was not run because this task did not authorize a push; its first remote run remains the final CI-environment confirmation.
- No paid/external APIs are involved anywhere.

## Out of scope

- **Pyright strict for `src`** — separate follow-up task after standard mode is green in CI (per approved decision 4).
- **Mutation testing (mutmut)** — proposed, not added (YAGNI): mutmut 3 does not run on native Windows; when desired, run it via Docker scoped to one critical module at a time (e.g. `numerals/_helpers.py` against `tests/`), per the production-readiness skill's documented recipe.
- **1.0.0 release** — VERSIONING.md already defines the pre-1.0 goals (lock default behavior, option naming, packaging/CLI shape); cutting 1.0 is a product decision, not part of this plan.
- **`.agents/skills` ↔ `.claude/skills` duplication** — intentional dual-convention support; left as is.
- **Fixing the 2 xfail known gaps** in `tests/test_known_gaps.py` — tracked there by design.
- **Confluence error notifications** — not applicable (public OSS library, no runtime service).
- **num2words upper version bound** — deliberately unbounded; the weekly CI cron is the chosen guard (see comment in ci.yml), now supplemented by the lock-refresh on scheduled runs (phase 3.2).

---
**Maintenance note (for the implementing agent):** when this plan is implemented, update the `Status:` line above, e.g. `Status: implemented YYYY-MM-DD in branch `feat/<name>``. If the plan changes during implementation, update the affected sections too — the plan must not lie about what was built.
