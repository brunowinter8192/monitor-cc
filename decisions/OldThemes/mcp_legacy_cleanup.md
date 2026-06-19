# MCP → CLI Legacy Cleanup

The `ClaudeCode/cli/*` projects (reddit, searxng, rag, gh) and `iterative-dev` migrated from MCP servers to CLI tools long ago. Stale "MCP server" references remained scattered across the rules, plugin tooling, manifests, READMEs, and one live code dependency. This file tracks the cleanup across two 2026-06-19 sessions. **Complete** — the four risk-bearing remainders were resolved in session 2.

## Done (2026-06-19)

Non-risky, behavior-shaping surfaces — committed in this session:
- **Rules** (`~/.claude/shared-rules`, 7 files): `global/tool-use.md`, `global/documentation.md`, `opus/workers-1.md`, `opus/workers-3.md`, `worker/verification.md`, `worker/code-organization.md`, `worker/worker-rules.md`. Removed "MCP tool/call/server" from verification lists; `dev_sync MCP tool` → `git checkout main && git merge dev`; `tool_name_workflow for MCP` → CLI command; `server.py` tool-registration → `cli.py` subcommand-registration.
- **Plugin tooling** (`iterative-dev`): `bin/plugin-publish` — removed the entire dead "kill MCP servers" step plus `--no-restart` flag, `DO_RESTART`, and the "(or run /mcp)" hint (no MCP server ever matched). `plugin-sync.sh` — stale `MCP/RAG` example path → `cli/rag-cli`.
- **Manifest descriptions**: `searxng-cli/.claude-plugin/plugin.json`, `rag-cli` + `reddit-cli/.claude-plugin/marketplace.json` — "MCP server" removed from the `description` field (NOT the `name` fields — see Remaining #1).
- **`claude-plugins/README.md`**: "bundles MCP servers" → "CLI tools"; repo links `searxng-mcp`/`github-MCP`/`Reddit-MCP`/`RAG` → `searxng-cli`/`gh-cli`/`reddit-cli`/`rag-cli`.
- **Code dependency** (`reddit-cli`): removed `from mcp.types import TextContent` from `search_subreddits.py` + `index_subreddits.py`; both workflows now return plain `str`; `cli.py` does `print(result)`; `mcp` removed from `requirements.txt`. Live-verified (`reddit-cli search_subreddits "python"` runs clean). Merged reddit-cli main `f4477c8`.

## Done (2026-06-19, session 2) — the four deferred remainders

### 1. Plugin-identifier manifest fields — RESOLVED (no rename needed)
Traced the full resolution chain before touching anything: `known_marketplaces.json` registers **only** `brunowinter-plugins` → source `claude-plugins`; CC reads `claude-plugins/.claude-plugin/marketplace.json` (the canonical manifest) and clones each plugin's `source.repo`. `plugin-publish` builds `KEY="${PLUGIN_NAME}@${MARKETPLACE}"` from **plugin.json** `name`, not marketplace.json. The canonical manifest + every `plugin.json` + `installed_plugins.json` keys + cache dirs were **already fully unified on `-cli`**. The `reddit-mcp`/`rag-mcp` names lived only in the per-repo `reddit-cli`/`rag-cli` `.claude-plugin/marketplace.json` — which CC never consumes (a plugin repo defines itself via its `plugin.json`; only `claude-plugins` is a registered marketplace; no other plugin repo even has a marketplace.json). **Resolution:** deleted both dead `marketplace.json` files. Zero install/cache risk — they were never in the consumed path.

### 2. Runtime path `~/.reddit-mcp/` → `~/.reddit-cli/` — MIGRATED (no re-login)
`mv ~/.reddit-mcp ~/.reddit-cli` carried the live Chrome session + 24h token cache over (checked first that no Chrome process held the session dir). Updated 4 source refs (`src/reddit/browser.py`, `src/reddit/client.py`, `dev/bg_chrome_probe/01_bg_launch.py`, `02_headless_new.py`) + 8 doc refs (DOCS.md, src/reddit/DOCS.md, retrieval01, auth02, auth03, OldThemes browser_cleanup_leak / background_chrome_launch / oauth_read_migration). Left untouched: `.claude-plugin/marketplace.json` (item 1) and the external `reddit-mcp-buddy` mention in a scraped Reddit post. **Live-verified:** `reddit-cli search_subreddits "python"` returned real results, exit 0, no Chrome/mint activity, token-cache mtime unchanged — token loaded from the new path.

### 3. Borderline legacy names — RENAMED
- Log: `reddit_mcp.log` → `reddit-cli.log` (`cli.py` FileHandler + 5 doc refs). Log file did not exist on disk (runtime-created) → zero data loss.
- Decision file: `decisions/delivery01_mcp_tools.md` → `delivery01_cli_tools.md` via `git mv` (history preserved) + 2 inbound refs (DOCS.md tree, oauth_read_migration.md).

### 4. Obsolete READMEs — DELETED, not rewritten (scope change by user)
User decision: not building for external, no per-feature README maintenance → delete all project-owned READMEs everywhere. Removed 7 files: `monitor-cc/README.md` + `monitor-cc/src/menubar/README.md`; `reddit-cli` + `rag-cli` + `searxng-cli` READMEs; `iterative-dev/README.md` + `iterative-dev/CLAUDE.md`. Vendored READMEs untouched (tmux `repo/`, rag-cli `llama.cpp/`, all `.venv`/`dist`/`build`). gh-cli had no README.

## Also done (session 2) — GitHub hygiene

- **Repo descriptions cleared** — all 10 non-empty descriptions PATCHed to empty via the GitHub API (Python `requests`, `GH_TOKEN` from `~/.zshrc`, routed through mitmproxy via env `HTTPS_PROXY` + `REQUESTS_CA_BUNDLE`; the official `gh` fails on the mitmproxy CA). Wiped the remaining "MCP server" text that still sat in descriptions (Arxiv, gh-cli, GmailMCP, reddit-cli, searxng-cli, claude-plugins).
- **Repo renames** — `Arxiv`→`arxiv`, `GmailMCP`→`gmail` (the last dir↔repo name mismatches; both out-of-marketplace tools). GitHub auto-redirects; local remotes updated. All other cli/ dirs already match their GitHub repos and plugin names.

## Commits

- monitor-cc `5c4184d` (main); reddit-cli `9475bf7` (main, plugin-publish); rag-cli `d25a4b1` + `e8b8cec` (main, plugin-publish; the `e8b8cec` is an unrelated untracked design-doc committed to clean the tree for plugin-publish); searxng-cli `340fabd` (**dev** — repo was mid-parallel-work; README deletion reaches main on the user's dev→main merge); iterative-dev `8249153` (main, plugin-publish). All four plugin caches re-synced at unchanged version.

## Sources
- `plugin-publish` resolution chain: `iterative-dev/bin/plugin-publish` (KEY/cache logic), `~/.claude/plugins/installed_plugins.json`.
- Reference cleaners (read for comparison, kept): gh-cli `src/github/text_cleaning.py`, searxng `skills/searxng-cli-capture-and-index/SKILL.md`.
