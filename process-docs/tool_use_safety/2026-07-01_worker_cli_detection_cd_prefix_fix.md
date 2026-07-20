# worker-cli detection: cd-prefix bug & fix (2026-07-01)

## Bug

`block_background_sleep_nonworker.py` was blocking legitimate worker-wait timers whenever the
preceding `worker-cli spawn` was cd-prefixed. Live repro: last cmd recorded as
`cd /Users/.../gh-cli\nworker-cli spawn doccheck-verify /tmp/p.md . sonnet` (two-line form:
`cd` + newline + `worker-cli`) → hook seeded that as the last cmd → next timer
(`sleep 600 && echo done`, `run_in_background=True`) → hook exited 2 (BLOCK) with
"Go idle immediately…".

Root cause: `_WORKER_CLI_RE = re.compile(r'^\s*worker-cli\b')` anchored at string start.
`_is_worker_cli` called `.match()` — only matches when `worker-cli` is the LEADING token.
All three real cd-prefix forms fail:
- `cd /p ; worker-cli …` — `;` at position 0 after cd/space → regex fails
- `cd /p && worker-cli …` — `&&` separator → regex fails  
- `cd /p\nworker-cli …` — newline separator → regex fails

Since spawns are ALWAYS cd-prefixed in practice (Opus always cd's to the worktree first),
the hook was over-blocking essentially every legitimate worker-timer.

## Fix

```python
# Before
_WORKER_CLI_RE = re.compile(r'^\s*worker-cli\b')
return bool(_WORKER_CLI_RE.match(stripped))

# After
_WORKER_CLI_RE = re.compile(r'(?:^|[;&|\n])\s*worker-cli\b')
return bool(_WORKER_CLI_RE.search(stripped))
```

`(?:^|[;&|\n])` matches at string start OR immediately after `;`, `&`, `|`, or `\n`.
`.search` (not `.match`) lets it find the pattern anywhere in the string.

## Verification

Bug reproduced BEFORE fix: exit 2 (BLOCK) on the exact live-repro last-cmd.
After fix: exit 0 (ALLOW) on same input.

Smoke extended from 7 → 10 cases:
- (g) `cd /p ; worker-cli spawn …` → ALLOW
- (h) `cd /p && worker-cli status …` → ALLOW
- (i) `cd /Users/…/gh-cli\nworker-cli spawn …` (exact live form) → ALLOW
All original cases preserved. All 10 pass.

## Files changed

- `src/hooks/block_background_sleep_nonworker.py` — regex line 14 + `.search` on line 77
- `dev/hook_smoke/test_block_background_sleep_nonworker.py` — 3 new cases, count 7→10
- `src/hooks/DOCS.md` — worker-cli detection line + smoke count
- The proxy-cache pipeline's safety-hooks current-state doc — worker-cli detection line + smoke count
