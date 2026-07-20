# C3 — Detection Logging: Log-Pfad-Bug + Transition-Observability

## Log-Pfad-Bug (menubar_log.py)

### Root Cause

`menubar_log.py:5-6` (pre-fix):
```python
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MENUBAR_LOG  = PROJECT_ROOT / 'src' / 'logs' / 'menubar.log'
```

In py2app-Bundle ist `__file__` für `menubar_log.py`:
```
.../Monitor_CC_Menubar.app/Contents/Resources/lib/python3.14/src/menubar/menubar_log.py
```
→ `parents[2]` = `.../Contents/Resources/lib/python3.14/`
→ `MENUBAR_LOG` = `.../lib/python3.14/src/logs/menubar.log`

Das ist innerhalb des `.app`-Bundles — durch `_prune_bundle_bloat()` geleert, für den
User nie sichtbar, niemals lesbar. Dev-Modus trifft zufällig den korrekten Pfad (Projekt-Root /
`src/logs/menubar.log`), Bundle-Modus schreibt stillschweigend in einen unzugänglichen Pfad.

Alle anderen APP_SUPPORT-Dateien (settings.json, hooks.json, menubar.pid, etc.) nutzen korrekt
`_APP_SUPPORT = ~/Library/Application Support/com.brunowinter.monitor_cc_menubar` aus `paths.py`.

### Fix

`menubar_log.py` importiert `_APP_SUPPORT` aus `.paths`:
```python
from .paths import _APP_SUPPORT
MENUBAR_LOG = _APP_SUPPORT / 'menubar.log'
```

Kein Zirkel: `paths.py` importiert nichts aus dem menubar-Package. `_migrate_from_dotfiles()`
läuft beim `paths.py`-Import und erstellt `_APP_SUPPORT` bereits — `MENUBAR_LOG.parent.mkdir()`
in `log_menubar()` wird No-op. Dev + Bundle schreiben beide nach
`~/Library/Application Support/com.brunowinter.monitor_cc_menubar/menubar.log`.

---

## Logging zu grob — Partial-Failure unsichtbar

### IST (pre-fix)

`detect_main_desktop_numbers` (desktop_detection.py) loggt nur:
- `all_failed` — wenn ALLE Mains None sind (Zeile 94)
- Sub-Resolution-Events in `_resolve_cgwindow_id` (`resolve_no_name_match`, `resolve_no_tty`,
  osc2-Events) — pro-Call, ohne cwd-Kontext, ohne Transition-Gating → Spam bei stabiler Situation

Wenn ein einzelnes Main seine Nummer verliert (Monitor_CC `[2]` → None, während andere Mains
sichtbar bleiben): **kein Log**. Ebenso: Erfolg / Wiederherstellung wird nie geloggt.

### Bestätigter Trigger (User, 2026-05-28)

Jede Worker-Task (Worker-Spawn UND `worker-cli send` an existierenden Worker) lässt die
Desktop-Nummer sofort verschwinden. Erwartetes Transition-Log-Pattern:

```
[detection] transition Monitor_CC/Monitor_CC 2->None win='Monitor_CC — Claude Code' n_cand=0
```

`n_cand=0` bedeutet: AppleScript liefert den Ghostty-Window-Namen, aber nach dem Worker-Spawn
findet `_cgwindow_list_ghostty` kein CGWindow mit diesem Titel. Hypothese: Worker-Spawn öffnet
ein neues Ghostty-Fenster → Window-Landschaft ändert sich → SkyLight-Title-Cache des bisherigen
Fensters wird kurzzeitig ungültig oder das CGWindowList-Snapshot kommt im falschen Moment.

Recovery: Nach dem nächsten erfolgreichen 10s-Cycle (oder wenn der User das Tab fokussiert):
```
[detection] transition Monitor_CC/Monitor_CC None->2 win='Monitor_CC — Claude Code' n_cand=1
```

### Fix: Transition-Logging

Modul-Level: `_last_result: Dict[str, Optional[int]] = {}` in `desktop_detection.py`.

Im Orchestrator-Loop: `_cwd_ctx[cwd] = {'win': win_name, 'n_cand': len(candidates)}` pro cwd
nach `_resolve_cgwindow_id()` (keine Signatur-Änderung an der Funktion).

Post-Loop Transition-Check (vor Cache-Update):
```python
for cwd, new_no in result.items():
    old_no = _last_result.get(cwd)
    if new_no == old_no:
        continue
    label  = os.path.basename(os.path.dirname(cwd)) + '/' + os.path.basename(cwd)
    ctx    = _cwd_ctx.get(cwd, {})
    detail = f'win={repr(ctx.get("win", ""))[:40]} n_cand={ctx.get("n_cand", "?")}'
    log_menubar('detection', f'transition {label} {old_no}->{new_no} {detail}')
_last_result = dict(result)
```

Transition-gated: bei stabilem Zustand kein Log. `_cwd_ctx` ist lokal pro Cycle (kein
State-Leak). Bei Exception (Ghostty down / error) bleibt `_cwd_ctx` leer → `detail = win=''
n_cand=?` (signalisiert: Info nicht verfügbar, Fehler-Pfad).

**Nicht implementiert:** Strategy-used (`name-unique / space-elim / osc2`) als Nice-to-have
zurückgestellt — würde Return-Tuple-Änderung an `_resolve_cgwindow_id` + alle 5 Exit-Paths
erfordern. `n_cand` reicht als erster Diagnose-Schritt: `n_cand=0` isoliert den CGWindowList-
Mismatch, `n_cand>1` würde auf Space-Elimination / OSC2-Fallback zeigen.
