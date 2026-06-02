# Naming Unification — RAG Collections

Part of Bead uoyx. Collections must follow the source-name schema, all hyphens.

## Rename mechanism (cheap — no reindex)

Collection name = string column `collection` in Postgres tables `documents` + `indexed_files` (grep: `src/rag/db.py`, `search_primitives.py`, `indexer.py`, `sync.py`). Rename =
1. SQL `UPDATE documents SET collection='<new>' WHERE collection='<old>'` + same on `indexed_files`. Embeddings untouched.
2. For reference/external collections: rename `data/documents/<old>/` → `<new>/` (folder name = collection fallback, `indexer.py:136 collection = data.get("collection", path.parent.name)`).
3. For `-docs` collections: update `"collection"` field in each project's `.rag-docs.json`.

rag-cli has NO `rename` command (surface: search_hybrid, list_collections, list_documents, progress, read_document, delete, status, update_docs, server). Options: add a `rename` subcommand to rag-cli (clean, reusable, cross-project edit in RAG/cli.py) OR one-off SQL. **Verify** no separate collections-registry table beyond documents/indexed_files before bulk rename.

## Current collections (rag-cli list_collections)

| Collection (DB) | Chunks | data/documents folder | → target |
|---|---|---|---|
| `gh_reference` | 7146 | `gh_reference` | `gh-cli-reference` |
| `github_discussions` | 286 | `github_discussions` | `gh-cli-discussions` |
| `github-docs` | 84 | — | `gh-cli-docs` (verify what it indexes) |
| `github_issues` | 1835 | `github_issues` | `gh-cli-issues` |
| `Monitor_CC-docs` | 920 | — | `monitor-cc-docs` |
| `Monitor_CC_reference` | 337 | `Monitor_CC_reference` | `monitor-cc-reference` |
| `RAG-docs` | 201 | — | `rag-cli-docs` |
| `RAG_reference` | 338 | `RAG_reference` | `rag-cli-reference` |
| `Reddit-docs` | 118 | — | `reddit-cli-docs` |
| `reddit_posts` | 123 | `reddit_posts` | `reddit-cli-posts` |
| `Reddit_reference` | 64 | `reddit_reference` (case ≠) | `reddit-cli-reference` |
| `searxng-docs` | 408 | — | `searxng-cli-docs` |
| `searxng_reference` | 1034 | `searxng_reference` | `searxng-cli-reference` |
| `Trading-docs` | 262 | — | `trading-docs` |
| `Trading_reference` | 7053 | `Trading_reference` | `trading-reference` |

Separator decision: `-reference` (hyphen), unified per "always - statt _".

## Resolved (user 2026-06-02)

Schema reads off the existing suffix — no ambiguity:
- `github-docs` → `gh-cli-docs`
- `reddit_reference` folder (lowercase) + `Reddit_reference` collection → both unify to `reddit-cli-reference`
- `test_db` → `test_db` UNCHANGED (test fixture, keep exact name incl. underscore)
- `wise2627_reference`: folder-only (no DB collection in the list) → rename folder to `wise2627-reference`; no SQL update needed.

## Rule references

Collection names referenced in 6 shared-rules files (update in sync with rename, NOT before): `opus/workers-1.md`, `global/tool-use.md`, `global/documentation.md`, `situational/monitor-standards.md`, `situational/monitor-dev-verification.md`, `situational/plugins.md`. Plus each project's `.rag-docs.json`.

## RAG project folder rename — docker bind-mount (NOT live-renameable)

DB physical storage: compose mounts `./data/postgres:/var/lib/postgresql` — a BIND MOUNT to the local folder, NOT a named volume. All embeddings live in `RAG/data/postgres/` and TRAVEL with the folder on rename — no data loss, no reindex. Container name `rag-postgres` is PINNED in compose (not dir-derived) → rename does not orphan it. Connection: rag-cli → `localhost:5433` (host port map), folder-independent.

The running container holds the OLD absolute bind-mount path → cannot rename live. Safe procedure for `RAG` → `cli/rag-cli`:
1. `docker compose down` (rag-postgres briefly offline → no RAG search during this window)
2. `mv` folder (`data/postgres` moves with it)
3. update `.env` `RAG_PROJECT_ROOT=<new abs path>`
4. `docker compose up -d` from new location → re-mounts new `./data/postgres`, same container, same data
5. update wrappers + paths

Collection renames (SQL UPDATE) are independent of the folder rename — done on the LIVE running DB, no downtime.

Stale: orphaned named volume `rag_rag_postgres_data` (from an older named-volume compose config) — unused now (current = bind-mount). Optional cleanup.

Same docker check needed for `Trading` before its rename — it has `tpch-postgres` container + `tradbot_tradbot_pgdata` named volume; verify compose project name is explicit (not dir-derived) before `mv`.
