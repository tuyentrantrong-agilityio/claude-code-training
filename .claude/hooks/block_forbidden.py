"""PreToolUse hook for Bash and PowerShell: block commands that CLAUDE.md forbids.

Reads the hook input as JSON on stdin. Exit code 2 blocks the command and
sends the message on stderr back to Claude; exit code 0 lets it run.
The hook fails closed: if it cannot read the input or parse the command,
it blocks and says why.

This is a guardrail against mistakes, not a sandbox: it does not try to
catch commands hidden inside scripts or interpreter code.
"""

import base64
import json
import ntpath
import posixpath
import re
import shlex
import subprocess
import sys

PROTECTED = {"main", "practice"}
OPERATOR_CHARS = set(";&|\n()")
RM_ALIASES = {"rm", "ri", "del", "erase", "rd", "rmdir", "remove-item"}
WRAPPERS = {"sudo", "doas", "env", "command", "nohup", "time", "exec", "xargs",
            "timeout", "nice", "stdbuf", "ionice", "setsid"}
# Wrapper options that take a separate value, which must be skipped as well.
WRAPPER_VALUE_OPTIONS = {
    "sudo": {"-u", "-g", "-h", "-p", "-C", "-D", "-R", "-T", "-r", "-t", "-U"},
    "doas": {"-u", "-C"},
    "env": {"-u", "-C", "-S", "--unset", "--chdir"},
    "xargs": {"-I", "-L", "-n", "-P", "-s", "-d", "-E", "-a"},
    "time": {"-f", "-o"},
    "timeout": {"-s", "-k", "--signal", "--kill-after"},
    "nice": {"-n"},
    "stdbuf": {"-i", "-o", "-e"},
    "ionice": {"-c", "-n", "-p"},
}
SHELLS = {"bash", "sh", "zsh"}
POWERSHELLS = {"pwsh", "powershell"}
GIT_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace",
                     "--super-prefix", "--config-env"}
# << but not <<< (here-string).
HEREDOC_START = re.compile(r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_]\w*)\1")


class Blocked(Exception):
    pass


def command_name(token):
    """Lowercase base name without directory or .exe, e.g. /bin/rm -> rm."""
    name = ntpath.basename(posixpath.basename(token)).lower()
    return name.removesuffix(".exe")


def in_quotes(text, end):
    """True if position end of text is inside a quoted string."""
    quote, i = "", 0
    while i < end:
        c = text[i]
        if quote == "'":
            if c == "'":
                quote = ""
        elif c == "\\":
            i += 1
        elif quote == '"':
            if c == '"':
                quote = ""
        elif c in "'\"":
            quote = c
        i += 1
    return bool(quote)


def strip_comments(text, escape="\\"):
    """Remove # comments (a # at the start of a word, outside quotes)."""
    out, quote, i = [], "", 0
    while i < len(text):
        c = text[i]
        if quote == "'":
            if c == "'":
                quote = ""
        elif c == escape and i + 1 < len(text):
            out.append(c)
            i += 1
            c = text[i]
        elif quote == '"':
            if c == '"':
                quote = ""
        elif c in "'\"":
            quote = c
        elif c == "#" and (not out or out[-1] in " \t\r\n;&|()"):
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def feeds_shell(rest):
    """True if the rest of a line pipes into a shell, e.g. 'cat <<EOF | bash'."""
    for part in re.split(r"&&|\|\||[;|&(]", rest)[1:]:
        words = part.split()
        if words and command_name(words[0]) in SHELLS | POWERSHELLS:
            return True
    return False


def is_long_option(arg, full):
    """True if arg is full or an abbreviation of it, e.g. --no-veri for --no-verify."""
    if not arg.startswith("--") or len(arg) < 3:
        return False
    return full.startswith(arg.split("=", 1)[0])


def drop_heredoc_bodies(text):
    """Remove heredoc bodies that are plain text (commit or PR messages).

    The rest of the opening line is kept and checked. A body fed to a shell
    (bash <<EOF) is a script, so it is kept and checked too.
    """
    out, pending = [], []
    for line in text.split("\n"):
        if pending:
            delimiter, keep = pending[0]
            if line.strip() == delimiter:
                pending.pop(0)
                continue
            if keep:
                out.append(line)
            continue
        out.append(line)
        for match in HEREDOC_START.finditer(line):
            if in_quotes(line, match.start()):
                continue
            owner = re.split(r"&&|\|\||[;|&(]", line[:match.start()])[-1].split()
            keep = (bool(owner) and command_name(owner[0]) in SHELLS) or feeds_shell(line[match.end():])
            pending.append((match.group(2), keep))
    return "\n".join(out)


