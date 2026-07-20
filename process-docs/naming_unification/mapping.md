# Naming Unification — Mapping

Cross-cutting cleanup. Goal: **directory = remote repo = plugin name**, consistently, `-` instead of `_`, lowercase. Surfaced during a version bump: plugin `iterative-dev` in dir `blank` with remote `Meta` = triple mismatch.

## Principle

- dir name = git remote repo name = plugin name (where a plugin exists)
- separator `-`, never `_`
- lowercase
- CLI-Tools get `-cli` suffix (matches existing wrapper names: rag-cli, gh-cli, reddit-cli, searxng-cli)
- marketplace-INTERNAL name (`brunowinter-plugins`, manifest field) is independent of repo name — NOT part of the unification

## Scope

In scope: 4 CLI plugins (gh-cli, rag-cli, reddit-cli, searxng-cli) + iterative-dev + monitor-cc + trading + parent dir rename.
**Marketplace-removal ONLY** (user 2026-06-02, corrected): `arxiv`, `gmail` removed from `marketplace.json` (+ manifest copies). **Source repos/folders are KEPT — never deleted.** `linkedin` is not in the marketplace (no plugin.json) → nothing to do, source stays. arxiv/gmail already absent from installed_plugins.json + cache.
`claude-plugins` (marketplace source repo): already consistent (dir=remote=`claude-plugins`, not a listed plugin) — no change.

## Marketplace final set (brunowinter-plugins)

Exactly 5 plugins, NONE has an MCP server (all former MCP servers retired — skill-only, or wrapper-only for rag-cli):
`gh-cli`, `reddit-cli`, `rag-cli`, `iterative-dev`, `searxng-cli`.

## Mapping (CONVERGED, user-confirmed 2026-06-02)

| Current dir | Current remote | Current plugin | → unified name | New path |
|---|---|---|---|---|
| `MCP/github` | `github-MCP` | `github-research` | `gh-cli` | `cli/gh-cli` |
| `MCP/RAG` | `RAG` | `rag` | `rag-cli` | `cli/rag-cli` |
| `MCP/Reddit` | `Reddit-MCP` | `reddit` | `reddit-cli` | `cli/reddit-cli` |
| `MCP/searxng` | `Websearch-MCP` | `searxng` | `searxng-cli` | `cli/searxng-cli` |
| `Meta/blank` | `Meta` | `iterative-dev` | `iterative-dev` | `Meta/iterative-dev` |
| `MCP/claude-plugins` | `claude-plugins` | — | `claude-plugins` (unchanged) | `cli/claude-plugins` |
| `Monitor_CC` | `ClaudeCode-Monitor` | — | `monitor-cc` | `monitor-cc` |
| `Trading` | `Trading` | — | `trading` | `trading` |
| parent `Meta/ClaudeCode/MCP/` | — | — | `cli/` | `Meta/ClaudeCode/cli/` |

Per entry: rename dir, rename GitHub remote repo, align plugin name (where exists), update marketplace manifest, fix hardcoded paths (worker-cli, rag-cli, configs, hooks).

## Discovered Defect

`searxng` marketplace entry points at `brunowinter8192/searxng-mcp`, but actual folder remote = `Websearch-MCP`. Manifest references a repo that is not the real source. MUST be resolved during rename — target is `searxng-cli` for both.

## Special Cases

- `linkedin`: no `plugin.json`, not in marketplace → out of scope (possibly dead dir).
- `claude-plugins`: IS the marketplace source. dir=remote already match. No plugin name. Marketplace-internal name `brunowinter-plugins` stays.
- Cache `~/.claude/plugins/cache/brunowinter-plugins/`: only 5 of 7 registered plugins installed (`arxiv`, `gmail` registered but not cached). Irrelevant post-scope-cut.

## Pending (execution, not done)

Per-project rename sequence (dir → remote → plugin → marketplace manifest → hardcoded paths → verify plugin-publish + cache resolve). Order TBD. This is the prerequisite "clean" step before the beads→gh-issues migration.
