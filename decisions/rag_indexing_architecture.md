# RAG Indexing Architecture

## Status Quo (IST)

Monitor_CC nutzt zwei separate Indexing-Pfade der RAG-Infrastruktur. Welcher Pfad gilt hängt ab davon ob Content im Projekt-Repo lebt oder zentral in der RAG-Infrastruktur.

**Pfad 1 — project-local** via `.rag-docs.json` am Repo-Root + `rag-cli update_docs .`. Hash-basierte Sync gegen die im Manifest deklarierten Globs. Files leben IM Projekt-Repo. Multi-Collection-Format erlaubt mehrere Collections pro Projekt. Wird bei jedem Session-Recap ausgeführt um Doku-Änderungen einzusyncen.

**Pfad 2 — central reference** via `python workflow.py index-dir --input <data/documents/<collection>>` im RAG-Projekt. Files leben in `Meta/ClaudeCode/MCP/RAG/data/documents/<collection_name>/`, dort gitignored (`data/` im RAG-`.gitignore`). Collection-Name = Directory-Name. Wird einmalig pro Reference-Material-Hinzufügung gefahren, nicht hash-synced.

Monitor_CC hat aktuell drei Collections:

| Collection | Pfad | Chunks | Inhalt |
|---|---|---|---|
| Monitor_CC-meta | local via .rag-docs.json | 185 | DOCS.md (22), decisions/*.md (8), sources/sources.md |
| Monitor_CC-features | local via .rag-docs.json | 125 | decisions/OldThemes/<topic>/*.md (14 files in 11 Subfoldern) |
| Monitor_reference | central via index-dir | 337 | 88 Anthropic API Doc Mirrors in `Meta/.../Monitor_reference/` |

`.rag-docs.json` Manifest enthält nur zwei Collections (-meta + -features). Die dritte (Monitor_reference) ist nicht im Manifest weil ihre Files nicht im Repo leben — sie wird über den index-dir-Pfad gewartet.

## Evidenz

`/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/RAG/src/rag/sync.py:74-115` — `update_docs_workflow` walkt `.rag-docs.json` Globs, hash-syncs per `(collection, relative_path)`-Key, akzeptiert Single- oder Multi-Collection-Format.

`/Users/brunowinter2000/Documents/ai/Meta/ClaudeCode/MCP/RAG/workflow.py:99-200` — `index-dir`-Command nimmt `--input <directory>` Flag (NICHT positional), default `--collection` ist der Directory-Name. Skip-by-default via `indexed_files`-Hash. `.md` only, `.txt` Files werden nicht indexiert.

Session 2026-05-11 Lesson: die ersten 92 API-Mirror-Files lagen falscherweise in `Monitor_CC/sources/` flach. Worker `source-alloc` wurde mit dem Auftrag gespawnt diese in `Monitor_CC/sources/<topic>/`-Subfolder zu gruppieren und eine `Monitor_CC_reference` Collection via project-local Pfad aufzubauen. Beides falsch — generische API-Dokus haben keinen project-spezifischen Bezug und gehören in den central reference store, nicht ins Projekt-Repo. Korrektur: `mv` der 91 Files cross-repo nach `Meta/.../Monitor_reference/`, `git rm` in Monitor_CC, Collection via `workflow.py index-dir` neu aufgebaut. Worker-Commit wurde verworfen.

## Recommendation (SOLL)

Keep — kein Architektur-Change nötig. Drei Konventionen sollen aber konsistent eingehalten werden.

**Konvention 1: Was wohin gehört.** Generische externe Reference (Anthropic API Mirror, Paper-PDFs, Vendor-Docs ohne project-spezifischen Decision-Bezug) → central via `workflow.py index-dir`. Project-spezifische Docs (DOCS.md, decisions/, OldThemes-Narrative, sources.md als Index) → local via `.rag-docs.json`. Project-interne Research-Reports (z.B. RAM_research) sind decisions/-Material, gehen nach `decisions/OldThemes/<topic>/`, nicht nach sources/.

**Konvention 2: Collection-Naming.** Project-local: `<Project>-meta` und `<Project>-features`. Central Reference: `<Project>_reference` (mit Underscore statt Dash, peer-Konvention zu `RAG_reference`, `searxng_reference`). Monitor_CC weicht hier ab: die zentrale Collection heißt `Monitor_reference` ohne `_CC` weil bereits angelegt — beibehalten.

**Konvention 3: sources.md Status.** Files im central reference store kriegen Status `Indexed (RAG: <central_collection>)`. Project-local Reference-Files kriegen Status `Referenced` (keine Indexierung dort). External URLs/Repos die nicht gespiegelt sind: `Referenced` oder `Verified`. Forum-Sources (Reddit/HN): permanent `Referenced`, kein RAG-Index.

## Offene Fragen

`.txt` Files im central store werden vom `index-dir` `.md`-only Filter übersprungen — 3 Files betroffen (ExtendedThinking5.txt, ExtendedThinking6.txt, PDF_support1.txt). Akzeptiert weil .md-Geschwister den Inhalt abdecken. Falls perfekte Coverage gebraucht: index-dir um `.txt` erweitern oder Files in `.md` umbenennen.

Cache-Read-Cost beim mehrfach-pro-Session-Run von `rag-cli update_docs .`: nicht gemessen. Skip-by-default sollte zero-cost-Run nach Initial-Index sein, aber bei Doku-Edits werden alle geänderten Files re-embedded.

## Quellen

- `Meta/ClaudeCode/MCP/RAG/src/rag/sync.py` — update_docs implementation
- `Meta/ClaudeCode/MCP/RAG/workflow.py` — index-dir command (lines 99-200, 276-285)
- `Meta/ClaudeCode/MCP/RAG/sources/sources.md` — Reference-Pattern für strikte 5-Spalten-Tabelle (kein description column)
- `~/.claude/shared-rules/global/documentation.md` § "sources/sources.md" — Format-Spec + Status-Rules
- Session 2026-05-11 — empirisches Beispiel für die zwei-Pfad-Trennung
