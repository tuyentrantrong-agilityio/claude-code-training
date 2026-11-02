"""Check that the test matrix of a kickoff matches the tests that really exist.

Usage: python scripts/check_matrix.py intent/<folder>

A ticket counts as built once `<folder>/evidence/T-NN/` exists (the build saves its
evidence there). For every matrix row of a built ticket, the Planned test
`<path>::test_<name>` must name a file under the repo root that defines that test
function. Rows of tickets not built yet are listed, not checked.

Prints one `<row>: <problem>` line per problem and exits 1 if there are any.
Standard library only, so CI can run it with plain python.
"""

import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lint_tickets import matrix_rows  # noqa: E402

PLANNED = re.compile(r"`?([\w./-]+\.py)::(test_\w+)`?")


def test_names(path, cache):
    """Names of every test function defined in a file (module level or in classes)."""
    if path not in cache:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        cache[path] = {
            node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_")
        }
    return cache[path]


def check(folder):
    """Return (problems, summary lines)."""
    root = folder.resolve().parent.parent
    matrix = folder / "test-matrix.md"
    if not matrix.exists():
        return [f"{matrix.name}: missing"], []
    built = {p.name for p in (folder / "evidence").glob("T-*") if p.is_dir()}
    problems, counts, cache = [], {}, {}
    for row in matrix_rows(matrix):
        rid, ticket, planned = row[0], row[1], row[7]
        done = counts.setdefault(ticket, [0, 0])
        done[1] += 1
        if ticket not in built:
            continue
        match = PLANNED.fullmatch(planned)
        if not match:
            problems.append(f"{rid}: planned test {planned!r} is not '<path>::test_<name>'")
            continue
        path, name = root / match.group(1), match.group(2)
        if not path.is_file():
            problems.append(f"{rid}: {match.group(1)} does not exist")
        elif name not in test_names(path, cache):
            problems.append(f"{rid}: {match.group(1)} has no {name}")
        else:
            done[0] += 1
    summary = [
        f"{ticket}: {ok}/{total} rows have their test" if ticket in built else f"{ticket}: not built yet ({total} rows)"
        for ticket, (ok, total) in sorted(counts.items())
    ]
    return problems, summary


def main(argv):
    if len(argv) != 1:
        print("usage: python scripts/check_matrix.py intent/<folder>", file=sys.stderr)
        return 2
    folder = Path(argv[0])
    if not folder.is_dir():
        print(f"no such folder: {folder}", file=sys.stderr)
        return 2
    problems, summary = check(folder)
    for line in summary + problems:
        print(line)
    if not problems:
        print(f"OK: {folder}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
