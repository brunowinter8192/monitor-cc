# Naming Unification — Execution Log

Live progress log for the structure migration (Bead uoyx). Resume state for a fresh session.

## Docker cleanup — DONE (2026-06-02)

Removed containers: `tor`, `searxng`, `tradbot-postgres`, `tpch-postgres`. Pruned ALL unused volumes (incl. orphan `rag_rag_postgres_data`) + all unused images. Reclaimed ~6.5 GB. KEPT: `rag-postgres` (pgvector/pgvector:pg18, bind-mount `data/postgres` = 619 MB) + its image.

GOTCHA observed: `rag-postgres` exited(0) during the heavy `docker ... prune` (OrbStack daemon hiccup) — NOT caused by the rm/prune targets. Recovered via `docker start rag-postgres`; all 15 collections intact (bind-mount untouched). If it recurs after a big prune: just `docker start rag-postgres`.

## Phase A — DONE + VERIFIED (2026-06-02)

Folder restructure (docker-offline window, `compose down` → mv → `compose up` from new path):
- `Meta/ClaudeCode/MCP` → `Meta/ClaudeCode/cli`
- inside `cli/`: `RAG`→`rag-cli`, `github`→`gh-cli`, `Reddit`→`reddit-cli`, `searxng`→`searxng-cli` (claude-plugins, arxiv, gmail, linkedin UNCHANGED)
- `Meta/blank` → `Meta/iterative-dev`

Path fixes:
- 7 wrappers in `~/.local/bin` (rag-cli, gh-cli, reddit-cli, searxng-cli, arxiv-cli, sync-rag-oldthemes, oom-watchdog comment) → `ClaudeCode/cli/<new>`
- `cli/rag-cli/.env` `RAG_PROJECT_ROOT` → new path
- `plugin-publish` symlink → `Meta/iterative-dev/bin/plugin-publish`

Verified: `rag-cli list_collections` ✓, `gh-cli`/`reddit-cli`/`searxng-cli` ✓, rag-postgres up from new path.

## Current resume state

- Folders: NEW (cli/ + iterative-dev). Wrappers: NEW. Local CLIs: WORKING.
- GitHub remote repos: RENAMED via REST (gh-cli, reddit-cli, rag-cli, searxng-cli, iterative-dev, trading) + local remote-urls updated. ONLY `ClaudeCode-Monitor` still old (user's finale). NOTE: `gh auth status` falsely reports GH_TOKEN invalid; token works fine via REST/curl (scopes incl `repo`). Use curl for GitHub ops, SSH for push.
- Plugins: ALL 5 migrated + cache-verified (gh-cli, reddit-cli, searxng-cli, rag-cli, iterative-dev). installed_plugins.json + cache + marketplace all on -cli scheme. Takes effect at CC RESTART (current session still runs the old-loaded plugins).
- RAG collections: still OLD names (gh_reference, Monitor_CC-docs, etc.).
- shared-rules: still reference OLD names/paths (6 files).

## Phase B progress (2026-06-02)

- gh-cli pilot DONE end-to-end (validated full flow). Old `github-research` cache removed.
- All remaining repos renamed + remote-urls updated (Batch 1).
- DONE: reddit-cli, searxng-cli, rag-cli (uninstall/install cycle), iterative-dev (plugin-publish, name unchanged). Skill folders renamed (reddit-cli-search, searxng-cli-{web-research,capture-and-index}, iterative-dev-refactor). iterative-dev agent + rule-consolidation + empty commands DELETED. searxng marketplace defect (searxng-mcp) fixed → searxng-cli. rag-cli rename cherry-picked onto master (default branch) so install cloned it. Old cache dirs (github-research, reddit, searxng, rag) removed, cache verified.
- rag-cli has divergent dev/master (active dev-workflow). Rename now on BOTH (dev via normal commit, master via cherry-pick). master is its default branch.

## PENDING

- **Phase B**: ✅ DONE — all 7 repos renamed (REST/curl, token works; `gh auth status` falsely reports invalid; SSH for push), all 5 plugins migrated (plugin.json/skills/marketplace/reinstall/cache). Plugin-LOAD verification pending CC restart.
- **RAG collection renames**: ✅ DONE — SQL renamed 15 collections in documents (20209 rows) + indexed_files (1492); `data/documents` folders renamed (gitignored, no commit); 6 `.rag-docs.json` updated (5 pushed, Monitor_CC at RECAP); verified via list_collections. NOTE: 9 stale orphan entries in indexed_files (Monitor_CC-features/-meta, RAG-features/-meta, searxng-features/-meta, Monitor_reference, reddit_meta_probe, Trafilatura_Reference) LEFT as separate cleanup.
- **trading**: ✅ DONE — repo + remote-url + local folder rename (Trading→trading, case-only via temp dir).
- **Docker**: cleaned to only rag-postgres (pg18+pgvector) + rag-cli_default network + pgvector image. All other containers/volumes/networks pruned.
- **Branches**: ✅ DONE — rag-cli + iterative-dev master→main (GitHub rename-endpoint + local). All repos now `main` (+`dev`). No `master`.
- **Phase E rules**: ✅ DONE — workers-1.md, tool-use.md, documentation.md, plugins.md updated + committed/pushed (`brunowinter8192/GlobalRules`). plugins.md catalog rewritten (5 skill-only plugins, no agents/MCP/commands). `_reference` convention → `-reference`. `~/.claude/shared-rules` confirmed canonical (own git repo, not plugin-synced). beads.md left untouched (slated for deletion in beads→gh migration).
- **Phase E feature**: PENDING — plugin-publish drift-validation (ERROR if skill folder/frontmatter not registered in manifest, OR registered without source; match key = skill name; user's 2-error example) + remove dead MCP-kill step (step 8, no plugin has MCP anymore). File: `~/Documents/ai/Meta/iterative-dev/bin/plugin-publish`. Full spec in tooling.md.
- **monitor-cc**: GitHub repo `ClaudeCode-Monitor`→`monitor-cc` + remote-url DONE (Opus, RECAP). REMAINS for USER: local folder `Monitor_CC`→`monitor-cc` (`cd ~/Documents/ai && mv Monitor_CC monitor-cc` from a FRESH session, outside the dir — underscore→hyphen+case, not case-only, so direct mv works) + CC restart (loads the renamed plugins/skills).
- **RAG re-index (update_docs) DEFERRED**: `embedding-8b` didn't start in 90s (cold-load timeout after docker/folder churn; PID 61300 RUNNING-but-UNHEALTHY + "No managed servers" → native llama-server likely orphaned from the OLD path `/MCP/RAG/`). Monitor_CC OldThemes are COMMITTED (git) but NOT yet indexed into `monitor-cc-docs`. Next session from the `monitor-cc` folder: restart RAG servers clean from `cli/rag-cli` (kill stale PIDs 61300/94605 or `rag-cli server restart embedding-8b`), then `rag-cli update_docs .`.
