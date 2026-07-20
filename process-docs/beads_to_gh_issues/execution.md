# Beads → GitHub Issues — Execution (2026-06-02)

Execution of the migration plan. Beads fully decommissioned this session.

## gh-cli issue commands built (prerequisite)

Added to the previously read-only `gh-cli` research CLI (worker `gh-issue-cli`, merged to gh-cli `main`): `create_issue`, `update_issue` (`--state` → close/reopen + `state_reason`), `list_issues` (**default state=open**, pull-requests filtered out), `comment_issue`, `delete_issue` (GraphQL `deleteIssue` — REST has no delete-issue endpoint). New generic `request()` helper in `src/github/client.py`. Auth + transport already solved by the existing client (zshrc token via `_read_zshrc_token`, `REQUESTS_CA_BUNDLE` = mitmproxy cert) → works THROUGH the proxy, unlike the Go `gh` binary which fails TLS verification on the intercepted `*.github.com` cert. REST endpoint specs sourced from the `gh-cli-reference` RAG collection; the GraphQL `deleteIssue` mutation came from model knowledge (the reference DB is REST-only) — indexing the GraphQL docs was left as follow-up work.

## Open-bead mapping method

bd DBs broken across all projects (`database not found: <oldname>` — rename casualty). Read open beads from each project's `.beads/issues.jsonl` (the bd export — survives the dead dolt server), filtered `status==open`. Cross-checked suspect "open" beads against `bd close` events in CC session JSONLs:
- monitor-cc `da3w` showed open but was `bd close`d 4× (dolt silent-revert bug) → actually DONE, not migrated.
- reddit-cli `issues.jsonl` was contaminated: held RAG's 89 beads + its own 35 (all own beads closed) → 0 real open.

Real open per project: monitor-cc 4, gh-cli 7, rag-cli 4, iterative-dev 7, trading 1, reddit-cli 0, searxng-cli 0.

## Migrated (user-selected) → GitHub Issues

| bead | → repo / issue |
|---|---|
| Monitor_CC-pxn7 | brunowinter8192/monitor-cc |
| github-0a7 | brunowinter8192/gh-cli #6 |
| github-1hp | brunowinter8192/gh-cli #7 |
| RAG-3a0 | brunowinter8192/rag-cli #5 |
| Trading-l42 | brunowinter8192/trading #1 |

Title + full description + a "Migrated from beads `<id>`" provenance line. All other open beads NOT migrated (user choice).

## Beads removed from the machine (restlos)

- 7 `dolt sql-server` processes killed; `dolt` brew-unpinned + uninstalled (+ `/opt/homebrew/etc/dolt`).
- `bd` binary (`~/.local/bin/bd`, 130 MB), `~/.beads/` registry, all 9 `.beads/` dirs (incl. arxiv/linkedin/wise2627), `~/beads-upgrade-backup-*` (86 MB).
- Menubar [Beads] tab (worker `menubar-beads-rm`): deleted `bead_controller.py`, `bead_data.py`, `bead_tracker_hook.py`; removed bead wiring from `app.py` + the bead-hook from `hook_setup.py` (activity working/idle hooks kept); rewired the tab ring 4→3 tabs (`Sessions · RAG · Queue`). Bundle rebuilt + reinstalled + relaunched, live-verified.

## Rules ported (`~/.claude/shared-rules`)

`opus/beads.md` → `opus/gh-issues.md` (full methodology port: Bead→Issue, `bd`→`gh-cli`, close = `update_issue --state closed`; meta unchanged — when/format/source-inventory/resume). ~30 scattered bead traces cleaned across opus/global/worker/situational. `proxy_rules.json` reconciled: injects `gh-issues.md`; new model = opus sessions get global+opus, worker sessions get global+worker, the `projects` section removed (it carried 11 stale file refs + stale `MCP/RAG`/`MCP/searxng` `path_contains` matchers).

## Preserved (per plan)

Other beads-related historical material kept untouched, per plan.

## Sources

- `~/.claude/shared-rules/opus/gh-issues.md`, `~/.claude/shared-rules/proxy_rules.json`
- gh-cli `src/github/{create,update,list,comment,delete}_issue.py` + `client.py:request()` + `DOCS.md`
