"""UserPromptSubmit hook: remind Claude of the git rules when a prompt is about git.

Whatever this prints on stdout is added to Claude's context. It prints nothing
for other prompts and always exits 0.
"""

import json
import re
import sys

GIT_WORDS = re.compile(r"\b(commit|push|merge|tag|rebase|branch|mr|pr|merge request|pull request)\b", re.IGNORECASE)

REMINDER = (
    "Git rules from CLAUDE.md: commit message format '<type>: <short description>' "
    "(lowercase, imperative, no period, no AI attribution lines); never push to main or "
    "practice; open a pull request into practice from a fix/, feat/ or docs/ branch with "
    "`gh pr create --base practice`; never force push or skip hooks; GitHub writes "
    "(push, PR, issue, merge) need the user's yes first."
)


def reminder_for(prompt):
    return REMINDER if GIT_WORDS.search(prompt or "") else ""


def main():
    try:
        prompt = json.load(sys.stdin).get("prompt", "")
    except ValueError:
        return 0
    text = reminder_for(prompt)
    if text:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
