# Day 02

Status: bug reproduced, failing test added

| File | Exercise |
|---|---|
| [ticket-analysis.md](ticket-analysis.md) | 1. Ticket analysis: 5 tickets × 3 sentences, plus clarifying questions |
| [bug-report.md](bug-report.md) | 2. Bug reproduction: cursor pagination skips same-ms bids |
| [git-practice.md](git-practice.md) | 3. Git practice: `pull --rebase` and merge conflict |

## Run (Python 3.10+, no dependencies)

```bash
cd day-02
python -m auction.demo                                # reproduce the bug
python -m unittest discover -s tests -t . -v          # 1 test fails on purpose (the bug)
```

## Notes

- Remote-side note added from another clone.
