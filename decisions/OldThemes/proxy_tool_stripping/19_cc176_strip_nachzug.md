# CC 2.1.176 Strip Nachzug

## Strukturelle Änderung in CC 2.1.176

CC 2.1.149 → 2.1.176 verschob mehrere Content-Klassen aus `role='user'`-SR-Blöcken in eine neue `role='system'`-Message:

| Content | bis 2.1.149 | ab 2.1.176 |
|---|---|---|
| Deferred-tools-Liste (CronCreate…) | `<system-reminder>` in `role='user'` msg | `role='system'` plain string (~9,559 chars) |
| Agent-types-Liste | `<system-reminder>` in `role='user'` msg | `role='system'` plain string (Opus) |
| Skills-Liste | `<system-reminder>` in `role='user'` msg | `role='system'` plain string (Opus) |
| Agent-types (Sonnet-Worker) | — | **weiterhin** als standalone user-SR (~2,353 chars) |

Zusätzlich: neues built-in Tool `Workflow` mit ~18.5k-char Description ohne Eintrag im `TOOL_BLOCKLIST`.

## Warum die Drift entstand (role==user Gate)

Jeder Pass in der `_passes`-Liste in `rules.py` ist auf `role == 'user'` gegated — zwei Muster:

- `_apply_first_pass`: 6 `elif`-Branches, alle mit `msg.get("role") == "user"` als erste Bedingung; `else` appended unverändert.
- Alle anderen 7 Passes: explizites `if msg.get("role") != "user": continue` am Schleifenanfang.

Eine `role='system'`-Message trifft jeden Skip-Guard und wird unverändert weitergeleitet. Die ~9,559-char-Message erschien in JEDEM Request (cached prefix, per-Request re-sent).

## Die vier Fixes

### Fix 1 — Workflow in TOOL_BLOCKLIST

`"Workflow"` zu `TOOL_BLOCKLIST` (frozenset, `constants.py`) hinzugefügt. `_strip_unused_tools` entfernt es vollständig. Die Description-Strip-Phase (`_strip_tool_descriptions`) hatte den Workflow-Description-Text bereits geleert, aber das Tool-Dict (Name + leeres Schema) wurde weiterhin forwarded.

### Fix 2 — `_apply_role_system_strip` (RS)

Neuer erster Pass in `_passes`. Bedingung: `role == 'system'` — kein Content-Marker, rein strukturell. `content → "."`. Idempotenz-Guard: leerer Content und bereits-`"."`-Content werden übersprungen.

**Attribution-Design (Q3-Entscheidung):** `_attribute_chunk` ist content-marker-basiert und wäre für einen role-basierten unconditional Strip fragil (zukünftige CC-Versionen könnten anderen Content liefern). Stattdessen: role-basierte Attribution direkt in `_process_messages_section` (`strip_inject_delta.py`): wenn `om_norm.get("role") == "system"` → `code = 'RS'` (bypasses `_attribute_chunk`). `_MSG_CODE_TO_FN['RS'] = '_apply_role_system_strip'`. strip_vocab.py `'RS'`-Entry mit leerem Marker-Array (kein Content-Marker vorgesehen oder notwendig).

Strip-Bedingung UND Attributions-Bedingung hängen beide an role, nicht am Content — konsistent mit dem Design-Intent „fire unconditional on role, regardless of content".

Log-Verifikation: 9,559c role=system-Message in echten Worker-Logs bestätigt.

### Fix 3 — `stripped_agent_types_sr` (AT)

Sonnet-Worker bekommen die agent-types-Liste weiterhin als standalone `<system-reminder>`-Block in einer `role='user'`-Message (~2,353 chars, `messages[0].content[1]`, beginnt `<system-reminder>\nAvailable agent types for the Agent tool:`). Nicht betroffen von Fix 2 (role=user, nicht role=system).

Fix: sauberer Mirror des Skills-Strips in `_apply_cumulative_sr_strips`:
- Neues Template `'agent-types': ('Available agent types for the Agent tool', 'full')` in `strip_sr.py._SR_TEMPLATES`
- `_MARKER_TO_TEMPLATE`-Eintrag: `'Available agent types for the Agent tool': 'agent-types'`
- Marker-Block in `_apply_cumulative_sr_strips` identisch zum `_SKILLS_MARKER`-Block
- mod-name: `stripped_agent_types_sr`
- strip_vocab.py: `'AT': ('stripped_agent_types_sr', ['Available agent types for the Agent tool'])`
- strip_inject_delta.py `_MSG_CODE_TO_FN['AT'] = '_apply_cumulative_sr_strips'`

Attribution content-marker-basiert (korrekt hier: SR-gewrapped und stabil, im Gegensatz zu Fix 2).

Log-Verifikation: 2,353c agent-types-SR in echten Sonnet-Worker-Logs bestätigt.

### Fix 4 — `stripped_bg_launch_ack` (BL) — gleiche Session, nicht 176-spezifisch

Background-Command-Launch-Acks (`"Command running in background with ID: <id>. Output is being written to: <path>. You will be notified when it completes. To check interim output, use Read on that file path."`) wurden nicht gestrippt. 54 Vorkommen in einer Session, reines Rauschen (Completion-Injection benachrichtigt ohnehin).

Neues Modul `strip_bg_launch_ack.py`. Neuer Pass `_apply_bg_launch_ack_strip` nach `_apply_bg_exit_strip` (Background-Strip-Gruppe). Fast-path-Marker: `'running in background with ID'`. Alle 4 Content-Shapes: str, list/text, list/tool_result-str, list/tool_result-list. Ganzer Block-Content → `"."` (keine Substring-Exzision, mirror des role=system-Strip-Patterns und des Rejection-Strip-Patterns). Captured Original in `pass_removed_by_idx` für dual-log-Attribution.

strip_vocab.py: `'BL': ('stripped_bg_launch_ack', ['running in background with ID'])`. `_MSG_CODE_TO_FN['BL'] = '_apply_bg_launch_ack_strip'`.

Nicht von CC 2.1.176 verursacht — Vorkommen in msg[63] in echten Logs bestätigt.

## Geänderte Dateien

| Datei | Änderung |
|---|---|
| `src/constants.py` | `"Workflow"` in `TOOL_BLOCKLIST` |
| `src/proxy/message_passes.py` | `_apply_role_system_strip` (neu, erster Pass); `_AGENT_TYPES_MARKER`-Block in `_apply_cumulative_sr_strips`; `_apply_bg_launch_ack_strip` (neu) |
| `src/proxy/rules.py` | Import + `_passes`-Einträge für alle drei neuen Passes |
| `src/proxy/strip_sr.py` | Template `'agent-types'` + `_MARKER_TO_TEMPLATE`-Eintrag |
| `src/proxy/strip_bg_launch_ack.py` | Neues Modul |
| `src/proxy/strip_vocab.py` | Codes RS, AT, BL |
| `src/proxy/strip_inject_delta.py` | RS/AT/BL in `_MSG_CODE_TO_FN`; role-basierte Attribution für RS in `_process_messages_section` |
