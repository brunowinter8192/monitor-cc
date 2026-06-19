# MCP → CLI Legacy Cleanup

The `ClaudeCode/cli/*` projects (reddit, searxng, rag, gh) and `iterative-dev` migrated from MCP servers to CLI tools long ago. Stale "MCP server" references remained scattered across the rules, plugin tooling, manifests, READMEs, and one live code dependency. This file tracks what was cleaned (2026-06-19) and what remains, deferred for risk.

## Done (2026-06-19)

Non-risky, behavior-shaping surfaces — committed in this session:
- **Rules** (`~/.claude/shared-rules`, 7 files): `global/tool-use.md`, `global/documentation.md`, `opus/workers-1.md`, `opus/workers-3.md`, `worker/verification.md`, `worker/code-organization.md`, `worker/worker-rules.md`. Removed "MCP tool/call/server" from verification lists; `dev_sync MCP tool` → `git checkout main && git merge dev`; `tool_name_workflow for MCP` → CLI command; `server.py` tool-registration → `cli.py` subcommand-registration.
- **Plugin tooling** (`iterative-dev`): `bin/plugin-publish` — removed the entire dead "kill MCP servers" step plus `--no-restart` flag, `DO_RESTART`, and the "(or run /mcp)" hint (no MCP server ever matched). `plugin-sync.sh` — stale `MCP/RAG` example path → `cli/rag-cli`.
- **Manifest descriptions**: `searxng-cli/.claude-plugin/plugin.json`, `rag-cli` + `reddit-cli/.claude-plugin/marketplace.json` — "MCP server" removed from the `description` field (NOT the `name` fields — see Remaining #1).
- **`claude-plugins/README.md`**: "bundles MCP servers" → "CLI tools"; repo links `searxng-mcp`/`github-MCP`/`Reddit-MCP`/`RAG` → `searxng-cli`/`gh-cli`/`reddit-cli`/`rag-cli`.
- **Code dependency** (`reddit-cli`): removed `from mcp.types import TextContent` from `search_subreddits.py` + `index_subreddits.py`; both workflows now return plain `str`; `cli.py` does `print(result)`; `mcp` removed from `requirements.txt`. Live-verified (`reddit-cli search_subreddits "python"` runs clean). Merged reddit-cli main `f4477c8`.

## Remaining (deferred — risk)

### 1. Plugin-identifier manifest fields
- `reddit-cli/.claude-plugin/marketplace.json`: `"name": "reddit-mcp"`, `"repo": "brunowinter8192/Reddit"`
- `rag-cli/.claude-plugin/marketplace.json`: `"name": "rag-mcp"`, `"repo": "brunowinter8192/RAG"`
- (searxng plugin.json `name` is already `searxng-cli`; gh-cli has no mcp-named manifest.)

**Risk:** the `name` field is the plugin identifier in the marketplace; `repo` is the source pointer. `plugin-publish` builds `KEY="${PLUGIN_NAME}@${MARKETPLACE}"` from **plugin.json** `name` (not marketplace.json), and there is a name mismatch (plugin.json `reddit-cli` vs marketplace.json `reddit-mcp`). The marketplace → `/plugin install` → `installed_plugins.json` key → cache-path chain may key off these. Trace that resolution before renaming, else install/update mapping could break.

**Next session:** understand how Claude Code consumes marketplace.json `name`/`repo` vs plugin.json `name` + `installed_plugins.json`. Then, if safe: reddit-mcp→reddit-cli, rag-mcp→rag-cli, repo Reddit→reddit-cli, RAG→rag-cli.

### 2. Runtime path `~/.reddit-mcp/`
- `reddit-cli/src/reddit/browser.py`: `SESSION_DIR = ~/.reddit-mcp/session` (persisted Chrome login session)
- `reddit-cli/src/reddit/client.py`: `TOKEN_CACHE_PATH = ~/.reddit-mcp/token_cache.json`

**Risk:** live data — the logged-in browser session + cached 24h token. Renaming the dir orphans the existing session (forces re-login + token re-mint).

**Next session:** decide whether it is worth touching (invisible runtime path). If renamed (e.g. `~/.reddit-cli/`), do it as a migration that moves the existing session/token, or accept a one-time re-login.

### 3. Borderline legacy names
- `reddit_mcp.log` — log filename (`reddit-cli/cli.py` logging setup + `DOCS.md` mention).
- `reddit-cli/decisions/delivery01_mcp_tools.md` — decision filename.

**Risk:** low. Renaming the log changes the log destination (2 references); renaming the decision file needs any inbound references updated. Cosmetic.

### 4. Obsolete READMEs (bigger than MCP — full rewrites)
- `reddit-cli/README.md`: describes 14 tools that no longer exist (`search_posts`, `reply_to_post`, `get_inbox`, …) + `claude mcp add-json` install. Current CLI = 2 subcommands (`search_subreddits`, `index_subreddits`, RAG-indexing model).
- `searxng-cli/README.md`: install via non-existent `mcp-start.sh`, old clone URL `SearXNG.git`, "MCP Tools" header. Tool list roughly current but the setup section is stale.

**Risk:** a blind rewrite could write WRONG setup steps (worse than stale). Needs each project's real current `cli.py` + setup flow.

**Next session:** rewrite both READMEs from the actual current interface, per project, deliberately.

## Sources
- `plugin-publish` resolution chain: `iterative-dev/bin/plugin-publish` (KEY/cache logic), `~/.claude/plugins/installed_plugins.json`.
- Reference cleaners (read for comparison, kept): gh-cli `src/github/text_cleaning.py`, searxng `skills/searxng-cli-capture-and-index/SKILL.md`.
