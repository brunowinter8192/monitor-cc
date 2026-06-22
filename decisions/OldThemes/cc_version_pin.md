# CC Version Pin — proxy-launched Claude Code (2026-05-30)

## IST (Stand 2026-06-22)
Mains + Workers laufen auf gepinntem **CC 2.1.176** (newest stable), kein Auto-Update. Bump-Kadenz: **monatlich auf newest stable**, kein Rollback-Behalten (nur aktuelle Version existiert).

**Pin-Konvention (etabliert, Historie 101→109→110→114→149→176):**
- Isolierte npm-Installation pro Version: `~/cc-cache-fix-<v>/node_modules/@anthropic-ai/claude-code/` — vanilla `npm install --prefix ~/cc-cache-fix-<v> @anthropic-ai/claude-code@<v>`. "cc-cache-fix" ist nur der Verzeichnisname (historisch); der eigentliche Cache-Fix macht der Proxy via cache_control-Override, KEIN Binary-Patch.
- Wrapper `~/.local/bin/claude-<v>`: setzt `DISABLE_AUTOUPDATER=1`, exec't `~/cc-cache-fix-<v>/.../bin/claude.exe "$@"`.
- **Mains:** `CLAUDE_BIN` Default in `src/claude_proxy_start.sh` → `${CLAUDE_BIN:-$HOME/.local/bin/claude-<v>}`. Überschreibbar via `CLAUDE_BIN` env (User startet `PATH="$HOME/.local/bin:$PATH" ./src/claude_proxy_start.sh --project <ROOT>`).
- **Workers:** spawnen über `tmux_spawn.sh` mit eigenem Default `${CLAUDE_BIN:-$HOME/.local/bin/claude-<v>}` (zwei Stellen: Zeile 510 `spawn_claude_worker` + 699 `worker_revive`) — NICHT bare `claude` (das war vor 2026-06 IST, ist überholt). `tmux_spawn.sh` lebt im iterative-dev-Plugin: Source `Meta/iterative-dev/src/spawn/tmux_spawn.sh`, Live-Cache `~/.claude/plugins/cache/brunowinter-plugins/iterative-dev/1.0.0/src/spawn/tmux_spawn.sh`. `worker-cli` (selbst im Cache) sourct die Cache-Kopie → Cache MUSS gesynct sein (via `plugin-publish`).
- **npm-global** (`~/.npm-global/bin/claude`): bare `claude` im Terminal des Users; ebenfalls auf `<v>` gehalten, damit nichts auf alter Version hängt. Workers brauchen es nicht mehr (nutzen den Wrapper über tmux_spawn.sh).
- Auto-Update global aus: env `DISABLE_AUTOUPDATER=1` (+ redundant im Wrapper).

## Update-Prozedur (Vorlage, monatlich auf newest stable)
0. Newest stable checken: `npm view @anthropic-ai/claude-code dist-tags` → `stable`-Tag nehmen (NICHT `latest`; die laufen auseinander).
1. `npm install --prefix ~/cc-cache-fix-<new> @anthropic-ai/claude-code@<new>` + Wrapper `~/.local/bin/claude-<new>` nach claude-<old>-Muster, `chmod +x`. (Orchestrator-Infra, kein Worker.)
2. `npm install -g @anthropic-ai/claude-code@<new>` (bare `claude` im Terminal).
3. `claude_proxy_start.sh`: `CLAUDE_BIN`-Default + Kommentar darüber auf `claude-<new>` (src/-Edit → Worker, monitor-cc).
4. `tmux_spawn.sh` Zeilen 510 + 699: `claude-<old>` → `claude-<new>` (src/-Edit → Worker, iterative-dev). Danach `plugin-publish` (rsync source→cache). plugin.json-Version NICHT bumpen — sonst wandert der Cache-Dir-Pfad und der hardcodierte worker-cli-Cache-Pfad (`iterative-dev/1.0.0`) bricht.
5. Alte Wrapper + `cc-cache-fix-<old>`-Dir LÖSCHEN (kein Rollback — nur aktuelle Version behalten). Laufende Prozesse überleben (gemapptes Binary).
6. Verify: `ls ~/.local/bin/claude-*` + `ls -d ~/cc-cache-fix-*` = nur `<new>`; `grep claude-<old>` in `claude_proxy_start.sh` + Cache-`tmux_spawn.sh` = leer. Live: neue Main-Session → Proxy-Log System-Block zeigt `cc_version=<new>`.

