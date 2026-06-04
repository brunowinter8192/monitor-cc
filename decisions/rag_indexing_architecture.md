# RAG Indexing Architecture

## Status Quo (IST)

Monitor_CC nutzt zwei separate Indexing-Pfade der RAG-Infrastruktur. Welcher Pfad gilt hängt ab davon ob Content im Projekt-Repo lebt oder zentral in der RAG-Infrastruktur.

**Pfad 1 — project-local** via `.rag-docs.json` am Repo-Root + `rag-cli update_docs .`. Hash-basierte Sync gegen die im Manifest deklarierten Globs. Files leben IM Projekt-Repo. Multi-Collection-Format erlaubt mehrere Collections pro Projekt. Wird bei jedem Session-Recap ausgeführt um Doku-Änderungen einzusyncen.

**Pfad 2 — central reference** via `rag-cli index --collection <name>` im RAG-Projekt. Files leben in `Meta/ClaudeCode/cli/rag-cli/data/documents/<collection_name>/`, dort gitignored (`data/` im RAG-`.gitignore`). Collection-Name = Subdirectory-Name. Wird einmalig pro Reference-Material-Hinzufügung gefahren, nicht hash-synced. `workflow.py` existiert nicht mehr — Einstiegspunkt ist ausschliesslich `cli.py` (via `rag-cli` wrapper).

Monitor_CC hat aktuell drei Collections:

| Collection | Pfad | Chunks | Inhalt |
|---|---|---|---|
| Monitor_CC-meta | local via .rag-docs.json | 185 | DOCS.md (22), decisions/*.md (8) |
| Monitor_CC-features | local via .rag-docs.json | 125 | decisions/OldThemes/<topic>/*.md (14 files in 11 Subfoldern) |
| Monitor_reference | central via rag-cli index | 337 | 88 Anthropic API Doc Mirrors in `Meta/.../Monitor_reference/` |

`.rag-docs.json` Manifest enthält nur zwei Collections (-meta + -features). Die dritte (Monitor_reference) ist nicht im Manifest weil ihre Files nicht im Repo leben — sie wird über den `rag-cli index`-Pfad gewartet.

## Evidenz

`cli/rag-cli/src/rag/sync.py` — `sync_docs_workflow` walkt `.rag-docs.json` Globs, hash-synced per `(collection, document)`-Key, akzeptiert Single- oder Multi-Collection-Format (via `update_docs` subcommand in `cli.py`).

`cli/rag-cli/cli.py:95-101` — `index` subcommand nimmt `--collection` (required), liest ausschliesslich `data/documents/<collection>/*.md`. Kein `--input`-Flag; `workflow.py` existiert nicht mehr.

Session 2026-05-11 Lesson: die ersten 92 API-Mirror-Files lagen falscherweise in `Monitor_CC/sources/` flach. Korrektur: `mv` der 91 Files cross-repo nach `Meta/.../Monitor_reference/`, `git rm` in Monitor_CC, Collection via `workflow.py index-dir` neu aufgebaut (historisch — seither durch rag-cli Konsolidierung abgelöst).

Session 2026-06-10: `workflow.py` bei rag-cli Konsolidierung entfernt. gh-cli (`index_issues/releases/discussions.py`) und searxng SKILL.md haben toten `workflow.py index-dir`-Aufruf durch `rag-cli index --collection <name>` ersetzt. Input-Model unverändert: gh-cli schreibt MDs nach `data/documents/<collection>/` (war schon korrekt), searxng setzt die Ausgabe-Directory auf `$RAG_ROOT/data/documents/$COLLECTION` direkt.

## Recommendation (SOLL)

Keep — kein Architektur-Change nötig. Drei Konventionen sollen konsistent eingehalten werden.

**Konvention 1: Was wohin gehört.** Generische externe Reference (Anthropic API Mirror, Paper-PDFs, Vendor-Docs ohne project-spezifischen Decision-Bezug) → central via `rag-cli index --collection`. Project-spezifische Docs (DOCS.md, decisions/, OldThemes-Narrative) → local via `.rag-docs.json`. Project-interne Research-Reports (z.B. RAM_research) sind decisions/-Material, gehen nach `decisions/OldThemes/<topic>/`.

**Konvention 2: Collection-Naming.** Project-local: `<Project>-meta` und `<Project>-features`. Central Reference: `<Project>_reference` (mit Underscore statt Dash, peer-Konvention zu `RAG_reference`, `searxng_reference`). Monitor_CC weicht hier ab: die zentrale Collection heißt `Monitor_reference` ohne `_CC` weil bereits angelegt — beibehalten.

## Offene Fragen

`.txt` Files im central store werden vom `index-dir` `.md`-only Filter übersprungen — 3 Files betroffen (ExtendedThinking5.txt, ExtendedThinking6.txt, PDF_support1.txt). Akzeptiert weil .md-Geschwister den Inhalt abdecken. Falls perfekte Coverage gebraucht: index-dir um `.txt` erweitern oder Files in `.md` umbenennen.

Cache-Read-Cost beim mehrfach-pro-Session-Run von `rag-cli update_docs .`: nicht gemessen. Skip-by-default sollte zero-cost-Run nach Initial-Index sein, aber bei Doku-Edits werden alle geänderten Files re-embedded.

## Quellen

- `cli/rag-cli/src/rag/sync.py` — update_docs / sync_docs_workflow implementation
- `cli/rag-cli/cli.py` — index subcommand (lines 95-101, 198-323)
- Session 2026-05-11 — empirisches Beispiel für die zwei-Pfad-Trennung
- Session 2026-06-10 — rag-cli Konsolidierung (workflow.py entfernt, index-command-Wechsel)
