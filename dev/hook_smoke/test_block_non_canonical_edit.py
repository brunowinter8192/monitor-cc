# INFRASTRUCTURE
import atexit
import json
import os
import shutil
import sys
import tempfile
from hook_runner import run_hook

HOOK = "src/hooks/block_non_canonical_edit.py.disabled"

_FIXTURE_DIR = tempfile.mkdtemp(prefix="block_non_canonical_edit_smoke_")
atexit.register(shutil.rmtree, _FIXTURE_DIR, True)


def _write_fixture(name: str, content: str) -> str:
    path = os.path.join(_FIXTURE_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


_EXISTING = _write_fixture("existing.txt", "line one\nline two\nline three\n")
_NEW_PATH = os.path.join(_FIXTURE_DIR, "brand_new.txt")

_CANONICAL_FORM = (
    "python3 - <<'LINEEDIT'\n"
    'path = "' + _EXISTING + '"\n'
    "edits = [\n"
    '    (1, 1, "line one", """REPLACED LINE"""),\n'
    "]\n"
    'with open(path, encoding="utf-8") as f:\n'
    '    lines = f.read().split("\\n")\n'
    "for start, end, fp, new in sorted(edits, reverse=True):\n"
    "    got = lines[start - 1].lstrip()[:len(fp)]\n"
    "    if got != fp:\n"
    '        raise SystemExit(f"fingerprint mismatch at line {start}: expected {fp!r}, got {got!r}")\n'
    '    lines[start - 1:end] = new.split("\\n")\n'
    'with open(path, "w", encoding="utf-8") as f:\n'
    '    f.write("\\n".join(lines))\n'
    "LINEEDIT"
)

_WRONG_DELIM_FORM = _CANONICAL_FORM.replace("LINEEDIT", "PY")

CASES = [
    ("sed -i on existing file BLOCK",
     f"sed -i '' '1s/.*/X/' {_EXISTING}", 2),
    ("perl -pi on existing file BLOCK",
     f"perl -pi -e 's/one/1/' {_EXISTING}", 2),
    ("gawk -i inplace on existing file BLOCK",
     f"gawk -i inplace '{{print}}' {_EXISTING}", 2),
    ("python open() mode r+ on existing file BLOCK",
     f"python3 -c \"open('{_EXISTING}', 'r+').read()\"", 2),
    ("cat > truncating an existing file BLOCK",
     f"cat > {_EXISTING} <<'EOF'\nfresh\nEOF", 2),
    ("python open() mode w on existing file, -c form BLOCK",
     f"python3 -c \"open('{_EXISTING}', 'w').write('x')\"", 2),
    ("non-canonical python heredoc (wrong delimiter) on existing file BLOCK",
     _WRONG_DELIM_FORM, 2),
    ("tee (no -a) on existing file BLOCK",
     f"tee {_EXISTING} <<< hi", 2),
    ("cat > creating a brand-new file PASS",
     f"cat > {_NEW_PATH} <<'EOF'\nhello\nEOF", 0),
    ("cat >> appending an existing file PASS",
     f"cat >> {_EXISTING} <<'EOF'\nmore\nEOF", 0),
    ("tee -a an existing file PASS",
     f"tee -a {_EXISTING} <<< hi", 0),
    ("python open() mode x on a brand-new file PASS",
     f"python3 -c \"open('{_NEW_PATH}', 'x').write('x')\"", 0),
    ("python open() mode w on a brand-new file PASS",
     f"python3 -c \"open('{_NEW_PATH}', 'w').write('x')\"", 0),
    ("the exact canonical LINEEDIT form on an existing file PASS",
     _CANONICAL_FORM, 0),
    ("unresolvable path (sys.argv) PASS",
     f"python3 -c \"import sys; open(sys.argv[1], 'w').write('x')\" {_EXISTING}", 0),
    ("sed -i mentioned only as prose inside a new-file heredoc PASS",
     f"cat > {os.path.join(_FIXTURE_DIR, 'prose.md')} <<'EOF'\n- `sed -i` is dangerous\nEOF", 0),
    ("sed -i mentioned only as a quoted search term PASS",
     'duallog search "sed -i" --only tool_use', 0),
]


# ORCHESTRATOR

def test_block_non_canonical_edit_workflow() -> None:
    failures = []
    for desc, cmd, expected in CASES:
        got = _run_hook(cmd)
        status = "OK  " if got == expected else "FAIL"
        print(f"  [{status}] {desc}: exit={got} (expected {expected})")
        if got != expected:
            failures.append(desc)
    got = _run_hook_raw(b"not valid json{{{")
    desc = "parse-error fail-open PASS"
    expected = 0
    status = "OK  " if got == expected else "FAIL"
    print(f"  [{status}] {desc}: exit={got} (expected {expected})")
    if got != expected:
        failures.append(desc)
    total = len(CASES) + 1
    print()
    if failures:
        print(f"FAILED: {len(failures)} case(s):")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)
    print(f"All {total} tests passed.")


# FUNCTIONS

def _run_hook(command: str) -> int:
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": _FIXTURE_DIR,
    })
    return _run_hook_raw(payload.encode())

def _run_hook_raw(stdin_bytes: bytes) -> int:
    result = run_hook(HOOK, stdin_bytes)
    return result.returncode


if __name__ == "__main__":
    test_block_non_canonical_edit_workflow()
