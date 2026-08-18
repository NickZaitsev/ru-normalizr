# ru-normalizr — Russian text normalization for TTS/NLP

## Core principle

Generalizable, morphology-aware rules. Never add a one-off replacement for a
single token or phrase — if a bug reproduces, fix the rule, not the string.
Target production-ready quality: no quick hacks or fragile workarounds unless
explicitly requested.

## Changelog and versions

- Any user-visible change goes to `CHANGELOG.md` under `## Unreleased`.
- Never bump the version outside explicit release tasks. On release, keep
  `__init__.py`, `pyproject.toml`, and `CHANGELOG.md` in sync (see `VERSIONING.md`).

# General rules

Write README.md, documentation, MRs and UI text in Russian.
Target production-ready quality: no quick hacks, temporary workarounds, or fragile solutions unless explicitly requested.
Never commit secrets or .env files; never print secrets to logs, error messages, events, or API responses.
YAGNI: Do not add infrastructure or integrations nobody asked for (monitoring, metrics, tracing, admin panels). Propose first; add only after explicit approval.
Whenever you identify a workaround, defect, or reliability risk, please highlight it and suggest a proper fix.

## Commits and branches

- Commit completed work yourself when a task or phase is finished — atomic conventional commits.
- Before every commit, run the project's lint, type-check, and test commands.
  Defaults when none are configured: Python — `uv run ruff check . && uv run pyright`
  (plus `uv run pytest` if tests exist); TypeScript — `npm run check`, otherwise the
  project's lint/type-check scripts plus relevant tests. Fix all errors caused by your changes.
- Commit messages and MR titles follow Git Atomic Conventional Commits: keep the type and scope in English (`feat(auth):`, `fix(db):`), write the description after the colon in Russian — e.g. `feat(consent): интегрировать Яндекс.Метрику`.
- Maintain .gitignore yourself: add generated, local, temporary, cache, build, and environment files as they appear.
- In the Bash tool, pass multi-line commit messages via `-m` with a regular double-quoted string (or heredoc), NOT PowerShell `@'...'@` syntax — the `@` leaks into the message text.
- Do not create new branches without explicit user confirmation. Work in the current branch; сreate a branch only on explicit request.
- On a push request: (1) run lint/type-check/tests; (2) push the current branch; (3) create annotated tag `tested-N` (next N from `git ls-remote --tags origin`) on the pushed commit and push it. Skip step 3 if 1 or 2 failed. Never move or delete existing tags.

## Tests and completion

- Add or update tests for changed behavior: happy path, failure path, and boundary cases; table-driven where one rule has many inputs.
- Run the relevant test scope when a change could affect behavior; run the full suite for broad, cross-cutting, risky, or release-level changes. Trivial non-behavioral edits (docs, comments, formatting, isolated constants) may skip tests.
- A bug fix starts with a test that reproduces the bug.
- No filler tests: no test without a meaningful assertion, no test whose only assertion is "the mock was called", no test that restates the implementation. Deleting a worthless test is an improvement.
- A task is "Done" only when tests pass and the change is verified end-to-end and committed.

## Performance target

- TTS throughput must stay at or above **180 000 characters per second**. Measure
  before and after any change to the numeral, unit, date, or preprocess stages:

  ```
  uv run python scripts/benchmark.py --real-only --mode tts --samples 1 --warmups 1 --prefix-chars 250000 --book benchmarks/corpus/03_karamzin_history_of_russian_state.txt
  ```

- A change that drops throughput is not "Done" until the loss is recovered or the
  user has explicitly accepted it. Record every measurement in
  `docs/SPEED_OBSERVATIONS.md` with the commit it was taken on.
- Measure only on an idle machine: a background build stole two thirds of the
  throughput in the August 2026 measurements. Check for foreign CPU consumers
  first, then measure. See [speed regression](docs/agents/speed-regression-2026-08.md).

## Error handling

- Error handling is mandatory, not optional: every operation that can fail at runtime (network calls, external APIs, DB, filesystem, subprocesses) must handle failure explicitly — never leave a bare call whose error crashes the app or disappears silently.
- Retry transient failures (network, 5xx, 429, timeouts) with bounded exponential backoff; no retries for deterministic 4xx/logic errors.
- Keep it proportional — don't wrap every line in try/catch; handle errors at the boundary where you can actually act on them.

# Implementation plans

- Implementation plans live in `docs/agents/plans/` — create them via the `make-plan` skill, implement via `implement-plan`; those skills define the file format and `Status:` line rules.

# Gotchas and observations

Record important observations from your work (results of long test runs, API behavior, environment quirks, etc.) as `docs/agents/<topic>.md` files, each listed in `docs/agents/README.md` with a short two-sentence description.

AGENTS.md gotchas are for CRITICAL facts only — the kind that break production or silently corrupt work. Everything less important lives in `docs/agents/`. Add one only if both are true:
1. Without it, the next agent will make a concrete mistake.
2. It cannot be learned from the code the agent will read anyway. 

One fact per bullet, max two lines; details go to `docs/agents/<topic>.md` with a link. 
Never add bullets to AGENTS.md on your own — propose the wording and get the user's explicit approval first; if you hesitate whether it's important enough, it isn't.

## Gotchas:
- Delete Gotchas that are no longer true or are now covered by a test.
- Mixed-case SI symbols must use the exact-case resolver; see
  [case-sensitive units](docs/agents/case-sensitive-units.md).
- Numeral context and dotted-unit boundary checks must stay linear; see
  [performance invariants](docs/agents/performance-invariants.md).
- Cached numeral rendering must canonicalize pymorphy grammemes before lookup;
  see [numeral cache grammemes](docs/agents/numeral-cache-grammemes.md).
- Keep reference, range, unit, and letter-name outputs aligned with
  [normalization conventions](docs/agents/conventions.md).
- Only `protect_negative_numbers` may decide that `-` is a minus; a bare `-` in
  a numerals regex eats hyphens, see [unary minus](docs/agents/negative-numbers.md).
- Every defect you discover and do not fix MUST immediately get an `xfail(strict=True)`
  test in `tests/test_known_gaps.py`, using a full realistic sentence, never isolated words or a short phrase.
- CI's Windows cell is cp1252 and the dev machine is cp1251, so locale-encoding
  bugs pass locally — always pass `encoding="utf-8"`, see
  [locale encoding](docs/agents/locale-encoding.md).
