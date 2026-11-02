# Hook proof

Produced by `python scripts/hook_proof.py`: each real hook script is run on a sample
payload. Exit code 2 or a deny decision means the hook blocked the action.

## block_forbidden.py: PreToolUse Bash: force push

- Exit code: 2
- Output:

```
Blocked by .claude/hooks/block_forbidden.py: force push is forbidden
```

## block_forbidden.py: PreToolUse Bash: push to practice

- Exit code: 2
- Output:

```
Blocked by .claude/hooks/block_forbidden.py: push to main or practice is forbidden; push a feature branch and open a pull request
```

## block_forbidden.py: PreToolUse Bash: harmless command

- Exit code: 0
- Output:

```
(no output)
```

## block_secrets.py: PreToolUse Write: .env file

- Exit code: 2
- Output:

```
Blocked by block_secrets: writing an .env file is forbidden (use .env.example without values)
```

## gate_guard.py: PreToolUse Bash: new issue before Gate 3

- Exit code: 2
- Output:

```
Blocked by kickoff policy: issues are created only after Gate 3. Ask the user to review 2026-11-02-cancel-bid and type `approve gate 3`.
```

## path_guard.py: PreToolUse Write: approval file

- Exit code: 0
- Output:

```
{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "Kickoff policy: approval files are written only when the user types `approve gate N`."}}
```

## record_approval.py: UserPromptSubmit: 'ok' is not an approval

- Exit code: 0
- Output:

```
(no output)
```