## 2026-05-30: 2.1.114 → 2.1.149
- Vorher: Mains gepinnt claude-114; Workers bare `claude` = npm-global 2.1.119 (Drift). Newest: latest 2.1.158, stable 2.1.149 → **149 (stable) gewählt**.
- Motivation: kontrollierte, stabile Version, damit System-Prompt-/Reminder-/Message-Änderungen ab nächster Session sauber im Monitor beobachtbar sind (nicht durch Auto-Update-Drift verwischt).
- Laufende Session blieb 2.1.114 (Effekt greift erst für neue Mains/Workers).

## 2026-06-22: 2.1.149 → 2.1.176
- npm dist-tags: stable **2.1.176**, latest/next 2.1.185 → **176 (stable) gewählt**. Kadenz ab jetzt monatlich auf newest stable.
- User-Entscheidung: **kein Rollback-Behalten mehr** — alle Pre-Versionen löschen, nur aktuelle (176) behalten. Damit npm-global mitgezogen (bare `claude` = 176); die frühere "mitziehen?"-Frage entfällt.
- Ausgeführt: `cc-cache-fix-176` + Wrapper `claude-176` installiert; `claude_proxy_start.sh` (monitor-cc dev, commit 3391fa3) + `tmux_spawn.sh` Zeilen 510/699 (iterative-dev main, commit 3c8f408 → `plugin-publish`, Cache-Version 1.0.0 unverändert) auf claude-176; `claude-149`-Wrapper + `cc-cache-fix-149` gelöscht.
- Doku-Korrektur: frühere IST-Behauptung "Workers laufen bare `claude` aus PATH" war überholt — Workers spawnen seit der 114→149-Runde (proxy_tool_stripping, 2026-06-02) über `tmux_spawn.sh` mit dem claude-<v>-Wrapper, nicht bare.
- Laufende Session blieb 2.1.149 (Effekt greift erst für neue Mains/Workers).

## Logging-Gate (verifiziert — warum Monitor-Beobachtung reicht)
Der Proxy loggt nach `src/logs/api_requests_<id>.jsonl` das **modified_payload** (= exakt was an die API geht) als Feld `raw_payload` — gebaut in `_build_entry()` (`src/proxy/logging.py`), aufgerufen mit `modified_payload` im `request()`-Hook von `src/proxy/addon.py` (nach allen Strip-/Inject-Schritten). Gestripptes bleibt in separaten Feldern erhalten: `stripped_msg_originals`, `original_system2_text`, `stripped_sys3_original`, `stripped_tool_descs_originals` + `modifications`-Liste.
- **Folge:** Nichts geht verloren; "was an die API geht" ist 1:1 im Monitor. **User-Entscheidung:** kugelsichere Pre-Modification-Original-Erfassung NICHT nötig — `raw_payload` (= API-Wahrheit) reicht für die Beobachtung.
- Beleg: 46/139 Records eines Opus-Logs mit `<system-reminder>` im raw_payload; Haupt-Requests mit 3-Block-System-Prompt inkl. `x-anthropic-billing-header: cc_version=...`.

## Quellen
- npm dist-tags `@anthropic-ai/claude-code` (stable/latest/next), abgefragt 2026-05-30 + 2026-06-22 (stable 2.1.176).
- `tmux_spawn.sh` (Worker-Pin, Zeilen 510/699), iterative-dev-Plugin (Source `Meta/iterative-dev`, Cache `iterative-dev/1.0.0`); `plugin-publish` (rsync source→cache).
- `src/proxy/addon.py` (`request()`-Hook, `modified_payload`), `src/proxy/logging.py` (`_build_entry`, `raw_payload`).
- `src/claude_proxy_start.sh` (`CLAUDE_BIN`-Default), `~/.local/bin/claude-<v>`-Wrapper.
