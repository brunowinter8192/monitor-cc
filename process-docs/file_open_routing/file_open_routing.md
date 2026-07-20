# File-Open Routing — CotEditor für .md/.txt (2026-05-27)

## Scope

Die `show <file>` Tool (Wrapper-Script unter `~/.local/bin/show`, Source: `Meta/blank/bin/show`) ist der zentrale Path um Files für den User zu öffnen — vom Menubar, von Workers, von Opus. Aktuell delegiert sie blind an macOS `open` welches anhand File-Type den Default-Handler picks (Preview für PDF/PNG, TextEdit für txt, Xcode für py, etc.).

User wants File-Type-Routing: `.md` und `.txt` IMMER in **CotEditor**, andere Typen unverändert beim Default.

## IST

`~/.local/bin/show` (Symlink → `/Users/brunowinter2000/Documents/ai/Meta/blank/bin/show`):

```bash
for f in "$@"; do
  f="${f/#\~/$HOME}"
  [[ "$f" != /* ]] && f="$(pwd)/$f"
  [ ! -e "$f" ] && { echo "show: not found: $f" >&2; exit 1; }
  open "$f"
  echo "opened: $f"
done
```

Kein File-Type-Routing. Kein Desktop-Awareness.

## Implementation (2026-05-27, Meta/blank/ commit cfd0d14)

**Extension-Routing in `Meta/blank/bin/show`:**
- `.md` / `.markdown` / `.txt` → `open -a "CotEditor" "$f"` (case-insensitive Extension-Check via `tr '[:upper:]' '[:lower:]'`)
- Alles andere → bestehendes `open "$f"` (macOS Default-Handler)

**Desktop-Awareness IST mit-implementiert** (nicht mehr deferred zu Etappe 4):
- Nach `open` ruft das Script `python3 desktop_targeting.py wait-and-move "$PPID" "<app_name>" 4` im Hintergrund auf
- Helper findet caller's Main-Session via Parent-PID-Walk zum nächsten `claude` Ancestor → dessen cwd via lsof → Lookup in Monitor_CC's `ghostty_cwd_uuid.json` → AppleScript-Window-Name → CGWindowList-Match → SpaceID via `CGSCopySpacesForWindows`
- Snapshot der bestehenden Windows der Ziel-App + Polling 4s auf neue Windows → `CGSMoveWindowsToManagedSpace` zu caller's Space-ID
- Best-effort: failure silent (File öffnet trotzdem, nur landet auf aktivem Desktop statt Ziel)
- Für unbekannte App-Handler (alles außer .md/.txt) übergibt show `app_name=""` → Helper pollt cross-app (excl. System-Apps Dock/WindowServer/etc.)

**Helper-Modul:** `Meta/blank/src/desktop/desktop_targeting.py` (CGS-Bridging extrahiert aus Monitor_CC dev/desktop_detection/01_probe.py, plus `CGSMoveWindowsToManagedSpace` für die Move-Action).

**Verifiziert installiert:**
- `/Applications/CotEditor.app` ✅
- `/opt/homebrew/bin/cot` (CLI-Shim) ✅

## Pending

- Live-Test sobald `plugin-publish` durchgelaufen ist (commit `cfd0d14` ist lokal, Plugin-Cache hat noch alte Version)
- Cross-App-Polling-Risiko: wenn während der 4s Polling-Window ein unrelated App-Window auftaucht (z.B. Notification) wird das fälschlich mit-verschoben. Niedrige Wahrscheinlichkeit, akzeptiert für jetzt

## Quellen

- `/Users/brunowinter2000/.local/bin/show` (Symlink)
- `/Users/brunowinter2000/Documents/ai/Meta/blank/bin/show` (Source)
- `/Applications/CotEditor.app` (Editor)
- `/opt/homebrew/bin/cot` (CLI-Shim, falls vorzuziehen vor `open -a`)
