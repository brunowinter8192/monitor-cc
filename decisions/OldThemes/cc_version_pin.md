# CC Version Pin — proxy-launched Claude Code (2026-05-30)

## IST (Stand 2026-05-30)
Mains + Workers laufen auf gepinntem **CC 2.1.149** (stable), kein Auto-Update.

**Pin-Konvention (etabliert, Historie 101→109→110→114→149):**
- Isolierte npm-Installation pro Version: `~/cc-cache-fix-<v>/node_modules/@anthropic-ai/claude-code/` — vanilla `npm install --prefix ~/cc-cache-fix-<v> @anthropic-ai/claude-code@<v>`. "cc-cache-fix" ist nur der Verzeichnisname (historisch); der eigentliche Cache-Fix macht der Proxy via cache_control-Override, KEIN Binary-Patch.
- Wrapper `~/.local/bin/claude-<v>`: setzt `DISABLE_AUTOUPDATER=1`, exec't `.../bin/claude.exe "$@"`.
- **Mains:** `CLAUDE_BIN` Default in `src/claude_proxy_start.sh` → `${CLAUDE_BIN:-$HOME/.local/bin/claude-<v>}`. Überschreibbar via `CLAUDE_BIN` env (User startet `PATH="$HOME/.local/bin:$PATH" ./src/claude_proxy_start.sh --project <ROOT>`).
- **Workers:** starten bare `claude` aus PATH → npm-global (`~/.npm-global/bin/claude`). Worker-Spawn liegt in `Meta/blank/bin/worker-cli` (sourced iterative-dev `tmux_spawn.sh`). Cache-Fix kommt über den Worker-Proxy (Port 8085) — kein Spezial-Build nötig.
- Auto-Update global aus: env `DISABLE_AUTOUPDATER=1` (+ redundant im Wrapper).

## Update-Prozedur (Vorlage)
1. `npm install --prefix ~/cc-cache-fix-<new> @anthropic-ai/claude-code@<new>` + Wrapper `~/.local/bin/claude-<new>` nach claude-114/149-Muster, `chmod +x`.
2. `npm install -g @anthropic-ai/claude-code@<new>` (Workers' bare claude).
3. `claude_proxy_start.sh`: `CLAUDE_BIN`-Default + Kommentar darüber auf `claude-<new>` (src/-Edit → Worker).
4. Alte Wrapper + `cc-cache-fix-<old>`-Dirs BEHALTEN (Rollback).
5. Verify: neue Main-Session → Proxy-Log System-Block zeigt `cc_version=<new>`.

## 2026-05-30: 2.1.114 → 2.1.149
- Vorher: Mains gepinnt claude-114; Workers bare `claude` = npm-global 2.1.119 (Drift). Newest: latest 2.1.158, stable 2.1.149 → **149 (stable) gewählt**.
- Motivation: kontrollierte, stabile Version, damit System-Prompt-/Reminder-/Message-Änderungen ab nächster Session sauber im Monitor beobachtbar sind (nicht durch Auto-Update-Drift verwischt).
- Laufende Session blieb 2.1.114 (Effekt greift erst für neue Mains/Workers).

## Logging-Gate (verifiziert — warum Monitor-Beobachtung reicht)
Der Proxy loggt nach `src/logs/api_requests_<id>.jsonl` das **modified_payload** (= exakt was an die API geht) als Feld `raw_payload` — gebaut in `_build_entry()` (`src/proxy/logging.py`), aufgerufen mit `modified_payload` im `request()`-Hook von `src/proxy/addon.py` (nach allen Strip-/Inject-Schritten). Gestripptes bleibt in separaten Feldern erhalten: `stripped_msg_originals`, `original_system2_text`, `stripped_sys3_original`, `stripped_tool_descs_originals` + `modifications`-Liste.
- **Folge:** Nichts geht verloren; "was an die API geht" ist 1:1 im Monitor. **User-Entscheidung:** kugelsichere Pre-Modification-Original-Erfassung NICHT nötig — `raw_payload` (= API-Wahrheit) reicht für die Beobachtung.
- Beleg: 46/139 Records eines Opus-Logs mit `<system-reminder>` im raw_payload; Haupt-Requests mit 3-Block-System-Prompt inkl. `x-anthropic-billing-header: cc_version=...`.

## Quellen
- npm dist-tags `@anthropic-ai/claude-code` (stable/latest/next), abgefragt 2026-05-30.
- `src/proxy/addon.py` (`request()`-Hook, `modified_payload`), `src/proxy/logging.py` (`_build_entry`, `raw_payload`).
- `src/claude_proxy_start.sh` (`CLAUDE_BIN`-Default), `~/.local/bin/claude-<v>`-Wrapper.
