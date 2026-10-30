# Day 02 — Git practice (branch `practice`)

"Remote" commits were made from a second clone (`remote-sim`) and pushed to `origin/day-2`, to simulate a teammate.

> The branch was named `day-2` when these outputs were recorded and was later renamed to `practice`, so the command output below still says `day-2`.

## 1. `git pull --rebase`: a local commit plus a new remote commit

```text
# Remote (second clone): d1390a5 Add notes section (remote side)   -> pushed
# Local:                 d0c4391 Note how to run tests (local side)

$ git fetch && git diff --stat HEAD origin/day-2
 day-02/README.md         | 4 ++++     <- remote has this change, local doesn't
 day-02/tests/__init__.py | 2 --       <- local has this change, remote doesn't
```

`git diff HEAD origin/day-2` shows the difference between the two *trees*, so a change that exists only locally shows up as `-`.

```text
$ git pull --rebase
Rebasing (1/1)Successfully rebased and updated refs/heads/day-2.

$ git log --oneline --graph
* dc42f09 Note how to run tests (local side)     <- was d0c4391, new hash after rebase
* d1390a5 Add notes section (remote side)
* 4e9d37c Day 02: ticket analysis, bug repro with failing test
* f327d4b Initial commit
```

**What I read from the output:** history stays linear (no merge commit). The local commit is "replayed" on top of the remote commit, so its **hash changes**. That's why you should never rebase a commit that someone else has already pulled.

## 2. Merge conflict #1: both sides edit the same line

Both sides changed the `Status:` line in `day-02/README.md`:

- Remote `456263b`: `Status: bug reproduced, failing test added`
- Local `dd400d3`: `Status: tickets analysed, bug reproduced, git practice done`

```text
$ git pull --rebase
CONFLICT (content): Merge conflict in day-02/README.md
error: could not apply dd400d3... Update status (local side)

$ git status --short
UU day-02/README.md

<<<<<<< HEAD
Status: bug reproduced, failing test added                    <- REMOTE (upstream)
=======
Status: tickets analysed, bug reproduced, git practice done   <- LOCAL commit being replayed
>>>>>>> dd400d3 (Update status (local side))
```

**Note:** during a **rebase**, `HEAD` / "ours" is the **upstream** branch and "theirs" is **your own commit**, the reverse of `git merge`.

Resolution: combine the information from both sides, then:

```text
$ git diff                      # combined diff (diff --cc) shows both parents
- Status: bug reproduced, failing test added
 -Status: tickets analysed, bug reproduced, git practice done
++Status: tickets analysed, bug reproduced + failing test added, git practice done

$ git add day-02/README.md
$ git rebase --continue
Successfully rebased and updated refs/heads/day-2.

$ git log --oneline --graph
* baf2894 Update status (local side)
* 456263b Update status (remote side)
* dc42f09 Note how to run tests (local side)
* d1390a5 Add notes section (remote side)
* 4e9d37c Day 02: ticket analysis, bug repro with failing test
* f327d4b Initial commit
```

Escape hatch if something goes wrong mid-way: `git rebase --abort` returns to the state before the pull.