def split_commands(command, powershell=False):
    """Split a command line into a list of token lists, one per chained command."""
    if powershell:
        text = command.replace("`\r\n", " ").replace("`\n", " ")
    else:
        text = command.replace("\\\r\n", " ").replace("\\\n", " ")
        text = drop_heredoc_bodies(text)
    text = strip_comments(text, "`" if powershell else "\\")
    lexer = shlex.shlex(text, posix=True, punctuation_chars="();&|\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    # A word that starts with # is a comment; # inside a word is not.
    lexer.commenters = ""
    if powershell:
        lexer.escape = "`"
    commands, current, in_comment = [], [], False
    for token in lexer:
        if token and set(token) <= OPERATOR_CHARS:
            if current:
                commands.append(current)
            current, in_comment = [], False
        elif in_comment or token.startswith("#"):
            in_comment = True
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
        # symbolic-ref also works on a branch with no commits yet.
        out = subprocess.run(["git", "symbolic-ref", "--short", "HEAD"], cwd=cwd,
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def check_git_push(args, cwd):
    if "f" in short_flags(args) or any(
            a.startswith("--force") or is_long_option(a, "--force") for a in args):
        raise Blocked("force push is forbidden")
    if any(is_long_option(a, "--mirror") or is_long_option(a, "--all") for a in args):
        raise Blocked("git push --all or --mirror is forbidden; push one feature branch")
    if any(is_long_option(a, "--no-verify") for a in args):
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
        if target in ("HEAD", "@"):
            target = current_branch(cwd)
        if target.removeprefix("refs/heads/") in PROTECTED:
            raise Blocked("push to main or practice is forbidden; push a feature branch and open a pull request")
    if not refspecs and current_branch(cwd) in PROTECTED:
        raise Blocked("plain git push while on main or practice is forbidden")


def check_git_commit(args):
    if any(is_long_option(a, "--no-verify") for a in args) or "n" in short_flags(args):
        raise Blocked("skipping hooks with --no-verify or -n is forbidden")


def check_unix_rm(args):
    flags = short_flags(args)
    recursive = "r" in flags or "R" in flags or any(is_long_option(a, "--recursive") for a in args)
    force = "f" in flags or any(is_long_option(a, "--force") for a in args)
    if recursive and force:
        raise Blocked("rm -rf is forbidden; delete specific files instead")


def check_powershell_remove(args):
    lowered = [a.lower() for a in args]
    # PowerShell accepts unambiguous prefixes: -r / -rec for -Recurse, -fo for -Force.
    recursive = any(re.fullmatch(r"-r(e(c(u(r(se?)?)?)?)?)?(:\$true)?", a) for a in lowered)
    force = any(re.fullmatch(r"-fo(r(ce?)?)?(:\$true)?", a) for a in lowered)
    if recursive and force:
        raise Blocked("recursive forced delete is forbidden; delete specific files instead")


def check_git_config_option(args):
    """Block inline config that skips hooks or defines aliases (git -c ...)."""
    opt = args[0]
    if opt in ("-c", "--config-env") and len(args) > 1:
        setting = args[1]
    elif opt.startswith("--config-env="):
        setting = opt.split("=", 1)[1]
    elif opt.startswith("-c") and len(opt) > 2:
        setting = opt[2:]
    else:
        return
    key = setting.split("=", 1)[0].lower()
    if key == "core.hookspath" or key.startswith("alias."):
        raise Blocked("git -c core.hooksPath or alias.* is forbidden")


def check_tokens(tokens, cwd, depth):
    # Skip VAR=value prefixes and wrappers such as sudo or env.
    while tokens and (re.fullmatch(r"\w+=.*", tokens[0]) or command_name(tokens[0]) in WRAPPERS):
        wrapper = command_name(tokens[0])
        tokens = tokens[1:]
        while tokens and tokens[0].startswith("-"):
            tokens = tokens[2:] if tokens[0] in WRAPPER_VALUE_OPTIONS.get(wrapper, ()) else tokens[1:]
        if wrapper == "timeout" and tokens:
            tokens = tokens[1:]  # the duration
    if not tokens:
        return
    name, args = command_name(tokens[0]), tokens[1:]

    if name in SHELLS:
        # -c may be bundled with other flags, e.g. -lc or -ec.
        for i, a in enumerate(args[:-1]):
            if re.fullmatch(r"-[A-Za-z]*c[A-Za-z]*", a):
                check_script(args[i + 1], cwd, depth + 1, powershell=False)
    elif name in POWERSHELLS:
        for i, a in enumerate(args[:-1]):
            low = a.lower()
            if re.fullmatch(r"-c(o(m(m(a(nd?)?)?)?)?)?", low):
                check_script(args[i + 1], cwd, depth + 1, powershell=True)
            elif re.fullmatch(r"-e(c|n(c(o(d(e(d(c(o(m(m(a(nd?)?)?)?)?)?)?)?)?)?)?)?)?", low):
                try:
                    script = base64.b64decode(args[i + 1]).decode("utf-16-le")
                except ValueError:
                    raise Blocked("cannot decode the -EncodedCommand value")
                check_script(script, cwd, depth + 1, powershell=True)
    elif name == "git":
        while args and args[0].startswith("-"):
            check_git_config_option(args)
            args = args[2:] if args[0] in GIT_VALUE_OPTIONS else args[1:]
        if args and args[0] == "push":
            check_git_push(args[1:], cwd)
        elif args and args[0] == "commit":
            check_git_commit(args[1:])
    elif name in RM_ALIASES:
        check_unix_rm(args)
        check_powershell_remove(args)


def check_script(command, cwd, depth, powershell):
    if depth > 3:
        raise Blocked("command is nested too deeply to check")
    for tokens in split_commands(command, powershell):
        check_tokens(tokens, cwd, depth)


def check(command, cwd=None, tool="Bash"):
    """Return the reason a command is forbidden, or None if it may run."""
    try:
        check_script(command, cwd, 0, powershell=(tool == "PowerShell"))
    except Blocked as exc:
        return str(exc)
    except ValueError as exc:
        return f"could not parse the command ({exc}); rewrite it without unbalanced quotes"
    return None


def main():
    try:
        data = json.load(sys.stdin)
        tool_input = data.get("tool_input") or {}
        command = tool_input.get("command") or ""
        reason = check(command, data.get("cwd"), data.get("tool_name") or "Bash")
    except Exception as exc:
        reason = f"hook could not read its input ({exc.__class__.__name__})"
    if reason:
        print(f"Blocked by .claude/hooks/block_forbidden.py: {reason}", file=sys.stderr)
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
