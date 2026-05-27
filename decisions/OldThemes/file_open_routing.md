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

## SOLL (pending Dispatch)

Extension-basiertes Routing per Switch:
- `.md` / `.markdown` / `.txt` → `open -a CotEditor "$f"` (oder via CLI-Shim `cot "$f"`)
- Alles andere → bestehendes `open "$f"`

**Verifiziert installiert:**
- `/Applications/CotEditor.app` ✅
- `/opt/homebrew/bin/cot` (CLI-Shim) ✅

Implementierung im selben `show`-Script. Cross-Project-Edit (lebt in `Meta/blank/`, nicht in Monitor_CC) — Opus editiert direkt (per Worker-Project-Scope-Regel: cross-project changes sind Opus-Surface, kein Worker).

## Desktop-Awareness (deferred zu desktop_allocation Etappe 4)

Heute öffnet `open` immer auf dem aktiven Space. Die "open on caller's Desktop"-Variante hängt von:
- Detection-Pipeline aus `desktop_allocation/00_design_overview.md` Etappe 1
- Knowledge welche Main-Session den Show-Call ausgelöst hat (über PARENT-PID/CC-Session-ID propagation? offener Punkt)
- Window-Polling-Strategie nach `open` (warten bis App-Window auftaucht, dann via `CGSMoveWindowsToManagedSpace` zum Ziel-Desktop verschieben)

Etappe 4 Design wird in `desktop_allocation/` weiterentwickelt sobald Etappe 1 verifiziert.

## Quellen

- `/Users/brunowinter2000/.local/bin/show` (Symlink)
- `/Users/brunowinter2000/Documents/ai/Meta/blank/bin/show` (Source)
- `/Applications/CotEditor.app` (Editor)
- `/opt/homebrew/bin/cot` (CLI-Shim, falls vorzuziehen vor `open -a`)
