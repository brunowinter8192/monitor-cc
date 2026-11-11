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

## Same day: claude-fable-5-2 is unknown to CC 2.1.290, 1M window forced via env

`strings` on the 2.1.290 binary: the built-in model list ends at `claude-fable-5-1` (plus `claude-mythos-5` and `claude-mythos-5-1`); `claude-fable-5-2` has zero hits. CC treats it as an unknown model and, since 2.1.223, auto-compacts inside an assumed window below 1M. The binary's own notice for this case names two remedies: append `[1m]` to the model name, or set `CLAUDE_CODE_MAX_CONTEXT_TOKENS` to the real window.

Decision: `CLAUDE_CODE_MAX_CONTEXT_TOKENS=1000000` in the environment of every launched Claude.
- monitor-cc `src/claude_proxy_start.sh`, `_launch_claude`, next to `HTTPS_PROXY`.
- iterative-dev `src/spawn/config.sh`, `_WORKER_ENV_PREFIX`, so every worker runner inherits it.

The `[1m]` suffix was rejected because the proxy forwards the model string verbatim; on 2026-07-20 `claude-sonnet-5[1m]` produced a 404 from the API (see the 176 -> 205 entry in this area). The env var leaves the model id untouched and is a no-op for models CC already knows.

Not verified live in this session: that a fresh fable-5-2 session reports a 1M window. Hypothesis until the user starts one. If auto-compact still triggers early, check whether the notice "the context window it assumes" still appears at startup.

## Correction the same day: the env var does not apply to claude-* ids, the [1m] suffix does

The user reported the window still capped after `CLAUDE_CODE_MAX_CONTEXT_TOKENS`. Reading the 2.1.290 resolver: the env var is only honored when the model id does not start with `claude-` (or is an alias that maps elsewhere). For `claude-fable-5-2` it is ignored and the startup notice offers only "append [1m] to the model name".

Applied the pattern already used for Haiku workers (see `process-docs/pdf_conversion_qa/`): the model id carries the suffix.
- `model_selection.json` main -> `claude-fable-5-2[1m]`.
- `proxy_rules.json` `model_params` got an exact-key entry `claude-fable-5-2[1m]` (the proxy matches exact strings, no suffix normalization).
- `src/menubar/model_selection.py` choice `claude-fable-5-2` -> `claude-fable-5-2[1m]` so the Models tab does not write the bare id back; `dev/model_selector/verify_model_cycle_and_io.py` adjusted, 9/9; bundle rebuilt with `setup_py2app.py py2app`.

The env var lines from the previous section were left in place; they are a no-op for claude-* ids and harmless. Not verified live: a fresh session on `claude-fable-5-2[1m]` reporting 1M. Hypothesis until the user launches one.
