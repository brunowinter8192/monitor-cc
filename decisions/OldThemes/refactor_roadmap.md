# Refactor Roadmap — Sequencing (2026-05-28)

## Decision

Vier Refactor/Fix-Themen laufen SEQUENTIELL, nicht parallel. Reihenfolge:

1. **Menubar** — Controller-Composition-Refactor (in flight)
2. **blank** — Desktop-Targeting Sidecar-Konsolidierung (Weg 2)
3. **Logging + Proxy** — unified Janitor + decisions/logging.md + count_tokens-Fix + Orphan-Cleanup
4. **Dolt** — bd↔dolt Lifecycle Hook-Fix

## Warum sequentiell, nicht parallel

- **Harte Abhängigkeit Menubar → blank:** blank Weg-2 (`desktop_allocation/D1_blank_sidecar_consolidation.md`) braucht, dass die Menubar ein `cwd → space_id`-Sidecar publiziert (Monitor_CC-Source-Änderung). Am saubersten *nach* dem Controller-Refactor in die dann klare Struktur eingehängt. blank kann nicht fertig werden bevor das Sidecar existiert.
- **Review-Last:** zwei parallele Refactor-Streams die beide auf `dev` mergen = doppelte Opus-Cross-Model-Review + verschränkte Merge-Topologie + höheres Regressionsrisiko. Sequentiell hält jeden Refactor auf sauberem dev-Stand verifizierbar bevor der nächste startet.
- **Menubar bereits in flight** (Steps 1-2 merged, 3 läuft, 4-6 pending) — erst fertigmachen für saubere Baseline.

## Stages

### 1. Menubar — Controller-Composition-Refactor
- OldThemes: `menubar_refactor_v1/`
- Status: Step 1 (Sessions) + Step 2 (Bead) merged; Step 3 (Queue) in flight; Steps 4 (PanelManager), 5 (Focus), 6 (Hotkey) pending.

### 2. blank — Desktop-Targeting Sidecar-Konsolidierung
- OldThemes: `desktop_allocation/D1_blank_sidecar_consolidation.md`
- Depends on: Stage 1 (Menubar publiziert cwd→space_id Sidecar).
- Scope: Menubar publiziert verifiziertes Detection-Result als Sidecar; blank `desktop_targeting.py` konsumiert es (fragile Namens-Match-Kette entfällt); blank-seitiges Logging für Worker-Spawn + File-Open; detect-before-disturb-Reorder.

### 3. Logging + Proxy — unified Janitor + count_tokens-Fix
- OldThemes (Prozess-Vorgeschichte): `log_janitor.md`, `audit_logging/architecture.md`; `decisions/pipe05_proxy_cache.md` (count-30 + Log-Naming)
- decisions (geplant, neu): `decisions/logging.md` — autoritatives Log-Inventar (Writer/Reader/Zweck/Format/Retention/Janitor), RAG-indexiert als Single Source.
- Scope:
  - **Unified Janitor:** verstreute Logik (`claude_proxy_start.sh` count-30, `log_janitor.py` 7-Tage-Records, `gpu_pane/status.py` TimedRotating, `ccwrap/ansi_log.py` keep-count) in `src/log_janitor.py` als deklaratives LogSpec-Registry zusammenführen. Zwei Trigger bleiben sinnvoll (Proxy-Start für api_requests, Monitor-24h-Tick für Rest).
  - **count_tokens-Proxy-Fix:** `_is_messages_request` (`src/proxy/addon.py:341-343`) matcht via `path.startswith("/v1/messages")` auch `/v1/messages/count_tokens`. Folge: `_inject_model_override` (`src/proxy/inject_helpers.py:27-28`) injiziert `max_tokens` + `output_config.effort` aus `proxy_rules.json` auch in count_tokens-Vorabprüfungen → 400 `max_tokens: Extra inputs are not permitted` (99 von 102 Error-Payloads). Echte `/v1/messages`-Generierungs-Requests sind unbetroffen (max_tokens dort legal, 200). **Fix (vereinfacht):** count_tokens KOMPLETT aus der Pipeline ausnehmen (`_is_messages_request` exakt auf Messages-Endpoint matchen, nicht Präfix) → CCs count_tokens geht unverändert durch, keine Injektion, kein 400, keine Datei-Flut. Kein Feld-Stripping nötig, weil wir die count_tokens-Zählung nirgends konsumieren (s.u.).
  - **Token-Counting-Audit (Befund 2026-05-28):** Production-`src/` hat KEIN `tiktoken`, KEINE count_tokens-Response-Konsumierung. Autoritative CC/CR-Zahlen kommen aus Session-JSONL-`usage` (`jsonl/jsonl_extractors.py` → `token_pane`/`proxy_display`/`worker_pane`). Einzige Eigen-Schätzung: `_chars_to_tokens` (chars/3.5) in `proxy_display` für "~Ntok"-Display-Labels — char-basiert, modellunabhängig, keine Buchhaltung. Offen: ob dieses Display-Heuristik bleibt oder raus. count_tokens-Pre-Flight ist CCs eigener Call, von uns nicht konsumiert → kann unangetastet durchlaufen.
  - **api_error_payload:** Proxy-Writer (`src/proxy/addon.py:235`) von Einzeldatei-pro-Fehler auf rollende `api_errors.jsonl` umstellen → eliminiert Datei-Flut by-design + wird vom bestehenden 7-Tage-Record-Janitor abgedeckt.
  - **Orphan-Cleanup:** `tool_use_errors.jsonl` (Legacy, kein Writer mehr) + verwaiste `.proxy_live_*`-Verzeichnisse toter Sessions.
- count-30-Retention für api_requests: bewusst KEINE Größen-Begrenzung — akzeptiert (User-Entscheidung 2026-05-28), 16GB kein Problem.

### 4. Dolt — bd↔dolt Lifecycle Hook-Fix
- OldThemes: noch keine.
- Root-Cause (Befund 2026-05-28): KEIN Dolt-Crash (Log sauber, kein panic/signal/OOM), KEIN Idle-Shutdown (idle-timeout=0 in `.beads/config.yaml`). Mechanismus: TIME_WAIT-Stau auf fixem Port 53351 (Menubar 7s-Polling + Worker + Opus = Connection-Churn) + Orphan-Dolt-Prozesse (2x live beobachtet, einer auf globaler Homebrew-Config) + bd lazy Auto-Start re-bindet den verstopften Port im engen 10s-Timeout → Bind-Fail → client-seitiger bd Circuit-Breaker öffnet. Verwandt: blank-Repo Bead-Thema "bd/Dolt auto-start fragility" (port collisions + 10s timeout + no fallback).
- Observability: Dolt-Bash-Fehler liegen bereits in `tool_errors.jsonl` + Warnings-Pane.
- Scope: Hook-basierte Koordination (Single-Owner / Health-Detect + Recover, z.B. `.port`-Datei löschen damit bd frischen Port statt TIME_WAIT-Port nimmt). Fix-Design pending.
