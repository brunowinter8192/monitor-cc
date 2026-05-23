#!/usr/bin/env python3
"""
Smoke test for bead_tracker_hook per-subcommand processing.

Creates two temporary test beads, pipes crafted PostToolUse payloads
to the hook, verifies labels via 'bd label list --json', then cleans up.

Usage (from project root): ./venv/bin/python3 dev/bead_tracker_chain/smoke.py
"""

# INFRASTRUCTURE
import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent   # worktree / project root
HOOK  = PROJECT_ROOT / 'src' / 'menubar' / 'bead_tracker_hook.py'
VENV  = PROJECT_ROOT / 'venv' / 'bin' / 'python3'
BD    = '/opt/homebrew/bin/bd'
BD_DB = None   # discovered in smoke_workflow


# ORCHESTRATOR

def smoke_workflow():
    global BD_DB
    BD_DB = _find_db()
    if BD_DB is None:
        print('FATAL: .beads/dolt not found (walked 6 levels up from project root)')
        sys.exit(1)

    bead_a = _create_bead('[TEST-bead-track-chain] case-A')
    bead_b = _create_bead('[TEST-bead-track-chain] case-B')
    if not bead_a or not bead_b:
        sys.exit(1)
    print(f'Test beads created: {bead_a}  {bead_b}\n')

    results = []
    try:
        results.append(_run_case(
            'a',
            f'bd show {bead_a}',
            {bead_a},
            bead_a, bead_b,
        ))
        results.append(_run_case(
            'b',
            f'bd show {bead_a}; bd show {bead_b}',
            {bead_a, bead_b},
            bead_a, bead_b,
        ))
        results.append(_run_case(
            'c',
            f'bd --db /tmp/fake show {bead_a}; bd show {bead_b}',
            {bead_b},
            bead_a, bead_b,
        ))
        results.append(_run_case(
            'd',
            f'bd show {bead_a} | head -5',
            {bead_a},
            bead_a, bead_b,
        ))
    finally:
        _cleanup(bead_a, bead_b)

    passed = sum(results)
    print(f'\n{"=" * 44}')
    print(f'Summary: {passed}/{len(results)} passed')
    sys.exit(0 if passed == len(results) else 1)


# FUNCTIONS

# Walk up from PROJECT_ROOT to locate .beads/dolt
def _find_db():
    cur = PROJECT_ROOT
    for _ in range(6):
        p = cur / '.beads' / 'dolt'
        if p.exists():
            return p
        cur = cur.parent
    return None


# Create a bead and return its ID; returns None on failure
def _create_bead(title):
    r = subprocess.run(
        [BD, 'create', title, '--type', 'task', '--db', str(BD_DB)],
        capture_output=True, text=True,
    )
    for line in r.stdout.splitlines():
        if 'Created issue:' in line:
            # line format: "✓ Created issue: Monitor_CC-xxxx — title"
            return line.split('Created issue:')[1].strip().split(' ')[0]
    print(f'FATAL: could not create bead "{title}":\n{r.stdout}\n{r.stderr}')
    return None


# Return True if bead carries the given label
def _has_label(bead_id, label):
    r = subprocess.run(
        [BD, 'label', 'list', bead_id, '--db', str(BD_DB), '--json'],
        capture_output=True, text=True,
    )
    try:
        labels = json.loads(r.stdout) or []
        return label in labels
    except Exception:
        return False


# Remove label (no-op if absent)
def _remove_label(bead_id, label):
    subprocess.run(
        [BD, 'label', 'remove', bead_id, label, '--db', str(BD_DB)],
        capture_output=True,
    )


# Pipe a PostToolUse payload to the hook; cwd is project root so hook finds DB
def _fire_hook(cmd):
    payload = json.dumps({
        'tool_name': 'Bash',
        'tool_input': {'command': cmd},
        'cwd': str(PROJECT_ROOT),
    })
    subprocess.run(
        [str(VENV), str(HOOK)],
        input=payload.encode(),
        capture_output=True,
    )


# Clean slate → fire hook → verify labels; returns True on PASS
def _run_case(case_id, cmd, expected, bead_a, bead_b):
    _remove_label(bead_a, 'tracked')
    _remove_label(bead_b, 'tracked')

    _fire_hook(cmd)

    got = {b for b in (bead_a, bead_b) if _has_label(b, 'tracked')}
    ok  = (got == expected)
    tag = 'PASS' if ok else 'FAIL'
    exp_str = ', '.join(sorted(expected)) or '(none)'
    got_str = ', '.join(sorted(got))      or '(none)'
    print(f'Case {case_id}: {tag}')
    print(f'  cmd:      {cmd}')
    print(f'  expected: {exp_str}')
    print(f'  got:      {got_str}')
    return ok


# Remove labels + delete beads; safe on None
def _cleanup(bead_a, bead_b):
    for bid in (bead_a, bead_b):
        if not bid:
            continue
        _remove_label(bid, 'tracked')
        subprocess.run(
            [BD, 'delete', bid, '--force', '--db', str(BD_DB)],
            capture_output=True,
        )
    print('\nCleanup done.')


if __name__ == '__main__':
    smoke_workflow()
