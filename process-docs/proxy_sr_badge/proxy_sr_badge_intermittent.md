# Proxy Pane ⚠SR Badge intermittent

## Symptom

Proxy-Pane in Monitor_CC zeigte das ⚠SR-Badge auf Strip-Events nicht konsistent. Originale Annahme: Badge fehlt nach längerer Pane-Lebenszeit, kommt nach Ctrl+R-Respawn zurück. Zweite Investigation-Runde verfeinerte das Symptom: **intermittent, nicht binär** — manche REQs haben Badge, andere nicht, auch im langlaufenden Pane-Prozess.

Stand 2026-05-12: User meldet, Monitor läuft einwandfrei. Symptom in aktueller Form nicht mehr beobachtet. Investigation als gelöst-durch-Drift / nicht-mehr-reproducibel abgeschlossen.

## Etablierte Fakten (Stand 2026-05-09)

1. Strip läuft. Jede REQ im JSONL hat 10 Mods inkl. `stripped_deferred_tools_sr`, `stripped_skills_sr`. `stripped_msg_indices=[0]`, `stripped_msg_removed["0"]` enthält literale `<system-reminder>`-Chunks.
2. `_aggregate_entry_tags(entry)` korrekt — returnt `['SR']` für REQ#1 (msg_count=1, BP:1, `diff_from_prev.first_diff_index=0`). Für REQ#2–#7 returnt `[]`, weil Strip auf msg[0] außerhalb delta-range — by-design.
3. `format_proxy_block` direkt gegen frisch geparste JSONL produziert `▶ #1 opus 1msg BP:1 eff:hig think:128k CR:0 CC:0 🔧+7 ⚠SR  TTFB:2.5s` (visible_width=71). Badge IST gerendert in fresh state.
4. Width-Truncation NICHT die Ursache — Ctrl+R ändert keine Pane-Breite und stellt Badge wieder her.
5. Live-Pane zeigte auf REQ#46 (msg_count=91, CR:143k, CC:6.4k) das Badge: `▶ #46 opus 91msg BP:1 eff:hig think:128k CR:143k CC:6.4k Δmsgs:+1.8k(~511tok) ⚠SR TTFB:4.3s`. Damit Symptom intermittent.
6. Worker hatte Commit `df9ec75` angefangen zu vergleichen (dev vs main) — Investigation mid-flight abgebrochen (Context-Limit).

## Hypothesen (offen geblieben)

- **H1:** `_lazy_load_messages` mutiert Entries nur unter bestimmten Bedingungen (erst- vs zweit-Aufruf).
- **H2:** `diff_from_prev.first_diff_index` Recompute schiebt nur bestimmte REQs aus delta-range.
- **H3:** `_proxy_cache_turns` regroupt selektiv weg.
- **H4:** `df9ec75` enthält Fix, der dev/main desyncen lässt — Live-Pane lief auf altem Code.

## Status

Zwei Investigation-Worker am Context-Limit gestorben (proxy-state-bug, proxy-strip-state). Investigation pausiert; seitdem keine erneute Reproduktion gemeldet — Monitor stabil. Geparkt; bei Wiederauftreten neue Investigation-Runde mit härter eingegrenztem Scope (nur Repro auf konkreten Live-Daten, mehrere REQs, keine breite Code-Lese-Session).

## Wo (falls reaktiviert)

- `src/proxy/` (Strip-Logik)
- `src/panes/` (Proxy-Pane Renderer, `format_proxy_block`, `_aggregate_entry_tags`)
- `_lazy_load_messages`, `_proxy_cache_turns`, `diff_from_prev.first_diff_index`
- Commit `df9ec75` für dev/main-Vergleich

---

## Resolution — ⚠SR/⚠TN double-fire (2026-06)

### Symptom (präzisiert)

⚠SR/⚠TN/⚠ND badges feuerten auf REQs, bei denen kein genuinely-new SR/TN existierte — jedes echte TN/SR wurde ZWEIMAL gebadgt: einmal bei gap=0 (genuinely new) und ~2 REQs später nochmals bei gap=2 (false positive).

### Root Cause — H2 bestätigt

**H2 war die Ursache.** `diff_from_prev.first_diff_index` ist ein Content-Diff-Anker für Cache-BP3-Placement — korrekt für diesen Zweck, aber er REGRESSIERT in alte Message-Indices wenn eine vorherige Nachricht sich auch nur um 1 Zeichen ändert.

Konkreter Mechanismus: `_apply_first_pass` in `rules.py` hängt `\n` ans Ende des TN-Strip-Wakeup-Blocks an (`_WAKEUP_TEXT`). Beim nächsten Turn serialisiert Claude Code dieselbe message list erneut zu einem String (47c→48c, blocks→empty). `first_diff_index` zeigt dann auf diese alte, leicht-veränderte Nachricht — nicht auf die erste wirklich neue. Damit lag der Gate-Wert für "Strips zu zählen" UNTER `prev_message_count`, und der Strip bei diesem alten Index wurde erneut als "new" gewertet → double-fire.

**H1, H3, H4 ausgeschlossen:** `_lazy_load_messages`-Mutationseffekte, `_proxy_cache_turns`-Regroup und dev/main-Code-Desync waren NICHT ursächlich — das Symptom war deterministisch reproduzierbar in frisch geparsten JSONL-Daten ohne jede Live-Pane-Interaktion.

### Fix

`start = message_count - (messages_added or 0)` = `prev_message_count` — der Index der ersten wirklich neuen Nachricht. `messages_added` ist bereits in `diff_from_prev` vorhanden.

Angewandt in BEIDEN betroffenen Stellen:
- `_aggregate_entry_tags()` in `src/proxy_display/render_messages.py` (Badge-Gate für ⚠SR/⚠TN/⚠ND)
- `classify_tags()` in `src/proxy/strip_vocab.py` (LEAK/SUS delta scope)

`first_diff_index` / `parser.py` NICHT angefasst — bleibt korrekt für seinen Cache-BP3-Zweck. Edge cases erhalten: `fdi is None` → `start=0` (erste REQ, alle Msgs neu); `fdi < 0` → early return (byte-identical re-fire, keine neue Strip-Aktivität).

### Verification

Getestet gegen Live-Log `src/logs/api_requests_opus_monitor_cc_1780585154.jsonl`:
- 10 TN-False-Positives (gap=2-Regressionen) supprimiert
- 0 cross-request double-flags nach Fix
- Alle genuinen SR/TN/ND-Badges erhalten (task-tools-nag SR, deferred-tools/skills SR, echte Timer-TNs)

Scope-Entscheidung (user-confirmed): Nur der Double-Fire wird entfernt; ALLE echten Reminder-Strips bleiben gebadgt.
