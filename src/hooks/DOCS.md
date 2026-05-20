# src/hooks/

## Role

Global CC safety hooks — PreToolUse scripts that intercept Bash tool calls and block known-destructive patterns before execution. Registered in `~/.claude/settings.json` (global, fires for ALL projects on this machine, not just Monitor_CC). Each hook script reads CC's JSON payload from stdin and exits 0 (allow) or 2 (block, stderr shown to user).

Design rationale and statistics: `decisions/OldThemes/tool_use_safety/2026-05-12_session_findings.md`.

## Public Interface

Each hook script is a standalone `python3 <script>.py` entry invoked by CC. Not imported by any module. Install via `hook_setup.py` (run once).

## Modules

### block_dangerous_kill.py (86 LOC)

**Purpose:** PreToolUse hook — blocks `pkill -f <pattern>` and `ps|grep|kill` pipe chains. Both patterns target processes via text substring matching against the full cmdline, which routinely kills unintended processes (CC worker sessions whose prompt text contains the matched string). Exits 2 + stderr with concrete safer alternatives. Exits 0 on any parse/internal error (fail-open).
**Reads:** stdin (CC PreToolUse JSON payload: `{tool_name, tool_input: {command}}`).
**Writes:** stderr (block message with alternatives) on match only.
**Called by:** CC hook system (`type: command` in `~/.claude/settings.json` PreToolUse/Bash entry). Never imported.
**Calls out:** stdlib only (`json`, `re`).

**Blocked patterns:**
- `pkill -f <anything>` — cmdline-substring matching, kills worker prompts
- `ps ... | ... grep ... | ... kill ...` — same problem via pipe chain

**Allowed patterns (not blocked):** `pkill -x <name>` (exact), `pkill <name>` (name-only), `kill <numeric_pid>`, `kill -<signal> <numeric_pid>`, `worker-cli kill <name>`, `launchctl bootout/kickstart`.

**Quote-aware matching.** Patterns must appear at command start OR after a shell separator (`;`, `&`, `|`, newline) — substrings inside `"..."` or `'...'` quoted arguments are stripped before regex match (`_strip_quoted` helper). Prevents the false-positive where a `bd comments add "...pkill -f..."` command (writing the pattern as text into a bead) gets blocked. Not a full shell parser; handles balanced quotes with simple backslash-escape.

---

### hook_setup.py (63 LOC)

**Purpose:** One-shot idempotent installer — adds a `PreToolUse` / matcher=`Bash` entry to `~/.claude/settings.json` pointing at the absolute path of `block_dangerous_kill.py`. Safe to re-run; detects existing entry by exact command string and skips duplicate. Atomic write via temp + `os.replace`.
**Reads:** `~/.claude/settings.json`.
**Writes:** `~/.claude/settings.json` (atomic via temp + `os.replace()`).
**Called by:** User manually (`python3 src/hooks/hook_setup.py` from Monitor_CC root). Never imported.
**Calls out:** stdlib only (`json`, `os`, `pathlib`).

**Usage:** `python3 src/hooks/hook_setup.py` — run once after clone or reinstall. Restart CC to activate.

---

## Gotchas

- **Fail-open is mandatory.** `block_dangerous_kill.py` exits 0 on any parse error or missing field — the hook must never block a legitimate tool call due to its own failure. A broken hook that blocks everything is a footgun.
- **Global registration.** The hook fires for every Bash tool call in every CC session on this machine (main sessions and workers). Keep the hook fast and narrowly scoped. Current timeout: 5s (set in `hook_setup.py`).
- **Absolute path in settings.json.** `hook_setup.py` writes the full resolved path of `block_dangerous_kill.py` at install time. If the repo is moved, re-run `hook_setup.py` to update the path.
- **Cache-bust on settings.json edit.** Editing `~/.claude/settings.json` busts CC's prompt cache — full message rebuild on the next request. Expected cost; CC must be restarted anyway to pick up the hook.
- **PreToolUse exit codes.** Exit 0 = allow, exit 2 = block (CC shows stderr to user as the block reason), exit 1 = hook error (CC logs but does not block). This hook uses exit 2 on block, exit 0 on allow and on hook-internal errors.
