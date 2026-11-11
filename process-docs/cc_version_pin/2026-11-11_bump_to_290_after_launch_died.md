# 2026-11-11 — CC 2.1.280 -> 2.1.290 after the menubar launch died silently

## Symptom

Clicking a project in the menubar Launch tab opened a Ghostty window that closed again within a second. No session, no proxy.

## Cause

The wrapper `~/.local/bin/claude-280` and `~/cc-cache-fix-280/` no longer existed on disk. On 2026-11-11 13:33 the wrapper `~/.local/bin/claude-290` was created and `~/.local/bin/claude` was repointed to it, the 280 install was removed. `src/claude_proxy_start.sh` still defaulted `CLAUDE_BIN` to `claude-280`, so `_resolve_claude_bin` printed `ERROR: ... not found or not executable` and exited 1. Because the window runs the script directly, the window vanished with the error, which is why it looked like a crash rather than a missing binary.

The menubar log does not show this failure: `launch_workflow` logs `OK` as soon as Ghostty accepted the command. The exit of the started script is invisible there.

## Fix

Pin bumped in the three places established by the bump procedure in this area:
- `src/claude_proxy_start.sh` `CLAUDE_BIN` default -> `claude-290`.
- iterative-dev `src/spawn/tmux_spawn.sh` `worker_claude_bin` default -> `claude-290`.
- iterative-dev `src/spawn/DOCS.md` Calls out line.

`bash -n` passed on both scripts, `claude-290 --version` reports `2.1.290 (Claude Code)`.

## Lesson for the next bump

Installing a new wrapper and deleting the old one must happen in the same step as the pin bump in both repos. Otherwise every launch dies until the pin follows. A quick check before deleting an old wrapper: `awk '/claude-2/' src/claude_proxy_start.sh <iterative-dev>/src/spawn/tmux_spawn.sh`.
