# tmux Issues - Offene Probleme

Diese Features wurden versucht aber haben nicht funktioniert. Dokumentiert fuer spaeteren Fix-Versuch.

---

## Issue 1: Wortsuche im gesamten Buffer

**Problem:** Standard-Suche in copy-mode sucht nur im sichtbaren Bereich, nicht im gesamten Scrollback.

**Gewuenschtes Verhalten:**
- Einfache Taste (z.B. `s`) startet Suche
- Suche durchsucht gesamten Buffer (50k Zeilen)
- `ENTER` springt zum naechsten Treffer

**Versuchte Loesung (FAILED):**
```python
subprocess.run(["tmux", "bind-key", "-T", "copy-mode-vi", "s", "command-prompt", "-ip", "search:", "send -X search-forward-incremental '%%'"])
subprocess.run(["tmux", "bind-key", "-T", "copy-mode-vi", "Enter", "send-keys", "-X", "search-again"])
```

**Warum gescheitert:** Unklar - muss weiter untersucht werden.

---

## Issue 2: Copy Mode Toggle mit einfacher Taste

**Problem:** Copy-Mode betreten erfordert `Ctrl+B` dann `[` - zu umstaendlich.

**Gewuenschtes Verhalten:**
- Eine Taste (z.B. `q`) toggled Copy-Mode ein/aus
- Gleiche Taste zum Betreten und Verlassen

**Versuchte Loesung (FAILED):**
```python
subprocess.run(["tmux", "bind-key", "-T", "root", "q", "copy-mode"])
subprocess.run(["tmux", "bind-key", "-T", "copy-mode-vi", "q", "send-keys", "-X", "cancel"])
```

**Warum gescheitert:**
- `q` in root table aktiviert copy-mode aber zeigt persistente Status-Bar
- Status-Bar zeigt `[monitor_c0:[tmux]]*` statt erwartetem Verhalten
- Vermutlich Konflikt mit anderen Bindings oder tmux defaults

---

## Issue 3: Mode-Indikator (COPY vs SCROLL)

**Problem:** Unklar ob man im Copy-Mode oder Normal-Modus ist.

**Gewuenschtes Verhalten:**
- Sichtbarer Indikator zeigt aktuellen Mode
- COPY (gelb) wenn in copy-mode
- SCROLL (gruen) wenn in auto-scroll

**Versuchte Loesung (FAILED):**
```python
subprocess.run(["tmux", "set-option", "-t", session_name, "status", "on"])
subprocess.run(["tmux", "set-option", "-t", session_name, "status-right", "#{?pane_in_mode,#[fg=yellow bold]COPY#[default],#[fg=green]SCROLL#[default]}"])
```

**Warum gescheitert:**
- Status-Bar erscheint aber zeigt falschen Inhalt
- Zeigt `[monitor_c0:[tmux]]*` statt COPY/SCROLL
- Status-Bar war vorher absichtlich off - wieder aktivieren verursacht Probleme

---

## Issue 4: Scroll 1 Zeile statt 5

**Status:** Bereits implementiert und funktioniert.

Aktuelle Config (workflow.py:146-147):
```python
subprocess.run(["tmux", "bind-key", "-T", "root", "WheelUpPane", "if-shell", "-F", "#{mouse_any_flag}", "send-keys -M", "copy-mode -e; send-keys -X -N 5 scroll-up"])
```

Aendern von `-N 5` zu `-N 1` fuer 1-Zeilen-Scroll. Nicht getestet ob das Probleme verursacht.

---

## Issue 5: Alle Tool-Parameter anzeigen

**Problem:** Im Subagent-Pane zeigt `get_input_preview()` nur den ersten/wichtigsten Parameter.

**Gewuenschtes Verhalten:**
- Alle Parameter anzeigen: `key=value, key2=value2`

**Versuchte Loesung (FAILED):**
```python
def get_input_preview(input_data: dict) -> str:
    parts = []
    for key, value in input_data.items():
        value_str = str(value)
        if len(value_str) > 60:
            value_str = value_str[:60] + '...'
        parts.append(f"{key}={value_str}")
    return ', '.join(parts)
```

**Warum gescheitert:**
- Nach dieser Aenderung wurden Subagent Tool Calls gar nicht mehr angezeigt
- Nur Header "Active Subagents" sichtbar, keine Tool Calls
- Vermutlich hat die Aenderung einen Downstream-Fehler verursacht
- Muss Logs pruefen: src/logs/08_ui_rendering.log

---

## Funktionierende Features

Diese wurden erfolgreich implementiert:

**Option+m / Option+s - Pane kopieren:**
```python
subprocess.run(["tmux", "bind-key", "-T", "root", "M-m", "run-shell", "tmux capture-pane -t 0 -pS - | pbcopy && tmux display 'Main pane copied'"])
subprocess.run(["tmux", "bind-key", "-T", "root", "M-s", "run-shell", "tmux capture-pane -t 1 -pS - | pbcopy && tmux display 'Subagent pane copied'"])
```

---

## Naechste Schritte

1. Issues einzeln debuggen, nicht alle gleichzeitig
2. Vor jeder Aenderung: Subagent-Pane testen ob es noch funktioniert
3. Logs pruefen bei Problemen: src/logs/08_ui_rendering.log
4. tmux-Bindings in isolierter tmux-Session testen bevor sie in workflow.py kommen
