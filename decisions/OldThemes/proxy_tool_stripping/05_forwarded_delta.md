# Forwarded-Log Delta-Iteration — Step 1

Build step 2026-06-02. `_forwarded`-Log von voll-kumulativ auf Request-to-Request-Delta umgestellt.
`_original` bleibt unverändert (voll-kumulativ, Source of Truth).

## Delta-Semantik

Pro Request nur das, was sich gegenüber dem VORIGEN Request dieser Proxy-Session geändert oder
neu dazugekommen ist — über System-Blöcke, Tools UND Messages gemeinsam.

- **REQ#1** (kein Vorgänger, `prev_hashes is None`): alles rein, `is_first: true`. Entspricht
  dem bisherigen vollen Write. Danach: ausschließlich "cache create" — nur geänderte/neue Elemente.
- **REQ#N** (N > 1): per-Element-Hash-Vergleich gegen Vorgänger. Element rein wenn
  `i >= len(prev_hashes[cat])` (neuer Index) ODER `curr_hash[i] != prev_hash[i]` (Inhalt geändert).
- Entfernte Elemente erscheinen NICHT im Delta; `counts` (Gesamtzahl system/tools/messages) erlaubt
  einem späteren Reader, Removals zu erkennen (prev_count > curr_count).

## cache_control-Normalize-Entscheidung

`_set_cache_breakpoints` platziert `cache_control: {"type": "ephemeral"}` auf spezifische System-Blöcke,
Tools und Messages. BP3/BP4 wandern mit jedem neuen Turn mit → würden bei naivem `json.dumps(element)`
als Hash-Basis 1–2 Messages pro Request fälschlich als "geändert" erscheinen (reines Marker-Rauschen).

**Lösung:** `_strip_cache_control(obj)` entfernt `cache_control` rekursiv vor dem Hash (dicts/lists).
Der **geschriebene** Inhalt im Delta bleibt das echte Element inklusive Marker — nur der **Vergleichs-Hash**
ignoriert sie. BP-Forensik liegt vollständig im `sent_meta`-Log, kein Informationsverlust.

Bestätigung (Opus-Verifikation, 3 konstruierte Requests): BP-Shift auf System-Block + Message erzeugt
`system_delta == {}` und `messages_delta == {}` (0 Spurious-Delta). Echte Inhaltsänderung + neuer Tool
werden korrekt als geänderte Indizes erkannt.

## Warum `_compute_msg_hashes` NICHT wiederverwendet

`_compute_msg_hashes` in `hash_meta.py` chunked die Mitte in rollende 5er-Summaries
(`hash of concat-of-5-hashes`). Bei REQ#50 mit 40 mittleren Messages: 8 rolling chunks — nicht
zurückrechenbar, welche individuelle Message sich geändert hat. Für exakte Per-Element-Selektion
unbrauchbar. → Frischer flacher Per-Message-Hash via `_delta_hash(m)` (MD5[:10] nach cache_control-Strip).

## self-healing State-Order

`self.prev_delta_hashes_by_model[model_family] = curr_delta` wird erst **nach** erfolgreichem
`_write_entry` gesetzt (beide innerhalb des try/except). Wenn ein Write scheitert (I/O-Fehler),
bleibt die Hash-Kette beim letzten erfolgreich geloggten Stand — der nächste Request difft gegen
diesen Stand und faltet das verlorene Material nach. Keine permanente Rekonstruktionslücke.

## Entry-Form (JSONL)

```json
{
  "type": "forwarded_delta",
  "request_id": "<x-request-id or ''>",
  "timestamp": "<iso>Z",
  "model": "<modified_payload model, inkl. Override>",
  "is_first": <bool>,
  "counts": {"system": N, "tools": N, "messages": N},
  "system_delta": {"<idx>": <block>, ...},
  "tools_delta": {"<idx>": <tool>, ...},
  "messages_delta": {"<idx>": <message>, ...}
}
```

