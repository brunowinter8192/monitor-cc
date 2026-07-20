# Schema-Drift Detection — CC Version Regression Alert

**Scope:** Session 2026-04-15 bis 2026-04-19. Bead Monitor_CC-rjs (closed 2026-04-19).
**Trigger:** Erste API-Request jeder Session (pro model_family: opus + sonnet) validiert Payload-Struktur gegen Baseline. Bei Drift → Warning im Warnings-Pane unter "SCHEMA DRIFT" Sektion.
**Next CC-Upgrade:** erneut relevant — siehe "Post-Upgrade Verification Procedure" unten.

---

## Problem

Neue CC-Versionen können silent die Payload-Struktur ändern. Proxy-Modifications (tools strip, system-reminder strip, rule injection, cache marker placement) brechen dann ohne Fehler-Signal. Kein Mechanismus zur Erkennung vorhanden.

## IST (Code-Stand 2026-04-19)

### Core-Logik — `src/proxy/addon.py`

`_check_payload_schema(payload) -> list[str]` prüft 5 Invarianten:

1. **Unknown top-level keys** — `set(payload.keys())` gegen whitelist bekannter Felder (model, max_tokens, system, messages, tools, stream, temperature, metadata, thinking, tool_choice, top_p, top_k, output_config, context_management, betas)
2. **System block count == 4** — payload["system"] muss genau 4 Blöcke haben (CC-Konvention: [0]=tiny cch-hash, [1]=misc, [2]=rules, [3]=gitStatus)
3. **system[2].type == "text"** — unser rules-Block ist text-typed
4. **messages[0].content ist list** — nicht str
5. **tools nicht leer** — CC sendet immer >= 1 tool

Zusätzlich: **Unknown keys in tools[0]** — gegen tool-def whitelist (name, description, input_schema, cache_control, type, max_uses, allowed_domains, blocked_domains, etc.)

### Gate — `ProxyAddon._schema_checked: Dict[str, bool]`

Check läuft **EINMAL pro model_family pro Proxy-Instance**. `_schema_checked` ist dict (nicht bool) seit commit cc92feb → Opus + Sonnet beide geprüft, Haiku excluded.

### Drift-Signal — Warnings-Pane

Warnings-Array wird als proxy log entry mit `type: schema_warning` geschrieben. `src/warnings_pane.py` parst diese Entries und rendert unter "SCHEMA DRIFT" Sektion.

### Baseline — empirisch gegen CC v2.1.114 etabliert

ZERO schema_warnings im aktuellen Code bei aktueller CC-Version = silent pass = Baseline gilt.

## Deliverables (D1-D5, alle committed auf dev→main)

| D | Commit | Was |
|---|---|---|
| D1 | ef86be8 | Session-scope fix: parse_proxy_log + schema_warnings resetten bei project-filter-Wechsel (vorher global-persistent) |
| D2 | 6396eb7 | is_error structural detection (ersetzt substring-match, 15 False-Positives weg) — indirekt für Schema-Quality |
| D3 | 6f1901d | Scroll-Richtungs-Fix im Warnings-Pane (button 64 = wheel-up = offset decrement) |
| D4 | 42f5105 | Mutation-Test (dev/proxy/test_schema_check.py): 6 Drift-Injection-Cases, 6/6 PASS → Detector feuert bei echter Drift |
| D5 | cc92feb | Sonnet-Coverage: `_schema_checked` auf Dict[str, bool] per model_family |

## Post-Upgrade Verification Procedure (WICHTIG beim nächsten CC-Update)

Wenn Auto-Update oder manueller Pin-Bump auf neue CC-Version:

### Step 1 — Natural check (passive)
Nach Monitor-Restart mit neuer CC-Version: Warnings-Pane öffnen, "SCHEMA DRIFT" Sektion beobachten beim ersten Opus-Request + ersten Sonnet-Request (Worker-Spawn). Silent = Baseline gilt noch, neue Version strukturkompatibel.

### Step 2 — Falls Drift-Warnings erscheinen
Output lesen — welche Invariante verletzt? Entscheidungsbaum:

- **"Unknown top-level keys: X"** → CC schickt neues Feld. Whitelist in `_check_payload_schema` erweitern (addon.py). Prüfen ob Feld proxy-relevant (z.B. neue cache_control-Variante, neues context_management-Feld).
- **"system has N blocks"** → CC-Struktur-Change. Kritisch. Prüfen ob unsere sys[2] rules-Injection noch funktioniert. Evtl. cache.py sys-marker-Logik anpassen.
- **"system[2].type=image"** → CC hat system-Layout reorganisiert. Fix: sys-Block-Detection neu kalibrieren, rules-Injection-Ziel anpassen.
- **"messages[0].content is str"** → CC-Message-Format changed. Rule-Chain (content_strip.py) prüfen auf list-assumption.
- **"tools is empty"** → CC schickt keine Tools im ersten Request. Sehr ungewöhnlich, strukturelle Änderung. Full-Check nötig.
- **"Unknown keys in tools[0]"** → CC hat Tool-Definition-Format erweitert. Whitelist in addon.py updaten.

### Step 3 — Regression-Test re-run
```bash
./venv/bin/python dev/proxy/test_schema_check.py
```
Sollte 6/6 PASS bleiben auch nach Baseline-Updates. Falls ein Case hart-coded auf alte CC-Struktur baut (z.B. system block count) → Test parallel zur Code-Baseline updaten.

### Step 4 — Manual Drift-Induction (optional, für Confidence)
Wenn Natural-Check silent aber Upgrade groß war: mock-payload mit künstlicher Drift gegen `_check_payload_schema()` feuern:
```python
from src.proxy.addon import _check_payload_schema
payload = {"model": "claude-opus-X", "extra_new_field": "xxx", ...}
print(_check_payload_schema(payload))
```
Erwartung: mindestens Warning "Unknown top-level keys: ['extra_new_field']". Beweist dass Detector in neuer CC-Env läuft.

## Files / Pfade

- **Core:** `src/proxy/addon.py` — `_check_payload_schema()`, `ProxyAddon._schema_checked`
- **Mutation Test:** `dev/proxy/test_schema_check.py` — 6 Cases
- **Warnings-Pane:** `src/warnings_pane.py` — SCHEMA DRIFT Sektion, `schema_warnings` list
- **Baseline-Referenz:** CC v2.1.114 (getestet 2026-04-18, silent pass)

## Offene Fragen für Future-Upgrade

- Detector ist one-shot pro Proxy-Session. Mid-session CC-Update würde silent bleiben (unrealistisch bei pinned version aber erwähnenswert).
- Sonnet-Schema-Check läuft NACH dem Override durch inject_helpers — der Check sieht die modifizierte Payload, nicht was CC original gesendet hat. Bei Upgrade-bezogener Drift im CC-Output direkt → unsere Override-Mutation könnte das maskieren. Falls je relevant: check vor `apply_modification_rules` einziehen.

## Related

- Commit `671ca54` — initialer Detector-Deploy
- Bead Monitor_CC-rjs (closed 2026-04-19)
- Shared-Rules: keine spezifische, reine Projekt-IST-Doku
- Companion: `content_drift_detection.md` — content-side drift (SR marker × location × frequency)
