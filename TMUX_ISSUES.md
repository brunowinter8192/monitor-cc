# tmux Issues - Recherche & Lösungen

Basierend auf Research von: Web (StackOverflow, tmux docs), GitHub (dotfiles, configs), Reddit (r/tmux)

---

## Issue 1: Wortsuche im gesamten Buffer

**Problem:** Standard-Suche in copy-mode sucht nur im sichtbaren Bereich, nicht im gesamten Scrollback.

**Versuchte Lösung (FAILED):**
```python
subprocess.run(["tmux", "bind-key", "-T", "copy-mode-vi", "s", "command-prompt", "-ip", "search:", "send -X search-forward-incremental '%%'"])
```

**Warum gescheitert:**
- `-ip` ist falsche Syntax - muss getrennt sein: `-i -I "#{pane_search_string}" -p`
- `%%` reicht nicht - für subprocess Escaping braucht man `\"%%%\"` (drei Prozent!)
- `s` als Taste ist unüblich - Standard ist `/` für Suche

**Korrekte Lösung:**
```python
# / für Vorwärtssuche, ? für Rückwärtssuche
subprocess.run(["tmux", "bind-key", "-T", "copy-mode-vi", "/",
    "command-prompt", "-i", "-I", "#{pane_search_string}", "-p", "(search down)",
    "send -X search-forward-incremental \"%%%\""])
subprocess.run(["tmux", "bind-key", "-T", "copy-mode-vi", "?",
    "command-prompt", "-i", "-I", "#{pane_search_string}", "-p", "(search up)",
    "send -X search-backward-incremental \"%%%\""])

# n/N für nächsten/vorherigen Treffer
subprocess.run(["tmux", "bind-key", "-T", "copy-mode-vi", "n", "send-keys", "-X", "search-again"])
subprocess.run(["tmux", "bind-key", "-T", "copy-mode-vi", "N", "send-keys", "-X", "search-reverse"])
```

**Erklärung der Flags:**
- `-i`: Aktiviert inkrementelle Suche (live während Tippen)
- `-I "#{pane_search_string}"`: Füllt Prompt mit letzter Suche
- `-p "(search down)"`: Zeigt Prompt-Text
- `\"%%%\"`: Drei Prozent für korrektes Escaping in subprocess

**Quellen:**
- [wincent/wincent dotfiles](https://github.com/wincent/wincent) - Stars: 4.8K
- [r/tmux: Incremental search in copy-mode-vi?](https://reddit.com/r/tmux/comments/arv927)

---

## Issue 5: Alle Tool-Parameter anzeigen

**Problem:** Im Subagent-Pane zeigt `get_input_preview()` nur den ersten/wichtigsten Parameter.

**Versuchte Lösung (FAILED):**
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
- Subagent Tool Calls wurden gar nicht mehr angezeigt
- Nur Header "Active Subagents" sichtbar
- Vermutlich: `input_data` ist manchmal `None` oder kein Dict

**Korrekte Lösung:**
```python
def get_input_preview(input_data: dict) -> str:
    # Defensive checks
    if not input_data:
        return '(no input)'

    if not isinstance(input_data, dict):
        return str(input_data)[:40] + '...' if len(str(input_data)) > 40 else str(input_data)

    try:
        parts = []
        for key, value in input_data.items():
            value_str = str(value)
            if len(value_str) > 50:
                value_str = value_str[:50] + '...'
            parts.append(f"{key}={value_str}")

        result = ', '.join(parts)
        # Gesamtlänge begrenzen
        if len(result) > 120:
            return result[:120] + '...'
        return result
    except Exception as e:
        # Fallback bei Fehlern - loggen und sicheren Wert zurückgeben
        return '(parse error)'
```

**Debug-Schritte:**
1. Log checken: `src/logs/08_ui_rendering.log`
2. Prüfen was `input_data` tatsächlich enthält
3. Try-catch um das Rendering

**Datei:** `src/subagent_ui.py:184-200`

---
