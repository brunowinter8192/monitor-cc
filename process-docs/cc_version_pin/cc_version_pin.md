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

## 2026-07-20: 2.1.176 → 2.1.205
- npm dist-tags on 2026-07-20: `stable` 2.1.205, `latest`/`next` 2.1.215 → chose **2.1.205** (stable tag, not latest; 2.1.215 was bleeding-edge latest with the open post-compaction 1M→200k regression).
- Motivation — the trigger was the 1M-context question. Workers pinned to `claude-sonnet-5` were capped at 200k while the orchestrator on `claude-opus-4-8` got the full 1M, same proxy/auth/account. Root cause: CC 2.1.176 (2026-06-13) predates Sonnet 5 (shipped CC 2.1.197, 2026-06-30), so its internal context-window table has no `claude-sonnet-5` entry and falls back to a 200k budget — CC caps client-side before the API ever sees a >200k request. Not proxy, not auth, not entitlement (proven by Opus 4.8 getting 1M on the same stack).
- Evidence: `src/logs/api_errors.jsonl` held zero context/"too long" API errors (only 401/400/429/404); the worker died client-side at ~171k tokens (below 200k); the `claude-sonnet-5[1m]` suffix test produced a `not_found_error` 404, confirming the proxy forwards the model string verbatim. The proxy code touches neither `anthropic-beta` headers nor auth (headers pass through as CC sets them).
- Executed: `npm install --prefix ~/cc-cache-fix-205 @anthropic-ai/claude-code@2.1.205`; wrapper `~/.local/bin/claude-205` (claude-176 pattern, `DISABLE_AUTOUPDATER=1`); `npm install -g @anthropic-ai/claude-code@2.1.205`; `claude_proxy_start.sh` CLAUDE_BIN default → claude-205 (monitor-cc, via worker); `tmux_spawn.sh` lines 542 + 734 → claude-205 (iterative-dev main, via worker; the Update-Prozedur template's 510/699 had drifted to 542/734).
- Cache sync: copied the edited `tmux_spawn.sh` directly into the `iterative-dev/1.0.0` cache instead of running `plugin-publish` — `plugin-publish` bumps the plugin version, which would move the cache dir off `1.0.0` and break worker-cli's hardcoded cache path. plugin.json version left at 1.0.0.
- Deferred: deletion of the old `claude-176` wrapper + `cc-cache-fix-176` dir. The bump session itself stayed live on 2.1.176 (its binary is mmap'd and survives), so the 176 cleanup runs after that session ends, not during it.
- Running session stayed on 2.1.176 (effect applies only to new mains/workers started via `claude_proxy_start.sh` / `tmux_spawn.sh`).

## Logging-Gate (verifiziert — warum Monitor-Beobachtung reicht)
Der Proxy loggt nach `src/logs/api_requests_<id>.jsonl` das **modified_payload** (= exakt was an die API geht) als Feld `raw_payload` — gebaut in `_build_entry()` (`src/proxy/logging.py`), aufgerufen mit `modified_payload` im `request()`-Hook von `src/proxy/addon.py` (nach allen Strip-/Inject-Schritten). Gestripptes bleibt in separaten Feldern erhalten: `stripped_msg_originals`, `original_system2_text`, `stripped_sys3_original`, `stripped_tool_descs_originals` + `modifications`-Liste.
- **Folge:** Nichts geht verloren; "was an die API geht" ist 1:1 im Monitor. **User-Entscheidung:** kugelsichere Pre-Modification-Original-Erfassung NICHT nötig — `raw_payload` (= API-Wahrheit) reicht für die Beobachtung.
- Beleg: 46/139 Records eines Opus-Logs mit `<system-reminder>` im raw_payload; Haupt-Requests mit 3-Block-System-Prompt inkl. `x-anthropic-billing-header: cc_version=...`.

## Quellen
- npm dist-tags `@anthropic-ai/claude-code` (stable/latest/next), abgefragt 2026-05-30 + 2026-06-22 (stable 2.1.176).
- `tmux_spawn.sh` (Worker-Pin, Zeilen 510/699), iterative-dev-Plugin (Source `Meta/iterative-dev`, Cache `iterative-dev/1.0.0`); `plugin-publish` (rsync source→cache).
- `src/proxy/addon.py` (`request()`-Hook, `modified_payload`), `src/proxy/logging.py` (`_build_entry`, `raw_payload`).
- `src/claude_proxy_start.sh` (`CLAUDE_BIN`-Default), `~/.local/bin/claude-<v>`-Wrapper.
