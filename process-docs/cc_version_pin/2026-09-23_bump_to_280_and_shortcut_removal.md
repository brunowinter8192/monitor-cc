# 2026-09-23 — CC 2.1.258 → 2.1.280, plus removal of the --fable/--opus launcher shortcuts

New file, not an edit of `cc_version_pin.md` — that file is not mine to touch this session (see
the standing process-docs rule: one writable file per session, cross-reference the area, never
another session's file). Cross-reference for the established bump procedure and prior history:
`process-docs/cc_version_pin/cc_version_pin.md`.

## What was different about this bump

The trigger, orchestrator-side, was adding a new model id (`claude-opus-5-5`) to the menubar's
Models tab — see `process-docs/model_selector/2026-09-23_opus55_addition_and_shortcut_removal.md`
for that half. `claude-opus-5-5` is absent from the previously pinned CC 2.1.258 and from the npm
`stable` tag 2.1.267 (both checked with `strings` on the binary by the orchestrator before this
task started — not re-derived here), and present in 2.1.280 (npm `latest`). 2.1.280 was already
installed at `~/cc-cache-fix-280/.../bin/claude.exe` and the wrapper `~/.local/bin/claude-280`
already existed (`DISABLE_AUTOUPDATER=1`, verified reporting `2.1.280 (Claude Code)`) before this
task started — install + wrapper creation were orchestrator infra, out of this task's scope, same
division of labor as the 2026-09-02 bump to 2.1.258.

Only the launcher pin was in scope here: `src/claude_proxy_start.sh` — `CLAUDE_BIN` default
`claude-258` → `claude-280`, plus the version-pin comment directly above it (now states exactly
the measured evidence — absent from 258/267-stable, present in 280 — rather than inventing an
"introduced in CC X" claim nobody verified). `tmux_spawn.sh`'s two `worker_claude_bin` defaults
(iterative-dev, lines 665 + 860) → `claude-280` in the same session, no `plugin-publish` run and
`plugin.json` untouched (orchestrator's own instruction — it handles the cache sync separately).
`src/spawn/DOCS.md`'s "Calls out" line for `tmux_spawn.sh` updated to match.

## Scope change mid-session: --fable/--opus removed entirely

Not part of the original task framing — added by the user after reviewing the initial plan. The
user's only invocation is now:

```
cd <repo> && PATH="$HOME/.local/bin:$PATH" ./src/claude_proxy_start.sh --project <path>
```

Model steering happens exclusively through the menubar's Models tab (writes
`~/.claude/shared-rules/model_selection.json`). Consequence: `src/claude_proxy_start.sh`'s
`--fable`/`--opus` case branches and the `SHORTCUT_MODEL` variable were deleted outright, not
just left unused. Precedence collapsed from 4 tiers to 3: explicit `--model` (anywhere in the
args) > `"main"` from the config file > nothing injected. The degradation behavior of the bottom
tier (missing/unreadable file, malformed JSON, missing/empty `"main"` key — all silently inject
nothing, launcher never fails on account of the config file) is byte-identical to before; only the
tier count and the now-removed middle tier changed.

`dev/model_selector/verify_launcher_model_precedence.sh` was brought into sync (its own header
comment commits it to mirroring the launcher's parse loop) — rewritten to prove the 3 remaining
tiers, 11/11 checks, including the actual real-world invocation shape (`--project` with no other
flags picks up the config's `main` model) and that an explicit `--model` still wins over the
config. Full case list and output are in `dev/model_selector/md/
verify_launcher_model_precedence_20260923_093701.md`.

## Verification run this session

- `bash -n src/claude_proxy_start.sh` — pass.
- `bash -n src/spawn/tmux_spawn.sh` (iterative-dev) — pass.
- `bash dev/model_selector/verify_launcher_model_precedence.sh` — 11/11 pass.
- Whole-repo grep sweep (both repos) for `claude-223`/`claude-258`/`2.1.223`/`2.1.258`/
  `--fable`/`--opus`/`SHORTCUT` after the edit — zero stale hits outside the deliberate
  explanatory sentences (the version-evidence comment, this file's own removal note).
- Confirmed via grep in the iterative-dev worktree that `bin/worker-cli` and `spawn.py` carry no
  hardcoded CLAUDE_BIN-style version path — the only two hardcode sites for the binary wrapper
  are `tmux_spawn.sh`'s two `worker_claude_bin` lines, both fixed.

## Not done here (explicitly out of scope, per the orchestrator)

- No `plugin-publish`, no `plugin.json` edit (iterative-dev cache sync).
- No live session start, no menubar rebuild (`setup_py2app.py` not run) — live/production
  verification is the orchestrator's own next step.
- Deletion of the old `claude-258` wrapper + `cc-cache-fix-258` dir — not mentioned in this
  task's scope; left for the orchestrator or a future cleanup, same deferred pattern as prior
  bumps in `cc_version_pin.md`.
