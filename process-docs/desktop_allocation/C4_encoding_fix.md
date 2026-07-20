# C4 — Subprocess ASCII-Locale UnicodeDecodeError: Root Cause + Fix

## Root Cause

**Confirmed by live APP_SUPPORT log (2026-05-28 ~22:39–22:41):**

```
22:39:XX [detection] all_failed n_mains=1 reason=error:UnicodeDecodeError('ascii', b'    1 /sbin/launchd...
22:40:50 [detection] transition Monitor_CC/Monitor_CC None->2 win=... n_cand=1
22:40:59 [detection] all_failed n_mains=1 reason=error:UnicodeDecodeError('ascii', b'...\xe2\xa0\x90 Offene Tasks...')
```

Two crash sites confirmed by log evidence:
- `22:39` — `ps -A -o pid=,command=` (`desktop_detection.py:170`) — Worker-Spawn-Prompt mit Emojis/Umlauten in argv
- `22:40:59` — `osascript` (`desktop_detection.py:196`) — Ghostty-Tab-Titel enthielt `'⠐ Offene Tasks'` (CC-Spinner + deutsch)

**Mechanismus:** launchd setzt keine Locale → `locale.getpreferredencoding()` = `'ascii'` →
`subprocess.run(..., text=True)` dekodiert stdout mit ASCII → `ps -A -o command=` liefert
vollständige argv aller Prozesse → CC-Worker hat seinen Spawn-Prompt in der argv (🛑, Umlaute)
→ `UnicodeDecodeError` → `detect_main_desktop_numbers` try/except fängt → `all_failed` →
Desktop-Nummer weg für alle Mains, solange der Worker läuft.

Gleicher Mechanismus betrifft alle weiteren `text=True`-Calls in der ASCII-Locale: osascript
(Fenstertitel), lsof (CWD-Pfade), tmux, bd CLI (Bead-Inhalte mit Emojis).

## Vollständiges Audit — alle betroffenen `text=True`-Calls in `src/menubar/`

| File:Line (pre-fix) | Befehl | Non-ASCII möglich | Bestätigt |
|---|---|---|---|
| `desktop_detection.py:170` | `ps -A -o pid=,command=` | Worker-argv Emojis/Umlaute | **CRASH (22:39)** |
| `desktop_detection.py:196` | `osascript` (Ghostty Fenster-/Tab-Namen) | `'⠐ Offene Tasks'` | **CRASH (22:40:59)** |
| `ghostty.py:95` | `ps -A -o pid=,command=` | identischer Vektor | latent |
| `bg_timer.py:48` | `ps -A -o pid=,ppid=,etime=,args=` | `args=` = vollständige argv | latent |
| `ghostty.py:66` | `osascript` (terminal id\|\|\|name) | andere Terminal-Namen | latent |
| `proc_cache.py:64` | `ps -A -o pid,tty,comm` | comm = Executable-Basename | niedrig |
| `proc_cache.py:83` | `lsof -a -d cwd -p pid` | non-ASCII CWD-Pfade | niedrig |
| `proc_cache.py:103` | `tmux list-sessions -F #{session_name}` | Session-Namen | niedrig |
| `proc_cache.py:120` | `tmux display-message #{window_activity}` | Integer — SICHER | SICHER |
| `ghostty.py:109` | `ps -A -o pid=,ppid=,tty=` | nur Ziffern + Device-Namen — SICHER | SICHER |
| `bead_data.py:38` | `bd show --json` | Bead-Titel/Beschreibungen mit Emojis | latent |
| `bead_data.py:70` | `bd comments --json` | Kommentartext | latent |
| `bead_data.py:118` | `bd list -l tracked --json` | Bead-Metadaten | latent |

Bereits sicher (kein `text=True`, manuelles `.decode(errors='replace')`): `system.py`,
`setup_menubar.py`, `queue.py`, `hook_writer.py`.

## Fix (Option c — beide Ebenen)

### Primär: per-Call `encoding='utf-8', errors='replace'`

Alle 13 `text=True`-Calls in den 5 betroffenen Modulen erhalten:
```python
capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=N
```

- `errors='replace'` → ungültige Bytes werden zu U+FFFD, kein Crash möglich
- Greift in **jedem** Launch-Modus (launchd, `open`, Finder, dev)
- Ein `?` an Stelle eines ungültigen Bytes wird von keinem unserer Pattern-Matches
  (`'Ghostty.app/Contents/MacOS' in line`, `'claude' in parts[2].lower()`, etc.) fälschlich
  gematcht → Zeile wird stille übersprungen (korrekt)

### Belt-and-Suspenders: `PYTHONUTF8=1` in LaunchAgent-Plist-Template

`src/menubar/com.brunowinter.monitor_cc_menubar.plist` → `EnvironmentVariables`:
```xml
<key>PYTHONUTF8</key>
<string>1</string>
```

PEP 540 (Python 3.7+): erzwingt UTF-8 für alle `text=True`-Subprocess-Decodes und `open()` im
Prozess. Greift im launchd-Kontext (Produktions-Deploy). Die installierte Plist unter
`~/Library/LaunchAgents/` wird beim nächsten Restart-Button-Click durch `write_plist_py2app()`
aus dem Template regeneriert — Opus deployt manuell für sofortigen Effekt.

`PYTHONUTF8=1` allein schützt nicht gegen invalid-UTF-8-Bytes (Standard `errors='strict'`
bleibt) und nicht gegen `open`/Finder-Launch → daher per-Call-Fix ist primär.
