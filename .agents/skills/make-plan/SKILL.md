---
name: make-plan
description: Create an implementation plan for any task — feature, refactor, migration, fix — and save it to docs/agents/plans/. Use when the user asks to plan work, write an implementation plan, or prepare a task spec for claude/codex. (Implementing an existing plan is the implement-plan skill, not this one.)
disable-model-invocation: true
---

Create an implementation plan for the requested work (feature, refactor, migration, fix, infra change — any task), written **in English** (it will be consumed by coding agents — Claude Code / Codex), and save it to `docs/agents/plans/YYYY-MM-DD-<kebab-case-slug>.md` (date = plan creation date, today; it never changes afterwards — the living state is the `Status:` line).

**Languages:** the plan FILE is written in English (it is consumed by coding agents). ALL communication with the user — clarifying questions, decision discussions, the final report — is in Russian.

## Process

1. **Research first.** Read the relevant code before writing anything. The plan must reference real files, functions, and line-level facts of THIS codebase — not generic advice. Verify every claim (paths, function names, existing patterns) against the actual code.
2. **Grill the user before writing the plan.** Interview the user **in Russian** about every open product/architecture decision (storage, flags, UX, defaults, scope cuts) until you reach a shared understanding. Rules of the interview:
   - Walk down each branch of the decision tree, resolving dependencies between decisions one by one — an answer often opens the next fork.
   - For each question, provide your **recommended answer** with a short reason.
   - If a question can be answered by exploring the codebase, explore the codebase instead of asking; the decisions themselves are always the user's.
   - Do not start writing the plan until the interview is finished. Record the answers in the "Approved decisions" section (in English, like the rest of the plan).
3. **Write the plan** (in English) using the structure below.
4. Report the created file path and a short summary of the plan to the user **in Russian**.

## Plan file structure

```markdown
# Plan: <task title>

Status: plan, YYYY-MM-DD.

> Note for agents: this plan is a point-in-time snapshot — its "codebase facts" describe the code as of the date above and may be outdated. Do NOT treat it as current architecture docs; verify every fact against the actual code before relying on it.

## Context
Why this is needed; current behavior; constraints. Relevant external services/APIs with exact endpoints and costs if any.

## Approved decisions
Numbered list of decisions confirmed with the user (flags, defaults, style, storage, scope cuts).

## Key codebase facts
Bullet list of concrete facts an implementing agent needs: file paths, existing patterns to follow, schemas, auth conventions, gotchas. Only verified facts.

## Implementation
Numbered/step-by-step sections (0., 1., 2., …), each naming the exact files to create or modify and what goes in them. Include function signatures, env vars, error-handling and retry policy where relevant.

## Testing & verification
What tests to add/update, what to run, and how to verify end-to-end. Never call paid external APIs from tests.

## Out of scope
What is deliberately NOT done (prevents scope creep).

---
**Maintenance note (for the implementing agent):** when this plan is implemented, update the `Status:` line above, e.g. `Status: implemented YYYY-MM-DD in branch `feat/<name>``. If the plan changes during implementation, update the affected sections too — the plan must not lie about what was built.
```

## Status line rules

- New plan: `Status: plan, YYYY-MM-DD.`
- After implementation: `Status: implemented YYYY-MM-DD in branch \`<branch>\`.` (add short caveats if something was skipped, e.g. "frontend verification skipped per user request").
- Partially done: `Status: in progress since YYYY-MM-DD, <what's done>.`
- Abandoned: `Status: rejected YYYY-MM-DD — <reason>.`

Use today's real date. The status line is always line 3 of the file (right under the H1) so it's visible at a glance.

## Rules

- One plan = one file; do not mix several unrelated tasks.
- The plan must be self-contained: an agent with no chat history should be able to implement it.
- Don't include code dumps; include signatures, paths, and behavior contracts instead.
- Commit the plan file after creating it (`docs: ...` conventional commit, description in Russian per repo rules).
