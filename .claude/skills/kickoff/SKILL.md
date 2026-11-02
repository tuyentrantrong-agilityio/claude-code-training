---
name: kickoff
description: Runs the feature kickoff pipeline (lead, ba, qa, dev agents) one stage per call, stopping at the user's three gates. Use when the user types /kickoff, says "next stage", or approves a gate with "approve gate N".
---

# Kickoff

Turns a client's vague feature request into a ticket pack a developer can build
without blocking questions. Four subagents do the work: `lead`, `ba`, `qa`, `dev`
(`.claude/agents/`). You are the orchestrator: you run stages, pass file paths and
stop at gates. You never write the brief, intake, spec, tickets or matrix yourself.

**One call = one stage.** Read the state, run the next stage, update the state,
stop, and tell the user what to look at. The only exception is the stage right
after a gate approval (see "Gates").

## State

- `intent/CURRENT`: one line, the active folder (`intent/2026-11-03-auction-end-time`).
  Missing means no kickoff yet.
- `<folder>/state.md`:

  ```markdown
  # Kickoff state

  next: intake
  gate: none
  dev_rounds: T-01=1, T-02=2

  ## Log
  - 2026-11-03 10:02 brief: "Auction end time" (lead)
  ```

  `next` is one of `brief`, `intake`, `answers`, `pack`, `dev-round`, `promote`,
  `reveal`, `done`. `gate` is `none` or the gate number that must be approved first.
- `<folder>/approvals/gate-N.md`: written **only** by the `record_approval` hook when
  the user types `approve gate N`. You never create, edit or delete these files; a
  hook and a permission rule block it anyway.

## Each call

1. Read `intent/CURRENT` and `state.md`. Missing means `next: brief`.
2. If `gate` is a number and `approvals/gate-<gate>.md` does not exist:
   - If the user's message has questions or changes, re-run the stage before the gate
     with those notes passed word for word (Gate 1: BA `intake`; Gate 2: BA `pack`
     and/or QA; Gate 3: BA `dev-round` on the named tickets). Stop at the same gate.
   - Otherwise remind them what is waiting and how to approve, and stop.
3. Run the `next` stage, append a log line, update `next` and `gate`, stop with the
   stage's message.

Lint: `python scripts/lint_tickets.py <folder>`. Score: `python scripts/score_kickoff.py <folder>`.

## Stages

### `brief`
Spawn `lead` with `Stage brief. Today is <YYYY-MM-DD>.` It replies with the feature
name and folder. Write the folder to `intent/CURRENT`, create `state.md` with
`next: intake`, `gate: none`. Tell the user the brief is in `<folder>/brief.md` and
that the client's private notes are in `.kickoff-private/` (agents cannot read them;
the user may). Do not quote the client truth.

### `intake`
Spawn `ba` with `Stage intake. Folder: <folder>.` Run the linter; on intake errors
send them back to `ba` once. Set `next: answers`, `gate: 1`.
Tell the user: **Gate 1**, review the open questions in `intake.md`; reply with
changes, or type `approve gate 1`.

### `answers`
Spawn `lead` with `Stage answers. Folder: <folder>.` Run the linter with `--answered`.
Set `next: pack`, `gate: none`. Tell the user how many answers came back.

### `pack`
1. Spawn `ba` with `Stage pack. Folder: <folder>.`
2. Spawn `qa` with `Folder: <folder>.`
3. Run the linter. Send ticket errors to `ba` and matrix errors to `qa`, then lint
   again, at most twice.

Set `next: dev-round`, `gate: 2`. Tell the user: **Gate 2**, review `spec.md`,
`tickets/` and `test-matrix.md` (list the tickets and how many QA questions each got);
reply with changes, or type `approve gate 2`.

### `dev-round`
Repeat up to 3 iterations while some ticket is not ready:

1. For every ticket with `Status: draft` and fewer than 3 rounds: bump its round `n`
   in `dev_rounds` and its `Dev rounds: n` line. Spawn a **fresh** `dev` per ticket,
   in parallel, with `Ticket: <path>. Iteration: <n>.` Never resume an earlier Dev
   agent: one that remembers earlier answers would fake a clean read.
2. Append each Dev's lines to that ticket's `## Questions` exactly as returned
   (replacing `- None yet.`). For `NO QUESTIONS`, append nothing.
3. For each ticket of this round (open questions or `NO QUESTIONS`), spawn `ba` with
   `Stage dev-round. Folder: <folder>. Ticket: <path>. Iteration: <n>.`, one at a time.
   The BA closes the questions and sets `ready` only if this round raised no `[B]`;
   a ticket whose round raised a `[B]` stays draft and gets the next round. The linter
   (and `lint_on_stop`) refuses `ready` right after a Dev `[B]`.
4. If the BA added `## Questions for the client (dev round)` to `intake.md`, spawn
   `lead` (`Stage answers. Folder: <folder>.`), then `ba` again for those tickets.

Then run the scorer. Set `next: promote`, `gate: 3`. Tell the user: **Gate 3**, the
scorecard summary and which tickets will become GitHub issues; type `approve gate 3`.

### `promote`
For each ready ticket (plus any the user named), in order, create a GitHub issue in
`tuyentrantrong-agilityio/claude-code-training`: title = the ticket H1 without `#`,
body = the ticket content plus a line linking `<folder>/spec.md`, assigned to the user.
Use the GitHub MCP tools if they are available, else
`gh issue create --title ... --body-file <ticket> --assignee @me`
(the `gate_guard` hook blocks both before Gate 3). Add `Issue: #<n>` under each ticket's `Status:`.
Set `next: reveal`, `gate: none`.

### `reveal`
1. Move `.kickoff-private/client-truth.md` to `<folder>/client-truth.md`.
2. Write `<folder>/recall.md`:

   ```markdown
   # Recall

   | H | Requirement | Hidden | Covered by | Verdict |
   |---|---|---|---|---|
   | H1 | ... | no | T-01 S2 | covered |
   ```

   Verdict is `covered`, `partial` or `missed`. Items under `## Added during answers`
   are H rows too, with Hidden `added`.
3. Run the scorer and show the recall line, the contradiction line and every
   `partial` or `missed` row. The verdicts are your judgement; the user has the final
   say. Apply their corrections and run the scorer again.

Set `next: done`. Suggest committing the folder on a `docs/kickoff-<slug>` branch and
opening a pull request into `practice`.

### `done`
Say the kickoff is finished. Start a new one only if the user asks (`/kickoff new`).

## Gates

When the `record_approval` hook reports an approval, continue straight into the
stage the gate was holding, in the same turn. "ok", "looks good" or "go ahead" are
**not** approvals: answer with the exact phrase to type.

## Rules

- Pass agents file paths, never pasted file content.
- Never summarise the brief, intake or answers to the BA, QA or Dev; they read files.
- Before `reveal`, never read or quote the client truth.
- If a subagent fails or returns something off-format, retry it once with the
  error; then stop and tell the user.
