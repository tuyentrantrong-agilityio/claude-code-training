---
paths:
  - "day-*/ticket*.md"
  - "day-*/0*-*.md"
---

# Ticket and planning documents

Applies to tickets (`day-NN/ticket-*.md`) and planning files (`00-client-brief.md`,
`01-intake.md`, `02-spec.md`, `03-test-matrix.md`).

## Ticket shape

```markdown
# T1: <short title>

**Component:** <file and function>
**Spec:** 02-spec.md, behaviour <n>

## Story

As a <user>, I want <goal>, so that <reason>.

## Acceptance criteria

- Given <state>, when <action>, then <observable result>.

## Open questions

- Q<n> (<who must answer>): <question>

## Dev questions (write here)

(none yet)
```

## Rules

- Every criterion is testable: a "then" names something a test or a user can see
  (a value, a status code, a message, a row). "Works correctly" is not a "then".
- Use concrete data (`user 42 bid 100 on auction 7`), not placeholders.
- Include at least one unhappy path per ticket (rejected input, empty state, error).
- Use the terms in `CONTEXT.md`. Add a new term there before using it.
- Never answer a question by guessing in code. Write it under "Dev questions" and,
  once decided, add a "Decisions" section naming who decided and why.
- Never delete a question or a decision; later sections ("BA reply", "Review
  change") are appended, so the history stays readable.
- No `TBD`, `TODO` or `???`.