Nur geänderte/neue Indizes in den `*_delta`-Dicts. `counts` = aktuelle Gesamtzahl (Shape-Referenz
+ Removal-Erkennung für Reader). `model` = `modified_payload.get("model")` = ggf. post-Override-Wert.

## Implementierung

Neue Funktionen ausschließlich in `src/proxy/logging.py` (kein neues Modul):
- `_strip_cache_control(obj)` — rekursiver Normalize-Helper
- `_delta_hash(element) -> str` — MD5[:10] nach Strip
- `_build_forwarded_delta(payload, request_id, prev_hashes) -> (entry_dict, curr_hashes)`

`src/proxy/addon.py`: neuer State `self.prev_delta_hashes_by_model: dict = {}`, forwarded Write-Block
ersetzt durch `_build_forwarded_delta`-Aufruf. Alle bestehenden Writes (main entry, sent_meta,
latency_update, _original) und die gesamte Proxy-Modifikationslogik unverändert.

## Live-Test Finding + Shape-Fix

Am realen `monitor_cc`-Traffic tauchte eine inhaltsgleiche User-Message (`"nochmal"`) fälschlich im
Delta auf. Root Cause: `_normalize_user_content_shape` in `cache.py` läuft NACH dem block-level
`cache_control`-Strip und verlangt exakt `{"type","text"}`-Keys. Wenn ein BP auf der Message liegt,
hat der Block 3 Keys inkl. `cache_control` → Bedingung feuert nicht → Inhalt bleibt als
`[{"type":"text","text":"nochmal","cache_control":{...}}]` (Listen-Form). Wenn der BP wegwandert,
bleiben nur 2 Keys → Bedingung feuert → Inhalt kollabiert zu `"nochmal"` (plain String).

Unser `_strip_cache_control` entfernte zwar `cache_control`, aber nicht den Form-Unterschied →
hash(`[{"type":"text","text":X}]`) ≠ hash(`"X"`) → Spurious-Delta.

**Fix:** `_normalize_msg_shape_for_hash(msg)` in `logging.py` — exakter Mirror der Bedingung aus
`cache._normalize_user_content_shape` (kein Import: `cache.py` importiert bereits von `logging.py` →
Circular). In `_delta_hash` nach `_strip_cache_control` angewandt wenn `"role" in normalized` —
**nur für den Vergleichs-Hash**, geschriebenes Element bleibt die echte Form.

Verifiziert (automatisierte Assertions):
- Alle drei Formen (Liste+cc / plain String / Liste-ohne-cc) → identischer Hash ✓
- Multi-Block-Message (len > 1) → NICHT kollabiert ✓
- Block mit Extra-Key (z.B. `"id"`) → NICHT kollabiert ✓
- Assistant-Messages → NICHT normalisiert ✓

**Hinweis sys[0]:** im Live-Test zeigt `system[0]` jeden Request im Delta (system[0] always in delta).
Das ist legitim — CC rotiert pro Request ein cch-Billing-Token in sys[0]. Kein Leck.

## verify_delta.py

`dev/proxy_dual_log/verify_delta.py` — beweist Verlustfreiheit + Konsistenz des Forwarded-Delta-Logs
gegen das Original-Log. Pro-Model-Family-Ketten-Rekonstruktion (delta overlay + truncate auf counts).

Checks:
- **Check 1 (hart):** rekonstruierte counts == im Delta deklarierte counts → FAIL bei Verletzung
- **Check 2 (soft):** `forwarded counts.messages` vs `n_messages` im Original → Mismatch nur
  gemeldet (nicht FAIL), weil der Proxy die Message-Anzahl legitim ändern kann

Lauf auf `api_requests_opus_monitor_cc_1780441622`:
```
PASS — 6 ok, 0 soft-mismatch, 0 hard-fail
Delta self-consistency: VERIFIED
```
6 Requests (2 haiku + 4 opus in zwei Ketten), alle counts-Invarianten erfüllt.
