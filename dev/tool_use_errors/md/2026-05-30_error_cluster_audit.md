# Tool Error Cluster Audit — 2026-05-30

## Phase 1 — Cluster Table

| Bucket | Count | % | Verdict |
|--------|------:|---:|---------|
| `hook_prefixed` | 59 | 11.9% | HISTORICAL — pre-strip-hook prefix; confirmed below (Phase 2) |
| `tool_use_error` | 113 | 22.8% | KEEP — CC error payload; agent needs full text for debugging |
| `exit_code_nonzero` | 202 | 40.8% | KEEP — real Bash failure output; agent needs for debugging |
| `exit_code_0` | 0 | 0.0% | KEEP (informational) — Bash success with warning output |
| `rejection` | 12 | 2.4% | ALREADY_STRIPPED — proxy `_apply_first_pass` strips rejection marker |
| `bare_guidance` | 109 | 22.0% | KEEP — hook guidance after prefix strip OR CC tool error |
| `other` | 0 | 0.0% | KEEP (conservative) |
| **Total** | **495** | 100% | |

### Exit Code Distribution (exit_code_nonzero)

| Exit Code | Count | Meaning |
|-----------|------:|---------|
| 1 | 139 | generic failure |
| 2 | 11 | hook block / program error |
| 127 | 12 | command not found |
| 128 | 21 | git/invalid-exit-arg |
| 139 | 1 | segfault |
| 143 | 18 | SIGTERM (killed) |

## Phase 2 — Cross-Check: Does strip_hook_prefix.py Reach Anthropic?

**Method:** Scan available proxy logs for `stripped_hook_error_prefix` in `modifications`.
The proxy logs store POST-modification content — `stripped_hook_error_prefix` confirms the
strip ran AND the modified (prefix-free) payload was sent to Anthropic.

### Available Proxy Logs
- Files scanned: **65** (`src/logs/api_requests_*.jsonl`)
- Requests with `stripped_hook_error_prefix` modification: **2,970**
- Total `stripped_hook_error_prefix` modification items: **4,892** (one request can strip N messages)
- First occurrence timestamp: `2026-05-25T15:14:57.745Z`

### Are the 59 hook_prefixed Entries Historical (Pre-Strip)?

- `hook_prefixed` earliest: `2026-05-24T20:59:11.638Z`
- `hook_prefixed` latest:   `2026-05-25T01:26:48.049Z`
- First strip in proxy logs: `2026-05-25T15:14:57.745Z`
- All 59 predate first strip: **YES ✓**

- Proxy files referenced by 59 entries: 4
  - Missing (rotated): 4
    - `api_requests_opus_monitor_cc_1779652226.jsonl`
    - `api_requests_opus_rag_1779647737.jsonl`
    - `api_requests_worker_f93afc17_audit-logging_1779655914.jsonl`
    - `api_requests_worker_f93afc17_cleanup-deploy_1779662560.jsonl`

### Cross-Check Verdict

✅ **strip_hook_prefix.py reaches Anthropic.** Confirmed: `stripped_hook_error_prefix`
appears in 2,970 proxy-log requests spanning 65 log files.
The MODIFIED (prefix-stripped) payload is what Anthropic receives.

✅ **59 hook_prefixed entries are PRE-strip historical.** All 59 predate the first
`stripped_hook_error_prefix` modification timestamp. Their proxy files are rotated (4/4 missing).
These entries cannot recur under current config — strip_hook_prefix.py prevents them.

## Phase 3 — Bare-Guidance Bucket Characterization

Bare guidance entries: no `PreToolUse:` prefix, no `<tool_use_error>`, no `Exit code`.
These are hook guidance texts (block reason + fix) that reached tool_errors.jsonl
either WITHOUT the CC wrapper (pre-strip behavior) or WITH the wrapper stripped by
`strip_hook_prefix.py` before the monitor read the payload.

### Hook Type Breakdown

