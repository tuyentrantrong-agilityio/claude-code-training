"""PreToolUse hook for Bash and PowerShell: block commands that CLAUDE.md forbids.

Reads the hook input as JSON on stdin. Exit code 2 blocks the command and
sends the message on stderr back to Claude; exit code 0 lets it run.
The hook fails closed: if it cannot read the input or parse the command,
it blocks and says why.
"""

import json
import re
import shlex
import subprocess
import sys

PROTECTED = {"main", "practice"}
SEPARATORS = {";", "&&", "||", "|", "&", "\n"}
RM_ALIASES = {"rm", "ri", "del", "erase", "rd", "rmdir", "remove-item"}
HEREDOC = re.compile(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n\s*\2\s*(?=\n|$)", re.DOTALL)


class Blocked(Exception):
    pass


def split_commands(command):
    """Split a command line into a list of token lists, one per chained command."""
    # Heredoc bodies are text (commit or MR messages), not commands.
    command = HEREDOC.sub("", command)
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    commands, current = [], []
    for token in lexer:
        if token in SEPARATORS:
            if current:
                commands.append(current)
            current = []
        else:
            current.append(token)
    if current:
        commands.append(current)
    return commands


def short_flags(args):
    """Letters from bundled short flags, e.g. -fu gives {'f', 'u'}."""
    letters = set()
    for arg in args:
        if re.fullmatch(r"-[A-Za-z]+", arg):
            letters.update(arg[1:])
    return letters


def current_branch(cwd):
    try:
        out = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd,
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def check_git_push(args, cwd):
    if "f" in short_flags(args) or any(a.startswith("--force") for a in args):
        raise Blocked("force push is forbidden")
    if "--no-verify" in args:
        raise Blocked("skipping hooks with --no-verify is forbidden")
    positional = [a for a in args if not a.startswith("-")]
    # Drop values that belong to options such as -o <value>.
    for i, a in enumerate(args[:-1]):
        if a in ("-o", "--push-option", "--repo") and args[i + 1] in positional:
            positional.remove(args[i + 1])
    refspecs = positional[1:]
    for spec in refspecs:
        if spec.startswith("+"):
            raise Blocked("force push with a +refspec is forbidden")
        target = spec.split(":", 1)[-1]
        if target.removeprefix("refs/heads/") in PROTECTED:
            raise Blocked("push to main or practice is forbidden; push a feature branch and open a merge request")
    if not refspecs and current_branch(cwd) in PROTECTED:
        raise Blocked("plain git push while on main or practice is forbidden")


def check_git_commit(args):
    if "--no-verify" in args or "n" in short_flags(args):
        raise Blocked("skipping hooks with --no-verify or -n is forbidden")


def check_unix_rm(args):
    flags = short_flags(args)
    recursive = "r" in flags or "R" in flags or "--recursive" in args
    force = "f" in flags or "--force" in args
    if recursive and force:
        raise Blocked("rm -rf is forbidden; delete specific files instead")


def check_powershell_remove(args):
    lowered = [a.lower() for a in args]
    # PowerShell accepts unambiguous prefixes: -r / -rec for -Recurse, -fo for -Force.
    recursive = any(re.fullmatch(r"-r(e(c(u(r(se?)?)?)?)?)?", a) for a in lowered)
    force = any(re.fullmatch(r"-fo(r(ce?)?)?", a) for a in lowered)
    if recursive and force:
        raise Blocked("recursive forced delete is forbidden; delete specific files instead")


def check_tokens(tokens, cwd):
    name = tokens[0].lower()
    args = tokens[1:]
    if name == "git":
        # Skip global options such as -C <dir> or -c <key=value> before the subcommand.
        while args and args[0].startswith("-"):
            args = args[2:] if args[0] in ("-C", "-c") else args[1:]
    if name == "git" and args:
        sub, rest = args[0], args[1:]
        if sub == "push":
            check_git_push(rest, cwd)
        elif sub == "commit":
            check_git_commit(rest)
    elif name in RM_ALIASES:
        check_unix_rm(args)
        check_powershell_remove(args)


def check(command, cwd=None):
    """Return the reason a command is forbidden, or None if it may run."""
    try:
        commands = split_commands(command)
    except ValueError as exc:
        return f"could not parse the command ({exc}); rewrite it without unbalanced quotes"
    try:
        for tokens in commands:
            check_tokens(tokens, cwd)
    except Blocked as exc:
        return str(exc)
    return None


def main():
    try:
        data = json.load(sys.stdin)
        tool_input = data.get("tool_input") or {}
        command = tool_input.get("command") or ""
        reason = check(command, data.get("cwd"))
    except Exception as exc:
        reason = f"hook could not read its input ({exc.__class__.__name__})"
    if reason:
        print(f"Blocked by .claude/hooks/block_forbidden.py: {reason}", file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
