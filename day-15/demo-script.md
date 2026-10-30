# Demo script: bid standing (10 minutes)

Flow: ticket -> plan -> MR -> review -> test -> artifact -> shipped.
Practice version. Edit the wording to your own.

## 1. Ticket (1 min)

Say: The client wanted bidders to see if they are winning. I turned the brief
into an intake, a spec and four tickets (T1 to T4) with Given/When/Then
criteria, plus a test matrix (TC1 to TC23). Open questions (Q6 inactive bids,
Q8 labels, last-view storage) were written in the ticket and answered by BA.

Likely question: How did you know the ticket was clear enough to code?
Answer: Every criterion is testable, and each open question has a recorded
decision ("Decisions" and "BA reply" sections), so I did not guess silently.

## 2. Plan (1 min)

Say: Day 13 used plan mode first. Two tickets, two worktrees, one MR each:
the atomic bid check (race) and the HTML markup tests. The plan listed the
verification steps before any code was written.

Likely question: Why plan first?
Answer: The race fix changes the core insert. I wanted the approach and the
checks agreed before touching it, and parallel work needed non-overlapping files.

## 3. MR (1 min)

Say: One MR per ticket into practice, created with push options, never pushing
to main or practice directly. MRs !15 to !22 are all merged into practice.

Likely question: Why so many small MRs?
Answer: Small MRs are easy to review and to revert. Each one maps to one ticket
or one set of review findings.

## 4. Review (2 min)

Say: I used /code-review and ultrareview on the work. Findings fixed in MRs
!20, !21, !22: the false outbid banner on first load, cancelled bids raising
the banner (now standing is null), cursor and input validation, and seven
bypasses in the safety hook.

Likely question: What did review catch that tests did not?
Answer: The false banner was found in a real browser, and the hook bypasses
were found by ultrareview. Tests alone did not show either.

Likely question: What is still open?
Answer: Standing is computed per bid with a per-bid query and no index; the
banner only checks the first 100 bids and shows once. Not required for this
release, tracked as retro items.

## 5. Test (2 min)

Say: Unit tests for standing, a race test with 20 threads on a file database
(it fails on the old place_bid), server tests, markup tests for the HTML, and
hook tests. Run with:

    cd day-02 && python -m unittest discover -s tests -t . -v
    cd day-11 && python -m unittest discover -s tests -t . -v

Likely question: Is the JavaScript tested?
Answer: No. Only the markup is tested (stdlib only, no JS runner). The banner
logic was checked by hand in Chrome and recorded in ticket-T4.md.

## 6. Artifact (1 min)

Honest status: there is no separate artifact yet. The deliverables are the
ticket pack in day-12, the code, and the MR history. If asked, say this is a
known gap and name what would count: a short release note or a screenshot of
the Standing column.

## 7. Shipped (2 min)

Say: practice was merged into main with MR !23, then tagged v0.1.0 on main.
The "deploy" is a local run, since there is no real hosting:

    cd day-11 && python -c "from webapp.server import make_server; make_server(8010).serve_forever()"

Then open http://127.0.0.1:8010/ (the default `python -m webapp.server` uses
port 8000, which may be taken).

Likely question: Is it really deployed?
Answer: No. It runs locally only; there is no hosting and CI/CD is disabled by
the admin. v0.1.0 is a git tag, not a live service.
