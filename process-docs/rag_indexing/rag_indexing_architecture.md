# RAG Indexing Architecture

## State as of this audit

Monitor_CC uses two separate indexing paths of the RAG infrastructure. Which path applies depends on whether content lives in the project repo or centrally in the RAG infrastructure.

**Path 1 — project-local** via `.rag-docs.json` at the repo root + `rag-cli update_docs .`. Hash-based sync against the globs declared in the manifest. Files live IN the project repo. The multi-collection format allows several collections per project. Run on every session recap to sync in doc changes.

**Path 2 — central reference** via `rag-cli index --collection <name>` in the RAG project. Files live in `Meta/ClaudeCode/cli/rag-cli/data/documents/<collection_name>/`, gitignored there (`data/` in RAG's `.gitignore`). Collection name = subdirectory name. Run once per reference-material addition, not hash-synced. `workflow.py` no longer exists — the entry point is exclusively `cli.py` (via the `rag-cli` wrapper).

Monitor_CC currently has three collections:

| Collection | Path | Chunks | Content |
|---|---|---|---|
| Monitor_CC-meta | local via .rag-docs.json | 185 | DOCS.md (22), process-docs/*.md (8) |
| Monitor_CC-features | local via .rag-docs.json | 125 | process-docs area docs (14 files in 11 subfolders) |
| Monitor_reference | central via rag-cli index | 337 | 88 Anthropic API doc mirrors in `Meta/.../Monitor_reference/` |

The `.rag-docs.json` manifest contains only two collections (-meta + -features). The third (Monitor_reference) is not in the manifest because its files don't live in the repo — it's maintained via the `rag-cli index` path.

## Evidence

`cli/rag-cli/src/rag/sync.py` — `sync_docs_workflow` walks `.rag-docs.json` globs, hash-syncs per `(collection, document)` key, accepts single- or multi-collection format (via the `update_docs` subcommand in `cli.py`).

`cli/rag-cli/cli.py:95-101` — the `index` subcommand takes `--collection` (required), reads exclusively `data/documents/<collection>/*.md`. No `--input` flag; `workflow.py` no longer exists.

Session 2026-05-11 lesson: the first 92 API-mirror files sat incorrectly flat in `Monitor_CC/sources/`. Correction: `mv` the 91 files cross-repo to `Meta/.../Monitor_reference/`, `git rm` in Monitor_CC, rebuilt the collection via `workflow.py index-dir` (historical — since superseded by the rag-cli consolidation).

Session 2026-06-10: `workflow.py` removed during the rag-cli consolidation. gh-cli (`index_issues/releases/discussions.py`) and searxng's SKILL.md had their dead `workflow.py index-dir` call replaced with `rag-cli index --collection <name>`. Input model unchanged: gh-cli writes MDs to `data/documents/<collection>/` (was already correct), searxng sets the output directory directly to `$RAG_ROOT/data/documents/$COLLECTION`.

## Recommendation (target state)

Keep — no architecture change needed. Three conventions should be kept consistent.

**Convention 1: what goes where.** Generic external reference (Anthropic API mirror, paper PDFs, vendor docs with no project-specific decision context) → central via `rag-cli index --collection`. Project-specific docs (DOCS.md, process-docs, area-doc narratives) → local via `.rag-docs.json`. Project-internal research reports (e.g. RAM_research) are process-docs material, go into `process-docs/<topic>/`.

**Convention 2: collection naming.** Project-local: `<Project>-meta` and `<Project>-features`. Central reference: `<Project>_reference` (underscore instead of dash, matching the peer convention of `RAG_reference`, `searxng_reference`). Monitor_CC deviates here: the central collection is named `Monitor_reference` without `_CC` because it was already created that way — kept as-is.

## Open Questions

`.txt` files in the central store are skipped by the `index-dir` `.md`-only filter — 3 files affected (ExtendedThinking5.txt, ExtendedThinking6.txt, PDF_support1.txt). Accepted because `.md` siblings cover the content. If perfect coverage is needed: extend index-dir to `.txt` or rename the files to `.md`.

Cache-read cost of running `rag-cli update_docs .` multiple times per session: not measured. Skip-by-default should make it a zero-cost run after the initial index, but doc edits cause all changed files to be re-embedded.

## Sources

- `cli/rag-cli/src/rag/sync.py` — update_docs / sync_docs_workflow implementation
- `cli/rag-cli/cli.py` — index subcommand (lines 95-101, 198-323)
- Session 2026-05-11 — empirical example of the two-path separation
- Session 2026-06-10 — rag-cli consolidation (workflow.py removed, index-command switch)
