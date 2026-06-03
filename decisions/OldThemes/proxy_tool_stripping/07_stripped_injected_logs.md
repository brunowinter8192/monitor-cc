# Stripped/Injected Delta Logs — Vier-Log-Architektur (Phase 5)

Build-Schritt 2026-06-03. Zwei neue DELTA-Logs `_stripped` / `_injected` in `src/logs/dual_log/`.
Neues Modul `src/proxy/diff_engine.py` (144 LOC) extrahiert als single source des Align+Classify-Engine.

## Kontext: Was davor existierte

Nach Phase 4 (05_forwarded_delta.md / 06_strip_inject_diff.md) gab es:
- `_original` — voll-kumulativ, roher CC-Payload, unberührt.
- `_forwarded` — Delta-Log: was ans API gesendet wurde (REQ#1 voll, ab REQ#2 Diff).
- `diff_strip_inject.py` in dev/ — Offline-Analyse, die Original↔Forwarded span-difft.

Die Klassifikation "was wurde gestrippt / injiziert" war NICHT persistiert — nur durch Offline-Analyse eines DEV/-Skripts ableitbar. Für die Monitor-Leseseite (grün/gelb-Highlighting) wäre das eine Runtime-Berechnung bei jedem Frame-Render — zu teuer. Entscheidung: materialisieren.

## Entscheidung: Vier Logs, keine Markierungen

**User-Entscheidung:** Kein Log bekommt Annotationen oder Kommentare. Vier Logs, die einfach gelesen werden.

**Warum `_stripped` ein eigenes Log braucht:** Der gestrippt Inhalt hat kein anderes Zuhause. In `_forwarded` ist er per Definition nicht (er wurde ja gestrippt). In `_original` liegt er zwar als Bytes — aber die Klassifikation "das hier ist gestrippt" ist nirgends gespeichert, sie muss hergeleitet werden. Materialisieren ist der Wert.

**Warum `_injected` ein eigenes Log braucht:** Symmetrie zu `_stripped` — injizierter Content ist nur in `_forwarded`, nicht in `_original`. Direkt greppbar für Verifikation der Inject-Logik.

**Logische Nicht-Redundanz:** Strip/Inject-Content ist *bytes-redundant* mit Original/Forwarded (die Bytes liegen auch dort), aber **nicht logisch redundant**: die Klassifikation ist nirgendwo gespeichert und muss sonst jedes Mal abgeleitet werden. Persistieren ist der Wert.

## Delta-Encoding für Stripped/Injected

Stripping ist hochgradig repetitiv: sys[2] CC-Prompt, sys[3], msg[0] SR-Blöcke werden bei jedem Request identisch gestrippt. Als volles Log würde `_stripped` pro Request die gleichen 130k-chars-Regeln wiederholen.

**Lösung:** Delta-Encoding analog zu `_build_forwarded_delta`. Per-Location-Hash-Chain (`loc_key → MD5[:10]` der Span-Texte, via `_hash_spans`). REQ#1 (`is_first: true`) schreibt alles. Ab REQ#2: nur Locations, deren Hash sich gegenüber dem vorigen Request geändert hat. Stabile Strips (sys[2] immer die gleichen Rules) erscheinen einmal im ersten Request, dann nie wieder.

Hash-State: `prev_stripped_hashes_by_model` / `prev_injected_hashes_by_model` in `ProxyAddon`, keyed by model_family. Identisch zur `prev_delta_hashes_by_model`-Architektur von `_forwarded`.

**Entry-Form `_stripped` (`type: stripped_delta`):**
```json
{
  "type": "stripped_delta",
  "request_id": "<id>",
  "timestamp": "<iso>Z",
  "model": "<post-override model>",
  "is_first": <bool>,
  "counts": {"system": N, "tools": N, "messages": N},
  "system_delta": {"<idx>": [<span_text>, ...]},
  "tools_delta": {"<name>": {"whole": true} | {"desc": [<span_text>, ...]}},
  "messages_delta": {"<msg_idx>": {"<block_idx>": [<span_text>, ...]}},
  "fields_delta": {"<key>": <orig_value>}
}
```

`_injected` ist identisch aufgebaut (`type: injected_delta`), aber enthält die insert-spans und `fwd_value` in `fields_delta`.

## Vollständiger Payload-Diff — Korrektheit bei Top-Level-Feldern

**Kern-Korrektheitspunkt:** Das Diff deckt ALLE Top-Level-Keys des Payloads ab, nicht nur system/tools/messages.

Konkretes Beispiel: `model`-Override (`claude-opus-4-7` → `claude-opus-4-8`) ist eine Feld-Ebene-Strip+Inject-Operation — exakt derselbe Mechanismus wie sys[2]-Ersetzung, nur auf Feld-Granularität statt Block-Granularität. Wenn `_diff_top_level_fields` fehlte, würde `_injected` behaupten "alles injiziert" während das `model`-Feld still übergangen wird — eine Inkonsistenz/Bug.

**`_diff_top_level_fields(orig_payload, fwd_payload) -> list`** (in `diff_engine.py`): iteriert alle Keys aus orig ∪ fwd, überspringt `_COLLECTION_KEYS = {"system", "tools", "messages"}`, klassifiziert jeden nicht-Collection-Key als:
- `stripped` (nur in orig)
- `injected` (nur in fwd)
- `replaced` (in beiden, Wert unterschiedlich)

`_build_stripped_injected_deltas` verarbeitet `field_diffs`: ein `replaced`-Eintrag landet sowohl in `s_fields` (`orig`-Wert) als auch in `i_fields` (`fwd`-Wert). Die Engine enumeriert keine Proxy-Operationen; sie difft den ganzen Payload. Jede aktuelle oder zukünftige Top-Level-Modifikation wird automatisch erfasst.

## `response()`-Hook-Platzierung — Off the Hot Path

**Problem:** `request()` ist synchron — mitmproxy wartet auf den Return bevor es forwarded. Ein teurer Diff im `request()`-Hook würde Client-Latenz addieren.

**Lösung:** Strip/Inject-Diff läuft in `response()` — nach dem upstream-Send (zero forwarding latency).

**Metadata-Bridge:**
- `request()` speichert `flow.metadata["mc_original_payload"] = payload` (Referenz auf das vor `apply_modification_rules` geparste Dict) und `flow.metadata["mc_modified_payload"] = modified_payload` (post-cache-ops, fertig).
- `flow.metadata["mc_model_family"] = model_family` — damit `response()` die richtige Hash-Kette lesen kann.
- `response()` liest diese drei Felder, ruft `_build_stripped_injected_deltas` auf, schreibt in `_stripped`/`_injected`. Isoliert in eigenem `try/except` — Failure berührt nie Forwarding oder die anderen Logs.

## Aliasing-Finding: Referenz ist sicher

**Frage:** `mc_original_payload` ist eine REFERENZ auf das Dict, das später durch `apply_modification_rules` etc. modifiziert wird. Wird der Original-Payload in-place verändert?

**Analyse + Befund: nein.** Die gesamte Modifikations-Pipeline ist funktional:
- `cache.py` und `rules.py` bauen neue Dicts/Listen (`{**msg, ...}`, `dict(msg)`, frische `new_blocks`/`new_system`-Listen).
- Kein nested-Objekt, das mit `mc_original_payload` geteilt wird, wird in-place mutiert.
- Einziger potenzieller Berührungs-Punkt: `cache_control`-Keys. Die werden aber bei der Normalisierung per `_strip_cache_control` vor dem Diff herausgefiltert — selbst wenn in-place mutiert, neutralisiert.

Kein Snapshot nötig. Die Referenz ist stabil bis `response()` sie liest.

## Single-Source Engine: `src/proxy/diff_engine.py`

**Ausgangssituation (06_strip_inject_diff.md):** `diff_strip_inject.py` hatte die Align+Classify-Logik inline (self-contained, keine Imports). Das war korrekt solange die Engine nur im DEV-Skript benötigt wurde.

**Neue Anforderung:** `_build_stripped_injected_deltas` in `logging.py` braucht dieselbe Engine. Zwei Kopien = zwei Divergenz-Risiken.

**Annahme revidiert:** Dev-Module dürfen src/ importieren. `dev/test_cwd_desktop_sidecar.py` macht das bereits (`import src.menubar`). Der `sys.path.insert` in `dev/`-Skripten ist das etablierte Pattern.

**Lösung:** Verbatim-Extraktion der Engine aus `diff_strip_inject.py` nach `src/proxy/diff_engine.py` (144 LOC). Alle Aufrufer importieren von dort:
- `src/proxy/logging.py` — direkter Import (`from .diff_engine import ...`)
- `dev/proxy_dual_log/verify_strip_inject.py` — via `sys.path.insert(0, parents[2])`, dann `from src.proxy.diff_engine import ...`
- `dev/proxy_dual_log/diff_strip_inject.py` — analog

Die OldThemes-06-Verifikation (ratio-Threshold, span-Klassifikation, Alignment-Strategie) bleibt gültig — git-History ist die eingefrorene Referenz, keine zweite Kopie nötig.

## cache_control-Normalisierung vor dem Diff

**Problem:** Original-Payload enthält CC's `cache_control`-Marker, Forwarded-Payload enthält die des Proxy (nach `_strip_all_cache_control` + `_set_cache_breakpoints`). Ein naiver Diff würde cache_control-Repositionierung als Strip/Inject-Spans melden — Rauschen. BP3/BP4-Wanderung würde bei jedem Request 1–2 Messages fälschlich als "gestrippt und injiziert" erscheinen lassen (weil sie je nach Turn BP tragen oder nicht).

**Lösung:** `_strip_cache_control` wird **an der Aufrufstelle** auf BEIDE Payloads angewendet (call site in `_build_stripped_injected_deltas`, nicht in der Engine). Die Engine bekommt cache_control-freie Inputs. Cache_control-Forensik liegt im `sent_meta`-Log, kein Informationsverlust.

## Whitespace-Fidelität (dokumentierte Limitation)

Word-level-Spans (ratio >= 0.1, echte Partial-Edits) werden als space-joined Words zurückgebaut. Interword-Whitespace wird dabei normalisiert (mehrere Spaces → ein Space). Whole-block-2-Span-Ersetzungen (ratio < 0.1, z.B. sys[2]: CC-Prompt → Rules) preservieren den exakten Text.

Für die primären Use-Cases (sys[2]-Strip, Tool-Whole-Strip, msg[0]-Block-Strips) ist das unproblematisch — diese sind alle ratio < 0.1 (Whole-Block). Cache_control-Suffix-Edits (ratio ≈ 1.0) verlieren evtl. internal whitespace in der Span-Text-Repräsentation. Für Monitor-Highlighting ausreichend, für byte-genaue Rekonstruktion nicht geeignet.

## Verifikationsstatus

**`verify_strip_inject.py`** (dev/proxy_dual_log/, 345 LOC) — Vollständigkeitsbeweis:
- **Check 1 (Span-Rekonstruktion):** Für jeden Block wo `orig_text != fwd_text` rekonstruiert die Engine `orig_text` aus (equal + stripped) und `fwd_text` aus (equal + injected) spans. Failure = `_diff_text` verliert Content.
- **Check 2 (Field-Coverage):** Jedes non-collection Top-Level-Feld das sich unterscheidet erscheint in `fields_delta`. Failure = Model-Override oder anderes Feld still übergangen.
- **Check 3 (Model-Cross-Check):** `injected fields_delta["model"]` (wenn vorhanden) matcht das `model`-Feld im entsprechenden `_forwarded`-Delta-Entry.

**Lauf auf `api_requests_opus_monitor_cc_1780497198`:** PASS 46/46 (historische Log-Daten).

**LIVE-Pfad:** Der Proxy schreibt `_stripped`/`_injected` während einer echten Session — dieser Pfad ist NOCH NICHT live-verifiziert (steht aus bis zur nächsten User-Test-Session). Monitor-Leseseite (Highlighting) ebenfalls deferred bis Daten vorhanden.

## Follow-Up: Janitor-Integration noch offen

`_stripped` und `_injected` sind noch **nicht** in `_LOG_REGISTRY` / der count-30-Rotation in `claude_proxy_start.sh` eingetragen. Sie akkumulieren unbegrenzt bis dieser Follow-up erledigt ist. Betrifft nur Platzverwaltung, nicht Korrektheit.
