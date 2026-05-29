# E2 — Bundle Encoding Crash: UnicodeDecodeError(ascii) → leeres cwd_desktop Sidecar (2026-05-29)

## Problem

Nach dem Stage-2-Deploy (E1 Sidecar-Write + blank-Consumer + py2app-Rebuild/Reinstall + Menubar-Relaunch) wird `cwd_desktop.json` zwar angelegt, bleibt aber `{}`. Der launchd-gespawnte py2app-Bundle crasht JEDEN Detection-Zyklus → `_cwd_desktop_lkg` füllt sich nie → blanks `desktop_targeting.py` fällt auf den aktiven Desktop zurück → Stage 2 (Worker-Spawn + `show` File-Open auf Caller-Main-Desktop) ist trotz vollständigem Deploy **nicht funktional live**.

Production-Status: deployed aber non-functional. Blockiert den ebqc-Live-Verify.

## Evidenz

`~/Library/Application Support/com.brunowinter.monitor_cc_menubar/menubar.log` (laufender Bundle PID 70723, gestartet 02:33 aus dem rebuilt Bundle):

```
[detection] all_failed n_mains=1 reason=error:UnicodeDecodeError('ascii', b'tab-group-600002aa1c20|||\xe2\xa0\x82 Offene Tasks ...
[detection] all_failed n_mains=0 reason=error:UnicodeDecodeError('ascii', b'    1 /sbin/launchd\n  495 /Library/Apple/System/L ...
```

- ZWEI Crash-Quellen: `ps -A`-Output (`1 /sbin/launchd ...`) UND AppleScript-Ghostty-Fenster/Tab-Namen (`tab-group-...|||⠂ Offene Tasks`).
- Bytes `\xe2\xa0\x82` = UTF-8 für U+2802 (⠂), der Claude-Code-Spinner-Glyph. Plus dt. Text „Offene Tasks". Non-ASCII-Subprocess-Output als ASCII dekodiert → Crash.
- Gefangen vom `detect_main_desktop_numbers` outer `except Exception` → geloggt als `all_failed reason=error:...`.
- EIN Erfolg um 22:40:50 (`osc2_match tty=ttys051 wid=5582` → `transition None->2 n_cand=12`): die Detection-LOGIK funktioniert wenn das Decoding gelingt — der Crash ist rein das Decoding.

## NICHT TCC

Screen-Recording-Permission IST erteilt (System Settings → Aufnahme von Bildschirm: Monitor_CC_Menubar Toggle AN, Screenshot 2026-05-29). Der Blocker ist also der Encoding-Crash, nicht eine fehlende Screen-Recording-Grant. Die frühere Etappe-2-TCC-Hypothese ist durch diese Evidenz superseded.

## Root-Cause-Hypothese

launchd-gespawnter py2app-Bundle läuft ohne UTF-8-Locale (kein LANG/LC_ALL in der launchd-Env) → Pythons Default-Text-Decoding für Subprocess-Output ist ASCII → jedes Non-ASCII-Byte (Spinner-Glyph, dt. Fenstertitel) wirft UnicodeDecodeError.

Kandidaten:
- Ein `subprocess.run(...)` im Detection-Pfad ohne `encoding='utf-8'` (+ `errors='replace'`) — trotz C4-Fix auf `_ghostty_pid_int` + `_applescript_uuid_window_map`. Der `ps`-Crash deutet auf einen weiteren Call (discover.py / proc_cache.py ps-Calls?).
- ODER bundle-weit: `PYTHONIOENCODING=utf-8` / `LANG` in der py2app-launchd-Plist oder `menubar_main.py`-Entry setzen, sodass ALLE Subprocess-Decodes default UTF-8 sind (belt-and-suspenders, deckt alle Calls).

## Fix-Richtung (SOLL — pending)

UTF-8 im Detection-Pfad erzwingen: entweder per-call (`encoding='utf-8', errors='replace'` auf jedem subprocess.run im Detection-Chain — ps + osascript-Calls in desktop_detection.py, discover.py, proc_cache.py auditieren) ODER bundle-weite Locale (PYTHONIOENCODING/LANG in launchd-Env). Bundle-weit ist robuster. Dann Rebuild (setup_py2app) + Reinstall (~/Applications) + Relaunch + Re-Verify dass cwd_desktop.json sich füllt.

Caveat: Rebuild+Reinstall (rm+cp) erzeugt eine frische py2app-Code-Signatur. Der TCC-Screen-Recording-Grant könnte an die vorherige Signatur gebunden sein; falls die Detection NACH dem Encoding-Fix immer noch leere CGWindow-Results liefert → re-granten (System Settings → Screen Recording → `−` raus + `+` die neue ~/Applications-App rein).

## Status

**RESOLVED (2026-05-29).** Der per-call Encoding-Fix (C4: alle 13 `subprocess.run(text=True)`-Calls mit `encoding='utf-8', errors='replace'` + `PYTHONUTF8=1` in der Plist) war zum Zeitpunkt der E2-Diagnose bereits im `src/`-Code — das damals beobachtete crashende Bundle war stale (vor C4 gebaut). Inzwischen wurde neu gebaut/installiert:

- Laufendes Bundle: executable mtime **02:30** (nach C4), PID 96325 seit 02:45.
- Letzter `UnicodeDecodeError` **2026-05-28T22:54:59** — alle 87 Crashes historisch, seit Start der aktuellen PID keiner mehr.
- `cwd_desktop.json` füllt sich: `Monitor_CC → space_id 780, desktop_no 2`.
- User hat dem 02:30-Bundle die Screen-Recording-TCC-Permission neu erteilt (adressiert die separate `cgw_list_empty`-Schwäche).

Ein in dieser Session gebauter Rebuild (03:18) wurde **NICHT deployed** — identischer Code zum laufenden 02:30-Bundle; ein Redeploy hätte nur das TCC-Signatur-Bruch-Risiko ohne Mehrwert gebracht.

**Verbleibend (separates Thema, nicht ftpu):** intermittierende `all_no_match` / `cgw_list_empty no_names_returned` in der Detection — TCC/CGWindowList-Sichtbarkeit, nicht Encoding. Der Sidecar funktioniert trotzdem über den `osc2_match`-Pfad. Falls die Detection unzuverlässig wird → eigener Bead.

## Quellen

- `~/Library/Application Support/com.brunowinter.monitor_cc_menubar/menubar.log` ([detection]-Einträge)
- `src/menubar/desktop_detection.py` (`detect_main_desktop_numbers` + subprocess-Calls)
- `decisions/OldThemes/desktop_allocation/E1_sidecar_publish.md` (der Sidecar-Write den das blockiert)
- `decisions/OldThemes/desktop_allocation/C4_encoding_fix.md` (früherer Encoding-Fix — partiell)
- `setup_py2app.py` (Bundle-Build — launchd-Env)
- System Settings → Aufnahme von Bildschirm (TCC-Grant bestätigt, 2026-05-29)
