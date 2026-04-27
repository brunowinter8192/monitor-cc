# Content-Drift Detection — SR-Marker × Location Coverage

**Scope:** Knowledge preserved from bead Monitor_CC-8k7 (closed 2026-04-27, deferred).
**Trigger:** Live-Audit 2026-04-19 fand 24,282 system-reminder-Instanzen in `tool_result.content` die unsere strip-Logik nicht griff — eine vom CC-Update eingeführte neue Inject-Location.
**Status:** NOT implemented as live pane or dev script. Doc preserves the approach for the next time a CC-upgrade introduces new SR markers or new injection-locations.

---

## Problem

2026-04-19: Live-Audit (ad-hoc Python-Script gegen 6 aktuelle Proxy-JSONLs) fand 24,282 `<system-reminder>`-Instanzen, die den proxy-strip passierten. Alle lagen in `tool_result.content` — einer Inject-Location, in die der strip-Code damals nicht rekursierte.

Der vorhandene schema-drift-Detector (`schema_drift_detection.md`) prüft ausschließlich strukturelle Invarianten: top-level Keys, system-Block-Count, types, tools-Vollständigkeit. Er sieht keine Inhalte. Content-Drift — neue SR-Marker-Texte, neue Injection-Locations — liegt auf einer orthogonalen Achse und ist vom Schema-Detector grundsätzlich nicht abgedeckt.

Das bedeutet: eine neue CC-Version kann SR-Blöcke in eine neue message-Content-Shape einbetten, und weder Schema-Drift noch bisherige strip-Funktionen feuern. Der Payload erreicht Claude unverändert.

## IST (Code-Stand 2026-04-21, commit e1a3b9a)

### Strip-Logik — `src/proxy/strip_sr.py`

`_strip_system_reminders(content, enabled_templates)` operiert auf **allen 4 bekannten Content-Shapes**:

| Shape | Code-Pfad |
|---|---|
| top-level string | `isinstance(content, str)` → `_apply_sr_strip(content, ...)` |
| list of text-blocks | `btype == 'text'` → `_apply_sr_strip(block['text'], ...)` |
| `tool_result.content` string | `btype == 'tool_result'`, `isinstance(inner, str)` → `_apply_sr_strip(inner, ...)` |
| `tool_result.content` list of text-sub-blocks | `btype == 'tool_result'`, `isinstance(inner, list)` → iterate sub-blocks, strip `type==text` entries |

Die Implementierung in `_apply_sr_strip()` matcht ausschließlich **standalone SR-Blöcke** (Regex `(?m)^<system-reminder>...` — nur Blöcke die am Zeilenanfang beginnen). Das verhindert False-Positives auf eingebettete Code-Literale wie `if "<system-reminder>" in text:`.

### Template-Katalog — 10 Templates

```
task-tools-nag       → "The task tools haven't been used recently"          (full)
pyright-diagnostics  → "<new-diagnostics>"                                   (full)
deferred-tools       → "The following deferred tools are now available..."    (full)
user-interrupt       → "The user sent a new message while you were working:"  (partial — preserve user body)
system-notification  → "[SYSTEM NOTIFICATION - NOT USER INPUT]"              (full)
file-modified        → "Note: "                                               (full)
claudemd-contents    → ["As you answer the user's questions", "Contents of "] (full, but see below)
date-changed         → "The date has changed."                               (full)
skills-available     → "The following skills are available"                  (full)
plan-mode            → "Plan mode "                                          (full)
```

**Preserve-Guard:** SR-Blöcke deren innerer Text mit `"As you answer the user's questions, you can use the following context:"` beginnt, werden **nicht** gestrippt. Das ist der CLAUDE.md-Context-Block den CC via SR injiziert — Opus braucht diesen für Projekt-Kontext, und `replaced_system_prompt` ersetzt bereits sys[2], dieser SR-Block ist der einzige verbleibende Delivery-Pfad.

**mode 'partial' (user-interrupt):** Entfernt nur die IMPORTANT-Zeile, bewahrt den User-Body im SR-Wrapper.

### Replay-Validation

Commit e1a3b9a: Replay über **22 historische JSONLs** (~37k Strip-Operationen) — **0 False-Positives** (Vorgänger greedy-regex hatte ~970 FPs, u.a. auf eingebettete Code-Literale in Payloads).

### Schema-Counterpart

Schema-Drift-Detection (`schema_drift_detection.md`) behandelt strukturelle Invarianten (top-level key whitelist, system-block-count, types). Content-Drift (welche SR-Marker in welchen Locations auftauchen) ist orthogonal — beide Detektoren decken zusammen das vollständige Bild ab.

## Why Deferred

Kein CC-Update ist aktuell im Anflug. Der akute Leak ist durch e1a3b9a geschlossen. Live-Pane oder Scanner-Script jetzt zu bauen wäre premature:

