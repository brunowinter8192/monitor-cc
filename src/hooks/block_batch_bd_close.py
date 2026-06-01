# INFRASTRUCTURE
import json
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _fire_log import log_fire

# Split command into statements at shell chain operators
_STMT_SEP_RE = re.compile(r'&&|\|\||[;|\n]')

# Bead-id token: letter, then word-chars, then dash, then word/dot chars (e.g. Monitor_CC-lhf, tqm-axt.1.24)
_BEAD_ID_RE = re.compile(r'^[A-Za-z]\w*-[\w.]+$')

# READ-ONLY subcommands — contribute 0 mutation units
_READ_ONLY = frozenset({
    'list', 'show', 'search', 'count', 'status', 'types',
    'graph', 'history', 'diff', 'stale', 'lint', 'ready',
    'export', 'backup', 'state', 'version', 'help',
})

# id-list mutators: count positional bead-id arguments; min 1 unit per invocation (no-id = last-touched)
_ID_LIST_MUTATORS = frozenset({'close', 'done', 'reopen', 'update'})

# Value-taking flags for id-list mutators: next token (or embedded =value) is a value, not a bead-id
_VALUE_FLAGS = frozenset({
    '-r', '--reason', '--reason-file', '--session',
    '-C', '--directory', '--db', '--actor', '--dolt-auto-commit',
    '-p', '--priority', '-t', '--type', '-s', '--status',
    '--assignee', '--label',
})

_BLOCK_MESSAGE = (
    "Batched bd mutations silently revert — dolt auto-import clobbers all writes after the first. "
    "Run ONE mutating bd command per Bash invocation; reads (list/show/export) are unaffected.\n"
)

# ORCHESTRATOR

# Read Bash tool_input; exit 2 + stderr if command contains more than 1 bd mutation unit
def block_batch_bd_close_workflow() -> None:
    command, session_id = _parse_command()
    if command is None:
        sys.exit(0)
    stripped = _strip_quoted(command)
    units = _count_mutation_units(stripped)
    if units > 1:
        print(_BLOCK_MESSAGE, file=sys.stderr, end="")
        log_fire("block_batch_bd_close", "block", "Bash", command, reason=_BLOCK_MESSAGE, session_id=session_id)
        sys.exit(2)
    sys.exit(0)

# FUNCTIONS

# Parse stdin JSON; return (command, session_id); (None, None) on any error (fail-open)
def _parse_command():
    try:
        payload = json.loads(sys.stdin.read())
        cmd = payload.get("tool_input", {}).get("command")
        return (cmd if isinstance(cmd, str) else None), payload.get("session_id")
    except Exception:
        return None, None

# Strip content inside single/double quotes so quoted bd examples cannot trigger matches
def _strip_quoted(s: str) -> str:
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c in ("'", '"'):
            quote, i = c, i + 1
            while i < n and s[i] != quote:
                if s[i] == "\\" and i + 1 < n:
                    i += 2
                else:
                    i += 1
            i += 1
        else:
            out.append(c)
            i += 1
    return "".join(out)

# Count total mutation units across all bd invocations in the quote-stripped command
def _count_mutation_units(stripped: str) -> int:
    total = 0
    for stmt in _STMT_SEP_RE.split(stripped):
        tokens = stmt.split()
        if len(tokens) < 2 or tokens[0] != 'bd':
            continue
        sub = tokens[1]
        rest = tokens[2:]

        # Flag-only forms (bd --help, bd -h): treat as read-only
        if sub.startswith('-'):
            continue

        if sub in _READ_ONLY:
            continue

        if sub == 'comments':
            if rest and rest[0] == 'add':
                total += 1
            # else: view form → 0

        elif sub == 'dep':
            if rest and rest[0] in ('add', 'remove'):
                total += 1
            # else: list form → 0

        elif sub in ('find-duplicates', 'duplicates'):
            if '--merge' in rest:
                total += 1
            # else: find form → 0

        elif sub in _ID_LIST_MUTATORS:
            total += max(1, _count_ids(rest))

        else:
            # create, set-state, todo, import, restore, supersede, duplicate, set-metadata,
            # label, epic, swarm, branch, federation, vc, unknown → 1 unit each
            total += 1

    return total

# Count bead-id positional args in args list; skip flags and values of value-taking flags
def _count_ids(args: list) -> int:
    count = 0
    skip_next = False
    for token in args:
        if skip_next:
            skip_next = False
            continue
        if token.startswith('-'):
            if '=' not in token and token in _VALUE_FLAGS:
                skip_next = True
            # Flag token: never a bead-id
        elif _BEAD_ID_RE.match(token):
            count += 1
        # else: non-id positional (redirect target, plain word) → skip
    return count


if __name__ == "__main__":
    block_batch_bd_close_workflow()
