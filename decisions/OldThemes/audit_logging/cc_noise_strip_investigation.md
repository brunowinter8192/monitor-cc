# CC Noise Prefix Strip — Tool Error Display Investigation (2026-05-24)

**Topic:** Proxy-Display-Layer Stripping von CC-added Noise-Prefixen aus
Tool-Error-Messages. Initial bekannter Fall: hook-block Errors mit
`PreToolUse:<Tool> hook error: [python3 <full-path>]: ` Wrapper. Ziel: generalisieren
auf andere CC Error-Class-Patterns die ähnliches Noise produzieren.

**Status:** Investigation deferred until `src/logs/tool_errors.jsonl` 1-2 Wochen
Daten akkumuliert hat. Preemptives Strippen birgt Risiko wertvollen Error-Content
zu entfernen — Pattern müssen empirisch identifiziert werden, nicht hypothetisch.

---

## Background

CC wrappt diverse Tool-Error-Messages mit Metadata-Prefixen bevor sie im Agent's
`tool_result` ankommen. Einige dieser Prefixe sind reine Display-Noise die dem
Agent beim Debugging nicht helfen. Andere könnten Kontext enthalten der nicht
weggestrippt werden darf.

**Confirmed noise case:** Hook-Block-Errors bekommen `PreToolUse:<Tool> hook error:
[python3 <full-path>]: ` prepended zu dem was der Hook auf stderr emittiert. Live
2026-05-24 demonstriert in `src/logs/hook_firing.jsonl` plus parallel im
Monitor-Display. Der vollständige Path-Prefix ist visuelles Rauschen — der Hook-Name
ist redundant verfügbar aus dem Hook-Log, der Filesystem-Path ist nie aktionable
Info. **Diese eine Pattern-Klasse ist sicher strippbar.**

**Suspected aber unconfirmed:** weitere CC-added wrapper-Prefixe für andere
Error-Klassen (MCP-tool-error, parallel-cancel, validation-error). TBD via die
Investigation unten.

## Investigation Plan (sobald Daten da sind)

1. **Pattern-Discovery:** Grep über `src/logs/tool_errors.jsonl` Cluster nach
   distinct Error-Prefix-Shapes. Identifikation der CC-wrapper-Patterns vs
   agent-relevant content.
2. **Pro Pattern decide:** pure Noise (strippbar) vs context-bearing (keep). Bias
   conservativ — im Zweifel KEEP.
3. **Implementation:** Strip-Logic in der Proxy-Display-Komponente, NICHT in
   `tool_errors.jsonl` selbst. Audit-Log behält everything; nur Display zeigt
   gecleante Version.

## Implementation Constraints

- Strip MUST sein eindeutig — Pattern muss CC-wrapper-spezifisch sein, keine
  Collision-Risk mit agent-emitted content.
- Kein Strippen von Error-Content den der Agent fürs Debugging braucht.
- Strip happens at proxy display formatting layer, NICHT in `tool_errors.jsonl`
  itself (Audit-Log behält Originale für künftige Re-Analyse).
- Wenn ein Pattern unsicher → in OldThemes-Update dokumentieren, NICHT strippen.

## Data-Source Bootstrap

Aktueller State: `tool_errors.jsonl` startete 2026-05-24 ~23:32 UTC nach Monitor-Restart.
1-2 Wochen Akkumulation = ~2026-06-07. Bis dahin kein Action.

Cross-Reference: `hook_firing.jsonl` enthält bereits hook-originated Events; für
die Hook-Prefix-Strip-Frage haben wir damit schon Sample-Daten. Andere CC-Noise-Klassen
brauchen aber Daten aus `tool_errors.jsonl` die heute noch dünn sind.

## Sources

- `src/logs/tool_errors.jsonl` (Primärquelle für die Pattern-Discovery)
- `src/logs/hook_firing.jsonl` (Cross-Reference für hook-originated Errors)
- `decisions/OldThemes/audit_logging/architecture.md` (Audit-Log-Architektur)
- `decisions/OldThemes/tool_use_safety/2026-05-24_hook_classification_audit.md`
  (Hook-Inventar das die CC-wrapper-Surface beeinflusst)