- Die KPI „stripped N / detected M" ist bedeutsam nur an CC-Upgrade-Grenzen; im Steady-State sitzt sie still bei 100%
- Pane-Bandbreite ist endlich — ein 24/7-Drift-Pane für ein Rare-Event ist die falsche Ressourcen-Allokation
- Der manuelle One-Shot-Audit (Step 1 unten) dauert 2-5 Minuten und reicht für den Upgrade-Fall vollständig aus

Entscheidung (2026-04-27): Approach als Rezept hier preservieren. Wenn das nächste CC-Upgrade kommt → Procedure unten ausführen. Falls sich der manuelle Ablauf über mehrere Upgrades als zu aufwändig erweist → dann erst zu dev-Scripts codifizieren.

## Post-Upgrade Verification Procedure

Wenn neues CC-Version-Upgrade (Auto-Update oder manueller Pin-Bump):

### Step 1 — Replay-Scan gegen neue Logs (One-Shot, keine committed Scaffolding)

Sobald die neue CC-Version ~10 Sessions Proxy-Logs erzeugt hat:

```python
# Iterate raw_payload.messages across recent JSONLs
# For each message, find ALL <system-reminder>...</system-reminder> occurrences
# Classify by location:
#   text_block            — top-level user-message text block (isinstance content str, or type==text in list)
#   tool_result_str       — string inside {type: tool_result, content: "..."}
#   tool_result_nested_text — {type: text, text: "..."} nested inside tool_result.content list
#   plain_string          — message.content is a plain string (not blocks)
# Count per (template_identifier × location)
# Surface any SR whose inner text does NOT match a known _SR_TEMPLATES identifier
```

Referenz: Der 2026-04-19 Audit hat genau dieses Scan-Pattern verwendet und 24,282 Bypässe in `tool_result_str` / `tool_result_nested_text` in unter 2 Minuten gefunden.

Expected coverage wenn der strip vollständig ist: jede SR-Location matcht entweder ein bekanntes Template (= bereits gehandhabt) oder erscheint als unbekanntes Template (= Drift-Signal).

### Step 2 — Drift-Triage

| Befund | Maßnahme |
|---|---|
| Bekanntes Template, neue Location | `_strip_system_reminders()` in `strip_sr.py` um neue content-shape erweitern (das 2026-04-21 Fix-Pattern) |
| Unbekanntes Template | CC hat neuen SR-Marker eingeführt. Entscheiden: strip-würdig (→ `_SR_TEMPLATES` erweitern) oder pass-through? |
| Kein Befund | Strip-Coverage ist vollständig für diese CC-Version. Done. |

### Step 3 — Optional: zu dev-Scripts codifizieren

Wenn mehrere CC-Upgrades hintereinander diesen manuellen Workflow auslösen, in `dev/tool_use_analysis/` codifizieren:

- `sr_scanner.py` — scannt Proxy-JSONLs, zählt SR pro Marker × Location × Session; Output: MD-Report
- `sr_marker_discovery.py` — findet unbekannte SR-Texte via stem-matching gegen bekannte Marker-Liste, clustert ähnliche

Report-Output: `YYYYMMDD_sr_content_drift.md` in `dev/tool_use_analysis/`.

Diese Scripts waren ursprünglich Teil A von bead 8k7. Nicht implementiert weil der manuelle One-Shot-Audit (Step 1) für den seltenen Upgrade-Fall ausreicht.

## Why NOT a Live Pane

Bead 8k7 hatte ursprünglich `src/drift_pane.py` analog `waste_pane` als Teil B vorgesehen. Rejected 2026-04-27:

- Pane-Bandbreite ist endlich — Drift-Detection ist Rare-Event-Monitoring, kein 24/7-Bedarf
- „Stripped N / detected M" KPI ist nur an CC-Upgrade-Grenzen bedeutsam; im Steady-State steht sie still bei 100%
- Window 2 (rules+hooks) wird deleted, nicht repurposed (separate Session)

Falls der manuelle Audit-Ablauf über mehrere Upgrades zu aufwändig wird → zu dev-Script (Step 3 oben) escalieren. Pane ist die falsche Shape für das Problem.

## Files / Pfade

- **Strip-Logik:** `src/proxy/strip_sr.py` — `_SR_TEMPLATES` Katalog, `_strip_system_reminders()` mit 4-Shape-Coverage, `_PRESERVE_PREAMBLE` Guard
- **Schema-Counterpart:** `decisions/OldThemes/schema_drift_detection.md`
- **Cache-Pipeline-Doc:** `decisions/pipe05_proxy_cache.md:10` — commit e1a3b9a, Replay-Zahlen (22 JSONLs, ~37k strips, 0 FP)

## Related

- Commit `e1a3b9a` (2026-04-21) — Template-Catalog SR-Strip mit 4-Content-Shape-Abdeckung; standalone-SR-Regex; 10 Templates
- Bead Monitor_CC-8k7 (closed 2026-04-27, deferred — knowledge preserved here)
- Bead Monitor_CC-rjs (closed 2026-04-19) — schema-drift-detector parent work
- Companion: `decisions/OldThemes/schema_drift_detection.md` — strukturelle Drift (top-level keys, system-block-count, types)
