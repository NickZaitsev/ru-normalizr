---
name: implement-plan
description: Implement an existing plan from docs/agents/plans/. Use when the user asks to implement, execute, resume, or continue a plan, or references a plan file — the plan's Status line must be updated on completion.
---

**Languages:** all edits to the plan file are in English (like the plan itself). ALL communication with the user — questions, discrepancy reports, the final report — is in Russian.

## Process

1. **Locate and read the whole plan.** If the user didn't name a file, list plans in `docs/agents/plans/` with status `plan` / `in progress` and ask **in Russian** which one to implement. If the plan's status is `implemented` or `rejected`, stop and confirm with the user before proceeding.
2. **Mark the plan started:** set `Status: in progress since YYYY-MM-DD.`.
3. **Implement step by step** in the plan's order, committing per phase (atomic conventional commits per repo rules).
4. **Test as you go, but don't over-test.** Run the plan's checks per stage, BUT skip a stage's test run when a later plan stage will exercise the same code anyway — speed matters; one honest end-to-end verification at the end (plan's "Testing & verification" section + repo lint/type-check/test rules) is mandatory and cannot be skipped.
5. **After each large stage (or a few small ones)**, compact the context yourself if your harness lets you trigger compaction. Stage boundaries are where compacting loses the least.
6. **Close the plan** — this is part of "Done":
   - Update the status line: `Status: implemented YYYY-MM-DD in branch \`<branch>\`.` (add short caveats if something was skipped).
   - Correct any sections where the implementation diverged — the plan must not lie about what was built.
   - Commit the plan update (may be folded into the final feature commit).
7. **Report to the user in Russian — a TL;DR, not a wall of text:** a few short bullets covering what was built, any divergences from the plan, and how it was verified. Details stay in the plan file and commits; expand only if the user asks.

If some change doesn't make sense or wrong, let the user know.

## Don't execute a broken step

No dedicated verification pass is needed — plans are usually implemented right after being written. But keep your eyes open: if while implementing you see that a plan step is wrong or won't work (relies on code that doesn't exist / behaves differently, contradicts something you've already built, would produce a broken result), do NOT execute it as written. Stop, explain **in Russian** what's wrong and what you propose instead, and agree with the user before continuing.

## Report non-prod-ready code you encounter

If along the way you notice existing code that is clearly not production-ready and genuinely must be fixed (a real hack, silent data loss, security hole — not stylistic nitpicks), don't silently fix it and don't ignore it: mention it to the user (in the final report or immediately if it blocks the plan). Fixing it is a separate decision, not part of this plan.

## Rules

- Work in the current branch; do not create branches unless the user asks.
- If implementation stalls partway, leave an honest `Status: in progress since YYYY-MM-DD, <what's done>.` so the next agent can resume.
