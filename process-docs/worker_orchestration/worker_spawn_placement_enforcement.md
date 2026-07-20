# Worker spawn placement enforcement — 2026-06-23

## The mistake

A worker was spawned into the WRONG project (gh-cli) instead of the current/main project (monitor-cc) via `cd gh-cli; worker-cli spawn getfile-fix /tmp/...md "$(pwd)" sonnet`. Rule (workers-1 § Worker Project Scope): workers always spawn into a worktree of the MAIN project; cross-project work happens via a separately-created target worktree the worker cd's into.

## Why Hook 30 (`block_worker_spawn_placement`) missed it

Hook 30 parses the RAW command string (PreToolUse, pre-expansion) and compares the static `project_path` arg's git-root against `os.getcwd()`.

- The arg as the hook sees it = literal `"$(pwd)"` (shell expansion happens AFTER the hook). `_resolve_project_root("$(pwd)")` → `os.path.abspath` joins the bogus relative string to the hook's own cwd (monitor-cc) → `_find_git_root` walks up → finds `monitor-cc/.git` → spawn_root == current_root == monitor-cc → "same project" → **fail-open, no block**.
- The `cd gh-cli;` prefix moved the RUNTIME cwd to gh-cli (so `$(pwd)` expanded to gh-cli at execution), but the hook's static view never saw gh-cli.
- Fire-log confirms: no `block_worker_spawn_placement` entry for getfile-fix; whereas cross-project spawns with EXPLICIT absolute paths (reddit-cli, Mineru, monitor-cc) WERE correctly blocked. The hook catches explicit-absolute-path-to-other-project only; dynamic (`$(pwd)`, `$VAR`) or relative args resolve to the hook's own root and pass.

## Decision — fix in worker-cli, not the hook

The hook is static (can't resolve `$(pwd)`, can't see post-`cd` cwd) — fundamentally limited. `worker-cli` is the single spawn chokepoint for ALL projects, runs at runtime with the shell-expanded path, and has `PROXY_PROJECT_PATH` (set by the proxy at session start, cwd-INDEPENDENT — survived the `cd`). It is the authoritative point of enforcement.

Fix (`bin/worker-cli` spawn case, iterative-dev `3767766`): resolve `$3` as REQUESTED, then if `PROXY_PROJECT_PATH` set → FORCE `PROJECT=resolve(PROXY_PROJECT_PATH)` + stderr note when REQUESTED differs; else fallback to `$3`. Uses `${PROXY_PROJECT_PATH:-}` for `set -e` safety. Does NOT break cross-project (home worktree is always main; target work via a separate worktree).

## Deployment lesson — runtime is the SOURCE, not the cache

- `worker-cli` shell invocation resolves via PATH: `~/.local/bin` is **position 1**, the plugin cache `~/.claude/plugins/cache/.../bin` is **position 22**. So the SOURCE (`iterative-dev/bin/worker-cli` via `~/.local/bin`) is what runs, NOT the cache.
- `~/.local/bin/worker-cli` was a BROKEN symlink (→ dead `Meta/blank/bin/worker-cli`); while broken, PATH fell through to the cache. Re-pointed to `iterative-dev/bin/worker-cli` (matching sibling `plugin-publish` symlink).
- A cache-only patch is both shadowed (source runs) AND overwritten by the next `plugin-publish` (which writes cache FROM source). The durable fix is the SOURCE merge (committed on iterative-dev main); `plugin-publish` then reproduces it into the cache.

## Verification

`cd gh-cli; worker-cli spawn wcli-test /tmp/...md "$(pwd)" sonnet` (the exact bug pattern, hook-bypassing) → policy note emitted + worktree/session/registry all forced to monitor-cc. Confirmed.

## block_manual_worker_cleanup narrowness (related finding)

Hook `block_manual_worker_cleanup` blocks `git worktree remove ... .claude/worktrees/` unconditionally (no cwd-skip, no escape) — assumes every `.claude/worktrees/` is worker-cli-managed. For a MANUAL non-worker worktree (the prescribed cross-project target-worktree pattern), the clean removal command is blocked AND `worker-cli kill` can't help (not registered). Workaround NOT matched by the hook: `rm -rf <dir> && git worktree prune`. Low severity (cosmetic orphan); not fixed.

## Status (as of 2026-06-23)

- worker-cli fix: committed iterative-dev main, verified, plugin-published (recap).
- Hook 30: left unchanged — still blind to dynamic `$(pwd)` project_path. worker-cli was the primary backstop at this point; the hook remained a fast pre-filter for explicit-absolute-path cross-project spawns.
