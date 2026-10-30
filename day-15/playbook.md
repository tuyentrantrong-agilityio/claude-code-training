# How I work with Claude (draft, edit to your own words)

## Before coding
- Turn the brief into a ticket with Given/When/Then and write open questions
  down. Do not let Claude guess silently; record each decision in the ticket.
- For anything that touches core logic, use plan mode first and agree the
  verification steps before code.

## While coding
- One ticket, one branch, one MR into practice. Small MRs are easy to review.
- Use worktrees when two tickets touch different files.
- Stdlib only. Do not change a test to make it pass; fix the code unless the
  test is wrong.

## Checking the work
- Run the tests myself; do not trust a "done" message.
- Use /code-review for bugs and a real browser for UI. The false outbid banner
  was found only in Chrome.
- Ultrareview found hook bypasses that tests missed, but its free runs are
  limited, so use it on high-risk changes only.

## Limits I keep
- Claude does not commit or push unless I ask, never to main or practice
  directly, and never force pushes.
- Anything that writes to GitLab (MRs, tags) needs my yes first.
- Hooks are a guardrail, not a sandbox.

## Mistakes to avoid next time
- Do not claim "shipped" before merge, tag and run are all done.
- Keep a list of known gaps (JS untested, no real deploy, no artifact) and say
  them out loud in the demo.