| Hook | Count | Sample guidance |
|------|------:|-----------------|
| `block_broad_grep` | 42 | `add --include='*.py' scope \| use the Grep tool \| grep -n <pattern> <file.py>` |
| `block_except_pass` | 16 | `replace `except ...: pass` with `raise` or `logger.error(e); raise`` |
| `block_cd_drift` | 10 | `use `git -C <worktree> diff` instead of `cd <worktree>`` |
| `cc_Read_error_no_wrapper` | 7 | `File does not exist. Note: your current working directory is /Users/brunowinter2` |
| `block_read_oversize (post-strip)` | 7 | `/Users/brunowinter2000/Documents/ai/Trading/concepts/phase_b_signal_exploration/` |
| `block_polling_loop` | 6 | `polling loop antipattern — use `wait $PID` then single `tail file` instead of re` |
| `block_dev_imports_src` | 6 | `dev/ scripts may not import from src/ — copy the logic into the dev/ module or i` |
| `block_venv_no_redirect` | 5 | `add redirect: `./venv/bin/python script.py > /tmp/name.md 2>&1`` |
| `block_dangerous_kill` | 5 | `pkill -f / pgrep -f\|kill risk killing worker sessions — use `worker-cli kill <na` |
| `block_git_destructive` | 2 | ``git commit --amend` — Never amend existing commits — create a new commit instea` |
| `block_read_oversize` | 2 | `File content (33719 tokens) exceeds maximum allowed tokens (25000). Use offset a` |
| `block_bd_cli_worker` | 1 | `bd from worker is forbidden — report bead ops in Completion Checklist, Opus hand` |
| **Total** | **109** | |

### Classification: All bare_guidance → KEEP

Every entry in this bucket is agent-relevant:
- **Hook guidance** (block reason + fix): the stripped content IS the signal —
  `block_broad_grep` tells the agent WHY grep was blocked and HOW to fix it;
  `block_except_pass` identifies the antipattern; etc. Without this text the
  agent cannot understand what was blocked or correct its next call.
- **CC Read errors without wrapper** (`cc_Read_error_no_wrapper`): native tool failures
  that CC emitted without `<tool_use_error>` wrapper — same KEEP verdict as `tool_use_error`.

## Sample Entries per Bucket

### `hook_prefixed` (59 entries)

- `2026-05-24T20:59:11` | `Bash` | `PreToolUse:Bash hook error: [python3 /Users/brunowinter2000/Documents/ai/Monitor_CC/src/hooks/block_broad_grep.py]: BLOCKED: recursive grep without --include scope (Rule 3, tool-use.md).↵Unrestricted `
- `2026-05-24T21:16:33` | `Bash` | `PreToolUse:Bash hook error: [python3 /Users/brunowinter2000/Documents/ai/Monitor_CC/src/hooks/block_cd_drift.py]: BLOCKED: `cd` into `.claude/worktrees/...` without a cd-back at the end of the chain.↵`
- `2026-05-24T21:12:16` | `Write` | `PreToolUse:Write hook error: [python3 /Users/brunowinter2000/Documents/ai/Monitor_CC/src/hooks/block_except_pass.py]: BLOCKED: silent exception swallow (`except ...: pass`) detected in written code.↵S`

### `tool_use_error` (113 entries)

- `2026-05-24T20:59:11` | `Edit` | `<tool_use_error>File has not been read yet. Read it first before writing to it.</tool_use_error>`
- `2026-05-24T21:14:00` | `Edit` | `<tool_use_error>File has not been read yet. Read it first before writing to it.</tool_use_error>`
- `2026-05-24T20:59:14` | `Edit` | `<tool_use_error>File has not been read yet. Read it first before writing to it.</tool_use_error>`

### `exit_code_nonzero` (202 entries)

- `2026-05-24T20:59:11` | `Bash` | `Exit code 1↵Info: cleaned up 1 orphaned dolt sql-server process(es)↵Comment added to Monitor_CC-8ggr↵===↵The following paths are ignored by one of your .gitignore files:↵.beads↵hint: Use -f if you rea`
- `2026-05-24T21:30:48` | `Bash` | `Exit code 128↵-- === before ===↵27d30ab docs(OldThemes): audit_logging subfolder + hook classification audit↵fatal: ambiguous argument 'dev': both revision and filename↵Use '--' to separate paths from`
- `2026-05-24T21:31:29` | `Bash` | `Exit code 1↵=== trigger any hook ===↵-rw-r--r--@ 1 brunowinter2000  staff  889 May 24 23:30 src/logs/hook_firing.jsonl↵=== tail log ===↵{"ts": "2026-05-24T21:30:48Z", "hook": "rewrite_git_ambiguous", `

### `rejection` (12 entries)

- `2026-05-25T14:41:29` | `Bash` | `The user doesn't want to proceed with this tool use. The tool use was rejected (eg. if it was a file edit, the new_string was NOT written to the file). STOP what you are doing and wait for the user to`
- `2026-05-25T14:41:29` | `Bash` | `The user doesn't want to proceed with this tool use. The tool use was rejected (eg. if it was a file edit, the new_string was NOT written to the file). STOP what you are doing and wait for the user to`
- `2026-05-25T15:29:50` | `Bash` | `The user doesn't want to proceed with this tool use. The tool use was rejected (eg. if it was a file edit, the new_string was NOT written to the file). STOP what you are doing and wait for the user to`

### `bare_guidance` (109 entries)

- `2026-05-24T23:15:41` | `Bash` | `add --include='*.py' scope \| use the Grep tool \| grep -n <pattern> <file.py>↵`
- `2026-05-24T23:15:41` | `Bash` | `add --include='*.py' scope \| use the Grep tool \| grep -n <pattern> <file.py>↵`
- `2026-05-25T01:21:16` | `Write` | `replace `except ...: pass` with `raise` or `logger.error(e); raise`↵`

## Conclusion

### New strippable patterns?

**No new strippable patterns identified.** Analysis of all 495 entries:

| Bucket | Verdict | Rationale |
|--------|---------|-----------|
| `hook_prefixed` (59) | HISTORICAL | Pre-strip-hook; can't recur; proxy files rotated |
| `tool_use_error` (113) | KEEP | CC error payload the agent needs for debugging |
| `exit_code_nonzero` (202) | KEEP | Real Bash failure output; agent needs context |
| `rejection` (12) | ALREADY_STRIPPED | Proxy `_apply_first_pass` strips before Anthropic |
| `bare_guidance` (109) | KEEP | Hook guidance (block reason + fix) + CC tool errors |

### Is strip_hook_prefix.py sufficient?

**Yes.** `strip_hook_prefix.py` is working correctly and reaches Anthropic:
- Confirmed in 2,970 requests across 65 available proxy logs.
- Post-strip, hook guidance appears in `bare_guidance` bucket WITHOUT the path-noise prefix —
  the agent sees only the actionable guidance text (reason + fix), not the filesystem path.
- The 59 `hook_prefixed` entries are a closed historical set from a 6-hour window
  (2026-05-24T20:59 → 2026-05-25T01:26) before strip_hook_prefix.py was active.

### No new strip module needed

The `rejection` bucket (12 entries) is already handled by `_apply_first_pass`.
No other bucket has a prefix pattern that is pure noise — all content is agent-relevant.
Conservative KEEP bias applied throughout.
