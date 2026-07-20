## ✅ SUPERSEDED — bd 1.0.4

The auto-import-clobber root cause documented in this file is **disproven on bd 1.0.4**. `maybeAutoImportJSONL` (`cmd/bd/auto_import_upgrade.go`) is emptiness-guarded via `GetStatistics` AND uses `importFromLocalJSONLConflictSkip` (insert-if-new, not UPSERT — GH#3955): a stale JSONL on a non-empty DB is a harmless no-op, categorically not a clobber. `block_batch_bd_close.py` has been retired.

The root cause below (#4239/#3948/#4135, pre-1.0.4 JSONL auto-import clobbering) was real and valid for the bd versions in use at investigation time. Preserved as historical evidence.

---

# bd Mutation Revert — Investigation

## Problem (Symptom)

`bd close <id>` (and other bead mutations) reported `✓ Closed` but the bead reverted to OPEN on a later command. Batch closes (`bd close A B`, or multiple `bd close` in one shell invocation) lost all but the first. Closing 7 beads consumed a whole session because closes silently reverted even when an immediate `bd show` confirmed CLOSED.

## Root Cause — two distinct mechanisms

1. **Batch revert (#4135):** multiple bd mutations in ONE shell invocation — the first persists, the rest are written + acked but reverted by downstream dolt-connection cycling / auto-flush against partial state.
2. **Single-close revert (#4239 / #3948 / #4128 / #3905):** bd auto-exports to `.beads/issues.jsonl` after every mutation AND attempts `git add` on it. With `.beads` gitignored, the `git add` fails (`paths are ignored by one of your .gitignore files: .beads`) → auto-export unreliable → JSONL stale. bd's `maybeAutoImportJSONL` re-imports the stale JSONL into dolt on a LATER command (GetStatistics intermittently returns 0; shared-server emptiness check fails) → clobbers the close. Even `bd config list` triggered the failing git-add — the export path runs on every command.

## Upstream issues (gastownhall/beads, indexed in `github_issues`)

| # | Title | Relevance |
|---|---|---|
| 4239 | shared-server auto-import overwrites live dolt on every command | core single-close revert; root in `maybeAutoImportJSONL` emptiness guard (`auto_import_upgrade.go`) |
| 3948 | GetStatistics returns 0 → auto-import fires repeatedly | revert ~5s after close |
| 4128 | reconciler treats JSONL as source-of-truth, clobbers even direct SQL writes | commit `bd: create N issue(s)` after `auto-migrate` |
| 3905 | `bd close` no-ops status UPDATE, prints success; `nothing to commit` | matches our `dolt-server.log` warnings |
| 4135 | multiple closes in one shell invocation revert | batch mechanism; workaround = one close + `bd export` per invocation |
| 4132 / 3392 | stale / multiple dolt sql-server processes; non-deterministic auto-start | matches our 6 servers + `idle-timeout:0`; fix `EnsureRunning()→KillStaleServers()` exists upstream |
| 284 | non-canonical db name → daemon refuses to run | our daemon is dead (db dir named `dolt`, daemon expects `beads.db`) |

## Fix — two layers

1. **Global hook** `block_batch_bd_close.py` (registered in `~/.claude/settings.json` → fires for ALL projects on this machine): blocks any Bash call carrying >1 bead-mutation unit. Structurally prevents the batch-revert (#4135). Module map: `src/hooks/DOCS.md`. 29 smoke cases (`dev/hook_smoke/test_block_batch_bd_close.py`).
2. **Per-repo config** `bd config set export.git-add false`: stops the failing `git add` → auto-export completes reliably (like an explicit `bd export > .beads/issues.jsonl`) → JSONL stays synced → auto-import imports the correct state → no revert. Addresses the single-close revert (#4239). **Per-project** — bd config is stored per-project (`bd config --help`: "stored per-project in the beads database"); no global config exists (`~/.beads/` holds only `registry.json`). Must be set in each bead repo.

## Stress-test evidence

Method: throwaway bead → close → 20 auto-import triggers (`bd show`/`bd list` ×10) → confirm CLOSED → `bd dolt stop` + fresh start → confirm CLOSED → delete.

| Repo | empty-DB symptom | intra-session (20 cmds) | cross-session (server bounce) |
|---|---|---|---|
| Monitor_CC | no | CLOSED ✓ | CLOSED ✓ |
| RAG | yes (auto-import into empty DB on cold start) | CLOSED ✓ | CLOSED ✓ |

The RAG test confirms the fix holds even for repos exhibiting the empty-DB auto-import symptom that Monitor_CC did not show.

**Pre-fix observation:** closing 6 beads sequentially → 4 reverted (gz7/iue/m6q/rkk) despite each inline `bd show` = CLOSED; only de8 (first) and t1i (last) held. The `bd close X; bd export > .beads/issues.jsonl` workaround per invocation held them — this confirmed export-reliability (the git-add failure) as the root, since the redirect export bypasses bd's internal git-add path. The config fix `export.git-add false` makes the internal auto-export reliable, eliminating the manual workaround.

## Cross-repo application

`export.git-add=false` confirmed on 7 repos: `Monitor_CC`, `Meta/blank`, `MCP/github`, `MCP/RAG`, `MCP/Reddit`, `MCP/searxng`, `Trading`. (MCP/arxiv + MCP/linkedin out of scope — broken dolt-server state: arxiv "database not found on server", linkedin "server unreachable :3307" + deprecated `dolt_server_port` cross-project-leakage warning.)

## Hook design notes

- **Mutation-unit counting:** id-list mutators (`close`/`done`/`reopen`/`update`/`delete`) → id-count with `max(1, count)`; other mutators (`create`/`set-state`/`todo`/…) → 1 per invocation; infra (`config`/`dolt`) → 0; reads → 0; compound (`comments add`, `dep add/remove`, `find-duplicates --merge`) → 1, view/list forms → 0. Full spec: `src/hooks/DOCS.md`.
- **Refinements landed this session:** (a) `set-state` moved to other-mutator (its state value e.g. `in-progress` matched the bead-id regex → false id count); (b) no-id mutator counts as `max(1,0)=1` (a no-id `bd close` chained with another mutation was slipping through as 0); (c) `config`/`dolt` exempted as infra (were blocking legitimate `bd config set; bd config get` chains); (d) `delete` added to id-list mutators (`bd delete A B` batch was bypassing detection).
- **KNOWN GAP (tracked):** `bd -C <repo>` / `bd --db <path>` forms place the subcommand at `tokens[2+]`, so `tokens[1]=='-C'` is skipped → batch detection bypassed. `bd -C <repo> close A B` is NOT blocked. Minor (only when operating on another repo's beads via `-C`); a tracking bead exists.

## dolt-server landscape (context)

6 `dolt sql-server` processes (one per project), `idle-timeout:0` → never shut down → accumulate. `bd dolt killall` reports "no orphans" (all considered active). Daemon is dead (non-canonical db name `dolt` vs expected `beads.db`, #284) → auto-sync daemon never runs. None of this blocks bead ops after the export.git-add fix.
