# bead_tracker_chained — A1

## Problem

`bead_tracker_hook.py` auto-tracks bead IDs seen in `bd show`/`bd comments [add]` Bash calls by adding the `tracked` label. When Opus chains multiple bd calls in one Bash invocation the hook silently drops all but the first.

**Repro 2026-05-22:** `bd show robl; bd show vj3v` → menubar bead panel showed only `robl`; `vj3v` never appeared.

## Root Cause

Two independent bugs in `bead_tracker_hook_workflow()` (pre-fix state):

### Bug 1 — Full-string `_HAS_DB_FLAG` check (line 31)

```python
if not cmd or _HAS_DB_FLAG.search(cmd):
    return   # cross-project call — ignore per spec
```

`_HAS_DB_FLAG = re.compile(r'--(?:db|repo)\b')` ran against the entire chained command string. A single `--db` flag in any subcommand (e.g. `bd --db /other show X`) disqualified the whole chain, including local subcommands that follow it.

### Bug 2 — First-match-only `_BD_TRACK_RE` (line 33)

```python
m = _BD_TRACK_RE.search(cmd)
```

`re.search` returns the first match only. In `bd show A; bd show B`, only `A` was captured; `B` was never reached.

## Fix Architecture

### Splitting strategy

New constant in INFRASTRUCTURE:

```python
_SEP_RE = re.compile(r'(?:;|&&|\|\|)')   # shell statement separators — NOT pipe
```

Splits on `;`, `&&`, `||`. Single `|` (pipe) is intentionally excluded — `bd show X | head -5` must stay one logical unit.

### Per-subcommand loop (new ORCHESTRATOR body)

```
cwd / db_path resolved ONCE (same for all subcommands — same CC session)
for subcmd in _SEP_RE.split(cmd):
    strip → skip if empty
    _HAS_DB_FLAG per subcmd    → skip cross-project subcommands only
    _BD_TRACK_RE per subcmd    → capture bead_id or continue
    _BEAD_ID_RE validate       → continue on false match
    _bd_label_add(bead_id, db_path)
```

`cwd` / `db_path` computed once outside the loop — all subcommands share the same CC session working directory.

### Edge cases

| Case | Handling |
|---|---|
| Trailing `;` → empty segment | `subcmd.strip()` == '' → `continue` |
| Non-bd subcommand (e.g. `ls`) | `_BD_TRACK_RE.search` → None → `continue` |
| Mixed chain: one cross-project, one local | Cross-project subcmd skipped via per-subcmd `_HAS_DB_FLAG`; local subcmd labeled normally |
| Pipe: `bd show X \| head -5` | `_SEP_RE` does not match single `\|`; treated as one subcommand → labeled correctly |
| `||` (logical OR): `bd show X \|\| true` | Split at `\|\|`; `true` → no match → skipped |

## Smoke Evidence

`dev/bead_tracker_chain/smoke.py` — 4 cases, two real test beads created/deleted per run.

```
Test beads created: Monitor_CC-v8cb  Monitor_CC-a7t7

Case a: PASS
  cmd:      bd show Monitor_CC-v8cb
  expected: Monitor_CC-v8cb
  got:      Monitor_CC-v8cb
Case b: PASS
  cmd:      bd show Monitor_CC-v8cb; bd show Monitor_CC-a7t7
  expected: Monitor_CC-a7t7, Monitor_CC-v8cb
  got:      Monitor_CC-a7t7, Monitor_CC-v8cb
Case c: PASS
  cmd:      bd --db /tmp/fake show Monitor_CC-v8cb; bd show Monitor_CC-a7t7
  expected: Monitor_CC-a7t7
  got:      Monitor_CC-a7t7
Case d: PASS
  cmd:      bd show Monitor_CC-v8cb | head -5
  expected: Monitor_CC-v8cb
  got:      Monitor_CC-v8cb

Cleanup done.

============================================
Summary: 4/4 passed
```

## Limitations

**Quoted separators** — `_SEP_RE` is a naive string split. A command like `bd show "Monitor_CC-aa;bb"` would split at the `;` inside the quoted argument. In practice, bead IDs never contain `;`, `&&`, or `||`, so this is a non-issue. A full shell tokenizer (e.g. `shlex`) would handle it but adds unnecessary complexity for zero real-world benefit.
