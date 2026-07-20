# CC Noise Prefix Strip — Tool Error Display Investigation (2026-05-24)

**Topic:** Proxy-Display-Layer Stripping von CC-added Noise-Prefixen aus
Tool-Error-Messages. Initial bekannter Fall: hook-block Errors mit
`PreToolUse:<Tool> hook error: [python3 <full-path>]: ` Wrapper. Ziel: generalisieren
auf andere CC Error-Class-Patterns die ähnliches Noise produzieren.

**Status:** ✅ CONCLUDED 2026-05-30 — empirical audit complete. No new strippable patterns.
`strip_hook_prefix.py` is sufficient. See Evidenz section below.

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

---

## Evidenz — Empirical Audit 2026-05-30

**Script:** `dev/tool_use_errors/A_error_cluster_audit.py`
**Report:** `dev/tool_use_errors/reports/2026-05-30_error_cluster_audit.md`
**Dataset:** `src/logs/tool_errors.jsonl` (495 entries, 2026-05-24 → 2026-05-30)
**Proxy logs scanned:** 65 `api_requests_*.jsonl` files

### Cluster Table (495 total entries)

| Bucket | Count | % | Verdict |
|--------|------:|---:|---------|
| `hook_prefixed` | 59 | 11.9% | HISTORICAL — pre-strip-hook; confirmed below |
| `tool_use_error` | 113 | 22.8% | KEEP |
| `exit_code_nonzero` | 202 | 40.8% | KEEP |
| `exit_code_0` | 0 | 0% | — |
| `rejection` | 12 | 2.4% | ALREADY_STRIPPED by proxy `_apply_first_pass` |
| `bare_guidance` | 109 | 22.0% | KEEP |

**bare_guidance hook breakdown** (hook guidance + CC Read errors without wrapper):
`block_broad_grep` 42, `block_except_pass` 16, `block_cd_drift` 10, `cc_Read_error_no_wrapper` 7,
`block_read_oversize (post-strip)` 7, `block_polling_loop` 6, `block_dev_imports_src` 6,
`block_venv_no_redirect` 5, `block_dangerous_kill` 5, `block_git_destructive` 2,
`block_read_oversize` 2, `block_bd_cli_worker` 1.

### Cross-Check: strip_hook_prefix.py reaches Anthropic

- `stripped_hook_error_prefix` confirmed in **2,970 requests** (4,892 modification items) across 65 proxy log files
- First occurrence: `2026-05-25T15:14:57.745Z`
- All 59 hook_prefixed entries predate first strip: latest `2026-05-25T01:26:48.049Z` < `2026-05-25T15:14:57`
- All 4 proxy files referenced by hook_prefixed entries are rotated (missing) — confirms pre-strip historical set

### Conclusion

**No new strippable patterns.** `strip_hook_prefix.py` is sufficient:
- Post-strip, hook guidance appears in `bare_guidance` WITHOUT the path-noise prefix — agent sees only actionable text
- `rejection` (12) already handled by `_apply_first_pass`
- `tool_use_error` (113) + `exit_code_nonzero` (202) + `bare_guidance` (109) are all agent-relevant KEEP

## Sources

- `src/logs/tool_errors.jsonl` (Primärquelle für die Pattern-Discovery)
- `src/logs/hook_firing.jsonl` (Cross-Reference für hook-originated Errors)
- `decisions/OldThemes/audit_logging/architecture.md` (Audit-Log-Architektur)
- `decisions/OldThemes/tool_use_safety/2026-05-24_hook_classification_audit.md`
  (Hook-Inventar das die CC-wrapper-Surface beeinflusst)
